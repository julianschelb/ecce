import { useMemo, useState } from "react";
import { PageNumbers } from "@/components/PageNumbers";
import { SearchBar } from "@/components/SearchBar";
import { Empty, ErrorNote, Spinner, Swatch } from "@/components/ui";
import { useIndex } from "@/hooks/useApi";
import type { CorpusDetail, DocumentOut, SearchResponse } from "@/lib/api";
import { colorOf, type ColorMap } from "@/lib/colors";
import { formatNumber, splitSnippet } from "@/lib/format";

export type SidebarTab = "index" | "contents" | "search";

interface Props {
  slug: string;
  corpus: CorpusDetail;
  documents: DocumentOut[];
  colors: ColorMap;
  page: number;
  currentDocumentId: number | null;
  selectedEntityId: number | null;
  tab: SidebarTab;
  onTab: (tab: SidebarTab) => void;
  search: string;
  results?: SearchResponse;
  searchLoading: boolean;
  filteredBySelection: boolean;
  onGoTo: (page: number, entityId?: number | null) => void;
  onSelectEntity: (id: number) => void;
}

/** Left rail of the explorer: the book index, the table of contents and search results. */
export function ReaderSidebar(props: Props) {
  const { tab, onTab, search } = props;
  const tabs: Array<[SidebarTab, string]> = [
    ["index", "Index"],
    ["contents", "Contents"],
  ];
  if (search) tabs.push(["search", "Search"]);
  return (
    <aside className="flex w-[300px] shrink-0 flex-col border-r border-line bg-surface" aria-label="Index and contents">
      <div className="flex border-b border-line-soft text-[13px]">
        {tabs.map(([key, label]) => (
          <button key={key} type="button" className={`flex-1 px-3 py-2 ${tab === key ? "border-b-2 border-accent-deep font-medium text-ink" : "text-muted hover:text-ink"}`} onClick={() => onTab(key)}>
            {label}
          </button>
        ))}
      </div>
      {tab === "index" && <EntityIndex {...props} />}
      {tab === "contents" && <Contents {...props} />}
      {tab === "search" && <SearchResults {...props} />}
    </aside>
  );
}

const INDEX_STEP = 150;

function EntityIndex({ slug, corpus, colors, page, selectedEntityId, onGoTo, onSelectEntity }: Props) {
  const index = useIndex(slug);
  const [filter, setFilter] = useState("");
  const [label, setLabel] = useState<string | null>(null);
  const [shown, setShown] = useState(INDEX_STEP);
  const labels = Object.keys(corpus.label_counts);
  const entries = useMemo(() => {
    const q = filter.trim().toLowerCase();
    return (index.data?.entries ?? []).filter((e) => (label === null || e.entity.label === label) && (!q || e.entity.text.toLowerCase().includes(q)));
  }, [index.data, filter, label]);
  return (
    <div className="flex min-h-0 flex-1 flex-col">
      <div className="space-y-2 border-b border-line-soft p-3">
        <SearchBar value={filter} onChange={setFilter} placeholder="Filter the index…" />
        <div className="flex flex-wrap gap-1">
          {labels.map((l) => (
            <button key={l} type="button" className={`chip hover:border-ink-2 ${label === l ? "chip--on" : ""}`} onClick={() => setLabel(label === l ? null : l)} title={`${corpus.label_counts[l]} entities`}>
              <Swatch color={colorOf(colors, l)} />
              {l}
            </button>
          ))}
        </div>
      </div>
      <div className="panel-head">
        <span>{formatNumber(entries.length)} entries</span>
        <span className="normal-case tracking-normal">mentions · pages</span>
      </div>
      <ul className="min-h-0 flex-1 overflow-y-auto">
        {index.isLoading && <Spinner label="Building the index" />}
        {index.error && <ErrorNote error={index.error} />}
        {entries.slice(0, shown).map(({ entity, pages }) => (
          <li key={entity.id} className={`border-b border-line-soft px-3 py-2 ${selectedEntityId === entity.id ? "bg-select/60" : ""}`}>
            <div className="flex items-center gap-2">
              <Swatch color={colorOf(colors, entity.label)} />
              <button type="button" className="min-w-0 flex-1 truncate text-left text-[13px] font-medium text-ink hover:text-accent-deep" onClick={() => onSelectEntity(entity.id)} title={`${entity.label} · select in the graph`}>
                {entity.text}
              </button>
              <span className="font-mono text-[11px] text-muted">
                {formatNumber(entity.count)} · {pages.length}
              </span>
            </div>
            <div className="mt-0.5 pl-[18px]">
              <PageNumbers pages={pages} current={page} onGoTo={(p) => onGoTo(p, entity.id)} limit={14} />
            </div>
          </li>
        ))}
        {entries.length > shown && (
          <li className="p-3 text-center">
            <button type="button" className="btn btn-sm" onClick={() => setShown((s) => s + INDEX_STEP)}>
              Show more · {formatNumber(entries.length - shown)} left
            </button>
          </li>
        )}
        {index.data && entries.length === 0 && <Empty>No entity matches.</Empty>}
      </ul>
    </div>
  );
}

