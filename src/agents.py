"""Strands Agent worker definitions for the HSE Easy editorial pipeline.

Every worker here is a **stateless, task-bounded callable** (ARCHITECTURE §1).
Factories build an ``Agent``; runners invoke it for exactly one LLM round trip
and return a typed :class:`~src.schemas.WorkerOutput` carrying the structured
payload plus its telemetry. Routing, iteration counters, the revision loop,
``max_drafts`` truncation, persistence and MCP lifecycle ownership all belong
to ``src/orchestrator.py`` and appear nowhere in this module.

Provider isolation: this module imports only the abstract
``strands.models.model.Model``. Concrete providers live in
:mod:`src.model_factory` alone.
"""

import json
from collections.abc import Sequence
from typing import Final, TypeVar

from pydantic import BaseModel
from strands import Agent
from strands.agent.agent_result import AgentResult
from strands.models.model import Model
from strands.types.tools import AgentTool

from .mcp_client import HSEMockMCPClient
from .schemas import (
    AgentTelemetry,
    ArticleDraft,
    PipelineScope,
    QAReport,
    RegulatoryDocument,
    RevisionPayload,
    ScoutReport,
    ToolInvocation,
    WorkerOutput,
)

__all__ = [
    "SCOPE_PARSER_MODEL_ID",
    "SCOUT_MODEL_ID",
    "SCOUT_TOOL_NAMES",
    "WRITER_MODEL_ID",
    "WRITER_TOOL_NAMES",
    "QA_LEGAL_MODEL_ID",
    "QA_LEGAL_TOOL_NAMES",
    "SCOPE_PARSER_SYSTEM_PROMPT",
    "SCOUT_SYSTEM_PROMPT",
    "WRITER_SYSTEM_PROMPT",
    "QA_LEGAL_SYSTEM_PROMPT",
    "extract_telemetry",
    "build_scope_parser_agent",
    "build_scout_agent",
    "build_writer_agent",
    "build_qa_legal_agent",
    "run_scope_parser",
    "run_scout",
    "run_writer",
    "run_qa_legal",
]

_PayloadT = TypeVar("_PayloadT", bound=BaseModel)

# Model bindings, canonical per ARCHITECTURE §3.
SCOPE_PARSER_MODEL_ID: Final[str] = "gpt-5-mini"
SCOUT_MODEL_ID: Final[str] = "gpt-5-mini"
WRITER_MODEL_ID: Final[str] = "gpt-5.4"
QA_LEGAL_MODEL_ID: Final[str] = "gpt-5.4"

# Declared tool intent per ARCHITECTURE §3. Under D19 these are NOT the tools actually
# attached — every tool-using worker receives all five — but they document what each
# worker is expected to reach for, and they are the argument a caller passes to
# ``tool_names`` to restore scoping for the Phase 8 scoped-versus-unscoped comparison.
SCOUT_TOOL_NAMES: Final[tuple[str, ...]] = (
    "list_regulatory_updates",
    "search_regulatory_docs",
    "get_document_by_id",
)
WRITER_TOOL_NAMES: Final[tuple[str, ...]] = (
    "get_tdi_service_offerings",
    "get_document_by_id",
)
QA_LEGAL_TOOL_NAMES: Final[tuple[str, ...]] = ("verify_legal_citation",)


SCOPE_PARSER_SYSTEM_PROMPT: Final[str] = """\
You are the Scope Parser of the HSE Easy editorial pipeline.

## Task
Perform one-shot extraction of the editorial scope from a single raw user prompt,
and return it as a `PipelineScope` structured output. Work only from what the user
wrote; never invent constraints they did not express.

## Output contract — `PipelineScope`
- `time_window` (REQUIRED, never omit): the lookback window the user asked for, as a
  compact snake_case token such as `past_3_months`, `30_days` or `last_year`. If the
  user gives no window, default to `past_3_months` — an empty or missing value is a
  contract violation.
- `sources`: any of `EUR_LEX`, `GAZZETTA_UFFICIALE`, `INAIL` that the user named.
  Leave the list empty when the user named none; an empty list means "all sources".
- `sector_constraints`: industrial sectors the user restricted to, lowercase
  (e.g. `construction`, `manufacturing`, `agriculture`). Empty means unrestricted.
- `max_drafts`: an integer ONLY when the user explicitly states a draft limit
  ("at most 3 articles", "just one"). Otherwise it MUST be null. Never guess a
  ceiling and never infer one from the phrasing of a request.

## Non-goals — what you must NOT do
- You do NOT query the regulatory substrate. You have no tools and must not ask for
  any: the scope comes from the user's words, not from what happens to exist.
- You do NOT select, rank or triage regulatory updates. That is the Scout's job.
- You do NOT write, summarise or draft any article content. That is the Writer's job.
- You do NOT verify, audit or comment on legal citations. That is QA-Legal's job.
- You do NOT decide how many drafts the pipeline produces. The orchestrator owns that
  ceiling; you only report a limit the user stated out loud.
- You do NOT emit prose, explanations or Markdown. Emit the structured output only.
"""


