# Phase 5 Implementation Plan: Strands Agent Workers

> **Revision 5** — supersedes Revision 4. **Tool scoping reversed for Scout, Writer and QA-Legal: all three now receive all five substrate tools.** ScopeParser stays tool-free. The role boundary moves from the tool list into the system prompts, which now carry explicit non-goals, and `tool_invocations` telemetry becomes the enforcement mechanism that detects role bleed. New Decision Log entry **D19** in `ARCHITECTURE.md`.
>
> **Revision 4** — supersedes Revision 3. Q3/Q4/Q9 approved; `SPECIFICATIONS.md` §3.3-3.4 updated with the new models. Telemetry extended with `tool_invocations` so per-agent tool behaviour is auditable while scoped bindings stay in force (Q1/Q2). E402 hoist reverted to deferred (Q8).
>
> **Revision 3** — supersedes Revision 2. Change: the `ScopedToolProvider` class is **dropped**. Strands documents two peer integration approaches, and the one whose stated qualifying condition is "cases requiring explicit control over the MCP session lifecycle" is literally our architecture. We take the documented manual path — a filtered tool list off one shared session. Batch 1 gets smaller: one less class, two fewer tests.
>
> **Revision 2** — provider wiring and credentials pulled into Phase 5 (Batch 0); `openai` added as a pinned dependency; ruff installed and scoped to Phase 5 files only.

## 1. Context & Task Scope

**Phase 5** implements the four LLM-backed callable workers of the HSE Easy pipeline in `src/agents.py`: `ScopeParser`, `Scout`, `Writer`, and `QA-Legal`. Each worker is a Strands `Agent` constructed by a factory function, invoked through a thin typed runner, and returns a Pydantic v2 structured payload together with captured telemetry.

The defining constraint is the Phase 5 / Phase 6 boundary. Per ARCHITECTURE §1 ("Code Owns the Flow"), these workers are **stateless, task-bounded functions**. They hold no routing logic, no iteration counters, no revision loop, no `max_drafts` truncation, no persistence, and no knowledge of one another. All of that is Phase 6's orchestrator. A worker receives typed inputs, invokes one LLM round trip (which may itself call scoped MCP tools), and returns a typed result.

This revision also adds the model-access layer the pipeline needs to talk to a real endpoint: `src/credentials.py` (an `.env`-backed `CredentialManager`) and `src/model_factory.py` (the single module permitted to import a concrete model provider).

### Objectives
1. Resolve model credentials from an `.env` file and construct provider-agnostic `Model` instances pointed at the Azure AI Foundry v1-compatible endpoints.
2. Define the four system prompts encoding TDI editorial guidelines and legal-audit rules, each enforcing its structured output model **and stating its explicit non-goals** — with tools unscoped (D19), the prompt is the role boundary.
3. Provide factory functions that construct each `Agent` with the correct model binding, substrate tools, and clean-stdout configuration.
4. Provide runner functions that invoke each agent and return a typed payload + telemetry envelope.
5. Extend `src/mcp_client.py` with `load_scoped_tools()` so optional per-agent scoping works over a single shared substrate subprocess (the Phase 8 comparison path).
6. Ship a deterministic, offline `ScriptedModel` test fixture so the entire suite runs at zero LLM cost (D16).

### Deliverables
| Path | Change |
| :--- | :--- |
| `src/credentials.py` | New — `CredentialManager`, `ModelCredentials` |
| `src/model_factory.py` | New — the only module importing `strands.models.openai` |
| `src/agents.py` | New — replaces the 7-line comment stub; provider-agnostic |
| `src/schemas.py` | Extended — `ScoutCandidate`, `ScoutReport`, `ToolInvocation`, `AgentTelemetry`, `WorkerOutput[T]` |
| `src/mcp_client.py` | Extended — `load_scoped_tools()`; `load_tools()` renamed to `list_all_tools()` |
| `tests/test_unit/test_credentials.py` | New |
| `tests/test_unit/test_model_factory.py` | New |
| `tests/test_unit/test_agents.py` | New — the main phase test file |
| `tests/test_integration/test_mcp_client.py` | 1 of 12 tests replaced (scoped-tool resolution) |
| `.env.example` | New — committed template |
| `pyproject.toml` | Dependencies + `[tool.ruff]` |

### Dependencies
Phases 1–4 (packaging, `src/schemas.py`, `src/template_engine.py`, `src/mcp_client.py`). Phase 5 consumes schemas and the MCP client; it does **not** touch `src/template_engine.py`.

---

## 2. Prerequisites

Verified by two Stage 1 architect reviews against the working tree at `7a6744f` (clean), on disk and by live probe — not from ROADMAP claims.

**Baseline: `pytest tests/ -q` → 49 passed (re-confirmed at 19.73s on the follow-up review).**

| Prerequisite | Status | Evidence |
| :--- | :--- | :--- |
| Phase 2 schemas complete | ✅ | All ten models present with `ConfigDict(extra="ignore", populate_by_name=True)`; `__all__` at `src/schemas.py:7-18` |
| Phase 3 template engine complete | ✅ | `src/template_engine.py:11,35,41,50,102` — not a Phase 5 dependency |
| Phase 4 MCP client complete | ✅ | `src/mcp_client.py:22-114`; 12/12 integration tests green; substrate reachable |
| Prior-phase debt closed | ✅ | phase-2/3 `FIXES.md` fully resolved; phase-4 architect verdict PASS |
| `strands-agents` installed | ✅ | 1.55.1 (Python 3.11.16, pydantic 2.13.5, mcp 2.1.1, fastmcp 4.0.3, pytest 9.1.1) |
| `pydantic-settings` / `python-dotenv` | ✅ | 2.15.0 / 1.2.3 — installed transitively via `fastmcp-slim`, **not declared** in `pyproject.toml` |
| `ruff` | ✅ | 0.16.7 installed at `.venv/Scripts/ruff.exe` (GAP B closed) |
| `openai` | ❌ | Not installed — **added in Batch 0**, see §4.5 |
| `.gitignore` covers `.env` | ✅ | `.env`, `.env.*`, `!.env.example` already present |

