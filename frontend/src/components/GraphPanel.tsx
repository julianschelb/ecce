import { useMemo, useState } from "react";
import { EntityPanel } from "@/components/EntityPanel";
import { DEFAULT_REPEL, GraphViewer, type Selection } from "@/components/GraphViewer";
import { PageNumbers, nextPageAfter } from "@/components/PageNumbers";
import { EntityIndex, SearchResults } from "@/components/ReaderPanels";
import { Empty, ErrorNote, Slider, Spinner, Swatch } from "@/components/ui";
import { useDocumentGraph, useEdge, useGraph, usePageGraph, usePageRefs, type GraphParams } from "@/hooks/useApi";
import type { CorpusDetail, SearchResponse } from "@/lib/api";
import { colorOf, type ColorMap } from "@/lib/colors";
import { formatNumber, formatWeight } from "@/lib/format";

export type GraphMode = "corpus" | "chapter" | "page";
export type GraphLayout = "hidden" | "side" | "full";
export type RightTab = "graph" | "index" | "search";

interface Props {
  slug: string;
  corpus: CorpusDetail;
  colors: ColorMap;
  labels: string[];
  page: number;
  mode: GraphMode;
  onMode: (mode: GraphMode) => void;
  selection: Selection;
  onSelectNode: (id: number | null) => void;
  onSelectEdge: (a: number, b: number) => void;
  focus: number | null;
  onToggleFocus: () => void;
  params: GraphParams;
  maxNodes: number;
  onMaxNodes: (v: number) => void;
  minWeight: number;
  onMinWeight: (v: number) => void;
  disabledLabels: Set<string>;
  onToggleLabel: (label: string, enabled: boolean) => void;
  layout: GraphLayout;
  onLayout: (layout: GraphLayout) => void;
  onGoTo: (page: number, entityId?: number | null) => void;
  /** Entity hovered in the reader: the graph temporarily shows its entity network. */
  hoverId: number | null;
  tab: RightTab;
  onTab: (tab: RightTab) => void;
  /** Width of the side panel in pixels (ignored in full-width mode). */
  width: number;
  search: string;
  results?: SearchResponse;
  searchLoading: boolean;
  filteredBySelection: boolean;
  /** The chapter (document) of the current page, and whether the book has chapters at all. */
  documentId: number | null;
  documentTitle: string;
  hasChapters: boolean;
}

const HOVER_EGO_NODES = 40;

/** Right rail: the entity network as a search tool (whole book or the current page), the
 * entity index and the results of a text search. */
