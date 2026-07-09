# ADR-0003: Next.js frontend over a FastAPI SSE backend

Supersedes the Streamlit UI in decision #10 (DECISIONS.md); local-only (no
deploy) stands. The user wants real frontend experience, and a serious UI needs
the agent behind an API anyway. FastAPI exposes the agent via Server-Sent
Events — each tool call and the answer stream to the UI live, which is also the
demo's best moment. Next.js + React + Tailwind consumes the stream. Rejected:
Streamlit (teaches no frontend), Next.js API routes shelling into Python
(fragile boundary), SvelteKit (weaker job-market signal than React).
