import { useLayoutEffect, useRef, useState } from "react";
import { EgoGraph, RelationTag } from "@/components/EgoGraph";
import { Spinner, Swatch } from "@/components/ui";
import { useEntity } from "@/hooks/useApi";
import type { NeighborOut, PageEntity } from "@/lib/api";
import { colorOf, type ColorMap } from "@/lib/colors";
import { formatNumber, formatWeight } from "@/lib/format";

interface Props {
  slug: string;
  entityId: number;
  anchor: DOMRect;
  pageEntities: PageEntity[];
  page: number;
  documentId: number | null;
  hasChapters: boolean;
  colors: ColorMap;
  onSelectEntity: (id: number) => void;
  onMouseEnter: () => void;
  onMouseLeave: () => void;
}

const WIDTH = 320;
const CLOSEST = 6;

/** Hover card for a mention: closest connections and a small ego network (book, chapter or page). */
export function EntityPopover({ slug, entityId, anchor, pageEntities, page, documentId, hasChapters, colors, onSelectEntity, onMouseEnter, onMouseLeave }: Props) {
  const entity = useEntity(slug, entityId, 80);
  const ref = useRef<HTMLDivElement>(null);
  const [position, setPosition] = useState({ top: anchor.bottom + 8, left: anchor.left });

  useLayoutEffect(() => {
    const height = ref.current?.offsetHeight ?? 320;
    const left = Math.min(Math.max(8, anchor.left), window.innerWidth - WIDTH - 8);
    const below = anchor.bottom + 8;
    const top = below + height > window.innerHeight - 8 ? Math.max(8, anchor.top - height - 8) : below;
    setPosition({ top, left });
  }, [anchor, entity.data]);

  const data = entity.data;
  const onPage = new Map(pageEntities.map((e) => [e.id, e.page_mentions]));
  const closest = data?.neighbors.slice(0, CLOSEST) ?? [];

  return (
    <div ref={ref} className="entity-popover" style={{ top: position.top, left: position.left, width: WIDTH }} onMouseEnter={onMouseEnter} onMouseLeave={onMouseLeave} role="tooltip">
      {!data && <Spinner label="Loading" />}
      {data && (
        <>
          <div className="flex items-center gap-2 border-b border-line-soft px-3 py-2">
            <Swatch color={colorOf(colors, data.label)} />
            <button type="button" className="min-w-0 flex-1 truncate text-left text-[14px] font-semibold text-ink hover:text-accent-deep" onClick={() => onSelectEntity(data.id)} title="Select">
              {data.text}
            </button>
            <span className="shrink-0 font-mono text-[10.5px] text-muted">
              {data.label} · {formatNumber(data.count)}×
            </span>
          </div>
          <div className="px-3 py-2">
            <div className="label">Closest connections</div>
            {closest.length === 0 && <p className="text-[12px] text-muted">No cooccurring entities.</p>}
            <ul className="space-y-0.5">
              {closest.map((n: NeighborOut) => (
                <li key={n.entity.id} className="flex items-center gap-1.5 text-[12.5px]">
                  <Swatch color={colorOf(colors, n.entity.label)} />
                  <button type="button" className="min-w-0 flex-1 truncate text-left text-ink hover:text-accent-deep" onClick={() => onSelectEntity(n.entity.id)}>
                    {n.entity.text}
                  </button>
                  <RelationTag relation={n.relation} head={n.relation_head} center={data} other={n.entity} />
                  {onPage.has(n.entity.id) && <span className="chip py-0 text-[9.5px]">on this page</span>}
                  <span className="font-mono text-[10.5px] text-muted">ω {formatWeight(n.weight)}</span>
                </li>
              ))}
            </ul>
          </div>
          <div className="border-t border-line-soft px-3 py-2">
            <div className="label">Ego network</div>
            <EgoGraph slug={slug} center={data} colors={colors} page={page} documentId={documentId} hasChapters={hasChapters} onSelectEntity={onSelectEntity} height={160} />
          </div>
        </>
      )}
    </div>
  );
}
