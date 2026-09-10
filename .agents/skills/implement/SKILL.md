---
name: implement
description: >-
  Select and execute the automated 3-stage implementation workflow for a roadmap milestone or task.
  Use whenever the user invokes /implement, /implement <phase_or_task>, or asks to implement a specific phase or task from ROADMAP.md.
---

# `/implement` Milestone & Task Implementation Command

This skill triggers the standardized 3-stage automated implementation workflow for the **HSE Easy Code-Orchestration** project, enforcing strict Test-Driven Development (TDD) and architectural integrity.

---

## 1. Syntax & Invocation Examples

The command accepts flexible phase and task identifier formats:

| Invocation | Matched Target | Target Artifact Folder |
| :--- | :--- | :--- |
| `/implement` | Interactive selection from [ROADMAP.md](file:///c:/Users/Saksham/Git/poc/AIAgents/code-orchestration/ROADMAP.md) | Next pending phase folder |
| `/implement 1` or `/implement Phase 1` | Phase 1: Environment & Packaging | `.agents/tasks/phase-1/` |
| `/implement 2` or `/implement Phase 2` | Phase 2: Schemas & Contracts | `.agents/tasks/phase-2/` |
| `/implement 3` or `/implement Phase 3` | Phase 3: Template Engine | `.agents/tasks/phase-3/` |
| `/implement 4` or `/implement Phase 4` | Phase 4: Substrate MCP Client | `.agents/tasks/phase-4/` |
| `/implement 5` or `/implement Phase 5` | Phase 5: Strands Agent Workers | `.agents/tasks/phase-5/` |
| `/implement 6` or `/implement Phase 6` | Phase 6: Procedural Orchestrator | `.agents/tasks/phase-6/` |
| `/implement 7` or `/implement Phase 7` | Phase 7: Publishing CLI | `.agents/tasks/phase-7/` |
| `/implement 8` or `/implement Phase 8` | Phase 8: E2E Verification | `.agents/tasks/phase-8/` |

---

## 2. Interactive Selection Flow

If the user invokes `/implement` without specifying an identifier:
1. Inspect [ROADMAP.md](file:///c:/Users/Saksham/Git/poc/AIAgents/code-orchestration/ROADMAP.md) to check current milestone completion status.
2. Present the progress tracker table to the user.
3. Automatically recommend the next pending milestone (e.g. `(Recommended) Phase 1: Environment, Dependencies & Packaging Setup`).
4. Await user confirmation before proceeding to Stage 1.

---

## 3. Workflow Execution

When this skill is triggered and a phase/task is confirmed, immediately load and execute the complete workflow defined in:

👉 **[`.agents/workflows/implement_task.md`](file:///c:/Users/Saksham/Git/poc/AIAgents/code-orchestration/.agents/workflows/implement_task.md)**

### Stage Summary:
* **Stage 1 (Plan):** Create `.agents/tasks/phase-<id>/PLAN.md` with explicit TDD Red-Green-Refactor strategy. **Halt at Human Approval Gate.**
* **Stage 2 (Implementation):** Upon approval, autonomously author tests in `tests/` (Red), implement code in `src/` (Green), optimize (Refactor), and author `.agents/tasks/phase-<id>/WALKTHROUGH.md` strictly from terminal `git diff`.
* **Stage 3 (Review Loop):** Execute parallel architectural and QA audits using [`architect-review`](file:///c:/Users/Saksham/Git/poc/AIAgents/code-orchestration/.agents/skills/architect-review) and [`code-reviewer`](file:///c:/Users/Saksham/Git/poc/AIAgents/code-orchestration/.agents/skills/code-reviewer). Apply fixes via `FIXES.md` (up to 3 iterations) and mark the phase `✅ Complete` in [ROADMAP.md](file:///c:/Users/Saksham/Git/poc/AIAgents/code-orchestration/ROADMAP.md).

