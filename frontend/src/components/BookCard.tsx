import { Link } from "react-router-dom";
import type { CorpusSummary } from "@/lib/api";
import { formatNumber, formatYear } from "@/lib/format";

/** Muted book-cloth colours; a corpus always gets the same one (hash of its slug). */
const CLOTH = [
  ["#2f4858", "#1f3341"], // slate blue
  ["#7a2e2e", "#5c2020"], // oxblood
  ["#2f5d3a", "#213f28"], // forest
  ["#8a6414", "#66490d"], // mustard
  ["#4a3a6e", "#332852"], // plum
  ["#3d434b", "#2a2f36"], // charcoal
  ["#1e5a6e", "#143f4e"], // teal
  ["#6b4a2b", "#4d351f"], // leather brown
];

export function clothFor(slug: string): [string, string] {
  let hash = 0;
  for (const ch of slug) hash = (hash * 31 + ch.charCodeAt(0)) >>> 0;
  const [a, b] = CLOTH[hash % CLOTH.length];
  return [a, b];
}

export function BookCard({ corpus, open = false }: { corpus: CorpusSummary; open?: boolean }) {
  const [cloth, clothDark] = clothFor(corpus.slug);
  const meta = [
    ["documents", corpus.n_documents],
    ["passages", corpus.n_chunks],
    ["entities", corpus.n_entities],
    ["relations", corpus.n_edges],
  ] as const;
  return (
    <Link to={`/corpus/${corpus.slug}`} className={`book group${open ? " is-open" : ""}`} aria-label={`Open ${corpus.title}`}>
      <div className="book__body">
        {/* pages block (visible when the cover opens) */}
        <div className="book__pages">
          <div className="book__page">
            <div className="font-mono text-[10px] uppercase tracking-[0.18em] text-muted">
              {corpus.author || "Anonymous"}
              {corpus.year !== null ? ` · ${formatYear(corpus.year)}` : ""}
            </div>
            <h3 className="mt-1 text-[15px] leading-snug">{corpus.title}</h3>
            {corpus.genre && <div className="mt-0.5 font-mono text-[10px] uppercase tracking-wider text-muted">{corpus.genre}</div>}
            <dl className="mt-3 space-y-0.5 border-t border-line-soft pt-2">
              {meta.map(([label, value]) => (
                <div key={label} className="flex min-w-0 items-baseline justify-between gap-2">
                  <dt className="font-mono text-[9.5px] uppercase tracking-wider text-muted">{label}</dt>
                  <dd className="font-mono text-[11.5px] text-ink">{formatNumber(value)}</dd>
                </div>
              ))}
            </dl>
            {corpus.excerpt && (
              <p className="book__excerpt mt-3 font-serif text-[12.5px] leading-[1.55] text-ink-2">
                <span className="book__initial">{corpus.excerpt.charAt(0)}</span>
                {corpus.excerpt.slice(1)}
              </p>
            )}
            <div className="book__cta">Open book <span aria-hidden="true">→</span></div>
          </div>
        </div>
        {/* cover: front face + inside face */}
        <div className="book__cover" style={{ ["--cloth" as string]: cloth, ["--cloth-dark" as string]: clothDark }}>
          <div className="book__face book__face--front">
            <div className="book__spine-stripe" />
            <div className="book__front-content">
              <div className="book__rule" />
              <h3 className="book__title">{corpus.title}</h3>
              <div className="book__rule" />
              <div className="book__author">{corpus.author || " "}</div>
              {corpus.year !== null && <div className="book__year">{formatYear(corpus.year)}</div>}
            </div>
            <div className="book__emblem">
              {corpus.language.toUpperCase()}
            </div>
          </div>
          <div className="book__face book__face--inside">
            <div className="book__inside">
              <div className="book__inside-title">Mentioned often</div>
              <ol className="book__cast">
                {corpus.highlights.slice(0, 6).map((name, index) => (
                  <li key={name}>
                    <span className="book__cast-index">{index + 1}</span>
                    <span className="book__cast-name">{name}</span>
                  </li>
                ))}
                {corpus.highlights.length === 0 && <li className="book__cast-name">—</li>}
              </ol>
              <div className="book__inside-foot">
                {formatNumber(corpus.n_entities)} entities · {formatNumber(corpus.n_mentions)} mentions
                <br />
                window {corpus.window} · {corpus.extractor || "—"}
                {corpus.source && (
                  <>
                    <br />
                    <span className="book__source">{corpus.source}</span>
                  </>
                )}
              </div>
            </div>
          </div>
        </div>
      </div>
      <div className="book__shadow" />
    </Link>
  );
}
