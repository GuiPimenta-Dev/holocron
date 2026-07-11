// Reducer tested against REAL captured streams (get_entity, get_relations,
// path_between shapes) — the same fixtures doctrine as everything else.
import { readFileSync } from "node:fs";
import { join } from "node:path";
import { describe, expect, it } from "vitest";
import { parseSSE, type AgentEvent } from "./events";
import { applyEvent, beginTurn, emptyGraph, type GraphState } from "./graph";

async function* chunks(bytes: Uint8Array): AsyncIterable<Uint8Array> {
  yield bytes;
}

async function loadEvents(fixture: string): Promise<AgentEvent[]> {
  const bytes = readFileSync(join(__dirname, "__fixtures__", fixture));
  const events: AgentEvent[] = [];
  for await (const ev of parseSSE(chunks(bytes))) events.push(ev);
  return events;
}

async function reduce(fixture: string, state?: GraphState): Promise<GraphState> {
  let g = state ?? beginTurn(emptyGraph());
  for (const ev of await loadEvents(fixture)) g = applyEvent(g, ev);
  return g;
}

describe("graph reducer over real streams", () => {
  it("get_entity spawns one node per continuity, typed and titled", async () => {
    const g = await reduce("ask-stream.sse"); // Kit Fisto question: get_entity
    const kit = g.nodes.find((n) => n.id === "Kit Fisto");
    const kitLegends = g.nodes.find((n) => n.id === "Kit Fisto/Legends");
    expect(kit).toMatchObject({ name: "Kit Fisto", type: "Character", continuity: "canon" });
    expect(kitLegends).toMatchObject({ continuity: "legends" });
  });

  it("get_relations fans out named edges to typed far ends", async () => {
    const g = await reduce("ask-relations.sse"); // Anakin trainers question
    const trained = g.links.filter((l) => l.relation === "TRAINED_BY" && l.source === "Anakin Skywalker");
    expect(trained.map((l) => l.target)).toContain("Obi-Wan Kenobi");
    const obiwan = g.nodes.find((n) => n.id === "Obi-Wan Kenobi");
    expect(obiwan).toMatchObject({ type: "Character", continuity: "canon" });
  });

  it("path_between draws every step and marks the path links", async () => {
    const g = await reduce("ask-path.sse"); // Boba Fett -> Jedi Order paths
    const pathLinks = g.links.filter((l) => l.onPath);
    expect(pathLinks.length).toBeGreaterThan(0);
    expect(g.nodes.some((n) => n.id === "Aurra Sing")).toBe(true);
    // path-only nodes get continuity from their title suffix
    expect(g.nodes.find((n) => n.id === "Aurra Sing")?.continuity).toBe("canon");
  });

  it("accumulates across turns and dims the previous ones", async () => {
    const first = await reduce("ask-stream.sse");
    const second = await reduce("ask-relations.sse", beginTurn(first));
    const kit = second.nodes.find((n) => n.id === "Kit Fisto");
    const anakin = second.nodes.find((n) => n.id === "Anakin Skywalker");
    expect(kit?.lastTurn).toBe(1);
    expect(anakin?.lastTurn).toBe(2);
    expect(second.turn).toBe(2); // renderer dims lastTurn < turn
    expect(second.nodes.length).toBeGreaterThan(first.nodes.length);
  });

  it("re-touching a node in a later turn un-dims it without duplicating", async () => {
    const once = await reduce("ask-relations.sse");
    const twice = await reduce("ask-relations.sse", beginTurn(once));
    const anakins = twice.nodes.filter((n) => n.id === "Anakin Skywalker");
    expect(anakins).toHaveLength(1);
    expect(anakins[0].lastTurn).toBe(2);
  });

  it("merging never downgrades a typed node to unknown", async () => {
    // "Human" is a typeless path node in ask-path.sse and a typed SPECIES far
    // end in ask-relations.sse — the second pass must upgrade, never downgrade
    const pathOnly = await reduce("ask-path.sse");
    expect(pathOnly.nodes.find((n) => n.id === "Human")?.type).toBe("Entity");
    const g = await reduce("ask-relations.sse", beginTurn(pathOnly));
    expect(g.nodes.find((n) => n.id === "Human")?.type).not.toBe("Entity");
  });

  it("caps incoming edges per entity so hubs don't hairball", async () => {
    const g = await reduce("ask-relations.sse"); // Anakin has ~50 incoming per continuity
    for (const title of ["Anakin Skywalker", "Anakin Skywalker/Legends"]) {
      const incoming = g.links.filter((l) => l.target === title);
      expect(incoming.length).toBeLessThanOrEqual(8);
    }
    // outgoing survives untouched — it's what relational answers hang on
    expect(g.links.some((l) => l.source === "Anakin Skywalker" && l.relation === "TRAINED_BY")).toBe(true);
  });

  it("run_cypher and chunk results are ignored (not graphable yet)", async () => {
    const g = await reduce("ask-stream.sse");
    // the Kit Fisto stream also called search_chunks — no satellite nodes in this ticket
    expect(g.nodes.every((n) => n.kind === "entity")).toBe(true);
  });
});