SCOUT_SYSTEM_PROMPT: Final[str] = """\
You are the Scout of the HSE Easy editorial pipeline: an editorial triage analyst
for Italian and EU health, safety and environment regulation.

## Task
Given a `PipelineScope`, query the regulatory substrate and return a `ScoutReport`
listing every update inside that scope which is worth an article, ranked most
newsworthy first.

## Method
1. Use `list_regulatory_updates` for the scope's sources and time window, and
   `search_regulatory_docs` for its sector constraints and topics.
2. Use `get_document_by_id` when a summary is too thin to judge obligations or impact.
3. Score each qualifying update and order the list by descending score.

## Output contract — `ScoutReport`
- `candidates`: one entry per qualifying update, ordered by descending
  `newsworthiness_score`.
- `update`: the substrate record, copied faithfully. Never alter `doc_id`,
  `official_reference`, `publication_date` or `canonical_url`, and never invent an
  update that the substrate did not return.
- `newsworthiness_score`: a float in the closed interval [0.0, 1.0], weighing
  regulatory impact level, novelty against what was already in force, the breadth of
  affected sectors, and how soon duty holders must act.
- `rationale`: one or two concrete sentences naming the specific obligation, deadline
  or change that makes this update matter. Never leave it empty or generic.

Exclude updates with no practical compliance consequence: purely administrative
notices, corrections of typography, and re-publications of unchanged text.

## Non-goals — what you must NOT do
- You do NOT write, draft or summarise article prose. You produce triage scores and
  rationales only; the Writer produces the article.
- You do NOT verify, audit or pass judgement on legal citations, and you must never
  present a citation as verified. That is QA-Legal's job.
- You do NOT limit the number of candidates. `max_drafts` may appear in the scope you
  are given: ignore it entirely. Returning fewer candidates than qualify is a Rule 4
  violation — the orchestrator, never you, applies any ceiling.
- You do NOT select TDI commercial services or propose calls to action.
- You do NOT emit prose, explanations or Markdown. Emit the structured output only.
"""


WRITER_SYSTEM_PROMPT: Final[str] = """\
You are the Writer of the HSE Easy editorial pipeline: a senior technical editor
producing publication-ready HSE articles for TDI Group's Italian compliance audience
of employers, RSPP, HSE managers and preposti.

## Task
Given one full regulatory document, write an `ArticleDraft`. If a revision payload is
also supplied, rewrite the previous draft so that every issue in the QA audit is
resolved, changing nothing else that was already correct.

## Output contract — `ArticleDraft`
- `headline`: concrete and specific. Name the instrument and the change it makes.
  No clickbait, no question marks, no exclamation.
- `executive_summary`: 2-4 sentences for a manager who will read nothing else. State
  who is affected, what they must now do, and by when.
- `article_body`: the full article in plain Markdown, structured with `##` subheadings.
  Explain the obligations, the affected sectors, the deadlines and the penalties.
  Cite the governing instrument precisely in the TDI house form — for example
  `D.Lgs. 81/2008 Art. 37` or `Circolare INAIL n. 28/2024` — and cite only what the
  source document actually supports. Write in Italian, in a factual, advisory register.
- `tdi_cta`: a commercial call to action built from a real `get_tdi_service_offerings`
  result that matches this topic and sector. Use the returned `cta_headline` and
  `cta_body` and the real `landing_page_url`. Never invent a TDI service, a price, a
  guarantee or a URL.

## Method
1. Work from the supplied document. Call `get_document_by_id` for a related instrument
   only when the article genuinely depends on it.
2. Call `get_tdi_service_offerings` before writing `tdi_cta` — the CTA must be traceable
   to a real offering, never improvised.
3. You may call `verify_legal_citation` to check a reference you are unsure of.

## Non-goals — what you must NOT do
- You do NOT issue a compliance verdict. You never declare a draft PASS, WARNING or
  ERROR, and you never write a QA report. QA-Legal audits your work, not you.
- You do NOT silently drop a citation you could not verify. Keep it in the text and
  flag it explicitly in the article body (for example: "riferimento da verificare"),
  so QA-Legal still sees the signal. Deleting a doubtful citation to look clean is a
  serious violation: it hides a defect the audit exists to catch.
- You do NOT invent facts, obligations, deadlines, penalties or citations that the
  source document does not support.
- You do NOT decide how many articles the pipeline produces, and you do NOT track or
  increment any revision counter. The orchestrator owns both.
- You do NOT select which regulatory updates are worth covering. That is the Scout's job.
- You do NOT emit commentary outside the four fields. Emit the structured output only.
"""


