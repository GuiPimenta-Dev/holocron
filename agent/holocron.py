"""The Holocron agent: a LangGraph state graph over the retrieval tools (ADR-0001).

Topology: reason (LLM, tools bound) -> tools -> reason ... -> synthesis (the
final reason pass, which streams the answer). Framework imports live here only;
`tools.py` stays framework-free. Every run is traced via the Langfuse callback
when LANGFUSE_* keys are configured.
"""

from __future__ import annotations

import json
import os
import sys
from collections.abc import AsyncIterator
from typing import Any

from langchain_anthropic import ChatAnthropic
from langchain_core.tools import tool as lc_tool
from langgraph.graph import START, MessagesState, StateGraph
from langgraph.prebuilt import ToolNode, tools_condition

import tools

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


def _text(content: Any) -> str:
    """Extract plain text from a streamed chunk's content (str or block list)."""
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        return "".join(
            b.get("text", "") for b in content if isinstance(b, dict) and b.get("type") == "text"
        )
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


class HolocronAgent:
    """Streams plain-dict events; the API layer maps them 1:1 onto SSE."""

    def __init__(self, model: str = MODEL):
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
        if os.environ.get("LANGFUSE_PUBLIC_KEY"):
            from langfuse.langchain import CallbackHandler

            self._callbacks = [CallbackHandler()]
        else:
            # "No trace, no merge" — degrade loudly, not silently.
            print(
                "WARNING: LANGFUSE_* keys not set; agent runs will NOT be traced", file=sys.stderr
            )

    def _build_graph(self, question_tools: list[Any]) -> Any:
        llm = self._llm.bind_tools(question_tools)

        def reason(state: MessagesState) -> dict[str, Any]:
            return {"messages": [llm.invoke(state["messages"])]}

        graph = StateGraph(MessagesState)
        graph.add_node("reason", reason)
        graph.add_node("tools", ToolNode(question_tools))
        graph.add_edge(START, "reason")
        graph.add_conditional_edges("reason", tools_condition)  # -> "tools" or END
        graph.add_edge("tools", "reason")
        return graph.compile()

    async def astream(
        self, question: str, continuity: str | None = None
    ) -> AsyncIterator[dict[str, Any]]:
        citations: list[dict[str, Any]] = []

        # Per-request tool closures: filter by continuity and collect citations
        # without shared mutable state between requests. path_between/run_cypher
        # bind directly; their citation story is the #7 synthesis slice.
        def filter_and_cite(results: list[dict[str, Any]]) -> list[dict[str, Any]]:
            if continuity:
                results = [r for r in results if r["continuity"] == continuity]
            citations.extend(
                {"title": r["title"], "name": r["name"], "continuity": r["continuity"]}
                | ({"section": r["section"]} if "section" in r else {})
                for r in results
            )
            return results

        def get_entity(name: str) -> list[dict[str, Any]]:
            return filter_and_cite(tools.get_entity(name))

        def get_relations(name: str) -> list[dict[str, Any]]:
            return filter_and_cite(tools.get_relations(name))

        user_continuity = continuity

        def search_chunks(query: str, continuity: str | None = None, k: int = 8):
            # a user-pinned continuity overrides whatever the LLM passes
            return filter_and_cite(tools.search_chunks(query, user_continuity or continuity, k))

        for w in (get_entity, get_relations, search_chunks):
            w.__doc__ = getattr(tools, w.__name__).__doc__  # the LLM routes by these docstrings
        graph = self._build_graph(
            [
                lc_tool(f)
                for f in (
                    get_entity,
                    get_relations,
                    search_chunks,
                    tools.path_between,
                    tools.run_cypher,
                )
            ]
        )

        note = (
            f"- The user restricted this question to {continuity} only: answer solely "
            f"from {continuity} sources and discard results from the other continuity, "
            f"including anything surfaced by path_between or run_cypher."
            if continuity
            else ""
        )
        inputs = {
            "messages": [
                ("system", SYSTEM_PROMPT.format(continuity_note=note)),
                ("user", question),
            ]
        }
        async for ev in graph.astream_events(
            inputs, config={"callbacks": self._callbacks}, version="v2"
        ):
            kind = ev["event"]
            if kind == "on_chat_model_stream":
                text = _text(ev["data"]["chunk"].content)
                if text:
                    yield {"type": "answer_delta", "text": text}
            elif kind == "on_tool_start":
                yield {"type": "tool_call", "name": ev["name"], "args": ev["data"].get("input")}
            elif kind == "on_tool_end":
                yield {
                    "type": "tool_result",
                    "name": ev["name"],
                    "result": _plain(ev["data"].get("output")),
                }
        seen: set[str] = set()
        unique = [c for c in citations if not (c["title"] in seen or seen.add(c["title"]))]
        yield {"type": "done", "citations": unique}
