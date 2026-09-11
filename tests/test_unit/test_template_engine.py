from datetime import date
from pathlib import Path
import pytest

from src.schemas import ArticleDraft, DraftMetadata, QAReport
from src.template_engine import (
    format_citations_list,
    format_review_notes,
    generate_draft_id,
    render_draft,
    save_draft,
)


def test_generate_draft_id_initial(tmp_path):
    drafts_dir = tmp_path / "drafts"
    draft_id = generate_draft_id(date(2026, 9, 11), drafts_dir)
    assert draft_id == "draft_20260911_001"
    assert drafts_dir.exists()


def test_generate_draft_id_sequential(tmp_path):
    drafts_dir = tmp_path / "drafts"
    drafts_dir.mkdir()
    (drafts_dir / "draft_20260911_001.md").touch()
    
    draft_id = generate_draft_id(date(2026, 9, 11), drafts_dir)
    assert draft_id == "draft_20260911_002"


def test_generate_draft_id_collision_prevention(tmp_path):
    drafts_dir = tmp_path / "drafts"
    drafts_dir.mkdir()
    (drafts_dir / "draft_20260911_001.md").touch()
    (drafts_dir / "draft_20260911_003.md").touch()
    
    draft_id = generate_draft_id(date(2026, 9, 11), drafts_dir)
    assert draft_id == "draft_20260911_004"


def test_generate_draft_id_custom_and_default_dates(tmp_path):
    drafts_dir = tmp_path / "drafts"
    
    # Test explicit date
    custom_date = date(2025, 1, 1)
    draft_id_custom = generate_draft_id(custom_date, drafts_dir)
    assert draft_id_custom == "draft_20250101_001"
    
    # Test default date
    draft_id_default = generate_draft_id(drafts_dir=drafts_dir)
    today_str = date.today().strftime("%Y%m%d")
    assert draft_id_default == f"draft_{today_str}_001"


def test_render_draft_success():
    draft = ArticleDraft(
        headline="Test Headline",
        executive_summary="Summary",
        article_body="Body",
        tdi_cta="CTA"
    )
    metadata = DraftMetadata(
        draft_id="draft_20260911_001",
        source_name="EUR_LEX",
        publication_date="2026-09-11",
        source_document_title="Title",
        approach_name="Approach 1",
        qa_report=QAReport(status="PASS", verified_citations=["Ref A"], review_notes="All good"),
        attempts=1,
        latency_seconds=1.234,
        estimated_cost=0.005,
        total_tokens=100,
        unresolved_errors=[]
    )
    
    # Mock template matching the exact placeholders mentioned in the plan
    template_content = (
        "# {headline}\n"
        "**Draft ID:** {draft_id}\n"
        "## 📌 Executive Summary\n"
        "{brief_summary_for_managers}\n"
        "## 📖 Article Body\n"
        "{full_article_content}\n"
        "## 💼 Next Steps & TDI Specialist Support\n"
        "{tdi_lead_generation_call_to_action}\n"
        "--- \n"
        "## 📋 Source & Approach Details\n"
        "* **Source:** {source_name} ({publication_date}) — *{source_document_title}*\n"
        "* **Approach:** {approach_name}\n"
        "--- \n"
        "## ⚖️ Legal & Compliance Review (QA-Legal)\n"
        "* **Status:** {PASS / WARNING / ERROR}\n"
        "* **Revision Attempts:** {attempt_count}\n"
        "* **Verified Citations:**\n"
        "  - {citation_1}\n"
        "  - {citation_2}\n"
        "* **Review Notes:** {any_warnings_or_notes}\n"
    )
    
    rendered = render_draft(draft, metadata, template_content=template_content)
    assert "# Test Headline" in rendered
    assert "**Draft ID:** draft_20260911_001" in rendered
    assert "Summary" in rendered
    assert "Body" in rendered
    assert "CTA" in rendered
    assert "EUR_LEX" in rendered
    assert "2026-09-11" in rendered
    assert "Title" in rendered
    assert "Approach 1" in rendered
    assert "* **Status:** PASS" in rendered
    assert "* **Revision Attempts:** 1" in rendered
    assert "  - Ref A" in rendered
    assert "* **Review Notes:** All good" in rendered
    assert "{headline}" not in rendered


def test_render_verified_citations():
    assert format_citations_list(["Ref A", "Ref B"]) == "  - Ref A\n  - Ref B"
    assert format_citations_list([]) == "  - (No citations verified)"


def test_render_draft_with_unresolved_alert():
    qa_report = QAReport(status="ERROR", review_notes="Original note", verified_citations=[])
    notes = format_review_notes(qa_report, ["Error 1"])
    assert "[UNRESOLVED COMPLIANCE ALERT]" in notes
    assert "Original note" in notes