### Prerequisite notes that shape this plan

- **`PipelineScope.time_window` is required with no default** (`src/schemas.py:95`). A ScopeParser response omitting it raises `ValidationError`. The prompt must always emit it; Batch 1 carries a negative test for that path.
- **`Agent(model="gpt-5-mini")` silently constructs a `BedrockModel`** (`strands/agent/agent.py:367-369`, verified twice). We are not using Bedrock. Factories type the parameter `Model` and never accept a bare string — this is exactly the binding the human ruled out.
- **`Agent.structured_output()` is deprecated in 1.55.1** (`strands/agent/agent.py:1046-1052`) and returns only `T`, discarding metrics. ROADMAP's phrasing invites it; this plan forbids it. The supported path — `agent(prompt, structured_output_model=X)` returning an `AgentResult` carrying **both** `.structured_output` and `.metrics` (`agent_result.py:35-41`) — is the only one that makes Rule 6 telemetry implementable.
- **Structured output is implemented as a synthetic tool, not a provider feature.** `StructuredOutputContext` builds a tool from the Pydantic class (`strands/tools/structured_output/_structured_output_context.py:42-44`), the event loop appends its spec and sets `tool_choice` (`strands/event_loop/event_loop.py:574-593`), and the result is harvested from the tool-use block (`event_loop.py:910-913`). Everything flows through plain `chat.completions.create` with `tools=[...]`; the OpenAI-proprietary `client.beta.chat.completions.parse` path (`openai.py:854`) is never reached. **Any endpoint implementing OpenAI chat-completions streaming + function calling works.**
- **Strands documents two peer integration approaches; we take the manual one, by architecture.** `mcp-tools/index.md` §2 labels `Agent(tools=[mcp_client])` "Managed Integration (Recommended)" and `with client: Agent(tools=client.list_tools_sync())` "Manual Context Management — **for cases requiring explicit control over the MCP session lifecycle**". ARCHITECTURE §3 assigns exactly that control to the Procedural Orchestrator ("manages stdio MCP connections"), so we are the documented qualifying case by construction. The manual form is not marked legacy or discouraged anywhere: §9 Best Practices endorses the `with` discipline unconditionally, and §3.1 uses this exact shape as its primary stdio example.
  The two modes are **mutually exclusive by design** — you either own the lifecycle or hand it over. Pre-starting the session and *then* handing the client to `Agent` raises `ValueError: ... Failed to start MCP client: the client session is currently running`, because `MCPClient.load_tools()` gates on `_tool_provider_started` (`mcp_client.py:545`) rather than `_is_session_active()` (`mcp_client.py:1922-1929`). That is an SDK gap, but "pre-start then also hand to the Agent" is not a documented mode in the first place. §4.6 gives the shape we ship.
- **Per-listing tool scoping is native.** `MCPClient.list_tools_sync(..., tool_filters=...)` (`mcp_client.py:718-723`) overrides the constructor default per call — "If explicitly provided (including empty dict), overrides constructor default" — so one session yields three different scopes. Documented explicitly in the TypeScript tab of §5 but only via docstring on the Python side: an under-documented API we rely on knowingly.
- **Managed lifecycle is incompatible with a single shared substrate.** Verified live: three managed clients = three subprocesses (process count 4 → 10); one shared managed client = no per-agent scoping *and* the subprocess dies when the last `Agent` is garbage-collected. The latter is concretely dangerous for Phase 6 — dropping the Scout after triage would kill the substrate under the Writer and QA.
- **`MCPClient.load_servers` cannot construct a subclass.** `_build_client_from_config` ends in a hardcoded `return MCPClient(...)`, not `cls(...)` (`mcp_client.py:2610-2617`). Subclassing to become a native `ToolProvider` would force us off `load_servers` and onto hand-built `stdio_client` transport plumbing — a further reason not to.
- **Strands ships no mock/test model.** Phase 5 must ship its own `Model` subclass fixture (recipe verified end-to-end in live probes).

### Deferred, by human decision

- **Pre-existing lint debt — 46 ruff findings across Phases 2–4, deferred to Phase 7.** `UP006` (11), `UP045` (10), `I001` (10), `E701` (8), `F401` (3), `UP035` (2), `E402` (2). Phase 5 fixes **only** findings in files it creates or modifies. `ROADMAP.md` Phase 7 is **not** updated yet. The `architect` subagent definition has been amended to run ruff on every Stage 3 audit and report in-scope findings (blocking) separately from deferred debt (counted, non-blocking) — see `.claude/agents/architect.md`.
- **The deferral is by file *and* by origin.** Phase 5 modifies `src/mcp_client.py` and `tests/test_integration/test_mcp_client.py`, but the pre-existing findings in those files (6, including the 2 × `E402` at lines 80-81) stay deferred by human decision. **The Stage 3 ruff gate blocks only on findings Phase 5 *introduces*** — new or modified lines. Pre-existing findings anywhere, including in files Phase 5 touches, are reported as a count and carried to Phase 7. See §6 Q8.

---

## 3. Strict TDD Strategy

All tests are unit tests unless stated otherwise. Every unit test is offline: no network, no subprocess, no real credentials. Fixtures live in-file, matching the house style (no `conftest.py` exists and Phase 5 does not introduce one).

### The `ScriptedModel` fixture (foundation for Batches 1–5)

A `strands.models.model.Model` subclass replaying a scripted list of turns, each turn a list of stream events. It exercises the **real** Strands event loop — strictly better than `patch("strands.Agent")`, which would verify nothing about the integration.

```python
class ScriptedModel(Model):
    """Deterministic offline Model replaying pre-scripted stream events."""

    def __init__(self, turns: list[list[dict[str, Any]]]) -> None: ...

    received_messages: list[list[Message]]   # captured for prompt assertions

    def update_config(self, **model_config: Any) -> None: ...
    def get_config(self) -> dict[str, Any]: ...
    def structured_output(self, output_model, prompt, system_prompt=None, **kwargs): ...
    async def stream(self, messages, tool_specs=None, system_prompt=None, **kwargs) -> AsyncIterable[dict[str, Any]]: ...
```

