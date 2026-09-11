"""Unit tests for HSE Easy Pydantic v2 schemas and data contracts.

Batch 1: Substrate data models (RegulatoryUpdateSummary, RegulatoryDocument,
CitationVerificationResult, TDIServiceOffering).
"""

import pytest
from pydantic import ValidationError

from src.schemas import (
    ArticleDraft,
    CitationVerificationResult,
    DraftMetadata,
    PipelineExitCode,
    PipelineScope,
    QAReport,
    RegulatoryDocument,
    RegulatoryUpdateSummary,
    RevisionPayload,
    TDIServiceOffering,
)


# ============================================================================
# Batch 1: Substrate Models Tests
# ============================================================================


def test_regulatory_update_summary_validation() -> None:
    """Test valid instantiation, literal constraints, and defaults of RegulatoryUpdateSummary."""
    valid_payload = {
        "doc_id": "inail-2024-circ-calore",
        "source": "INAIL",
        "doc_type": "circular",
        "official_reference": "Circolare INAIL n. 28/2024",
        "title": "Linee guida per la gestione del rischio calore nei luoghi di lavoro",
        "publication_date": "2024-07-01",
        "impact_level": "high",
        "summary": "Misure precauzionali e tutela dei lavoratori esposti ad elevate temperature ambientali.",
        "canonical_url": "https://www.inail.it/atti/circolare-28-2024.html",
    }
    model = RegulatoryUpdateSummary(**valid_payload)
    assert model.doc_id == "inail-2024-circ-calore"
    assert model.source == "INAIL"
    assert model.doc_type == "circular"
    assert model.impact_level == "high"
    assert model.effective_date is None
    assert model.topic_tags == []

    # Test invalid literal for source
    with pytest.raises(ValidationError) as exc_info:
        RegulatoryUpdateSummary(**{**valid_payload, "source": "INVALID_SOURCE"})
    assert "source" in str(exc_info.value)

    # Test invalid literal for impact_level
    with pytest.raises(ValidationError) as exc_info:
        RegulatoryUpdateSummary(**{**valid_payload, "impact_level": "extreme"})
    assert "impact_level" in str(exc_info.value)

    # Test missing mandatory field
    incomplete_payload = valid_payload.copy()
    del incomplete_payload["doc_id"]
    with pytest.raises(ValidationError) as exc_info:
        RegulatoryUpdateSummary(**incomplete_payload)
    assert "doc_id" in str(exc_info.value)


def test_regulatory_document_inheritance_and_fields() -> None:
    """Test RegulatoryDocument inherits from RegulatoryUpdateSummary and validates tier 2 fields."""
    valid_doc_payload = {
        "doc_id": "gu-2024-dl-preposti",
        "source": "GAZZETTA_UFFICIALE",
        "doc_type": "decree",
        "official_reference": "D.Lgs. 81/2008 Art. 19",
        "title": "Modifiche e integrazioni alle attribuzioni del preposto per la sicurezza",
        "publication_date": "2024-05-15",
        "effective_date": "2024-06-01",
        "impact_level": "critical",
        "topic_tags": ["workplace_safety", "preposti"],
        "summary": "Nuovi obblighi di vigilanza e interruzione temporanea delle lavorazioni.",
        "canonical_url": "https://www.gazzettaufficiale.it/eli/id/2024/05/15/24G00088/sg",
        "status": "in_force",
        "target_sectors": ["manufacturing", "construction"],
        "key_obligations": [
            "Sovrintendere e vigilare sulla conformità alle norme di prevenzione",
            "Interrompere l'attività lavorativa in caso di pericolo grave e immediato",
        ],
        "penalties_summary": "Arresto fino a 2 mesi o ammenda da 491,40 a 1.474,21 euro",
        "related_citations": ["D.Lgs. 81/2008 Art. 19", "D.Lgs. 81/2008 Art. 37"],
        "content_markdown": "# Modifiche D.Lgs. 81/2008\n\nTesto coordinato con le novità...",
    }
    model = RegulatoryDocument(**valid_doc_payload)
    assert isinstance(model, RegulatoryUpdateSummary)
    assert model.status == "in_force"
    assert len(model.target_sectors) == 2
    assert len(model.key_obligations) == 2
    assert model.penalties_summary is not None
    assert "preposti" in model.topic_tags
    assert "# Modifiche" in model.content_markdown

    # Test invalid status literal
    with pytest.raises(ValidationError) as exc_info:
        RegulatoryDocument(**{**valid_doc_payload, "status": "deprecated"})
    assert "status" in str(exc_info.value)


