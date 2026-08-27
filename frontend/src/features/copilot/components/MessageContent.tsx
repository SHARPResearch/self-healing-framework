import type { ReactNode } from "react";

// Handles only the handful of patterns the mock responses actually emit
// ("## heading", "- bullet", "_caption_", plain paragraph) -- not a real
// markdown parser, deliberately, to avoid adding a new dependency for a
// prototype demo.
function renderChunk(chunk: string, chunkKey: string): ReactNode {
  const lines = chunk.split("\n").filter((l) => l.trim().length > 0);
  const nodes: ReactNode[] = [];
  let bulletBuf: string[] = [];

  const flushBullets = (key: string) => {
    if (bulletBuf.length === 0) return;
    nodes.push(
      <ul key={key} className="ml-4 list-disc space-y-0.5 text-sm text-white/75">
        {bulletBuf.map((b, i) => (
          <li key={i}>{b}</li>
        ))}
      </ul>,
    );
    bulletBuf = [];
  };

  lines.forEach((line, i) => {
    if (line.startsWith("## ")) {
      flushBullets(`b-${i}`);
      nodes.push(
        <h4 key={i} className="text-xs font-semibold tracking-wide text-white/90 uppercase first:mt-0">
          {line.slice(3)}
        </h4>,
      );
    } else if (line.startsWith("- ")) {
      bulletBuf.push(line.slice(2));
    } else if (line.startsWith("_") && line.endsWith("_")) {
      flushBullets(`b-${i}`);
      nodes.push(
        <p key={i} className="text-[11px] text-white/40 italic">
          {line.slice(1, -1)}
        </p>,
      );
    } else {
      flushBullets(`b-${i}`);
      nodes.push(
        <p key={i} className="text-sm leading-relaxed text-white/75">
          {line}
        </p>,
      );
    }
  });
  flushBullets("b-end");

  return (
    <div key={chunkKey} className="space-y-1.5">
      {nodes}
    </div>
  );
}

export function MessageContent({ chunks }: { chunks: string[] }) {
  return <div className="space-y-3">{chunks.map((chunk, i) => renderChunk(chunk, `c-${i}`))}</div>;
}