Helper `_tool_use_turn(name, args, *, input_tokens, output_tokens, latency_ms)` builds one turn. **Critical detail (verified):** the structured-output tool name equals the Pydantic model's class name — a turn naming `PipelineScope` / `ArticleDraft` / `QAReport` drives structured output, while a turn naming `verify_legal_citation` drives a real tool call.

---

### Batch 0 — Dependencies, credentials, model factory, lint config

Sequenced first: it is the only batch changing dependencies, so every later batch runs under the ruff gate.

**Target tests — `tests/test_unit/test_credentials.py`:**
| Test | Expected Red failure |
| :--- | :--- |
| `test_credential_manager_constructs_from_explicit_values` | `ModuleNotFoundError: No module named 'src.credentials'` — built with `_env_file=None` so a developer's real `.env` cannot leak in |
| `test_credential_manager_reads_env_file` | as above — loads from a `tmp_path` `.env` |
| `test_credential_manager_missing_vars_raises` | `ValidationError` naming the missing keys; no crash at import |
| `test_api_key_is_masked_in_str_and_repr` | `SecretStr` renders `'**********'` — protects Rule 6 logging |
| `test_for_model_returns_fast_credentials` | `for_model("gpt-5-mini")` → fast credentials |
| `test_for_model_returns_strong_credentials` | `for_model("gpt-5.4")` → strong credentials |
| `test_for_model_rejects_unknown_model_id` | `ValueError` naming the unknown ID |

**Target tests — `tests/test_unit/test_model_factory.py`:**
| Test | Expected Red failure |
| :--- | :--- |
| `test_build_model_returns_strands_model` | `ModuleNotFoundError: No module named 'src.model_factory'` — result is a `strands.models.model.Model` |
| `test_build_model_passes_endpoint_and_key_as_client_args` | `client_args` carries `base_url` + `api_key` |
| `test_build_model_sets_model_id_to_deployment` | `get_config()["model_id"]` equals the deployment name |
| `test_build_model_makes_no_network_call` | construction alone reaches no socket (`OpenAIModel.__init__` only stores config, `openai.py:120-125`) |

**Target implementation — `src/credentials.py`:**
```python
class ModelCredentials(BaseModel):
    model_config = ConfigDict(extra="ignore")
    endpoint: str
    api_key: SecretStr
    deployment: str


class CredentialManager(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", extra="ignore", case_sensitive=False
    )
    fast_endpoint: str = Field(..., alias="HSE_MODEL_FAST_ENDPOINT")
    fast_api_key: SecretStr = Field(..., alias="HSE_MODEL_FAST_API_KEY")
    fast_deployment: str = Field(default="gpt-5-mini", alias="HSE_MODEL_FAST_DEPLOYMENT")
    strong_endpoint: str = Field(..., alias="HSE_MODEL_STRONG_ENDPOINT")
    strong_api_key: SecretStr = Field(..., alias="HSE_MODEL_STRONG_API_KEY")
    strong_deployment: str = Field(default="gpt-5.4", alias="HSE_MODEL_STRONG_DEPLOYMENT")

    def for_model(self, model_id: str) -> ModelCredentials: ...
```
`for_model` is keyed on the ARCHITECTURE §3 model IDs (`gpt-5-mini` → fast, `gpt-5.4` → strong), keeping ARCHITECTURE §3 as the single source of truth. `SecretStr` is mandatory, not stylistic — it is what keeps keys out of logs.

**Target implementation — `src/model_factory.py`:**
```python
def build_model(model_id: str, credentials: CredentialManager | None = None) -> Model:
    """Construct a Strands Model for the given pipeline model ID."""
```
Per the human's confirmation, endpoints are the **`/openai/v1/` compatibility surface**, so this is a plain pass-through with no path rewriting and no `api-version`:
```python
creds = (credentials or CredentialManager()).for_model(model_id)
return OpenAIModel(
    client_args={"base_url": creds.endpoint, "api_key": creds.api_key.get_secret_value()},
    model_id=creds.deployment,
)
```
`client_args` is forwarded verbatim into `openai.AsyncOpenAI(**client_args)` (verified: `openai.py:128-135`, `:681`), and Strands builds a fresh client per request by design — so no event-loop-bound client is shared.

**Target implementation — `.env.example`** (committed; `.gitignore` already covers `.env`):
```dotenv
# Azure AI Foundry, OpenAI v1-compatible surface. Copy to .env and fill in.
# Fast model — ScopeParser + Scout (ARCHITECTURE §3)
HSE_MODEL_FAST_ENDPOINT=https://<resource>.openai.azure.com/openai/v1/
HSE_MODEL_FAST_API_KEY=
HSE_MODEL_FAST_DEPLOYMENT=gpt-5-mini
# Strong model — Writer + QA-Legal (ARCHITECTURE §3)
HSE_MODEL_STRONG_ENDPOINT=https://<resource>.openai.azure.com/openai/v1/
HSE_MODEL_STRONG_API_KEY=
HSE_MODEL_STRONG_DEPLOYMENT=gpt-5.4
```

**Target implementation — `pyproject.toml`:**
```toml
# dependencies
"openai>=1.68.0,<3.0.0",      # wire-protocol client; see §4.5
"pydantic-settings>=2.0.0",   # currently only transitive via fastmcp-slim
"python-dotenv>=1.0.0",       # ditto
"strands-agents>=1.55.0",     # was >=0.1.0; the APIs used here are 1.x

[tool.ruff]
line-length = 120
target-version = "py311"

[tool.ruff.lint]
select = ["E", "F", "I", "UP", "B"]
```
`line-length = 120` clears the existing 119-char maximum with zero reflow churn. The rule set is the smallest that mechanically enforces the review skills' named criteria: `E402` import hygiene, `F401` dead imports, `I001` import grouping, `UP006`/`UP045` PEP 585/604 annotations, `B` bugbear.

**Scope limit:** Batch 0 does **not** run `ruff check --fix` across the repo. The 46 pre-existing findings stay untouched and deferred to Phase 7.

---

### Batch 1 — Scoped tool loading, telemetry contract, fixture harness, ScopeParser

