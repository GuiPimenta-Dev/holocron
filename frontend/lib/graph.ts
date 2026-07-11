// Pure reducer: agent events in, graph data out. No React, no rendering —
// this is the unit-testable core of the live traversal panel (spec #26).

import type { AgentEvent, Citation, Continuity } from "./events";

export interface GraphNode {
  id: string; // entities: wiki title; chunk satellites: "<title>#<section>"
  name: string;
  type: string; // entity type (Character, Celestialbody...); "Entity" when unknown
  continuity: Continuity;
  kind: "entity" | "chunk";
  section?: string; // chunk satellites only
  properties?: Record<string, string>; // infobox properties, when get_entity delivered them
  lastTurn: number; // dimmed by the renderer when < GraphState.turn
}

export interface GraphLink {
  source: string;
  target: string;
  relation: string;
  onPath: boolean; // part of a path_between result — rendered highlighted
  lastTurn: number;
}

export interface GraphState {
  turn: number; // current question number, 1-based
  nodes: GraphNode[];
  links: GraphLink[];
}

export function emptyGraph(): GraphState {
  return { turn: 0, nodes: [], links: [] };
}

/** Start a new question: everything existing becomes "previous" (dimmed). */
export function beginTurn(state: GraphState): GraphState {
  return { ...state, turn: state.turn + 1 };
}

/** Fold one agent event into the graph. Non-graph events pass through untouched. */
export function applyEvent(state: GraphState, event: AgentEvent): GraphState {
  if (event.type !== "tool_result") return state;
  switch (event.name) {
    case "get_entity":
      return foldEntities(state, event.result);
    case "get_relations":
      return foldRelations(state, event.result);
    case "path_between":
      return foldPaths(state, event.result);
    case "search_chunks":
      return foldChunks(state, event.result);
    default:
      return state; // run_cypher rows are arbitrary — not graphable
  }
}

/** The graph node a done-event citation points at (chat ↔ graph cross-highlight). */
export function citationNodeId(citation: Pick<Citation, "title" | "section">): string {
  return citation.section ? `${citation.title}#${citation.section}` : citation.title;
}

export interface NodeDetails {
  node: GraphNode;
  owner: GraphNode | null; // chunk satellites: the entity this excerpt belongs to
  properties: Record<string, string>;
  outgoing: GraphLink[];
  incoming: GraphLink[];
}

/** Everything the stream has delivered about one node (decision 3: no new endpoints). */
export function nodeDetails(state: GraphState, nodeId: string): NodeDetails | null {
  const node = state.nodes.find((n) => n.id === nodeId);
  if (!node) return null;
  const tether = node.kind === "chunk" ? state.links.find((l) => l.source === nodeId) : undefined;
  return {
    node,
    owner: tether ? (state.nodes.find((n) => n.id === tether.target) ?? null) : null,
    properties: node.properties ?? {},
    outgoing: state.links.filter((l) => l.source === nodeId && l.relation !== "EXCERPT_OF"),
    incoming: state.links.filter((l) => l.target === nodeId && l.relation !== "EXCERPT_OF"),
  };
}

/** The chat question the Ask-about button pre-fills — continuity-explicit for Legends twins. */
export function askAboutQuestion(details: NodeDetails): string {
  const subject = details.owner ?? details.node;
  const suffix = subject.continuity === "legends" ? " in Legends" : "";
  return `Tell me about ${subject.name}${suffix}`;
}

interface EntityResult {
  title: string;
  name: string;
  type: string;
  continuity: Continuity;
  properties?: Record<string, string>;
}

interface RelationResult {
  relation: string;
  other_title: string;
  other_type: string;
  other_continuity: Continuity;
}

// the get_relations center entity carries no `type` on the wire (EntityRelations)
interface RelationsResult {
  title: string;
  name: string;
  continuity: Continuity;
  outgoing: RelationResult[];
  incoming: RelationResult[];
}

interface PathResult {
  entities: string[];
  steps: { source: string; relation: string; target: string }[];
}

interface ChunkResult {
  title: string;
  name: string;
  section: string;
  continuity: Continuity;
}

function foldEntities(state: GraphState, result: unknown): GraphState {
  let g = state;
  for (const e of asArray<EntityResult>(result)) {
    g = upsertNode(g, {
      id: e.title,
      name: e.name,
      type: e.type,
      continuity: e.continuity,
      properties: e.properties,
    });
  }
  return g;
}

