# Phase 5 — QA & Verification Review

**Reviewer:** `qa` subagent (Stage 3, iteration 1)
**Scope:** Strands Agent Workers — `src/agents.py`, `src/credentials.py`, `src/model_factory.py`, `src/schemas.py` (§3.3-3.4), `src/mcp_client.py`, and their tests.
**Method:** suite executed by the reviewer, not taken on report; contracts read from `SPECIFICATIONS.md`; telemetry field names verified against installed SDK source; claims falsified by source mutation.

---

## 1. Summary & Verdict

### `CHANGES REQUIRED` — 0 blockers, 3 major, 3 minor

Production code is **correct**. Every one of the 49 tests named in the plan's six batch tables exists, under its planned name, and the suite is genuinely green and warning-free. No rework of `src/` is required and no contract is broken.

The findings are confined to **test strength**. Three of them are proven escapes: I mutated `src/agents.py` and watched the suite stay green. Two of eight Rule 6 telemetry mappings are not actually asserted, one Scout test passes vacuously against an empty result, and two credential tests read the developer's real OS environment rather than being hermetic. None of these breaks the build today; all three would let a real regression ship green tomorrow. That is the definition of coverage that is not coverage, so the phase is not signed off until they are closed.

### Observed test results (executed by the reviewer)

```
.venv/Scripts/python.exe -m pytest tests/ -v -p no:cacheprovider
============================= 98 passed in 20.68s =============================
```

Confirmed twice (20.68 s, then 20.56 s). The implementation's claim of **98 passed / 0 failed / 0 warnings in ~20.3 s is accurate**.

| Bucket | Observed | Claimed | Match |
| :--- | ---: | ---: | :---: |
| `tests/test_unit/test_agents.py` | 38 | 38 | OK |
| `tests/test_unit/test_credentials.py` | 7 | 7 | OK |
| `tests/test_unit/test_model_factory.py` | 4 | 4 | OK |
| New tests this phase | **49** | 49 | OK |
| Pre-existing tests still green | 49 | 49 | OK |
| Integration (`test_mcp_client.py`) | 12 (1 replaced, 11 untouched) | 12 | OK |
| **Full suite** | **98 passed, 0 failed, 0 skipped** | 98 | OK |

Warnings verified **independently and more strictly than claimed**: unit suite re-run under `-W error` gives `78 passed in 2.75s`, and the full suite under `-W error::DeprecationWarning` gives `98 passed`. There is no `DeprecationWarning` from `agent.structured_output(` because that call does not appear in `src/` at all — the only textual match is a docstring stating it is forbidden. **Zero-warnings claim holds.**

---

## 2. Rule Adherence Matrix

| Gate | Rule | Status | Notes |
| :--- | :--- | :---: | :--- |
| Gate 1 | Rule 7: Strict TDD | WARN | All 49 planned tests present and named as planned; no untested logic in `src/`. Downgraded from PASS by three proven weak/vacuous assertions (QA-1, QA-2, QA-3) and one test that passed at Red (QA-4). |
| Gate 2 | Rule 2: Pydantic v2 Contracts | PASS | `ScoutCandidate`, `ScoutReport`, `ToolInvocation`, `AgentTelemetry`, `WorkerOutput[T]` match SPECIFICATIONS §3.3-3.4 field-for-field. `ConfigDict(extra="ignore")` on all five. `newsworthiness_score` bounded `ge=0.0, le=1.0` and tested on both edges. Zero `dict[str, Any]` crossing a boundary — the only textual matches in `src/` are inside docstrings. |
| Gate 3 | Rule 3: Bounded Revision Loop | PASS (N/A) | Correctly **out of scope** (Phase 6) and correctly **absent**. AST guard proves no `while`, `attempts` or `max_drafts` in executable code; `grep` confirms. `run_writer` neither reads nor mutates `attempt`. |
| Gate 4 | Rule 6: Strands Telemetry | WARN | `metrics.get_summary()` read in exactly one place. All eight mappings are **correct** — verified against `strands/telemetry/metrics.py` source and the `Usage`/`Metrics` TypedDicts, not against the test's own fixture. Downgraded because two of the eight are not actually asserted (QA-1). No `logging` in `src/` at all, so no misrouting; handler config correctly deferred to Phase 6. |
| Gate 5 | Rule 5: Draft Markdown Format | PASS (N/A) | Phase 5 touches no persistence and no template engine. `src/agents.py` does no file I/O and emits no Markdown. 11 Phase 3 template tests still green. |
| Gate 6 | Python Typing & Subprocess Safety | PASS | Complete PEP 585/604 annotations; `pathlib.Path` used in the one test that touches disk. `ruff check` reports **0 findings in any file Phase 5 created**. No subprocess leak: process census identical before (7) and after (7) the suite; the three `uv`/`fastmcp` processes present are this review session's own MCP servers (creation timestamps all predate the run). `HSEMockMCPClient()` construction proven to spawn nothing (`subprocess.Popen` trap returns `[]`). |

