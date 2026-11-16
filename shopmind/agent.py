"""Phase 4: the ShopMind agent.

One agent, built with LangChain v1's `create_agent`, that decides for each
question where the answer lives:

    store documents  -> search_store_docs     (RAG, Phases 1 to 3)
    numbers/records  -> query_database        (SQL, staff only)
    my own orders    -> get_my_orders
    live stock       -> check_stock           (comes from the MCP server)
    cancel an order  -> cancel_order          (pauses for human approval)

Pieces from the LangChain Essentials course, and where they are below:
    tools + MCP          build_agent()
    memory               the checkpointer + thread_id
    dynamic prompt       role_prompt()
    human-in-the-loop    HumanInTheLoopMiddleware
    structured output    SupportReply
    streaming            run_turn()
"""
from __future__ import annotations

import re
import sys
import time
from typing import Literal

from langchain.agents import create_agent
from langchain.agents.middleware import (AgentMiddleware, HumanInTheLoopMiddleware, ModelRequest,
                                         ToolCallLimitMiddleware, dynamic_prompt)
from langchain.agents.structured_output import ToolStrategy
from langchain_mcp_adapters.client import MultiServerMCPClient
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.errors import GraphBubbleUp
from langgraph.types import Command
from pydantic import BaseModel, Field

from shopmind.config import AGENT_FALLBACKS, AGENT_MODEL, ROOT
from shopmind.llm import chat_model
from shopmind.tools import LOCAL_TOOLS, UserContext

BASE_PROMPT = """You are ShopMind, the assistant of ShopMind Electronics, an online electronics store in Egypt.

How to work:
- Policies, how things work, product advice: call search_store_docs. Answer only from what it returns
  and cite the document ids in square brackets, for example [POL-001].
- Whether a product is available: call check_stock. Never guess stock from a product page.
- When a question needs two sources (for example "a phone under 15,000 that is in stock"), call both tools.
- To cancel an order, call cancel_order with the order id. A human approves it before it runs.
- If the tools do not give you the answer, say you do not know and suggest calling support on 19555.
  Never invent prices, dates, stock or policies.
- Search queries: keep the exact product names and key words from the question (for example
  "Pixel 10a return", not just "return policy"). A question about a specific product needs that product's page.
- Search at most three times per question. If the answer is still missing, stop and say you do not know.
- A rule on a product's own page (for example a clearance item is final sale) wins over the general policy.
- For a yes/no question, decide the final answer first and start with it. Never open with "Yes" and
  then add an exception that makes the real answer "No".
- Be short and friendly.
"""

CUSTOMER_RULES = """
You are talking to a customer: {name} (customer id {customer_id}).
- For their orders use get_my_orders. You cannot see other customers' data and must not try.
- You cannot run SQL for customers.
"""

STAFF_RULES = """
You are talking to a staff member: {name}.
- For numbers and records (sales, top customers, order counts) write a SQL SELECT and call query_database.
- You may show business data to staff. Format amounts in EGP.
"""


@dynamic_prompt
def role_prompt(request: ModelRequest) -> str:
    """Dynamic prompt: built again before every model call from who is logged in."""
    ctx: UserContext = request.runtime.context
    rules = STAFF_RULES if ctx.role == "staff" else CUSTOMER_RULES
    return BASE_PROMPT + rules.format(name=ctx.name, customer_id=ctx.customer_id) + language_rule(request.messages)


def language_rule(messages) -> str:
    """Decide the reply language in code and state it as a fact.

    The golden evaluation showed the smaller models replying in Arabic to English
    questions when the prompt only said "reply in the user's language". Detecting
    the language here (any Arabic letter in the last user message) is exact and free.
    """
    last_user = next((m.content for m in reversed(messages) if m.type == "human"), "")
    if re.search("[\u0600-\u06FF]", str(last_user)):
        return "\nThe user's last message is in Arabic. Write your answer in Egyptian Arabic."
    return "\nThe user's last message is in English. Write your answer in English only, not Arabic."


class SupportReply(BaseModel):
    """The agent's final reply. A fixed shape, so the app can show each part separately."""
    answer: str = Field(description="The reply to the user, with [doc_id] citations after facts from documents")
    sources: list[str] = Field(default_factory=list, description="Document ids cited, e.g. POL-001")
    route: Literal["documents", "database", "stock", "action", "mixed", "none"] = Field(
        description="Where the answer came from: documents (search), database (SQL or orders), stock, "
                    "action (an order was changed), mixed (more than one), none (could not answer)")


def _model(name: str):
    return chat_model(name)


