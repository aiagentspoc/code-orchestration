"""Unit tests for the four Strands Agent workers (Phase 5).

Every test in this module is offline (D16): no network call, no subprocess and
no real credentials. LLM behaviour is supplied by :class:`ScriptedModel`, a
``strands.models.model.Model`` subclass that replays pre-recorded stream events
through the **real** Strands event loop, and substrate tools are supplied by
:class:`StubSubstrateClient`, which mirrors the ``HSEMockMCPClient`` surface
that the agent factories consume.
"""

import ast
import copy
import inspect
import json
from collections.abc import AsyncIterator, Sequence
from pathlib import Path
from typing import Any

import pytest
from pydantic import ValidationError
from strands import Agent, tool
from strands.handlers import null_callback_handler
from strands.models.model import Model
from strands.types.exceptions import StructuredOutputException
from strands.types.tools import AgentTool

from src import agents as agents_module
from src.agents import (
    QA_LEGAL_MODEL_ID,
    QA_LEGAL_SYSTEM_PROMPT,
    QA_LEGAL_TOOL_NAMES,
    SCOPE_PARSER_MODEL_ID,
    SCOPE_PARSER_SYSTEM_PROMPT,
    SCOUT_MODEL_ID,
    SCOUT_SYSTEM_PROMPT,
    SCOUT_TOOL_NAMES,
    WRITER_MODEL_ID,
    WRITER_SYSTEM_PROMPT,
    WRITER_TOOL_NAMES,
    build_qa_legal_agent,
    build_scope_parser_agent,
    build_scout_agent,
    build_writer_agent,
    extract_telemetry,
    run_qa_legal,
    run_scope_parser,
    run_scout,
    run_writer,
)
from src.mcp_client import HSEMockMCPClient, MCPClientNotConnectedError
from src.schemas import (
    AgentTelemetry,
    ArticleDraft,
    PipelineScope,
    QAReport,
    RegulatoryDocument,
    RevisionPayload,
    ScoutCandidate,
    ScoutReport,
    ToolInvocation,
)

# ---------------------------------------------------------------------------
# Scripted stream-event fixtures
# ---------------------------------------------------------------------------


def _tool_use_turn(
    name: str,
    args: dict[str, Any],
    *,
    input_tokens: int = 10,
    output_tokens: int = 5,
    latency_ms: int = 100,
) -> list[dict[str, Any]]:
    """Build one model turn that invokes ``name`` with ``args``.

    The structured-output tool is named after the Pydantic model class, so a
    turn naming ``PipelineScope`` produces structured output while a turn
    naming ``list_regulatory_updates`` produces a real substrate tool call.
    """
    return [
        {"messageStart": {"role": "assistant"}},
        {"contentBlockStart": {"start": {"toolUse": {"name": name, "toolUseId": f"{name}-1"}}}},
        {"contentBlockDelta": {"delta": {"toolUse": {"input": json.dumps(args)}}}},
        {"contentBlockStop": {}},
        {"messageStop": {"stopReason": "tool_use"}},
        {
            "metadata": {
                "usage": {
                    "inputTokens": input_tokens,
                    "outputTokens": output_tokens,
                    "totalTokens": input_tokens + output_tokens,
                },
                "metrics": {"latencyMs": latency_ms},
            }
        },
    ]


def _text_turn(
    text: str,
    *,
    input_tokens: int = 3,
    output_tokens: int = 2,
    latency_ms: int = 50,
) -> list[dict[str, Any]]:
    """Build one model turn that emits plain text and stops."""
    return [
        {"messageStart": {"role": "assistant"}},
        {"contentBlockStart": {"start": {}}},
        {"contentBlockDelta": {"delta": {"text": text}}},
        {"contentBlockStop": {}},
        {"messageStop": {"stopReason": "end_turn"}},
        {
            "metadata": {
                "usage": {
                    "inputTokens": input_tokens,
                    "outputTokens": output_tokens,
                    "totalTokens": input_tokens + output_tokens,
                },
                "metrics": {"latencyMs": latency_ms},
            }
        },
    ]


class ScriptedModel(Model):
    """Deterministic offline ``Model`` replaying pre-scripted stream events.

    Turns are consumed in order. Exhausting the script raises rather than
    repeating the last turn, so an unexpected extra model round trip fails
    loudly instead of recursing.
    """

    def __init__(self, turns: Sequence[Sequence[dict[str, Any]]]) -> None:
        self._turns: list[list[dict[str, Any]]] = [list(turn) for turn in turns]
        self._index: int = 0
        self.received_messages: list[list[dict[str, Any]]] = []
        self.received_tool_specs: list[list[dict[str, Any]] | None] = []
        self.received_system_prompts: list[str | None] = []
        self._config: dict[str, Any] = {"model_id": "scripted-test-model"}

    @property
    def turns_consumed(self) -> int:
        """Number of model round trips the event loop has driven so far."""
        return self._index

    def update_config(self, **model_config: Any) -> None:
        """Merge configuration overrides into the scripted config."""
        self._config.update(model_config)

    def get_config(self) -> dict[str, Any]:
        """Return the scripted model configuration."""
        return self._config

    def structured_output(self, output_model: Any, prompt: Any, system_prompt: str | None = None, **kwargs: Any) -> Any:
        """Fail loudly: the deprecated direct structured-output path is forbidden."""
        raise NotImplementedError(
            "ScriptedModel does not implement the deprecated Model.structured_output path; "
            "workers must use agent(prompt, structured_output_model=...)."
        )

    async def stream(
        self,
        messages: Any,
        tool_specs: Any = None,
        system_prompt: str | None = None,
        **kwargs: Any,
    ) -> AsyncIterator[dict[str, Any]]:
        """Replay the next scripted turn, capturing what the model received."""
        self.received_messages.append(copy.deepcopy(list(messages)))
        self.received_tool_specs.append(copy.deepcopy(tool_specs))
        self.received_system_prompts.append(system_prompt)
        if self._index >= len(self._turns):
            raise AssertionError(
                f"ScriptedModel script exhausted after {self._index} turn(s); the agent requested another."
            )
        turn = self._turns[self._index]
        self._index += 1
        for event in turn:
            yield event