### Verified independently

- **Telemetry field names against the SDK, not the fixture.** `EventLoopMetrics.get_summary()` emits `total_cycles`, `total_duration`, `tool_usage.<name>.execution_stats.{call_count, success_count, error_count, total_time}`, `accumulated_usage`, `accumulated_metrics`. `strands.types.event_loop.Usage` declares `inputTokens`/`outputTokens`/`totalTokens`; `Metrics` declares `latencyMs`. `extract_telemetry` matches all eight exactly.
- **Live substrate shape vs. test fixtures.** A live `verify_legal_citation` call returns exactly the eight keys the `test_agents.py` stub fixture mirrors. The substrate advertises exactly the five tools the integration test asserts.
- **D16 zero-cost determinism — mostly holds.** No unit test opens a socket or spawns a process; the unit suite runs in 2.75 s. The one hole is environment leakage (QA-3).
- **Ruff, in scope.** 0 findings in `src/agents.py`, `src/credentials.py`, `src/model_factory.py`, `test_agents.py`, `test_credentials.py`, `test_model_factory.py`. The 34 remaining findings (`schemas.py` 19, `mcp_client.py` 9, `test_mcp_client.py` 6) are all on pre-existing lines and are the Phase 7 debt the plan defers. Nothing introduced.

---

## 3. Plan Coverage — batch by batch

Every test named in the plan's six tables is present, under its exact planned name. Nothing renamed, nothing dropped.

| Batch | Planned | Present | Hollow? |
| :--- | ---: | ---: | :--- |
| 0 — `test_credentials.py` | 7 | 7 | 2 not hermetic (QA-3) |
| 0 — `test_model_factory.py` | 4 | 4 | 1 weak socket guard (QA-6) |
| 1 — harness, scoping, telemetry, ScopeParser | 10 | 10 | telemetry duration fields unasserted (QA-1) |
| 2 — Scout | 8 | 8 | 1 vacuous (QA-2) |
| 3 — Writer initial | 5 | 5 | — |
| 4 — Writer revision (D18) | 4 | 4 | 1 incomplete (QA-5); 1 passed at Red (QA-4) |
| 5 — QA-Legal + cross-cutting | 11 | 11 | — |
| **Total** | **49** | **49** | |

The plan's own estimate ("roughly 44 new tests; full suite approximately 93") was exceeded, not padded — the extra five are real distinct behaviours.

### `ScriptedModel` — the anti-mock mandate is honoured

The plan forbade `patch("strands.Agent")` theatre and required a real event loop. Verified: `ScriptedModel` subclasses `strands.models.model.Model` and implements `stream()` as an async generator of genuine Bedrock-shaped stream events. `grep` finds **no** `unittest.mock`, `patch`, or `MagicMock` anywhere in `test_agents.py`. Consequences that matter:

