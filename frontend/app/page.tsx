"use client";

import { useState } from "react";
import { CONTINUITY_THEME } from "@/lib/continuity";
import { askAgent, type AgentEvent, type Citation, type Continuity } from "@/lib/events";
import {
  applyEvent as applyGraphEvent,
  beginTurn,
  citationNodeId,
  emptyGraph,
  nodeDetails,
  type GraphState,
} from "@/lib/graph";
import { Markdown } from "@/lib/markdown";
import { GraphPanel } from "./GraphPanel";
import { NodePanel } from "./NodePanel";

const API_BASE = process.env.NEXT_PUBLIC_API_BASE ?? "http://localhost:8000";

// Empty-state examples: each one exercises a different retrieval path (PRODUCT.md:
// the empty state teaches). Order: relational, multi-hop, narrative.
const EXAMPLES = [
  "Who trained Anakin Skywalker?",
  "How is Boba Fett connected to the Jedi Order?",
  "Describe the Nautolan species",
];

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
  const [graph, setGraph] = useState<GraphState>(emptyGraph());
  const [input, setInput] = useState("");
  const [busy, setBusy] = useState(false);
  const [highlightId, setHighlightId] = useState<string | null>(null); // chip hover -> graph ring
  const [hoveredNodeId, setHoveredNodeId] = useState<string | null>(null); // graph hover -> chip ring
  const [selectedNodeId, setSelectedNodeId] = useState<string | null>(null); // click -> side panel
  const [continuity, setContinuity] = useState<Continuity | null>(null); // 3-state toggle, null = both
  const selectedDetails = selectedNodeId ? nodeDetails(graph, selectedNodeId) : null;

  async function ask(question: string) {
    setBusy(true);
    setTurns((t) => [...t, { question, answer: "", citations: [], toolCalls: [], pending: true }]);
    setGraph((g) => beginTurn(g));
    const patch = (fn: (turn: Turn) => Turn) =>
      setTurns((t) => [...t.slice(0, -1), fn(t[t.length - 1])]);
    try {
      for await (const ev of askAgent(API_BASE, question, continuity)) {
        applyEvent(ev, patch);
        setGraph((g) => applyGraphEvent(g, ev));
      }
    } catch (err) {
      patch((turn) => ({ ...turn, error: String(err), pending: false }));
    } finally {
      setBusy(false);
    }
  }

  return (
    <main className="flex h-screen font-sans text-sm">
      <section className="flex w-2/5 min-w-[24rem] flex-col border-r border-ink-700 bg-ink-900">
        <header className="border-b border-ink-700 px-6 py-4">
          <h1 className="text-xl font-semibold tracking-tight">Holocron</h1>
          <p className="mt-0.5 text-xs text-parchment-faint">
            A lore agent that chooses between graph traversal and vector search. Watch it think.
          </p>
        </header>

        <div className="flex flex-1 flex-col gap-6 overflow-y-auto px-6 py-6">
          {turns.length === 0 && <EmptyState onPick={(q) => void ask(q)} busy={busy} />}
          {turns.map((turn, i) => (
            <TurnView key={i} turn={turn} hoveredNodeId={hoveredNodeId} onHoverCitation={setHighlightId} />
          ))}
        </div>

        <form
          className="flex flex-col gap-2 border-t border-ink-700 px-6 py-4"
          onSubmit={(e) => {
            e.preventDefault();
            const q = input.trim();
            if (!q || busy) return;
            setInput("");
            void ask(q);
          }}
        >
          <ContinuityToggle value={continuity} onChange={setContinuity} disabled={busy} />
          <div className="flex gap-2">
            <input
              className="flex-1 rounded-lg border border-ink-700 bg-ink-800 px-4 py-2 text-parchment placeholder-parchment-faint outline-none transition-colors duration-150 focus:border-parchment-faint"
              value={input}
              onChange={(e) => setInput(e.target.value)}
              placeholder="Ask the Holocron…"
              disabled={busy}
            />
            <button
              className="rounded-lg bg-parchment px-4 py-2 font-medium text-ink-950 transition-opacity duration-150 disabled:opacity-30"
              disabled={busy || !input.trim()}
            >
              Ask
            </button>
          </div>
        </form>
      </section>

      <section className="relative w-3/5 bg-ink-950">
        <GraphPanel
          graph={graph}
          highlightId={highlightId}
          onNodeHover={setHoveredNodeId}
          onNodeClick={setSelectedNodeId}
          onReset={() => {
            setGraph(emptyGraph());
            setSelectedNodeId(null);
          }}
        />
        {selectedDetails && (
          <NodePanel
            details={selectedDetails}
            onAskAbout={(question) => {
              setInput(question);
              setSelectedNodeId(null);
            }}
            onClose={() => setSelectedNodeId(null)}
          />
        )}
      </section>
    </main>
  );
}

