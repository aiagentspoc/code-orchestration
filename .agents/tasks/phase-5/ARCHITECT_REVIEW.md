# Phase 5 — Architect Review (Stage 3, iteration 1)

**Scope audited:** `src/agents.py`, `src/credentials.py`, `src/model_factory.py`, `src/schemas.py`,
`src/mcp_client.py`, `tests/test_unit/test_agents.py`, `tests/test_unit/test_credentials.py`,
`tests/test_unit/test_model_factory.py`, `tests/test_integration/test_mcp_client.py`,
`pyproject.toml`, `.env.example`, and the `ARCHITECTURE.md` / `SPECIFICATIONS.md` deltas (D19, §3.3-3.4).

**Method:** `git diff` for modified files, direct reads for the six untracked files, plus independent
execution — `pytest tests/ -q` (98 passed, 20.24 s), `pytest tests/test_unit -q -W error`
(78 passed, 2.61 s), `pytest tests/test_integration -q` (20 passed, 19.80 s, no orphan processes),
and `ruff check src tests --no-cache` against both the working tree and the `HEAD` copies of every
modified file.

---

## 1. Overall Alignment Verdict

### `APPROVED WITH RESERVATIONS`

The phase ships exactly what Revision 5 of the plan specifies. The Phase 5/6 boundary is clean, the
D19 two-way tool binding is real and doubly tested, provider isolation holds, the telemetry envelope
maps every field in SPECIFICATIONS §3.4, and the four system prompts are substantive role boundaries
rather than box-ticking. Ruff introduces **zero** new findings — independently verified, not taken on
trust.

One reservation blocks a clean `APPROVED`: two credential tests are not isolated from the process
environment and fail deterministically when the `HSE_MODEL_*` variables are exported — which is the
project's own documented production configuration path. That is a Major test-hygiene defect in a file
this phase created, so it is in-scope and fixable inside the phase. It is not an architectural
violation and does not put the design at risk.

---

## 2. Principle Compliance Audit — the 6 Pillars

| # | Pillar | Status | Evidence |
| :--- | :--- | :---: | :--- |
| 1 | Code Owns the Flow | ✅ | `src/agents.py` contains no `while`, no `for` over pipeline state, no `attempts`, no `max_drafts` read, no routing, no persistence, no template call, no cost computation, no MCP lifecycle ownership, no `logging` import at all. Runners are one LLM round trip each (`src/agents.py:340`). No agent is passed as a tool to another agent; no swarm/graph/handoff primitive is imported. |
| 2 | Bounded Revision Loop | ✅ (N/A, correctly) | `run_writer` (`src/agents.py:468-505`) accepts `revision: RevisionPayload \| None` and reads no counter; `attempt` reaches the model only through the caller's serialized payload. `run_qa_legal` returns the report as issued and interprets nothing. Guarded by `test_writer_revision_does_not_manage_attempts` (`tests/test_unit/test_agents.py:843-858`). |
| 3 | Substrate Isolation (MCP over stdio) | ✅ | All transport detail stays in `src/mcp_client.py`: `list_all_tools` (`:68-71`) and `load_scoped_tools` (`:73-81`) own `list_tools_sync`/`tool_filters`. `src/agents.py` imports only `strands`, `strands.agent.agent_result`, `strands.models.model`, `strands.types.tools` — nothing from `strands.tools.mcp` (`src/agents.py:20-23`). Integration run leaves process count unchanged (4 → 4). |
| 4 | Human-in-the-Loop Gate | ✅ (N/A) | Phase 5 emits no artifact and writes no file. |
| 5 | Deterministic Candidate Throttling | ✅ | `run_scout` docstring and `SCOUT_SYSTEM_PROMPT:153-155` forbid truncation explicitly ("`max_drafts` may appear in the scope you are given: ignore it entirely"), enforced by `test_scout_does_not_truncate_to_max_drafts`. |
| 6 | Code Quality & Python Conventions | ✅ | Ruff: **0 findings introduced**. All six new files annotate every signature (PEP 484/585/604), carry module + function + model docstrings, declare `__all__`, and end with a single newline. No `dict[str, Any]` anywhere in `src/` except one docstring reference (`src/agents.py:258`). |

---

## 3. Plan §5 Checklist — 24 gates + 3a

