"""One traced LLM call — proves the Langfuse wiring before the agent exists.

Usage: uv run python -m agent.smoke
Needs ANTHROPIC_API_KEY + LANGFUSE_* in .env (see .env.example); the Langfuse
keys are pre-provisioned by docker-compose, so copying the example works as-is.
"""

from __future__ import annotations

import os
import sys

from dotenv import load_dotenv


def main() -> None:
    load_dotenv()
    missing = [
        v
        for v in (
            "ANTHROPIC_API_KEY",
            "LANGFUSE_PUBLIC_KEY",
            "LANGFUSE_SECRET_KEY",
            "LANGFUSE_HOST",
        )
        if not os.environ.get(v)
    ]
    if missing:
        sys.exit(f"missing in .env: {', '.join(missing)} — copy .env.example to .env and fill in")

    from langchain_anthropic import ChatAnthropic
    from langfuse import get_client
    from langfuse.langchain import CallbackHandler

    llm = ChatAnthropic(model="claude-sonnet-5", max_tokens=64)  # pyright: ignore[reportCallIssue]
    reply = llm.invoke(
        "In one word: which order did Kit Fisto belong to?",
        config={"callbacks": [CallbackHandler()]},
    )
    get_client().flush()
    print(f"answer: {reply.text()}")
    print(f"trace:  {os.environ['LANGFUSE_HOST']} -> Holocron project -> Tracing")


if __name__ == "__main__":
    main()
