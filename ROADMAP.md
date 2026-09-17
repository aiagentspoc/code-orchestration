# HSE Easy — Approach 1 Implementation Roadmap (`ROADMAP.md`)
## Deterministic Code-Orchestrated Editorial Pipeline

This document defines the phase-by-phase implementation roadmap to complete the **code-orchestration** pipeline. All development must strictly adhere to **Test-Driven Development (TDD)** as specified in [AGENTS.md](AGENTS.md), the system blueprint in [.agents/docs/ARCHITECTURE.md](.agents/docs/ARCHITECTURE.md), and the contracts in [.agents/docs/SPECIFICATIONS.md](.agents/docs/SPECIFICATIONS.md).

---

### Milestone Overview & Progress Tracker

```text
[Phase 1] ──► [Phase 2] ──► [Phase 3] ──► [Phase 4] ──► [Phase 5] ──► [Phase 6] ──► [Phase 7] ──► [Phase 8]
Packaging     Schemas &     Template      MCP Stdio     Strands       Procedural    Publisher     End-to-End
& Env Setup   Contracts     Engine        Client        Agents        Orchestrator  CLI           Validation
```

| Phase | Focus Area | TDD Scope | Deliverables | Status |
| :---: | :--- | :--- | :--- | :---: |
| **1** | Environment & Dependencies | Environment smoke checks | `pyproject.toml`, directory structure | ✅ Complete |
| **2** | Schemas & Contracts | `tests/test_unit/test_schemas.py` | `src/schemas.py` | ✅ Complete |
| **3** | Template Engine & Formatting | `tests/test_unit/test_template_engine.py` | `src/template_engine.py` | ✅ Complete |
| **4** | Substrate MCP Stdio Client | `tests/test_integration/test_mcp_client.py` | `src/mcp_client.py` | ✅ Complete |
| **5** | Strands Agent Workers | `tests/test_unit/test_agents.py` | `src/agents.py` | ✅ Complete |
| **6** | Procedural Orchestrator & Loop | `tests/test_integration/test_orchestrator.py` | `src/orchestrator.py` | ⏳ Pending |
| **7** | Human Gate & Publishing CLI | `tests/test_unit/test_publish.py` | `src/publish.py` | ⏳ Pending |
| **8** | End-to-End Benchmark & Verification | `tests/test_integration/test_e2e.py` | Sample run, telemetry audit | ⏳ Pending |

---

### Phase 1: Environment, Dependencies & Packaging Setup
* **Status:** ✅ Complete (Completed: 2026-09-10 | Test Suite: 8/8 passed | Artifacts: `.agents/tasks/phase-1/`)
* **Objective:** Establish reproducible environment packaging and project structure.
* **Tasks:**
  1. Initialize `pyproject.toml` with dependencies:
     * `strands-agents>=0.1.0`
     * `pydantic>=2.0.0`
     * `fastmcp>=0.1.0`
     * `pytest>=8.0.0`, `pytest-asyncio`
     * Editable path dependency to `../mcp-server` (`hse-easy-mock-mcp`)
  2. Create source and test directories:
     * `src/` (`__init__.py`, `orchestrator.py`, `agents.py`, `mcp_client.py`, `schemas.py`, `template_engine.py`, `publish.py`)
     * `tests/test_unit/` and `tests/test_integration/`
     * `drafts/` and `logs/`
  3. Verify Python virtual environment via `uv sync` or `pip install -e .`.
* **Exit Criteria:** `pytest` runs and recognizes test directories with 0 errors. (Passed: 8 tests green).

---

