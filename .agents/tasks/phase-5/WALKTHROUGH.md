# Phase 5 Walkthrough: Strands Agent Workers

## 1. Overview

Phase 5 built the four LLM-backed workers that the procedural orchestrator will drive, and the model-access layer they need to reach a real endpoint.

`src/agents.py` grew from a seven-line comment stub into a 558-line module holding four system prompts, four agent factories, four runners, and the telemetry projection that converts Strands' untyped metrics dictionary into a Pydantic contract. Every worker is a stateless, task-bounded callable: it accepts typed inputs, performs exactly one LLM round trip, and returns a `WorkerOutput[T]` carrying its structured payload alongside the telemetry for that call. No worker knows the pipeline exists. Routing, the revision loop, iteration counters, `max_drafts` truncation, persistence and MCP lifecycle ownership are all absent by construction and remain Phase 6's work.

Two decisions shaped the phase more than the roadmap did.

**D19 — worker tools are unscoped.** The original design scoped each agent to a subset of the five substrate tools. That was reversed during planning. The decisive argument was that scoping under-provisioned QA-Legal rather than disciplining it: ARCHITECTURE §3 charges QA with auditing "every citation **and statutory statement**," which requires `get_document_by_id` to compare a draft's claims against the source document's `key_obligations` and `penalties_summary` — impossible with `verify_legal_citation` alone. The same reasoning applied to the Writer, where a cleaner first draft is a better and cheaper outcome, and where the bounded revision loop remains verified by mocked Scenario A/B/C tests regardless of how often it fires in production. Scout, Writer and QA-Legal therefore receive all five tools; ScopeParser is structurally tool-free (its factory takes no client parameter at all).

The consequence is that **the role boundary moved from the tool list into the system prompts**, which is why the prompts in this phase are substantial rather than perfunctory, and why `AgentTelemetry.tool_invocations` exists: it is the compensating control that makes role bleed detectable after the fact.

**Provider independence without provider avoidance.** `src/agents.py` imports only the abstract `strands.models.model.Model`. Exactly one module in `src/` — `src/model_factory.py`, 42 lines — imports a concrete provider. Credentials come from an `.env` file through a `pydantic-settings` manager with `SecretStr` keys. Swapping providers means editing one file; nothing else in `src/`, and no test, would change.

**Result: 49 new tests, full suite 98 passed, zero warnings, zero ruff findings introduced.**

---

## 2. Component Structure

### `src/credentials.py` (new)

Two credential slots keyed by the ARCHITECTURE §3 model bindings — a *fast* slot for ScopeParser and Scout, a *strong* slot for Writer and QA-Legal.

| Symbol | Responsibility |
| :--- | :--- |
| `FAST_MODEL_ID` / `STRONG_MODEL_ID` | The canonical `gpt-5-mini` / `gpt-5.4` identifiers |
| `ModelCredentials` | One resolved slot: `endpoint`, `api_key: SecretStr`, `deployment` |
| `CredentialManager` | A `BaseSettings` reading `HSE_MODEL_{FAST,STRONG}_{ENDPOINT,API_KEY,DEPLOYMENT}` from the environment or `.env` |
| `CredentialManager.for_model()` | Maps a pipeline model ID to its slot; raises `ValueError` on an unknown ID |

`api_key` is `SecretStr` rather than `str` deliberately: it renders as `**********` in both `str()` and `repr()`, so a key cannot reach the `strands` logger that Rule 6 configures. The module imports nothing from `strands`.

### `src/model_factory.py` (new)

The isolation boundary. `build_model(model_id, credentials=None) -> Model` resolves the credential slot and constructs an `OpenAIModel` with `client_args={"base_url": ..., "api_key": ...}` and `model_id` set to the deployment name.

Because the configured endpoints are Azure AI Foundry's OpenAI **v1-compatible** surface, this is a plain pass-through — no deployment path rewriting, no `api-version` query parameter, no `AzureOpenAI` client. Construction opens no socket; Strands builds a fresh HTTP client per request.

### `src/agents.py` (rewritten)

