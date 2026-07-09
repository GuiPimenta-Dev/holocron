"""Serve the real agent locally:  uv run python -m api

Then:  curl -N localhost:8000/ask -X POST -H 'content-type: application/json' \
           -d '{"question": "What species is Kit Fisto?"}'
"""

from dotenv import load_dotenv


def main() -> None:
    load_dotenv()

    import uvicorn

    from agent.holocron import HolocronAgent
    from api.app import create_app

    uvicorn.run(create_app(HolocronAgent()), host="127.0.0.1", port=8000)


if __name__ == "__main__":
    main()