- `agent(prompt, structured_output_model=X)` really goes through `StructuredOutputContext`, the synthetic tool spec, `tool_choice`, and the tool-result harvest. When a test asserts a `ScoutReport` comes back, the SDK genuinely produced it.
- `telemetry.cycles == 1`, `latency_ms == 678`, `total_tokens == 168` are real values accumulated by the real `EventLoopMetrics`, not fixture echoes.
- Tool invocations in `tool_invocations` are produced by real `@tool` functions executed by the real loop — `test_scout_invokes_regulatory_tools` and `test_qa_legal_verifies_each_citation` prove genuine integration.
- `ScriptedModel.structured_output()` raises `NotImplementedError` by design, so the deprecated path would fail loudly if anyone reintroduced it. That is a good negative guard.
- Script exhaustion raises rather than repeating the last turn, so a stray extra round trip fails loudly instead of looping.

This fixture is the strongest thing in the phase and the reason the Green signal is credible.

### D18 revision payload — the verbatim guarantee, judged

Asked to judge whether "verbatim" actually holds. It does, for what is asserted, and I confirmed the mechanics rather than accepting the note.

`json.dumps(model_dump(), indent=2)` escapes `\n`, so a multi-line value is **not** recoverable by naive substring match. Probed directly:

```
body verbatim present: False
each line present:     True
```

`test_writer_revision_serialises_structured_payload` asserts `headline`, `tdi_cta`, all `issues`, and `review_notes` — every one of them single-line, so each **is** matched verbatim, unescaped and unparaphrased. The guarantee holds. `test_qa_legal_produces_pass_report` demonstrates the line-by-line technique correctly for the multi-line `article_body`. The gap (QA-5) is that the Writer revision test never applies that technique to the previous draft's body.

### `test_agents_module_contains_no_loop_state` — acceptable, but not TDD

It self-reports as passing at Red. That is true and unavoidable: at Red `src/agents.py` was a 7-line comment stub containing no loop state, so the assertion was vacuously satisfied. It therefore **drove no implementation** and is not a Red-Green cycle.

Judgement: **acceptable, not a violation.** It is an architectural regression guard for ARCHITECTURE §1, and its value is prospective — it fails the moment someone adds a counter. It is also well built: it parses the AST rather than grepping text, precisely because the prompts must legitimately mention `max_drafts`. Text-matching here would have been the fragile choice. The only correction is honesty in labelling: it should be documented as a regression guard, not counted as TDD evidence.

---

## 4. Findings by Severity

**0 blockers, 3 major, 3 minor.** All three majors are proven by experiment, not inferred.

### QA-1 (Major) — Two Rule 6 telemetry mappings are unasserted; a typo in either ships green

`test_extract_telemetry_maps_usage_and_latency` asserts `total_duration_seconds >= 0.0` and `test_extract_telemetry_captures_tool_invocations` asserts `total_time_seconds >= 0.0`. Both fields default to `0.0`, so `>= 0.0` is satisfied by the default — the assertion cannot distinguish a correct mapping from a broken one. Gate 4 names telemetry extraction as a mandatory gate and 2 of the 8 mapped fields are effectively untested.

**Proven.** I replaced both source keys with typos in `src/agents.py`:

```python
total_duration_seconds=summary.get("TYPO_total_duration", 0.0),
...
total_time_seconds=stats.get("TYPO_total_time", 0.0),
```

```
38 passed in 1.56s
```

Both mappings are in fact correct — I verified them against `strands/telemetry/metrics.py`. The defect is that the tests do not know that. Source restored; suite re-verified at 98 passed.

### QA-2 (Major) — `test_scout_applies_newsworthiness_scoring` passes vacuously on an empty candidate list

All three assertions iterate a list, so all three are trivially true when the list is empty: `all(...)` over `[]` is `True`, and `[] == sorted([], reverse=True)`. A Scout that returns nothing satisfies a test named "applies newsworthiness scoring".

**Proven.** I made `run_scout` return zero candidates. Two sibling tests caught it; **this one stayed green**:

