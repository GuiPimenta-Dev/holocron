// The agent's SSE event protocol (api/app.py) as types + a chunk-safe parser.
// This file is the frontend's single source of truth for the wire format.

export type Continuity = "canon" | "legends";

export interface Citation {
  title: string;
  name: string;
  continuity: Continuity;
  section?: string;
}

export type AgentEvent =
  | { type: "tool_call"; name: string; args: Record<string, unknown> }
  | { type: "tool_result"; name: string; result: unknown }
  | { type: "answer_delta"; text: string }
  | { type: "done"; citations: Citation[]; trace_id: string | null }
  | { type: "error"; message: string };

/**
 * Parse an SSE byte stream into AgentEvents.
 *
 * Chunk-boundary safe: frames may be split anywhere (mid-line, mid-UTF-8
 * character) across chunks; the parser buffers until a full `\n\n` frame.
 */
export async function* parseSSE(chunks: AsyncIterable<Uint8Array>): AsyncGenerator<AgentEvent> {
  const decoder = new TextDecoder();
  let buffer = "";
  for await (const chunk of chunks) {
    buffer += decoder.decode(chunk, { stream: true });
    let sep;
    while ((sep = buffer.indexOf("\n\n")) !== -1) {
      const frame = buffer.slice(0, sep);
      buffer = buffer.slice(sep + 2);
      const event = parseFrame(frame);
      if (event) yield event;
    }
  }
}

function parseFrame(frame: string): AgentEvent | null {
  let type = "";
  let data = "";
  for (const line of frame.split("\n")) {
    if (line.startsWith("event: ")) type = line.slice(7).trim();
    else if (line.startsWith("data: ")) data += line.slice(6);
  }
  if (!type || !data) return null;
  return { type, ...JSON.parse(data) } as AgentEvent;
}

/** POST a question and stream the agent's events. */
export async function* askAgent(
  apiBase: string,
  question: string,
  continuity: Continuity | null = null,
  signal?: AbortSignal,
): AsyncGenerator<AgentEvent> {
  const res = await fetch(`${apiBase}/ask`, {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify({ question, continuity }),
    signal,
  });
  if (!res.ok || !res.body) {
    throw new Error(`API error: ${res.status} ${res.statusText}`);
  }
  yield* parseSSE(iterate(res.body));
}

async function* iterate(body: ReadableStream<Uint8Array>): AsyncIterable<Uint8Array> {
  const reader = body.getReader();
  try {
    while (true) {
      const { done, value } = await reader.read();
      if (done) break;
      if (value) yield value;
    }
  } finally {
    reader.releaseLock();
  }
}