function Contents({ documents, corpus, currentDocumentId, onGoTo }: Props) {
  return (
    <ol className="min-h-0 flex-1 overflow-y-auto">
      {documents.map((d, i) => {
        const last = i + 1 < documents.length ? documents[i + 1].first_page - 1 : corpus.n_pages;
        const current = d.id === currentDocumentId;
        return (
          <li key={d.id}>
            <button type="button" className={`flex w-full items-baseline gap-3 border-b border-line-soft px-4 py-2.5 text-left hover:bg-select/40 ${current ? "bg-select/60" : ""}`} onClick={() => onGoTo(d.first_page)}>
              <span className="w-5 shrink-0 font-mono text-[11px] text-muted">{i + 1}</span>
              <span className={`min-w-0 flex-1 truncate font-serif text-[14px] ${current ? "font-semibold" : ""}`}>{d.title}</span>
              <span className="shrink-0 font-mono text-[11px] text-accent-deep">
                {d.first_page}
                {last > d.first_page ? `–${last}` : ""}
              </span>
            </button>
          </li>
        );
      })}
      {documents.length === 0 && <Empty>No documents.</Empty>}
    </ol>
  );
}

function SearchResults({ search, results, searchLoading, filteredBySelection, page, onGoTo }: Props) {
  return (
    <div className="flex min-h-0 flex-1 flex-col">
      <div className="panel-head">
        <span>{results ? `${formatNumber(results.total)} passages` : "Searching…"}</span>
        {filteredBySelection && <span className="normal-case tracking-normal">within selection</span>}
      </div>
      <ul className="min-h-0 flex-1 overflow-y-auto">
        {searchLoading && !results && <Spinner label="Searching" />}
        {results?.hits.map((hit) => (
          <li key={hit.chunk.id}>
            <button type="button" className="w-full border-b border-line-soft px-4 py-3 text-left hover:bg-select/40" onClick={() => onGoTo(hit.chunk.page)} title={`Open page ${hit.chunk.page}`}>
              <div className="mb-1 flex items-baseline justify-between gap-2 font-mono text-[11px] uppercase tracking-wider text-muted">
                <span className="truncate">{hit.chunk.document_title}</span>
                <span className={`pageno shrink-0 normal-case ${hit.chunk.page === page ? "pageno--current" : ""}`}>p. {hit.chunk.page}</span>
              </div>
              <p className="font-serif text-[13.5px] leading-[1.55] text-ink-2">
                {splitSnippet(hit.snippet).map((part, i) => (part.mark ? <mark key={i}>{part.text}</mark> : <span key={i}>{part.text}</span>))}
              </p>
            </button>
          </li>
        ))}
        {results && results.hits.length === 0 && <Empty>No passages match “{search}”.</Empty>}
      </ul>
    </div>
  );
}
