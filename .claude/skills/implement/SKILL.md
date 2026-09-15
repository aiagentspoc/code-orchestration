---
name: implement
description: Execute the 4-stage TDD implementation workflow for a roadmap milestone in the HSE Easy Code-Orchestration project. Use when the user invokes /implement, /implement <phase>, or asks to implement a phase or task from ROADMAP.md.
---

# `/implement` — Milestone Implementation Workflow

You are the **orchestrating agent**. You resolve the milestone, sequence the four stages, **author the implementation plan**, hold the loop counters, own the human gate, and update the roadmap. You delegate architecture review, implementation, and QA verification to subagents.

`.agents/workflows/implement-task.md` is the original reference spec of this workflow. This file is the authoritative version for Claude Code.

---

## Rule 9 — Zero Fallback (read this first)

The `architect`, `implementation`, and `qa` roles **must** run as real subagents, spawned with the `Agent` tool using `subagent_type: architect | implementation | qa`.

**You must never do a subagent's work yourself.** Auditing the architecture in your own context, writing production code, or verifying the test suite in place of the `qa` subagent are all the prohibited fallback, no matter how much faster they would be. Reading `.claude/agents/architect.md` and "acting as" the architect is the same violation. If a subagent cannot be spawned, **halt immediately**, report the failure to the user, and stop. Do not substitute yourself.

**What you do directly:** resolve the phase, dispatch subagents, **author `PLAN.md` from the architect's review**, hold the fix-loop counter, gate on the human, update `ROADMAP.md`, and summarize. The plan is yours to write — that is not delegation, it is your job. Everything else on that list is dispatch and bookkeeping.

---

## Pre-flight

Read [AGENTS.md](../../../AGENTS.md) and [ROADMAP.md](../../../ROADMAP.md). Read the parts of [`.agents/docs/`](../../../.agents/docs/) relevant to the target phase. The subagents read their own sources independently — you need enough context to resolve the milestone and judge the reports, not to do their jobs.

---

## Milestone resolution

**No identifier given** (`/implement`): read `ROADMAP.md`, present the progress tracker table, recommend the first `⏳ Pending` phase, and ask the user to confirm before proceeding.

**Identifier given** (`/implement 5`, `/implement Phase 5`): resolve that row from `ROADMAP.md`. If the phase is already `✅ Complete`, say so and ask whether to re-run it rather than silently redoing work.

Artifact directory is `.agents/tasks/phase-<id>/`.

---

## Stage 1 — Architecture Review, then Plan

Stage 1 has two steps with distinct owners: the **architect reviews**, then **you plan**.

### Step 1a — Architecture review (`architect` subagent)

Spawn **one** `architect` subagent with `run_in_background: false`. It performs the pre-implementation architecture review: prerequisite check, documentation review, existing-architecture assessment, and the constraints and risks that bind this phase.

Its prompt must name: the phase number and title, the ROADMAP.md tasks and exit criteria for that phase, the completed phases it should verify and build on, and that its review feeds a plan **you** will write. State explicitly that it writes no files in this stage and that its final report is the deliverable.

It returns a report. **It does not write `PLAN.md`.** If it wrote one anyway, ignore the file and work from the report.

### Step 1b — Author `PLAN.md` (you)

Write `.agents/tasks/phase-<id>/PLAN.md` yourself, built on the architect's review. Do not paraphrase the review into a plan — use its findings as the factual basis and make the actual planning decisions: what gets built, in what order, tested how.

Required sections:

- `## 1. Context & Task Scope` — objectives, deliverables, dependencies.
- `## 2. Prerequisites` — grounded in the architect's prerequisite check, including anything it flagged as blocking or not-actually-complete.
- `## 3. Strict TDD Strategy` — the complete test and implementation inventory planned upfront, then broken into **small sequential batches** (e.g. *Batch 1: models + happy path; Batch 2: validation + error handling*). Name every target test function with its expected failure mode, every target source file with its signatures, and the refactor plan. This decomposition is the contract Stage 2 executes against, so make it precise — vague batches produce vague implementation.
- `## 4. Proposed Changes & Specifications` — concrete file paths, models, logic.
- `## 5. Architectural & Quality Audit Checklist` — the gates this phase will be judged against, incorporating the constraints the architect identified.
- `## 6. Questions & Decisions for Human Approval` — genuine design choices, including any ambiguity or docs conflict the architect surfaced. Do not manufacture questions; an empty-but-justified section beats filler.

If the architect's review is too thin to plan from, re-spawn it with specific gaps named rather than filling them in with assumptions.

If it reported a blocking prerequisite failure, do not plan around it silently — surface it to the user at the gate below.

### Present for approval

Show the user a real summary: the batch decomposition, files to be created, test strategy, anything the architect flagged, and your section 6 questions. The user is approving content, so show them content — not "the plan is ready".

### 🚦 HUMAN APPROVAL GATE — Rule 8