// ponytail: hub entities (Anakin, Tatooine) have up to 50 incoming edges — the
// full fan is an unreadable hairball on canvas. Outgoing edges are what the
// agent reasons with for "X of/by Y" questions; incoming get a readability cap.
// Raise it (or make it a UI control) if a question ever hinges on the tail.
export const INCOMING_RENDER_CAP = 8;

function foldRelations(state: GraphState, result: unknown): GraphState {
  let g = state;
  for (const e of asArray<RelationsResult>(result)) {
    g = upsertNode(g, { id: e.title, name: e.name, type: "Entity", continuity: e.continuity });
    for (const rel of e.outgoing ?? []) {
      g = upsertNode(g, farEnd(rel));
      g = upsertLink(g, { source: e.title, target: rel.other_title, relation: rel.relation, onPath: false });
    }
    for (const rel of (e.incoming ?? []).slice(0, INCOMING_RENDER_CAP)) {
      g = upsertNode(g, farEnd(rel));
      g = upsertLink(g, { source: rel.other_title, target: e.title, relation: rel.relation, onPath: false });
    }
  }
  return g;
}

function foldPaths(state: GraphState, result: unknown): GraphState {
  let g = state;
  for (const path of asArray<PathResult>(result)) {
    for (const title of path.entities ?? []) {
      g = upsertNode(g, { id: title, name: baseName(title), type: "Entity", continuity: continuityOf(title) });
    }
    for (const step of path.steps ?? []) {
      g = upsertLink(g, { source: step.source, target: step.target, relation: step.relation, onPath: true });
    }
  }
  return g;
}

function foldChunks(state: GraphState, result: unknown): GraphState {
  let g = state;
  for (const c of asArray<ChunkResult>(result)) {
    // the owning entity node hosts the satellite — create it if the graph
    // tools never touched it (vector-only questions must not render empty)
    g = upsertNode(g, { id: c.title, name: c.name, type: "Entity", continuity: c.continuity });
    const satId = citationNodeId(c); // one owner for the "<title>#<section>" scheme
    g = upsertNode(g, {
      id: satId,
      name: c.section,
      type: "Chunk",
      continuity: c.continuity,
      kind: "chunk",
      section: c.section,
    });
    // UI-only tether, not a Neo4j edge — the SCREAMING_SNAKE set is infobox-derived
    g = upsertLink(g, { source: satId, target: c.title, relation: "EXCERPT_OF", onPath: false });
  }
  return g;
}

function farEnd(rel: RelationResult): Omit<GraphNode, "kind" | "lastTurn"> {
  return {
    id: rel.other_title,
    name: baseName(rel.other_title),
    type: rel.other_type,
    continuity: rel.other_continuity,
  };
}

function baseName(title: string): string {
  return title.replace(/\/Legends$/, "");
}

function continuityOf(title: string): Continuity {
  return title.endsWith("/Legends") ? "legends" : "canon";
}

function asArray<T>(result: unknown): T[] {
  return Array.isArray(result) ? (result as T[]) : [];
}

function upsertNode(
  state: GraphState,
  node: Omit<GraphNode, "kind" | "lastTurn"> & { kind?: GraphNode["kind"]; section?: string },
): GraphState {
  const existing = state.nodes.find((n) => n.id === node.id);
  if (existing) {
    const upgraded: GraphNode = {
      ...existing,
      // never downgrade a typed node to the unknown placeholder; kind is fixed at creation
      type: node.type !== "Entity" ? node.type : existing.type,
      // last full write wins: get_entity always ships the whole infobox, and a
      // sighting WITHOUT properties (relations, paths) must not erase a full one
      properties: node.properties ?? existing.properties,
      lastTurn: state.turn,
    };
    return { ...state, nodes: state.nodes.map((n) => (n.id === node.id ? upgraded : n)) };
  }
  return { ...state, nodes: [...state.nodes, { kind: "entity", ...node, lastTurn: state.turn }] };
}

function upsertLink(state: GraphState, link: Omit<GraphLink, "lastTurn">): GraphState {
  const key = (l: { source: string; target: string; relation: string }) =>
    `${l.source}\u001F${l.relation}\u001F${l.target}`;
  const existing = state.links.find((l) => key(l) === key(link));
  if (existing) {
    const updated: GraphLink = { ...existing, onPath: existing.onPath || link.onPath, lastTurn: state.turn };
    return { ...state, links: state.links.map((l) => (key(l) === key(link) ? updated : l)) };
  }
  return { ...state, links: [...state.links, { ...link, lastTurn: state.turn }] };
}
