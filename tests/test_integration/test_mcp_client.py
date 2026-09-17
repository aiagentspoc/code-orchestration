import os
import pytest
from src.mcp_client import HSEMockMCPClient
from src.schemas import RegulatoryUpdateSummary, RegulatoryDocument, CitationVerificationResult

def test_mcp_client_connection_handshake():
    """Verify client connects over stdio and lists registered tools."""
    client = HSEMockMCPClient()
    client.start()
    try:
        tools = [tool.tool_name for tool in client.mcp_client.list_tools_sync()]
        assert "list_regulatory_updates" in tools
        assert "search_regulatory_docs" in tools
        assert "get_document_by_id" in tools
        assert "verify_legal_citation" in tools
        assert "get_tdi_service_offerings" in tools
    finally:
        client.stop()

def test_mcp_client_context_manager_lifecycle():
    """Verify context manager enters cleanly, exposes functional tools, and tears down subprocess on exit."""
    with HSEMockMCPClient() as client:
        tools = [tool.tool_name for tool in client.mcp_client.list_tools_sync()]
        assert "list_regulatory_updates" in tools

def test_mcp_client_absolute_path_resolution(monkeypatch):
    """Verify client resolves the server directory as an absolute path via HSE_MCP_SERVER_PATH."""
    monkeypatch.setenv("HSE_MCP_SERVER_PATH", "/tmp/custom-mcp-server")
    client = HSEMockMCPClient()
    assert client.server_dir == "/tmp/custom-mcp-server"

    monkeypatch.delenv("HSE_MCP_SERVER_PATH", raising=False)
    client2 = HSEMockMCPClient()
    assert client2.server_dir == r"C:\Users\Saksham\Git\poc\AIAgents\mcp-server"

def test_client_list_regulatory_updates():
    """Call list_regulatory_updates and verify returns List[RegulatoryUpdateSummary]."""
    with HSEMockMCPClient() as client:
        updates = client.list_regulatory_updates(source="INAIL", limit=5)
        assert isinstance(updates, list)
        assert len(updates) > 0
        for u in updates:
            assert isinstance(u, RegulatoryUpdateSummary)
            assert u.source == "INAIL"

def test_client_search_regulatory_docs():
    """Call search_regulatory_docs and verify returns List[RegulatoryUpdateSummary]."""
    with HSEMockMCPClient() as client:
        updates = client.search_regulatory_docs(query="calore")
        assert isinstance(updates, list)
        assert len(updates) > 0
        for u in updates:
            assert isinstance(u, RegulatoryUpdateSummary)

def test_client_get_document_by_id():
    """Call get_document_by_id and verify returns RegulatoryDocument."""
    with HSEMockMCPClient() as client:
        doc = client.get_document_by_id("gu-2024-dl-preposti")
        assert isinstance(doc, RegulatoryDocument)
        assert doc.content_markdown
        assert doc.key_obligations
        assert doc.penalties_summary

def test_client_verify_legal_citation_valid():
    """Call verify_legal_citation and assert is_valid is True."""
    with HSEMockMCPClient() as client:
        res = client.verify_legal_citation("D.Lgs. 81/2008 Art. 37")
        assert isinstance(res, CitationVerificationResult)
        assert res.is_valid is True
        assert res.status == "in_force"

def test_client_verify_legal_citation_invalid():
    """Call verify_legal_citation and assert is_valid is False."""
    with HSEMockMCPClient() as client:
        res = client.verify_legal_citation("Invalid Citation XYZ")
        assert isinstance(res, CitationVerificationResult)
        assert res.is_valid is False
        assert res.status == "unrecognized"

from src.mcp_client import MCPClientNotConnectedError, MCPToolExecutionError, MCPClientError
from src.schemas import TDIServiceOffering

def test_client_get_tdi_service_offerings():
    with HSEMockMCPClient() as client:
        res = client.get_tdi_service_offerings(topic="workplace_safety")
        assert isinstance(res, list)
        assert len(res) > 0
        assert isinstance(res[0], TDIServiceOffering)

def test_scoped_tool_lists_share_one_session():
    """Three per-agent tool scopes resolve off a single live substrate session."""
    with HSEMockMCPClient() as client:
        all_tools = client.list_all_tools()
        assert {t.tool_name for t in all_tools} == {
            "list_regulatory_updates",
            "search_regulatory_docs",
            "get_document_by_id",
            "verify_legal_citation",
            "get_tdi_service_offerings",
        }

        scout_scope = client.load_scoped_tools(
            ["list_regulatory_updates", "search_regulatory_docs", "get_document_by_id"]
        )
        writer_scope = client.load_scoped_tools(["get_tdi_service_offerings", "get_document_by_id"])
        qa_scope = client.load_scoped_tools(["verify_legal_citation"])

        assert {t.tool_name for t in scout_scope} == {
            "list_regulatory_updates",
            "search_regulatory_docs",
            "get_document_by_id",
        }
        assert {t.tool_name for t in writer_scope} == {"get_tdi_service_offerings", "get_document_by_id"}
        assert {t.tool_name for t in qa_scope} == {"verify_legal_citation"}

        # The same session still serves unscoped listings afterwards.
        assert len(client.list_all_tools()) == 5

def test_client_error_handling_nonexistent_doc():
    with HSEMockMCPClient() as client:
        with pytest.raises(MCPToolExecutionError):
            client.get_document_by_id("nonexistent-slug")

def test_client_not_started_error():
    client = HSEMockMCPClient()
    with pytest.raises(MCPClientNotConnectedError):
        client.get_tdi_service_offerings(topic="workplace_safety")
