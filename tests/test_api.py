"""SSE protocol tests: TestClient + scripted stub agent injected via the app factory.

This stubs OUR agent interface, never the LLM — agent quality is measured only by
the phase-4 eval (testing doctrine).
"""

import json

from fastapi.testclient import TestClient

from api.app import create_app

SCRIPT = [
    {"type": "tool_call", "name": "get_entity", "args": {"name": "Kit Fisto"}},
    {"type": "tool_result", "name": "get_entity", "result": [{"title": "Kit Fisto"}]},
    {"type": "answer_delta", "text": "Kit Fisto was "},
    {"type": "answer_delta", "text": "a Nautolan Jedi Master."},
    {
        "type": "done",
        "citations": [{"title": "Kit Fisto", "name": "Kit Fisto", "continuity": "canon"}],
    },
]


class ScriptedAgent:
    """Replays a fixed event script; records what it was asked."""

    def __init__(self, events=SCRIPT, explode_after=None):
        self.events = events
        self.explode_after = explode_after
        self.calls = []

    async def astream(self, question, continuity=None):
        self.calls.append((question, continuity))
        for i, event in enumerate(self.events):
            if self.explode_after is not None and i >= self.explode_after:
                raise RuntimeError("kaboom")
            yield event


def parse_sse(body: str) -> list[tuple[str, dict]]:
    events = []
    for block in body.strip().split("\n\n"):
        lines = dict(line.split(": ", 1) for line in block.splitlines())
        events.append((lines["event"], json.loads(lines["data"])))
    return events


def post_ask(agent, payload):
    client = TestClient(create_app(agent), raise_server_exceptions=False)
    return client.post("/ask", json=payload)


def test_ask_streams_the_five_event_types_in_order():
    resp = post_ask(ScriptedAgent(), {"question": "What species is Kit Fisto?"})
    assert resp.status_code == 200
    assert resp.headers["content-type"].startswith("text/event-stream")
    events = parse_sse(resp.text)
    assert [e for e, _ in events] == [
        "tool_call",
        "tool_result",
        "answer_delta",
        "answer_delta",
        "done",
    ]
    assert events[0][1] == {"name": "get_entity", "args": {"name": "Kit Fisto"}}
    assert events[-1][1]["citations"][0]["continuity"] == "canon"


def test_continuity_filter_reaches_the_agent():
    agent = ScriptedAgent()
    post_ask(agent, {"question": "Who is Kit Fisto?", "continuity": "legends"})
    assert agent.calls == [("Who is Kit Fisto?", "legends")]


def test_empty_question_is_rejected():
    assert post_ask(ScriptedAgent(), {"question": ""}).status_code == 422
    assert post_ask(ScriptedAgent(), {}).status_code == 422


def test_invalid_continuity_is_rejected():
    resp = post_ask(ScriptedAgent(), {"question": "hi", "continuity": "disney"})
    assert resp.status_code == 422


def test_agent_failure_mid_stream_emits_error_event():
    resp = post_ask(ScriptedAgent(explode_after=2), {"question": "boom"})
    assert resp.status_code == 200  # headers already sent; error travels in-stream
    events = parse_sse(resp.text)
    assert [e for e, _ in events] == ["tool_call", "tool_result", "error"]
    assert "kaboom" in events[-1][1]["message"]
