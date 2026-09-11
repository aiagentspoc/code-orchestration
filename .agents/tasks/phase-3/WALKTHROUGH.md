# Phase 3 Walkthrough: Template Engine & Formatting

## Overview
This document outlines the implementation details for Phase 3 of the HSE Easy pipeline. It covers the iterative Test-Driven Development (TDD) process applied to build a robust template engine (`src/template_engine.py`) that predictably and deterministically formats Pydantic objects (`ArticleDraft` and `DraftMetadata`) into a final Markdown artifact based on the required specifications.

## 1. Incremental TDD Batches 

### Batch 1: Draft ID Generation & File Collision Handling
**Rationale:** To persist drafts with consistent numbering without accidentally overwriting existing ones, a directory parser was needed.
- **Implementation:** Added `generate_draft_id` which normalizes dates, creates the output directory `drafts/` if it does not exist (using `Path.mkdir(parents=True, exist_ok=True)`), and scans for `draft_{YYYYMMDD}_{XXX}.md` via regex. It correctly extracts the sequence numbers and returns the next highest `XXX`. 
- **Tests (Green):** Covered default date logic, sequential appending, gap-filling collision prevention (e.g., skips gracefully to max+1), and edge cases where no files are present.

### Batch 2: Template Rendering, Placeholders, QA Badge & Compliance Alert Injection
**Rationale:** "Code Owns the Flow" mandates no LLM emergent behavior for document compilation. A direct string replacement approach ensures strict adherence to `.agents/templates/draft.md`.
- **Implementation:** Added `render_draft` that maps all fields inside `ArticleDraft` and `DraftMetadata` to string replacement tuples.
  - Implemented `format_citations_list` that seamlessly falls back to `"  - (No citations verified)"` when the list is empty, preserving the template's exact layout.
  - Implemented `format_review_notes` that injects `[UNRESOLVED COMPLIANCE ALERT]` if QA status is `ERROR` or there are unresolved errors.
  - Included a fail-fast mechanism (as approved by human design decisions) that uses regex `\{[a-zA-Z0-9_]+\}` to detect unrendered placeholders post-replacement, raising a `ValueError`.
- **Tests (Green):** Covered accurate placeholder mapping, citation formatting, correct alert injection behavior, and verified that a `ValueError` is raised precisely when unrecognized template blocks are present.

### Batch 3: Telemetry Formatting, Draft Persistence & End-to-End File Output
**Rationale:** Proper float formatting is crucial for executive telemetry, and saving files correctly finishes the output requirement.
- **Implementation:** Added rounding behavior directly inside the replacements mapping (`{latency_seconds:.2f}` and `{estimated_cost:.4f}`). Wrote the `save_draft` function to write raw text bytes safely to the output path. Exported all critical components into `src/__init__.py`.
- **Tests (Green):** Confirmed float string format bounds, checked successful file creation with `save_draft`, and successfully performed a full roundtrip end-to-end flow test mimicking the actual program.

## 2. Test Coverage & Verification Results
- **Test Coverage:** Authored 11 comprehensive unit tests within `tests/test_unit/test_template_engine.py` using `tmp_path` fixtures for filesystem isolation.
- **Regression Suite:** Executed `uv run pytest` across the entire workspace (Phase 1, 2, and 3 tests collectively).
- **Result:** **37 tests passed in ~1.89 seconds with 0 regressions.**

## 3. Human-Approved Decisions Executed
1. **Missing Placeholder Fail-Fast Policy:** Raised `ValueError` aggressively when missing placeholders were left unrendered. 
2. **Directory Auto-Creation:** `Path.mkdir(parents=True, exist_ok=True)` deployed across `generate_draft_id` and `save_draft`.
3. **Citations Fallback:** Rendered fallback `"  - (No citations verified)"` to keep Markdown bullet list layouts intact on empty citations. 