# ---------------------------------------------------------------------------
# Stub substrate client — mirrors the HSEMockMCPClient tool-loading surface
# ---------------------------------------------------------------------------

SUBSTRATE_TOOL_NAMES: tuple[str, ...] = (
    "list_regulatory_updates",
    "search_regulatory_docs",
    "get_document_by_id",
    "verify_legal_citation",
    "get_tdi_service_offerings",
)

_UPDATE_FIXTURE: dict[str, Any] = {
    "doc_id": "inail-2024-circ-calore",
    "source": "INAIL",
    "doc_type": "circular",
    "official_reference": "Circolare INAIL n. 28/2024",
    "title": "Circolare INAIL n. 28 del 24 luglio 2024: prevenzione delle patologie da calore",
    "publication_date": "2024-07-24",
    "effective_date": "2024-07-24",
    "impact_level": "high",
    "topic_tags": ["heat_stress", "construction_safety"],
    "summary": "Indicazioni operative per la prevenzione dello stress termico nei luoghi di lavoro all'aperto.",
    "canonical_url": "https://www.inail.it/circolare-inail-28-2024.html",
}


@tool
def list_regulatory_updates(source: str | None = None, limit: int = 10) -> str:
    """Stub substrate tool: list recent HSE regulatory updates."""
    return json.dumps([_UPDATE_FIXTURE])


@tool
def search_regulatory_docs(query: str, topic: str | None = None) -> str:
    """Stub substrate tool: keyword search over the regulatory database."""
    return json.dumps([_UPDATE_FIXTURE])


@tool
def get_document_by_id(doc_id: str) -> str:
    """Stub substrate tool: retrieve one full regulatory document."""
    return json.dumps(
        {
            **_UPDATE_FIXTURE,
            "doc_id": doc_id,
            "status": "in_force",
            "target_sectors": ["construction", "agriculture"],
            "key_obligations": [
                "Riprogrammare i turni di lavoro nelle ore piu calde",
                "Garantire aree ombreggiate e dotazioni idriche",
            ],
            "penalties_summary": "Arresto o ammenda fino a 5.000 EUR per datori di lavoro e dirigenti.",
            "related_citations": ["D.Lgs. 81/2008 Art. 28"],
            "content_markdown": "# Circolare INAIL n. 28/2024",
        }
    )


@tool
def verify_legal_citation(citation: str) -> str:
    """Stub substrate tool: verify one legal citation."""
    return json.dumps(
        {
            "citation_input": citation,
            "is_valid": True,
            "status": "in_force",
            "canonical_citation": "D.Lgs. 9 aprile 2008, n. 81, Art. 37",
            "official_reference": "D.Lgs. 9 aprile 2008, n. 81",
            "official_url": "https://www.normattiva.it/urn:nir:stato:decreto.legislativo:2008-04-09;81~art37",
            "verified_against_doc_id": "gu-2024-dl-preposti",
            "notes": "Modificato da ultimo dal D.L. 19/2024.",
        }
    )


_TDI_OFFERING_FIXTURE: dict[str, Any] = {
    "service_id": "tdi-srv-preposti-training",
    "service_name": "Corso di Formazione e Aggiornamento Preposti (D.Lgs. 81/08)",
    "topic_category": "workplace_safety",
    "applicable_sectors": ["construction", "manufacturing"],
    "value_proposition": "Percorsi formativi certificati per l'obbligo di aggiornamento biennale.",
    "cta_headline": "Adeguati ai nuovi obblighi formativi per i Preposti.",
    "cta_body": "Pianifica il piano formativo certificato con TDI.",
    "landing_page_url": "https://www.tdigroup.it/servizi/formazione-sicurezza-preposti",
}


@tool
def get_tdi_service_offerings(topic: str, sector: str | None = None) -> str:
    """Stub substrate tool: retrieve TDI consulting services and CTA templates."""
    return json.dumps([_TDI_OFFERING_FIXTURE])


_STUB_TOOLS: dict[str, AgentTool] = {
    "list_regulatory_updates": list_regulatory_updates,
    "search_regulatory_docs": search_regulatory_docs,
    "get_document_by_id": get_document_by_id,
    "verify_legal_citation": verify_legal_citation,
    "get_tdi_service_offerings": get_tdi_service_offerings,
}


class StubSubstrateClient:
    """Offline stand-in for ``HSEMockMCPClient``'s tool-loading surface."""

    def __init__(self) -> None:
        self.scope_requests: list[list[str]] = []
        self.list_all_calls: int = 0

    def list_all_tools(self) -> list[AgentTool]:
        """Return every substrate tool (the D19 default binding)."""
        self.list_all_calls += 1
        return list(_STUB_TOOLS.values())

    def load_scoped_tools(self, names: Sequence[str]) -> list[AgentTool]:
        """Return only the named substrate tools."""
        self.scope_requests.append(list(names))
        return [_STUB_TOOLS[name] for name in names]


class RecordingMCPSession:
    """Offline stand-in for ``strands.tools.mcp.MCPClient.list_tools_sync``."""

    def __init__(self) -> None:
        self.tool_filters_seen: list[dict[str, Any] | None] = []

    def list_tools_sync(self, tool_filters: dict[str, Any] | None = None, **kwargs: Any) -> list[AgentTool]:
        """Return the stub tools, honouring an ``allowed`` filter when given."""
        self.tool_filters_seen.append(tool_filters)
        allowed = (tool_filters or {}).get("allowed")
        if allowed is None:
            return list(_STUB_TOOLS.values())
        return [tool_obj for name, tool_obj in _STUB_TOOLS.items() if name in allowed]


