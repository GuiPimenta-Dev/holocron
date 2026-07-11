"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import dynamic from "next/dynamic";
import type { Continuity } from "@/lib/events";
import type { GraphState } from "@/lib/graph";

// react-force-graph touches window at import time — client-only.
const ForceGraph2D = dynamic(() => import("react-force-graph-2d"), { ssr: false });

import { CONTINUITY_THEME } from "@/lib/continuity";

interface PanelNode {
  id: string;
  name: string;
  type: string;
  continuity: Continuity;
  kind: "entity" | "chunk";
  dimmed: boolean;
  highlighted: boolean;
}

interface PanelLink {
  source: string;
  target: string;
  relation: string;
  onPath: boolean;
  dimmed: boolean;
}

export function GraphPanel({
  graph,
  highlightId,
  onNodeHover,
  onNodeClick,
  onReset,
}: {
  graph: GraphState;
  highlightId: string | null;
  onNodeHover: (nodeId: string | null) => void;
  onNodeClick: (nodeId: string) => void;
  onReset: () => void;
}) {
  const containerRef = useRef<HTMLDivElement>(null);
  const [size, setSize] = useState({ width: 0, height: 0 });

  useEffect(() => {
    const el = containerRef.current;
    if (!el) return;
    const observer = new ResizeObserver(([entry]) =>
      setSize({ width: entry.contentRect.width, height: entry.contentRect.height }),
    );
    observer.observe(el);
    return () => observer.disconnect();
  }, []);

  // force-graph mutates its data objects (simulation coords) — feed it copies,
  // keyed so React re-renders only when the underlying graph actually changes.
  const data = useMemo(
    () => ({
      nodes: graph.nodes.map<PanelNode>((n) => ({
        id: n.id,
        name: n.name,
        type: n.type,
        continuity: n.continuity,
        kind: n.kind,
        dimmed: n.lastTurn < graph.turn,
        highlighted: n.id === highlightId,
      })),
      links: graph.links.map<PanelLink>((l) => ({
        source: l.source,
        target: l.target,
        relation: l.relation,
        onPath: l.onPath,
        dimmed: l.lastTurn < graph.turn,
      })),
    }),
    [graph, highlightId],
  );

  return (
    <div ref={containerRef} className="relative h-full w-full overflow-hidden">
      {graph.nodes.length === 0 ? (
        <div className="flex h-full items-center justify-center">
          <p className="max-w-xs text-center text-sm text-zinc-400">
            The graph lights up as the agent works — ask something relational to
            watch it traverse.
          </p>
        </div>
      ) : (
        <ForceGraph2D
          width={size.width}
          height={size.height}
          graphData={data}
          nodeId="id"
          nodeCanvasObject={(node, ctx, scale) => drawNode(placedNode(node), ctx, scale)}
          nodePointerAreaPaint={(node, color, ctx) => {
            const n = placedNode(node);
            ctx.fillStyle = color;
            ctx.beginPath();
            ctx.arc(n.x, n.y, 8, 0, 2 * Math.PI);
            ctx.fill();
          }}
          linkColor={(l) => (panelLink(l).dimmed ? "#3f3f4620" : "#a1a1aa66")}
          linkWidth={(l) => (panelLink(l).onPath && !panelLink(l).dimmed ? 2.5 : 1)}
          linkDirectionalParticles={(l) => (panelLink(l).onPath && !panelLink(l).dimmed ? 2 : 0)}
          linkDirectionalParticleSpeed={0.004}
          nodeLabel={(node) => {
            const n = placedNode(node);
            return `${n.name} · ${n.kind === "chunk" ? `§ ${n.name}` : n.type} · ${n.continuity}`;
          }}
          onNodeHover={(node) => onNodeHover(node ? placedNode(node).id : null)}
          onNodeClick={(node) => onNodeClick(placedNode(node).id)}
          cooldownTicks={120}
          backgroundColor="rgba(0,0,0,0)"
        />
      )}
      {graph.nodes.length > 0 && (
        <button
          onClick={onReset}
          className="absolute right-3 top-3 rounded-md border border-zinc-300 bg-white/80 px-2.5 py-1 text-xs text-zinc-600 backdrop-blur hover:bg-white dark:border-zinc-700 dark:bg-zinc-900/80 dark:text-zinc-300 dark:hover:bg-zinc-900"
        >
          Clear graph
        </button>
      )}
    </div>
  );
}

// next/dynamic erases react-force-graph's generics, so its callbacks hand us
// loosely-typed objects. Cast once here, not per callback. Note: at runtime
// force-graph replaces link.source/target strings with node object references —
// only read PanelLink's own fields (dimmed, onPath, relation) through this.
function panelLink(l: unknown): PanelLink {
  return l as PanelLink;
}

function placedNode(n: unknown): PanelNode & { x: number; y: number } {
  return n as PanelNode & { x: number; y: number };
}

function drawNode(node: PanelNode & { x: number; y: number }, ctx: CanvasRenderingContext2D, scale: number) {
  const hue = CONTINUITY_THEME[node.continuity]?.hex ?? "#71717a";
  const alpha = node.dimmed && !node.highlighted ? "44" : "ff";

  let radius: number;
  if (node.kind === "chunk") {
    // satellites: small squares — a "document", not an entity
    radius = 3;
    ctx.fillStyle = `${hue}${alpha}`;
    ctx.fillRect(node.x - radius, node.y - radius, radius * 2, radius * 2);
  } else {
    radius = 5;
    ctx.beginPath();
    ctx.arc(node.x, node.y, radius, 0, 2 * Math.PI);
    ctx.fillStyle = `${hue}${alpha}`;
    ctx.fill();
    if (!node.dimmed || node.highlighted) {
      ctx.strokeStyle = `${hue}55`;
      ctx.lineWidth = 3;
      ctx.stroke();
    }
  }

  if (node.highlighted) {
    ctx.beginPath();
    ctx.arc(node.x, node.y, radius + 5, 0, 2 * Math.PI);
    ctx.strokeStyle = hue;
    ctx.lineWidth = 2;
    ctx.stroke();
  }

  if (node.kind === "entity" && (scale > 1.2 || !node.dimmed)) {
    ctx.font = `${Math.max(10 / scale, 2)}px sans-serif`;
    ctx.textAlign = "center";
    ctx.textBaseline = "top";
    ctx.fillStyle = node.dimmed ? "#a1a1aa66" : "#52525b";
    ctx.fillText(node.name, node.x, node.y + radius + 2);
  }
}