### Phase 2: Core Schemas & Data Contracts (TDD Cycle 1)
* **Status:** ✅ Complete (Completed: 2026-09-11 | Test Suite: 18/18 phase tests passed, 26/26 total suite green | Artifacts: `.agents/tasks/phase-2/`)
* **Objective:** Implement type-safe Pydantic v2 schemas matching `SPECIFICATIONS.md`.
* **TDD Tasks:**
  1. **Red:** Write `tests/test_unit/test_schemas.py`:
     * Test instantiation, validation, and JSON serialization of `RegulatoryUpdateSummary`, `RegulatoryDocument`, `CitationVerificationResult`, `TDIServiceOffering`.
     * Test `PipelineScope` defaults (`max_drafts=None` when unconstrained).
     * Test `ArticleDraft`, `QAReport`, `DraftMetadata`, and `RevisionPayload`.
  2. **Green:** Implement `src/schemas.py` importing/re-exporting models and declaring internal pipeline contracts.
  3. **Refactor:** Ensure clean type annotations and strict validation settings (`extra="ignore"`).
* **Exit Criteria:** `pytest tests/test_unit/test_schemas.py` passes 100%. (Passed: 12/12 tests green).

---

### Phase 3: Template Engine & Telemetry Compiler (TDD Cycle 2)
* **Status:** ✅ Complete (Completed: 2026-09-11 | Test Suite: 11/11 phase tests passed, 37/37 total suite green | Artifacts: `.agents/tasks/phase-3/`)
* **Objective:** Build the Markdown artifact compiler that renders `.agents/templates/draft.md`.
* **TDD Tasks:**
  1. **Red:** Write `tests/test_unit/test_template_engine.py`:
     * Test date-based draft ID generation (`draft_YYYYMMDD_001.md`).
     * Test sequential numbering without overwriting existing files in `drafts/`.
     * Test placeholder replacement for headline, summary, body, CTA, source metadata, and QA badge.
     * Test injection of `[UNRESOLVED COMPLIANCE ALERT]` banner when QA status is `ERROR`.
     * Test formatting of telemetry (wall-clock seconds, tokens, cost).
  2. **Green:** Implement `src/template_engine.py`.
  3. **Refactor:** Optimize regex string replacements and file writing logic.
* **Exit Criteria:** `pytest tests/test_unit/test_template_engine.py` passes 100%. (Passed: 11/11 tests green).

---

### Phase 4: Substrate MCP Stdio Client (TDD Cycle 3)
* **Status:** ✅ Complete (Completed: 2026-09-15 | Test Suite: 12/12 phase tests passed, 49/49 total suite green | Artifacts: `.agents/tasks/phase-4/`)
* **Objective:** Connect to `HSE-Easy-Mock-Server` over `stdio` using Strands MCP utilities.
* **TDD Tasks:**
  1. **Red:** Write `tests/test_integration/test_mcp_client.py`:
     * Test stdio connection handshake to `uv run --directory ../mcp-server fastmcp run server.py`.
     * Test calling `list_regulatory_updates` and deserializing into `List[RegulatoryUpdateSummary]`.
     * Test calling `get_document_by_id` and deserializing into `RegulatoryDocument`.
     * Test calling `verify_legal_citation` and verifying `CitationVerificationResult`.
     * Test calling `get_tdi_service_offerings` and deserializing `List[TDIServiceOffering]`.
  2. **Green:** Implement `src/mcp_client.py` wrapping Strands `MCPClient`.
  3. **Refactor:** Add clean error handling and timeout guardrails.
* **Exit Criteria:** `pytest tests/test_integration/test_mcp_client.py` passes 100%. (Passed: 12/12 tests green, full suite 49/49 green).

---

### Phase 5: Strands Agent Workers (TDD Cycle 4)
* **Status:** ✅ Complete (Completed: 2026-09-16 | Test Suite: 49/49 phase tests passed, 98/98 total suite green | Artifacts: `.agents/tasks/phase-5/`)
* **Objective:** Implement the 4 specialized Strands `Agent` workers.
* **TDD Tasks:**
  1. **Red:** Write `tests/test_unit/test_agents.py` using mock LLM model fixtures:
     * Test `ScopeParserAgent` extracts `PipelineScope` with unconstrained `max_drafts`.
     * Test `ScoutAgent` queries regulatory updates and applies newsworthiness scoring.
     * Test `WriterAgent` generates initial draft and accepts `RevisionPayload` on revision.
     * Test `QALegalAgent` checks citations and produces tri-state `QAReport`.
  2. **Green:** Implement `src/agents.py`:
     * Define system prompts adhering to TDI editorial and legal audit guidelines.
     * Attach tools to Scout (`list_regulatory_updates`, `get_document_by_id`), Writer (`get_tdi_service_offerings`), and QA (`verify_legal_citation`).
  3. **Refactor:** Ensure prompts enforce structured output models.