def _offline_client(session: RecordingMCPSession) -> HSEMockMCPClient:
    """Build an ``HSEMockMCPClient`` wired to an offline session stub."""
    client = HSEMockMCPClient()
    client.mcp_client = session
    client._connected = True
    return client


_VALID_SCOPE_ARGS: dict[str, Any] = {
    "time_window": "past_3_months",
    "sources": ["INAIL"],
    "sector_constraints": ["construction"],
}


# ---------------------------------------------------------------------------
# Batch 1 — harness, scoped tool loading, telemetry contract, ScopeParser
# ---------------------------------------------------------------------------


def test_scripted_model_drives_structured_output() -> None:
    """Self-test: the offline harness drives the real event loop to a typed payload."""
    model = ScriptedModel([_tool_use_turn("PipelineScope", _VALID_SCOPE_ARGS)])
    agent = Agent(model=model, callback_handler=None, system_prompt="harness self-test")

    result = agent("extract the scope", structured_output_model=PipelineScope)

    assert isinstance(result.structured_output, PipelineScope)
    assert result.structured_output.time_window == "past_3_months"
    assert model.turns_consumed == 1
    assert model.received_system_prompts[0] == "harness self-test"
    assert "extract the scope" in json.dumps(model.received_messages[0])


def test_load_scoped_tools_returns_only_requested_names() -> None:
    """``load_scoped_tools`` narrows one shared session to the named tools."""
    session = RecordingMCPSession()
    client = _offline_client(session)

    tools = client.load_scoped_tools(["get_document_by_id", "verify_legal_citation"])

    assert [tool_obj.tool_name for tool_obj in tools] == ["get_document_by_id", "verify_legal_citation"]
    assert session.tool_filters_seen[-1] == {"allowed": ["get_document_by_id", "verify_legal_citation"]}

    all_tools = client.list_all_tools()
    assert len(all_tools) == len(SUBSTRATE_TOOL_NAMES)
    assert session.tool_filters_seen[-1] is None


def test_extract_telemetry_maps_usage_and_latency() -> None:
    """Every Rule 6 telemetry field is projected out of ``metrics.get_summary()``."""
    model = ScriptedModel(
        [_tool_use_turn("PipelineScope", _VALID_SCOPE_ARGS, input_tokens=123, output_tokens=45, latency_ms=678)]
    )
    agent = Agent(model=model, callback_handler=None)
    result = agent("prompt", structured_output_model=PipelineScope)

    telemetry = extract_telemetry(result, "gpt-5-mini")

    assert isinstance(telemetry, AgentTelemetry)
    assert telemetry.model_id == "gpt-5-mini"
    assert telemetry.input_tokens == 123
    assert telemetry.output_tokens == 45
    assert telemetry.total_tokens == 168
    assert telemetry.latency_ms == 678
    assert telemetry.cycles == 1
    # Pinned to the SDK's own value, not to ``>= 0.0``: the field defaults to 0.0, so a
    # lower-bound assertion cannot distinguish a correct key mapping from a typo'd one.
    assert telemetry.total_duration_seconds == pytest.approx(result.metrics.get_summary()["total_duration"])

    # ``EventLoopMetrics`` times its cycles with ``time.time()``, whose Windows
    # resolution leaves a scripted sub-millisecond cycle at exactly 0.0 — the same
    # value as the field default, so the equality above is real but not yet decisive.
    # Record a known duration on the real metrics object and re-project: only a
    # correct ``total_duration`` mapping can report it back.
    baseline = result.metrics.get_summary()["total_duration"]
    result.metrics.cycle_durations.append(0.25)

    assert extract_telemetry(result, "gpt-5-mini").total_duration_seconds == pytest.approx(baseline + 0.25)


def test_extract_telemetry_captures_tool_invocations() -> None:
    """Per-tool execution stats become typed ``ToolInvocation`` entries."""
    model = ScriptedModel(
        [
            _tool_use_turn("list_regulatory_updates", {"source": "INAIL", "limit": 5}),
            _tool_use_turn("PipelineScope", _VALID_SCOPE_ARGS),
        ]
    )
    agent = Agent(model=model, callback_handler=None, tools=[list_regulatory_updates])
    result = agent("prompt", structured_output_model=PipelineScope)

    telemetry = extract_telemetry(result, "gpt-5-mini")

    by_name = {invocation.tool_name: invocation for invocation in telemetry.tool_invocations}
    assert "list_regulatory_updates" in by_name
    invocation = by_name["list_regulatory_updates"]
    assert isinstance(invocation, ToolInvocation)
    assert invocation.call_count == 1
    assert invocation.success_count == 1
    assert invocation.error_count == 0
    # Pin to the real execution_stats value rather than to ``>= 0.0``, which the 0.0
    # field default satisfies unconditionally.
    stats = result.metrics.get_summary()["tool_usage"]["list_regulatory_updates"]["execution_stats"]
    assert invocation.total_time_seconds == pytest.approx(stats["total_time"])

    # A scripted tool call also completes inside one ``time.time()`` tick, so record a
    # known duration on the real ``ToolMetrics`` and re-project to make the mapping
    # decisive rather than merely 0.0 == 0.0.
    result.metrics.tool_metrics["list_regulatory_updates"].total_time += 0.5
    reprojected = {
        invocation.tool_name: invocation
        for invocation in extract_telemetry(result, "gpt-5-mini").tool_invocations
    }

    assert reprojected["list_regulatory_updates"].total_time_seconds == pytest.approx(stats["total_time"] + 0.5)


def test_agent_telemetry_rejects_extra_and_defaults_to_zero() -> None:
    """``AgentTelemetry`` ignores unknown keys and defaults every counter to zero."""
    telemetry = AgentTelemetry(model_id="gpt-5-mini", unexpected_upstream_field="ignored")

    assert telemetry.model_id == "gpt-5-mini"
    assert telemetry.input_tokens == 0
    assert telemetry.output_tokens == 0
    assert telemetry.total_tokens == 0
    assert telemetry.latency_ms == 0
    assert telemetry.total_duration_seconds == 0.0
    assert telemetry.cycles == 0
    assert telemetry.tool_invocations == []
    assert not hasattr(telemetry, "unexpected_upstream_field")


