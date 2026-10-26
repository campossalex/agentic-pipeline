"""Run mcp-server-milvus over Streamable HTTP on 0.0.0.0.

The upstream CLI hard-codes a localhost bind, which other containers cannot reach.
"""
import os

from mcp.server.transport_security import TransportSecuritySettings
from mcp_server_milvus import server

server.mcp.config = {
    "milvus_uri": os.environ.get("MILVUS_URI", "http://milvus:19530"),
    "milvus_token": os.environ.get("MILVUS_TOKEN"),
    "db_name": os.environ.get("MILVUS_DB", "default"),
}
server.mcp.settings.host = "0.0.0.0"
server.mcp.settings.port = 8000
# Only agentgateway calls this server, using the compose service name as Host.
server.mcp.settings.transport_security = TransportSecuritySettings(
    allowed_hosts=["mcp-milvus", "mcp-milvus:*", "localhost:*"],
)
server.mcp.run(transport="streamable-http")
