import { useMemo } from "react";
import { Link, useLocation, useSearchParams } from "react-router-dom";
import { LINKS } from "@/components/AboutDialog";
import { useLayoutContext } from "@/components/Layout";
import { BookCard } from "@/components/BookCard";
import { Empty, ErrorNote, Spinner } from "@/components/ui";
import { useCorpora } from "@/hooks/useApi";
import { useAuth } from "@/hooks/useAuth";
import { SITE_TITLE, useDocumentMeta } from "@/hooks/useDocumentMeta";
import type { CorpusSummary } from "@/lib/api";
import { LANGUAGE_NAMES, formatNumber } from "@/lib/format";

const SORTS = {
  title: { label: "Title A–Z", compare: (a: CorpusSummary, b: CorpusSummary) => a.title.localeCompare(b.title) },
  author: { label: "Author", compare: (a: CorpusSummary, b: CorpusSummary) => (a.author || "￿").localeCompare(b.author || "￿") || a.title.localeCompare(b.title) },
  oldest: { label: "Year, oldest first", compare: (a: CorpusSummary, b: CorpusSummary) => (a.year ?? 9999) - (b.year ?? 9999) },
  newest: { label: "Year, newest first", compare: (a: CorpusSummary, b: CorpusSummary) => (b.year ?? -9999) - (a.year ?? -9999) },
  entities: { label: "Most entities", compare: (a: CorpusSummary, b: CorpusSummary) => b.n_entities - a.n_entities },
  relations: { label: "Most relations", compare: (a: CorpusSummary, b: CorpusSummary) => b.n_edges - a.n_edges },
  longest: { label: "Longest", compare: (a: CorpusSummary, b: CorpusSummary) => b.n_chunks - a.n_chunks },
  recent: { label: "Recently added", compare: (a: CorpusSummary, b: CorpusSummary) => b.created_at.localeCompare(a.created_at) },
} as const;
type SortKey = keyof typeof SORTS;


/** "Fiction · Gothic" -> "Fiction" (the coarse category used for the filter). */
function category(corpus: CorpusSummary): string {
  return corpus.genre.split("·")[0].trim() || "Other";
}