def test_scope_parser_agent_has_no_tools() -> None:
    """The ScopeParser is a pure extractor: no substrate tools, clean stdout."""
    agent = build_scope_parser_agent(ScriptedModel([]))

    assert agent.tool_names == []
    assert agent.system_prompt == SCOPE_PARSER_SYSTEM_PROMPT
    assert agent.callback_handler is null_callback_handler


def test_scope_parser_extracts_pipeline_scope_unconstrained_max_drafts() -> None:
    """An unconstrained prompt yields ``max_drafts=None`` (Rule 4)."""
    model = ScriptedModel([_tool_use_turn("PipelineScope", _VALID_SCOPE_ARGS)])
    agent = build_scope_parser_agent(model)

    output = run_scope_parser(agent, "Analyze recent INAIL updates on heat stress in construction")

    assert isinstance(output.payload, PipelineScope)
    assert output.payload.time_window == "past_3_months"
    assert output.payload.sources == ["INAIL"]
    assert output.payload.sector_constraints == ["construction"]
    assert output.payload.max_drafts is None
    assert "Analyze recent INAIL updates on heat stress" in json.dumps(model.received_messages[0])


def test_scope_parser_returns_telemetry_with_model_id() -> None:
    """The runner stamps its ARCHITECTURE §3 model ID onto the telemetry."""
    model = ScriptedModel(
        [_tool_use_turn("PipelineScope", _VALID_SCOPE_ARGS, input_tokens=20, output_tokens=7, latency_ms=321)]
    )
    agent = build_scope_parser_agent(model)

    output = run_scope_parser(agent, "Analyze recent INAIL updates")

    assert output.telemetry.model_id == SCOPE_PARSER_MODEL_ID == "gpt-5-mini"
    assert output.telemetry.total_tokens == 27
    assert output.telemetry.latency_ms == 321


def test_scope_parser_invalid_output_raises() -> None:
    """A payload missing the required ``time_window`` never surfaces as a valid scope."""
    model = ScriptedModel(
        [
            _tool_use_turn("PipelineScope", {"sources": ["INAIL"]}),
            _text_turn("I could not comply."),
            _text_turn("Still unable to comply."),
        ]
    )
    agent = build_scope_parser_agent(model)

    with pytest.raises((StructuredOutputException, ValidationError)):
        run_scope_parser(agent, "Analyze recent INAIL updates")


def test_scope_parser_prompt_declares_output_model() -> None:
    """The prompt names its structured output model and the required fields."""
    assert "PipelineScope" in SCOPE_PARSER_SYSTEM_PROMPT
    assert "time_window" in SCOPE_PARSER_SYSTEM_PROMPT
    assert "max_drafts" in SCOPE_PARSER_SYSTEM_PROMPT


# ---------------------------------------------------------------------------
# Batch 2 — Scout (substrate triage and newsworthiness scoring)
# ---------------------------------------------------------------------------


def _candidate_args(doc_id: str, score: float, rationale: str) -> dict[str, Any]:
    """Build one scripted ``ScoutCandidate`` payload."""
    return {
        "update": {**_UPDATE_FIXTURE, "doc_id": doc_id},
        "newsworthiness_score": score,
        "rationale": rationale,
    }


_SCOUT_SCOPE = PipelineScope(time_window="past_3_months", sources=["INAIL"], sector_constraints=["construction"])


def test_scout_candidate_score_bounds() -> None:
    """``newsworthiness_score`` is constrained to the closed interval [0.0, 1.0]."""
    candidate = ScoutCandidate.model_validate(_candidate_args("inail-1", 0.87, "High impact heat-stress circular"))
    assert candidate.newsworthiness_score == 0.87
    assert candidate.update.doc_id == "inail-1"

    with pytest.raises(ValidationError):
        ScoutCandidate.model_validate(_candidate_args("inail-1", 1.5, "Out of range"))
    with pytest.raises(ValidationError):
        ScoutCandidate.model_validate(_candidate_args("inail-1", -0.1, "Out of range"))


def test_scout_agent_receives_all_tools() -> None:
    """D19: the Scout is built with every substrate tool by default."""
    client = StubSubstrateClient()
    agent = build_scout_agent(ScriptedModel([]), client)

    assert len(agent.tool_names) == 5
    assert set(agent.tool_names) == set(SUBSTRATE_TOOL_NAMES)
    assert client.list_all_calls == 1
    assert client.scope_requests == []
    assert agent.callback_handler is null_callback_handler
    assert agent.system_prompt == SCOUT_SYSTEM_PROMPT


def test_scout_agent_accepts_explicit_tool_scope() -> None:
    """An explicit ``tool_names`` narrows the binding — the Phase 8 comparison path."""
    client = StubSubstrateClient()
    agent = build_scout_agent(ScriptedModel([]), client, tool_names=SCOUT_TOOL_NAMES)

    assert set(agent.tool_names) == set(SCOUT_TOOL_NAMES)
    assert len(SCOUT_TOOL_NAMES) == 3
    assert client.scope_requests == [list(SCOUT_TOOL_NAMES)]
    assert client.list_all_calls == 0


def test_scout_returns_ranked_scout_report() -> None:
    """The Scout returns a typed ``ScoutReport`` and receives the scope verbatim."""
    model = ScriptedModel(
        [
            _tool_use_turn(
                "ScoutReport",
                {
                    "candidates": [
                        _candidate_args("inail-2024-circ-calore", 0.92, "Critical heat-stress obligations"),
                        _candidate_args("gu-2024-dl-preposti", 0.71, "New biennial training duty"),
                    ]
                },
            )
        ]
    )
    agent = build_scout_agent(model, StubSubstrateClient())

    output = run_scout(agent, _SCOUT_SCOPE)

    assert isinstance(output.payload, ScoutReport)
    assert [candidate.update.doc_id for candidate in output.payload.candidates] == [
        "inail-2024-circ-calore",
        "gu-2024-dl-preposti",
    ]
    assert output.telemetry.model_id == SCOUT_MODEL_ID == "gpt-5-mini"

    sent = json.dumps(model.received_messages[0])
    assert "past_3_months" in sent
    assert "INAIL" in sent
    assert "construction" in sent