def test_citation_verification_result_validation() -> None:
    """Test CitationVerificationResult fields, status literals, and optional fields."""
    valid_citation = {
        "citation_input": "D.Lgs. 81/2008 Art. 37",
        "is_valid": True,
        "status": "in_force",
        "canonical_citation": "Decreto Legislativo 9 aprile 2008, n. 81 - Articolo 37",
        "official_reference": "D.Lgs. 81/2008",
        "official_url": "https://www.normattiva.it/uri-res/N2Ls?urn:nir:stato:decreto.legislativo:2008-04-09;81!art37",
        "verified_against_doc_id": "gu-2008-dlgs-81",
        "notes": "Formazione obbligatoria dei lavoratori e loro rappresentanti.",
    }
    model = CitationVerificationResult(**valid_citation)
    assert model.citation_input == "D.Lgs. 81/2008 Art. 37"
    assert model.is_valid is True
    assert model.status == "in_force"

    # Test unrecognized status
    unrecognized_citation = {
        "citation_input": "Regolamento Fantasma 99/9999",
        "is_valid": False,
        "status": "unrecognized",
        "canonical_citation": "Non riconosciuto",
    }
    model_unrec = CitationVerificationResult(**unrecognized_citation)
    assert model_unrec.is_valid is False
    assert model_unrec.status == "unrecognized"
    assert model_unrec.official_reference is None


def test_tdi_service_offering_validation() -> None:
    """Test TDIServiceOffering fields and pre-approved CTA templates."""
    offering_data = {
        "service_id": "tdi-audit-calore",
        "service_name": "Audit e Valutazione Microclima e Rischio Calore",
        "topic_category": "thermal_stress",
        "applicable_sectors": ["construction", "agriculture", "foundry"],
        "value_proposition": "Valutazione strumentale con sonde WBGT e protocolli operativi certificati.",
        "cta_headline": "Proteggi i tuoi lavoratori dal rischio stress termico estivo",
        "cta_body": "Contatta gli esperti HSE di TDI per pianificare la valutazione strumentale del microclima.",
        "landing_page_url": "https://www.tdi.it/servizi/valutazione-rischio-calore",
    }
    offering = TDIServiceOffering(**offering_data)
    assert offering.service_id == "tdi-audit-calore"
    assert offering.topic_category == "thermal_stress"
    assert len(offering.applicable_sectors) == 3


def test_substrate_models_extra_ignore() -> None:
    """Test that all substrate models ignore extraneous fields (extra='ignore')."""
    payload = {
        "doc_id": "eurlex-2024-dir-1234",
        "source": "EUR_LEX",
        "doc_type": "directive",
        "official_reference": "Direttiva (UE) 2024/1234",
        "title": "Direttiva sulle emissioni industriali",
        "publication_date": "2024-04-10",
        "impact_level": "medium",
        "summary": "Nuove soglie di emissione per impianti di combustione.",
        "canonical_url": "https://eur-lex.europa.eu/legal-content/IT/TXT/?uri=CELEX:32024L1234",
        "unexpected_backend_internal_flag": True,
        "legacy_metadata_v1": {"random_key": "random_value"},
    }
    summary = RegulatoryUpdateSummary(**payload)
    assert not hasattr(summary, "unexpected_backend_internal_flag")
    assert not hasattr(summary, "legacy_metadata_v1")


# ============================================================================
# Batch 2: Internal Pipeline Models & Revision Payload Tests
# ============================================================================


def test_pipeline_scope_defaults_and_unconstrained() -> None:
    """Test PipelineScope default unconstrained ceiling (max_drafts=None) and sources filtering."""
    scope = PipelineScope(time_window="past_3_months")
    assert scope.time_window == "past_3_months"
    assert scope.max_drafts is None  # Mandatory default per Rule 4
    assert scope.sources == []
    assert scope.sector_constraints == []

    # Valid with constrained ceiling and sources
    custom_scope = PipelineScope(
        time_window="30_days",
        sources=["INAIL", "EUR_LEX"],
        sector_constraints=["construction"],
        max_drafts=3,
    )
    assert custom_scope.max_drafts == 3
    assert len(custom_scope.sources) == 2

    # Invalid source literal
    with pytest.raises(ValidationError) as exc_info:
        PipelineScope(time_window="30_days", sources=["UNKNOWN_SOURCE"])  # type: ignore[list-item]
    assert "sources" in str(exc_info.value)


def test_article_draft_fields() -> None:
    """Test ArticleDraft requires all 4 mandatory components from Writer agent."""
    valid_draft = {
        "headline": "Nuove Linee Guida INAIL sul Rischio Calore nei Cantieri",
        "executive_summary": "Sintesi per i responsabili RSPP sulle misure contro lo stress termico.",
        "article_body": "## Dettagli tecnici\nL'INAIL ha pubblicato le indicazioni operative...",
        "tdi_cta": "Contatta TDI per la redazione del Piano di Emergenza Calore.",
    }
    draft = ArticleDraft(**valid_draft)
    assert draft.headline.startswith("Nuove Linee")
    assert draft.tdi_cta.startswith("Contatta TDI")

    # Missing field raises ValidationError
    incomplete = valid_draft.copy()
    del incomplete["tdi_cta"]
    with pytest.raises(ValidationError) as exc_info:
        ArticleDraft(**incomplete)
    assert "tdi_cta" in str(exc_info.value)


