import { useCallback, useEffect, useRef, useState } from "react";
import { EntityPopover } from "@/components/EntityPopover";
import { HighlightedText } from "@/components/HighlightedText";
import { Empty, ErrorNote, Spinner, Swatch } from "@/components/ui";
import { usePage, usePrefetchPages } from "@/hooks/useApi";
import type { CorpusDetail, DocumentOut, PageOut } from "@/lib/api";
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
const FLIP_MS = 480;

type Turn = { page: PageOut; direction: "next" | "prev" };

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

  // ---- page turn: keep the previous page for the duration of the flip
  const [leaving, setLeaving] = useState<Turn | null>(null);
  const previous = useRef<PageOut | null>(null);
  useEffect(() => {
    if (!data) return;
    const before = previous.current;
    if (before && before.number !== data.number) {
      setLeaving({ page: before, direction: data.number > before.number ? "next" : "prev" });
    }
    previous.current = data;
  }, [data]);
  useEffect(() => {
    if (!leaving) return;
    const handle = window.setTimeout(() => setLeaving(null), FLIP_MS);
    return () => window.clearTimeout(handle);
  }, [leaving]);

  // ---- hover: a mention opens a popover after a short delay and hands the entity to the graph;
  // a click pins the popover, which then stays open until a click outside it (or Esc)
  const [hover, setHover] = useState<{ id: number; rect: DOMRect } | null>(null);
  const [pinned, setPinned] = useState(false);
  const pinnedRef = useRef(false);
  const popoverRef = useRef<HTMLDivElement>(null);
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
    pinnedRef.current = false;
    setPinned(false);
    setHover(null);
    onHoverEntity?.(null);
  }, [cancelHide, onHoverEntity]);
  const scheduleHide = useCallback(() => {
    if (pinnedRef.current) return;
    cancelHide();
    hideTimer.current = window.setTimeout(hideNow, HOVER_HIDE_MS);
  }, [cancelHide, hideNow]);
  const handleHover = useCallback(
    (id: number | null, element: HTMLElement | null) => {
      if (pinnedRef.current) return; // a pinned menu ignores the pointer
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
  const pin = useCallback(() => {
    cancelHide();
    if (showTimer.current !== null) window.clearTimeout(showTimer.current);
    showTimer.current = null;
    pinnedRef.current = true;
    setPinned(true);
    onHoverEntity?.(null); // the entity is selected now: the graph shows the selection
  }, [cancelHide, onHoverEntity]);
  const selectMention = useCallback(
    (id: number, element?: HTMLElement) => {
      onSelectEntity(id);
      if (!element) return;
      pin();
      setHover({ id, rect: element.getBoundingClientRect() });
    },
    [onSelectEntity, pin],
  );
  useEffect(() => {
    if (!pinned) return;
    const onDown = (event: MouseEvent) => {
      if (!popoverRef.current?.contains(event.target as Node)) hideNow();
    };
    const onKey = (event: KeyboardEvent) => event.key === "Escape" && hideNow();
    document.addEventListener("mousedown", onDown);
    document.addEventListener("keydown", onKey);
    return () => {
      document.removeEventListener("mousedown", onDown);
      document.removeEventListener("keydown", onKey);
    };
  }, [pinned, hideNow]);
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
      <div className="bar flex items-center gap-2 border-b border-line bg-surface px-3">
        <button type="button" className="btn btn-sm" disabled={page <= 1} onClick={() => onGoTo(page - 1)} title="Previous page (←)">
          ←<span className="hidden sm:inline"> Prev</span>
        </button>
        <select
          className="input min-w-0 flex-1 py-1 text-[13px] sm:max-w-[18rem] sm:flex-none"
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
          <span className="hidden sm:inline">Page</span>
          <input className="input w-16 px-1 py-0.5 text-center font-mono text-[12px]" value={jump} onChange={(e) => setJump(e.target.value)} onBlur={submitJump} aria-label="Go to page" inputMode="numeric" />
          <span>of {formatNumber(nPages)}</span>
        </form>
        <button type="button" className="btn btn-sm" disabled={page >= nPages} onClick={() => onGoTo(page + 1)} title="Next page (→)">
          <span className="hidden sm:inline">Next </span>→
        </button>
      </div>
      <div className="reader-progress" aria-hidden="true">
        <span style={{ width: `${nPages ? (100 * page) / nPages : 0}%` }} />
      </div>

      {/* ---- the page */}
      <div className="min-h-0 flex-1 overflow-y-auto px-4" onScroll={() => hover && !pinnedRef.current && hideNow()}>
        {query.error && <ErrorNote error={query.error} />}
        {!data && query.isLoading && <Spinner label="Opening page" />}
        {nPages === 0 && <Empty>This corpus has no pages yet.</Empty>}
        {data && (
          <>
            <div className="reader-stack">
              {leaving && (
                <article key={`leaving-${leaving.page.number}`} className={`reader-page reader-page--leave-${leaving.direction}`} aria-hidden="true">
                  <PageSheet page={leaving.page} corpusTitle={corpus.title} colors={colors} activeEntities={activeEntities} terms={terms} />
                </article>
              )}
              <article key={data.number} className={`reader-page ${leaving ? `reader-page--enter-${leaving.direction}` : ""} ${query.isFetching ? "is-loading" : ""}`}>
                <PageSheet page={data} corpusTitle={corpus.title} colors={colors} activeEntities={activeEntities} terms={terms} onSelectEntity={selectMention} onHoverEntity={handleHover} />
              </article>
            </div>

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
                      <button key={entity.id} type="button" className={`chip transition-colors hover:border-ink-2 ${active ? "border-accent-deep bg-accent-soft text-ink" : ""}`} onClick={() => onSelectEntity(entity.id)} title={`${entity.label} · ${entity.count} occurrences in the whole book`}>
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
      {hover && data && !leaving && (
        <div ref={popoverRef}>
          <EntityPopover
            slug={slug}
            entityId={hover.id}
            anchor={hover.rect}
            page={page}
            documentId={data.document_id}
            hasChapters={documents.length > 1}
            colors={colors}
            onSelectEntity={(id) => {
              pin();
              onSelectEntity(id);
            }}
            onMouseEnter={cancelHide}
            onMouseLeave={scheduleHide}
          />
        </div>
      )}
    </section>
  );
}

/** The content of one sheet: running head, chapter heading, paragraphs and the page number. */
function PageSheet({
  page,
  corpusTitle,
  colors,
  activeEntities,
  terms,
  onSelectEntity,
  onHoverEntity,
}: {
  page: PageOut;
  corpusTitle: string;
  colors: ColorMap;
  activeEntities: Set<number>;
  terms: RegExp | null;
  onSelectEntity?: (id: number, element?: HTMLElement) => void;
  onHoverEntity?: (id: number | null, element: HTMLElement | null) => void;
}) {
  return (
    <>
      <header className="reader-page__head">
        <span className="truncate">{corpusTitle}</span>
        <span className="truncate text-right">{page.document_title}</span>
      </header>
      {page.opens_document && <h2 className="reader-page__chapter">{page.document_title}</h2>}
      {page.chunks.map((chunk) => (
        <HighlightedText key={chunk.id} chunk={chunk} colors={colors} activeEntities={activeEntities} onSelectEntity={onSelectEntity ?? (() => undefined)} onHoverEntity={onHoverEntity} terms={terms} className="reader-page__para" />
      ))}
      <footer className="reader-page__foot">{page.number}</footer>
    </>
  );
}
