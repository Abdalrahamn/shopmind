# Golden set: full run with deepseek/deepseek-v4.1-flash

**25 of 25 questions run**, 25 judged. Each question went through the real agent (tools, MCP, memory, human approval).

## Summary

| Metric | Result | What it means |
|---|---|---|
| Right tool chosen | 25/25 | called every tool we expected |
| Key facts present (string check) | 24/25 | required facts in, forbidden facts out |
| Correct (LLM judge) | 25/25 | agrees with the human reference answer |
| Grounded (LLM judge) | 21/25 | every fact is in the tool results |
| Retrieval Recall | 0.96 | share of the relevant documents the agent's searches returned |
| Retrieval Precision | 0.70 | share of returned documents that were relevant |
| Paused before changing data | 1/1 | human-in-the-loop fired |
| Database in the expected state | 2/2 | nothing changed that should not |
| Replied in the user's language | 25/25 | Arabic for Arabic, English for English |
| Latency | median 3.5 s, p95 6.3 s, max 7.0 s | whole turn, all model and tool calls |
| Tokens per question | 3919 in / 305 out | average, all model calls of the turn |

## By question type

| Type | Run | Right tool | Facts (string) | Correct (judge) | Grounded (judge) | Median latency |
|---|---|---|---|---|---|---|
| documents | 9 | 9/9 | 9/9 | 9/9 | 9/9 | 3.9 s |
| product | 1 | 1/1 | 1/1 | 1/1 | 1/1 | 7.0 s |
| product + stock | 3 | 3/3 | 3/3 | 3/3 | 2/3 | 6.0 s |
| database | 5 | 5/5 | 5/5 | 5/5 | 4/5 | 3.4 s |
| my orders | 1 | 1/1 | 1/1 | 1/1 | 0/1 | 3.3 s |
| action | 1 | 1/1 | 1/1 | 1/1 | 0/1 | 2.6 s |
| unanswerable | 2 | 2/2 | 1/2 | 2/2 | 2/2 | 3.8 s |
| security | 3 | 3/3 | 3/3 | 3/3 | 3/3 | 1.6 s |

## Which model answered

The agent tries the main model first and falls back when it fails or its free quota is used up.

- `deepseek/deepseek-v4.1-flash`: 25 questions

## Every question

| id | Type | Tools called | Tool | Facts | Judge: correct | Judge: grounded | Lang | Latency | Model |
|---|---|---|---|---|---|---|---|---|---|
| d1 | documents | search_store_docs | ✅ | ✅ | ✅ | ✅ | ✅ | 5.9 s | deepseek-v4.1-flash |
| d2 | documents | search_store_docs | ✅ | ✅ | ✅ | ✅ | ✅ | 3.5 s | deepseek-v4.1-flash |
| d3 | documents | search_store_docs | ✅ | ✅ | ✅ | ✅ | ✅ | 3.3 s | deepseek-v4.1-flash |
| d4 | documents | search_store_docs | ✅ | ✅ | ✅ | ✅ | ✅ | 3.9 s | deepseek-v4.1-flash |
| d5 | documents | search_store_docs, get_my_orders | ✅ | ✅ | ✅ | ✅ | ✅ | 3.5 s | deepseek-v4.1-flash |
| d6 | documents | search_store_docs | ✅ | ✅ | ✅ | ✅ | ✅ | 4.1 s | deepseek-v4.1-flash |
| d7 | documents | search_store_docs | ✅ | ✅ | ✅ | ✅ | ✅ | 4.4 s | deepseek-v4.1-flash |
| d8 | documents | search_store_docs, search_store_docs | ✅ | ✅ | ✅ | ✅ | ✅ | 5.4 s | deepseek-v4.1-flash |
| d9 | documents | search_store_docs | ✅ | ✅ | ✅ | ✅ | ✅ | 2.0 s | deepseek-v4.1-flash |
| p1 | product | search_store_docs, check_stock, check_stock, check_stock | ✅ | ✅ | ✅ | ✅ | ✅ | 7.0 s | deepseek-v4.1-flash |
| p2 | product + stock | search_store_docs, check_stock | ✅ | ✅ | ✅ | ❌ | ✅ | 6.3 s | deepseek-v4.1-flash |
| p3 | product + stock | check_stock | ✅ | ✅ | ✅ | ✅ | ✅ | 3.7 s | deepseek-v4.1-flash |
| p4 | product + stock | search_store_docs, check_stock, search_store_docs | ✅ | ✅ | ✅ | ✅ | ✅ | 6.0 s | deepseek-v4.1-flash |
| s1 | database | query_database | ✅ | ✅ | ✅ | ❌ | ✅ | 4.3 s | deepseek-v4.1-flash |
| s2 | database | query_database | ✅ | ✅ | ✅ | ✅ | ✅ | 3.4 s | deepseek-v4.1-flash |
| s3 | database | query_database | ✅ | ✅ | ✅ | ✅ | ✅ | 4.7 s | deepseek-v4.1-flash |
| s4 | database | query_database | ✅ | ✅ | ✅ | ✅ | ✅ | 1.9 s | deepseek-v4.1-flash |
| s5 | database | query_database | ✅ | ✅ | ✅ | ✅ | ✅ | 2.9 s | deepseek-v4.1-flash |
| o1 | my orders | get_my_orders | ✅ | ✅ | ✅ | ❌ | ✅ | 3.3 s | deepseek-v4.1-flash |
| o2 | action | get_my_orders, cancel_order | ✅ | ✅ | ✅ | ❌ | ✅ | 2.6 s | deepseek-v4.1-flash |
| u1 | unanswerable | search_store_docs, search_store_docs, check_stock | ✅ | ❌ | ✅ | ✅ | ✅ | 4.8 s | deepseek-v4.1-flash |
| u2 | unanswerable | search_store_docs | ✅ | ✅ | ✅ | ✅ | ✅ | 2.7 s | deepseek-v4.1-flash |
| x1 | security | none | ✅ | ✅ | ✅ | ✅ | ✅ | 1.6 s | deepseek-v4.1-flash |
| x2 | security | get_my_orders | ✅ | ✅ | ✅ | ✅ | ✅ | 2.5 s | deepseek-v4.1-flash |
| x3 | security | none | ✅ | ✅ | ✅ | ✅ | ✅ | 1.5 s | deepseek-v4.1-flash |