def test_qa_report_tri_state_and_defaults() -> None:
    """Test QAReport status literals (PASS/WARNING/ERROR) and default collections."""
    report_pass = QAReport(status="PASS", verified_citations=["D.Lgs. 81/2008 Art. 37"])
    assert report_pass.status == "PASS"
    assert report_pass.issues == []
    assert report_pass.review_notes == ""

    report_error = QAReport(
        status="ERROR",
        issues=["Citazione non valida o abrogata: Art. 999"],
        review_notes="Correggere riferimento normativo.",
    )
    assert report_error.status == "ERROR"
    assert len(report_error.issues) == 1

    report_warning = QAReport(status="WARNING", review_notes="Raccomandazione prudenziale")
    assert report_warning.status == "WARNING"

    with pytest.raises(ValidationError) as exc_info:
        QAReport(status="FAILED")  # type: ignore[arg-type]
    assert "status" in str(exc_info.value)


def test_revision_payload_structure() -> None:
    """Test RevisionPayload structure and nested model validation for revision loops."""
    draft = ArticleDraft(
        headline="Bozza Iniziale",
        executive_summary="Sintesi",
        article_body="Corpo dell'articolo con riferimento errato",
        tdi_cta="CTA TDI",
    )
    qa_audit = QAReport(
        status="ERROR",
        issues=["Citazione fittizia rilevata"],
        review_notes="Rimuovere citazione inesistente.",
    )
    payload = RevisionPayload(
        attempt=2,
        draft=draft,
        qa_audit=qa_audit,
    )
    assert payload.action == "revise_draft"
    assert payload.attempt == 2
    assert isinstance(payload.draft, ArticleDraft)
    assert isinstance(payload.qa_audit, QAReport)
    assert payload.qa_audit.status == "ERROR"


# ============================================================================
# Batch 3: Composite Metadata, Exit Codes & Serialization Roundtrip Tests
# ============================================================================


def test_draft_metadata_composition() -> None:
    """Test DraftMetadata schema composition, defaults, and telemetry fields."""
    qa_report = QAReport(
        status="PASS",
        verified_citations=["D.Lgs. 81/2008 Art. 37"],
        issues=[],
        review_notes="Nessuna non conformità rilevata.",
    )
    metadata = DraftMetadata(
        draft_id="draft_20260910_001",
        source_name="INAIL",
        publication_date="2024-07-01",
        source_document_title="Circolare INAIL n. 28/2024",
        qa_report=qa_report,
        attempts=1,
        latency_seconds=14.2,
        estimated_cost=0.045,
        total_tokens=1820,
    )
    assert metadata.draft_id == "draft_20260910_001"
    assert metadata.approach_name == "Approach 1 (Code-Orchestrated Pipeline)"
    assert metadata.unresolved_errors == []
    assert metadata.qa_report.status == "PASS"
    assert metadata.attempts == 1
    assert metadata.latency_seconds == 14.2
    assert metadata.estimated_cost == 0.045
    assert metadata.total_tokens == 1820


def test_pipeline_exit_codes() -> None:
    """Test PipelineExitCode integer values and mapping matching SPECIFICATIONS.md Section 6."""
    assert PipelineExitCode.SUCCESS == 0
    assert PipelineExitCode.NO_UPDATES == 1
    assert PipelineExitCode.MCP_ERROR == 2
    assert PipelineExitCode.PARSER_ERROR == 3
    assert PipelineExitCode.PERSISTENCE_ERROR == 4


def test_schema_json_serialization_roundtrip() -> None:
    """Test model_dump_json and model_validate_json roundtrips across models."""
    qa_report = QAReport(
        status="WARNING",
        verified_citations=["Direttiva 2024/1234"],
        issues=["Circolare ministeriale non ancora pubblicata in GU"],
        review_notes="Pubblicare con nota di cautela.",
    )
    metadata = DraftMetadata(
        draft_id="draft_20260910_002",
        source_name="EUR_LEX",
        publication_date="2024-04-10",
        source_document_title="Direttiva sulle emissioni",
        qa_report=qa_report,
        attempts=2,
        latency_seconds=28.5,
        estimated_cost=0.082,
        total_tokens=3500,
        unresolved_errors=[],
    )
    json_str = metadata.model_dump_json()
    reconstructed = DraftMetadata.model_validate_json(json_str)
    assert reconstructed.draft_id == metadata.draft_id
    assert reconstructed.qa_report.status == "WARNING"
    assert reconstructed.qa_report.verified_citations == ["Direttiva 2024/1234"]
    assert reconstructed.latency_seconds == 28.5

    # Also test RevisionPayload serialization roundtrip
    draft = ArticleDraft(
        headline="Test Headline",
        executive_summary="Test Summary",
        article_body="Test Body",
        tdi_cta="Test CTA",
    )
    rev_payload = RevisionPayload(
        attempt=2,
        draft=draft,
        qa_audit=qa_report,
    )
    rev_json = rev_payload.model_dump_json()
    reconstructed_rev = RevisionPayload.model_validate_json(rev_json)
    assert reconstructed_rev.attempt == 2
    assert reconstructed_rev.draft.headline == "Test Headline"
    assert reconstructed_rev.qa_audit.status == "WARNING"