| Group | Members |
| :--- | :--- |
| Model bindings | `SCOPE_PARSER_MODEL_ID`, `SCOUT_MODEL_ID`, `WRITER_MODEL_ID`, `QA_LEGAL_MODEL_ID` |
| Declared tool intent | `SCOUT_TOOL_NAMES`, `WRITER_TOOL_NAMES`, `QA_LEGAL_TOOL_NAMES` |
| System prompts | `SCOPE_PARSER_SYSTEM_PROMPT`, `SCOUT_SYSTEM_PROMPT`, `WRITER_SYSTEM_PROMPT`, `QA_LEGAL_SYSTEM_PROMPT` |
| Factories | `build_scope_parser_agent`, `build_scout_agent`, `build_writer_agent`, `build_qa_legal_agent` |
| Runners | `run_scope_parser`, `run_scout`, `run_writer`, `run_qa_legal` |
| Telemetry | `extract_telemetry` |
| Private helpers | `_resolve_tools`, `_run_worker`, `_as_json` |

The `*_TOOL_NAMES` constants survive D19 as *declared intent* — what each worker is expected to reach for — and as the argument a caller passes to `tool_names` to restore scoping for the Phase 8 comparison. They are no longer the tools actually attached.

`_resolve_tools(client, tool_names)` is the whole of the D19 mechanism: `client is None` yields a tool-free agent, `tool_names is None` attaches everything via `client.list_all_tools()`, and an explicit sequence narrows via `client.load_scoped_tools(names)`. All three paths are exercised by tests.

`_run_worker` is the single invocation shape. It always calls `agent(prompt, structured_output_model=output_model)` and never the deprecated `Agent.structured_output()`, which returns only the payload and discards the metrics Rule 6 depends on. `grep` over `src/` finds that method nowhere.

`_as_json` serialises a Pydantic model with `ensure_ascii=False, indent=2` for embedding in a prompt — structured object passing, not narrative interpolation (D18).

### `src/schemas.py` (extended)

Five new models, matching SPECIFICATIONS §3.3–3.4 field for field, all carrying `ConfigDict(extra="ignore", populate_by_name=True)`:

- `ScoutCandidate` — a triaged update with a `newsworthiness_score` bounded to `[0.0, 1.0]` and a `rationale`.
- `ScoutReport` — the candidate list, with a docstring recording that the Scout never truncates.
- `ToolInvocation` — per-tool `call_count`, `success_count`, `error_count`, `total_time_seconds`.
- `AgentTelemetry` — the typed projection of `get_summary()`, carrying `model_id` so Phase 6 can key its cost table without re-deriving it.
- `WorkerOutput[T]` — the generic envelope, `payload` plus `telemetry`.

New models use PEP 585 `list[...]` rather than the `List[...]` of the specification snippets. The surrounding Phase 2 code still uses `List`; normalising it is deferred Phase 7 work, and writing `List` in new code would have emitted `UP006` under the ruff configuration this phase introduced.

### `src/mcp_client.py` (extended)

- `load_tools()` → **renamed** `list_all_tools()`. The old name was a synchronous method shadowing the asynchronous `ToolProvider.load_tools` contract on a class that is not a `ToolProvider` — which is precisely why the test it replaced had to inspect the return value for a coroutine.
- `load_scoped_tools(names)` — **new**. Delegates to `list_tools_sync(tool_filters={"allowed": [...]})`. The filter applies per listing, so several scopes resolve off the one shared stdio session.

All `tool_filters` and `list_tools_sync` detail stays in this module; `src/agents.py` imports nothing from `strands.tools.mcp`.

### `pyproject.toml`

`openai>=1.68.0,<3.0.0` (the upper bound matters — unpinned, resolution reaches 3.x while Strands declares `<3.0.0`), `pydantic-settings` and `python-dotenv` promoted from transitive to declared, and `strands-agents` raised from `>=0.1.0` to `>=1.55.0` since the APIs used here are 1.x. Plus `[tool.ruff]`: line length 120, target `py311`, rules `E,F,I,UP,B`.

---

## 3. TDD Batch Rationale & Execution

Six batches, each Red → Green → Refactor. Full-suite count after each:

