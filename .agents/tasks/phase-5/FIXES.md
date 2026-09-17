# Phase 5 — Fixes (iteration 1)

**Status: all items closed by the `implementation` subagent, Stage 3 iteration 1.**
Full suite after the fixes: `98 passed, 0 warnings` (`-W error` also clean). No test added or
removed; production code in `src/` unchanged. Reviewer reasoning is preserved in
`ARCHITECT_REVIEW.md` and `QA_REVIEW.md`.

## 🧹 Code Quality & Conventions

_Appended by the `architect` subagent, Stage 3 iteration 1._

| Item | Resolution |
| :--- | :--- |
| **M-1** — credential tests not isolated from the process environment | **Fixed.** Autouse `_isolate_environment` fixture (keyed off `_EXPLICIT_VALUES`) added to `tests/test_unit/test_credentials.py`, and the same guard added to `tests/test_unit/test_model_factory.py`. Verified: with all six `HSE_MODEL_*` exported, both files pass (7 + 4 = 11); with the fixture disabled under the same pollution, the two credential tests fail again. |
| **m-2** — AST loop-state guard blind spot | **Fixed (`ast.keyword` half only).** `test_agents_module_contains_no_loop_state` now inspects `ast.keyword`. The `ast.For` half was **deliberately not applied**: `extract_telemetry` legitimately iterates `tool_usage` at `src/agents.py:274`, as the finding itself notes. Verified by mutation: a `PipelineScope(..., max_drafts=1)` call in `run_scout` now fails the guard and passed it before. |
| **m-3** — bare public `T = TypeVar(...)` in `src/schemas.py:216` | **No action** (recorded only; matches the SPECIFICATIONS snippet). |

## 🧪 Quality Assurance & Test Verification

_Appended by the `qa` subagent, Stage 3 iteration 1 — verdict `CHANGES REQUIRED` (0 blockers, 3 major, 3 minor)._

| Item | Resolution |
| :--- | :--- |
| **QA-1** (Major) — two telemetry mappings never asserted | **Fixed, with a stronger technique than the suggested diff.** On this Windows box `EventLoopMetrics` times cycles and tool calls with `time.time()` (~15.6 ms resolution), so both `total_duration` and `execution_stats.total_time` are almost always exactly `0.0` — an equality against `get_summary()` would still have been `0.0 == 0.0`, and `> 0.0` would have been flaky. Each test now pins the equality **and** records a known duration on the real metrics object (`cycle_durations.append(0.25)`, `tool_metrics[...].total_time += 0.5`) and re-projects. Verified: the `TYPO_total_duration` / `TYPO_total_time` mutation now fails **both** tests (was `38 passed`). |
| **QA-2** (Major) — `test_scout_applies_newsworthiness_scoring` vacuous on `[]` | **Fixed.** Candidate count and doc-id ordering asserted before the three iterating assertions. Verified: the zero-candidate `run_scout` mutation now fails 3 tests including this one (was 2). |
| **QA-3** (Major) — credential tests read the real OS environment | **Fixed** — same change as M-1 above. |
| **QA-4** (Minor) — label `test_agents_module_contains_no_loop_state` honestly | **Fixed.** Docstring now states it is an executable architectural constraint (ARCHITECTURE §1 / D19) and a prospective regression guard, not TDD evidence. Test kept. |
| **QA-5** (Minor) — D18 revision test never checks the previous `article_body` | **Fixed.** Per-line assertion over `_PREVIOUS_DRAFT.article_body.splitlines()` added, matching the `test_qa_legal_produces_pass_report` idiom. Verified: excluding `draft.article_body` from the serialised `RevisionPayload` now fails the test. |
| **QA-6** (Minor) — narrow socket guard in `test_build_model_makes_no_network_call` | **No action required**, as the finding states. |

### Acceptance criteria — observed

