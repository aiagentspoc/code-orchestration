"""Markdown template compiler and telemetry renderer for HSE Easy drafts."""

import re
from datetime import date
from pathlib import Path
from typing import Optional

from .schemas import ArticleDraft, DraftMetadata, QAReport


def generate_draft_id(date_val: Optional[date] = None, drafts_dir: Path | str = "drafts") -> str:
    if date_val is None:
        date_val = date.today()
    
    date_str = date_val.strftime("%Y%m%d")
    drafts_path = Path(drafts_dir)
    drafts_path.mkdir(parents=True, exist_ok=True)
    
    max_seq = 0
    pattern = re.compile(rf"^draft_{date_str}_(\d{{3}})\.md$")
    
    for file_path in drafts_path.glob(f"draft_{date_str}_*.md"):
        match = pattern.match(file_path.name)
        if match:
            seq = int(match.group(1))
            if seq > max_seq:
                max_seq = seq
                
    return f"draft_{date_str}_{max_seq + 1:03d}"


DEFAULT_TEMPLATE_PATH: Path = Path(".agents/templates/draft.md")


def format_citations_list(citations: list[str]) -> str:
    if not citations:
        return "  - (No citations verified)"
    return "\n".join(f"  - {citation}" for citation in citations)


def format_review_notes(qa_report: QAReport, unresolved_errors: list[str]) -> str:
    alert_prefix = "[UNRESOLVED COMPLIANCE ALERT]\n\n"
    has_errors = qa_report.status == "ERROR" or len(unresolved_errors) > 0
    notes = qa_report.review_notes or ""
    if has_errors:
        return alert_prefix + notes
    return notes


def render_draft(
    draft: ArticleDraft,
    metadata: DraftMetadata,
    template_path: Optional[Path | str] = None,
    template_content: Optional[str] = None
) -> str:
    if template_content is None:
        path = Path(template_path) if template_path else DEFAULT_TEMPLATE_PATH
        template_content = path.read_text(encoding="utf-8")
        
    citations_str = format_citations_list(metadata.qa_report.verified_citations)
    review_notes_str = format_review_notes(metadata.qa_report, metadata.unresolved_errors)
    
    # Substitute multi-line verified citations block if standard template placeholders exist
    template_content = template_content.replace(
        "  - {citation_1}\n  - {citation_2}", 
        citations_str
    )
    
    # Map draft and metadata fields to corresponding template placeholders
    replacements = {
        "{headline}": draft.headline,
        "[Article Headline Here]": draft.headline,
        "{draft_id}": metadata.draft_id,
        "{brief_summary_for_managers}": draft.executive_summary,
        "{full_article_content}": draft.article_body,
        "{tdi_lead_generation_call_to_action}": draft.tdi_cta,
        "{source_name}": metadata.source_name,
        "{publication_date}": metadata.publication_date,
        "{source_document_title}": metadata.source_document_title,
        "{approach_name}": metadata.approach_name,
        "{PASS / WARNING / ERROR}": metadata.qa_report.status,
        "{attempt_count}": str(metadata.attempts),
        "{any_warnings_or_notes}": review_notes_str,
        # Also need telemetry formatting but that's batch 3, though we can map it here.
        "{latency_seconds}": f"{metadata.latency_seconds:.2f}",
        "{estimated_cost}": f"{metadata.estimated_cost:.4f}",
        "{total_tokens}": str(metadata.total_tokens)
    }
    
    rendered = template_content
    for placeholder, value in replacements.items():
        rendered = rendered.replace(placeholder, str(value))
        
    # Check for unrendered placeholders
    unrendered = re.findall(r"\{[a-zA-Z0-9_]+\}", rendered)
    if unrendered:
        raise ValueError(f"Unresolved placeholder found: {unrendered[0]}")
        
    return rendered


def save_draft(content: str, draft_id: str, output_dir: Path | str = "drafts") -> Path:
    out_path = Path(output_dir)
    out_path.mkdir(parents=True, exist_ok=True)
    file_path = out_path / f"{draft_id}.md"
    file_path.write_text(content, encoding="utf-8")
    return file_path