**Target tests — `tests/test_unit/test_agents.py`:**
| Test | Expected Red failure |
| :--- | :--- |
| `test_scripted_model_drives_structured_output` | `ImportError` — no `ScriptedModel` helper yet (self-test of the harness) |
| `test_load_scoped_tools_returns_only_requested_names` | `AttributeError` — `HSEMockMCPClient` has no `load_scoped_tools` (stub `mcp_client` exposing `list_tools_sync`, offline) |
| `test_extract_telemetry_maps_usage_and_latency` | `ImportError: cannot import name 'extract_telemetry' from 'src.agents'` |
| `test_extract_telemetry_captures_tool_invocations` | `ImportError: cannot import name 'ToolInvocation' from 'src.schemas'` — maps `tool_usage.<name>.execution_stats` into one `ToolInvocation` per tool (Q1 auditability) |
| `test_agent_telemetry_rejects_extra_and_defaults_to_zero` | `ImportError: cannot import name 'AgentTelemetry' from 'src.schemas'` — `tool_invocations` defaults to `[]` |
| `test_scope_parser_agent_has_no_tools` | `ImportError: cannot import name 'build_scope_parser_agent'` |
| `test_scope_parser_extracts_pipeline_scope_unconstrained_max_drafts` | `ImportError: cannot import name 'run_scope_parser'` |
| `test_scope_parser_returns_telemetry_with_model_id` | asserts `total_tokens`, `latency_ms`, `model_id == "gpt-5-mini"` |
| `test_scope_parser_invalid_output_raises` | missing `time_window` → `ValidationError` / `StructuredOutputException` |
| `test_scope_parser_prompt_declares_output_model` | `ImportError: cannot import name 'SCOPE_PARSER_SYSTEM_PROMPT'` |

**Target test — `tests/test_integration/test_mcp_client.py`:**
- `test_scoped_tool_lists_share_one_session` — the three scopes resolve correctly off a **single** live session. This **replaces** `test_client_strands_tool_provider_compatibility` (lines 90-101), whose premise is now known false: `HSEMockMCPClient` is not a `ToolProvider` and should not be one. The other 11 Phase 4 tests are untouched.
- The 2 × `E402` at lines 80-81 stay **deferred to Phase 7** (§6 Q8). Do not hoist them.

**Target implementation — `src/mcp_client.py`:**
```python
def load_scoped_tools(self, names: Sequence[str]) -> list[MCPAgentTool]:
    """Return only the named substrate tools, for per-agent tool scoping."""
    self._ensure_connected()
    return list(self.mcp_client.list_tools_sync(tool_filters={"allowed": list(names)}))
```
All `tool_filters` / `list_tools_sync` detail stays inside `src/mcp_client.py`; `src/agents.py` imports nothing from `strands.tools.mcp`.

**Rename `load_tools()` → `list_all_tools()`** (`src/mcp_client.py:66-68`). As written it is a **sync** method whose name shadows the **async** `ToolProvider.load_tools` contract, on a class that is not a `ToolProvider` — an active trap for the next reader, and the direct cause of the existing test having to sniff for a coroutine. One call site repo-wide.

**Do not** pass `tool_filters` through `HSEMockMCPClient.__init__`'s `load_servers` config — that welds one scope per client and forces one subprocess per agent (verified: 3 clients → 3 subprocesses).

**Target implementation — `src/schemas.py`:**
```python
class ToolInvocation(BaseModel):
    model_config = ConfigDict(extra="ignore", populate_by_name=True)
    tool_name: str
    call_count: int = 0
    success_count: int = 0
    error_count: int = 0
    total_time_seconds: float = 0.0


class AgentTelemetry(BaseModel):
    model_config = ConfigDict(extra="ignore", populate_by_name=True)
    model_id: str
    input_tokens: int = 0
    output_tokens: int = 0
    total_tokens: int = 0
    latency_ms: int = 0
    total_duration_seconds: float = 0.0
    cycles: int = 0
    tool_invocations: list[ToolInvocation] = Field(default_factory=list)


T = TypeVar("T", bound=BaseModel)


class WorkerOutput(BaseModel, Generic[T]):
    model_config = ConfigDict(extra="ignore")
    payload: T
    telemetry: AgentTelemetry
```

**Target implementation — `src/agents.py`:**
```python
SCOPE_PARSER_MODEL_ID: Final[str] = "gpt-5-mini"
SCOUT_MODEL_ID: Final[str] = "gpt-5-mini"
WRITER_MODEL_ID: Final[str] = "gpt-5.4"
QA_LEGAL_MODEL_ID: Final[str] = "gpt-5.4"

SCOPE_PARSER_SYSTEM_PROMPT: Final[str] = ...

def extract_telemetry(result: AgentResult, model_id: str) -> AgentTelemetry: ...
def build_scope_parser_agent(model: Model) -> Agent: ...
def run_scope_parser(agent: Agent, user_prompt: str, *, model_id: str = SCOPE_PARSER_MODEL_ID) -> WorkerOutput[PipelineScope]: ...
```

`extract_telemetry` is the **only** place `metrics.get_summary()` is read; the raw `dict[str, Any]` never crosses a module boundary (Rule 2). Every factory passes `callback_handler=None` so stdout stays clean (ARCHITECTURE §6.3).

---

### Batch 2 — Scout (scoped regulatory tools + newsworthiness scoring)

**Objective:** The triage worker — queries the substrate, scores editorial relevance, returns a ranked candidate list **without** truncating.

| Test | Expected Red failure |
| :--- | :--- |
| `test_scout_candidate_score_bounds` | `ImportError: cannot import name 'ScoutCandidate'`; then `ValidationError` on a score of `1.5` |
| `test_scout_agent_receives_all_tools` | `ImportError: cannot import name 'build_scout_agent'` — `len(agent.tool_names) == 5` (D19) |
| `test_scout_agent_accepts_explicit_tool_scope` | passing `SCOUT_TOOL_NAMES` narrows `set(agent.tool_names)` to those three — the Phase 8 comparison path |
| `test_scout_returns_ranked_scout_report` | `ImportError: cannot import name 'run_scout'` |
| `test_scout_applies_newsworthiness_scoring` | scores within `[0.0, 1.0]`, descending order, non-empty rationale |
| `test_scout_does_not_truncate_to_max_drafts` | **Rule 4 guard** — pass `PipelineScope(max_drafts=1)`, assert all qualifying candidates returned |
| `test_scout_invokes_regulatory_tools` | `telemetry.tool_invocations` contains a `list_regulatory_updates` entry with `call_count >= 1` |
| `test_scout_prompt_declares_role_boundary` | prompt names `ScoutReport`, and states its non-goals: it does not draft, does not audit citations, and does not limit candidate count |

