# Official OpenSandbox MCP server, exposing sandbox lifecycle, command and file tools.
FROM python:3.12-slim
RUN pip install --no-cache-dir opensandbox-mcp==1.1.1
EXPOSE 8000
ENTRYPOINT ["opensandbox-mcp", "--transport", "streamable-http", "--host", "0.0.0.0", "--port", "8000", \
            "--domain", "opensandbox-server:8090", "--protocol", "http", "--use-server-proxy", \
            "--request-timeout-seconds", "120"]
