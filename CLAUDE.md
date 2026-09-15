# CLAUDE.md

Claude Code entry point for **HSE Easy — Approach 1 (Code-Orchestrated Pipeline)**.

## Read this first

**[AGENTS.md](AGENTS.md) is the authoritative guide.** Read it before any work in this repository. It defines the product rules (2–6) constraining the code you write, and the working rules (7–9) constraining how you work — Strict TDD, manual human sign-off at approval gates, and mandatory subagent delegation with zero fallback.

Supporting sources of truth, all harness-neutral, in [`.agents/docs/`](.agents/docs/):

| Document | What it settles |
| :--- | :--- |
| [ARCHITECTURE.md](.agents/docs/ARCHITECTURE.md) | System blueprint, data flow, component roles, D1–D18 Decision Log |
| [SPECIFICATIONS.md](.agents/docs/SPECIFICATIONS.md) | The Pydantic v2 contracts — substrate and internal |
| [DESIGN.md](.agents/docs/DESIGN.md) | Concept notes and original approach |

[ROADMAP.md](ROADMAP.md) tracks phase-by-phase progress. Per-phase artifacts live in [`.agents/tasks/phase-<id>/`](.agents/tasks/).

## Project principle — "Code as Orchestrator"

The pipeline's defining property: `src/orchestrator.py` holds all routing, iteration counters, and error recovery in imperative Python, and the Strands agents are callable workers with zero autonomy over pipeline sequencing. See [ARCHITECTURE.md §1](.agents/docs/ARCHITECTURE.md).

This constrains **the code you write**. It is not a statement about how you sequence your own work.

## Repository layout

- **`.agents/`** — harness-neutral. Anything true about the project regardless of which assistant is running: docs, review skills, templates, task artifacts.
- **`.claude/`** — Claude Code only. How this harness acts on the above: [`agents/`](.claude/agents/) (architect, implementation, qa subagents) and [`skills/implement/`](.claude/skills/implement/) (the `/implement` workflow).

When adding a file, ask which of the two it is. Project truth goes in `.agents/`; harness mechanics go in `.claude/`.

## Implementation workflow

Roadmap milestones are implemented via **`/implement`** — see [.claude/skills/implement/SKILL.md](.claude/skills/implement/SKILL.md). Four stages: architect reviews the existing architecture and prerequisites, and the main thread writes `PLAN.md` from that review → **human approval gate** → implementation executes incremental TDD → architect and qa review in parallel with a bounded 3-iteration fix loop → main thread writes `WALKTHROUGH.md` from the git diff, then updates the roadmap.

Within that workflow the `Agent` tool is not merely permitted but **required**: the architect, implementation, and qa roles must run as real subagents (`subagent_type: architect | implementation | qa`). Simulating them inline is prohibited by Rule 9; if one cannot be spawned, halt and report rather than substituting yourself.

## Commands

```bash
# Run the pipeline
python -m src.orchestrator "Analyze recent INAIL updates on heat stress"

# Publish an approved draft
python src/publish.py --draft draft_20260909_001

# Tests
pytest tests/test_unit/ tests/test_integration/ -v

# Check MCP substrate connectivity
uv run --directory C:\Users\Saksham\Git\poc\AIAgents\mcp-server fastmcp inspect server.py
```

## MCP servers

Registered in [.mcp.json](.mcp.json): `hse-easy-mock` (the local regulatory substrate over stdio) and `strands-agents` (SDK documentation search). Tool signatures are listed in [AGENTS.md §4](AGENTS.md).

## Conventions

- Python with complete PEP 484/585/604 type annotations; imports at top of file.
- Pydantic v2 models with `model_config = ConfigDict(extra="ignore")`; no `dict[str, Any]` across module boundaries.
- `pathlib.Path` for all path handling — this is a Windows development environment.
- Tests before production code, always. No code in `src/` without a test in `tests/`.
