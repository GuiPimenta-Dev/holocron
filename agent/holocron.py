"""The Holocron agent: a LangGraph state graph over the retrieval layer (ADR-0001).

Topology: reason (LLM, tools bound) -> tools -> reason ... -> synthesis (the
final reason pass, which streams the answer). Framework imports live here only;
`retrieval/` stays framework-free. Every run is traced via the Langfuse
callback when LANGFUSE_* keys are configured.
"""

from __future__ import annotations

import json
import sys
from collections.abc import AsyncIterator
from typing import Any, Protocol

from langchain_anthropic import ChatAnthropic
from langchain_core.tools import tool as lc_tool
from langgraph.graph import START, MessagesState, StateGraph
from langgraph.prebuilt import ToolNode, tools_condition

from core.domain import Citation, Continuity
from retrieval import KnowledgeGraph, VectorIndex

MODEL = "claude-sonnet-5"

SYSTEM_PROMPT = """\
You are Holocron, a Star Wars lore assistant answering strictly from a pinned
Wookieepedia corpus exposed through your tools.

Rules:
- Ground every claim in tool results. If the tools return nothing relevant,
  say you don't know — never answer from memory, never invent lore.
- Every fact belongs to a continuity: `canon` or `legends`. When your sources
  conflict across continuities, answer per continuity ("In canon, ... In
  Legends, ...") instead of blending them.
- Strategy: start with get_entity to locate the subject; use get_relations for
  relational facts and path_between for multi-hop connections; use
  search_chunks for descriptive/narrative questions answered by article prose;
  use run_cypher only when the typed tools cannot express the question.
- Keep answers concise and name the entities you drew from.
{continuity_note}"""


class Cited(Protocol):
    """What a retrieval result must expose to be citable (read-only: frozen dataclasses)."""

    @property
    def title(self) -> str: ...
    @property
    def name(self) -> str: ...
    @property
    def continuity(self) -> Continuity: ...


class Citations:
    """Per-request citation collector: continuity filter + dedup by title."""

    def __init__(self, restrict: Continuity | None):
        self._restrict = restrict
        self._by_title: dict[str, Citation] = {}

    def record[T: Cited](self, results: list[T]) -> list[T]:
        """Filter results to the restricted continuity and remember their sources."""
        if self._restrict:
            results = [r for r in results if r.continuity is self._restrict]
        for r in results:
            citation = Citation(
                title=r.title,
                name=r.name,
                continuity=r.continuity,
                section=getattr(r, "section", None),
            )
            self._by_title.setdefault(citation.title, citation)
        return results

    def as_dicts(self) -> list[dict[str, Any]]:
        return [c.as_dict() for c in self._by_title.values()]


class HolocronAgent:
    """Streams plain-dict events; the API layer maps them 1:1 onto SSE."""

    def __init__(self, graph: KnowledgeGraph, index: VectorIndex, traced: bool, model: str = MODEL):
        self._graph = graph
        self._index = index
        # ponytail: thinking disabled — Sonnet 5 defaults to adaptive thinking, but
        # langchain-anthropic 1.4.x drops the thinking field when echoing the
        # assistant turn back after a tool round-trip (API 400). Re-enable once
        # the serialization bug is fixed upstream.
        self._llm = ChatAnthropic(
            model=model,  # pyright: ignore[reportCallIssue]
            max_tokens=1024,  # pyright: ignore[reportCallIssue]
            thinking={"type": "disabled"},
        )
        self._callbacks: list[Any] = []
        if traced:
            from langfuse.langchain import CallbackHandler

            self._callbacks = [CallbackHandler()]
        else:
            # "No trace, no merge" — degrade loudly, not silently.
            print("WARNING: LANGFUSE_* keys not set; agent runs will NOT be traced", file=sys.stderr)

    async def astream(self, question: str, continuity: str | None = None) -> AsyncIterator[dict[str, Any]]:
        restrict = Continuity.parse(continuity)
        citations = Citations(restrict)
        graph = self._build_graph(self._bind_tools(citations, restrict))

        note = (
            f"- The user restricted this question to {restrict} only: answer solely "
            f"from {restrict} sources and discard results from the other continuity, "
            f"including anything surfaced by path_between or run_cypher."
            if restrict
            else ""
        )
        inputs = {
            "messages": [
                ("system", SYSTEM_PROMPT.format(continuity_note=note)),
                ("user", question),
            ]
        }
        async for ev in graph.astream_events(inputs, config={"callbacks": self._callbacks}, version="v2"):
            kind = ev["event"]
            if kind == "on_chat_model_stream":
                if text := _text(ev["data"]["chunk"].content):
                    yield {"type": "answer_delta", "text": text}
            elif kind == "on_tool_start":
                yield {"type": "tool_call", "name": ev["name"], "args": ev["data"].get("input")}
            elif kind == "on_tool_end":
                yield {
                    "type": "tool_result",
                    "name": ev["name"],
                    "result": _plain(ev["data"].get("output")),
                }
        yield {"type": "done", "citations": citations.as_dicts()}

    def _bind_tools(self, citations: Citations, restrict: Continuity | None) -> list[Any]:
        """Per-request closures over the retrieval layer.

        Domain objects become dicts here — this is the JSON edge the LLM sees.
        The closures' docstrings are copied from the retrieval methods: they are
        the prompt the agent routes by.
        """

        def get_entity(name: str) -> list[dict[str, Any]]:
            return [r.as_dict() for r in citations.record(self._graph.get_entity(name))]

        def get_relations(name: str) -> list[dict[str, Any]]:
            return [r.as_dict() for r in citations.record(self._graph.get_relations(name))]

        def search_chunks(query: str, continuity: str | None = None, k: int = 8) -> list[dict[str, Any]]:
            # a user-pinned continuity overrides whatever the LLM passes
            wanted = str(restrict) if restrict else continuity
            return [c.as_dict() for c in citations.record(self._index.search(query, wanted, k))]

        def path_between(a: str, b: str, max_hops: int = 4) -> list[dict[str, Any]]:
            return [p.as_dict() for p in self._graph.path_between(a, b, max_hops)]

        def run_cypher(query: str) -> list[dict[str, Any]] | dict[str, str]:
            return self._graph.run_cypher(query)

        sources = {
            get_entity: self._graph.get_entity,
            get_relations: self._graph.get_relations,
            search_chunks: self._index.search,
            path_between: self._graph.path_between,
            run_cypher: self._graph.run_cypher,
        }
        for wrapper, method in sources.items():
            wrapper.__doc__ = method.__doc__
        return [lc_tool(w) for w in sources]

    def _build_graph(self, tools: list[Any]) -> Any:
        llm = self._llm.bind_tools(tools)

        def reason(state: MessagesState) -> dict[str, Any]:
            return {"messages": [llm.invoke(state["messages"])]}

        graph = StateGraph(MessagesState)
        graph.add_node("reason", reason)
        graph.add_node("tools", ToolNode(tools))
        graph.add_edge(START, "reason")
        graph.add_conditional_edges("reason", tools_condition)  # -> "tools" or END
        graph.add_edge("tools", "reason")
        return graph.compile()


def _text(content: Any) -> str:
    """Extract plain text from a streamed chunk's content (str or block list)."""
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        return "".join(b.get("text", "") for b in content if isinstance(b, dict) and b.get("type") == "text")
    return ""


def _plain(output: Any) -> Any:
    """ToolMessage -> JSON-friendly payload for the tool_result event."""
    content = getattr(output, "content", output)
    if isinstance(content, str):
        try:
            return json.loads(content)
        except ValueError:
            return content
    return content
