import { Link } from "react-router-dom";
import type { CorpusSummary } from "@/lib/api";
import { formatDate, formatNumber, formatYear } from "@/lib/format";

export function CorpusCard({ corpus }: { corpus: CorpusSummary }) {
  return (
    <Link to={`/corpus/${corpus.slug}`} className="panel group flex flex-col gap-3 p-5 transition-colors hover:border-ink-2">
      <div>
        <h3 className="text-[20px] leading-tight group-hover:text-accent-deep">{corpus.title}</h3>
        {(corpus.author || corpus.year !== null) && (
          <div className="mt-0.5 text-[13px] text-ink-2">
            {corpus.author}
            {corpus.author && corpus.year !== null ? " · " : ""}
            {formatYear(corpus.year)}
          </div>
        )}
        {corpus.genre && <div className="mt-1 font-mono text-[11px] uppercase tracking-wider text-muted">{corpus.genre}</div>}
      </div>
      {corpus.description && <p className="line-clamp-3 text-[14px] text-ink-2">{corpus.description}</p>}
      <dl className="mt-auto grid grid-cols-4 gap-2 border-t border-line-soft pt-3">
        {[
          ["documents", corpus.n_documents],
          ["chunks", corpus.n_chunks],
          ["entities", corpus.n_entities],
          ["edges", corpus.n_edges],
        ].map(([label, value]) => (
          <div key={String(label)}>
            <dt className="font-mono text-[10px] uppercase tracking-wider text-muted">{label}</dt>
            <dd className="font-mono text-[14px] text-ink">{formatNumber(Number(value))}</dd>
          </div>
        ))}
      </dl>
      <div className="flex items-center justify-between font-mono text-[11px] text-muted">
        <span>{corpus.source || "—"}</span>
        <span>{formatDate(corpus.processed_at ?? corpus.created_at)}</span>
      </div>
    </Link>
  );
}