def test_scout_applies_newsworthiness_scoring() -> None:
    """Scores stay within bounds, rank descending, and carry a non-empty rationale."""
    model = ScriptedModel(
        [
            _tool_use_turn(
                "ScoutReport",
                {
                    "candidates": [
                        _candidate_args("doc-a", 0.95, "Critical impact, immediate compliance deadline"),
                        _candidate_args("doc-b", 0.6, "Moderate impact on construction sector"),
                        _candidate_args("doc-c", 0.4, "Background guidance, limited novelty"),
                    ]
                },
            )
        ]
    )
    agent = build_scout_agent(model, StubSubstrateClient())

    candidates = run_scout(agent, _SCOUT_SCOPE).payload.candidates

    # Guard the iteration: without this every assertion below is vacuously true for
    # an empty list, and the test passes against a Scout that returns nothing.
    assert len(candidates) == 3
    assert [candidate.update.doc_id for candidate in candidates] == ["doc-a", "doc-b", "doc-c"]

    scores = [candidate.newsworthiness_score for candidate in candidates]
    assert all(0.0 <= score <= 1.0 for score in scores)
    assert scores == sorted(scores, reverse=True)
    assert all(candidate.rationale.strip() for candidate in candidates)


def test_scout_does_not_truncate_to_max_drafts() -> None:
    """Rule 4 guard: the ``max_drafts`` ceiling belongs to the orchestrator, not the Scout."""
    model = ScriptedModel(
        [
            _tool_use_turn(
                "ScoutReport",
                {
                    "candidates": [
                        _candidate_args("doc-a", 0.9, "Qualifying"),
                        _candidate_args("doc-b", 0.8, "Qualifying"),
                        _candidate_args("doc-c", 0.7, "Qualifying"),
                    ]
                },
            )
        ]
    )
    agent = build_scout_agent(model, StubSubstrateClient())
    constrained_scope = PipelineScope(time_window="past_3_months", max_drafts=1)

    output = run_scout(agent, constrained_scope)

    assert len(output.payload.candidates) == 3


def test_scout_invokes_regulatory_tools() -> None:
    """Substrate tool use is visible in telemetry, which is how role bleed is detected."""
    model = ScriptedModel(
        [
            _tool_use_turn("list_regulatory_updates", {"source": "INAIL", "limit": 10}),
            _tool_use_turn("ScoutReport", {"candidates": [_candidate_args("doc-a", 0.9, "Qualifying")]}),
        ]
    )
    agent = build_scout_agent(model, StubSubstrateClient())

    telemetry = run_scout(agent, _SCOUT_SCOPE).telemetry

    by_name = {invocation.tool_name: invocation for invocation in telemetry.tool_invocations}
    assert "list_regulatory_updates" in by_name
    assert by_name["list_regulatory_updates"].call_count >= 1
    assert by_name["list_regulatory_updates"].error_count == 0


def test_scout_prompt_declares_role_boundary() -> None:
    """The Scout prompt names its output model and states its explicit non-goals (D19)."""
    prompt = SCOUT_SYSTEM_PROMPT
    lowered = prompt.lower()

    assert "ScoutReport" in prompt
    assert "newsworthiness_score" in prompt
    assert "non-goals" in lowered
    # Does not draft.
    assert "do not write" in lowered or "do not draft" in lowered
    # Does not audit citations.
    assert "citation" in lowered
    # Does not limit candidate count.
    assert "max_drafts" in prompt
    assert "never" in lowered


# ---------------------------------------------------------------------------
# Batch 3 — Writer (initial draft)
# ---------------------------------------------------------------------------

_DOCUMENT = RegulatoryDocument.model_validate(
    {
        **_UPDATE_FIXTURE,
        "status": "in_force",
        "target_sectors": ["construction", "agriculture"],
        "key_obligations": [
            "Riprogrammare i turni di lavoro nelle ore piu calde",
            "Garantire aree ombreggiate e dotazioni idriche",
        ],
        "penalties_summary": "Arresto o ammenda fino a 5.000 EUR per datori di lavoro e dirigenti.",
        "related_citations": ["D.Lgs. 81/2008 Art. 28"],
        "content_markdown": "# Circolare INAIL n. 28/2024",
    }
)

_DRAFT_ARGS: dict[str, Any] = {
    "headline": "Stress termico nei cantieri: cosa cambia con la Circolare INAIL 28/2024",
    "executive_summary": "La circolare impone la riprogrammazione dei turni e dotazioni idriche obbligatorie.",
    "article_body": "## Obblighi operativi\nIl datore di lavoro deve riprogrammare i turni (D.Lgs. 81/2008 Art. 28).",
    "tdi_cta": "Adeguati ai nuovi obblighi formativi per i Preposti. Pianifica il piano formativo con TDI.",
}


def test_writer_agent_receives_all_tools() -> None:
    """D19: the Writer is built with every substrate tool by default."""
    client = StubSubstrateClient()
    agent = build_writer_agent(ScriptedModel([]), client)

    assert len(agent.tool_names) == 5
    assert set(agent.tool_names) == set(SUBSTRATE_TOOL_NAMES)
    assert agent.callback_handler is null_callback_handler
    assert agent.system_prompt == WRITER_SYSTEM_PROMPT

    scoped = build_writer_agent(ScriptedModel([]), StubSubstrateClient(), tool_names=WRITER_TOOL_NAMES)
    assert set(scoped.tool_names) == set(WRITER_TOOL_NAMES)
    assert len(WRITER_TOOL_NAMES) == 2