| Batch | Red signal observed | Suite |
| :--- | :--- | ---: |
| — baseline | — | 49 |
| **0** Dependencies, credentials, model factory, lint config | `ModuleNotFoundError: No module named 'src.credentials'` | **60** |
| **1** Scoped tool loading, telemetry, `ScriptedModel`, ScopeParser | `ImportError: cannot import name 'SCOPE_PARSER_MODEL_ID'`; `AttributeError: … has no attribute 'list_all_tools'` | **70** |
| **2** Scout | `ImportError: cannot import name 'SCOUT_MODEL_ID'` | **78** |
| **3** Writer, initial draft | `ImportError: cannot import name 'WRITER_MODEL_ID'` | **83** |
| **4** Writer revision path (D18) | `TypeError: run_writer() got an unexpected keyword argument 'revision'` | **87** |
| **5** QA-Legal, cross-cutting guards, refactor | `ImportError: cannot import name 'QA_LEGAL_MODEL_ID'` | **98** |

### Batch 0 — the dependency and configuration floor

Sequenced first so every later batch ran under the ruff gate. Red was a collection error in both new test modules. Green delivered `src/credentials.py`, `src/model_factory.py`, `.env.example` and the `pyproject.toml` changes.

The tests assert on construction only — that `build_model` returns a `Model`, that `client_args` carries the endpoint and key, that `model_id` is the deployment name — because `OpenAIModel.__init__` merely stores configuration. No network call occurs, and none is mocked away.

### Batch 1 — the foundations every later batch stands on

The `ScriptedModel` fixture is the phase's most consequential piece of test infrastructure. It genuinely subclasses `strands.models.model.Model` and replays scripted stream events, so tests drive the **real** Strands event loop: the real `StructuredOutputContext`, the real synthetic tool spec, the real `EventLoopMetrics`. There is no `unittest.mock`, no `patch`, no `MagicMock` anywhere in `tests/test_unit/test_agents.py`. Had the tests patched `strands.Agent`, they would have verified nothing about the integration this phase exists to establish.

Two details make it decisive rather than merely offline. The structured-output tool name equals the Pydantic model's class name, so a scripted turn naming `PipelineScope` drives structured output while one naming `verify_legal_citation` drives a real tool call. And the model **raises when its script is exhausted** rather than repeating its last turn, so a test cannot pass by accident through unbounded re-prompting.

Green delivered `list_all_tools()`, `load_scoped_tools()`, the five schema models, `extract_telemetry`, and the ScopeParser factory and runner. `build_scope_parser_agent` takes no `client` parameter at all — structurally tool-free, which is stronger than asserting an empty tool list.

### Batch 2 — Scout

`test_scout_does_not_truncate_to_max_drafts` is the Rule 4 / D3 guard: a scope carrying `max_drafts=1` still yields every qualifying candidate, because the ceiling is the orchestrator's to apply. The Scout prompt states this explicitly — *"`max_drafts` may appear in the scope you are given: ignore it entirely."*

`test_scout_agent_receives_all_tools` asserts set equality against all five tool names, and `test_scout_agent_accepts_explicit_tool_scope` asserts both that the scoped request was made **and** that `list_all_calls == 0` — proving the narrow path was genuinely taken rather than a post-filter applied to a full listing. Both D19 paths are live; neither is dead code.

### Batch 3 — Writer, initial draft

Tool binding, `ArticleDraft` completeness, CTA traceability to the `get_tdi_service_offerings` result, and the `gpt-5.4` telemetry binding. The revision parameter did not yet exist.

### Batch 4 — Writer revision path (D18)

Red was a genuine `TypeError` on the unknown `revision` keyword — the runner had no such parameter.

`test_writer_revision_serialises_structured_payload` proves the previous headline, the QA issues and the previous `article_body` reach the model **verbatim**, read off `ScriptedModel`'s captured messages. Because `json.dumps(indent=2)` escapes newlines, multi-line fields are asserted line by line; every single-line field is asserted whole. The verbatim guarantee D18 requires holds either way — what it forbids is paraphrase, not escaping.

`test_agents_module_contains_no_loop_state` deviates from the plan, which described a text grep. A grep is unworkable here: the ScopeParser prompt must mention `max_drafts` in order to extract it, and the Scout prompt must mention it in order to ignore it. The test therefore parses `src/agents.py` with `ast` and asserts no `ast.While` node and no `Name`, `Attribute`, `arg`, `keyword` or definition named `attempts` or `max_drafts` in executable code — correctly blind to string literals, and stronger than a grep for catching `scope.max_drafts` as an attribute read. It does **not** assert on `ast.For`, because `extract_telemetry` legitimately iterates `tool_usage`.