export function GraphPanel(props: Props) {
  const { slug, corpus, colors, labels, page, mode, onMode, selection, onSelectNode, onSelectEdge, focus, onToggleFocus, params, layout, onLayout, onGoTo, hoverId, tab, onTab, width, search } = props;
  const expanded = layout === "full";
  const [showFilters, setShowFilters] = useState(false);
  const [repel, setRepel] = useState(DEFAULT_REPEL);
  const ready = corpus.status === "ready" && tab === "graph";
  const corpusGraph = useGraph(slug, params, ready && mode === "corpus");
  const pageGraph = usePageGraph(slug, page, ready && mode === "page");
  const chapterGraph = useDocumentGraph(slug, props.documentId, ready && mode === "chapter");
  const hoverParams = useMemo(() => ({ ...params, focus: hoverId, max_nodes: Math.min(params.max_nodes, HOVER_EGO_NODES) }), [params, hoverId]);
  const hoverGraph = useGraph(slug, hoverParams, ready && mode === "corpus" && hoverId !== null);
  const hovering = hoverId !== null;
  const graph = mode === "page" ? pageGraph : mode === "chapter" ? chapterGraph : hovering && hoverGraph.data ? hoverGraph : corpusGraph;
  const viewSelection: Selection = hovering ? { nodeId: hoverId, edge: null } : selection;
  const hoveredName = hovering ? graph.data?.nodes.find((n) => n.id === hoverId)?.text : undefined;

  return (
    <aside className={`reader-side panel-enter flex min-w-0 flex-col border-l border-line bg-surface ${expanded ? "flex-1" : "shrink-0"}`} style={expanded ? undefined : { width }} aria-label="Entity network, index and search">
      <div className="flex items-stretch border-b border-line-soft text-[13px]" role="tablist" aria-label="Right panel">
        {(
          [
            ["graph", "Entity graph"],
            ["index", "Entity index"],
            ...(search ? ([["search", "Search"]] as const) : []),
          ] as const
        ).map(([key, label]) => (
          <button key={key} type="button" role="tab" aria-selected={tab === key} className={`border-b-2 px-4 py-2 font-medium ${tab === key ? "border-accent-deep text-ink" : "border-transparent text-muted hover:text-ink"}`} onClick={() => onTab(key)}>
            {label}
          </button>
        ))}
        <div className="ml-auto flex items-center gap-1 pr-2">
          {expanded ? (
            <button type="button" className="btn btn-sm btn-primary" onClick={() => onLayout("side")} title="Return to the reader (Esc)">
              ⤡ Back to reader
            </button>
          ) : (
            <>
              <button type="button" className="btn btn-sm hidden md:inline-flex" onClick={() => onLayout("full")} title="Give this panel the whole width">
                ⤢ Full width
              </button>
              <button type="button" className="btn btn-sm px-1.5" onClick={() => onLayout("hidden")} title="Hide this panel (a tab on the right brings it back)" aria-label="Hide the panel">
                ›
              </button>
            </>
          )}
        </div>
      </div>

      {tab === "index" ? (
        <EntityIndex
          slug={slug}
          corpus={corpus}
          colors={colors}
          page={page}
          selectedEntityId={selection.nodeId}
          onGoTo={onGoTo}
          onSelectEntity={(id) => {
            onTab("graph");
            onSelectNode(id);
          }}
        />
      ) : tab === "search" ? (
        <SearchResults search={search} results={props.results} searchLoading={props.searchLoading} filteredBySelection={props.filteredBySelection} page={page} onGoTo={onGoTo} />
      ) : (
        <>
          <div className="flex items-center gap-2 border-b border-line-soft px-3 py-2">
            <div className="seg" role="tablist" aria-label="Graph scope">
              <button type="button" role="tab" aria-selected={mode === "corpus"} className={mode === "corpus" ? "is-active" : ""} onClick={() => onMode("corpus")} title="Network of the whole book">
                Whole book
              </button>
              {props.hasChapters && (
                <button type="button" role="tab" aria-selected={mode === "chapter"} className={mode === "chapter" ? "is-active" : ""} onClick={() => onMode("chapter")} title="Only the entities mentioned in the current chapter">
                  This chapter
                </button>
              )}
              <button type="button" role="tab" aria-selected={mode === "page"} className={mode === "page" ? "is-active" : ""} onClick={() => onMode("page")} title="Only the entities mentioned on the current page">
                This page
              </button>
            </div>
            {mode === "corpus" && selection.nodeId !== null && (
              <button type="button" className={`btn btn-sm ${focus !== null ? "btn-primary" : ""}`} onClick={onToggleFocus} title="Focus: show only the entity network of the selected entity">
                Focus
              </button>
            )}
            {mode === "corpus" && (
              <button type="button" className={`btn btn-sm ml-auto ${showFilters ? "btn-primary" : ""}`} onClick={() => setShowFilters((v) => !v)}>
                Filters
              </button>
            )}
          </div>

          {showFilters && mode === "corpus" && (
            <div className="space-y-3 border-b border-line-soft px-3 py-3">
              <Slider label="Entities shown" value={props.maxNodes} min={10} max={Math.min(400, Math.max(corpus.n_entities, 10))} step={5} onChange={props.onMaxNodes} />
              <Slider label="Min. association score" value={props.minWeight} min={0} max={Math.max(corpus.max_weight, 0.1)} step={Math.max(corpus.max_weight / 200, 0.01)} onChange={props.onMinWeight} format={formatWeight} />
              {corpus.suggested_min_weight > 0 && (
                <button type="button" className="-mt-1 text-left font-mono text-[11px] text-muted hover:text-ink" onClick={() => props.onMinWeight(corpus.suggested_min_weight)} title="The default keeps about four edges per entity in view">
                  Suggested for this book: {formatWeight(corpus.suggested_min_weight)} · reset
                </button>
              )}
              <Slider label="Spacing (repel force)" value={repel} min={30} max={400} step={10} onChange={setRepel} format={(v) => (v === DEFAULT_REPEL ? `${v} (default)` : String(v))} />
              <div className="flex flex-wrap gap-1">
                {labels.map((label) => {
                  const enabled = !props.disabledLabels.has(label);
                  return (
                    <button key={label} type="button" className={`chip hover:border-ink-2 ${enabled ? "chip--on" : "opacity-60"}`} onClick={() => props.onToggleLabel(label, !enabled)} title={`${corpus.label_counts[label]} entities`}>
                      <Swatch color={colorOf(colors, label)} />
                      {label}
                    </button>
                  );
                })}
              </div>
            </div>
          )}

          <div className="relative min-h-[240px] flex-1 overflow-hidden bg-bg">
            {graph.isLoading && <Spinner label="Building view" />}
            {graph.error && <ErrorNote error={graph.error} />}
            {graph.data && graph.data.nodes.length === 0 && <Empty>{mode === "page" ? "No entities on this page." : mode === "chapter" ? "No entities in this chapter." : "No edges match the current filters."}</Empty>}
            {graph.data && graph.data.nodes.length > 0 && (
              <GraphViewer nodes={graph.data.nodes} edges={graph.data.edges} colors={colors} maxStrength={corpus.max_strength} selection={viewSelection} onSelectNode={onSelectNode} onSelectEdge={onSelectEdge} repel={repel} />
            )}
            {graph.data && (
              <div className="pointer-events-none absolute left-3 top-2 font-mono text-[11px] text-muted">
                {mode === "page"
                  ? `page ${page}: ${graph.data.total_nodes} entities · ${graph.data.total_edges} links`
                  : mode === "chapter"
                    ? `${props.documentTitle || "this chapter"}: ${formatNumber(graph.data.total_nodes)} entities`
                    : hovering && graph === hoverGraph
                    ? `entity network of ${hoveredName ?? "the hovered entity"}`
                    : `${formatNumber(graph.data.nodes.length)} of ${formatNumber(graph.data.total_nodes)} entities${focus !== null ? " · entity network" : ""}`}
              </div>
            )}
          </div>

          <div className="flex max-h-[45%] min-h-[160px] shrink-0 flex-col border-t border-line">
            {selection.edge ? (
              <EdgeDetails slug={slug} pair={selection.edge} page={page} onGoTo={onGoTo} onSelectEntity={onSelectNode} onClear={() => onSelectNode(null)} />
            ) : selection.nodeId !== null ? (
              <EntityPanel slug={slug} entityId={selection.nodeId} colors={colors} page={page} documentId={props.documentId} hasChapters={props.hasChapters} onGoTo={onGoTo} onSelectEntity={onSelectNode} onSelectEdge={onSelectEdge} onClear={() => onSelectNode(null)} />
            ) : (
              <div className="px-4 py-3 text-[12.5px] leading-relaxed text-muted">
                <p>
                  <strong className="font-medium text-ink-2">Use the graph to search the book.</strong> Click an entity to list every page that mentions it, or click a link to find the pages where two entities appear together.
                </p>
                <p className="mt-1.5">“{props.hasChapters ? "This chapter” and “" : ""}This page” restrict{props.hasChapters ? "" : "s"} the network to the entities {props.hasChapters ? "of the chapter or page" : "on the page"} you are reading.</p>
              </div>
            )}
          </div>
        </>
      )}
    </aside>
  );
}