export function GalleryView() {
  const { openAbout } = useLayoutContext();
  const { data, isLoading, error } = useCorpora(false);
  const { isAdmin } = useAuth();
  const peek = useLocation().hash === "#peek"; // demo/screenshot mode: all books open
  const [params, setParams] = useSearchParams();

  const q = params.get("q") ?? "";
  const genre = params.get("genre") ?? "";
  const lang = params.get("lang") ?? "";
  const sort = (params.get("sort") as SortKey) in SORTS ? (params.get("sort") as SortKey) : "title";
  useDocumentMeta({
    title: SITE_TITLE,
    description: `Explore ${data?.length ? `${formatNumber(data.length)} book${data.length === 1 ? "" : "s"}` : "text corpora"} as networks of the people, places and things they mention. Read page by page, search the text and follow every connection.`,
    path: "/",
  });

  const update = (key: string, value: string) => {
    const next = new URLSearchParams(params);
    if (value) next.set(key, value);
    else next.delete(key);
    setParams(next, { replace: true });
  };

  const categories = useMemo(() => Array.from(new Set((data ?? []).map(category))).sort(), [data]);
  const languages = useMemo(() => Array.from(new Set((data ?? []).map((c) => c.language))).sort(), [data]);

  const shown = useMemo(() => {
    const needle = q.trim().toLowerCase();
    return (data ?? [])
      .filter((c) => !genre || category(c) === genre)
      .filter((c) => !lang || c.language === lang)
      .filter((c) => !needle || `${c.title} ${c.author} ${c.description} ${c.genre}`.toLowerCase().includes(needle))
      .sort(SORTS[sort].compare);
  }, [data, q, genre, lang, sort]);

  const filtered = Boolean(q || genre || lang);
  const totalRelations = (data ?? []).reduce((sum, c) => sum + c.n_edges, 0);

  return (
    <div className="mx-auto max-w-[1600px] px-6 py-8">
      <header className="mb-6 flex flex-wrap items-end justify-between gap-x-10 gap-y-4">
        <div className="max-w-[900px]">
          <h1 className="text-[34px] leading-tight">Book gallery</h1>
          <p className="mt-3 text-[16px] leading-[1.6] text-ink-2">
            Every book on this shelf has been turned into an <em>implicit entity network</em>: entities mentioned close to
            each other are linked, and the strength of a link decays with the distance of their mentions. Hover a book to
            peek inside; open it to explore the network, read the passages behind every relation and search the text.
          </p>
          <p className="mt-2 font-mono text-[11.5px] uppercase tracking-wider text-muted">
            <a className="hover:text-ink" href={LINKS.paper} target="_blank" rel="noreferrer">
              Paper (WWW ’22)
            </a>
            <span className="mx-2">·</span>
            <a className="hover:text-ink" href={LINKS.code} target="_blank" rel="noreferrer">
              Code
            </a>
            <span className="mx-2">·</span>
            <a className="hover:text-ink" href={LINKS.package} target="_blank" rel="noreferrer">
              Python package
            </a>
            <span className="mx-2">·</span>
            <button type="button" className="uppercase tracking-wider hover:text-ink" onClick={openAbout}>
              More info
            </button>
          </p>
        </div>
        {data && (
          <div className="meta whitespace-nowrap">
            {formatNumber(data.length)} books · {formatNumber(data.reduce((sum, c) => sum + c.n_entities, 0))} entities ·{" "}
            {formatNumber(totalRelations)} relations
          </div>
        )}
      </header>

      {/* ---- toolbar: filters & sorting */}
      {data && data.length > 0 && (
        <div className="mb-8 flex flex-wrap items-center gap-3 border-y border-line-soft py-3">
          <input
            className="input w-64"
            placeholder="Filter by title, author or genre…"
            value={q}
            onChange={(e) => update("q", e.target.value)}
            aria-label="Filter books"
          />
          <select className="input w-auto" value={genre} onChange={(e) => update("genre", e.target.value)} aria-label="Genre">
            <option value="">All genres</option>
            {categories.map((c) => (
              <option key={c} value={c}>
                {c}
              </option>
            ))}
          </select>
          <select className="input w-auto" value={lang} onChange={(e) => update("lang", e.target.value)} aria-label="Language">
            <option value="">All languages</option>
            {languages.map((l) => (
              <option key={l} value={l}>
                {LANGUAGE_NAMES[l] ?? l.toUpperCase()}
              </option>
            ))}
          </select>
          <label className="ml-auto flex items-center gap-2 text-[13px] text-muted">
            Sort by
            <select className="input w-auto" value={sort} onChange={(e) => update("sort", e.target.value)} aria-label="Sort books">
              {(Object.keys(SORTS) as SortKey[]).map((key) => (
                <option key={key} value={key}>
                  {SORTS[key].label}
                </option>
              ))}
            </select>
          </label>
          <span className="font-mono text-[12px] text-muted">
            {shown.length} of {data.length}
          </span>
          {filtered && (
            <button type="button" className="btn btn-sm" onClick={() => setParams(new URLSearchParams(sort !== "title" ? { sort } : {}), { replace: true })}>
              Clear
            </button>
          )}
        </div>
      )}

      {isLoading && <Spinner label="Loading books" />}
      {error && <ErrorNote error={error} />}
      {data && data.length === 0 && (
        <Empty>
          No books have been published yet.{" "}
          {isAdmin ? (
            <Link to="/admin" className="text-accent-deep underline">
              Create one in the admin panel.
            </Link>
          ) : (
            "An administrator can add corpora."
          )}
        </Empty>
      )}
      {data && data.length > 0 && shown.length === 0 && <Empty>No books match the current filters.</Empty>}
      {shown.length > 0 && (
        <div className="grid grid-cols-[repeat(auto-fill,minmax(230px,1fr))] justify-items-center gap-x-8 gap-y-12 py-4">
          {shown.map((corpus) => (
            <BookCard key={corpus.slug} corpus={corpus} open={peek} />
          ))}
        </div>
      )}
    </div>
  );
}
