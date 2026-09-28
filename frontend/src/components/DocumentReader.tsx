import { Fragment, type ReactNode } from "react";
import type { ChunkOut, MentionOut } from "@/lib/api";
import { colorOf, withAlpha, type ColorMap } from "@/lib/colors";

interface Props {
  chunks: ChunkOut[];
  colors: ColorMap;
  activeEntities: Set<number>;
  onSelectEntity: (id: number) => void;
  header?: ReactNode;
  footer?: ReactNode;
}

/** Render chunk text with entity mention spans highlighted (non-overlapping, left to right). */
export function HighlightedText({ chunk, colors, activeEntities, onSelectEntity }: { chunk: ChunkOut; colors: ColorMap; activeEntities: Set<number>; onSelectEntity: (id: number) => void }) {
  const spans = [...chunk.mentions].sort((a, b) => a.start - b.start);
  const parts: ReactNode[] = [];
  let cursor = 0;
  spans.forEach((m: MentionOut, i) => {
    if (m.start < cursor) return; // overlapping mention: skip
    if (m.start > cursor) parts.push(<Fragment key={`t${i}`}>{chunk.text.slice(cursor, m.start)}</Fragment>);
    const color = colorOf(colors, m.label);
    const active = activeEntities.has(m.entity_id);
    parts.push(
      <button
        key={`m${i}`}
        type="button"
        onClick={() => onSelectEntity(m.entity_id)}
        title={m.label}
        className="rounded-sm px-0.5 font-medium transition-colors"
        style={{
          background: withAlpha(color, active ? 0.35 : 0.14),
          boxShadow: active ? `inset 0 -2px 0 ${color}` : `inset 0 -1px 0 ${withAlpha(color, 0.6)}`,
          color: "#1f2328",
        }}
      >
        {chunk.text.slice(m.start, m.end)}
      </button>,
    );
    cursor = m.end;
  });
  if (cursor < chunk.text.length) parts.push(<Fragment key="tail">{chunk.text.slice(cursor)}</Fragment>);
  return <p className="font-serif text-[15.5px] leading-[1.7] text-ink">{parts}</p>;
}

export function DocumentReader({ chunks, colors, activeEntities, onSelectEntity, header, footer }: Props) {
  let lastDocument: number | null = null;
  return (
    <div className="flex h-full flex-col">
      {header}
      <div className="flex-1 overflow-y-auto">
        {chunks.map((chunk) => {
          const showTitle = chunk.document_id !== lastDocument;
          lastDocument = chunk.document_id;
          return (
            <article key={chunk.id} className="border-b border-line-soft px-4 py-3">
              {showTitle && <div className="mb-2 font-mono text-[11px] uppercase tracking-wider text-muted">{chunk.document_title}</div>}
              <HighlightedText chunk={chunk} colors={colors} activeEntities={activeEntities} onSelectEntity={onSelectEntity} />
              <div className="mt-1 font-mono text-[10px] text-muted">§ {chunk.position + 1}</div>
            </article>
          );
        })}
        {footer}
      </div>
    </div>
  );
}