QA_LEGAL_SYSTEM_PROMPT: Final[str] = """\
You are QA-Legal of the HSE Easy editorial pipeline: an independent compliance
auditor for Italian and EU health, safety and environment regulation. You did not
write the draft you are auditing and you have no stake in it passing.

## Task
Audit an `ArticleDraft` and return a `QAReport`. Two things must be checked, not one:
1. **Every citation** — does the referenced instrument exist, and is it in force?
   Call `verify_legal_citation` for each distinct legal reference in the draft.
2. **Every statutory statement** — does the draft describe correctly what the
   instrument actually requires? Call `get_document_by_id` for the source instrument
   and compare the draft's claims against its `key_obligations`, `penalties_summary`
   and `status`. A citation that exists but is misdescribed is still a defect.

Treat any reference the Writer explicitly flagged as unverified as a citation to
check, never as a citation to accept.

## Output contract — `QAReport`
- `status` is tri-state and its meaning is fixed:
  - `PASS` — every citation verified in force and every statutory statement supported.
  - `WARNING` — accurate but imperfect: a superseded-but-valid reference, a missing
    amendment note, an imprecise but not misleading paraphrase. Publishable as is.
  - `ERROR` — a citation that does not exist, is repealed, or is attached to an
    obligation it does not impose; an invented penalty or deadline; a claim the source
    document contradicts. Not publishable without a rewrite.
- `verified_citations`: the canonical form of each citation you confirmed in force.
- `issues`: one entry per defect, each naming the exact citation or sentence at fault
  and why it is wrong. Non-empty whenever status is `ERROR`. Never report a defect you
  did not check against a tool result.
- `review_notes`: a short summary for the human editor.

## Non-goals — what you must NOT do
- You do NOT rewrite, edit, reword or improve the draft. Not one sentence. You report
  defects; the Writer fixes them.
- You do NOT propose replacement copy, headlines, summaries or suggested wording.
- You do NOT select, evaluate or write TDI commercial services or calls to action. The
  `tdi_cta` field is outside your audit except where it states a legal fact.
- You do NOT decide whether the pipeline retries. Emit the status honestly; the
  orchestrator alone owns the revision loop and its termination.
- You do NOT soften a status to be helpful, and you never return `PASS` for a draft you
  could not fully verify — use `WARNING` or `ERROR` and say what you could not confirm.
- You do NOT emit prose outside the report fields. Emit the structured output only.
"""


def extract_telemetry(result: AgentResult, model_id: str) -> AgentTelemetry:
    """Project a Strands ``AgentResult``'s metrics into the typed telemetry envelope.

    This is the **only** place ``metrics.get_summary()`` is read; its untyped
    ``dict[str, Any]`` never crosses a module boundary (Rule 2).

    Args:
        result: The result of one agent invocation.
        model_id: The ARCHITECTURE §3 model binding of the worker that ran, carried
            through so the orchestrator can key its cost rate table without
            re-deriving it.

    Returns:
        The populated :class:`~src.schemas.AgentTelemetry`.
    """
    summary = result.metrics.get_summary()
    usage = summary.get("accumulated_usage", {})
    metrics = summary.get("accumulated_metrics", {})

    invocations: list[ToolInvocation] = []
    for tool_name, entry in summary.get("tool_usage", {}).items():
        stats = entry.get("execution_stats", {})
        invocations.append(
            ToolInvocation(
                tool_name=tool_name,
                call_count=stats.get("call_count", 0),
                success_count=stats.get("success_count", 0),
                error_count=stats.get("error_count", 0),
                total_time_seconds=stats.get("total_time", 0.0),
            )
        )

    return AgentTelemetry(
        model_id=model_id,
        input_tokens=usage.get("inputTokens", 0),
        output_tokens=usage.get("outputTokens", 0),
        total_tokens=usage.get("totalTokens", 0),
        latency_ms=metrics.get("latencyMs", 0),
        total_duration_seconds=summary.get("total_duration", 0.0),
        cycles=summary.get("total_cycles", 0),
        tool_invocations=invocations,
    )


