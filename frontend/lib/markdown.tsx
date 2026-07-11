// Minimal markdown for agent answers: **bold**, ## headings, - lists, paragraphs.
// This is the OBSERVED output subset (the SYSTEM_PROMPT doesn't pin a format);
// anything else renders as literal text, safely. A full md library would be a
// dependency for four rules (ponytail: extend when observed output grows).
import type { ReactNode } from "react";

export function Markdown({ text }: { text: string }) {
  const blocks = text.split(/\n\n+/).filter((b) => b.trim());
  return (
    <>
      {blocks.map((block, i) => (
        <MarkdownBlock key={i} block={block.trim()} />
      ))}
    </>
  );
}

function MarkdownBlock({ block }: { block: string }) {
  if (block.startsWith("## ")) {
    return <h3 className="mt-4 mb-1 text-base font-semibold text-parchment">{inline(block.slice(3))}</h3>;
  }
  const lines = block.split("\n");
  if (lines.every((l) => /^\s*[-*] /.test(l))) {
    return (
      <ul className="my-1.5 flex list-disc flex-col gap-1 pl-5 marker:text-parchment-faint">
        {lines.map((l, i) => (
          <li key={i}>{inline(l.replace(/^\s*[-*] /, ""))}</li>
        ))}
      </ul>
    );
  }
  return <p className="my-1.5">{inline(block)}</p>;
}

function inline(text: string): ReactNode[] {
  // **bold** only — the sole inline mark the agent emits
  return text.split(/(\*\*[^*]+\*\*)/).map((part, i) =>
    part.startsWith("**") && part.endsWith("**") ? (
      <strong key={i} className="font-semibold text-parchment">
        {part.slice(2, -2)}
      </strong>
    ) : (
      part
    ),
  );
}
