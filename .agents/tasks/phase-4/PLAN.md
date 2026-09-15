# Phase 4 Implementation Plan: Substrate MCP Stdio Client

## 1. Context & Task Scope
**Phase 4** establishes a robust, typed Python client (`src/mcp_client.py`) connecting the HSE Easy pipeline to the `hse-easy-mock` MCP server over `stdio`. The client wraps the `strands-agents` SDK's native `MCPClient`, abstracting the underlying JSON-RPC protocol and deserializing tool responses strictly into pre-defined Pydantic v2 schemas (`src.schemas`). 

In addition to providing typed synchronous wrapper methods for procedural calls in the orchestrator, the client enables direct tool consumption by Strands agents in Phase 5: following canonical Strands documentation, the `MCPClient` instance can be passed directly to `Agent(tools=[...])`. This guarantees that upper layers (Agents and Orchestrator) interact seamlessly and predictably with the substrate, fulfilling the architectural rule of strict substrate isolation ("Code Owns the Flow").

## 2. Prerequisites
- Python 3.11 environment initialized via `uv`.
- `tests/test_integration/test_substrate_compatibility.py` confirms that the mock server's payloads successfully roundtrip with Pydantic v2 models.
- `strands-agents` package is installed and provides `strands.tools.mcp.mcp_client.MCPClient`.
- The local `hse-easy-mock` server path is configured as an absolute path via `HSE_MCP_SERVER_PATH` (defaulting to `C:\Users\Saksham\Git\poc\AIAgents\mcp-server`), executable via `uv run --directory <HSE_MCP_SERVER_PATH> fastmcp run server.py`.

## 3. Strict TDD Strategy

### Batch 1: MCP Client Configuration, Stdio Connection Handshake & Lifecycle Management
- **Objective:** Configure stdio parameters using the absolute path from `HSE_MCP_SERVER_PATH`, verify connection handshake, and implement the context manager lifecycle (`__enter__` and `__exit__`) and explicit lifecycle methods (`start()` and `stop()`).
- **Target Tests in `tests/test_integration/test_mcp_client.py`:**
  - `test_mcp_client_connection_handshake`: Verify client successfully connects over stdio and lists registered tools (`list_regulatory_updates`, `search_regulatory_docs`, `get_document_by_id`, `verify_legal_citation`, `get_tdi_service_offerings`).
  - `test_mcp_client_context_manager_lifecycle`: Verify `with HSEMockMCPClient() as client:` enters cleanly, exposes functional tools, and tears down subprocess on exit.
  - `test_mcp_client_absolute_path_resolution`: Verify client resolves the server directory as an absolute path via `HSE_MCP_SERVER_PATH` (default: `C:\Users\Saksham\Git\poc\AIAgents\mcp-server`).
- **Target Implementation in `src/mcp_client.py`:**
  - `HSEMockMCPClient` wrapping `strands.tools.mcp.MCPClient`.
  - Configured with `MCPServerConfig` (`command="uv"`, `args=["run", "--directory", server_dir, "fastmcp", "run", "server.py"]`).
  - `server_dir` always resolved as an absolute path via `os.environ.get("HSE_MCP_SERVER_PATH", r"C:\Users\Saksham\Git\poc\AIAgents\mcp-server")`.

### Batch 2: Regulatory Update Queries (`list_regulatory_updates` & `search_regulatory_docs`)
- **Objective:** Implement typed synchronous query methods deserializing responses into `List[RegulatoryUpdateSummary]`.
- **Target Tests in `tests/test_integration/test_mcp_client.py`:**
  - `test_client_list_regulatory_updates`: Call `list_regulatory_updates(source="INAIL", limit=5)` and verify returns `List[RegulatoryUpdateSummary]`.
  - `test_client_search_regulatory_docs`: Call `search_regulatory_docs(query="calore")` and verify returns `List[RegulatoryUpdateSummary]`.
- **Target Implementation in `src/mcp_client.py`:**
  - `def list_regulatory_updates(self, source: Optional[str] = None, date_from: Optional[str] = None, date_to: Optional[str] = None, limit: int = 10) -> List[RegulatoryUpdateSummary]`
  - `def search_regulatory_docs(self, query: str, source: Optional[str] = None, topic: Optional[str] = None, sector: Optional[str] = None) -> List[RegulatoryUpdateSummary]`

### Batch 3: Document Retrieval & Legal Citation Verification (`get_document_by_id` & `verify_legal_citation`)
- **Objective:** Implement typed methods for full document retrieval and legal citation audits.
- **Target Tests in `tests/test_integration/test_mcp_client.py`:**
  - `test_client_get_document_by_id`: Call `get_document_by_id("gu-2024-dl-preposti")` and verify returns `RegulatoryDocument` with markdown content, obligations, and penalties.
  - `test_client_verify_legal_citation_valid`: Call `verify_legal_citation("D.Lgs. 81/2008 Art. 37")` and assert `is_valid is True` and `status == "in_force"`.
  - `test_client_verify_legal_citation_invalid`: Call `verify_legal_citation("Invalid Citation XYZ")` and assert `is_valid is False` and `status == "unrecognized"`.