function EmptyState({ onPick, busy }: { onPick: (q: string) => void; busy: boolean }) {
  return (
    <div className="flex flex-1 flex-col justify-center gap-6">
      <div>
        <p className="text-base text-parchment-dim">
          Every answer comes from a pinned Wookieepedia corpus: a knowledge graph and a vector
          index. The agent picks its path per question; the sky on the right shows the traversal.
        </p>
      </div>
      <div className="flex flex-col items-start gap-2">
        <p className="font-mono text-[11px] uppercase tracking-wider text-parchment-faint">
          Try one
        </p>
        {EXAMPLES.map((q) => (
          <button
            key={q}
            type="button"
            disabled={busy}
            onClick={() => onPick(q)}
            className="rounded-lg border border-ink-700 px-3 py-1.5 text-left text-parchment-dim transition-colors duration-150 hover:border-parchment-faint hover:text-parchment"
          >
            {q}
          </button>
        ))}
      </div>
    </div>
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

function ContinuityToggle({
  value,
  onChange,
  disabled,
}: {
  value: Continuity | null;
  onChange: (v: Continuity | null) => void;
  disabled: boolean;
}) {
  const options: { label: string; value: Continuity | null }[] = [
    { label: "both", value: null },
    { label: "canon", value: "canon" },
    { label: "legends", value: "legends" },
  ];
  // real radio inputs: keyboard behavior for free, pill look via labels
  return (
    <fieldset
      className="flex gap-1 self-start rounded-full bg-ink-800 p-0.5 text-xs"
      aria-label="Continuity"
      disabled={disabled}
    >
      {options.map((o) => (
        <label
          key={o.label}
          className={`cursor-pointer rounded-full px-2.5 py-1 transition-colors duration-150 ${
            value === o.value
              ? o.value
                ? CONTINUITY_THEME[o.value].chip // selected continuity: its hue, nothing else
                : "bg-ink-950 text-parchment"
              : "text-parchment-faint hover:text-parchment-dim"
          }`}
        >
          <input
            type="radio"
            name="continuity"
            className="sr-only"
            checked={value === o.value}
            onChange={() => onChange(o.value)}
          />
          {o.label}
        </label>
      ))}
    </fieldset>
  );
}

function TurnView({
  turn,
  hoveredNodeId,
  onHoverCitation,
}: {
  turn: Turn;
  hoveredNodeId: string | null;
  onHoverCitation: (nodeId: string | null) => void;
}) {
  const thinking = turn.pending && !turn.answer;
  return (
    <article className="rise-in flex flex-col gap-1.5">
      <p className="font-medium text-parchment">{turn.question}</p>
      {turn.toolCalls.length > 0 && (
        <p className={`font-mono text-[11px] text-parchment-faint ${thinking ? "streaming-cursor" : ""}`}>
          {turn.toolCalls.join(" → ")}
        </p>
      )}
      {thinking && turn.toolCalls.length === 0 && (
        <p className="streaming-cursor font-mono text-[11px] text-parchment-faint">
          consulting the archive…
        </p>
      )}
      {turn.error ? (
        <div className="rounded-lg border border-error/40 bg-error/10 px-3 py-2 text-error">
          <p className="font-medium">The archive did not answer.</p>
          <p className="mt-0.5 font-mono text-[11px] opacity-80">{turn.error}</p>
        </div>
      ) : (
        <div className="max-w-prose leading-relaxed text-parchment-dim">
          <Markdown text={turn.answer} />
          {turn.pending && turn.answer && <span className="streaming-cursor">▍</span>}
        </div>
      )}
      {turn.citations.length > 0 && (
        <ul className="mt-1 flex flex-wrap gap-1.5">
          {turn.citations.map((c) => (
            <li
              key={citationNodeId(c)}
              className={`cursor-default rounded-full px-2.5 py-0.5 text-xs ring-current transition-shadow duration-150 hover:ring-1 ${
                hoveredNodeId === citationNodeId(c) ? "ring-2" : ""
              } ${CONTINUITY_THEME[c.continuity].chip}`}
              title={c.section ? `${c.title} · ${c.section}` : c.title}
              onMouseEnter={() => onHoverCitation(citationNodeId(c))}
              onMouseLeave={() => onHoverCitation(null)}
            >
              {c.title}
            </li>
          ))}
        </ul>
      )}
    </article>
  );
}
