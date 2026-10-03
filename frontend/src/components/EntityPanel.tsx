import { AssociatedEntities } from "@/components/AssociatedEntities";
import { EgoGraph } from "@/components/EgoGraph";
import { PageNumbers, nextPageAfter } from "@/components/PageNumbers";
import { Empty, ErrorNote, Spinner, Swatch } from "@/components/ui";
import { useEntity, usePageRefs } from "@/hooks/useApi";
import { colorOf, type ColorMap } from "@/lib/colors";
import { formatNumber, formatWeight } from "@/lib/format";

interface Props {
  slug: string;
  entityId: number;
  colors: ColorMap;
  page: number;
  documentId: number | null;
  hasChapters: boolean;
  onGoTo: (page: number, entityId?: number | null) => void;
  onSelectEntity: (id: number) => void;
  onSelectEdge: (a: number, b: number) => void;
  onClear: () => void;
}

/** Details of a selected entity: where it is mentioned (pages) and its strongest relations. */
export function EntityPanel({ slug, entityId, colors, page, documentId, hasChapters, onGoTo, onSelectEntity, onSelectEdge, onClear }: Props) {
  const entity = useEntity(slug, entityId);
  const refs = usePageRefs(slug, { entity_id: [entityId], document_id: null });
  if (entity.isLoading) return <Spinner label="Loading entity" />;
  if (entity.error) return <ErrorNote error={entity.error} />;
  if (!entity.data) return <Empty>Select an entity in the graph.</Empty>;
  const data = entity.data;
  const pages = refs.data?.items.map((r) => r.number) ?? [];
  const next = nextPageAfter(pages, page);
  return (
    <div className="flex h-full flex-col">
      <div className="border-b border-line-soft px-4 py-3">
        <div className="flex items-center gap-2">
          <Swatch color={colorOf(colors, data.label)} />
          <h2 className="min-w-0 flex-1 truncate text-[19px] leading-tight">{data.text}</h2>
          <button type="button" className="font-mono text-[12px] text-muted hover:text-ink" onClick={onClear} title="Clear selection">
            clear
          </button>
        </div>
        <div className="mt-1.5 flex flex-wrap gap-1.5">
          <span className="chip">{data.label}</span>
          <span className="chip">{formatNumber(data.count)} occurrences</span>
          <span className="chip">{refs.data ? `${formatNumber(refs.data.total)} pages` : "… pages"}</span>
          <span className="chip">{formatNumber(data.degree)} associated entities</span>
          <span className="chip" title="Sum of its association scores">association strength {formatWeight(data.strength)}</span>
        </div>
        {next !== null && (
          <button type="button" className="btn btn-sm btn-primary mt-2.5" onClick={() => onGoTo(next, entityId)} title="Open the next page that mentions this entity">
            {next > page ? "Next mention" : "First mention"} · p. {next}
          </button>
        )}
      </div>
      <div className="min-h-0 flex-1 overflow-y-auto">
        <div className="panel-head">Entity network</div>
        <div className="px-4 py-2.5">
          <EgoGraph slug={slug} center={data} colors={colors} page={page} documentId={documentId} hasChapters={hasChapters} onSelectEntity={onSelectEntity} size={10} height={210} />
        </div>
        <div className="panel-head">
          <span>Pages</span>
          {refs.isFetching && <span className="normal-case tracking-normal">loading…</span>}
        </div>
        <div className="px-4 py-2.5">
          <PageNumbers pages={pages} current={page} onGoTo={(p) => onGoTo(p, entityId)} limit={48} />
        </div>
        <div className="panel-head">Associated entities</div>
        <div className="px-4 py-2.5">
          {data.neighbors.length === 0 ? <Empty>No associated entities within the window.</Empty> : <AssociatedEntities entity={data} neighbours={data.neighbors} colors={colors} onSelectEntity={onSelectEntity} onSelectEdge={onSelectEdge} />}
        </div>
      </div>
    </div>
  );
}