* **Exit Criteria:** `pytest tests/test_unit/test_agents.py` passes 100%. (Passed: 38/38 tests green; 49 phase tests total across `test_agents.py`, `test_credentials.py` and `test_model_factory.py`; full suite 98/98 green, zero warnings.)
* **Delivered beyond the stated scope:** `src/credentials.py` (`.env`-backed `CredentialManager`, `SecretStr` keys) and `src/model_factory.py` (the only module importing a concrete model provider), plus `SPECIFICATIONS.md` §3.3-3.4 and Decision Log **D19** — worker tools are unscoped; role boundaries live in the system prompts and are audited via `AgentTelemetry.tool_invocations`.

---

### Phase 6: Procedural Orchestrator & Bounded Revision Loop (TDD Cycle 5)
* **Objective:** Implement the core Python controller that drives the pipeline deterministically.
* **TDD Tasks:**
  1. **Red:** Write `tests/test_integration/test_orchestrator.py`:
     * Test linear flow: Scope $\rightarrow$ Scout $\rightarrow$ Writer $\rightarrow$ QA $\rightarrow$ Persistence.
     * Test revision loop termination:
       * Scenario A: Status `PASS` on attempt 1 $\rightarrow$ terminates and saves draft.
       * Scenario B: Status `ERROR` on attempt 1, `PASS` on attempt 2 $\rightarrow$ invokes Writer with `RevisionPayload`, terminates and saves clean draft.
       * Scenario C: Status `ERROR` on attempts 1 and 2 $\rightarrow$ terminates when `attempts > 2`, saves draft with unresolved compliance banner.
     * Test empty scout results: terminates cleanly without invoking Writer/QA.
     * Test candidate throttling: processes all qualifying updates by default.
  2. **Green:** Implement `src/orchestrator.py`.
  3. **Refactor:** Integrate Strands telemetry capture (`AgentResult.metrics`) and cost calculation.
* **Exit Criteria:** `pytest tests/test_integration/test_orchestrator.py` passes 100%.

---

### Phase 7: Human Gate & Publisher CLI (TDD Cycle 6)
* **Objective:** Implement the explicit human review and publishing script.
* **TDD Tasks:**
  1. **Red:** Write `tests/test_unit/test_publish.py`:
     * Test loading draft from `drafts/{draft_id}.md`.
     * Test validation check: blocks or warns if publishing an `ERROR` draft.
     * Test metadata extraction and publication formatting.
  2. **Green:** Implement `src/publish.py`.
  3. **Refactor:** Clean CLI argument parsing with `argparse`.
* **Exit Criteria:** `pytest tests/test_unit/test_publish.py` passes 100%.

---

### Phase 8: End-to-End Benchmark & Verification
* **Objective:** Perform full end-to-end execution against sample regulatory updates.
* **Tasks:**
  1. Execute pipeline with realistic queries:
     ```bash
     python -m src.orchestrator "Analyze recent INAIL updates on heat stress"
     ```
  2. Verify output file in `drafts/draft_YYYYMMDD_001.md`:
     * Validate Executive Summary, Article Body, and TDI CTA.
     * Check QA-Legal review notes and verified citations.
     * Check Run Telemetry (latency seconds, tokens, cost).
  3. Execute `python src/publish.py --draft draft_YYYYMMDD_001`.
  4. Run complete test suite:
     ```bash
     pytest tests/test_unit/ tests/test_integration/ -v
     ```
* **Exit Criteria:** All unit and integration tests green; valid draft generated on disk with zero unresolved bugs.