```
FAILED tests/test_unit/test_agents.py::test_scout_returns_ranked_scout_report
FAILED tests/test_unit/test_agents.py::test_scout_does_not_truncate_to_max_drafts
2 failed, 36 passed in 1.78s
```

Mitigating: the truncation guard is real and strong, so the Rule 4 behaviour is covered elsewhere. The fix is one line.

### QA-3 (Major) — Two credential tests read the developer's real OS environment (D16 / audit item 15)

`test_credential_manager_reads_env_file` and `test_credential_manager_missing_vars_raises` pass `_env_file=<tmp_path>`, which correctly neutralises the project `.env` — but `pydantic-settings` ranks **OS environment variables above dotenv values**. Neither test clears `HSE_MODEL_*` from the environment, so both are environment-dependent.

This is not hypothetical: it fires the moment a developer exports the variables for a real pipeline run, and it fires in any CI that injects them as secrets. **Proven** by running the file with the variables set:

```
E       AssertionError: assert 'https://LEAKED.example/' == 'https://file...id/openai/v1/'
E         - https://file-fast.example.invalid/openai/v1/
E         + https://LEAKED.example/
tests\test_unit\test_credentials.py:59: AssertionError

>       with pytest.raises(ValidationError) as excinfo:
E       Failed: DID NOT RAISE ValidationError
tests\test_unit\test_credentials.py:72: Failed

2 failed, 5 passed in 1.55s
```

The worse half is `test_credential_manager_missing_vars_raises`: it exists to prove missing keys are caught, and a populated environment silences exactly the failure it was written to detect.

### QA-4 (Minor) — Label `test_agents_module_contains_no_loop_state` as a regression guard

Reasoning in §3. Keep the test; add one docstring line stating it passed at Red by construction and is prospective, so the next reader does not mistake it for TDD evidence.

### QA-5 (Minor) — D18 revision test never checks the previous `article_body` reaches the model

The test asserts `headline` and `tdi_cta` verbatim but not the body — the largest and most consequential part of what the Writer is asked to revise. Risk is genuinely low, since all three are siblings inside the one `draft` sub-object produced by a single `model_dump()`, so a body omission is implausible. But the test is named for the serialisation guarantee and should cover it. `test_qa_legal_produces_pass_report` already shows the correct line-by-line idiom.

### QA-6 (Minor) — `test_build_model_makes_no_network_call` guards a narrow surface

It patches `socket.socket.connect` and `socket.create_connection`. An `httpx`/`anyio` path or a DNS resolution would slip past. Adequate in practice — `OpenAIModel.__init__` only stores config and Strands builds its client per request — so this is a nitpick, recorded for completeness rather than for action.

---

## 5. What Was Checked and Found Clean

Recorded so the next reviewer need not repeat it:

- **Rule 4 / D3** — `test_scout_does_not_truncate_to_max_drafts` is a real guard: `max_drafts=1` against three candidates asserts all three survive. Mutation-confirmed to fail when violated.
- **D19 role boundaries** — all three tool-using factories attach exactly 5 tools; explicit `tool_names` genuinely narrows. `test_all_worker_prompts_declare_non_goals` is not a token grep: it splits on `## Non-goals`, requires at least 3 bullets and the literal `you do not`. Audit item 3a is enforced as the plan demanded.
- **Negative and edge paths present** — score bounds tested on both `1.5` and `-0.1`; `test_scope_parser_invalid_output_raises` drives a genuine missing-`time_window` failure through the real loop including retry turns; `test_factory_requires_live_client` covers both scoped and unscoped calls across all three factories; `AgentTelemetry` extra-key rejection asserts `not hasattr`.
- **Provider isolation** — `grep -rn "strands.models" src/` matches only `src/model_factory.py` (concrete) and abstract `Model` imports. Holds exactly as §4.5 promised.
- **Secrets** — `SecretStr` masking asserted on both slots in `str()` and `repr()`, and on the derived `ModelCredentials`. `.env.example` committed; no key literal in `src/`.
- **Subprocess hygiene** — process census 7 before / 7 after; no orphan `python.exe`, `uv.exe` or `fastmcp.exe` attributable to the run.
- **Phase 4 regression** — the `load_tools` to `list_all_tools` rename (Q9) landed with its single call site updated; the replaced integration test is a genuine improvement over the coroutine-sniffing original, and the other 11 are untouched and green.