- **Target Implementation in `src/mcp_client.py`:**
  - `def get_document_by_id(self, doc_id: str) -> RegulatoryDocument`
  - `def verify_legal_citation(self, citation: str, source: Optional[str] = None) -> CitationVerificationResult`

### Batch 4: Commercial Offerings Retrieval, Strands Agent Tool Binding & Error Guardrails
- **Objective:** Implement TDI lead generation retrieval, provide direct Strands agent tool compatibility, and wrap transport/runtime exceptions in descriptive exceptions.
- **Target Tests in `tests/test_integration/test_mcp_client.py`:**
  - `test_client_get_tdi_service_offerings`: Call `get_tdi_service_offerings(topic="workplace_safety")` and verify returns `List[TDIServiceOffering]`.
  - `test_client_strands_tool_provider_compatibility`: Verify that `client.mcp_client` (or `client` itself via `load_tools`) can be provided directly to a Strands `Agent(tools=[...])` per canonical Strands documentation.
  - `test_client_error_handling_nonexistent_doc`: Call `get_document_by_id("nonexistent-slug")` and verify raises descriptive `MCPToolExecutionError`.
  - `test_client_not_started_error`: Calling methods before `start()` or outside `with` context raises `MCPClientNotConnectedError`.
- **Target Implementation in `src/mcp_client.py`:**
  - `def get_tdi_service_offerings(self, topic: str, sector: Optional[str] = None) -> List[TDIServiceOffering]`
  - Expose `client.mcp_client` (and implement `load_tools()` delegating to the underlying `MCPClient`) so the client can be supplied directly as tools to Strands `Agent(tools=[...])`.
  - Custom exceptions: `MCPClientError`, `MCPClientNotConnectedError`, `MCPToolExecutionError`.

## 4. Proposed Changes & Specifications

### Target Files:
1. **`src/mcp_client.py`**:
   - Production wrapper `HSEMockMCPClient`.
   - Complete type annotations (PEP 484/585/604).
   - Top-of-file imports (PEP 8 E402).
   - Absolute path resolution for `mcp-server` directory via `HSE_MCP_SERVER_PATH` (defaulting to absolute `C:\Users\Saksham\Git\poc\AIAgents\mcp-server`).
   - Clean lifecycle management (`__enter__`, `__exit__`, `start()`, `stop()`).
   - Synchronous typed wrapper methods returning validated Pydantic v2 models.
   - Strands Agent tool compatibility: expose the underlying `MCPClient` instance and/or implement `load_tools()` so Strands agents can consume tools directly.
2. **`tests/test_integration/test_mcp_client.py`**:
   - Full integration test suite exercising all 4 batches against the live local stdio server.
3. **`src/__init__.py`**:
   - Export `HSEMockMCPClient`, `MCPClientError`, `MCPClientNotConnectedError`, `MCPToolExecutionError`.

## 5. Architectural & Quality Audit Checklist
- [x] **"Code Owns the Flow" (Rule 1):** `HSEMockMCPClient` exposes pure deterministic procedural Python methods. Zero autonomous routing or emergent loops.
- [x] **Strict Schemas (Rule 2):** All returned data structures are validated Pydantic v2 schemas (`RegulatoryUpdateSummary`, `RegulatoryDocument`, `CitationVerificationResult`, `TDIServiceOffering`). Zero raw dict leaks.
- [x] **Substrate Isolation:** FastMCP stdio transport and JSON-RPC call serialization are strictly encapsulated in `src/mcp_client.py`.
- [x] **Agent Reusability & Strands Tool Binding (Phase 5 Compatibility):** The underlying Strands `MCPClient` can be provided directly to Strands `Agent(tools=[...])` as demonstrated in Strands documentation.
- [x] **Absolute Path Resolution:** Always uses absolute path via `HSE_MCP_SERVER_PATH` with fallback to `C:\Users\Saksham\Git\poc\AIAgents\mcp-server`, eliminating relative path ambiguity.
- [x] **Strict TDD (Rule 7):** Incremental Red-Green-Refactor execution across 4 small testable batches.

## 6. Questions & Decisions for Human Approval
1. **Synchronous vs Asynchronous Interface:**
   - **Decision:** Confirmed. Keep wrapper methods synchronous (`call_tool_sync`), aligning with the procedural orchestrator flow in `src/orchestrator.py`.
2. **Substrate Server Path Resolution:**
   - **Decision:** Confirmed. Always use an absolute path resolved via `HSE_MCP_SERVER_PATH` (defaulting to `C:\Users\Saksham\Git\poc\AIAgents\mcp-server`), completely avoiding relative paths.
3. **Strands Agent Tool Consumption:**
   - **Decision:** Confirmed. Per Strands documentation, `MCPClient` is passed directly as tools to the Strands agent (`Agent(tools=[mcp_client])`). `HSEMockMCPClient` will expose the underlying `MCPClient` (e.g. via property `.mcp_client`) and implement `load_tools()` so it can be passed directly as tools to Strands agents in Phase 5.
