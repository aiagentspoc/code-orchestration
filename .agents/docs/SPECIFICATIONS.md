# HSE Easy — Technical Specifications & Data Contracts
## Approach 1: Code-Orchestrated Pipeline

---

### 1. Purpose & Scope
This document specifies the technical requirements, data models, MCP tool signatures, and interface contracts for **Approach 1 (Content Factory)**. All components must strictly adhere to the schemas defined herein.

---

### 2. Substrate MCP Tools Specification (`HSE-Easy-Mock-Server`)

The pipeline connects to `HSE-Easy-Mock-Server` over `stdio` using FastMCP / JSON-RPC 2.0.

#### Transport & Launch
```json
{
  "command": "uv",
  "args": [
    "run",
    "--directory",
    "C:\\Users\\Saksham\\Git\\poc\\AIAgents\\mcp-server",
    "fastmcp",
    "run",
    "server.py"
  ]
}
```

#### Tool 1: `list_regulatory_updates`
* **Description:** Lists recent HSE regulatory updates, decrees, and circulars across EUR-Lex, Gazzetta Ufficiale, and INAIL within an optional date window. Returns lightweight metadata summaries for feed monitoring and newsworthiness triage.
* **Input Parameters:**
  | Name | Type | Required | Default | Description |
  | :--- | :--- | :---: | :--- | :--- |
  | `source` | `Optional[Literal["EUR_LEX", "GAZZETTA_UFFICIALE", "INAIL"]]` | No | `None` | Authoritative regulatory source body to filter by. |
  | `date_from` | `Optional[str]` | No | `None` | Start of publication date window (strict ISO 8601 `YYYY-MM-DD`). |
  | `date_to` | `Optional[str]` | No | `None` | End of publication date window (strict ISO 8601 `YYYY-MM-DD`). |
  | `limit` | `int` | No | `10` | Maximum number of updates to return (capped between 1 and 50). |
* **Return Type:** `List[RegulatoryUpdateSummary]`

#### Tool 2: `search_regulatory_docs`
* **Description:** Searches the regulatory database by keyword, topic category, industrial sector, or source authority. Returns matching document summaries and unique IDs for discovery.
* **Input Parameters:**
  | Name | Type | Required | Default | Description |
  | :--- | :--- | :---: | :--- | :--- |
  | `query` | `str` | **Yes** | — | Keyword to search in titles, summaries, references, topics, sectors, and markdown content. |
  | `source` | `Optional[Literal["EUR_LEX", "GAZZETTA_UFFICIALE", "INAIL"]]` | No | `None` | Source body filter. |
  | `topic` | `Optional[str]` | No | `None` | HSE topic category filter (e.g. `workplace_safety`, `chemical_risk`). |
  | `sector` | `Optional[str]` | No | `None` | Industrial sector filter (e.g. `manufacturing`, `construction`). |
* **Return Type:** `List[RegulatoryUpdateSummary]`

#### Tool 3: `get_document_by_id`
* **Description:** Retrieves the full structured text, article breakdown, legal obligations, and official metadata for a specific regulatory document by its ID.
* **Input Parameters:**
  | Name | Type | Required | Default | Description |
  | :--- | :--- | :---: | :--- | :--- |
  | `doc_id` | `str` | **Yes** | — | Unique slug identifier (e.g. `gu-2024-dl-preposti`, `inail-2024-circ-calore`). |
* **Return Type:** `RegulatoryDocument`

#### Tool 4: `verify_legal_citation`
* **Description:** Verifies whether a specific legal reference or article citation (e.g., `'D.Lgs. 81/2008 Art. 37'`) exists and is currently in force. Returns canonical citation text and official source URLs for legal QA.
* **Input Parameters:**
  | Name | Type | Required | Default | Description |
  | :--- | :--- | :---: | :--- | :--- |
  | `citation` | `str` | **Yes** | — | The raw legal reference or article citation text to verify. |
  | `source` | `Optional[Literal["EUR_LEX", "GAZZETTA_UFFICIALE", "INAIL"]]` | No | `None` | Optional source body filter (backward-compatible no-op). |
* **Return Type:** `CitationVerificationResult`