| # | Gate | Result |
| :---: | :--- | :--- |
| 1 | No routing / `attempts` / `while` / `max_drafts` truncation / file I/O / `RevisionPayload` construction in `src/agents.py` | ✅ verified by grep and by AST guard |
| 2 | No agent-as-tool, no multi-agent primitive | ✅ |
| 3 | All 5 tools for Scout/Writer/QA-Legal, `[]` for ScopeParser; explicit `tool_names` still narrows | ✅ **both paths live** (see §4 below) |
| 3a | Every prompt states substantive non-goals | ✅ **judged on substance, passes** (see §5 below) |
| 4 | MCP transport confined to `src/mcp_client.py` | ✅ |
| 5 | No Markdown/template formatting in `src/agents.py` | ✅ |
| 6 | Factories, not import-time instances; no subprocess at import | ✅ module level holds only `Final` constants and a `TypeVar` |
| 7 | `grep -rn "strands.models" src/` → only `model_factory.py` + abstract `Model` | ✅ `src/agents.py:22` (abstract), `src/model_factory.py:13-14` (abstract + `OpenAIModel`) |
| 8 | ≤ 1 substrate subprocess per integration test | ✅ process count 4 before / 4 after; `test_scoped_tool_lists_share_one_session` resolves 3 scopes off one session |
| 9 | Every worker returns `WorkerOutput[T]`; `get_summary()` read only in `extract_telemetry` | ✅ `src/agents.py:269` is the sole call site |
| 10 | All new models carry `ConfigDict(extra="ignore")` | ✅ `src/schemas.py:162, 176, 192, 205, 223` |
| 11 | `structured_output_model=` only; zero deprecated `agent.structured_output(` | ✅ only occurrence is the docstring at `src/agents.py:328`; the fixture at `tests/test_unit/test_agents.py:157-162` raises if the deprecated path is ever taken |
| 12 | Telemetry maps §4.4 in full, carries `model_id`, populates `tool_invocations` | ✅ `src/agents.py:269-295`; asserted end-to-end by four tests |
| 13 | No literal key/endpoint/deployment in `src/` outside `credentials.py` defaults; `git ls-files .env` empty; `.env.example` committed-ready | ✅ `git ls-files .env` → empty; `git check-ignore -v .env.example` → matched by the `!.env.example` negation, i.e. it *will* commit |
| 14 | `SecretStr`, masked in `str()`/`repr()` | ✅ `src/credentials.py:34, 53, 56`; `test_api_key_is_masked_in_str_and_repr` |
| 15 | Unit tests never read a developer's real credentials | 🟡 **partially** — `.env` is isolated, the *process environment* is not. See Finding M-1. |
| 16 | No `logging.basicConfig` / handler attachment at import | ✅ `grep -rn "logging" src/` → no match |
| 17 | `callback_handler=None` on every agent | ✅ all four factories; asserted `is null_callback_handler` in three tests |
| 18 | No unit test makes a network call or spawns a subprocess; runtime near baseline | ✅ 78 unit tests in 2.61 s; full suite 20.24 s vs 19.73 s baseline |
| 19 | Zero ruff findings introduced | ✅ **independently verified** — see §6 |
| 20 | Complete PEP 484/585/604 annotations | ✅ no unannotated `def` in any new file |
| 21 | `__all__` in all three new modules; docstrings throughout | ✅ `agents.py:38`, `credentials.py:16`, `model_factory.py:18` |
| 22 | No dead code or stub comments; two blank lines; trailing newline | ✅ the Phase 4 7-line stub is fully replaced |
| 23 | Suite green, zero warnings, prior 49 still pass | ✅ 98 passed; `-W error` clean on the unit suite |
| 24 | TDD evidence per batch | ✅ with one qualification — see §7.4 |

---

## 4. D19 tool access is genuinely two-way (gate 3)

Neither branch of `_resolve_tools` (`src/agents.py:298-316`) is dead code:

- **Default (all 5).** `tool_names=None` → `client.list_all_tools()`. Exercised by
  `test_scout_agent_receives_all_tools` (`:517`), `test_writer_agent_receives_all_tools` (`:685`),
  `test_qa_legal_agent_receives_all_tools` (`:902`) — each asserting `len(agent.tool_names) == 5`
  **and** that the full set matches the five substrate names, not merely the count.
- **Narrowed.** An explicit sequence → `client.load_scoped_tools(names)`. Exercised by
  `test_scout_agent_accepts_explicit_tool_scope` (`:530`) and by the second half of the Writer and
  QA-Legal tests (`:695-697`, `:912-914`). The Scout test additionally asserts
  `client.list_all_calls == 0`, proving the narrowed path was taken rather than the default path
  plus a post-filter.
