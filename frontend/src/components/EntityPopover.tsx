import { useLayoutEffect, useRef, useState } from "react";
import { Spinner, Swatch } from "@/components/ui";
import { useEntity } from "@/hooks/useApi";
import type { EntityOut, NeighborOut, PageEntity } from "@/lib/api";
import { colorOf, type ColorMap } from "@/lib/colors";
import { formatNumber, formatWeight } from "@/lib/format";

interface Props {
  slug: string;
  entityId: number;
  anchor: DOMRect;
  pageEntities: PageEntity[];
  colors: ColorMap;
  onSelectEntity: (id: number) => void;
  onMouseEnter: () => void;
  onMouseLeave: () => void;
}

const WIDTH = 300;
const CLOSEST = 6;
const PAGE_EGO = 8;

/** Hover card for a mention: closest connections and a small ego network of this page only. */
export function EntityPopover({ slug, entityId, anchor, pageEntities, colors, onSelectEntity, onMouseEnter, onMouseLeave }: Props) {
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
  const pageNeighbours = (data?.neighbors ?? []).filter((n) => onPage.has(n.entity.id)).slice(0, PAGE_EGO);

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
                  {onPage.has(n.entity.id) && <span className="chip py-0 text-[9.5px]">on this page</span>}
                  <span className="font-mono text-[10.5px] text-muted">ω {formatWeight(n.weight)}</span>
                </li>
              ))}
            </ul>
          </div>
          <div className="border-t border-line-soft px-3 py-2">
            <div className="label">Ego network on this page</div>
            {pageNeighbours.length === 0 ? (
              <p className="text-[12px] text-muted">None of its connections is mentioned on this page.</p>
            ) : (
              <MiniEgo center={data} neighbours={pageNeighbours} colors={colors} onSelectEntity={onSelectEntity} />
            )}
          </div>
        </>
      )}
    </div>
  );
}

function shorten(text: string, max = 14): string {
  return text.length > max ? `${text.slice(0, max - 1)}…` : text;
}

/** Radial layout: the hovered entity in the middle, its page neighbours around it (edge width ∝ ω). */
function MiniEgo({ center, neighbours, colors, onSelectEntity }: { center: EntityOut; neighbours: NeighborOut[]; colors: ColorMap; onSelectEntity: (id: number) => void }) {
  const W = WIDTH - 24;
  const H = 150;
  const cx = W / 2;
  const cy = H / 2;
  const R = 48;
  const maxW = Math.max(...neighbours.map((n) => n.weight), 1e-9);
  return (
    <svg viewBox={`0 0 ${W} ${H}`} width={W} height={H} className="block" aria-label={`Ego network of ${center.text} on this page`}>
      {neighbours.map((n, i) => {
        const angle = -Math.PI / 2 + (2 * Math.PI * i) / neighbours.length;
        const cos = Math.cos(angle);
        const sin = Math.sin(angle);
        const x = cx + R * cos;
        const y = cy + R * sin;
        const rel = n.weight / maxW;
        const r = 3.5 + 3 * Math.sqrt(rel);
        const vertical = Math.abs(cos) < 0.35;
        const anchor = vertical ? "middle" : cos > 0 ? "start" : "end";
        const lx = vertical ? x : x + (cos > 0 ? r + 4 : -(r + 4));
        const ly = vertical ? y + (sin > 0 ? r + 11 : -(r + 5)) : y + 3.5;
        return (
          <g key={n.entity.id} className="cursor-pointer" onClick={() => onSelectEntity(n.entity.id)}>
            <line x1={cx} y1={cy} x2={x} y2={y} stroke="#33618f" strokeOpacity={0.25 + 0.65 * rel} strokeWidth={0.8 + 2.4 * rel} />
            <circle cx={x} cy={y} r={r} fill={colorOf(colors, n.entity.label)} stroke="#fff" strokeWidth={1} />
            <text x={lx} y={ly} textAnchor={anchor} fontSize="9.5" fontFamily="IBM Plex Sans, sans-serif" fill="#1f2328">
              {shorten(n.entity.text)}
              <title>
                {n.entity.text} · ω {formatWeight(n.weight)} · {n.count} cooccurrences
              </title>
            </text>
          </g>
        );
      })}
      <circle cx={cx} cy={cy} r={7} fill={colorOf(colors, center.label)} stroke="#1f2328" strokeWidth={1.5} />
    </svg>
  );
}
