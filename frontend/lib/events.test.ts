// Parser tested against a REAL captured stream (curl -N of POST /ask, saved raw) —
// same doctrine as the backend: real fixtures, no synthetic shapes.
import { readFileSync } from "node:fs";
import { join } from "node:path";
import { describe, expect, it } from "vitest";
import { parseSSE, type AgentEvent } from "./events";

const FIXTURE = readFileSync(join(__dirname, "__fixtures__", "ask-stream.sse"));

async function* chunked(bytes: Uint8Array, size: number): AsyncIterable<Uint8Array> {
  for (let i = 0; i < bytes.length; i += size) yield bytes.slice(i, i + size);
}

async function collect(size: number): Promise<AgentEvent[]> {
  const events: AgentEvent[] = [];
  for await (const ev of parseSSE(chunked(FIXTURE, size))) events.push(ev);
  return events;
}

describe("parseSSE over the real captured stream", () => {
  it("yields the agent's event protocol in order", async () => {
    const events = await collect(4096);
    expect(events[0]).toMatchObject({ type: "tool_call", name: "get_entity" });
    const types = events.map((e) => e.type);
    expect(types).toContain("tool_result");
    expect(types).toContain("answer_delta");
    expect(types.at(-1)).toBe("done");
  });

  it("reassembles the answer from deltas", async () => {
    const events = await collect(4096);
    const answer = events
      .filter((e) => e.type === "answer_delta")
      .map((e) => (e.type === "answer_delta" ? e.text : ""))
      .join("");
    expect(answer.toLowerCase()).toContain("nautolan");
  });

  it("carries citations and trace_id on done", async () => {
    const events = await collect(4096);
    const done = events.at(-1);
    if (done?.type !== "done") throw new Error("last event must be done");
    expect(done.citations.length).toBeGreaterThan(0);
    expect(done.citations[0]).toHaveProperty("title");
    expect(done.citations[0]).toHaveProperty("continuity");
    expect(done.trace_id).toBeTruthy();
  });

  it("is chunk-boundary safe: 1-byte chunks parse identically", async () => {
    expect(await collect(1)).toEqual(await collect(65536));
  });
});