- **Tool-free.** `build_scope_parser_agent` takes no `client` parameter at all
  (`src/agents.py:355-368`) — structurally incapable of receiving tools, which is stronger than an
  assertion. `test_scope_parser_agent_has_no_tools` confirms `agent.tool_names == []`.
- **Transport level.** `load_scoped_tools` is verified offline against a recording session
  (`tests/test_unit/test_agents.py:355-367`, asserting the exact `{"allowed": [...]}` filter) and
  live against the real substrate (`tests/test_integration/test_mcp_client.py:90-120`), including
  that the same session still serves an unscoped listing afterwards.

---

## 5. Prompts as the role boundary (gate 3a) — judged on substance

With tools unscoped, the prompts are the only structural guard. I read all four in full rather than
checking for a heading. They pass, and they are not generic.

- **ScopeParser** (`src/agents.py:106-114`) — six non-goals, each naming the owner of the displaced
  responsibility. Critically it forbids the failure mode D19 creates for a tool-free extractor:
  "You do NOT query the regulatory substrate … the scope comes from the user's words, not from what
  happens to exist," and "You do NOT decide how many drafts the pipeline produces."
- **Scout** (`:148-157`) — forbids drafting, forbids presenting a citation as verified, and states
  the Rule 4 constraint in operational terms: "`max_drafts` may appear in the scope you are given:
  ignore it entirely. Returning fewer candidates than qualify is a Rule 4 violation."
- **Writer** (`:193-205`) — the plan's specific concern is met head-on: "You do NOT silently drop a
  citation you could not verify. Keep it in the text and flag it explicitly in the article body (for
  example: 'riferimento da verificare'), so QA-Legal still sees the signal. Deleting a doubtful
  citation to look clean is a serious violation: it hides a defect the audit exists to catch." It
  also forbids issuing any compliance verdict and forbids tracking a revision counter.
- **QA-Legal** (`:240-250`) — "You do NOT rewrite, edit, reword or improve the draft. Not one
  sentence. You report defects; the Writer fixes them," plus no replacement copy, no CTA selection,
  no retry decision, and a prohibition on softening a status. The prompt also carries the D19
  justification operationally: §Task item 2 requires `get_document_by_id` to check statutory
  statements against `key_obligations`/`penalties_summary`, which is precisely the capability
  scoping had denied it.

The `test_all_worker_prompts_declare_non_goals` gate (`tests/test_unit/test_agents.py:1063-1072`) is
itself non-trivial: it requires the `## Non-goals` heading, at least three bullets, and the literal
phrase "you do not" inside the section. That is a reasonable mechanical floor; the substance above is
what carries the gate.

---

## 6. Mandatory lint pass

Command: `.venv/Scripts/ruff.exe check src tests --no-cache` → **46 errors**.

### In-scope findings introduced by Phase 5 — **0 (blocking: none)**

Verified independently rather than accepted from the implementation report. I extracted the `HEAD`
copies of the three modified Python files into a scratch tree with the same relative paths and the
same `pyproject.toml`, and ran ruff against both:

| File | Findings at `HEAD` | Findings in working tree | Delta |
| :--- | :---: | :---: | :---: |
| `src/schemas.py` | 19 | 19 | **0** |
| `src/mcp_client.py` | 9 | 9 | **0** |
| `tests/test_integration/test_mcp_client.py` | 6 | 6 | **0** |
| **Total, modified files** | **34** | **34** | **0** |

The six files Phase 5 created — `src/agents.py`, `src/credentials.py`, `src/model_factory.py`,
`tests/test_unit/test_agents.py`, `tests/test_unit/test_credentials.py`,
`tests/test_unit/test_model_factory.py` — appear nowhere in ruff output: **0 findings**.
Arithmetic closes: 34 (modified) + 12 (untouched files) = 46 total.

The claim of zero introduced findings is **confirmed**.

### Pre-existing debt — 46, deferred to Phase 7 by human decision (non-blocking)

| Rule | Count | Where |
| :--- | :---: | :--- |
| `UP006` (`List` → `list`) | 11 | `src/schemas.py`, `tests/test_integration/test_substrate_compatibility.py` |
| `UP045` (`Optional` → `X \| None`) | 10 | `src/schemas.py` (7), `src/template_engine.py` (3) |
| `I001` (import block unsorted) | 10 | 10 files across `src/` and `tests/` |
| `E701` (multiple statements on one line) | 8 | `src/mcp_client.py` |
| `F401` (unused import) | 3 | `tests/test_integration/test_mcp_client.py` (2), `tests/test_unit/test_template_engine.py` (1) |
| `UP035` (deprecated `typing` import) | 2 | `src/schemas.py`, `tests/test_integration/test_substrate_compatibility.py` |
| `E402` (import not at top) | 2 | `tests/test_integration/test_mcp_client.py:80, :81` |