class FallbackWithCooldown(AgentMiddleware):
    """Model fallback with a "circuit breaker".

    LangChain's ModelFallbackMiddleware tries the main model first on EVERY model call. When the main
    model's free quota is used up, each call waits for it to fail before a fallback answers, and one
    turn has 2 to 4 model calls: the Phase 5 evaluation measured a 28 s median turn because of this.

    Here a model that fails is skipped for COOLDOWN seconds, so the wait is paid once, not on every call.
    After the cooldown it is tried again (the quota may be back).
    """
    COOLDOWN = 300  # seconds

    def __init__(self, *models):
        super().__init__()
        self.models = list(models)   # in order of preference; the first is the main model
        self.skip_until = {}         # position in the list -> time when we may try that model again

    def _order(self):
        now = time.monotonic()
        ready = [i for i in range(len(self.models)) if self.skip_until.get(i, 0) <= now]
        return ready or list(range(len(self.models)))  # all cooling down: try them all anyway

    async def awrap_model_call(self, request, handler):
        last_error = None
        for i in self._order():
            try:
                return await handler(request.override(model=self.models[i]))
            except GraphBubbleUp:      # not an error: this is how the agent pauses for human approval
                raise
            except Exception as e:     # quota, overload, timeout: remember it and move on
                self.skip_until[i] = time.monotonic() + self.COOLDOWN
                last_error = e
        raise last_error

    def wrap_model_call(self, request, handler):
        last_error = None
        for i in self._order():
            try:
                return handler(request.override(model=self.models[i]))
            except GraphBubbleUp:
                raise
            except Exception as e:
                self.skip_until[i] = time.monotonic() + self.COOLDOWN
                last_error = e
        raise last_error


async def build_agent(checkpointer=None):
    """Create the agent. Async because the MCP tools are fetched from the server first."""
    mcp_client = MultiServerMCPClient({
        "inventory": {"transport": "stdio", "command": sys.executable,
                      "args": [str(ROOT / "shopmind" / "mcp_server.py")]},
    })
    mcp_tools = await mcp_client.get_tools()          # -> [check_stock]

    return create_agent(
        model=_model(AGENT_MODEL),
        tools=[*LOCAL_TOOLS, *mcp_tools],
        context_schema=UserContext,                    # who is logged in; tools and the prompt read it
        response_format=ToolStrategy(SupportReply),    # structured final answer
        checkpointer=checkpointer or InMemorySaver(),  # memory: saves the conversation per thread_id
        middleware=[
            role_prompt,
            # The free Gemini tier allows ~20 requests per model per day: move to the next model on failure,
            # and stop retrying a failed model for a few minutes.
            FallbackWithCooldown(*[_model(m) for m in [AGENT_MODEL, *AGENT_FALLBACKS]]),
            # Stop search loops: the evaluation caught 10 searches for one unanswerable question.
            ToolCallLimitMiddleware(tool_name="search_store_docs", run_limit=3),
            # Pause before cancel_order runs and wait for a human decision.
            HumanInTheLoopMiddleware(interrupt_on={"cancel_order": True}),
        ],
    )


async def run_turn(agent, user_input, thread_id: str, context: UserContext, callbacks=None, tags=None):
    """Run one turn and yield simple events while it happens (streaming).

    user_input is either the user's text, or a decision on a paused action:
        {"type": "approve"}  or  {"type": "reject", "message": "why"}

    Events:
        {"type": "tool_call", "name", "args"}
        {"type": "tool_result", "name", "content"}
        {"type": "approval_needed", "name", "args"}   the agent is paused
        {"type": "answer", "reply": SupportReply, "model": name of the model that answered}
    """
    # callbacks: e.g. a token counter. tags: labels that show up on the trace in LangSmith.
    config = {"configurable": {"thread_id": thread_id}, "callbacks": callbacks or [], "tags": tags or []}
    if isinstance(user_input, dict):
        payload = Command(resume={"decisions": [user_input]})
    else:
        payload = {"messages": [{"role": "user", "content": user_input}]}

    model_used = "unknown"  # which model actually answered (the fallback may have stepped in)
    async for update in agent.astream(payload, config, context=context, stream_mode="updates"):
        for node, data in update.items():
            if node == "__interrupt__":
                for request in data[0].value["action_requests"]:
                    yield {"type": "approval_needed", "name": request["name"], "args": request["args"]}
                continue
            if "HumanInTheLoop" in node:
                continue  # after approval this node repeats the tool call we already showed
            for msg in (data or {}).get("messages", []):
                if msg.type == "ai":
                    model_used = msg.response_metadata.get("model_name", model_used)
                    for call in msg.tool_calls:
                        if call["name"] != SupportReply.__name__:
                            yield {"type": "tool_call", "name": call["name"], "args": call["args"]}
                elif msg.type == "tool" and msg.name != SupportReply.__name__:
                    yield {"type": "tool_result", "name": msg.name, "content": str(msg.content)}
            if (data or {}).get("structured_response") is not None:
                yield {"type": "answer", "reply": data["structured_response"], "model": model_used}
