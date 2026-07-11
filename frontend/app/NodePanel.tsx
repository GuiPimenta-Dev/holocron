"use client";

import type { NodeDetails } from "@/lib/graph";

const CONTINUITY_BADGE: Record<string, string> = {
  canon: "bg-sky-100 text-sky-900 dark:bg-sky-900/40 dark:text-sky-200",
  legends: "bg-amber-100 text-amber-900 dark:bg-amber-900/40 dark:text-amber-200",
};

/** Side panel: everything the stream delivered about one node (decision 3). */
export function NodePanel({
  details,
  onAskAbout,
  onClose,
}: {
  details: NodeDetails;
  onAskAbout: (name: string) => void;
  onClose: () => void;
}) {
  const { node, properties, outgoing, incoming } = details;
  return (
    <aside className="absolute inset-y-0 right-0 z-10 flex w-80 flex-col gap-4 overflow-y-auto border-l border-zinc-200 bg-white/95 p-4 backdrop-blur dark:border-zinc-800 dark:bg-zinc-950/95">
      <header className="flex items-start justify-between gap-2">
        <div>
          <h2 className="font-semibold">{node.name}</h2>
          <p className="mt-1 flex flex-wrap gap-1.5 text-xs">
            <span className="rounded-full bg-zinc-100 px-2 py-0.5 text-zinc-600 dark:bg-zinc-800 dark:text-zinc-300">
              {node.kind === "chunk" ? `§ ${node.section}` : node.type}
            </span>
            <span className={`rounded-full px-2 py-0.5 ${CONTINUITY_BADGE[node.continuity]}`}>
              {node.continuity}
            </span>
          </p>
        </div>
        <button
          onClick={onClose}
          aria-label="Close"
          className="rounded-md px-2 py-0.5 text-zinc-400 hover:bg-zinc-100 hover:text-zinc-600 dark:hover:bg-zinc-800"
        >
          ×
        </button>
      </header>

      {Object.keys(properties).length > 0 && (
        <section>
          <h3 className="mb-1.5 text-xs font-medium uppercase tracking-wide text-zinc-400">Infobox</h3>
          <dl className="grid grid-cols-[auto_1fr] gap-x-3 gap-y-1 text-sm">
            {Object.entries(properties).map(([k, v]) => (
              <div key={k} className="contents">
                <dt className="text-zinc-400">{k}</dt>
                <dd className="text-zinc-700 dark:text-zinc-300">{v}</dd>
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

      <p className="text-xs text-zinc-400">
        Showing only what the agent has retrieved this session — this panel never queries the backend.
      </p>

      <button
        onClick={() => onAskAbout(node.name)}
        className="mt-auto rounded-lg bg-zinc-900 px-4 py-2 text-sm text-white dark:bg-zinc-100 dark:text-zinc-900"
      >
        Ask about {node.name}
      </button>
    </aside>
  );
}

function RelationList({ title, links }: { title: string; links: { relation: string; other: string }[] }) {
  return (
    <section>
      <h3 className="mb-1.5 text-xs font-medium uppercase tracking-wide text-zinc-400">{title}</h3>
      <ul className="flex flex-col gap-1 text-sm">
        {links.map((l, i) => (
          <li key={i} className="flex items-baseline gap-2">
            <span className="font-mono text-[10px] text-zinc-400">{l.relation}</span>
            <span className="text-zinc-700 dark:text-zinc-300">{l.other}</span>
          </li>
        ))}
      </ul>
    </section>
  );
}