Count is unchanged from the Stage 1 baseline. These are **not** blocking and must not be fixed inside
Phase 5 — including the six findings sitting in files this phase modified. The 2 × `E402` at
`tests/test_integration/test_mcp_client.py:80-81` remain deferred per plan §6 Q8. I did not run
`ruff check --fix`.

---

## 7. The three self-reported deviations, plus the Red question

### 7.1 AST walk instead of a text grep — **sound, and net stronger. Accepted.**

`test_agents_module_contains_no_loop_state` (`tests/test_unit/test_agents.py:861-884`) parses
`src/agents.py` and walks the tree, flagging `ast.Name`, `ast.Attribute`, `ast.arg` and
definition names matching `{"attempts", "max_drafts"}`, and asserting no `ast.While` node exists.

The rationale is correct and unavoidable: `SCOPE_PARSER_SYSTEM_PROMPT:102` must mention `max_drafts`
to instruct extraction of it, and `SCOUT_SYSTEM_PROMPT:153` must mention it to instruct ignoring it.
A text grep would have to be defeated by string-splitting the prompts — strictly worse. The AST form
is *stronger* than a grep on the axis that matters: `scope.max_drafts` as an attribute read is caught
(`ast.Attribute`), whereas a grep whitelisting the prompt regions could miss it.

Two residual gaps (Finding m-2). First, `ast.keyword` is not inspected, so `PipelineScope(max_drafts=1)`
inside `src/agents.py` would pass the guard — cheap to close and worth closing. Second, only
`ast.While` is asserted against, not `ast.For`; the plan named only `while`, so this is faithful to
the plan, and a blanket `ast.For` assertion is in fact **not** available, because
`extract_telemetry` legitimately iterates `tool_usage` at `src/agents.py:274`. Closing that second
gap would require scoping the check by function, which is more machinery than the risk warrants.

### 7.2 Three-turn script accepting `StructuredOutputException` — **legitimate. Accepted.**

`test_scope_parser_invalid_output_raises` (`:466-478`) scripts one invalid `PipelineScope` turn
followed by two text turns, and accepts `(StructuredOutputException, ValidationError)`.

This does not weaken the test, for a concrete reason: `ScriptedModel.stream` raises `AssertionError`
on script exhaustion (`:175-178`) rather than repeating the last turn. So the test cannot pass by
accident through unbounded re-prompting — if Strands took a fourth turn the test would fail loudly
with a different exception type than the one `pytest.raises` accepts. The assertion the plan wanted
("a payload missing `time_window` never surfaces as a valid scope") is fully preserved; what changed
is only the exception class the real SDK surfaces after its internal retry, which is a fact about
Strands, not a concession. Accepting a two-tuple is correct here rather than lax.

### 7.3 PEP 585 `list[...]` instead of the spec's `List[...]` — **correct call.**

`pyproject.toml` now selects `UP`, so `List[ScoutCandidate]` in new code would emit `UP006` and
violate gate 19 on the same run. The SPECIFICATIONS §3.3-3.4 snippets are illustrative contracts, not
literal source; CLAUDE.md and the review skills both mandate PEP 585/604. The implementation chose
correctly.

The consequence is a documentation drift the orchestrating agent should close: SPECIFICATIONS §3.3-3.4
still shows `List[...]`, which now disagrees with both `src/schemas.py` and the repo's own lint
configuration. See Finding m-1 — a docs fix, outside the implementation subagent's write scope.

### 7.4 Did `test_agents_module_contains_no_loop_state` pass at Red? — **acceptable under Rule 7.**

It did, and it could not have done otherwise: it is an invariant assertion over module structure, not
a behavioural test, so it is green whenever the invariant holds. Rule 7's "confirm it fails for the
expected reason" is aimed at tests that *drive* an implementation; this one guards a boundary that
D19 makes load-bearing. The honest description is "an executable architectural constraint, not a
TDD driver" — it is valuable and should stay, but it should not be counted as TDD evidence for the
Batch 4 code. Every *behavioural* test in the phase does have a stated Red failure. No action.

---

## 8. Code Review Findings by Severity

### 🔴 Blocker — none

### 🟡 Major — 1

