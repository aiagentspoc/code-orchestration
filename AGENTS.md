# Instructions for AI Coding Assistants (`AGENTS.md`)
## Project: HSE Easy — Approach 1 (Code-Orchestrated Pipeline)

Welcome to the **code-orchestration** repository. This document provides essential instructions, architectural guidelines, and an index of project resources located in `.agents/` that any AI coding assistant must consult and adhere to when implementing, maintaining, or refactoring code in this repository.

---

### 1. The Single Source of Truth: `.agents/` Directory

All architectural blueprints, technical specifications, templates, MCP plugins, and specialized agent skills are maintained inside the `.agents/` directory:

```text
code-orchestration/
├── AGENTS.md                  <-- You are here (AI Assistant Guide)
├── README.md                  <-- User-facing setup & overview
├── .agents/
│   ├── docs/
│   │   ├── DESIGN.md          <-- Initial approach notes & concept overview
│   │   ├── ARCHITECTURE.md    <-- System blueprint, data flow, flowchart, Decision Log
│   │   └── SPECIFICATIONS.md  <-- Strict Pydantic v2 schemas, MCP tool signatures, CLI specs
│   ├── plugins/
│   │   ├── strands-mcp/       <-- Strands Agents documentation MCP server plugin
│   │   └── hse-easy-mock/     <-- Local HSE Easy Mock MCP server plugin
│   ├── skills/
│   │   ├── architect-review/  <-- Architecture review & design guidance skill
│   │   └── code-reviewer/     <-- Code quality & security auditing skill
│   └── templates/
│       └── draft.md           <-- Canonical Markdown template for generated draft articles
├── drafts/                    <-- Local storage for draft_YYYYMMDD_XXX.md artifacts
├── src/                       <-- Production pipeline implementation
└── tests/                     <-- Unit and integration test suites
```

---

### 2. Mandatory Rules for AI Coding Assistants

When implementing or modifying code in this repository, you **MUST** uphold the following rules:

#### Rule 1: "Code Owns the Flow"
* **No Autonomous Sequencing:** Do **not** build autonomous swarms, open-ended agent loops, or emergent routing where LLMs decide which agent to run next.
* **Procedural Control:** All pipeline control flow, agent invocation sequences, candidate throttling, revision iteration counters, and error recovery must be hardcoded in imperative, procedural Python inside `src/orchestrator.py`.
* **Callable Workers:** LLM agents act strictly as callable worker functions using the **Strands Agents SDK** (`strands-agents`).

#### Rule 2: Strict Adherence to Schemas (`SPECIFICATIONS.md`)
* Never invent arbitrary or unstructured dictionary payloads between agents.
* All data transfer objects **MUST** adhere to the Pydantic v2 schemas defined in `.agents/docs/SPECIFICATIONS.md`:
  * Substrate: `RegulatoryUpdateSummary`, `RegulatoryDocument`, `CitationVerificationResult`, `TDIServiceOffering` (matching `outputSchema` of `hse-easy-mock`).
  * Internal: `PipelineScope`, `ArticleDraft`, `QAReport`, `DraftMetadata`, `RevisionPayload`.

#### Rule 3: Bounded Revision Loop Mechanics
* When the QA-Legal agent evaluates a draft:
  * Status `PASS` or `WARNING`: Terminate revision loop immediately and proceed to save.
  * Status `ERROR`: Increment `attempts`.
  * **Termination Condition:** The revision loop **MUST** terminate when `attempts > 2`. If an error persists after attempt 2, do not re-invoke Writer; save the draft with an `[UNRESOLVED COMPLIANCE ALERT]` banner in the review notes.

#### Rule 4: Candidate Selection & Throttling
* The Scout agent filters updates by newsworthiness and compliance relevance.
* Unless the user prompt explicitly specifies a draft limit (`PipelineScope.max_drafts`), the pipeline **MUST** generate drafts for **all qualifying updates** returned by the Scout agent.

#### Rule 5: Draft Persistence & Format
* Persist drafts strictly as self-contained Markdown files named `drafts/draft_{YYYYMMDD}_{XXX}.md`.
* Do **not** create separate JSON database files for drafts; Markdown is the single source of truth for editorial review.
* Use the exact placeholders and structure provided in `.agents/templates/draft.md`.

#### Rule 6: Telemetry & Token Accounting
* Use the native Strands observability API: inspect `AgentResult.metrics.get_summary()` to extract `accumulated_usage` (`inputTokens`, `outputTokens`, `totalTokens`) and `accumulated_metrics` (`latencyMs`).
* Compute and populate wall-clock latency, token usage, and dollar cost estimates in the draft telemetry section.
* Direct all Strands SDK logs to `logging.getLogger("strands")`.

#### Rule 7: Strict Test-Driven Development (TDD)
* **Red-Green-Refactor Cycle:** Write tests **before** writing production code.
  1. **Red:** Author a targeted unit or integration test in `tests/` that exercises the expected behavior or contract defined in `SPECIFICATIONS.md`. Execute the test to confirm it fails for the expected reason.
  2. **Green:** Write the minimal implementation in `src/` required to make the test pass.
  3. **Refactor:** Clean up, type-annotate, and optimize while keeping the test suite green.
* **Coverage Scope:**
  * Unit tests (`tests/test_unit/`) for schemas, scope parsing, template compilation, and procedural loop logic.
  * Integration tests (`tests/test_integration/`) for `hse-easy-mock` MCP stdio connectivity, revision loop state transitions, and draft artifact emission.
* **Zero Untested Production Code:** Never commit or introduce code in `src/` without accompanying automated tests.

---

### 3. MCP Servers & Tool Reference

This repository interacts with two MCP servers:

#### 1. `hse-easy-mock` (Local Substrate over `stdio`)
* **Location:** `C:\Users\Saksham\Git\poc\AIAgents\mcp-server`
* **Launch Command:** `uv run --directory C:\Users\Saksham\Git\poc\AIAgents\mcp-server fastmcp run server.py`
* **Key Tools:**
  * `list_regulatory_updates(source, date_from, date_to, limit)` $\rightarrow$ `List[RegulatoryUpdateSummary]`
  * `search_regulatory_docs(query, source, topic, sector)` $\rightarrow$ `List[RegulatoryUpdateSummary]`
  * `get_document_by_id(doc_id)` $\rightarrow$ `RegulatoryDocument`
  * `verify_legal_citation(citation, source)` $\rightarrow$ `CitationVerificationResult`
  * `get_tdi_service_offerings(topic, sector)` $\rightarrow$ `List[TDIServiceOffering]`

#### 2. `strands-agents` (SDK Documentation Search)
* **Command:** `uvx strands-agents-mcp-server`
* **Key Tools:**
  * `search_docs(query, k)`: Ranked search over Strands documentation.
  * `fetch_doc(uri, section)`: Retrieve specific documentation pages and guides.

---

### 4. Development & Testing Commands

* **Run the Pipeline:**
  ```bash
  python -m src.orchestrator "Analyze recent INAIL updates on heat stress"
  ```
* **Publish an Approved Draft:**
  ```bash
  python src/publish.py --draft draft_20260909_001
  ```
* **Run Tests:**
  ```bash
  pytest tests/test_unit/
  pytest tests/test_integration/
  ```
* **Check MCP Connection:**
  ```bash
  uv run --directory C:\Users\Saksham\Git\poc\AIAgents\mcp-server fastmcp inspect server.py
  ```

