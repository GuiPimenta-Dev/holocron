# Holocron frontend

Next.js + React + Tailwind UI over the FastAPI SSE backend (ADR-0003).
Local-only — there is no deploy.

```sh
# from the repo root: docker compose up -d && uv run python -m api
npm install
npm run dev        # http://localhost:3000
```

If port 3000 is taken, `npm run dev -- -p 3005` and start the API with
`HOLOCRON_UI_ORIGIN=http://localhost:3005` (CORS allows a single origin).

```sh
npm run lint       # eslint
npm run typecheck  # tsc --noEmit
npm test           # vitest (SSE parser against a real captured stream)
npm run build
```

`lib/events.ts` mirrors the SSE wire format defined in `api/app.py` —
change them together (see CLAUDE.md boundary rules).
