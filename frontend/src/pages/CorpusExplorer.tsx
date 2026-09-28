import { useCallback, useEffect, useMemo, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { DocumentReader, HighlightedText } from "@/components/DocumentReader";
import { EntityPanel } from "@/components/EntityPanel";
import { GraphViewer, type Selection } from "@/components/GraphViewer";
import { SearchBar } from "@/components/SearchBar";
import { Empty, ErrorNote, Slider, Spinner, Swatch } from "@/components/ui";
import { useChunks, useCorpus, useDocuments, useEdge, useEntitySearch, useGraph, useSearch } from "@/hooks/useApi";
import { colorMap, colorOf } from "@/lib/colors";
import { formatNumber, formatWeight, formatYear, splitSnippet } from "@/lib/format";

const PAGE_SIZE = 30;

export function CorpusExplorer() {
  const { slug = "" } = useParams();
  const corpus = useCorpus(slug);
  const documents = useDocuments(slug);

  // ---- graph controls
  const [maxNodes, setMaxNodes] = useState(80);
  const [minWeight, setMinWeight] = useState(0);
  const [disabledLabels, setDisabledLabels] = useState<Set<string>>(new Set());
  const [focus, setFocus] = useState<number | null>(null);
  const [showControls, setShowControls] = useState(true);
  const [showPanel, setShowPanel] = useState(true);

  // ---- selection & reader state
  const [selection, setSelection] = useState<Selection>({ nodeId: null, edge: null });
  const [documentId, setDocumentId] = useState<number | null>(null);
  const [page, setPage] = useState(1);
  const [search, setSearch] = useState("");
  const [entityQuery, setEntityQuery] = useState("");
  const [panelTab, setPanelTab] = useState<"entity" | "passages">("entity");

  const labels = useMemo(() => Object.keys(corpus.data?.label_counts ?? {}), [corpus.data]);
  const colors = useMemo(() => colorMap(labels), [labels]);
  const activeLabels = useMemo(() => labels.filter((l) => !disabledLabels.has(l)), [labels, disabledLabels]);

  const graphParams = useMemo(
    () => ({ min_weight: minWeight, max_nodes: maxNodes, labels: activeLabels.length === labels.length ? [] : activeLabels, focus }),
    [minWeight, maxNodes, activeLabels, labels.length, focus],
  );
  const graph = useGraph(slug, graphParams, corpus.data?.status === "ready");

  const entityIds = useMemo(() => (selection.edge ? [...selection.edge] : selection.nodeId !== null ? [selection.nodeId] : []), [selection]);
  const chunks = useChunks(slug, { document_id: documentId, entity_id: entityIds, page, page_size: PAGE_SIZE }, !search);
  const results = useSearch(slug, search, entityIds);
  const edge = useEdge(slug, selection.edge?.[0] ?? null, selection.edge?.[1] ?? null);
  const entityHits = useEntitySearch(slug, entityQuery);

  useEffect(() => setPage(1), [documentId, entityIds, search]);

  const selectNode = useCallback((id: number | null) => {
    setSelection({ nodeId: id, edge: null });
    setPanelTab("entity");
    if (id === null) setFocus(null);
  }, []);
  const selectEdge = useCallback((a: number, b: number) => setSelection({ nodeId: null, edge: [a, b] }), []);
  const activeEntities = useMemo(() => new Set(entityIds), [entityIds]);

  if (corpus.isLoading) return <Spinner label="Loading corpus" />;
  if (corpus.error || !corpus.data) return <ErrorNote error={corpus.error ?? "Corpus not found"} />;
  const detail = corpus.data;
  const total = chunks.data?.total ?? 0;
  const pages = Math.max(1, Math.ceil(total / PAGE_SIZE));

  return (
    <div className="flex h-[calc(100vh-6.1rem)] flex-col">
      {/* ---- top bar */}
      <div className="flex items-center gap-3 border-b border-line bg-surface px-4 py-2">
        <Link to="/" className="font-mono text-[12px] text-muted hover:text-ink">
          ← Gallery
        </Link>
        <h1 className="truncate text-[18px]">{detail.title}</h1>
        {detail.author && (
          <span className="hidden truncate text-[13px] text-ink-2 md:inline">
            {detail.author}
            {detail.year !== null ? ` · ${formatYear(detail.year)}` : ""}
          </span>
        )}
        <span className="hidden font-mono text-[11px] text-muted lg:inline">
          {formatNumber(detail.n_entities)} entities · {formatNumber(detail.n_edges)} edges · window {detail.window} · {detail.extractor || "—"}
        </span>
        <div className="ml-auto w-72">
          <SearchBar value={search} onChange={setSearch} placeholder="Search passages…" />
        </div>
        <button type="button" className="btn btn-sm" onClick={() => setShowControls((v) => !v)} title="Toggle controls">
          {showControls ? "◧" : "◨"} Controls
        </button>
        <button type="button" className="btn btn-sm" onClick={() => setShowPanel((v) => !v)} title="Toggle reader">
          Reader {showPanel ? "◨" : "◧"}
        </button>
      </div>

      <div className="flex min-h-0 flex-1">
        {/* ---- left: controls */}
        {showControls && (
          <aside className="w-[270px] shrink-0 overflow-y-auto border-r border-line bg-sidebar p-4">
            <div className="space-y-5">
              <Slider label="Entities shown" value={maxNodes} min={10} max={Math.min(400, Math.max(detail.n_entities, 10))} step={5} onChange={setMaxNodes} />
              <Slider label="Min. edge weight" value={minWeight} min={0} max={Math.max(detail.max_weight, 0.1)} step={Math.max(detail.max_weight / 200, 0.01)} onChange={setMinWeight} format={formatWeight} />
              <div>
                <div className="label">Entity types</div>
                <ul className="space-y-1">
                  {labels.map((label) => (
                    <li key={label}>
                      <label className="flex cursor-pointer items-center gap-2 text-[13px]">
                        <input
                          type="checkbox"
                          checked={!disabledLabels.has(label)}
                          onChange={(e) =>
                            setDisabledLabels((prev) => {
                              const next = new Set(prev);
                              if (e.target.checked) next.delete(label);
                              else next.add(label);
                              return next;
                            })
                          }
                        />
                        <Swatch color={colorOf(colors, label)} />
                        <span className="flex-1">{label}</span>
                        <span className="font-mono text-[11px] text-muted">{detail.label_counts[label]}</span>
                      </label>
                    </li>
                  ))}
                </ul>
              </div>
              <div>
                <div className="label">Find entity</div>
                <SearchBar value={entityQuery} onChange={setEntityQuery} placeholder="Entity name…" />
                {entityHits.data && entityQuery && (
                  <ul className="mt-1 max-h-48 overflow-y-auto rounded-md border border-line-soft bg-surface">
                    {entityHits.data.map((e) => (
                      <li key={e.id}>
                        <button type="button" className="flex w-full items-center gap-2 px-2 py-1 text-left text-[13px] hover:bg-select" onClick={() => { selectNode(e.id); setFocus(e.id); setEntityQuery(""); }}>
                          <Swatch color={colorOf(colors, e.label)} />
                          <span className="flex-1 truncate">{e.text}</span>
                          <span className="font-mono text-[11px] text-muted">{e.count}</span>
                        </button>
                      </li>
                    ))}
                    {entityHits.data.length === 0 && <li className="px-2 py-1 text-[12px] text-muted">No match</li>}
                  </ul>
                )}
              </div>
              <div>
                <div className="label">Document</div>
                <select className="input" value={documentId ?? ""} onChange={(e) => setDocumentId(e.target.value ? Number(e.target.value) : null)}>
                  <option value="">All documents</option>
                  {documents.data?.map((d) => (
                    <option key={d.id} value={d.id}>
                      {d.title}
                    </option>
                  ))}
                </select>
              </div>
              {graph.data && (
                <div className="meta border-t border-line-soft pt-3">
                  showing {graph.data.nodes.length} of {graph.data.total_nodes} entities and {graph.data.edges.length} of {graph.data.total_edges} edges
                  {focus !== null && " · ego network"}
                </div>
              )}
              {detail.description && <p className="border-t border-line-soft pt-3 text-[12.5px] text-ink-2">{detail.description}</p>}
            </div>
          </aside>
        )}

        {/* ---- centre: graph */}
        <div className="relative min-w-0 flex-1 bg-bg">
          {graph.isLoading && <Spinner label="Building view" />}
          {graph.error && <ErrorNote error={graph.error} />}
          {graph.data && graph.data.nodes.length === 0 && <Empty>No edges match the current filters.</Empty>}
          {graph.data && graph.data.nodes.length > 0 && (
            <GraphViewer nodes={graph.data.nodes} edges={graph.data.edges} colors={colors} maxStrength={detail.max_strength} selection={selection} onSelectNode={selectNode} onSelectEdge={selectEdge} />
          )}
        </div>

        {/* ---- right: reader / entity / search */}
        {showPanel && (
          <aside className="flex w-[420px] shrink-0 flex-col border-l border-line bg-surface">
            {search ? (
              <div className="flex h-full flex-col">
                <div className="panel-head">
                  <span>Search · {results.data ? `${formatNumber(results.data.total)} hits` : "…"}</span>
                  {entityIds.length > 0 && <span className="normal-case tracking-normal">filtered by selection</span>}
                </div>
                <div className="flex-1 overflow-y-auto">
                  {results.isLoading && <Spinner label="Searching" />}
                  {results.data?.hits.map((hit) => (
                    <article key={hit.chunk.id} className="border-b border-line-soft px-4 py-3">
                      <div className="mb-1 font-mono text-[11px] uppercase tracking-wider text-muted">
                        {hit.chunk.document_title} · § {hit.chunk.position + 1}
                      </div>
                      <p className="font-serif text-[14.5px] leading-[1.6]">
                        {splitSnippet(hit.snippet).map((part, i) => (part.mark ? <mark key={i}>{part.text}</mark> : <span key={i}>{part.text}</span>))}
                      </p>
                      <div className="mt-1.5 flex flex-wrap gap-1">
                        {uniqueMentions(hit.chunk.mentions).slice(0, 8).map((m) => (
                          <button key={m.entity_id} type="button" className="chip hover:border-ink-2" onClick={() => selectNode(m.entity_id)}>
                            <Swatch color={colorOf(colors, m.label)} />
                            {hit.chunk.text.slice(m.start, m.end)}
                          </button>
                        ))}
                      </div>
                    </article>
                  ))}
                  {results.data && results.data.hits.length === 0 && <Empty>No passages match “{search}”.</Empty>}
                </div>
              </div>
            ) : selection.edge ? (
              <div className="flex h-full flex-col">
                <div className="panel-head">
                  <span>Cooccurrence</span>
                  <button type="button" className="normal-case tracking-normal hover:text-ink" onClick={() => selectNode(null)}>
                    clear
                  </button>
                </div>
                {edge.isLoading && <Spinner label="Loading passages" />}
                {edge.error && <ErrorNote error={edge.error} />}
                {edge.data && (
                  <>
                    <div className="border-b border-line-soft px-4 py-3">
                      <h2 className="text-[17px] leading-snug">
                        <button type="button" className="hover:text-accent-deep" onClick={() => selectNode(edge.data.source.id)}>{edge.data.source.text}</button>
                        <span className="text-muted"> — </span>
                        <button type="button" className="hover:text-accent-deep" onClick={() => selectNode(edge.data.target.id)}>{edge.data.target.text}</button>
                      </h2>
                      <div className="mt-1 flex gap-1.5">
                        <span className="chip">ω {formatWeight(edge.data.weight)}</span>
                        <span className="chip">{edge.data.count} cooccurrences</span>
                        <span className="chip">{edge.data.chunks.length} shared passages</span>
                      </div>
                    </div>
                    <div className="flex-1 overflow-y-auto">
                      {edge.data.chunks.map((chunk) => (
                        <article key={chunk.id} className="border-b border-line-soft px-4 py-3">
                          <div className="mb-1 font-mono text-[11px] uppercase tracking-wider text-muted">{chunk.document_title} · § {chunk.position + 1}</div>
                          <HighlightedText chunk={chunk} colors={colors} activeEntities={activeEntities} onSelectEntity={selectNode} />
                        </article>
                      ))}
                    </div>
                  </>
                )}
              </div>
            ) : (
              <div className="flex h-full flex-col">
                {selection.nodeId !== null && (
                  <div className="flex border-b border-line-soft text-[13px]">
                    {(["entity", "passages"] as const).map((tab) => (
                      <button key={tab} type="button" className={`flex-1 px-3 py-2 capitalize ${panelTab === tab ? "border-b-2 border-accent-deep font-medium text-ink" : "text-muted hover:text-ink"}`} onClick={() => setPanelTab(tab)}>
                        {tab}
                      </button>
                    ))}
                  </div>
                )}
                {selection.nodeId !== null && panelTab === "entity" ? (
                  <EntityPanel slug={slug} entityId={selection.nodeId} colors={colors} focused={focus === selection.nodeId} onSelectEntity={selectNode} onSelectEdge={selectEdge} onToggleFocus={() => setFocus((f) => (f === selection.nodeId ? null : selection.nodeId))} />
                ) : (
                  <DocumentReader
                    chunks={chunks.data?.items ?? []}
                    colors={colors}
                    activeEntities={activeEntities}
                    onSelectEntity={selectNode}
                    header={
                      <div className="panel-head">
                        <span>
                          {selection.nodeId !== null ? "Passages mentioning the entity" : documentId ? "Document" : "Reader"} · {formatNumber(total)}
                        </span>
                        {chunks.isFetching && <span className="normal-case tracking-normal">loading…</span>}
                      </div>
                    }
                    footer={
                      total > PAGE_SIZE ? (
                        <div className="flex items-center justify-between px-4 py-3 font-mono text-[12px] text-muted">
                          <button type="button" className="btn btn-sm" disabled={page <= 1} onClick={() => setPage((p) => p - 1)}>
                            ← prev
                          </button>
                          <span>
                            {page} / {pages}
                          </span>
                          <button type="button" className="btn btn-sm" disabled={page >= pages} onClick={() => setPage((p) => p + 1)}>
                            next →
                          </button>
                        </div>
                      ) : chunks.data && chunks.data.items.length === 0 ? (
                        <Empty>No passages.</Empty>
                      ) : null
                    }
                  />
                )}
              </div>
            )}
          </aside>
        )}
      </div>
    </div>
  );
}

function uniqueMentions<T extends { entity_id: number }>(mentions: T[]): T[] {
  const seen = new Set<number>();
  return mentions.filter((m) => (seen.has(m.entity_id) ? false : (seen.add(m.entity_id), true)));
}