def test_writer_generates_article_draft() -> None:
    """The Writer returns a fully populated ``ArticleDraft`` for the source document."""
    model = ScriptedModel([_tool_use_turn("ArticleDraft", _DRAFT_ARGS)])
    agent = build_writer_agent(model, StubSubstrateClient())

    output = run_writer(agent, _DOCUMENT)

    draft = output.payload
    assert isinstance(draft, ArticleDraft)
    assert draft.headline.strip()
    assert draft.executive_summary.strip()
    assert draft.article_body.strip()
    assert draft.tdi_cta.strip()

    sent = json.dumps(model.received_messages[0])
    assert "Circolare INAIL n. 28/2024" in sent
    assert "Riprogrammare i turni di lavoro nelle ore piu calde" in sent


def test_writer_includes_tdi_cta_from_offerings() -> None:
    """The CTA is traceable to a real ``get_tdi_service_offerings`` result."""
    model = ScriptedModel(
        [
            _tool_use_turn("get_tdi_service_offerings", {"topic": "workplace_safety", "sector": "construction"}),
            _tool_use_turn("ArticleDraft", _DRAFT_ARGS),
        ]
    )
    agent = build_writer_agent(model, StubSubstrateClient())

    output = run_writer(agent, _DOCUMENT)

    assert _TDI_OFFERING_FIXTURE["cta_headline"] in output.payload.tdi_cta

    by_name = {invocation.tool_name: invocation for invocation in output.telemetry.tool_invocations}
    assert by_name["get_tdi_service_offerings"].call_count == 1
    assert by_name["get_tdi_service_offerings"].error_count == 0


def test_writer_telemetry_carries_writer_model_id() -> None:
    """The Writer is bound to the strong model per ARCHITECTURE §3."""
    model = ScriptedModel(
        [_tool_use_turn("ArticleDraft", _DRAFT_ARGS, input_tokens=900, output_tokens=600, latency_ms=4200)]
    )
    agent = build_writer_agent(model, StubSubstrateClient())

    telemetry = run_writer(agent, _DOCUMENT).telemetry

    assert telemetry.model_id == WRITER_MODEL_ID == "gpt-5.4"
    assert telemetry.total_tokens == 1500
    assert telemetry.latency_ms == 4200


def test_writer_prompt_declares_role_boundary() -> None:
    """The Writer prompt names its output model, the CTA duty, and its non-goals (D19)."""
    prompt = WRITER_SYSTEM_PROMPT
    lowered = prompt.lower()

    assert "ArticleDraft" in prompt
    assert "get_tdi_service_offerings" in prompt
    assert "tdi_cta" in prompt
    assert "non-goals" in lowered
    # Issues no compliance verdict.
    assert "verdict" in lowered
    assert "qa-legal" in lowered
    # Never silently drops an unverifiable citation: keep it and flag it.
    assert "never" in lowered
    assert "flag" in lowered
    assert "citation" in lowered


# ---------------------------------------------------------------------------
# Batch 4 — Writer revision path (D18)
# ---------------------------------------------------------------------------

_PREVIOUS_DRAFT = ArticleDraft.model_validate(_DRAFT_ARGS)

_QA_AUDIT = QAReport(
    status="ERROR",
    verified_citations=["Circolare INAIL n. 28/2024"],
    issues=[
        "La citazione 'D.Lgs. 81/2008 Art. 28' non supporta l'obbligo di turnazione descritto.",
        "Manca il riferimento alla soglia dei 35 gradi per l'attivazione della CIGO.",
    ],
    review_notes="Correggere i due rilievi mantenendo invariato il resto del testo.",
)

_REVISED_DRAFT_ARGS: dict[str, Any] = {
    **_DRAFT_ARGS,
    "headline": "Stress termico nei cantieri: obblighi operativi della Circolare INAIL 28/2024",
    "article_body": "## Obblighi operativi\nSoglia di 35 gradi per l'attivazione della CIGO.",
}


def _sent_text(model: ScriptedModel, turn: int = 0) -> str:
    """Concatenate the text the model actually received on ``turn``."""
    return "\n".join(
        block["text"]
        for message in model.received_messages[turn]
        for block in message.get("content", [])
        if isinstance(block, dict) and "text" in block
    )


def _revision(attempt: int = 2) -> RevisionPayload:
    """Build a revision payload as the orchestrator would."""
    return RevisionPayload(attempt=attempt, draft=_PREVIOUS_DRAFT, qa_audit=_QA_AUDIT)


def test_writer_accepts_revision_payload() -> None:
    """With a revision payload the Writer returns a revised ``ArticleDraft``."""
    model = ScriptedModel([_tool_use_turn("ArticleDraft", _REVISED_DRAFT_ARGS)])
    agent = build_writer_agent(model, StubSubstrateClient())

    output = run_writer(agent, _DOCUMENT, revision=_revision())

    assert isinstance(output.payload, ArticleDraft)
    assert output.payload.headline == _REVISED_DRAFT_ARGS["headline"]
    assert output.payload.headline != _PREVIOUS_DRAFT.headline
    assert "35 gradi" in output.payload.article_body
    assert output.telemetry.model_id == WRITER_MODEL_ID


def test_writer_revision_serialises_structured_payload() -> None:
    """D18: the payload is passed as structured JSON, never narrative interpolation."""
    model = ScriptedModel([_tool_use_turn("ArticleDraft", _REVISED_DRAFT_ARGS)])
    agent = build_writer_agent(model, StubSubstrateClient())

    run_writer(agent, _DOCUMENT, revision=_revision(attempt=2))

    sent = _sent_text(model)
    # The previous draft reaches the model verbatim.
    assert _PREVIOUS_DRAFT.headline in sent
    assert _PREVIOUS_DRAFT.tdi_cta in sent
    # The body is multi-line, so the serializer escapes its newlines; match per line.
    for line in _PREVIOUS_DRAFT.article_body.splitlines():
        assert line in sent
    # So does every QA issue, unparaphrased.
    for issue in _QA_AUDIT.issues:
        assert issue in sent
    assert _QA_AUDIT.review_notes in sent
    # And it arrives as a JSON object, not as prose about the object.
    assert '"action": "revise_draft"' in sent
    assert '"qa_audit"' in sent
    assert '"draft"' in sent