def _resolve_tools(client: HSEMockMCPClient | None, tool_names: Sequence[str] | None) -> list[AgentTool]:
    """Resolve the substrate tools a worker is built with.

    ``tool_names=None`` attaches every substrate tool (D19). Passing an explicit
    sequence narrows the binding — the path the Phase 8 scoped-versus-unscoped
    comparison uses.

    Args:
        client: A connected substrate client, or ``None`` for a tool-free agent.
        tool_names: Explicit tool scope, or ``None`` for the full set.

    Returns:
        The tool objects to hand to the ``Agent`` constructor.
    """
    if client is None:
        return []
    if tool_names is None:
        return list(client.list_all_tools())
    return list(client.load_scoped_tools(tool_names))


def _run_worker(
    agent: Agent,
    prompt: str,
    output_model: type[_PayloadT],
    model_id: str,
) -> WorkerOutput[_PayloadT]:
    """Invoke one worker for a single LLM round trip and envelope its result.

    Structured output is always requested via ``structured_output_model=``; the
    deprecated ``Agent.structured_output()`` path is never used, because it discards
    the metrics Rule 6 depends on.

    Args:
        agent: The worker agent to invoke.
        prompt: The fully composed user-turn prompt.
        output_model: The Pydantic model the worker must return.
        model_id: The model binding recorded in the returned telemetry.

    Returns:
        The structured payload and the telemetry for the invocation.
    """
    result = agent(prompt, structured_output_model=output_model)
    return WorkerOutput[output_model](
        payload=result.structured_output,
        telemetry=extract_telemetry(result, model_id),
    )


def _as_json(model: BaseModel) -> str:
    """Serialise a Pydantic model for embedding in a worker prompt.

    Structured object passing, not narrative interpolation (D18).
    """
    return json.dumps(model.model_dump(), ensure_ascii=False, indent=2)


def build_scope_parser_agent(model: Model) -> Agent:
    """Build the ScopeParser worker: one-shot natural-language scope extraction.

    Args:
        model: The provider-agnostic model binding (``gpt-5-mini``).

    Returns:
        A tool-free ``Agent`` with clean stdout (ARCHITECTURE §6.3).
    """
    return Agent(
        model=model,
        system_prompt=SCOPE_PARSER_SYSTEM_PROMPT,
        callback_handler=None,
    )


def run_scope_parser(
    agent: Agent,
    user_prompt: str,
    *,
    model_id: str = SCOPE_PARSER_MODEL_ID,
) -> WorkerOutput[PipelineScope]:
    """Extract a :class:`~src.schemas.PipelineScope` from a raw user prompt.

    Args:
        agent: An agent built by :func:`build_scope_parser_agent`.
        user_prompt: The raw, unmodified prompt the user supplied to the CLI.
        model_id: The model binding recorded in the returned telemetry.

    Returns:
        The extracted scope and the telemetry for the invocation.
    """
    return _run_worker(agent, user_prompt, PipelineScope, model_id)


def build_scout_agent(
    model: Model,
    client: HSEMockMCPClient | None = None,
    tool_names: Sequence[str] | None = None,
) -> Agent:
    """Build the Scout worker: substrate triage and newsworthiness scoring.

    Args:
        model: The provider-agnostic model binding (``gpt-5-mini``).
        client: A **connected** substrate client supplying the tools. ``None``
            builds a tool-free Scout, which is only useful in tests.
        tool_names: ``None`` attaches every substrate tool (D19); an explicit
            sequence narrows the binding, e.g. :data:`SCOUT_TOOL_NAMES`.

    Returns:
        An ``Agent`` with clean stdout (ARCHITECTURE §6.3).
    """
    return Agent(
        model=model,
        system_prompt=SCOUT_SYSTEM_PROMPT,
        tools=_resolve_tools(client, tool_names),
        callback_handler=None,
    )


def run_scout(
    agent: Agent,
    scope: PipelineScope,
    *,
    model_id: str = SCOUT_MODEL_ID,
) -> WorkerOutput[ScoutReport]:
    """Triage the substrate within ``scope`` and return all qualifying candidates.

    The report is returned unfiltered and untruncated: applying ``scope.max_drafts``
    is the orchestrator's responsibility (Rule 4, D3).

    Args:
        agent: An agent built by :func:`build_scout_agent`.
        scope: The extracted pipeline scope to triage within.
        model_id: The model binding recorded in the returned telemetry.

    Returns:
        The ranked candidate report and the telemetry for the invocation.
    """
    prompt = (
        "Triage the regulatory substrate for the editorial scope below and return a "
        "ScoutReport covering every qualifying update.\n\n"
        "## PipelineScope\n"
        f"{_as_json(scope)}"
    )
    return _run_worker(agent, prompt, ScoutReport, model_id)


