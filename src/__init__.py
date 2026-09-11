"""HSE Easy: Approach 1 - Code-Orchestrated Pipeline Package."""

from .schemas import (
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
from .template_engine import (
    generate_draft_id,
    render_draft,
    save_draft,
    format_citations_list,
    format_review_notes,
)

__version__ = "0.1.0"

__all__ = [
    "__version__",
    "RegulatoryUpdateSummary",
    "RegulatoryDocument",
    "CitationVerificationResult",
    "TDIServiceOffering",
    "PipelineScope",
    "ArticleDraft",
    "QAReport",
    "DraftMetadata",
    "RevisionPayload",
    "PipelineExitCode",
    "generate_draft_id",
    "render_draft",
    "save_draft",
    "format_citations_list",
    "format_review_notes",
]