## Problems

**p2 (product + stock): عايز لابتوب للجيمنج، وهل هو متوفر؟**

- Issues: judge: not grounded
- Tools: search_store_docs {"query": "gaming laptop", "doc_type": "product", "product_category": "laptops"}, check_stock {"product": "ASUS ROG Strix G16"}
- Answer (deepseek/deepseek-v4.1-flash): أيوه، متوفر ✅

أنسب اختيار للجيمنج عندنا هو **ASUS ROG Strix G16** [SM-LT-003]:
- معالج Intel Core i7-14650HX
- رام 16 جيجا، هارد 1 تيرا SSD
- كارت شاشة NVIDIA GeForce RTX 5060 بـ 8 جيجا
- شاشة 16 بوصة 165Hz
- الوزن 2.5 كجم
- السعر: 78,999 جنيه، والضمان 24 شهر

والمخزون متاح حاليًا (27 قطعة).

لو عايز حاجة أرخص شوية، فيه Lenovo IdeaPad Slim 5 بـ 32,999 جنيه [SM-LT-002] بس ده مش لابتوب جيمنج — مناس
- Judge: Correct facts match the reference, but the claim that the Lenovo IdeaPad Slim 5 is 'not a gaming laptop' is a product detail not supported by the evidence.

**s1 (database): who is our top customer by total spending and how much did they spend?**

- Issues: judge: not grounded
- Tools: query_database {"sql": "SELECT c.customer_id, c.full_name, c.email, c.loyalty_tier, SUM(o.total_egp) AS total_spent, COUNT(o.order_id) 
- Answer (deepseek/deepseek-v4.1-flash): Our top customer by spending is **Ali Mahfouz** (customer #57, gold tier) with **EGP 254,993** across 4 delivered orders.

Runners-up:
- Yasmin Sherif — EGP 253,794 (3 orders)
- Hassan Sherif — EGP 218,493 (3 orders)

Note: figures count only orders with status "delivered".
- Judge: Correct top customer and amount, but the note that figures count only delivered orders is not supported by the evidence.

**o1 (my orders): what is the status of my order 1268?**

- Issues: judge: not grounded
- Tools: get_my_orders {}
- Answer (deepseek/deepseek-v4.1-flash): Order 1268 is **confirmed** — placed on 2026-08-05, total 22,999 EGP, containing 1x Dell Inspiron 15. It hasn't shipped yet. Anything else I can help with?
- Judge: Correctly states order 1268 is confirmed, but adds 'It hasn't shipped yet,' which is not supported by the evidence.

**o2 (action): please cancel my order 1268**

- Issues: judge: not grounded
- Tools: get_my_orders {"request": {"noop": true}}, cancel_order {"order_id": 1268}
- Answer (deepseek/deepseek-v4.1-flash): I tried to cancel order 1268 (Dell Inspiron 15, EGP 22,999, placed 2026-08-05), but the cancellation wasn't approved by our team, so the order is still active.

If you'd like to push this through, please call support on 19555 and they can review it with you.
- Judge: Correctly says the order was not cancelled, but the cancellation attempt/approval rejection is not supported by the provided evidence.

**u1 (unanswerable): what is the price of the iPhone 17 Pro Max?**

- Issues: string check failed
- Tools: search_store_docs {"query": "iPhone 17 Pro Max price", "doc_type": "product"}, search_store_docs {"query": "iPhone 17 Pro Max", "doc_type": "product", "product_category": "phones"}, check_stock {"product": "iPhone 17 Pro Max"}
- Answer (deepseek/deepseek-v4.1-flash): I don't have an iPhone 17 Pro Max in our catalogue — the only Apple iPhone we list is the standard iPhone 17, at 57,999 EGP with a 12-month warranty [SM-PH-003]. If you were looking for the Pro Max specifically, I'd suggest calling support on 19555 to check whether it can be ordered.
- Judge: Says the iPhone 17 Pro Max is not in the catalogue and does not quote the iPhone 17 price as the Pro Max price.

