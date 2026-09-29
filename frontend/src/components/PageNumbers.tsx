import { useState } from "react";

interface Props {
  pages: number[];
  current: number;
  onGoTo: (page: number) => void;
  /** How many numbers to show before folding the rest behind "+N more". */
  limit?: number;
  className?: string;
}

/** A run of page numbers, like a book index entry; the current page is marked. */
export function PageNumbers({ pages, current, onGoTo, limit = 24, className = "" }: Props) {
  const [expanded, setExpanded] = useState(false);
  const shown = expanded ? pages : pages.slice(0, limit);
  if (pages.length === 0) return <span className="font-mono text-[11px] text-muted">—</span>;
  return (
    <span className={`inline-flex flex-wrap gap-x-1 gap-y-0.5 font-mono text-[11.5px] leading-5 ${className}`}>
      {shown.map((page) => (
        <button key={page} type="button" className={`pageno ${page === current ? "pageno--current" : ""}`} onClick={() => onGoTo(page)} title={`Go to page ${page}`}>
          {page}
        </button>
      ))}
      {!expanded && pages.length > limit && (
        <button type="button" className="text-muted hover:text-ink" onClick={() => setExpanded(true)}>
          +{pages.length - limit} more
        </button>
      )}
    </span>
  );
}

/** The first page after ``current`` in ``pages`` (wrapping to the first page). */
export function nextPageAfter(pages: number[], current: number): number | null {
  if (pages.length === 0) return null;
  return pages.find((p) => p > current) ?? pages[0];
}