---

## 6. Required Actions

Three fixes, all in `tests/`, all localized. Full instructions with copy-pasteable diffs are in `.agents/tasks/phase-5/FIXES.md` under **Quality Assurance & Test Verification**.

1. **QA-1** — assert the two duration mappings against real values, not `>= 0.0`.
2. **QA-2** — assert the candidate count before iterating.
3. **QA-3** — clear `HSE_MODEL_*` from the environment in the two affected credential tests.

QA-4 and QA-5 are one-line improvements worth taking while the file is open. QA-6 needs no action.

Re-run `.venv/Scripts/python.exe -m pytest tests/ -v` after the fixes; the expected result is unchanged at **98 passed**, since none of these adds or removes a test.

---

# Phase 5 — QA & Verification Review (iteration 2)

**Reviewer:** `qa` subagent (Stage 3, iteration 2 — re-review after the fix pass)
**Method:** every iteration-1 acceptance criterion reproduced by deliberate source mutation on this machine; SDK timing claims checked against the installed `strands` source and the canonical docs; the suite executed by the reviewer before, during and after each mutation, with byte-level restoration verified by checksum.

The iteration-1 record above is preserved unaltered.

## 1. Verdict

### `PASSED` — 0 blockers, 0 major, 0 minor. All six iteration-1 findings are closed.

Every one of my three proven escapes is now caught by mutation. The two "no action" items (QA-6, m-3) remain correctly no-action. No test was added or removed, `src/` is genuinely untouched, and the suite is green, warning-free and leak-free.

### Observed test results (executed by the reviewer)

```
.venv/Scripts/python.exe -m pytest tests/test_unit/ tests/test_integration/ -q
98 passed in 20.54s      (baseline, before any mutation)
98 passed in 20.61s      (-W error)
98 passed in 20.22s      (full OS environment polluted with all six HSE_MODEL_*)
98 passed in 20.20s      (final, after every mutation reverted)
```

98 collected, 98 passed, 0 failed, 0 skipped, 0 warnings. Per-file counts unchanged from iteration 1: `test_agents.py` 38, `test_credentials.py` 7, `test_model_factory.py` 4 — **no test added or removed**, exactly as claimed.

## 2. Acceptance criteria — reproduced, one by one

| # | Criterion | Result |
| :--- | :--- | :--- |
| 1 | Both telemetry source keys typo'd (`TYPO_total_duration`, `TYPO_total_time`) | **2 failed, 36 passed.** Both telemetry tests fail. Repeated 5x: `2 failed` every time — deterministic, not luck. Was `38 passed` in iteration 1. PASS |
| 2 | `run_scout` returns zero candidates | **3 failed, 35 passed**, including `test_scout_applies_newsworthiness_scoring`. Was 2 failed with the scoring test green in iteration 1. PASS |
| 3 | All six `HSE_MODEL_*` exported | `test_credentials.py` gives **7 passed**; `test_model_factory.py` gives 4 passed; both together **11 passed**; **full suite 98 passed** under the same pollution. PASS |
| 4 | Full suite | **98 passed, 0 warnings**, and **98 passed under `-W error`**. `pyproject.toml` sets no `filterwarnings`, so `-W error` is genuinely load-bearing here. PASS |
| 5 | Tree clean; `src/` untouched | `git status --short` identical to session start; `git diff --stat` unchanged (`src/agents.py 563 +`). MD5 of all six Phase 5 files identical before and after every mutation (`src/agents.py` = `bdbfcbf05c6ae4f1fe21f6be5b019cb8`). `src/credentials.py` and `src/model_factory.py` mtimes still 18:44 — the fix pass never opened them. PASS |
| 6 | QA-5 bite: `RevisionPayload` serialised without `article_body` | **1 failed** — `test_writer_revision_serialises_structured_payload`, on the per-line body assertion. PASS |
| 7 | m-2 bite: `PipelineScope(..., max_drafts=1)` keyword call in `src/agents.py` | **1 failed** — `test_agents_module_contains_no_loop_state`. PASS |