**M-1 · `tests/test_unit/test_credentials.py:41-77` — two tests are not isolated from the process environment.**

`test_credential_manager_reads_env_file` and `test_credential_manager_missing_vars_raises` construct
`CredentialManager(_env_file=<tmp_path>)` without passing explicit field values. `pydantic-settings`
ranks environment variables **above** dotenv values, so exported `HSE_MODEL_*` variables silently
override the fixture. Reproduced:

```
$ HSE_MODEL_FAST_ENDPOINT=... HSE_MODEL_FAST_API_KEY=... \
  HSE_MODEL_STRONG_ENDPOINT=... HSE_MODEL_STRONG_API_KEY=... pytest tests/test_unit/test_credentials.py -q
FAILED test_credential_manager_reads_env_file   - assert ... == 'https://leaked.example/'
FAILED test_credential_manager_missing_vars_raises - DID NOT RAISE ValidationError
2 failed, 5 passed
```

This is the exact configuration `.env.example` tells a developer to set up, so the suite becomes
red on a correctly-configured machine. It breaks code-reviewer Gate 1 ("fast, **isolated** tests")
and the intent of plan audit item 15. Remedy in `FIXES.md`.

### 🟢 Minor — 3

**m-1 · `.agents/docs/SPECIFICATIONS.md:245` — stale sentence contradicts D19.**
§3.4 still closes with "…without relaxing the scoped tool bindings in ARCHITECTURE §3." That was true
under plan Revision 4; D19 explicitly relaxes exactly those bindings. Reword to state that
`tool_invocations` is the *detection* mechanism for role bleed now that the bindings are unscoped.
**Docs, not `src/` — routed to the orchestrating agent, not to `FIXES.md`.**

**m-2 · `tests/test_unit/test_agents.py:871-884` — AST guard has a blind spot.**
Add `ast.keyword` to the walk (catches `PipelineScope(max_drafts=1)`). `FIXES.md` carries the exact
change, including the caveat that a blanket `ast.For` assertion would fail against the legitimate
`tool_usage` iteration in `extract_telemetry`.

**m-3 · `src/schemas.py:216` — bare public `T = TypeVar("T", bound=BaseModel)`.**
The schemas module exports a single-letter public name while `src/agents.py:61` uses the private,
descriptive `_PayloadT` for the same concept. It matches the SPECIFICATIONS snippet verbatim and is
harmless, so I am **not** raising it as an actionable fix — recorded only so the inconsistency is
visible if a future phase consolidates typing conventions.

### Informational (no action)

- `_run_worker` parametrises `WorkerOutput[output_model]` with a runtime variable
  (`src/agents.py:341`). Runtime-correct and in fact beneficial — Pydantic validates `payload`
  against the concrete model, so a `None` `structured_output` fails loudly rather than propagating.
  A static type checker would object, but the project runs no type checker; ruff is clean.
- `src/mcp_client.py:29`'s hardcoded default server path is pre-existing Phase 4 debt and is a
  filesystem path, not a credential. Out of scope for gate 13.

---

## 9. Anti-Patterns and Risks

No autonomy leak, no state coupling, no hidden control flow, no dead code. Two forward-looking risks
worth carrying into Phase 6 rather than fixing here:

1. **Role bleed is now detectable, not preventable.** D19 traded structural enforcement for
   prompt-level enforcement plus `tool_invocations` telemetry. The detection half only pays off if
   Phase 6 actually surfaces per-worker tool usage in the draft telemetry section. If it does not,
   D19's compensating control is inert. Recommend Phase 6's plan carry an explicit gate on this.
2. **`_resolve_tools` requires a connected client.** Factories fail fast with
   `MCPClientNotConnectedError` (verified by `test_factory_requires_live_client`), which is the right
   behaviour — but it means Phase 6 must construct all four agents *inside* the `with
   HSEMockMCPClient()` block and must not cache an agent across sessions. Plan §4.6 says so; it needs
   to survive into the Phase 6 plan.

---

## 10. Remediation Directives

| ID | Severity | Owner | Action |
| :--- | :--- | :--- | :--- |
| M-1 | 🟡 Major | `implementation` | Isolate the two credential tests from the process environment — `FIXES.md` → Code Quality & Conventions |
| m-2 | 🟢 Minor | `implementation` | Extend the AST guard with `ast.keyword` and `ast.For` — `FIXES.md` |
| m-1 | 🟢 Minor | orchestrating agent | Reword `.agents/docs/SPECIFICATIONS.md:245` to match D19 |
| m-3 | — | none | Recorded only |