**Target implementation — `src/schemas.py`:**
```python
class ScoutCandidate(BaseModel):
    model_config = ConfigDict(extra="ignore", populate_by_name=True)
    update: RegulatoryUpdateSummary
    newsworthiness_score: float = Field(..., ge=0.0, le=1.0)
    rationale: str


class ScoutReport(BaseModel):
    model_config = ConfigDict(extra="ignore", populate_by_name=True)
    candidates: list[ScoutCandidate] = Field(default_factory=list)
```

**Target implementation — `src/agents.py`:**
```python
SCOUT_TOOL_NAMES: Final[tuple[str, ...]] = (
    "list_regulatory_updates", "search_regulatory_docs", "get_document_by_id",
)
SCOUT_SYSTEM_PROMPT: Final[str] = ...

def build_scout_agent(model: Model, client: HSEMockMCPClient | None = None,
                      tool_names: Sequence[str] | None = None) -> Agent: ...
def run_scout(agent: Agent, scope: PipelineScope, *, model_id: str = SCOUT_MODEL_ID) -> WorkerOutput[ScoutReport]: ...
```

The Scout prompt filters by newsworthiness and compliance relevance and explicitly states that it must **never** limit the number of candidates — that ceiling belongs to the orchestrator (Rule 4, D3).

---

### Batch 3 — Writer (initial draft)

| Test | Expected Red failure |
| :--- | :--- |
| `test_writer_agent_receives_all_tools` | `ImportError: cannot import name 'build_writer_agent'` — `len(agent.tool_names) == 5` (D19) |
| `test_writer_generates_article_draft` | `ImportError: cannot import name 'run_writer'` — all four `ArticleDraft` fields non-empty |
| `test_writer_includes_tdi_cta_from_offerings` | CTA text traceable to the `get_tdi_service_offerings` tool result |
| `test_writer_telemetry_carries_writer_model_id` | `model_id == "gpt-5.4"` |
| `test_writer_prompt_declares_role_boundary` | prompt names `ArticleDraft` and the TDI CTA requirement, and states its non-goals: it issues no compliance verdict, and **never silently drops a citation it cannot verify** — it keeps it and flags it, so QA still sees the signal |

```python
WRITER_TOOL_NAMES: Final[tuple[str, ...]] = ("get_tdi_service_offerings", "get_document_by_id")
WRITER_SYSTEM_PROMPT: Final[str] = ...

def build_writer_agent(model: Model, client: HSEMockMCPClient | None = None,
                       tool_names: Sequence[str] | None = None) -> Agent: ...
def run_writer(
    agent: Agent,
    document: RegulatoryDocument,
    revision: RevisionPayload | None = None,
    *,
    model_id: str = WRITER_MODEL_ID,
) -> WorkerOutput[ArticleDraft]: ...
```
Batch 3 implements the `revision is None` path only.

---

### Batch 4 — Writer revision path (D18)

| Test | Expected Red failure |
| :--- | :--- |
| `test_writer_accepts_revision_payload` | assertion failure — must return a revised `ArticleDraft` |
| `test_writer_revision_serialises_structured_payload` | asserts the message the model received contains the previous headline **and** a QA issue string **verbatim** (from `ScriptedModel.received_messages`) — guards against the narrative interpolation D18 explicitly rejects |
| `test_writer_revision_does_not_manage_attempts` | `run_writer` neither reads nor mutates any counter; `attempt` comes solely from the passed payload |
| `test_agents_module_contains_no_loop_state` | **source-level guard** — `src/agents.py` contains no `attempts`, no `max_drafts`, no `while` |

**Implementation:** when `revision is not None`, embed `json.dumps(revision.model_dump(), ensure_ascii=False, indent=2)` inside a clearly delimited block appended to the prompt. The nested `draft` and `qa_audit` serializations satisfy D18's `current_draft.model_dump()` / `qa_report.model_dump()` requirement exactly.

---

### Batch 5 — QA-Legal (tri-state) and final refactor

| Test | Expected Red failure |
| :--- | :--- |
| `test_qa_legal_agent_receives_all_tools` | `ImportError: cannot import name 'build_qa_legal_agent'` — `len(agent.tool_names) == 5` (D19) |
| `test_qa_legal_fact_checks_against_source_document` | QA calls `get_document_by_id` and its `issues` reference a `key_obligations` mismatch — the audit capability scoping previously made impossible |
| `test_qa_legal_produces_pass_report` | `ImportError: cannot import name 'run_qa_legal'` |
| `test_qa_legal_produces_warning_report` | `status == "WARNING"` |
| `test_qa_legal_produces_error_report_with_issues` | `status == "ERROR"`, `issues` non-empty |
| `test_qa_legal_verifies_each_citation` | `telemetry.tool_invocations` contains `verify_legal_citation` with `call_count >= 1` |
| `test_qa_legal_prompt_declares_role_boundary` | prompt names `QAReport` and the tri-state semantics, and states its non-goals: it never rewrites prose, never proposes copy, and never selects CTAs |
| `test_all_worker_prompts_declare_structured_output_model` | the ROADMAP "Refactor" step, made testable across all four prompts |
| `test_all_worker_prompts_declare_non_goals` | **D19 enforcement** — with tools no longer bounding roles, every prompt must state what the worker does *not* do |
| `test_agents_module_exports_public_surface` | `__all__` present and complete |
| `test_factory_requires_live_client` | calling a factory with a disconnected client raises `MCPClientNotConnectedError` |