def test_writer_revision_does_not_manage_attempts() -> None:
    """``attempt`` comes solely from the payload; the runner neither reads nor mutates a counter."""
    signature = inspect.signature(run_writer)
    assert "attempts" not in signature.parameters
    assert "max_drafts" not in signature.parameters

    for attempt in (2, 3):
        model = ScriptedModel([_tool_use_turn("ArticleDraft", _REVISED_DRAFT_ARGS)])
        agent = build_writer_agent(model, StubSubstrateClient())
        payload = _revision(attempt=attempt)

        run_writer(agent, _DOCUMENT, revision=payload)

        assert f'"attempt": {attempt}' in _sent_text(model)
        # The runner leaves the caller's payload untouched.
        assert payload.attempt == attempt


def test_agents_module_contains_no_loop_state() -> None:
    """Source-level guard: no loop counters, no ceilings and no ``while`` in executable code.

    Not a Red-Green cycle: this is an executable architectural constraint on
    ARCHITECTURE §1 / D19 rather than TDD evidence. It passed at Red against the
    7-line stub and drove no implementation; its value is prospective — it fails
    the moment orchestrator loop state is added to this module.

    The check is over the AST rather than the raw text, because the system prompts
    must legitimately mention ``max_drafts`` in order to instruct the ScopeParser to
    extract it and the Scout to ignore it. Only executable code is inspected.
    """
    module_path = Path(__file__).resolve().parents[2] / "src" / "agents.py"
    tree = ast.parse(module_path.read_text(encoding="utf-8"))

    forbidden = {"attempts", "max_drafts"}
    offending: list[str] = []
    for node in ast.walk(tree):
        assert not isinstance(node, ast.While), "src/agents.py must contain no while loop"
        if isinstance(node, ast.Name) and node.id in forbidden:
            offending.append(node.id)
        elif isinstance(node, ast.Attribute) and node.attr in forbidden:
            offending.append(node.attr)
        elif isinstance(node, ast.arg) and node.arg in forbidden:
            offending.append(node.arg)
        elif isinstance(node, ast.keyword) and node.arg in forbidden:
            # Without this a call such as ``PipelineScope(max_drafts=1)`` slips through.
            offending.append(node.arg)
        elif isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef | ast.ClassDef) and node.name in forbidden:
            offending.append(node.name)

    assert offending == [], f"src/agents.py references orchestrator loop state: {offending}"


# ---------------------------------------------------------------------------
# Batch 5 — QA-Legal (tri-state) and the cross-cutting public-surface guards
# ---------------------------------------------------------------------------


def _qa_args(status: str, *, issues: list[str] | None = None, notes: str = "") -> dict[str, Any]:
    """Build one scripted ``QAReport`` payload."""
    return {
        "status": status,
        "verified_citations": ["D.Lgs. 81/2008 Art. 28", "Circolare INAIL n. 28/2024"],
        "issues": issues or [],
        "review_notes": notes,
    }


def test_qa_legal_agent_receives_all_tools() -> None:
    """D19: QA-Legal is built with every substrate tool by default."""
    client = StubSubstrateClient()
    agent = build_qa_legal_agent(ScriptedModel([]), client)

    assert len(agent.tool_names) == 5
    assert set(agent.tool_names) == set(SUBSTRATE_TOOL_NAMES)
    assert agent.callback_handler is null_callback_handler
    assert agent.system_prompt == QA_LEGAL_SYSTEM_PROMPT

    scoped = build_qa_legal_agent(ScriptedModel([]), StubSubstrateClient(), tool_names=QA_LEGAL_TOOL_NAMES)
    assert set(scoped.tool_names) == set(QA_LEGAL_TOOL_NAMES)
    assert QA_LEGAL_TOOL_NAMES == ("verify_legal_citation",)


def test_qa_legal_fact_checks_against_source_document() -> None:
    """D19 in practice: QA reaches ``get_document_by_id`` to check statutory statements."""
    mismatch = (
        "L'articolo attribuisce alla Circolare INAIL n. 28/2024 un obbligo di dotazione idrica "
        "non presente fra le key_obligations del documento di origine."
    )
    model = ScriptedModel(
        [
            _tool_use_turn("get_document_by_id", {"doc_id": "inail-2024-circ-calore"}),
            _tool_use_turn("QAReport", _qa_args("ERROR", issues=[mismatch])),
        ]
    )
    agent = build_qa_legal_agent(model, StubSubstrateClient())

    output = run_qa_legal(agent, _PREVIOUS_DRAFT)

    by_name = {invocation.tool_name: invocation for invocation in output.telemetry.tool_invocations}
    assert by_name["get_document_by_id"].call_count == 1
    assert by_name["get_document_by_id"].error_count == 0
    assert any("key_obligations" in issue for issue in output.payload.issues)


def test_qa_legal_produces_pass_report() -> None:
    """A clean draft yields ``PASS`` with no issues."""
    model = ScriptedModel([_tool_use_turn("QAReport", _qa_args("PASS", notes="Tutte le citazioni sono vigenti."))])
    agent = build_qa_legal_agent(model, StubSubstrateClient())

    output = run_qa_legal(agent, _PREVIOUS_DRAFT)

    assert isinstance(output.payload, QAReport)
    assert output.payload.status == "PASS"
    assert output.payload.issues == []
    assert output.payload.verified_citations
    assert output.telemetry.model_id == QA_LEGAL_MODEL_ID == "gpt-5.4"

    # The draft reaches the auditor as JSON, so its body arrives line by line
    # with newlines escaped by the serializer.
    sent = _sent_text(model)
    assert _PREVIOUS_DRAFT.headline in sent
    for line in _PREVIOUS_DRAFT.article_body.splitlines():
        assert line in sent