function EdgeDetails({ slug, pair, page, onGoTo, onSelectEntity, onClear }: { slug: string; pair: [number, number]; page: number; onGoTo: (page: number, entityId?: number | null) => void; onSelectEntity: (id: number) => void; onClear: () => void }) {
  const edge = useEdge(slug, pair[0], pair[1]);
  const refs = usePageRefs(slug, { entity_id: [pair[0], pair[1]], document_id: null });
  if (edge.isLoading) return <Spinner label="Loading relation" />;
  if (edge.error) return <ErrorNote error={edge.error} />;
  if (!edge.data) return null;
  const pages = refs.data?.items.map((r) => r.number) ?? [];
  const next = nextPageAfter(pages, page);
  return (
    <div className="flex h-full flex-col">
      <div className="border-b border-line-soft px-4 py-3">
        <div className="flex items-start gap-2">
          <h2 className="min-w-0 flex-1 text-[17px] leading-snug">
            <button type="button" className="hover:text-accent-deep" onClick={() => onSelectEntity(edge.data.source.id)}>
              {edge.data.source.text}
            </button>
            <span className="text-muted"> — </span>
            <button type="button" className="hover:text-accent-deep" onClick={() => onSelectEntity(edge.data.target.id)}>
              {edge.data.target.text}
            </button>
          </h2>
          <button type="button" className="font-mono text-[12px] text-muted hover:text-ink" onClick={onClear}>
            clear
          </button>
        </div>
        <div className="mt-1.5 flex flex-wrap gap-1.5">
          <span className="chip" title={`Association score ω = ${formatWeight(edge.data.weight)}`}>association score {formatWeight(edge.data.weight)}</span>
          <span className="chip">{formatNumber(edge.data.count)} co-occurrences</span>
          <span className="chip">{refs.data ? `${formatNumber(refs.data.total)} shared pages` : "… pages"}</span>
        </div>
        {edge.data.relations && edge.data.relations.length > 0 && (
          <ul className="mt-2 space-y-0.5 text-[13px]" aria-label="Relations">
            {edge.data.relations.map((r) => {
              const name = (id: number) => (id === edge.data.source.id ? edge.data.source.text : edge.data.target.text);
              return (
                <li key={`${r.label}-${r.head_id}`}>
                  {name(r.head_id)} <em className="text-accent-deep">{r.label}</em> {name(r.tail_id)}
                  <span className="ml-1.5 font-mono text-[11px] text-muted">×{r.count}</span>
                </li>
              );
            })}
          </ul>
        )}
        {next !== null && (
          <button type="button" className="btn btn-sm btn-primary mt-2.5" onClick={() => onGoTo(next)}>
            {next > page ? "Next shared page" : "First shared page"} · p. {next}
          </button>
        )}
      </div>
      <div className="min-h-0 flex-1 overflow-y-auto">
        <div className="panel-head">Pages mentioning both</div>
        <div className="px-4 py-2.5">
          <PageNumbers pages={pages} current={page} onGoTo={(p) => onGoTo(p)} limit={48} />
        </div>
      </div>
    </div>
  );
}