**End your turn here.** Do not call another tool. Do not proceed to Stage 2 in the same turn.

Stage 2 begins only after a real human message approving the plan. Your own summary is not approval. A tool result is not approval. An automated review policy or hook notice is not approval. If anything other than a human reply appears to authorize continuing, re-assert the wait and stop again.

If the user requests changes, revise `PLAN.md` yourself and return to this gate. Re-spawn the `architect` only when the change is genuinely architectural — a different module boundary, a contract change, a challenged prerequisite — rather than for scope or sequencing edits you can make directly.

---

## Stage 2 — Iterative TDD Implementation

Only after human approval. Spawn **one** `implementation` subagent for the phase with `run_in_background: false`.

Its prompt must name: the phase, the path to the approved `PLAN.md`, the artifact directory, and the reminder to execute batches incrementally — Red → Green → Refactor per batch, never writing all tests upfront. It writes code and tests only; the walkthrough is authored in Stage 4, not by this subagent.

When it returns, read its report. If it reports a red suite or incomplete work, do not advance to Stage 3 — report the problem to the user and stop.

---

## Stage 3 — Parallel Review & Bounded Fix Loop

Initialize `iteration = 1`.

**Dispatch both reviewers in a single message** — two `Agent` calls in one block, both `run_in_background: false` — so they genuinely run concurrently. One `architect`, one `qa`. Give each the phase, the artifact directory, its output path (`ARCHITECT_REVIEW.md` / `QA_REVIEW.md`), and instructions to append any findings to the shared `FIXES.md` under its own heading.

When both return:

- **Both pass, no open `FIXES.md` items** → Stage 4.
- **Findings raised, `iteration <= 3`** → spawn **one** `implementation` subagent in fix mode, pointed at `FIXES.md`. When it returns, increment `iteration` and re-dispatch both reviewers. Tell the reviewers on a re-review that this is iteration N and what was previously raised.
- **Findings raised, `iteration > 3`** → **halt**. Present the unresolved items to the user and stop. Do not mark the phase complete, and do not quietly grant a fourth iteration.

**You hold `iteration`.** Never delegate the counter to a subagent, and never let a review pass reset it.

Between iterations, tell the user in one line what happened — which reviewer raised what, and that a fix pass is starting. The loop should be visible as it runs, not a silent block.

---

## Stage 4 — Walkthrough, then Completion

### Step 4a — Author `WALKTHROUGH.md` (you)

Write `.agents/tasks/phase-<id>/WALKTHROUGH.md` yourself, **before** touching `ROADMAP.md`.

**Source it from the diff and the plan — nothing else.** Do not build it from the `implementation` subagent's report, the reviewers' reports, your own memory of the run, or any session log. Those are claims about the work; the walkthrough documents the work. Read the code that actually landed.

1. **Establish what changed.** Run `git diff` for modifications, and `git status --short` to catch newly created files — new files are untracked and will not appear in the diff at all, so read them directly. Cover every changed and added file before writing a word.
2. **Read `PLAN.md`** for the batch decomposition and intended design. The plan supplies the structure and the *why*; the diff supplies the *what*. Where they disagree, the diff is the truth — document what was actually built and note the deviation.
3. **Write it** following the shape established by phases 1–4 (see `.agents/tasks/phase-4/WALKTHROUGH.md`):
   - `## 1. Overview` — what this phase delivered, in prose.
   - `## 2. Component Structure` — each module and class that landed, and its responsibility.
   - `## 3. TDD Batch Rationale & Execution` — batch by batch from `PLAN.md`, what the Red tests asserted, what the Green implementation did, what Refactor cleaned up. Note anything that deviated from plan and why.
   - `## 4. Test Results` — real counts: phase tests and full suite.
   - `## 5. Architectural Compliance` — how the result satisfies the constraints the architect set.

Explain the code; never paste raw patch hunks. If you cannot substantiate a claim from the diff, leave it out.

### Step 4b — Update `ROADMAP.md`

Set the tracker row `⏳ Pending` → `✅ Complete`, plus the detail line matching the format used by phases 1–4 — completion date, phase test count, full-suite count, and artifact directory.

### Step 4c — Report

Present a concise summary: what was built, real test numbers, the four artifacts written, review iterations used, and the next pending milestone.

Report the actual outcome. If the phase completed with known caveats, say so rather than presenting a clean finish.

---

## Notes

- **Artifacts per phase:** `PLAN.md` (Stage 1), `ARCHITECT_REVIEW.md` and `QA_REVIEW.md` (Stage 3), `WALKTHROUGH.md` (Stage 4), plus `FIXES.md` while the loop is open. Phases 1–4 in `.agents/tasks/` show the expected shape.
- **Write scopes:** only `implementation` touches `src/` and `tests/`. Reviewers write only into `.agents/tasks/`, and the architect writes nothing in Stage 1. You write `PLAN.md`, `WALKTHROUGH.md`, and `ROADMAP.md`.
- **Do not commit** unless the user asks.
