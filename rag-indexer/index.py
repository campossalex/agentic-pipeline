"""Index /workspace/docs into Milvus for the knowledge-search skill.

Creates the `workspace_docs` collection with a BM25 function, so Milvus derives the
sparse vectors from raw text. The agent then searches it through the Milvus MCP
server's `milvus_text_search` tool, which queries the `sparse` field, without
having to produce embeddings itself.
"""
import os
import re
import sys
import time
from pathlib import Path

from pymilvus import DataType, Function, FunctionType, MilvusClient

MILVUS_URI = os.environ.get("MILVUS_URI", "http://milvus:19530")
DOCS_DIR = Path(os.environ.get("DOCS_DIR", "/workspace/docs"))
COLLECTION = os.environ.get("COLLECTION", "workspace_docs")
MAX_CHARS = 1200


def chunk_markdown(text: str) -> list[str]:
    """Split on headings, then pack paragraphs up to MAX_CHARS."""
    sections = re.split(r"(?m)^(?=#{1,3} )", text)
    chunks: list[str] = []
    carry = ""  # a heading-only section (e.g. the title) is prepended to the next one
    for section in sections:
        section = carry + section
        if len(section.strip()) < 120:
            carry = section
            continue
        carry = ""
        buf = ""
        for para in re.split(r"\n\s*\n", section):
            if buf and len(buf) + len(para) > MAX_CHARS:
                chunks.append(buf.strip())
                buf = ""
            buf += para + "\n\n"
        if buf.strip():
            chunks.append(buf.strip())
    if carry.strip():
        chunks.append(carry.strip())
    return chunks


def connect() -> MilvusClient:
    for attempt in range(60):
        try:
            client = MilvusClient(uri=MILVUS_URI)
            client.list_collections()
            return client
        except Exception as exc:  # Milvus takes a while on first boot
            print(f"waiting for milvus ({attempt}): {exc}", flush=True)
            time.sleep(5)
    sys.exit("milvus not reachable")


def main() -> None:
    client = connect()
    if client.has_collection(COLLECTION):
        client.drop_collection(COLLECTION)

    schema = client.create_schema(auto_id=True, enable_dynamic_field=False)
    schema.add_field("id", DataType.INT64, is_primary=True)
    schema.add_field("text", DataType.VARCHAR, max_length=8192, enable_analyzer=True)
    schema.add_field("source", DataType.VARCHAR, max_length=512)
    schema.add_field("sparse", DataType.SPARSE_FLOAT_VECTOR)
    schema.add_function(Function(
        name="text_bm25",
        function_type=FunctionType.BM25,
        input_field_names=["text"],
        output_field_names=["sparse"],
    ))
    index_params = client.prepare_index_params()
    index_params.add_index(field_name="sparse", index_type="SPARSE_INVERTED_INDEX", metric_type="BM25")
    client.create_collection(COLLECTION, schema=schema, index_params=index_params)

    rows = []
    for path in sorted(DOCS_DIR.rglob("*.md")):
        rel = str(path.relative_to(DOCS_DIR.parent))
        for chunk in chunk_markdown(path.read_text(encoding="utf-8")):
            rows.append({"text": chunk, "source": rel})
    if rows:
        client.insert(COLLECTION, rows)
    client.load_collection(COLLECTION)
    print(f"indexed {len(rows)} chunks from {DOCS_DIR} into '{COLLECTION}'", flush=True)


if __name__ == "__main__":
    main()
