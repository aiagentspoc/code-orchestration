# Implementation Plan: Phase 1 — Environment, Dependencies & Packaging Setup

**Target Milestone:** Phase 1: Environment & Packaging  
**Target Artifact Directory:** `.agents/tasks/phase-1/`  
**Execution Mode:** Strict Test-Driven Development (TDD) via 3 Incremental Batches  
**Architectural Standard:** "Code Owns the Flow" (AGENTS.md Rule 1 & Rule 7)

---

## 1. Context & Task Scope

### Objectives
1. Establish a reproducible, modern Python packaging configuration in `pyproject.toml` using `uv` and `hatchling`.
2. Configure all project dependencies specified in [ROADMAP.md](file:///c:/Users/Saksham/Git/poc/AIAgents/code-orchestration/ROADMAP.md) and [.agents/docs/SPECIFICATIONS.md](file:///c:/Users/Saksham/Git/poc/AIAgents/code-orchestration/.agents/docs/SPECIFICATIONS.md):
   - `strands-agents>=0.1.0` (Strands Agents SDK for callable worker LLM agents)
   - `pydantic>=2.0.0` (Pydantic v2 data models and strict contracts)
   - `fastmcp>=0.1.0` (FastMCP stdio substrate transport)
   - `hse-easy-mock-mcp` (Local editable substrate package from `../mcp-server`)
   - `pytest>=8.0.0` & `pytest-asyncio>=0.23.0` (Test execution harness)
3. Scaffold production source modules in `src/` and test suites in `tests/`:
   - `src/__init__.py`
   - `src/schemas.py`
   - `src/mcp_client.py`
   - `src/agents.py`
   - `src/template_engine.py`
   - `src/orchestrator.py`
   - `src/publish.py`
   - `tests/__init__.py`, `tests/test_unit/__init__.py`, `tests/test_integration/__init__.py`
   - `drafts/.gitkeep` and `logs/.gitkeep`
4. Configure `pytest` options (`testpaths = ["tests"]`, `pythonpath = ["."]`, `asyncio_mode = "auto"`).
5. Verify test environment smoke pass with 0 errors.

---

## 2. Prerequisites

1. **Python Interpreter:** Python >= 3.11 (local environment confirmed running Python 3.11.16).
2. **Package Manager:** `uv` installed and available (confirmed `uv 0.12.9`).
3. **Substrate MCP Server:** Located at `../mcp-server` with `hse-easy-mock-mcp` package.
4. **Permissions & Hooks:** Automation hooks active in `.agents/hooks.json` and `.agents/hooks/auto_allow.py` for pre-approved test and build commands.

---

## 3. Strict TDD Strategy (Rule 7)

Execution is divided into 3 small, incremental TDD batches. Tests for each batch are authored and verified failing before any implementation code is written.

### Batch 1: Packaging Configuration & Dependency Resolution
* **Red:**
  - Create `tests/test_unit/test_packaging.py`.
  - Author tests:
    - `test_pyproject_toml_exists()`: Validates `pyproject.toml` exists at workspace root.
    - `test_pyproject_metadata()`: Parses `pyproject.toml` with stdlib `tomllib` and validates:
      - `project.name == "code-orchestration"`
      - `project.version == "0.1.0"`
      - Declared runtime dependencies include `strands-agents`, `pydantic`, `fastmcp`, and `hse-easy-mock-mcp`.
      - Declared dev dependencies include `pytest` and `pytest-asyncio`.
    - `test_dependencies_importable()`: Verifies that core runtime dependencies (`pydantic`, `fastmcp`, `strands`, `fastmcp`) can be imported in the active environment.
  - **Expected Failure Mode:** `FileNotFoundError` or assertion failure because `pyproject.toml` is not yet created.
* **Green:**
  - Create `pyproject.toml` adhering to standard PEP 621 / Hatchling specifications.
  - Run `uv run pytest tests/test_unit/test_packaging.py`.
  - Verify all Batch 1 tests pass.
* **Refactor:**
  - Standardize dependency specifiers and format TOML cleanly.

### Batch 2: Module Skeleton & Directory Scaffolding
* **Red:**
  - Create `tests/test_unit/test_module_structure.py`.
  - Author tests:
    - `test_src_package_importable()`: Verifies `import src` succeeds and exposes `src.__version__ == "0.1.0"`.
    - `test_submodules_exist()`: Verifies that all mandated pipeline modules (`src.schemas`, `src.mcp_client`, `src.agents`, `src.template_engine`, `src.orchestrator`, `src.publish`) are importable.
    - `test_artifact_directories_exist()`: Verifies that `drafts/` and `logs/` directories exist and are writable filesystem directories.
  - **Expected Failure Mode:** `ModuleNotFoundError: No module named 'src'` or missing submodule imports.
* **Green:**
  - Create `src/__init__.py` with `__version__ = "0.1.0"`.
  - Create typed stub files:
    - `src/schemas.py`
    - `src/mcp_client.py`
    - `src/agents.py`
    - `src/template_engine.py`
    - `src/orchestrator.py`
    - `src/publish.py`
  - Create `drafts/.gitkeep` and `logs/.gitkeep`.
  - Run `uv run pytest tests/test_unit/test_module_structure.py`.
  - Verify all Batch 2 tests pass.
* **Refactor:**
  - Add docstrings to all newly created modules defining their role in the "Code Owns the Flow" architecture.

### Batch 3: Pytest Configuration & Test Harness Integration
* **Red:**
  - Configure `[tool.pytest.ini_options]` in `pyproject.toml`.
  - Author a baseline smoke test in `tests/test_integration/test_smoke.py`:
    - `test_test_runner_smoke()`: Asserts basic pytest assertion and asyncio fixture compatibility.
* **Green:**
  - Run `uv run pytest -v` across both `tests/test_unit/` and `tests/test_integration/`.
  - Confirm 100% test pass rate with zero errors, zero warnings.
* **Refactor:**
  - Clean up any warnings or transient cache files.

---

## 4. Proposed Changes & Specifications

### File Manifest

| File Path | Action | Description |
| :--- | :---: | :--- |
| `pyproject.toml` | `[NEW]` | PEP 621 packaging metadata, dependencies, UV sources, and Pytest configuration |
| `src/__init__.py` | `[NEW]` | Package initializer with `__version__ = "0.1.0"` |
| `src/schemas.py` | `[NEW]` | Stub module for Pydantic v2 data models |
| `src/mcp_client.py` | `[NEW]` | Stub module for FastMCP stdio client wrapper |
| `src/agents.py` | `[NEW]` | Stub module for Strands Agent worker definitions |
| `src/template_engine.py` | `[NEW]` | Stub module for Markdown template compiler |
| `src/orchestrator.py` | `[NEW]` | Stub module for procedural pipeline controller |
| `src/publish.py` | `[NEW]` | Stub module for human gate publishing CLI |
| `tests/__init__.py` | `[NEW]` | Tests root package marker |
| `tests/test_unit/__init__.py` | `[NEW]` | Unit tests package marker |
| `tests/test_unit/test_packaging.py` | `[NEW]` | TDD Batch 1: Packaging & dependency validation tests |
| `tests/test_unit/test_module_structure.py` | `[NEW]` | TDD Batch 2: Module structure & import tests |
| `tests/test_integration/__init__.py` | `[NEW]` | Integration tests package marker |
| `tests/test_integration/test_smoke.py` | `[NEW]` | TDD Batch 3: Pytest & harness smoke tests |
| `drafts/.gitkeep` | `[NEW]` | Git placeholder ensuring drafts folder exists |
| `logs/.gitkeep` | `[NEW]` | Git placeholder ensuring logs folder exists |

---

## 5. Architectural & Quality Audit Checklist

### Architect Audit Checklist (`@architect-review`)
- [x] **"Code Owns the Flow" alignment:** Pipeline architecture layout cleanly isolates procedural orchestration (`src/orchestrator.py`), callable workers (`src/agents.py`), substrate client (`src/mcp_client.py`), and publishing gate (`src/publish.py`).
- [x] **Zero autonomous sequence leak:** Stubs do not introduce emergent agent loops or autonomous delegation.
- [x] **Substrate Isolation:** `src/mcp_client.py` designated as sole interface to `hse-easy-mock` stdio transport; no direct imports of `mcp-server` into orchestrator.
- [x] **Template Decoupling:** `src/template_engine.py` isolated from LLM workers.

### Code Reviewer Audit Checklist (`@code-reviewer`)
- [x] **Strict TDD adherence:** 3 incremental batches with clear Red-Green-Refactor cycles. No production code authored before failing tests.
- [x] **Type Annotations:** Full typing on all module variables and functions.
- [x] **Cross-platform path safety:** Use of `pathlib.Path` for all filesystem operations.
- [x] **Subprocess & Environment hygiene:** Clean invocation via `uv run pytest`.

---

## 6. Questions & Decisions for Human Approval

1. **Build Backend:** We use `hatchling` as the build backend, which works natively with `uv` and standard PEP 621 packaging.
2. **Local Substrate Dependency:** Configured `hse-easy-mock-mcp` via `[tool.uv.sources]` referencing `../mcp-server` in editable mode.
3. **Drafts and Logs Retention:** Added `.gitkeep` markers so the required output directories are tracked in version control while keeping actual generated artifacts ignored via `.gitignore`.
