# Implementation Plan: Phase 3 (Template Engine & Formatting)

**Target Milestone:** Phase 3: Template Engine & Formatting  
**Target Artifact Directory:** `.agents/tasks/phase-3/`  
**Execution Mode:** Strict Test-Driven Development (TDD) via 3 Incremental Batches (Rule 7)  
**Architectural Standard:** "Code Owns the Flow" & Deterministic Template Compilation (AGENTS.md Rule 1 & Rule 5)

---

## 1. Context & Task Scope
This phase focuses on building the deterministic Markdown artifact compiler (`src/template_engine.py`) that transforms validated Pydantic models (`ArticleDraft` and `DraftMetadata`) into publication-ready Markdown files matching `.agents/templates/draft.md`. 
The template engine enforces strict compliance with:
- **Rule 1 ("Code Owns the Flow"):** Pure procedural Python formatting and file I/O utility with zero autonomous agent routing or emergent behavior.
- **Rule 2 (Strict Schemas):** Relies strictly on Pydantic v2 models (`ArticleDraft` and `DraftMetadata`) defined in `src/schemas.py`.
- **Rule 5 (Draft Format & Persistence):** Persists drafts strictly as self-contained Markdown files (`drafts/draft_{YYYYMMDD}_{XXX}.md`) without separate JSON databases.
- **Rule 6 (Telemetry Rendering):** Formats wall-clock latency, token usage, and dollar cost estimates into the telemetry section.
- **Rule 3 & Rule 5 (Compliance Alerting):** Injects `[UNRESOLVED COMPLIANCE ALERT]` banner prominently into review notes when QA status is `ERROR` or unresolved errors exist.

---

## 2. Prerequisites
* `src/schemas.py` is fully implemented and tested (Phase 2 complete, all 26 tests green).
* Canonical template exists at `.agents/templates/draft.md`.
* The `drafts/` directory exists or is dynamically created by `src/template_engine.py` using `Path.mkdir(parents=True, exist_ok=True)`.

---

## 3. Strict TDD Strategy (Rule 7)

The implementation is partitioned into 3 incremental Red-Green-Refactor batches. Unit tests will be authored incrementally in `tests/test_unit/test_template_engine.py`.

### Batch 1: Draft ID Generation & File Collision Handling
* **Objective:** Implement sequential, date-based draft ID generation (`draft_YYYYMMDD_XXX.md` where `XXX` is a 3-digit zero-padded integer) that inspects existing files in `drafts/` and picks `max(XXX) + 1` safely to avoid overwriting.
* **Red:**
  - Author test functions in `tests/test_unit/test_template_engine.py`:
    - `test_generate_draft_id_initial()`: Returns `draft_{YYYYMMDD}_001` when the target directory is empty.
    - `test_generate_draft_id_sequential()`: Returns `draft_{YYYYMMDD}_002` when `draft_{YYYYMMDD}_001.md` already exists.
    - `test_generate_draft_id_collision_prevention()`: When gaps exist (e.g. `001` and `003`), safely selects `max(seq) + 1` = `004`.
    - `test_generate_draft_id_custom_and_default_dates()`: Verifies explicit `date` object and default current date handling.
  - **Expected Failure Mode:** `ImportError` / `AttributeError` for `generate_draft_id` and regex parsing logic.
* **Green:**
  - Implement `generate_draft_id(date_val: Optional[date] = None, drafts_dir: Path | str = "drafts") -> str` in `src/template_engine.py`.
  - Run `uv run pytest tests/test_unit/test_template_engine.py`.
  - Confirm all Batch 1 tests pass.
* **Refactor:**
  - Clean regex pattern matching, path normalization, and typing.

### Batch 2: Template Rendering, Placeholders, QA Badge & Compliance Alert Injection
* **Objective:** Map `ArticleDraft` and `DraftMetadata` fields to template placeholders according to `SPECIFICATIONS.md` Section 4. Handle verified citations list formatting and `[UNRESOLVED COMPLIANCE ALERT]` injection.
* **Red:**
  - Author test functions in `tests/test_unit/test_template_engine.py`:
    - `test_render_draft_success()`: Asserts all placeholders (`{headline}`, `{draft_id}`, `{brief_summary_for_managers}`, `{full_article_content}`, `{tdi_lead_generation_call_to_action}`, `{source_name}`, `{publication_date}`, `{source_document_title}`, `{approach_name}`, `{PASS / WARNING / ERROR}`, `{attempt_count}`) are replaced accurately.
    - `test_render_verified_citations()`: Verifies `qa_report.verified_citations` converts list of citations into markdown bullet points, or fallback message if none.
    - `test_render_draft_with_unresolved_alert()`: When `qa_report.status == "ERROR"` or `metadata.unresolved_errors` contains items, asserts `[UNRESOLVED COMPLIANCE ALERT]` is prominently prepended to review notes.
    - `test_render_draft_missing_placeholder_validation()`: Fails fast with `ValueError` if template is malformed or unrecognized placeholder remains.
  - **Expected Failure Mode:** `ImportError` / `AttributeError` for `render_draft`.