```python
QA_LEGAL_TOOL_NAMES: Final[tuple[str, ...]] = ("verify_legal_citation",)
QA_LEGAL_SYSTEM_PROMPT: Final[str] = ...

def build_qa_legal_agent(model: Model, client: HSEMockMCPClient | None = None,
                         tool_names: Sequence[str] | None = None) -> Agent: ...
def run_qa_legal(agent: Agent, draft: ArticleDraft, *, model_id: str = QA_LEGAL_MODEL_ID) -> WorkerOutput[QAReport]: ...
```

**Refactor pass:** collapse the four runners onto a shared private `_run_worker` helper; declare `__all__` in all three new modules; complete PEP 604/585 annotations and docstrings; confirm the full suite is green with **zero warnings** and `ruff check` clean **on Phase 5 files**.

**Expected outcome:** roughly 44 new tests; full suite approximately 93 green; integration runtime materially unchanged (still one substrate subprocess).

---

## 4. Proposed Changes & Specifications

### 4.1 `src/agents.py` — full public surface

```python
"""Strands Agent worker definitions for HSE Easy editorial pipeline."""

__all__ = [
    "SCOPE_PARSER_MODEL_ID", "SCOUT_MODEL_ID", "WRITER_MODEL_ID", "QA_LEGAL_MODEL_ID",
    "SCOUT_TOOL_NAMES", "WRITER_TOOL_NAMES", "QA_LEGAL_TOOL_NAMES",
    "SCOPE_PARSER_SYSTEM_PROMPT", "SCOUT_SYSTEM_PROMPT",
    "WRITER_SYSTEM_PROMPT", "QA_LEGAL_SYSTEM_PROMPT",
    "extract_telemetry",
    "build_scope_parser_agent", "build_scout_agent",
    "build_writer_agent", "build_qa_legal_agent",
    "run_scope_parser", "run_scout", "run_writer", "run_qa_legal",
]
```

### 4.2 Model and tool bindings (ARCHITECTURE §3, canonical)

| Worker | Model ID | Credential slot | Tools | Structured output |
| :--- | :--- | :--- | :--- | :--- |
| ScopeParser | `gpt-5-mini` | fast | **none** — pure extraction | `PipelineScope` |
| Scout | `gpt-5-mini` | fast | **all 5** (declared intent: `list_regulatory_updates`, `search_regulatory_docs`, `get_document_by_id`) | `ScoutReport` |
| Writer | `gpt-5.4` | strong | **all 5** (declared intent: `get_tdi_service_offerings`, `get_document_by_id`) | `ArticleDraft` |
| QA-Legal | `gpt-5.4` | strong | **all 5** (declared intent: `verify_legal_citation`, `get_document_by_id`) | `QAReport` |

**D19 (this phase) supersedes the "Scoped Tools" column of ARCHITECTURE §3** for Scout, Writer and QA-Legal. The `*_TOOL_NAMES` constants remain in `src/agents.py` as *declared intent* — what each worker is expected to reach for — and are what a caller passes to `tool_names` to restore scoping for the Phase 8 comparison. They are no longer the tools actually attached. See §6 Q1 for the reasoning and D19 in `ARCHITECTURE.md` for the record.

### 4.3 Invocation contract

```python
result: AgentResult = agent(prompt, structured_output_model=OutputModel)
payload = result.structured_output                 # the Pydantic model
telemetry = extract_telemetry(result, model_id)    # from result.metrics.get_summary()
return WorkerOutput[OutputModel](payload=payload, telemetry=telemetry)
```
Zero occurrences of `agent.structured_output(` or `structured_output_async(` anywhere in `src/`.

### 4.4 Telemetry mapping (Rule 6, D17)

| `AgentTelemetry` field | Source in `metrics.get_summary()` |
| :--- | :--- |
| `input_tokens` | `accumulated_usage.inputTokens` |
| `output_tokens` | `accumulated_usage.outputTokens` |
| `total_tokens` | `accumulated_usage.totalTokens` |
| `latency_ms` | `accumulated_metrics.latencyMs` |
| `total_duration_seconds` | `total_duration` |
| `cycles` | `total_cycles` |
| `tool_invocations` | `tool_usage.<tool_name>.execution_stats` — call/success/error counts and total time, per tool |
| `model_id` | passed by the runner from its module constant |

`model_id` is carried so Phase 6 can key into the per-model rate table (ARCHITECTURE §6.2) without re-deriving it.

### 4.5 Provider isolation — the actual guarantee

`src/agents.py` imports **no** concrete model provider; its factories take `model: Model`, the abstract ABC. Provider knowledge is confined to **one** module, `src/model_factory.py`.

Adding `openai` does not bind the PoC to OpenAI-the-company. It is an HTTP client for the OpenAI *wire protocol* — the de-facto industry interface, spoken by Azure AI Foundry, vLLM, Ollama, Together, Groq and OpenRouter alike. In our code it is reached only through `client_args={"base_url", "api_key"}`; nothing in `src/` will ever reference an `api.openai.com` URL or an OpenAI-specific feature, and the proprietary `beta.chat.completions.parse` path is never taken (see §2). The lock-in that was rightly rejected — `BedrockModel` demanding a boto3 session and AWS region, or an agent framework dictating control flow — is exactly what this avoids.

Swapping providers later means editing one ~20-line file. `src/agents.py`, `src/orchestrator.py` and every test stay untouched because they only ever see `Model`.

**Pinning matters:** `openai>=1.68.0,<3.0.0`. Unpinned, `uv` resolves **3.14.1**, while Strands declares `openai<3.0.0`. Do **not** use the `strands-agents[openai]` extra — it also pulls `aws-bedrock-token-generator`, an AWS dependency we do not want.

Rejected alternatives: `LiteLLMModel` (26 packages, and downgrades installed `importlib-metadata` 9.0.1 → 8.9.0); a hand-rolled `httpx` `Model` (the real provider is 950 lines of SSE tool-call delta reassembly, telemetry extraction that Rule 6 depends on, and error classification the retry loop keys on — all of which would become ours to test).

### 4.6 MCP tool attachment

