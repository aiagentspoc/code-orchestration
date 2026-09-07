# HSE Easy — Approach 1 Design Specification
## Content Factory (Code-Orchestrated Pipeline)

### 1. Executive Summary & Core Principle
* **Concept:** An industrial, deterministic editorial assembly line that transforms Italian and EU health-safety-environment (HSE) regulatory updates into high-quality, compliant technical content with explicit TDI lead-generation hooks.
* **Core Architectural Principle:** **Code owns the flow.** All routing, stage transitions, iteration counters, and error handling are hardcoded in procedural Python. Agents act as pure callable workers with zero autonomy over pipeline sequencing.

---

### 2. Models & Component Breakdown

| Component | Model | Role & Responsibilities |
| :--- | :--- | :--- |
| **Scope Parser** | `gpt-5-mini` | One-shot extraction of time window, sources, and sector constraints from the raw user prompt. |
| **Scout Agent** | `gpt-5-mini` | Calls local MCP server to fetch regulatory notices, applies newsworthiness scoring, and filters out noise. |
| **Writer Agent** | `gpt-5.4` | Generates a publication-ready HSE technical article adhering to TDI editorial and conversion guidelines. |
| **QA-Legal Agent** | `gpt-5.4` | Cross-checks legal citations against certified TDI references and outputs a structured compliance audit. |
| **Orchestrator** | Pure Python | Executes linear flow, handles deterministic retry loops, manages file I/O, and captures telemetry. |

---

### 3. Substrate & Tool Interfaces (`1_local_mcp_server`)
Approach 1 connects to the isolated local MCP server over `stdio` via Strands `MCPClient`:
* `fetch_regulatory_updates(sources: list[str], time_window: str)` $\rightarrow$ Returns curated fixtures from EUR-Lex, Gazzetta Ufficiale, and INAIL.
* `lookup_tdi_citations(query: str)` $\rightarrow$ Queries TDI’s certified legal cross-reference database.

---

### 4. Step-by-Step Data Flow & Control Logic

```text
[User Prompt]
      │
      ▼
[Scope Parser (gpt-5-mini)] ──► {"time_window": "2_months", "sources": ["Gazzetta", "INAIL"]}
      │
      ▼
[Scout Agent (gpt-5-mini)] ──► Queries MCP fetch_regulatory_updates() ──► Ranks qualifying updates
      │
      ▼ (For each qualifying update)
[Writer Agent (gpt-5.4)]   ──► Generates initial technical draft
      │
      ▼
[QA-Legal Agent (gpt-5.4)] ──► Evaluates legal accuracy via lookup_tdi_citations()
      │
      ├───────────────────────┬───────────────────────┐
      ▼                       ▼                       ▼
  [status: "PASS"]       [status: "WARNING"]     [status: "ERROR"]
      │                       │                       │
      │                       │               (Attempts < 2?)
      │                       │               ├── YES: Re-invoke Writer with error list -> QA
      │                       │               └── NO:  Append unresolved error notice
      │                       │                       │
      └───────────────────────┴───────────────────────┘
                              │
                              ▼
        [Save Candidate Draft to drafts/draft_<id>.json]
                              │
                              ▼ (Pipeline Execution Ends)
             [Human Review & Explicit TDI Approval]
                              │
                              ▼
    [publish.py --draft <id>] ──► Generates SEO, CTAs, & Final Article