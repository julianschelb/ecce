import { useLayoutEffect, useRef, useState } from "react";
import { AssociatedEntities } from "@/components/AssociatedEntities";
import { EgoGraph } from "@/components/EgoGraph";
import { Spinner, Swatch } from "@/components/ui";
import { useEntity } from "@/hooks/useApi";

import { colorOf, type ColorMap } from "@/lib/colors";
import { formatNumber } from "@/lib/format";

interface Props {
  slug: string;
  entityId: number;
  anchor: DOMRect;
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

/** Hover card for a mention: its associated entities and its entity network (book, chapter or page). */
export function EntityPopover({ slug, entityId, anchor, page, documentId, hasChapters, colors, onSelectEntity, onMouseEnter, onMouseLeave }: Props) {
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
              {data.label} · {formatNumber(data.count)} occurrences
            </span>
          </div>
          <div className="px-3 py-2">
            <div className="label">Associated entities</div>
            {closest.length === 0 ? <p className="text-[12px] text-muted">No associated entities.</p> : <AssociatedEntities entity={data} neighbours={closest} colors={colors} onSelectEntity={onSelectEntity} compact />}
          </div>
          <div className="border-t border-line-soft px-3 py-2">
            <div className="label">Entity network</div>
            <EgoGraph slug={slug} center={data} colors={colors} page={page} documentId={documentId} hasChapters={hasChapters} onSelectEntity={onSelectEntity} height={160} />
          </div>
        </>
      )}
    </div>
  );
}