**Ruff: 0 introduced (blocking) / 46 pre-existing (deferred to Phase 7).**

---
---

# Phase 5 — Architect Review (Stage 3, iteration 2)

**Scope re-audited:** the three files the fix pass touched — `tests/test_unit/test_agents.py`,
`tests/test_unit/test_credentials.py`, `tests/test_unit/test_model_factory.py` — plus independent
re-verification that `src/` is untouched, that the `.agents/docs/SPECIFICATIONS.md` doc-drift item is
closed, and that the plan §5 gates most exposed to test churn (3, 3a, 15) still hold.

**Method:** `git diff src/` plus content hashing of `src/agents.py`, `src/schemas.py`,
`src/mcp_client.py`; direct reads of every changed region; mutation testing in an out-of-tree mirror
(no repository file was modified); inspection of the installed
`.venv/Lib/site-packages/strands/telemetry/metrics.py`; empirical clock and metrics probes;
`pytest tests/ -q -W error` (98 passed), `pytest tests/test_unit -q` x 6 (78 passed each),
`pytest tests/test_integration -q` (20 passed, process counts unchanged), a run under a fully
polluted `HSE_MODEL_*` environment, and `.venv/Scripts/ruff.exe check src tests --no-cache`.

---

## 1. Overall Alignment Verdict — iteration 2

### `APPROVED`

All four iteration-1 findings are closed on disk. Nothing regressed: `src/` is byte-identical to its
iteration-1 state, both D19 tool paths are still exercised, the prompt-as-role-boundary gate is
intact, and test isolation now holds under the exact environment `.env.example` tells a developer to
create. Ruff is unchanged at **0 introduced / 46 pre-existing (deferred)**. I raise **no new
findings**.

The one deviation referred to my judgement — the QA-1 replacement technique — is **sound and
accepted**; I verified its premises against the installed SDK myself and reproduced its mutation
result. One factual detail in the fix agent's justification is wrong and is corrected in §5 below;
the code is nevertheless correct and no change is warranted.

---

## 2. Iteration-1 findings — closure status

