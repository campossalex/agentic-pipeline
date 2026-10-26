# Zilliz's Milvus MCP server, built from source (not on PyPI) at a pinned commit.
FROM python:3.12-slim
RUN apt-get update && apt-get install -y --no-install-recommends git \
 && rm -rf /var/lib/apt/lists/*
ARG MCP_MILVUS_REF=6a2bff91fa629c0e62581be46ae7abba78f3a2c1
RUN pip install --no-cache-dir "fastmcp>=2.14.1,<3" "pymilvus>=2.6,<3" \
    "git+https://github.com/zilliztech/mcp-server-milvus@${MCP_MILVUS_REF}"
COPY serve.py /serve.py
EXPOSE 8000
ENTRYPOINT ["python", "/serve.py"]
