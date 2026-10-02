interface Props {
  page: number;
  pages: number;
  total: number;
  pageSize: number;
  onPage: (page: number) => void;
}

/** Page numbers with the current page, its neighbours, and the first and last page. */
function pageList(page: number, pages: number): Array<number | "…"> {
  const keep = new Set([1, pages, page - 1, page, page + 1].filter((p) => p >= 1 && p <= pages));
  const out: Array<number | "…"> = [];
  let last = 0;
  for (const p of [...keep].sort((a, b) => a - b)) {
    if (p - last > 1) out.push("…");
    out.push(p);
    last = p;
  }
  return out;
}

export function Pagination({ page, pages, total, pageSize, onPage }: Props) {
  if (pages <= 1) return null;
  const first = (page - 1) * pageSize + 1;
  const last = Math.min(page * pageSize, total);
  return (
    <nav className="pagination" aria-label="Pages">
      <span className="font-mono text-[12px] text-muted">
        {first}–{last} of {total}
      </span>
      <div className="flex items-center gap-1">
        <button type="button" className="btn btn-sm" disabled={page <= 1} onClick={() => onPage(page - 1)} aria-label="Previous page">
          ← Prev
        </button>
        {pageList(page, pages).map((p, i) =>
          p === "…" ? (
            <span key={`gap-${i}`} className="px-1 text-muted">
              …
            </span>
          ) : (
            <button key={p} type="button" className={`pagination__page ${p === page ? "is-current" : ""}`} aria-current={p === page ? "page" : undefined} onClick={() => onPage(p)}>
              {p}
            </button>
          ),
        )}
        <button type="button" className="btn btn-sm" disabled={page >= pages} onClick={() => onPage(page + 1)} aria-label="Next page">
          Next →
        </button>
      </div>
    </nav>
  );
}
