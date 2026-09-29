import { useCallback, useEffect, useMemo, useState } from "react";
import { Link, useParams, useSearchParams } from "react-router-dom";
import { GraphPanel, type GraphMode } from "@/components/GraphPanel";
import type { Selection } from "@/components/GraphViewer";
import { termsRegex } from "@/components/HighlightedText";
import { PageReader } from "@/components/PageReader";
import { ReaderSidebar, type SidebarTab } from "@/components/ReaderSidebar";
import { SearchBar } from "@/components/SearchBar";
import { Empty, ErrorNote, Spinner } from "@/components/ui";
import { useCorpus, useDocuments, usePage, useSearch } from "@/hooks/useApi";
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
  const [showRight, setShowRight] = useState(() => window.innerWidth >= 860);
  const [expanded, setExpanded] = useState(false);
  const [hoverId, setHoverId] = useState<number | null>(null);
  const [maxNodes, setMaxNodes] = useState(80);
  const [minWeight, setMinWeight] = useState(0);
  const [disabledLabels, setDisabledLabels] = useState<Set<string>>(new Set());

  const detail = corpus.data;
  const nPages = detail?.n_pages ?? 0;

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

  // ← / → turn pages when no form control has the focus
  useEffect(() => {
    const onKey = (event: KeyboardEvent) => {
      if (event.altKey || event.ctrlKey || event.metaKey) return;
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
    <div className="flex h-[calc(100vh-6.1rem)] flex-col">
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
        <div className="ml-auto w-64 shrink-0">
          <SearchBar value={search} onChange={setSearch} placeholder="Search the text…" />
        </div>
        <button type="button" className={`btn btn-sm shrink-0 ${showLeft ? "btn-primary" : ""}`} onClick={() => setShowLeft((v) => !v)} title="Toggle index and contents">
          ◧ Index
        </button>
        <button
          type="button"
          className={`btn btn-sm shrink-0 ${showRight ? "btn-primary" : ""}`}
          onClick={() => {
            setShowRight((v) => !v);
            setExpanded(false);
          }}
          title="Toggle the entity network"
        >
          Graph ◨
        </button>
      </div>

      <div className="flex min-h-0 flex-1">
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
          />
        )}
        {!(expanded && showRight) && (
          <PageReader slug={slug} corpus={detail} documents={documents.data ?? []} page={page} colors={colors} activeEntities={activeEntities} terms={terms} onSelectEntity={selectNode} onGoTo={goTo} onHoverEntity={setHoverId} />
        )}
        {showRight && (
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
            expanded={expanded}
            onToggleExpand={() => setExpanded((v) => !v)}
            onGoTo={goTo}
            hoverId={hoverId}
          />
        )}
      </div>
    </div>
  );
}
