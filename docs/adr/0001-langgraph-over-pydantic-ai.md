# ADR-0001: LangGraph instead of Pydantic AI for the agent layer

**Status:** accepted (2026-07-09). Supersedes decision #8 in DECISIONS.md.

## Context

Decision #8 picked Pydantic AI for its simplicity. The project's primary goal,
however, is employability as an AI/LLM Engineer, and LangGraph is the most
demanded agent-framework keyword in job postings. The agent-layer boundary rule
(framework imports live in `agent.py` only) was designed to make exactly this
swap cheap — no other module changes.

Plain LangChain (AgentExecutor/chains) was rejected: LangChain itself has moved
its agent story to LangGraph; learning the deprecated API would invite the
"why not LangGraph?" interview question.

## Decision

The agent is a LangGraph state graph: an explicit routing/reasoning node that
calls the retrieval tools (vector search, graph queries) and a synthesis step.
`tools.py` stays framework-free; LangGraph types appear only in the agent layer.

## Consequences

- CV alignment with the LangChain/LangGraph/LangSmith ecosystem.
- Explicit graph topology replaces an implicit tool loop — more code than
  Pydantic AI, but the topology itself becomes portfolio material.
- Observability integrates natively (LangSmith/Langfuse callbacks).
