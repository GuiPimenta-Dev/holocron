"""FastAPI app factory. POST /ask streams agent events via SSE (ADR-0003).

The agent is injected as a dependency (the test seam): any object with
`astream(question, continuity) -> AsyncIterator[dict]` where each dict carries
a "type" key. SSE protocol (the phase-3 frontend contract):

    event: tool_call     data: {"name": ..., "args": {...}}
    event: tool_result   data: {"name": ..., "result": ...}
    event: answer_delta  data: {"text": ...}
    event: done          data: {"citations": [{"title", "name", "continuity", "section"?}], "trace_id": ...}
    event: error         data: {"message": ...}

`done` (or `error`) terminates the stream. Errors after headers are sent
travel in-stream as an `error` event — HTTP status stays 200.
"""

from __future__ import annotations

import json
from collections.abc import AsyncIterator
from typing import Any, Literal, Protocol

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field


class Agent(Protocol):
    def astream(self, question: str, continuity: str | None = None) -> AsyncIterator[dict[str, Any]]: ...


class AskRequest(BaseModel):
    question: str = Field(min_length=1)
    continuity: Literal["canon", "legends"] | None = None


def _sse(event: dict[str, Any]) -> str:
    payload = {k: v for k, v in event.items() if k != "type"}
    return f"event: {event['type']}\ndata: {json.dumps(payload)}\n\n"


def create_app(agent: Agent, ui_origin: str) -> FastAPI:
    app = FastAPI(title="Holocron")
    # Local-only (ADR-0003): the Next.js dev server is the single allowed origin.
    app.add_middleware(
        CORSMiddleware,
        allow_origins=[ui_origin],
        allow_methods=["POST"],
        allow_headers=["content-type"],
    )

    @app.post("/ask")
    async def ask(req: AskRequest) -> StreamingResponse:  # pyright: ignore[reportUnusedFunction]
        async def stream() -> AsyncIterator[str]:
            try:
                async for event in agent.astream(req.question, req.continuity):
                    yield _sse(event)
            except Exception as exc:  # noqa: BLE001 — error framing is the contract
                yield _sse({"type": "error", "message": str(exc)})

        return StreamingResponse(stream(), media_type="text/event-stream")

    return app