Additional check the brief did not require: the QA-3 fixture was proven to be what does the work, not something incidental. A copy of `test_credentials.py` with `autouse=False`, run outside the repo tree under the same pollution, reproduces the original iteration-1 failure exactly:

```
FAILED ::test_credential_manager_reads_env_file - AssertionError
FAILED ::test_credential_manager_missing_vars_raises - Failed: DID NOT RAISE ValidationError
2 failed, 5 passed
```

## 3. QA-1 — judging the replacement I did not propose

My iteration-1 diff (`== approx(summary["total_duration"])` plus `> 0.0`) was **not** applied. I verified the fix agent's justification rather than accepting it, and it is correct on the substance:

- `time.get_clock_info("time")` on this box reports `resolution=0.015625` (15.625 ms), `monotonic=False`, `adjustable=True`. `EventLoopMetrics.end_cycle` timestamps with `time.time()` (`strands/telemetry/metrics.py:292,314`).
- Five probe runs of the exact scripted scenario gave `total_duration` values `0.0018`, `0.0027`, `0.0`, `0.0`, `0.0`. **A `> 0.0` assertion would indeed have been flaky**, and on a 0.0 run the equality alone degenerates to `0.0 == 0.0` and cannot catch the typo. My proposed diff was the weaker option. Correctly rejected.

**One claim in the fix report is wrong and is corrected here for the record:** `total_duration` is *not* "structurally 0.0 on the structured-output path because that path ends without `end_cycle`, leaving `cycle_durations` empty". `end_cycle` *is* called on this path — `cycle_durations` held exactly one entry in all five probes, and was non-zero in two of them. The real cause is only clock resolution. This does not affect the fix, which is robust either way because it asserts against a captured `baseline` rather than against zero. The in-file comment ("leaves a scripted sub-millisecond cycle at exactly 0.0") is likewise an over-generalisation of a usually-true observation, not a misdescription of what the test does; no action.

**Is the replacement coupled to SDK internals?** No — it is coupled to **documented public surface**. The canonical Strands metrics guide itself instructs users to read `sum(result.metrics.cycle_durations)` and `result.metrics.tool_metrics`, the same two attributes the test writes to. Both are public dataclass fields with docstrings (`cycle_durations: list[float]`, `ToolMetrics.total_time: float`). Two further properties make the technique sound:

- `get_summary()` builds a **fresh** dict literal on every call (`metrics.py:429`), so the `stats` snapshot taken before the mutation is a true baseline and not a live view that would move with it.
- The assertion is `approx(baseline + 0.25)` / `approx(stats["total_time"] + 0.5)`, so it holds whether the real measured duration is 0.0 or not.

Stability confirmed empirically: the two telemetry tests were run 10x consecutively on unmutated source — **2 passed, every time**. The replacement is stronger than what I asked for, and it is not brittle.

## 4. Did the fixes introduce new weakness?

Checked specifically for the three failure modes named in the brief. None found.

- **Fixture over-reach.** Both `_isolate_environment` fixtures delete only the six names in `_EXPLICIT_VALUES` and are keyed off that dict, so they cannot drift. They use `monkeypatch.delenv(..., raising=False)`, so state is restored per test and nothing leaks into other files. Scope is one module each. The `test_model_factory.py` copy is defensive rather than load-bearing (init kwargs already outrank the environment in `pydantic-settings`) and its docstring says exactly that — accurate, not overstated.
- **Assertions coupled to incidental fixture values.** The new doc-id ordering assertion pins identity *and* relay order against the scripted order; it pairs with the descending-score assertion rather than duplicating it. Legitimate. The new per-line body assertion iterates two substantive non-blank lines — no vacuous empty-string element — and was proven decisive by mutation.
- **Docstrings that now misdescribe.** The `test_credentials.py` module docstring is now accurate: every test does construct `CredentialManager` with `_env_file=None` (via `_manager()`) or a `tmp_path` file — verified test by test. The `test_agents_module_contains_no_loop_state` docstring correctly labels itself an executable architectural constraint that passed at Red and drove no implementation (QA-4 as requested). The only imprecision found anywhere is the `time.time()` comment noted in section 3, which is about the SDK and not about the test.