#### Tool 5: `get_tdi_service_offerings`
* **Description:** Retrieves relevant TDI consulting services, compliance audit offerings, and pre-approved Call-to-Action (CTA) templates matching a specific HSE regulatory topic or industry sector for commercial lead generation.
* **Input Parameters:**
  | Name | Type | Required | Default | Description |
  | :--- | :--- | :---: | :--- | :--- |
  | `topic` | `str` | **Yes** | — | HSE regulatory topic category (pass `""` for sector-only matching). |
  | `sector` | `Optional[str]` | No | `None` | Optional target industry sector to filter by. |
* **Return Type:** `List[TDIServiceOffering]`

---

### 3. Pydantic v2 Data Models

#### 3.1 Substrate Models (`models.py` / `src/schemas.py`)

```python
from typing import List, Literal, Optional
from pydantic import BaseModel, ConfigDict, Field

class RegulatoryUpdateSummary(BaseModel):
    """Tier 1 lightweight summary model for HSE regulatory updates."""
    model_config = ConfigDict(extra="ignore", populate_by_name=True)

    doc_id: str = Field(..., description="Unique slug identifier")
    source: Literal["EUR_LEX", "GAZZETTA_UFFICIALE", "INAIL"]
    doc_type: Literal["directive", "regulation", "decree", "circular", "guideline"]
    official_reference: str = Field(..., description="Canonical reference, e.g. 'D.Lgs. 81/2008'")
    title: str = Field(..., description="Official title in Italian")
    publication_date: str = Field(..., description="ISO 8601 YYYY-MM-DD")
    effective_date: Optional[str] = None
    impact_level: Literal["critical", "high", "medium", "low"]
    topic_tags: List[str] = Field(default_factory=list)
    summary: str = Field(..., description="Executive summary")
    canonical_url: str

class RegulatoryDocument(RegulatoryUpdateSummary):
    """Tier 2 comprehensive document model."""
    status: Literal["in_force", "amended", "repealed", "proposed"]
    target_sectors: List[str] = Field(default_factory=list)
    key_obligations: List[str] = Field(default_factory=list)
    penalties_summary: Optional[str] = None
    related_citations: List[str] = Field(default_factory=list)
    content_markdown: str

class CitationVerificationResult(BaseModel):
    """Legal citation verification result returned by legal QA tools."""
    model_config = ConfigDict(extra="ignore", populate_by_name=True)

    citation_input: str
    is_valid: bool
    status: Literal["in_force", "amended", "repealed", "unrecognized"]
    canonical_citation: str
    official_reference: Optional[str] = None
    official_url: Optional[str] = None
    verified_against_doc_id: Optional[str] = None
    notes: Optional[str] = None

class TDIServiceOffering(BaseModel):
    """Commercial service offering and pre-approved CTA templates."""
    model_config = ConfigDict(extra="ignore", populate_by_name=True)

    service_id: str
    service_name: str
    topic_category: str
    applicable_sectors: List[str] = Field(default_factory=list)
    value_proposition: str
    cta_headline: str
    cta_body: str
    landing_page_url: str
```

#### 3.2 Pipeline Internal Models (`src/schemas.py`)

```python
class PipelineScope(BaseModel):
    """Extracted scope boundaries from raw user prompt."""
    time_window: str = Field(..., description="Lookback window, e.g., '2_months', '30_days'")
    sources: List[Literal["EUR_LEX", "GAZZETTA_UFFICIALE", "INAIL"]] = Field(default_factory=list)
    sector_constraints: List[str] = Field(default_factory=list)
    max_drafts: Optional[int] = Field(default=None, description="Draft limit; None = unconstrained")

class ArticleDraft(BaseModel):
    """Article content generated by Writer Agent."""
    headline: str
    executive_summary: str
    article_body: str
    tdi_cta: str

class QAReport(BaseModel):
    """Compliance audit returned by QA-Legal Agent."""
    status: Literal["PASS", "WARNING", "ERROR"]
    verified_citations: List[str] = Field(default_factory=list)
    issues: List[str] = Field(default_factory=list)
    review_notes: str = ""

class DraftMetadata(BaseModel):
    """Complete record required to render .agents/templates/draft.md."""
    draft_id: str = Field(..., description="Consistent format: draft_YYYYMMDD_001")
    source_name: str
    publication_date: str
    source_document_title: str
    approach_name: str = "Approach 1 (Code-Orchestrated Pipeline)"
    qa_report: QAReport
    attempts: int
    latency_seconds: float
    estimated_cost: float
    total_tokens: int
    unresolved_errors: List[str] = Field(default_factory=list)

class RevisionPayload(BaseModel):
    """Structured payload passed directly to Writer Agent on revision attempts."""
    action: Literal["revise_draft"] = "revise_draft"
    attempt: int = Field(..., description="Revision attempt counter (2 or 3)")
    draft: ArticleDraft = Field(..., description="The previous ArticleDraft object to revise")
    qa_audit: QAReport = Field(..., description="The full QAReport containing errors and notes")
```