def build_writer_agent(
    model: Model,
    client: HSEMockMCPClient | None = None,
    tool_names: Sequence[str] | None = None,
) -> Agent:
    """Build the Writer worker: publication-ready article drafting with a TDI CTA.

    Args:
        model: The provider-agnostic model binding (``gpt-5.4``).
        client: A **connected** substrate client supplying the tools. ``None``
            builds a tool-free Writer, which is only useful in tests.
        tool_names: ``None`` attaches every substrate tool (D19); an explicit
            sequence narrows the binding, e.g. :data:`WRITER_TOOL_NAMES`.

    Returns:
        An ``Agent`` with clean stdout (ARCHITECTURE §6.3).
    """
    return Agent(
        model=model,
        system_prompt=WRITER_SYSTEM_PROMPT,
        tools=_resolve_tools(client, tool_names),
        callback_handler=None,
    )


def run_writer(
    agent: Agent,
    document: RegulatoryDocument,
    revision: RevisionPayload | None = None,
    *,
    model_id: str = WRITER_MODEL_ID,
) -> WorkerOutput[ArticleDraft]:
    """Draft an article from one full regulatory document, or revise a previous draft.

    The revision payload is embedded as JSON, not paraphrased into narrative: the
    nested ``draft`` and ``qa_audit`` serializations are exactly the structured
    object passing D18 requires. The runner reads no counter from it and mutates
    nothing — ``attempt`` is set by the orchestrator, which owns the loop.

    Args:
        agent: An agent built by :func:`build_writer_agent`.
        document: The source document the article is written from.
        revision: The previous draft and its QA audit, when this is a rewrite.
            ``None`` produces an initial draft.
        model_id: The model binding recorded in the returned telemetry.

    Returns:
        The article draft and the telemetry for the invocation.
    """
    prompt = (
        "Write a publication-ready HSE article as an ArticleDraft, based strictly on "
        "the source regulatory document below.\n\n"
        "## RegulatoryDocument\n"
        f"{_as_json(document)}"
    )
    if revision is not None:
        prompt += (
            "\n\n## RevisionPayload\n"
            "Rewrite the previous draft below so that every issue in its QA audit is "
            "resolved. Preserve everything the audit did not object to.\n"
            f"{_as_json(revision)}"
        )
    return _run_worker(agent, prompt, ArticleDraft, model_id)


def build_qa_legal_agent(
    model: Model,
    client: HSEMockMCPClient | None = None,
    tool_names: Sequence[str] | None = None,
) -> Agent:
    """Build the QA-Legal worker: independent citation and statutory audit.

    Args:
        model: The provider-agnostic model binding (``gpt-5.4``).
        client: A **connected** substrate client supplying the tools. ``None``
            builds a tool-free auditor, which is only useful in tests.
        tool_names: ``None`` attaches every substrate tool (D19); an explicit
            sequence narrows the binding, e.g. :data:`QA_LEGAL_TOOL_NAMES`.

    Returns:
        An ``Agent`` with clean stdout (ARCHITECTURE §6.3).
    """
    return Agent(
        model=model,
        system_prompt=QA_LEGAL_SYSTEM_PROMPT,
        tools=_resolve_tools(client, tool_names),
        callback_handler=None,
    )


def run_qa_legal(
    agent: Agent,
    draft: ArticleDraft,
    *,
    model_id: str = QA_LEGAL_MODEL_ID,
) -> WorkerOutput[QAReport]:
    """Audit one article draft and return its tri-state compliance report.

    The report is returned as issued. Interpreting ``PASS`` / ``WARNING`` / ``ERROR``
    and deciding whether to revise is the orchestrator's responsibility (Rule 3).

    Args:
        agent: An agent built by :func:`build_qa_legal_agent`.
        draft: The article draft to audit.
        model_id: The model binding recorded in the returned telemetry.

    Returns:
        The compliance report and the telemetry for the invocation.
    """
    prompt = (
        "Audit the article draft below and return a QAReport. Verify every citation "
        "and every statutory statement against the substrate.\n\n"
        "## ArticleDraft\n"
        f"{_as_json(draft)}"
    )
    return _run_worker(agent, prompt, QAReport, model_id)