Tools reach each agent as a **filtered list off one shared session** — the "Manual Context Management" approach Strands documents for callers that own the MCP lifecycle (§2):

```python
with HSEMockMCPClient() as client:              # orchestrator owns the lifecycle
    scout = build_scout_agent(model, client)    # all 5 tools (D19)
    writer = build_writer_agent(model, client)
    qa = build_qa_legal_agent(model, client)
```

`tool_names=None` (the default) attaches every substrate tool via `client.list_all_tools()`. Passing an explicit sequence narrows the set via `client.load_scoped_tools(names)` — the path Phase 8 uses to benchmark scoped against unscoped. Both paths are tested; neither is dead code.

Three agents, three scopes, **one** substrate subprocess — verified live:
```
scout  tool_names = ['get_document_by_id', 'list_regulatory_updates', 'search_regulatory_docs']
writer tool_names = ['get_document_by_id', 'get_tdi_service_offerings']
qa     tool_names = ['verify_legal_citation']
process count constant throughout; no orphans after stop()
```

A real `verify_legal_citation` round trip executed through this shape and returned live substrate data — the scopes are not merely resolving names.

Three mechanics that matter:
- **The agent receives identical objects either way.** `ToolProvider.load_tools()` → `_list_all_tools_sync()` → `list_tools_sync()` (`mcp_client.py:558-596`), which constructs `MCPAgentTool(tool, self)`. Both paths hand the agent the same `MCPAgentTool` instances bound to the same client; execution behaviour is byte-identical. A plain list registers synchronously (`registry.py:119-122`) with no `run_async` hop and no consumer bookkeeping.
- **Nothing is lost by skipping the provider.** `ToolRegistry._tool_providers` has one consumer SDK-wide — `ToolRegistry.cleanup()` calling `remove_consumer` (`registry.py:694-708`). There is no reconnection logic and no refresh-into-agent logic; `_refresh_loaded_tools()` (`mcp_client.py:1589-1607`) never touches a `ToolRegistry` and only fires if an `on_tools_changed` callback was registered, which we do not do against a static fixture server.
- **The client must already be connected when a factory runs, and the agent must be *invoked* inside the `with` block** (docs §10). The orchestrator's entire run already is (ARCHITECTURE §5). This strengthens the factories-not-instances rationale (Q6).

**Do not** pass `HSEMockMCPClient.mcp_client` directly to `Agent(tools=[...])` — it raises (see §2), and it would hand subprocess lifecycle to Strands, contradicting ARCHITECTURE §3's "Procedural Orchestrator … manages stdio MCP connections".

### 4.7 Explicitly out of scope (Phase 6, per ARCHITECTURE §1 and §5.4)

Routing · `attempts` counters · the revision loop and its termination condition · `max_drafts` truncation · `RevisionPayload` **construction** · draft ID allocation · file writes and any `src/template_engine.py` call · `[UNRESOLVED COMPLIANCE ALERT]` injection · cost computation and rate tables · MCP client lifecycle ownership · logging handler configuration.

Also forbidden: passing any `Agent` as a tool to another `Agent` (agent-to-agent delegation), and any `logging.basicConfig()` or handler attachment at import.

**Deferred to Phase 7:** the 46 pre-existing ruff findings in Phases 2–4 files.

---

## 5. Architectural & Quality Audit Checklist

**Architecture**
1. `src/agents.py` contains zero routing, `attempts`, `while`, `max_drafts` truncation, file I/O, or `RevisionPayload` construction.
2. No agent is passed as a tool to another agent; no swarm/handoff/multi-agent primitive imported.
3. `agent.tool_names` has all 5 substrate tools for Scout/Writer/QA-Legal and `[]` for ScopeParser (D19); passing explicit `tool_names` still narrows correctly.
3a. **Every system prompt states the worker's non-goals.** With tools no longer bounding roles, this is the only structural guard against role bleed — treat a missing or vague non-goals section as a blocker, not a nit.
4. All MCP transport detail (`tool_filters`, `list_tools_sync`, subprocess config) stays in `src/mcp_client.py`; `src/agents.py` imports nothing from `strands.tools.mcp`.
5. No Markdown or template formatting in `src/agents.py`.
6. Factories, not import-time agent instances; no MCP subprocess spawned at import.
7. `grep -rn "strands.models" src/` matches only `src/model_factory.py` and abstract-`Model` type imports.
8. At most one substrate subprocess is live during any integration test.

**Data contracts**

9. Every worker returns `WorkerOutput[T]`; no `dict[str, Any]` crosses a module boundary; `get_summary()` is read only inside `extract_telemetry`.
10. All new models carry `model_config = ConfigDict(extra="ignore")`.
11. Structured output uses `structured_output_model=`; zero deprecated `agent.structured_output(` calls.
12. Telemetry maps every field in §4.4, carries the ARCHITECTURE §3 `model_id`, and populates `tool_invocations` from `tool_usage.<name>.execution_stats` — the audit trail that makes scoped tool bindings verifiable rather than merely asserted (Q1).

**Security / configuration**

13. No literal API key, endpoint URL, or deployment name in `src/` outside `src/credentials.py` defaults; `git ls-files .env` is empty; `.env.example` is committed.
14. API keys are `SecretStr` and masked in `str()` and `repr()`.
15. Unit tests construct credentials with `_env_file=None` and never read a developer's real `.env`.

**Process / resilience**

16. No `logging.basicConfig` or handler attachment at import.
17. `callback_handler=None` on every agent (clean stdout, ARCHITECTURE §6.3).
18. No unit test makes a network call or spawns a subprocess; suite runtime does not materially exceed the ~19.7 s baseline.

**Code quality**

19. `ruff check src tests` reports **zero findings introduced by this phase**. Pre-existing findings — including those in files this phase modifies — are reported as a count and deferred to Phase 7; they do not fail the phase.
20. Complete PEP 484/585/604 annotations; modern `X | None` and `list[X]`.
21. `__all__` declared in all three new modules; docstrings on the module, all public functions, and all new models.
22. No dead code or leftover stub comments; two blank lines between top-level definitions; single trailing newline.
23. `pytest tests/ -q` fully green with zero warnings; the prior 49 tests still pass.
24. TDD evidence: tests precede implementation per batch (Rule 7).