def test_qa_legal_produces_warning_report() -> None:
    """A non-blocking defect yields ``WARNING``, which the orchestrator treats as terminal."""
    model = ScriptedModel(
        [
            _tool_use_turn(
                "QAReport",
                _qa_args(
                    "WARNING",
                    issues=["La citazione e vigente ma e stata modificata dal D.L. 19/2024."],
                    notes="Rilievo non bloccante.",
                ),
            )
        ]
    )
    agent = build_qa_legal_agent(model, StubSubstrateClient())

    report = run_qa_legal(agent, _PREVIOUS_DRAFT).payload

    assert report.status == "WARNING"
    assert report.issues


def test_qa_legal_produces_error_report_with_issues() -> None:
    """A blocking defect yields ``ERROR`` and a non-empty issue list."""
    model = ScriptedModel(
        [
            _tool_use_turn(
                "QAReport",
                _qa_args(
                    "ERROR",
                    issues=[
                        "La citazione 'D.Lgs. 81/2008 Art. 999' non esiste.",
                        "Le sanzioni descritte non corrispondono al penalties_summary del documento.",
                    ],
                ),
            )
        ]
    )
    agent = build_qa_legal_agent(model, StubSubstrateClient())

    report = run_qa_legal(agent, _PREVIOUS_DRAFT).payload

    assert report.status == "ERROR"
    assert len(report.issues) == 2


def test_qa_legal_verifies_each_citation() -> None:
    """Citation verification is visible in telemetry, per citation checked."""
    model = ScriptedModel(
        [
            _tool_use_turn("verify_legal_citation", {"citation": "D.Lgs. 81/2008 Art. 28"}),
            _tool_use_turn("verify_legal_citation", {"citation": "Circolare INAIL n. 28/2024"}),
            _tool_use_turn("QAReport", _qa_args("PASS")),
        ]
    )
    agent = build_qa_legal_agent(model, StubSubstrateClient())

    telemetry = run_qa_legal(agent, _PREVIOUS_DRAFT).telemetry

    by_name = {invocation.tool_name: invocation for invocation in telemetry.tool_invocations}
    assert "verify_legal_citation" in by_name
    assert by_name["verify_legal_citation"].call_count >= 1
    assert by_name["verify_legal_citation"].call_count == by_name["verify_legal_citation"].success_count


def test_qa_legal_prompt_declares_role_boundary() -> None:
    """The QA prompt names its output model, the tri-state semantics, and its non-goals."""
    prompt = QA_LEGAL_SYSTEM_PROMPT
    lowered = prompt.lower()

    assert "QAReport" in prompt
    for status in ("PASS", "WARNING", "ERROR"):
        assert status in prompt
    assert "verify_legal_citation" in prompt
    assert "get_document_by_id" in prompt
    assert "non-goals" in lowered
    # Never rewrites prose, never proposes copy, never selects CTAs.
    assert "rewrite" in lowered
    assert "cta" in lowered or "call to action" in lowered
    assert "never" in lowered


_ALL_WORKER_PROMPTS: dict[str, str] = {
    "ScopeParser": SCOPE_PARSER_SYSTEM_PROMPT,
    "Scout": SCOUT_SYSTEM_PROMPT,
    "Writer": WRITER_SYSTEM_PROMPT,
    "QA-Legal": QA_LEGAL_SYSTEM_PROMPT,
}

_PROMPT_OUTPUT_MODELS: dict[str, str] = {
    "ScopeParser": "PipelineScope",
    "Scout": "ScoutReport",
    "Writer": "ArticleDraft",
    "QA-Legal": "QAReport",
}


def test_all_worker_prompts_declare_structured_output_model() -> None:
    """Every worker prompt names the structured output model it must emit (D8)."""
    for worker, prompt in _ALL_WORKER_PROMPTS.items():
        assert _PROMPT_OUTPUT_MODELS[worker] in prompt, f"{worker} prompt does not name its output model"


def test_all_worker_prompts_declare_non_goals() -> None:
    """D19 enforcement: with tools unscoped, the prompt is the only role boundary."""
    for worker, prompt in _ALL_WORKER_PROMPTS.items():
        lowered = prompt.lower()
        assert "## non-goals" in lowered, f"{worker} prompt has no non-goals section"

        section = lowered.split("## non-goals", 1)[1]
        bullets = [line for line in section.splitlines() if line.strip().startswith("-")]
        assert len(bullets) >= 3, f"{worker} non-goals section is too thin: {len(bullets)} item(s)"
        assert "you do not" in section, f"{worker} non-goals section does not state what it must not do"


def test_agents_module_exports_public_surface() -> None:
    """``__all__`` is declared, complete, and every name resolves."""
    expected = {
        "SCOPE_PARSER_MODEL_ID",
        "SCOUT_MODEL_ID",
        "WRITER_MODEL_ID",
        "QA_LEGAL_MODEL_ID",
        "SCOUT_TOOL_NAMES",
        "WRITER_TOOL_NAMES",
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
    }

    assert set(agents_module.__all__) == expected
    for name in agents_module.__all__:
        assert hasattr(agents_module, name), f"__all__ names missing attribute {name}"


def test_factory_requires_live_client() -> None:
    """A factory called with a disconnected client fails loudly, before any agent exists."""
    client = HSEMockMCPClient()  # constructed, never started: spawns no subprocess

    for factory in (build_scout_agent, build_writer_agent, build_qa_legal_agent):
        with pytest.raises(MCPClientNotConnectedError):
            factory(ScriptedModel([]), client)
        with pytest.raises(MCPClientNotConnectedError):
            factory(ScriptedModel([]), client, tool_names=["get_document_by_id"])