---

### 4. Template Placeholder Mapping (`.agents/templates/draft.md`)

Draft files are stored strictly as Markdown files in `drafts/draft_{YYYYMMDD}_{XXX}.md`:

```markdown
# {headline}

**Draft ID:** {draft_id}

---

## 📌 Executive Summary
{brief_summary_for_managers}

## 📖 Article Body
{full_article_content}

## 💼 Next Steps & TDI Specialist Support
{tdi_lead_generation_call_to_action}

---

## 📋 Source & Approach Details
* **Source:** {source_name} ({publication_date}) — *{source_document_title}*  
* **Approach:** {approach_name}

---

## ⚖️ Legal & Compliance Review (QA-Legal)
* **Status:** {status}
* **Revision Attempts:** {attempt_count}
* **Verified Citations:**
{verified_citations_markdown_list}
* **Review Notes:** {any_warnings_or_notes}

---

### ⏱️ Run Telemetry (For Benchmark)
* **Time Taken:** {latency_seconds}s
* **Estimated Cost:** ${estimated_cost} ({total_tokens} tokens)
```

#### Mapping Rules
1. `{headline}` $\rightarrow$ `ArticleDraft.headline`
2. `{brief_summary_for_managers}` $\rightarrow$ `ArticleDraft.executive_summary`
3. `{full_article_content}` $\rightarrow$ `ArticleDraft.article_body`
4. `{tdi_lead_generation_call_to_action}` $\rightarrow$ `ArticleDraft.tdi_cta`
5. `{status}` $\rightarrow$ `DraftMetadata.qa_report.status` (`PASS`, `WARNING`, or `ERROR`)
6. `{attempt_count}` $\rightarrow$ `DraftMetadata.attempts` (`1` or `2`)
7. `{verified_citations_markdown_list}` $\rightarrow$ Markdown bullet points of `DraftMetadata.qa_report.verified_citations`
8. `{any_warnings_or_notes}` $\rightarrow$ `DraftMetadata.qa_report.review_notes` plus any unresolved error banners.

---

### 5. CLI Command Specifications

#### 5.1 Pipeline Execution CLI
```bash
python -m src.orchestrator [PROMPT] [OPTIONS]
```
* **Arguments:**
  * `PROMPT` (required): Natural language task prompt (e.g. `"Analyze INAIL heat stress circular from last month"`).
* **Options:**
  * `--max-drafts INT`: Override prompt draft ceiling.
  * `--log-level [DEBUG|INFO|WARN|ERROR]`: Set logging verbosity (default: `INFO`).
  * `--drafts-dir PATH`: Directory to write draft files (default: `drafts/`).

#### 5.2 Publication CLI
```bash
python src/publish.py --draft DRAFT_ID [OPTIONS]
```
* **Arguments:**
  * `--draft DRAFT_ID` (required): Draft identifier to publish (e.g. `draft_20260909_001`).
* **Behavior:**
  1. Reads `drafts/{DRAFT_ID}.md`.
  2. Verifies QA status is `PASS` or `WARNING` (warns if publishing an `ERROR` draft).
  3. Formats publication metadata, generates SEO tags, and moves or marks draft as published.

---

### 6. Error & Exit Codes

| Code | Label | Meaning |
| :---: | :--- | :--- |
| `0` | `SUCCESS` | Pipeline executed; qualifying updates processed and drafts saved. |
| `1` | `NO_UPDATES` | Scout found no regulatory updates matching scope; clean exit. |
| `2` | `MCP_ERROR` | Subprocess connection to `hse-easy-mock` failed or crashed. |
| `3` | `PARSER_ERROR` | Scope parser failed to extract mandatory parameters. |
| `4` | `PERSISTENCE_ERROR` | Failed to write markdown draft to disk. |