This test passed at Red, since the seven-line stub already complied. It is an executable architectural constraint and a prospective regression guard, not TDD evidence for the batch — its docstring says so.

### Batch 5 — QA-Legal and the cross-cutting guards

`test_qa_legal_fact_checks_against_source_document` is the test the scoped design made impossible: QA calls `get_document_by_id` and raises an issue on a `key_obligations` mismatch. It exists because of D19.

`test_all_worker_prompts_declare_non_goals` is D19's enforcement. With tools no longer bounding roles, it requires every prompt to carry a `## Non-goals` section with at least three bullets and an explicit "you do not". The prompts satisfy it on substance: QA-Legal states *"You do NOT rewrite, edit, reword or improve the draft. Not one sentence."* The Writer states *"You do NOT silently drop a citation you could not verify. Keep it in the text and flag it explicitly … Deleting a doubtful citation to look clean is a serious violation."*

`test_scope_parser_invalid_output_raises` also deviates from plan. A `PipelineScope` tool-use missing the required `time_window` does not raise immediately — Strands treats the validation failure as a tool error, re-prompts, then forces the tool once. A single-turn script therefore recursed. The test scripts three turns and accepts `(StructuredOutputException, ValidationError)`; what changed is the exception class the SDK surfaces after its own retry, not the strength of the assertion.

### Review iterations

Two iterations were used of the three available.

**Iteration 1** — architect `APPROVED WITH RESERVATIONS` (1 major, 3 minor), QA `CHANGES REQUIRED` (3 major, 3 minor). Both reviewers agreed `src/` was correct; every finding was a test that would stay green against a broken implementation, and three were proven by deliberate source mutation:

- `tests/test_unit/test_credentials.py` read the developer's real OS environment. `_env_file=<tmp_path>` neutralises the project `.env`, but `pydantic-settings` ranks environment variables **above** dotenv. With `HSE_MODEL_*` exported the suite went red — including `test_credential_manager_missing_vars_raises` reporting `DID NOT RAISE`, meaning the test written to prove missing keys are caught was silenced on any correctly configured machine.
- Two telemetry assertions used `>= 0.0` against fields defaulting to `0.0`. Replacing the source keys with typos left all 38 tests green — 2 of 8 Rule 6 mappings were untested.
- `test_scout_applies_newsworthiness_scoring` asserted only inside a loop, so it passed on an empty list.

**The fix pass touched only the three test files; `src/` was not modified**, verified by checksum. No test was added or removed.

One fix deviated from the suggested remedy. The proposed `> 0.0` assertion for the duration mappings proved flaky: `EventLoopMetrics` timestamps with `time.time()`, whose resolution on this machine is 15.625 ms, so `total_duration` measured `0.0` in most runs and tool `total_time` in all of them. The replacement records a known duration on the real `EventLoopMetrics` / `ToolMetrics` objects — public, documented dataclass fields the Strands metrics guide itself directs users to read — and asserts the re-projection relative to a captured baseline. Both reviewers verified the premise independently and accepted it as stronger than their own suggestion. *(One claim in the fix report was itself wrong and was corrected in the review artifacts: `end_cycle` **is** called and `cycle_durations` is `[0.0]` rather than empty. Clock resolution alone explains the zero; the fix is unaffected.)*

**Iteration 2** — architect `APPROVED`, QA `PASSED`. Zero new findings from either. QA reproduced every acceptance criterion by mutation, confirming each previously-escaping defect now fails loudly, and reverted everything.

---

## 4. Test Results

Verified directly, not reported from a subagent:

```
.venv/Scripts/python.exe -m pytest tests/ -q
98 passed in 20.13s
```

| Scope | Count |
| :--- | ---: |
| `tests/test_unit/test_agents.py` | 38 |
| `tests/test_unit/test_credentials.py` | 7 |
| `tests/test_unit/test_model_factory.py` | 4 |
| **Phase 5 new tests** | **49** |
| `tests/test_integration/test_mcp_client.py` | 12 (1 replaced, 11 untouched) |
| Unit suite | 78 in 2.54 s |
| Integration suite | 20 in 19.26 s |
| **Full suite** | **98 passed, 0 failed, 0 skipped, 0 warnings** |

Baseline was 49. The unit suite runs in under three seconds because no unit test opens a socket or spawns a subprocess; the integration suite's ~19 s is the substrate subprocess, unchanged from Phase 4. Process censuses before and after a full run show no orphaned `uv` or `fastmcp` processes.