* **Green:**
  - Implement `render_draft(draft: ArticleDraft, metadata: DraftMetadata, template_path: Optional[Path | str] = None, template_content: Optional[str] = None) -> str` in `src/template_engine.py`.
  - Run `uv run pytest tests/test_unit/test_template_engine.py`.
  - Confirm all Batch 2 tests pass.
* **Refactor:**
  - Optimize string replacement and format helpers.

### Batch 3: Telemetry Formatting, Draft Persistence & End-to-End File Output
* **Objective:** Format numeric telemetry accurately (e.g. `{latency_seconds}s`, `${estimated_cost:.4f}`, `{total_tokens}`) and persist rendered drafts to `drafts/{draft_id}.md`.
* **Red:**
  - Author test functions in `tests/test_unit/test_template_engine.py`:
    - `test_render_telemetry_formatting()`: Asserts `latency_seconds` formats cleanly to 2 decimal places, and `estimated_cost` formats to `$0.0042` / tokens as integer.
    - `test_save_draft_persistence()`: Asserts `save_draft` writes the rendered markdown to `drafts/{draft_id}.md`, creates directories if missing (`parents=True, exist_ok=True`), and returns the resolved `Path`.
    - `test_template_engine_e2e_flow()`: End-to-end roundtrip: constructs sample models, renders draft, persists to disk, reads file back, and verifies all sections and placeholders.
  - **Expected Failure Mode:** `ImportError` / `AttributeError` for `save_draft`.
* **Green:**
  - Implement `save_draft(content: str, draft_id: str, output_dir: Path | str = "drafts") -> Path` in `src/template_engine.py`.
  - Export public API in `src/__init__.py`.
  - Run `uv run pytest tests/test_unit/test_template_engine.py`.
  - Confirm Batch 3 tests pass.
* **Refactor:**
  - Run complete test suite `uv run pytest` to ensure 0 regressions.

---

## 4. Proposed Changes & Specifications

### Target Files
1. **`src/template_engine.py`**:
   - `DEFAULT_TEMPLATE_PATH`: Path to `.agents/templates/draft.md`.
   - `generate_draft_id(target_date: Optional[date] = None, drafts_dir: Path | str = "drafts") -> str`
   - `format_citations_list(citations: list[str]) -> str`
   - `format_review_notes(qa_report: QAReport, unresolved_errors: list[str]) -> str`
   - `render_draft(draft: ArticleDraft, metadata: DraftMetadata, template_path: Optional[Path | str] = None, template_content: Optional[str] = None) -> str`
   - `save_draft(content: str, draft_id: str, output_dir: Path | str = "drafts") -> Path`
2. **`tests/test_unit/test_template_engine.py`**:
   - Comprehensive unit test suite executing all 3 TDD batches using `tmp_path` fixtures for filesystem isolation.
3. **`src/__init__.py`**:
   - Export public template engine functions.

---

## 5. Architectural & Quality Audit Checklist

### Architect Audit Checklist (`@architect-review`)
- [x] **"Code Owns the Flow" Alignment:** Pure deterministic procedural Python. Zero emergent loops or LLM sequencing.
- [x] **Strict Data Contracts (Rule 2):** Ingests `ArticleDraft` and `DraftMetadata` directly; no loose dictionaries.
- [x] **Draft Format Enforcement (Rule 5):** Hardcodes persistence strictly to Markdown (`drafts/draft_{YYYYMMDD}_{XXX}.md`) based on `.agents/templates/draft.md`.
- [x] **Telemetry & Cost Accounting (Rule 6):** Accurately renders wall-clock latency, token usage, and dollar cost estimates into template placeholders.
- [x] **Compliance Alert Injection (Rule 3):** Prominently injects `[UNRESOLVED COMPLIANCE ALERT]` when QA status is `ERROR` or unresolved errors exist.

### Code Reviewer Audit Checklist (`@code-reviewer`)
- [x] **Strict TDD Adherence (Rule 7):** 3 incremental Red-Green-Refactor batches executed sequentially without writing all tests upfront.
- [x] **Filesystem Safety:** Safe path resolution, auto-creating `drafts/` directory, and avoiding file overwrites on duplicate dates.
- [x] **Type Annotations (PEP 484/585/604):** Complete type annotations across all function signatures.

---

## 6. Questions & Decisions for Human Approval

1. **Missing Placeholder Fail-Fast Policy:** If any unrendered placeholder `{...}` remains in the rendered markdown, should `render_draft` raise a `ValueError` immediately?
   - *(Recommended)* **Yes, fail fast** with `ValueError` to prevent publication of malformed draft artifacts.
2. **Directory Auto-Creation:** Should `save_draft` and `generate_draft_id` auto-create the target drafts directory if it does not exist?
   - *(Recommended)* **Yes**, using `Path.mkdir(parents=True, exist_ok=True)`.
3. **Citations Fallback:** If `qa_report.verified_citations` is empty, should it render `  - (No citations verified)` or leave it blank?
   - *(Recommended)* Render `  - (No citations verified)` to maintain valid Markdown list structure under `* **Verified Citations:**`.