---

## 6. Questions & Decisions for Human Approval

All questions are resolved. Q1/Q2 were re-opened by the human and are answered in full below; Q3, Q4 and Q9 are approved; Q6 is settled by a standing project convention.

| # | Question | Decision | Basis |
| :---: | :--- | :--- | :--- |
| **Q1** | **Should PoC agents get scoped tools, or all five?** | ✅ **Resolved by human: unscope Scout, Writer and QA-Legal.** ScopeParser stays tool-free. Recorded as **D19**. | I initially recommended scoping; the human's counter-arguments were stronger and I withdrew it. **On the Writer:** "the loop exists to ensure the draft is good, not to make the Writer iterate" is correct — I had conflated the mechanism *firing* with the mechanism being *valuable*. A first-attempt PASS is a better and cheaper outcome, and my objection that the loop would go unverified collapses under our own design: Phase 6 tests Scenarios A/B/C with mocked QA (D16), so the loop is verified deterministically regardless of production frequency. **On QA:** the human's point is stronger than they put it. ARCHITECTURE §3 charges QA with auditing "every citation **and statutory statement**". Scoped to `verify_legal_citation`, QA can confirm a citation exists and is in force but **cannot** check whether the draft correctly describes what it requires — `get_document_by_id` returns exactly the `key_obligations` and `penalties_summary` needed. Scoping was not discipline; it was under-provisioning. **Residual risks, now handled by prompt rather than tool list:** a Writer that verifies its own citations might silently drop an unverifiable one, losing signal QA would otherwise surface — the Writer prompt forbids this explicitly. QA independence becomes prompt-deep rather than structurally enforced — hence the mandatory non-goals section in every prompt (audit item 3a) and the `test_all_worker_prompts_declare_non_goals` gate. `tool_invocations` telemetry is the detection mechanism for role bleed. |
| **Q2** | **Which tools, given the Q1 outcome?** | All five for Scout/Writer/QA-Legal; none for ScopeParser. The ARCHITECTURE §3 lists survive as the `*_TOOL_NAMES` constants. | ScopeParser is one-shot NL→`PipelineScope` extraction; giving it tools invites it to query the substrate and derive scope from what it finds rather than what the user asked (agreed by the human). The `*_TOOL_NAMES` constants stay in `src/agents.py` as declared intent and as the `tool_names` argument that restores scoping for the Phase 8 comparison. |
| **Q3** | **Scout had no output model in SPECIFICATIONS.** | ✅ **Approved.** `ScoutCandidate` + `ScoutReport` added to `SPECIFICATIONS.md` §3.3. | Without a bounded `newsworthiness_score` field the ROADMAP's scoring test asserts nothing observable. The spec section records that the Scout never truncates to `max_drafts` (Rule 4 / D3). |
| **Q4** | **Telemetry envelope** — `get_summary()` returns `dict[str, Any]`, which Rule 2 forbids across boundaries. | ✅ **Approved.** `ToolInvocation` + `AgentTelemetry` + `WorkerOutput[T]` added to `SPECIFICATIONS.md` §3.4. | Returning `AgentResult` directly types `.structured_output` as `BaseModel \| None`, forcing a narrowing check at every Phase 6 call site, and carries no `model_id` for cost keying. The envelope now also carries `tool_invocations`, which is what makes Q1's scoping decision auditable rather than merely asserted. |
| **Q5** | **GAP A — model provider and the `openai` dependency.** | ✅ **Resolved by human:** add `openai>=1.68.0,<3.0.0`, isolated to `src/model_factory.py`. | See §4.5. Endpoints confirmed as the **`/openai/v1/` compatibility surface**, so the factory is a plain `base_url` + `api_key` pass-through with no `api-version` handling. |
| **Q6** | **Naming** — ROADMAP uses class-like names (`ScopeParserAgent`, …). | `build_*_agent()` factories + `run_*()` runners. | ✅ **Settled by standing convention:** `ROADMAP.md` is read for *task scope only* — never for approach, naming, or technical detail. Where it conflicts with `ARCHITECTURE.md` or `SPECIFICATIONS.md`, those win. (This also retroactively settles Q1/Q2.) Factories are independently forced by `load_scoped_tools()` needing a connected client, and by D16. |
| **Q7** | **GAP B — ruff.** | ✅ **Resolved:** installed (0.16.7). The 46 pre-existing findings go to Phase 7; `ROADMAP.md` Phase 7 is **not** updated yet. `.claude/agents/architect.md` now mandates a ruff pass on every Stage 3 audit, reporting in-scope findings (blocking) separately from deferred debt (counted). | — |
| **Q8** | **Severity of the 2 × E402, and are they urgent?** | **Cosmetic, zero runtime risk.** ✅ **Deferred to Phase 7** per your decision. | Both are at `tests/test_integration/test_mcp_client.py:80-81`. Python executes module-level imports in order at load time regardless of position, so behaviour is identical: no shadowing, no circular-import exposure, no import-time side effects (both modules are already loaded by line 3). E402 is a readability convention, in a **test** file, not `src/`. Consequence for the gate: because Phase 5 modifies this file, the Stage 3 ruff gate blocks only on findings Phase 5 **introduces**, not on pre-existing ones in files it touches. §2 states this explicitly so the reviewer does not treat it as a regression. |
| **Q9** | **Rename `HSEMockMCPClient.load_tools()` → `list_all_tools()`** — touches a shipped Phase 4 symbol. | ✅ **Approved.** Lands in Phase 5, Batch 1. | As written it is a **sync** method whose name shadows the **async** `ToolProvider.load_tools` contract, on a class that is not a `ToolProvider` — the reason the existing test has to sniff for a coroutine. One call site repo-wide; 1 of Phase 4's 12 tests is rewritten (that same test, whose premise is independently false under Revision 3). |

**All nine questions are closed.** Docs updated to match: `SPECIFICATIONS.md` §3.3-3.4 (new models), `ARCHITECTURE.md` D19 and the §3 supersession note (tool access). Nothing in this plan now awaits a decision.
