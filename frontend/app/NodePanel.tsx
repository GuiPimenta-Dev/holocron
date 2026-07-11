"use client";

import { CONTINUITY_THEME } from "@/lib/continuity";
import { askAboutQuestion, type NodeDetails } from "@/lib/graph";

/** Side panel: everything the stream delivered about one node (decision 3). */
export function NodePanel({
  details,
  onAskAbout,
  onClose,
}: {
  details: NodeDetails;
  onAskAbout: (question: string) => void;
  onClose: () => void;
}) {
  const { node, owner, properties, outgoing, incoming } = details;
  const isChunk = node.kind === "chunk";
  const askSubject = owner ?? node;
  return (
    <aside className="rise-in absolute inset-y-0 right-0 z-10 flex w-80 flex-col gap-4 overflow-y-auto border-l border-ink-700 bg-ink-900 p-4 text-sm">
      <header className="flex items-start justify-between gap-2">
        <div>
          <h2 className="font-semibold text-parchment">{isChunk ? (owner?.name ?? node.name) : node.name}</h2>
          <p className="mt-1 flex flex-wrap gap-1.5 text-xs">
            <span className="rounded-full bg-ink-800 px-2 py-0.5 text-parchment-dim">
              {isChunk ? `excerpt · § ${node.section}` : node.type}
            </span>
            <span className={`rounded-full px-2 py-0.5 ${CONTINUITY_THEME[node.continuity].chip}`}>
              {node.continuity}
            </span>
          </p>
        </div>
        <button
          onClick={onClose}
          aria-label="Close"
          className="rounded-md px-2 py-0.5 text-parchment-faint transition-colors duration-150 hover:bg-ink-800 hover:text-parchment-dim"
        >
          ×
        </button>
      </header>

      {isChunk && (
        <p className="text-parchment-dim">
          A prose excerpt the agent retrieved from the &ldquo;{node.section}&rdquo; section of{" "}
          <span className="font-medium text-parchment">{owner?.name ?? "its entity"}</span>.
        </p>
      )}

      {Object.keys(properties).length > 0 && (
        <section>
          <h3 className="mb-1.5 font-mono text-[11px] uppercase tracking-wider text-parchment-faint">Infobox</h3>
          <dl className="grid grid-cols-[auto_1fr] gap-x-3 gap-y-1">
            {Object.entries(properties).map(([k, v]) => (
              <div key={k} className="contents">
                <dt className="text-parchment-faint">{k}</dt>
                <dd className="text-parchment-dim">{v}</dd>
              </div>
            ))}
          </dl>
        </section>
      )}

      {outgoing.length > 0 && (
        <RelationList title="Relations" links={outgoing.map((l) => ({ relation: l.relation, other: l.target }))} />
      )}
      {incoming.length > 0 && (
        <RelationList
          title="Referenced by"
          links={incoming.map((l) => ({ relation: l.relation, other: l.source }))}
        />
      )}

      <p className="text-xs text-parchment-faint">
        Showing only what the agent has retrieved this session; this panel never queries the backend.
      </p>

      <button
        onClick={() => onAskAbout(askAboutQuestion(details))}
        className="mt-auto rounded-lg bg-parchment px-4 py-2 font-medium text-ink-950 transition-opacity duration-150 hover:opacity-90"
      >
        Ask about {askSubject.name}
      </button>
    </aside>
  );
}

function RelationList({ title, links }: { title: string; links: { relation: string; other: string }[] }) {
  return (
    <section>
      <h3 className="mb-1.5 font-mono text-[11px] uppercase tracking-wider text-parchment-faint">{title}</h3>
      <ul className="flex flex-col gap-1">
        {links.map((l, i) => (
          <li key={i} className="flex items-baseline gap-2">
            <span className="font-mono text-[10px] text-parchment-faint">{l.relation}</span>
            <span className="text-parchment-dim">{l.other}</span>
          </li>
        ))}
      </ul>
    </section>
  );
}
