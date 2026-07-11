"use client";

import { useState } from "react";
import { askAgent, type AgentEvent, type Citation } from "@/lib/events";

const API_BASE = process.env.NEXT_PUBLIC_API_BASE ?? "http://localhost:8000";

interface Turn {
  question: string;
  answer: string;
  citations: Citation[];
  toolCalls: string[];
  error?: string;
  pending: boolean;
}

export default function Home() {
  const [turns, setTurns] = useState<Turn[]>([]);
  const [input, setInput] = useState("");
  const [busy, setBusy] = useState(false);

  async function ask(question: string) {
    setBusy(true);
    setTurns((t) => [...t, { question, answer: "", citations: [], toolCalls: [], pending: true }]);
    const patch = (fn: (turn: Turn) => Turn) =>
      setTurns((t) => [...t.slice(0, -1), fn(t[t.length - 1])]);
    try {
      for await (const ev of askAgent(API_BASE, question)) {
        applyEvent(ev, patch);
      }
    } catch (err) {
      patch((turn) => ({ ...turn, error: String(err), pending: false }));
    } finally {
      setBusy(false);
    }
  }

  return (
    <main className="mx-auto flex min-h-screen max-w-3xl flex-col gap-6 px-6 py-10 font-sans">
      <header>
        <h1 className="text-2xl font-semibold">Holocron</h1>
        <p className="text-sm text-zinc-500">
          Star Wars lore agent — graph traversal + vector search, chosen at runtime
        </p>
      </header>

      <section className="flex flex-1 flex-col gap-6">
        {turns.length === 0 && (
          <p className="text-sm text-zinc-400">
            Ask about the lore — try &ldquo;Who trained Anakin Skywalker?&rdquo;
          </p>
        )}
        {turns.map((turn, i) => (
          <TurnView key={i} turn={turn} />
        ))}
      </section>

      <form
        className="flex gap-2"
        onSubmit={(e) => {
          e.preventDefault();
          const q = input.trim();
          if (!q || busy) return;
          setInput("");
          void ask(q);
        }}
      >
        <input
          className="flex-1 rounded-lg border border-zinc-300 px-4 py-2 text-sm outline-none focus:border-zinc-500 dark:border-zinc-700 dark:bg-zinc-900"
          value={input}
          onChange={(e) => setInput(e.target.value)}
          placeholder="Ask the Holocron…"
          disabled={busy}
        />
        <button
          className="rounded-lg bg-zinc-900 px-4 py-2 text-sm text-white disabled:opacity-40 dark:bg-zinc-100 dark:text-zinc-900"
          disabled={busy || !input.trim()}
        >
          Ask
        </button>
      </form>
    </main>
  );
}

function applyEvent(ev: AgentEvent, patch: (fn: (turn: Turn) => Turn) => void) {
  switch (ev.type) {
    case "tool_call":
      patch((t) => ({ ...t, toolCalls: [...t.toolCalls, ev.name] }));
      break;
    case "answer_delta":
      patch((t) => ({ ...t, answer: t.answer + ev.text }));
      break;
    case "done":
      patch((t) => ({ ...t, citations: ev.citations, pending: false }));
      break;
    case "error":
      patch((t) => ({ ...t, error: ev.message, pending: false }));
      break;
  }
}

const CONTINUITY_STYLE: Record<Citation["continuity"], string> = {
  canon: "bg-sky-100 text-sky-900 dark:bg-sky-900/40 dark:text-sky-200",
  legends: "bg-amber-100 text-amber-900 dark:bg-amber-900/40 dark:text-amber-200",
};

function TurnView({ turn }: { turn: Turn }) {
  return (
    <article className="flex flex-col gap-2">
      <p className="font-medium">{turn.question}</p>
      {turn.toolCalls.length > 0 && (
        <p className="font-mono text-xs text-zinc-400">{turn.toolCalls.join(" → ")}</p>
      )}
      {turn.error ? (
        <p className="rounded-lg bg-red-50 px-3 py-2 text-sm text-red-700 dark:bg-red-950 dark:text-red-300">
          {turn.error}
        </p>
      ) : (
        <p className="whitespace-pre-wrap text-sm leading-relaxed text-zinc-700 dark:text-zinc-300">
          {turn.answer}
          {turn.pending && <span className="animate-pulse">▍</span>}
        </p>
      )}
      {turn.citations.length > 0 && (
        <ul className="flex flex-wrap gap-1.5">
          {turn.citations.map((c) => (
            <li
              key={c.title}
              className={`rounded-full px-2.5 py-0.5 text-xs ${CONTINUITY_STYLE[c.continuity]}`}
              title={c.section ? `${c.title} · ${c.section}` : c.title}
            >
              {c.title}
            </li>
          ))}
        </ul>
      )}
    </article>
  );
}