| ID | Severity | Status | Evidence on disk |
| :--- | :--- | :--- | :--- |
| **M-1** (= qa's QA-3) | Major | **Closed** | Autouse `_isolate_environment(monkeypatch)` at `tests/test_unit/test_credentials.py:27-38`, keyed off `_EXPLICIT_VALUES` (`:17-24`) so it cannot drift; mirrored at `tests/test_unit/test_model_factory.py:26-35`. Re-ran both files with all six `HSE_MODEL_*` exported to leaked values: **11 passed**. Previously 2 failed under the same conditions. The autouse form was the one I proposed. `.env.example` uses only the six uppercase names the fixture strips, so the documented configuration path is fully covered. |
| **m-2** | Minor | **Closed as specified** | `ast.keyword` branch present at `tests/test_unit/test_agents.py:921-923` with an inline comment naming the case it catches. The `ast.For` half was correctly **not** applied — my own §7.1 stated a blanket `ast.For` assertion is unavailable because `extract_telemetry` legitimately iterates `tool_usage` at `src/agents.py:274` (still there, still legitimate). My §10 remediation row was looser than my §7.1 analysis; the implementation followed the analysis, which is the right call. |
| **m-1** | Minor | **Closed** | `.agents/docs/SPECIFICATIONS.md:245` now reads "...`tool_invocations` is the compensating control that makes role bleed **detectable** after the fact." The stale clause "without relaxing the scoped tool bindings in ARCHITECTURE §3" is gone (grep returns nothing). It now agrees with D19 and adds the correct forward obligation on Phase 6. |
| **m-3** | — | **Correctly no action** | `src/schemas.py:216` unchanged, as recorded. |

---

## 3. Regression check — `src/` is untouched

The claim was verified independently, not accepted:

- `git diff src/agents.py | md5sum` is byte-stable across two samples taken ~10 minutes apart in this
  session: `037ed2f9140791d11afff9347363a6c9` both times.
- Every structural anchor cited in the iteration-1 review still resolves to the same line:
  `_PayloadT` :61; the four prompts :85 / :118 / :161 / :209 with `## Non-goals` at
  :106 / :148 / :193 / :240; `extract_telemetry` :254 (sole `get_summary()` call at :269,
  `tool_usage` loop at :274); `_resolve_tools` :298; `_run_worker` :319;
  `build_scope_parser_agent` :355; `run_writer` :468. 558 lines, unchanged.
- `grep -n max_drafts src/agents.py` returns four hits, all in docstrings or prompts
  (:7, :102, :153, :423). No executable reference.
- `src/credentials.py`, `src/model_factory.py`, `src/mcp_client.py` and `src/schemas.py` all carry
  pre-iteration-1 mtimes.

**Note on a transient observation.** One `pytest tests/test_unit` run during this audit reported
`test_agents_module_contains_no_loop_state` as failed; six subsequent runs of the same command
passed, and `src/agents.py`'s mtime advanced twice during the session while its content hash stayed
constant. That signature is a concurrent mutate-and-restore cycle by the `qa` reviewer running in
parallel, not a flaky test: the assertion is a pure function of the file's bytes. Recorded so the
observation is not later mistaken for intermittency in the guard.

---

## 4. Plan §5 gates most exposed to test churn

| Gate | Result |
| :--- | :--- |
| **3 — D19 two-way tool paths, neither dead** | PASS, unchanged, both live. Default path: `test_scout_agent_receives_all_tools` (`:543-553`), `test_writer_agent_receives_all_tools` (`:716-728`), `test_qa_legal_agent_receives_all_tools` (`:944-956`) each assert `len(agent.tool_names) == 5` **and** set-equality with `SUBSTRATE_TOOL_NAMES`. Narrowed path: `test_scout_agent_accepts_explicit_tool_scope` (`:556-564`) still asserts `client.scope_requests == [list(SCOUT_TOOL_NAMES)]` **and** `client.list_all_calls == 0`, which is what proves the narrowed branch was taken rather than the default path plus a post-filter; the Writer and QA-Legal tests keep their scoped second halves. |
| **3a — prompts as the role boundary** | PASS, intact. The prompts live in `src/agents.py`, which is byte-identical, so the substance assessed in iteration 1 §5 stands unmodified. The mechanical gate `test_all_worker_prompts_declare_non_goals` (`:1105-1114`) is unchanged and still requires the heading, at least three bullets, and the literal "you do not" inside the section. |
| **15 — test isolation** | PASS, now genuinely held; see §2 M-1. Both new fixtures are autouse, fully annotated (`monkeypatch: pytest.MonkeyPatch) -> None`), docstringed, and use `delenv(..., raising=False)` so they are safe on a clean machine. |
| **23 — suite green, zero warnings** | PASS. `98 passed` under `-W error`; 78 unit + 20 integration; no test added or removed (38 + 7 + 4 `def test_` across the three changed files, matching iteration 1). |
| **18 / process lifecycle** | PASS. The integration run leaves process counts unchanged (`uv.exe` 2 -> 2, `python.exe` 4 -> 4). No orphans. |

The two qa-raised fixes that touch my area are sound: `test_scout_applies_newsworthiness_scoring`
(`:599-627`) now pins `len(candidates) == 3` and the doc-id ordering before its three iterating
assertions, so it can no longer pass vacuously; `test_writer_revision_serialises_structured_payload`
(`:853-875`) now asserts every line of `_PREVIOUS_DRAFT.article_body` reaches the model,
strengthening the D18 structured-passing guarantee.

---

## 5. The QA-1 deviation — judged on merit: sound, accepted

The fix agent declined the suggested `> 0.0` diff and instead mutates the real SDK metrics object and
re-projects. I verified its premises rather than taking them.

**Premise 1 — coarse clock. Confirmed.** `EventLoopMetrics.start_cycle` and `end_cycle` time with
`time.time()` (`.venv/Lib/site-packages/strands/telemetry/metrics.py:292, :314`), `Trace` likewise
(`:49, :62`), and `total_duration` is `sum(self.cycle_durations)` (`:431`). On this interpreter
`time.get_clock_info("time").resolution` is **0.015625 s**. Probing the single-cycle scenario used by
`test_extract_telemetry_maps_usage_and_latency` gave `cycle_durations == [0.0]` and
`total_duration == 0.0` in **6 of 6** runs; probing the two-cycle tool scenario gave
`execution_stats.total_time == 0.0` in **3 of 5** runs. A `> 0.0` assertion is therefore either
always-failing or intermittently failing, exactly as reported. The suggested diff was not safe.

**Premise 2 — "`total_duration` is structurally 0.0 because the structured-output path ends without
`end_cycle`, leaving `cycle_durations` empty". Incorrect, and corrected here.** `end_cycle` *is*
called (`strands/event_loop/event_loop.py:335, :366, :786, :966`) and `cycle_durations` is
populated — it contains `[0.0]`, not `[]`. The value is 0.0 because the scripted cycle completes
inside one clock tick, not because the list is empty. The conclusion drawn from it is nonetheless
right, so the code needs no change; the record does, which is what this paragraph is.

**Is mutating SDK internals brittle coupling? No — acceptable, and here the stronger design.**
`cycle_durations`, `tool_metrics` and `ToolMetrics.total_time` are public dataclass fields documented
in the SDK's own class docstrings (`metrics.py:117, :124, :213, :222`), not private attributes, and
the test mutates the instance handed back by the SDK rather than patching the class. The test already
depends on the `get_summary()` key names, so this adds coupling only to three field names whose
rename would fail loudly with `AttributeError` / `KeyError`, never silently. The residual
false-positive mode — the SDK re-deriving `total_duration` from something other than
`sum(cycle_durations)` — is unlikely and also loud.

**Does it catch the defect it exists to catch? Yes — reproduced.** I mirrored `src/` and `tests/`
into a scratch tree (no repository file touched), applied the `TYPO_total_duration` /
`TYPO_total_time` mutation, and ran the unit file: **both** telemetry tests fail
(`Obtained: 0.0, Expected: 0.5`), 36 others pass. Under the originally-suggested assertion the first
would have passed on `0.0 == 0.0`. The replacement is strictly stronger than what was asked for.

One cleaner alternative exists — construct a synthetic `AgentResult` / `EventLoopMetrics` with pinned
values and call `extract_telemetry` on it directly, removing both the timing dependence and the
mutation. It is *not* better on balance: the current form also proves the real SDK still emits the
key names the projection reads. **Informational only; no action.**

---

## 6. Mandatory lint pass — iteration 2

Command: `.venv/Scripts/ruff.exe check src tests --no-cache` gives **46 errors**, identical to the
iteration-1 and Stage 1 baselines.

### In-scope findings introduced by Phase 5 — **0 (blocking: none)**

`ruff check` over the six files Phase 5 created — `src/agents.py`, `src/credentials.py`,
`src/model_factory.py`, `tests/test_unit/test_agents.py`, `tests/test_unit/test_credentials.py`,
`tests/test_unit/test_model_factory.py` — returns **`All checks passed!`**. The three *modified*
files were re-checked against their `HEAD` copies extracted into a scratch tree with the same
`pyproject.toml`: 34 findings at `HEAD`, 34 in the working tree, **delta 0**
(`src/schemas.py` 19 / `src/mcp_client.py` 9 / `tests/test_integration/test_mcp_client.py` 6).
Arithmetic closes: 34 + 12 in untouched files = 46.

### Pre-existing debt — 46, deferred to Phase 7 (non-blocking)

| Rule | Count |
| :--- | :---: |
| `UP006` | 11 |
| `UP045` | 10 |
| `I001` | 10 |
| `E701` | 8 |
| `F401` | 3 |
| `UP035` | 2 |
| `E402` | 2 |

By file: `src/schemas.py` 19, `src/mcp_client.py` 9, `tests/test_integration/test_mcp_client.py` 6,
`src/template_engine.py` 3, `tests/test_integration/test_substrate_compatibility.py` 3,
`tests/test_unit/test_template_engine.py` 2, and one each in `tests/test_unit/test_schemas.py`,
`tests/test_unit/test_packaging.py`, `tests/test_unit/test_module_structure.py` and
`tests/test_integration/test_smoke.py`.

These are **deferred to the Phase 7 cleanup milestone** and must not be fixed inside Phase 5. The
2 x `E402` at `tests/test_integration/test_mcp_client.py:80-81` remain deliberately deferred per plan
§6 Q8 and are not flagged. I did not run `ruff check --fix`.

---

## 7. New findings

**None.** No blocker, no major, no minor. The fix pass changed only test files, changed them
correctly, added no dead code, kept every new fixture fully annotated and docstringed, and left the
lint surface unmoved. `FIXES.md` was therefore not appended to in iteration 2.

The two forward-looking risks from iteration 1 §9 are unchanged and still belong to Phase 6, not
here: (1) Phase 6 must surface `AgentTelemetry.tool_invocations` in the draft telemetry section or
D19's detection half is inert — SPECIFICATIONS §3.4 now states this obligation explicitly; (2) Phase 6
must construct all four agents inside the `with HSEMockMCPClient()` block and must not cache an agent
across sessions.

**Ruff: 0 introduced (blocking) / 46 pre-existing (deferred to Phase 7).**
**Verdict: `APPROVED`.**
