"""Load the store documents and split them into chunks."""
from pathlib import Path

import yaml
from langchain_core.documents import Document
from langchain_text_splitters import MarkdownHeaderTextSplitter, RecursiveCharacterTextSplitter

from shopmind.config import CHUNK_OVERLAP, CHUNK_SIZE


def load_documents(docs_dir: Path) -> list[Document]:
    """Read every Markdown file and turn its YAML frontmatter into metadata."""
    docs = []
    for path in sorted(docs_dir.rglob("*.md")):
        text = path.read_text(encoding="utf-8")
        _, front, body = text.split("---", 2)
        meta = yaml.safe_load(front)
        meta["source"] = str(path.relative_to(docs_dir))
        docs.append(Document(page_content=body.strip(), metadata=meta))
    return docs


def chunk_documents(docs: list[Document]) -> list[Document]:
    """Split by Markdown sections first, then by size.

    Splitting on headers keeps each chunk about one topic (for example
    "Refunds" or "Shipping fees"). Long sections are then cut to CHUNK_SIZE
    with some overlap so a sentence on the border is not lost. The section
    path is put in front of each chunk so it still makes sense on its own.
    """
    header_splitter = MarkdownHeaderTextSplitter(
        headers_to_split_on=[("#", "h1"), ("##", "h2")], strip_headers=True
    )
    size_splitter = RecursiveCharacterTextSplitter(
        chunk_size=CHUNK_SIZE, chunk_overlap=CHUNK_OVERLAP, separators=["\n\n", "\n", ". ", " "]
    )

    chunks = []
    for doc in docs:
        sections = header_splitter.split_text(doc.page_content)
        index = 0
        for section in sections:
            heading = " > ".join(v for k, v in section.metadata.items() if k in ("h1", "h2"))
            for piece in size_splitter.split_text(section.page_content):
                text = f"{heading}\n\n{piece}" if heading else piece
                meta = {**doc.metadata, "section": heading, "chunk_index": index}
                chunks.append(Document(page_content=text, metadata=meta))
                index += 1
    return chunks