Zero warnings was verified more strictly than a plain run: the unit suite passes under `-W error`, and the full suite under `-W error::DeprecationWarning`. `pyproject.toml` declares no `filterwarnings`, so that pass is load-bearing.

**Ruff:** `All checks passed!` across all six Phase 5 files. The repository still reports 46 findings, all on pre-existing Phase 2–4 lines and deferred to Phase 7 by decision — including the two `E402` violations at `tests/test_integration/test_mcp_client.py:80-81`, deliberately left in place. The architect verified the zero-introduced claim by extracting the `HEAD` copies of the three modified files into a scratch tree and comparing: 34 findings at `HEAD`, 34 in the working tree, delta zero.

---

## 5. Architectural Compliance

| Constraint | How it is satisfied |
| :--- | :--- |
| **"Code owns the flow"** (ARCHITECTURE §1) | `src/agents.py` contains no routing, no `attempts` counter, no `while` loop, no `max_drafts` read, no `RevisionPayload` construction, no file I/O, no template call, no cost computation, no MCP lifecycle ownership. Enforced by an executable AST guard, not just review. |
| **Rule 2 — typed contracts** | Every worker returns `WorkerOutput[T]`. No `dict[str, Any]` crosses a module boundary; `metrics.get_summary()` is read at exactly one line, inside `extract_telemetry`. |
| **Rule 3 — bounded revision loop** | Correctly *absent*. `run_writer` accepts a `RevisionPayload` but reads no counter from it and mutates nothing; `run_qa_legal` returns the tri-state report as issued without interpreting it. |
| **Rule 4 / D3 — no truncation** | `run_scout` returns all qualifying candidates. Asserted against a scope carrying `max_drafts=1`, and stated in the Scout prompt. |
| **Rule 6 / D17 — telemetry** | Every SPECIFICATIONS §3.4 field mapped, including `tool_invocations` from `tool_usage.<name>.execution_stats` and the carried `model_id`. |
| **Rule 7 — TDD** | Six batches, each with a distinct observed Red signal. The one test that passed at Red is documented as an architectural constraint rather than counted as evidence. |
| **D8 — structured output** | Always `structured_output_model=`. The deprecated `Agent.structured_output()` appears nowhere in `src/`. |
| **D13 — substrate isolation** | All MCP transport detail stays in `src/mcp_client.py`; `src/agents.py` imports nothing from `strands.tools.mcp`. |
| **D16 — zero-cost determinism** | No unit test makes a network call, spawns a subprocess, or reads a real `.env`. `ScriptedModel` drives the real event loop offline; an autouse fixture clears `HSE_MODEL_*` from the process environment. |
| **D18 — structured object passing** | The revision payload is embedded as JSON. Proven verbatim for the previous headline, body and QA issues. |
| **D19 — unscoped tools** | Scout, Writer and QA-Legal receive all five tools; ScopeParser is structurally tool-free. Both the default and the narrowing path are exercised, so neither is dead code. |
| **Provider isolation** | `grep -rn "strands.models" src/` matches only `src/model_factory.py` and the abstract `Model` import in `src/agents.py`. |
| **Clean stdout** (ARCHITECTURE §6.3) | `callback_handler=None` on all four factories. No `logging` call anywhere in `src/agents.py`. |
| **Secrets** | `git ls-files .env` is empty; `.env.example` is committed-ready; keys are `SecretStr` and masked in `str()` and `repr()`; no literal key or endpoint in `src/` outside `credentials.py` defaults. |

### Carried into Phase 6

1. **D19 traded structural enforcement for prompt enforcement plus telemetry detection.** The detection half only pays off if Phase 6 actually surfaces `tool_invocations` in the draft's telemetry section. Otherwise D19's compensating control is inert, and the boundary rests on prompts alone. This warrants an explicit gate in the Phase 6 plan.
2. **The factories require a connected client** and fail fast with `MCPClientNotConnectedError`. Phase 6 must construct all four agents *inside* the `with HSEMockMCPClient()` block, and must not cache an agent across sessions.
3. **No live endpoint was exercised.** Batch 0's tests assert on construction only. The first real call against Azure AI Foundry is a Phase 6 or Phase 8 event, and remains unproven until then.
