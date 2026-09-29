import { Fragment, type ReactNode } from "react";
import type { ChunkOut, MentionOut } from "@/lib/api";
import { colorOf, withAlpha, type ColorMap } from "@/lib/colors";

interface Props {
  chunk: ChunkOut;
  colors: ColorMap;
  activeEntities: Set<number>;
  onSelectEntity: (id: number) => void;
  /** Search terms to mark inside the plain text (a regex with one capture group). */
  terms?: RegExp | null;
  /** Pointer entered (element given) or left (null) a mention. */
  onHoverEntity?: (id: number | null, element: HTMLElement | null) => void;
  className?: string;
}

/** Escape a string for use inside a RegExp. */
export function escapeRegExp(value: string): string {
  return value.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
}

/** Build the term regex for a free-text query (word tokens, case-insensitive, one capture group). */
export function termsRegex(queryText: string): RegExp | null {
  const tokens = queryText.match(/[\p{L}\p{N}'’-]+/gu)?.filter((t) => t.length > 1) ?? [];
  if (tokens.length === 0) return null;
  return new RegExp(`(${tokens.map(escapeRegExp).join("|")})`, "giu");
}

function markTerms(text: string, terms: RegExp | null | undefined, key: string): ReactNode {
  if (!terms) return <Fragment key={key}>{text}</Fragment>;
  const pieces = text.split(terms);
  if (pieces.length === 1) return <Fragment key={key}>{text}</Fragment>;
  return (
    <Fragment key={key}>
      {pieces.map((piece, i) => (i % 2 === 1 ? <mark key={i}>{piece}</mark> : <Fragment key={i}>{piece}</Fragment>))}
    </Fragment>
  );
}

/** Render chunk text with entity mention spans highlighted (non-overlapping, left to right). */
export function HighlightedText({ chunk, colors, activeEntities, onSelectEntity, terms, onHoverEntity, className }: Props) {
  const spans = [...chunk.mentions].sort((a, b) => a.start - b.start);
  const parts: ReactNode[] = [];
  let cursor = 0;
  spans.forEach((m: MentionOut, i) => {
    if (m.start < cursor) return; // overlapping mention: skip
    if (m.start > cursor) parts.push(markTerms(chunk.text.slice(cursor, m.start), terms, `t${i}`));
    const color = colorOf(colors, m.label);
    const active = activeEntities.has(m.entity_id);
    parts.push(
      <button
        key={`m${i}`}
        type="button"
        onClick={() => onSelectEntity(m.entity_id)}
        onMouseEnter={(e) => onHoverEntity?.(m.entity_id, e.currentTarget)}
        onMouseLeave={() => onHoverEntity?.(null, null)}
        onFocus={(e) => onHoverEntity?.(m.entity_id, e.currentTarget)}
        onBlur={() => onHoverEntity?.(null, null)}
        title={m.label}
        className={`mention rounded-sm px-0.5 font-medium transition-colors ${active ? "mention--active" : ""}`}
        style={{
          background: withAlpha(color, active ? 0.4 : 0.14),
          boxShadow: active ? `inset 0 -2px 0 ${color}` : `inset 0 -1px 0 ${withAlpha(color, 0.6)}`,
          color: "#1f2328",
        }}
      >
        {chunk.text.slice(m.start, m.end)}
      </button>,
    );
    cursor = m.end;
  });
  if (cursor < chunk.text.length) parts.push(markTerms(chunk.text.slice(cursor), terms, "tail"));
  return <p className={className ?? "font-serif text-[15.5px] leading-[1.7] text-ink"}>{parts}</p>;
}