def test_render_draft_missing_placeholder_validation():
    draft = ArticleDraft(headline="H", executive_summary="S", article_body="B", tdi_cta="C")
    metadata = DraftMetadata(
        draft_id="ID", source_name="SN", publication_date="2026",
        source_document_title="Title", approach_name="Approach",
        qa_report=QAReport(status="PASS", verified_citations=[], review_notes=""),
        attempts=1, latency_seconds=1.0, estimated_cost=0.1, total_tokens=10,
        unresolved_errors=[]
    )
    
    # Template has a placeholder not in replacement map
    template_content = "{headline} and {unknown_placeholder}"
    with pytest.raises(ValueError, match="Unresolved placeholder found"):
        render_draft(draft, metadata, template_content=template_content)


def test_render_telemetry_formatting():
    draft = ArticleDraft(headline="H", executive_summary="S", article_body="B", tdi_cta="C")
    metadata = DraftMetadata(
        draft_id="ID", source_name="SN", publication_date="2026",
        source_document_title="Title", approach_name="Approach",
        qa_report=QAReport(status="PASS", verified_citations=[], review_notes=""),
        attempts=1, latency_seconds=1.239, estimated_cost=0.00421, total_tokens=100,
        unresolved_errors=[]
    )
    template_content = "{latency_seconds}s ${estimated_cost} {total_tokens}"
    rendered = render_draft(draft, metadata, template_content=template_content)
    assert "1.24s" in rendered
    assert "$0.0042" in rendered
    assert "100" in rendered


def test_save_draft_persistence(tmp_path):
    out_dir = tmp_path / "drafts"
    content = "Hello World"
    draft_id = "draft_20260911_001"
    saved_path = save_draft(content, draft_id, output_dir=out_dir)
    
    assert saved_path.exists()
    assert saved_path.name == f"{draft_id}.md"
    assert saved_path.read_text(encoding="utf-8") == "Hello World"
    assert out_dir.exists()


def test_template_engine_e2e_flow(tmp_path, monkeypatch):
    # Mock DEFAULT_TEMPLATE_PATH to point to a test template
    test_template_dir = tmp_path / ".agents" / "templates"
    test_template_dir.mkdir(parents=True)
    test_template = test_template_dir / "draft.md"
    test_template.write_text(
        "# [Article Headline Here]\n"
        "**Draft ID:** {draft_id}\n"
        "## 📌 Executive Summary\n"
        "{brief_summary_for_managers}\n"
        "## 📖 Article Body\n"
        "{full_article_content}\n"
        "## 💼 Next Steps & TDI Specialist Support\n"
        "{tdi_lead_generation_call_to_action}\n"
        "--- \n"
        "## 📋 Source & Approach Details\n"
        "* **Source:** {source_name} ({publication_date}) — *{source_document_title}*\n"
        "* **Approach:** {approach_name}\n"
        "--- \n"
        "## ⚖️ Legal & Compliance Review (QA-Legal)\n"
        "* **Status:** {PASS / WARNING / ERROR}\n"
        "* **Revision Attempts:** {attempt_count}\n"
        "* **Verified Citations:**\n"
        "  - {citation_1}\n"
        "  - {citation_2}\n"
        "* **Review Notes:** {any_warnings_or_notes}\n"
        "--- \n"
        "### ⏱️ Run Telemetry (For Benchmark)\n"
        "* **Time Taken:** {latency_seconds}s\n"
        "* **Estimated Cost:** ${estimated_cost} ({total_tokens} tokens)\n",
        encoding="utf-8"
    )
    
    import src.template_engine
    monkeypatch.setattr(src.template_engine, "DEFAULT_TEMPLATE_PATH", test_template)
    
    draft = ArticleDraft(
        headline="My Final Headline",
        executive_summary="Final Summary",
        article_body="Final Body",
        tdi_cta="Final CTA"
    )
    metadata = DraftMetadata(
        draft_id="draft_20261010_005",
        source_name="INAIL",
        publication_date="2026-10-10",
        source_document_title="INAIL Circular",
        approach_name="Approach 2",
        qa_report=QAReport(status="PASS", verified_citations=["Cite 1", "Cite 2"], review_notes="Looks great"),
        attempts=2,
        latency_seconds=3.1415,
        estimated_cost=0.01234,
        total_tokens=456,
        unresolved_errors=[]
    )
    
    out_dir = tmp_path / "drafts"
    rendered = render_draft(draft, metadata)
    saved_path = save_draft(rendered, metadata.draft_id, output_dir=out_dir)
    
    content = saved_path.read_text(encoding="utf-8")
    assert "# My Final Headline" in content
    assert "**Draft ID:** draft_20261010_005" in content
    assert "Final Summary" in content
    assert "Final Body" in content
    assert "Final CTA" in content
    assert "INAIL" in content
    assert "2026-10-10" in content
    assert "Approach 2" in content
    assert "PASS" in content
    assert "  - Cite 1\n  - Cite 2" in content
    assert "Looks great" in content
    assert "3.14s" in content
    assert "$0.0123" in content
    assert "456 tokens" in content
    
    # Assert no curly braces are left unrendered
    assert "{" not in content
    assert "}" not in content
