import { useCallback, useEffect, useMemo, useState } from "react";
import { Link, useParams, useSearchParams } from "react-router-dom";
import { GraphPanel, type GraphLayout, type GraphMode } from "@/components/GraphPanel";
import type { Selection } from "@/components/GraphViewer";
import { termsRegex } from "@/components/HighlightedText";
import { PageReader } from "@/components/PageReader";
import { ReaderSidebar, type SidebarTab } from "@/components/ReaderSidebar";
import { SearchBar } from "@/components/SearchBar";
import { Empty, ErrorNote, Spinner } from "@/components/ui";
import { useCorpus, useDocuments, usePage, useSearch } from "@/hooks/useApi";
import { SITE_TITLE, shorten, useDocumentMeta } from "@/hooks/useDocumentMeta";
import { colorMap } from "@/lib/colors";
import { formatNumber, formatYear } from "@/lib/format";

function readInt(value: string | null): number | null {
  const n = Number.parseInt(value ?? "", 10);
  return Number.isFinite(n) ? n : null;
}

/**
 * The explorer is a reader first: one page at a time in the middle, the book index and
 * contents on the left, and the entity network on the right as a way to search the text.
 * The page and the selected entity live in the URL so any position can be shared.
 */
export function CorpusExplorer() {
  const { slug = "" } = useParams();
  const [params, setParams] = useSearchParams();
  const page = Math.max(1, readInt(params.get("page")) ?? 1);
  const entityParam = readInt(params.get("entity"));
  const corpus = useCorpus(slug);
  const documents = useDocuments(slug);

  const [selection, setSelection] = useState<Selection>({ nodeId: entityParam, edge: null });
  const [focus, setFocus] = useState<number | null>(null);
  const [mode, setMode] = useState<GraphMode>("corpus");
  const [search, setSearch] = useState("");
  const [tab, setTab] = useState<SidebarTab>("index");
  const [showLeft, setShowLeft] = useState(() => window.innerWidth >= 1100);
  const [graphLayout, setGraphLayout] = useState<GraphLayout>(() => (window.innerWidth >= 860 ? "side" : "hidden"));
  const [hoverId, setHoverId] = useState<number | null>(null);
  const [maxNodes, setMaxNodes] = useState(80);
  const [minWeight, setMinWeight] = useState(0);
  const [disabledLabels, setDisabledLabels] = useState<Set<string>>(new Set());

  const detail = corpus.data;
  const nPages = detail?.n_pages ?? 0;
  const by = detail?.author ? ` by ${detail.author}` : "";
  const network = detail
    ? `Read ${detail.title}${by} page by page and explore its network of ${formatNumber(detail.n_entities)} people, places and things.`
    : "";
  useDocumentMeta({
    title: detail ? `${detail.title}${by} · ECCE` : SITE_TITLE,
    description: detail ? shorten(detail.description ? `${detail.description} ${network}` : network) : undefined,
    path: `/corpus/${encodeURIComponent(slug)}`,
  });

  const updateParams = useCallback(
    (patch: Record<string, string | null>) => {
      setParams(
        (prev) => {
          const next = new URLSearchParams(prev);
          for (const [key, value] of Object.entries(patch)) {
            if (value === null) next.delete(key);
            else next.set(key, value);
          }
          return next;
        },
        { replace: true },
      );
    },
    [setParams],
  );

  /** Turn to a page; optionally select an entity at the same time (its mentions get highlighted). */
  const goTo = useCallback(
    (target: number, entityId?: number | null) => {
      const clamped = nPages ? Math.min(Math.max(1, target), nPages) : Math.max(1, target);
      const patch: Record<string, string | null> = { page: String(clamped) };
      if (entityId !== undefined) {
        patch.entity = entityId === null ? null : String(entityId);
        setSelection({ nodeId: entityId, edge: null });
      }
      updateParams(patch);
    },
    [nPages, updateParams],
  );

  const selectNode = useCallback(
    (id: number | null) => {
      setSelection({ nodeId: id, edge: null });
      if (id === null) setFocus(null);
      updateParams({ entity: id === null ? null : String(id) });
    },
    [updateParams],
  );
  const selectEdge = useCallback(
    (a: number, b: number) => {
      setSelection({ nodeId: null, edge: [a, b] });
      setFocus(null);
      updateParams({ entity: null });
    },
    [updateParams],
  );

  // keep the page inside the book once its size is known
  useEffect(() => {
    if (nPages && page > nPages) goTo(nPages);
  }, [nPages, page, goTo]);

  // a search query opens the results tab; clearing it returns to the index
  useEffect(() => {
    if (search) {
      setTab("search");
      setShowLeft(true);
    } else setTab((t) => (t === "search" ? "index" : t));
  }, [search]);

  // ← / → turn pages when no form control has the focus; Esc leaves the full-width graph
  useEffect(() => {
    const onKey = (event: KeyboardEvent) => {
      if (event.altKey || event.ctrlKey || event.metaKey) return;
      if (event.key === "Escape") {
        setGraphLayout((l) => (l === "full" ? "side" : l));
        return;
      }
      const target = event.target as HTMLElement | null;
      if (target && (["INPUT", "TEXTAREA", "SELECT"].includes(target.tagName) || target.isContentEditable)) return;
      if (event.key === "ArrowRight") {
        event.preventDefault();
        goTo(page + 1);
      } else if (event.key === "ArrowLeft") {
        event.preventDefault();
        goTo(page - 1);
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [goTo, page]);

  const labels = useMemo(() => Object.keys(detail?.label_counts ?? {}), [detail]);
  const colors = useMemo(() => colorMap(labels), [labels]);
  const activeLabels = useMemo(() => labels.filter((l) => !disabledLabels.has(l)), [labels, disabledLabels]);
  const graphParams = useMemo(
    () => ({ min_weight: minWeight, max_nodes: maxNodes, labels: activeLabels.length === labels.length ? [] : activeLabels, focus }),
    [minWeight, maxNodes, activeLabels, labels.length, focus],
  );
  const entityIds = useMemo(() => (selection.edge ? [...selection.edge] : selection.nodeId !== null ? [selection.nodeId] : []), [selection]);
  const activeEntities = useMemo(() => new Set(entityIds), [entityIds]);
  const results = useSearch(slug, search, entityIds);
  const terms = useMemo(() => termsRegex(search), [search]);
  const current = usePage(slug, page, nPages > 0); // shares the reader's cache entry

  if (corpus.isLoading) return <Spinner label="Opening the book" />;
  if (corpus.error || !detail) return <ErrorNote error={corpus.error ?? "Corpus not found"} />;
  if (detail.status !== "ready") return <Empty>This corpus is not processed yet ({detail.status}).</Empty>;

  return (
    <div className="flex h-[calc(100vh-3.1rem)] flex-col">
      {/* ---- top bar */}
      <div className="flex items-center gap-3 border-b border-line bg-surface px-4 py-2">
        <Link to="/" className="shrink-0 font-mono text-[12px] text-muted hover:text-ink">
          ← Gallery
        </Link>
        <h1 className="truncate text-[18px]">{detail.title}</h1>
        {detail.author && (
          <span className="hidden shrink-0 truncate text-[13px] text-ink-2 md:inline">
            {detail.author}
            {detail.year !== null ? ` · ${formatYear(detail.year)}` : ""}
          </span>
        )}
        <span className="hidden shrink-0 font-mono text-[11px] text-muted xl:inline">
          {formatNumber(detail.n_pages)} pages · {formatNumber(detail.n_entities)} entities · {formatNumber(detail.n_edges)} relations
        </span>
        <div className="ml-auto w-72 shrink-0">
          <SearchBar value={search} onChange={setSearch} placeholder="Search the text…" />
        </div>
      </div>

      <div className="flex min-h-0 flex-1">
        {!showLeft && (
          <button type="button" className="rail rail--left" onClick={() => setShowLeft(true)} title="Show the index and contents">
            <span aria-hidden="true">›</span>
            <span className="rail__label">Index · Contents</span>
          </button>
        )}
        {showLeft && (
          <ReaderSidebar
            slug={slug}
            corpus={detail}
            documents={documents.data ?? []}
            colors={colors}
            page={page}
            currentDocumentId={current.data?.document_id ?? null}
            selectedEntityId={selection.nodeId}
            tab={tab}
            onTab={setTab}
            search={search}
            results={results.data}
            searchLoading={results.isLoading}
            filteredBySelection={entityIds.length > 0}
            onGoTo={goTo}
            onSelectEntity={selectNode}
            onHide={() => setShowLeft(false)}
          />
        )}
        {graphLayout !== "full" && (
          <PageReader slug={slug} corpus={detail} documents={documents.data ?? []} page={page} colors={colors} activeEntities={activeEntities} terms={terms} onSelectEntity={selectNode} onGoTo={goTo} onHoverEntity={setHoverId} />
        )}
        {graphLayout === "hidden" && (
          <button type="button" className="rail rail--right" onClick={() => setGraphLayout("side")} title="Show the entity network">
            <span aria-hidden="true">‹</span>
            <span className="rail__label">Graph</span>
          </button>
        )}
        {graphLayout !== "hidden" && (
          <GraphPanel
            slug={slug}
            corpus={detail}
            colors={colors}
            labels={labels}
            page={page}
            mode={mode}
            onMode={setMode}
            selection={selection}
            onSelectNode={selectNode}
            onSelectEdge={selectEdge}
            focus={focus}
            onToggleFocus={() => setFocus((f) => (f === selection.nodeId ? null : selection.nodeId))}
            params={graphParams}
            maxNodes={maxNodes}
            onMaxNodes={setMaxNodes}
            minWeight={minWeight}
            onMinWeight={setMinWeight}
            disabledLabels={disabledLabels}
            onToggleLabel={(label, enabled) =>
              setDisabledLabels((prev) => {
                const next = new Set(prev);
                if (enabled) next.delete(label);
                else next.add(label);
                return next;
              })
            }
            layout={graphLayout}
            onLayout={setGraphLayout}
            onGoTo={goTo}
            hoverId={hoverId}
          />
        )}
      </div>
    </div>
  );
}