## 5. Re-confirmed clean

- **Warnings.** No `filterwarnings` in `pyproject.toml`; the `-W error` pass is real.
- **Subprocess hygiene.** Process census for `python`/`uv`/`fastmcp`: **7 before, 7 after** a full suite run. No orphan attributable to the run. The long-lived entries predate the session.
- **Lint.** `ruff check` on all six Phase 5 files (the three rewritten test files included): **All checks passed.**
- **Substrate shape.** A live `verify_legal_citation("D.Lgs. 81/2008 Art. 28")` still returns the eight-key shape the `test_agents.py` stub mirrors (`citation_input`, `is_valid`, `status`, `canonical_citation`, `official_reference`, `official_url`, `verified_against_doc_id`, `notes`). The 12 integration tests exercise the real stdio transport and are inside the 98.

### Gate matrix — iteration 1 versus iteration 2

| Gate | Rule | Iter-1 | Iter-2 | Notes |
| :--- | :--- | :---: | :---: | :--- |
| Gate 1 | Rule 7: Strict TDD | WARN | **PASS** | QA-2, QA-3, QA-5 closed and mutation-proven; QA-4 honestly labelled. |
| Gate 2 | Rule 2: Pydantic v2 Contracts | PASS | PASS | Unchanged — `src/` not modified. |
| Gate 3 | Rule 3: Bounded Revision Loop | PASS (N/A) | PASS (N/A) | AST guard now also catches the keyword form (m-2). |
| Gate 4 | Rule 6: Strands Telemetry | WARN | **PASS** | Both duration mappings now decisively asserted; typo mutation fails both tests 5/5. |
| Gate 5 | Rule 5: Draft Markdown Format | PASS (N/A) | PASS (N/A) | Phase 5 touches no persistence. |
| Gate 6 | Python Typing & Subprocess Safety | PASS | PASS | Ruff clean; 7 processes before / 7 after. |

## 6. Iteration-1 findings — disposition

| Finding | Severity | Status | Evidence |
| :--- | :--- | :--- | :--- |
| QA-1 — two telemetry mappings unasserted | Major | **CLOSED** | Typo mutation gives 2 failed, deterministic over 5 runs; unmutated stable over 10 runs. |
| QA-2 — scoring test vacuous on empty list | Major | **CLOSED** | Zero-candidate mutation gives 3 failed, this test among them. |
| QA-3 — credential tests read real OS env | Major | **CLOSED** | 7 passed under full pollution; fixture proven load-bearing by disabling it. |
| QA-4 — label the AST guard honestly | Minor | **CLOSED** | Docstring states it is an architectural constraint, passed at Red, prospective value. |
| QA-5 — D18 test never checked `article_body` | Minor | **CLOSED** | Excluding the body from the payload now fails the test. |
| QA-6 — narrow socket guard | Minor | **CLOSED (no action)** | Correctly recorded, no action required, as stated in iteration 1. |

## 7. Observation (informational — not a finding, no action)

No test covers `CredentialManager` sourcing values from OS environment variables — the primary `pydantic-settings` mechanism and the likely CI-secrets deployment path. This gap existed identically in iteration 1 on the same seven tests; the new fixture neither creates nor widens it (it only removes the variables for the duration of each test, restoring them afterwards). Recorded so a future phase that adds an env-var deployment path knows to add the test. **Not a Phase 5 defect and not grounds for another pass.**

## 8. Required actions

**None.** Phase 5 is signed off from the QA side.
