"""Typed FastMCP stdio client wrapper for HSE-Easy-Mock substrate."""

import json
import os
from collections.abc import Sequence
from strands.tools.mcp import MCPClient
from strands.tools.mcp.mcp_agent_tool import MCPAgentTool
from .schemas import (
    RegulatoryUpdateSummary,
    RegulatoryDocument,
    CitationVerificationResult,
    TDIServiceOffering
)

class MCPClientError(Exception):
    """Base exception for MCP client errors."""

class MCPClientNotConnectedError(MCPClientError):
    """Raised when calling methods before start() or outside with block."""

class MCPToolExecutionError(MCPClientError):
    """Raised when tool execution fails on the server side."""

class HSEMockMCPClient:
    """Mock MCP Client wrapping Strands MCPClient."""
    
    def __init__(self):
        self.server_dir = os.environ.get("HSE_MCP_SERVER_PATH", r"C:\Users\Saksham\Git\poc\AIAgents\mcp-server")
        clients = MCPClient.load_servers({
            "mock": {
                "command": "uv",
                "args": ["run", "--quiet", "--directory", self.server_dir, "fastmcp", "run", "server.py"],
                "env": {"PYTHONUNBUFFERED": "1"}
            }
        })
        self.mcp_client = clients[0]
        self._connected = False

    def start(self):
        """Explicitly start the MCP client subprocess."""
        self.mcp_client.__enter__()
        self._connected = True

    def stop(self):
        """Explicitly stop the MCP client subprocess."""
        self.mcp_client.__exit__(None, None, None)
        self._connected = False

    def __enter__(self):
        self.start()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.stop()

    def _ensure_connected(self):
        if not self._connected:
            raise MCPClientNotConnectedError("Client not connected. Call start() or use context manager.")

    def _call_tool(self, tool_name: str, args: dict) -> dict:
        self._ensure_connected()
        res = self.mcp_client.call_tool_sync(tool_name + "_id", tool_name, args)
        if res.get("status") == "error" or res.get("isError"):
            error_msg = res.get("content", [{"text": "Unknown error"}])[0]["text"]
            raise MCPToolExecutionError(error_msg)
        return json.loads(res["content"][0]["text"])

    def list_all_tools(self) -> list[MCPAgentTool]:
        """Return every substrate tool advertised by the connected server."""
        self._ensure_connected()
        return list(self.mcp_client.list_tools_sync())

    def load_scoped_tools(self, names: Sequence[str]) -> list[MCPAgentTool]:
        """Return only the named substrate tools, for per-agent tool scoping.

        The filter is applied per listing, so several scopes can be resolved
        off the one shared stdio session this client owns.
        """
        self._ensure_connected()
        return list(self.mcp_client.list_tools_sync(tool_filters={"allowed": list(names)}))

    def list_regulatory_updates(
        self, 
        source: str | None = None, 
        date_from: str | None = None, 
        date_to: str | None = None, 
        limit: int = 10
    ) -> list[RegulatoryUpdateSummary]:
        args = {"limit": limit}
        if source: args["source"] = source
        if date_from: args["date_from"] = date_from
        if date_to: args["date_to"] = date_to
        
        data = self._call_tool("list_regulatory_updates", args)
        return [RegulatoryUpdateSummary.model_validate(item) for item in data]

    def search_regulatory_docs(
        self, 
        query: str, 
        source: str | None = None, 
        topic: str | None = None, 
        sector: str | None = None
    ) -> list[RegulatoryUpdateSummary]:
        args = {"query": query}
        if source: args["source"] = source
        if topic: args["topic"] = topic
        if sector: args["sector"] = sector
        
        data = self._call_tool("search_regulatory_docs", args)
        return [RegulatoryUpdateSummary.model_validate(item) for item in data]

    def get_document_by_id(self, doc_id: str) -> RegulatoryDocument:
        data = self._call_tool("get_document_by_id", {"doc_id": doc_id})
        return RegulatoryDocument.model_validate(data)

    def verify_legal_citation(self, citation: str, source: str | None = None) -> CitationVerificationResult:
        args = {"citation": citation}
        if source: args["source"] = source
        data = self._call_tool("verify_legal_citation", args)
        return CitationVerificationResult.model_validate(data)

    def get_tdi_service_offerings(self, topic: str, sector: str | None = None) -> list[TDIServiceOffering]:
        args = {"topic": topic}
        if sector: args["sector"] = sector
        data = self._call_tool("get_tdi_service_offerings", args)
        return [TDIServiceOffering.model_validate(item) for item in data]