1. `.venv/Scripts/python.exe -m pytest tests/ -q` → **98 passed in 20.47s**. ✅
2. `pytest tests/ -q -W error` → **98 passed**. ✅
3. QA-1 typo mutation → both telemetry tests **fail**. ✅ (source restored, byte-identical)
4. QA-2 zero-candidate mutation → scoring test **fails**. ✅ (source restored)
5. `test_credentials.py` with `HSE_MODEL_*` exported → **7 passed**. ✅
6. `ruff check` on all six Phase 5 files → **All checks passed**; repo-wide total unchanged at 46 pre-existing (Phase 7 debt). ✅

## 🧪 Quality Assurance & Test Verification — iteration 2 (re-verification, no new items)

_Appended by the `qa` subagent, Stage 3 iteration 2. Verdict `PASSED`. **No new findings, no new actions.**_

All six iteration-1 QA items are **closed and independently re-proven**, each by re-running the
mutation that originally exposed it. Every mutation was reverted and the restoration confirmed by
MD5 (`src/agents.py` = `bdbfcbf05c6ae4f1fe21f6be5b019cb8`, unchanged); `git status --short` is
identical to the session start and `git diff src/` is unchanged.

| Iteration-1 item | Re-verified by | Observed |
| :--- | :--- | :--- |
| QA-1 | `TYPO_total_duration` + `TYPO_total_time` in `src/agents.py` | `2 failed, 36 passed` — deterministic across 5 consecutive runs (was `38 passed`). Unmutated: `2 passed` across 10 consecutive runs, so not flaky. |
| QA-2 | `run_scout` forced to return zero candidates | `3 failed, 35 passed`, including `test_scout_applies_newsworthiness_scoring` (was 2 failed with this test green). |
| QA-3 | all six `HSE_MODEL_*` exported | `test_credentials.py` 7 passed, `test_model_factory.py` 4 passed, full suite 98 passed. With the fixture forced to `autouse=False` under the same pollution the original 2 failures return, so the fixture is load-bearing. |
| QA-4 | docstring read | Correctly labelled an executable architectural constraint that passed at Red and drove no implementation. |
| QA-5 | `RevisionPayload` serialised with `draft.article_body` excluded | `test_writer_revision_serialises_structured_payload` fails. |
| m-2 (architect) | `PipelineScope(..., max_drafts=1)` keyword call inserted into `src/agents.py` | `test_agents_module_contains_no_loop_state` fails. |

### QA-1 replacement — accepted

The substituted technique was verified, not taken on report. `time.get_clock_info("time")` on this
machine reports `resolution=0.015625`, and five probes of the scripted scenario gave `total_duration`
values `0.0018 / 0.0027 / 0.0 / 0.0 / 0.0`, so the `> 0.0` assertion proposed in iteration 1 would
indeed have been flaky and is correctly rejected. Mutating `cycle_durations` and
`tool_metrics[...].total_time` is **not** coupling to SDK internals: the canonical Strands metrics
guide instructs users to read exactly those two public attributes, and `get_summary()` rebuilds its
dict on every call so the captured baseline cannot drift. The replacement is stronger than the
original suggestion.

One correction for the record (no action): the claim that `total_duration` is structurally `0.0` on
the structured-output path "because that path ends without `end_cycle`" is **wrong** — `end_cycle`
is called and `cycle_durations` held one entry in all five probes, non-zero in two of them. Only
clock resolution is responsible. The fix is unaffected because it asserts against a captured
baseline rather than against zero.

### Suite, hygiene and lint at close

`98 passed` (baseline), `98 passed` under `-W error`, `98 passed` with the OS environment polluted,
and `98 passed` after every mutation was reverted. 0 warnings; `pyproject.toml` declares no
`filterwarnings`, so `-W error` is meaningful. Process census `python`/`uv`/`fastmcp`: 7 before,
7 after — no orphaned subprocess. `ruff check` on all six Phase 5 files: all checks passed.
