import { useCallback, useEffect, useRef, useState } from "react";
import { EntityPopover } from "@/components/EntityPopover";
import { HighlightedText } from "@/components/HighlightedText";
import { Empty, ErrorNote, Spinner, Swatch } from "@/components/ui";
import { usePage, usePrefetchPages } from "@/hooks/useApi";
import type { CorpusDetail, DocumentOut } from "@/lib/api";
import { colorOf, type ColorMap } from "@/lib/colors";
import { formatNumber } from "@/lib/format";

interface Props {
  slug: string;
  corpus: CorpusDetail;
  documents: DocumentOut[];
  page: number;
  colors: ColorMap;
  activeEntities: Set<number>;
  terms: RegExp | null;
  onSelectEntity: (id: number) => void;
  onGoTo: (page: number) => void;
  /** The entity under the pointer (after a short delay), or null. */
  onHoverEntity?: (id: number | null) => void;
}

const ON_PAGE_LIMIT = 30;
const HOVER_SHOW_MS = 220;
const HOVER_HIDE_MS = 260;

/** The reader: one page at a time, paper-like, with a running head and a page number. */
export function PageReader({ slug, corpus, documents, page, colors, activeEntities, terms, onSelectEntity, onGoTo, onHoverEntity }: Props) {
  const query = usePage(slug, page, corpus.n_pages > 0);
  usePrefetchPages(slug, page, corpus.n_pages);
  const data = query.data;
  const nPages = corpus.n_pages;
  const [jump, setJump] = useState(String(page));
  const [showAllEntities, setShowAllEntities] = useState(false);
  useEffect(() => {
    setJump(String(page));
    setShowAllEntities(false);
  }, [page]);

  // ---- hover: a mention opens a popover after a short delay and hands the entity to the graph
  const [hover, setHover] = useState<{ id: number; rect: DOMRect } | null>(null);
  const showTimer = useRef<number | null>(null);
  const hideTimer = useRef<number | null>(null);
  const cancelHide = useCallback(() => {
    if (hideTimer.current !== null) window.clearTimeout(hideTimer.current);
    hideTimer.current = null;
  }, []);
  const hideNow = useCallback(() => {
    cancelHide();
    if (showTimer.current !== null) window.clearTimeout(showTimer.current);
    showTimer.current = null;
    setHover(null);
    onHoverEntity?.(null);
  }, [cancelHide, onHoverEntity]);
  const scheduleHide = useCallback(() => {
    cancelHide();
    hideTimer.current = window.setTimeout(hideNow, HOVER_HIDE_MS);
  }, [cancelHide, hideNow]);
  const handleHover = useCallback(
    (id: number | null, element: HTMLElement | null) => {
      if (showTimer.current !== null) window.clearTimeout(showTimer.current);
      showTimer.current = null;
      if (id === null || !element) {
        scheduleHide();
        return;
      }
      cancelHide();
      const rect = element.getBoundingClientRect();
      showTimer.current = window.setTimeout(() => {
        setHover({ id, rect });
        onHoverEntity?.(id);
      }, HOVER_SHOW_MS);
    },
    [cancelHide, scheduleHide, onHoverEntity],
  );
  useEffect(() => hideNow, [page, hideNow]); // turning the page closes the popover
  useEffect(
    () => () => {
      if (showTimer.current !== null) window.clearTimeout(showTimer.current);
      if (hideTimer.current !== null) window.clearTimeout(hideTimer.current);
    },
    [],
  );

  const submitJump = (event: React.FormEvent) => {
    event.preventDefault();
    const target = Number.parseInt(jump, 10);
    if (Number.isFinite(target) && target >= 1 && target <= nPages) onGoTo(target);
    else setJump(String(page));
  };

  const entities = data ? (showAllEntities ? data.entities : data.entities.slice(0, ON_PAGE_LIMIT)) : [];

  return (
    <section className="flex h-full min-w-0 flex-1 flex-col bg-bg" aria-label="Reader">
      {/* ---- reader toolbar */}
      <div className="flex items-center gap-2 border-b border-line bg-surface px-3 py-2">
        <button type="button" className="btn btn-sm" disabled={page <= 1} onClick={() => onGoTo(page - 1)} title="Previous page (←)">
          ← Prev
        </button>
        <select
          className="input min-w-0 max-w-[18rem] py-1 text-[13px]"
          value={data?.document_id ?? ""}
          onChange={(e) => {
            const doc = documents.find((d) => d.id === Number(e.target.value));
            if (doc) onGoTo(doc.first_page);
          }}
          aria-label="Chapter"
        >
          {documents.map((d) => (
            <option key={d.id} value={d.id}>
              {d.title}
            </option>
          ))}
        </select>
        <form onSubmit={submitJump} className="ml-auto flex items-center gap-1.5 font-mono text-[12px] text-muted">
          <span>Page</span>
          <input className="input w-16 px-1 py-0.5 text-center font-mono text-[12px]" value={jump} onChange={(e) => setJump(e.target.value)} onBlur={submitJump} aria-label="Go to page" inputMode="numeric" />
          <span>of {formatNumber(nPages)}</span>
        </form>
        <button type="button" className="btn btn-sm" disabled={page >= nPages} onClick={() => onGoTo(page + 1)} title="Next page (→)">
          Next →
        </button>
      </div>
      <div className="reader-progress" aria-hidden="true">
        <span style={{ width: `${nPages ? (100 * page) / nPages : 0}%` }} />
      </div>

      {/* ---- the page */}
      <div className="min-h-0 flex-1 overflow-y-auto px-4" onScroll={() => hover && hideNow()}>
        {query.error && <ErrorNote error={query.error} />}
        {!data && query.isLoading && <Spinner label="Opening page" />}
        {nPages === 0 && <Empty>This corpus has no pages yet.</Empty>}
        {data && (
          <>
            <article className={`reader-page ${query.isFetching ? "is-loading" : ""}`}>
              <header className="reader-page__head">
                <span className="truncate">{corpus.title}</span>
                <span className="truncate text-right">{data.document_title}</span>
              </header>
              {data.opens_document && <h2 className="reader-page__chapter">{data.document_title}</h2>}
              {data.chunks.map((chunk) => (
                <HighlightedText key={chunk.id} chunk={chunk} colors={colors} activeEntities={activeEntities} onSelectEntity={onSelectEntity} onHoverEntity={handleHover} terms={terms} className="reader-page__para" />
              ))}
              <footer className="reader-page__foot">{page}</footer>
            </article>

            {/* ---- entities on this page */}
            <div className="mx-auto mb-8 max-w-[46rem]">
              <div className="mb-1.5 flex items-baseline justify-between">
                <span className="label mb-0">On this page</span>
                <span className="font-mono text-[11px] text-muted">
                  {data.entities.length} entities · {data.entities.reduce((n, e) => n + e.page_mentions, 0)} mentions
                </span>
              </div>
              {data.entities.length === 0 ? (
                <p className="text-[12.5px] text-muted">No entities were recognised on this page.</p>
              ) : (
                <div className="flex flex-wrap gap-1.5">
                  {entities.map((entity) => {
                    const active = activeEntities.has(entity.id);
                    return (
                      <button key={entity.id} type="button" className={`chip transition-colors hover:border-ink-2 ${active ? "border-accent-deep bg-accent-soft text-ink" : ""}`} onClick={() => onSelectEntity(entity.id)} title={`${entity.label} · ${entity.count} mentions in the whole book`}>
                        <Swatch color={colorOf(colors, entity.label)} />
                        <span className="font-sans text-[12.5px]">{entity.text}</span>
                        <span className="text-muted">{entity.page_mentions}</span>
                      </button>
                    );
                  })}
                  {!showAllEntities && data.entities.length > ON_PAGE_LIMIT && (
                    <button type="button" className="chip text-muted hover:text-ink" onClick={() => setShowAllEntities(true)}>
                      +{data.entities.length - ON_PAGE_LIMIT} more
                    </button>
                  )}
                </div>
              )}
            </div>
          </>
        )}
      </div>
      {hover && data && (
        <EntityPopover
          slug={slug}
          entityId={hover.id}
          anchor={hover.rect}
          pageEntities={data.entities}
          colors={colors}
          onSelectEntity={(id) => {
            hideNow();
            onSelectEntity(id);
          }}
          onMouseEnter={cancelHide}
          onMouseLeave={scheduleHide}
        />
      )}
    </section>
  );
}
