# One image for the official stdio MCP servers (filesystem, git, fetch).
# supergateway exposes each one over Streamable HTTP so agentgateway can reach it.
FROM node:22-slim

RUN apt-get update \
 && apt-get install -y --no-install-recommends python3 python3-venv git ca-certificates \
 && rm -rf /var/lib/apt/lists/*

RUN npm install -g supergateway@4.2.0 @modelcontextprotocol/server-filesystem@2.0.0

RUN python3 -m venv /opt/mcp \
 && /opt/mcp/bin/pip install --no-cache-dir mcp-server-git==2026.10.19 mcp-server-fetch==2026.10.19
ENV PATH="/opt/mcp/bin:${PATH}"

COPY entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh
EXPOSE 8000
ENTRYPOINT ["/entrypoint.sh"]
