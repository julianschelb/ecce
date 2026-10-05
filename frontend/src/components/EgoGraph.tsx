import { useLayoutEffect, useMemo, useRef, useState } from "react";
import { useDocumentGraph, useGraph, usePageGraph } from "@/hooks/useApi";
import type { EntityOut, GraphEdge, GraphNode, GraphResponse } from "@/lib/api";
import { colorOf, type ColorMap } from "@/lib/colors";
import { formatWeight } from "@/lib/format";

export type EgoScope = "book" | "chapter" | "page";

interface Props {
  slug: string;
  center: EntityOut;
  colors: ColorMap;
  page: number;
  documentId: number | null;
  hasChapters: boolean;
  onSelectEntity: (id: number) => void;
  /** Most neighbours shown around the centre. */
  size?: number;
  height?: number;
}

const ACCENT = "#33618f";
const INK = "#1f2328";
const BOOK_NODES = 40; // the whole-book ego network is requested with this many nodes

// the last scope chosen is kept for the next entity (popovers are short-lived)
let rememberedScope: EgoScope = "book";

/** Entity (ego) network of an entity in the whole book, the current chapter or the current page: the
 * entity in the middle, its strongest associated entities around it and links between them as
 * chords. */
export function EgoGraph({ slug, center, colors, page, documentId, hasChapters, onSelectEntity, size = 8, height = 170 }: Props) {
  const [scope, setScopeState] = useState<EgoScope>(hasChapters || rememberedScope !== "chapter" ? rememberedScope : "book");
  const setScope = (next: EgoScope) => {
    rememberedScope = next;
    setScopeState(next);
  };
  const bookParams = useMemo(() => ({ min_weight: 0, max_nodes: BOOK_NODES, labels: [], focus: center.id }), [center.id]);
  const book = useGraph(slug, bookParams, scope === "book");
  const chapter = useDocumentGraph(slug, documentId, scope === "chapter");
  const onPage = usePageGraph(slug, page, scope === "page");
  const source = scope === "book" ? book : scope === "chapter" ? chapter : onPage;
  const ego = useMemo(() => (source.data ? egoOf(source.data, center.id, size) : null), [source.data, center.id, size]);

  const ref = useRef<HTMLDivElement>(null);
  const [width, setWidth] = useState(260);
  useLayoutEffect(() => {
    const element = ref.current;
    if (!element) return;
    setWidth(element.getBoundingClientRect().width || 260);
    const observer = new ResizeObserver((entries) => setWidth(entries[0].contentRect.width || 260));
    observer.observe(element);
    return () => observer.disconnect();
  }, []);

  const scopes: [EgoScope, string][] = [["book", "Whole book"], ...(hasChapters ? ([["chapter", "Chapter"]] as [EgoScope, string][]) : []), ["page", "Page"]];
  const where = scope === "book" ? "in the book" : scope === "chapter" ? "in this chapter" : "on this page";
  return (
    <div ref={ref}>
      <div className="seg mb-1.5" role="tablist" aria-label="Entity network scope">
        {scopes.map(([key, label]) => (
          <button key={key} type="button" role="tab" aria-selected={scope === key} className={`!px-2 !py-0.5 !text-[11px] ${scope === key ? "is-active" : ""}`} onClick={() => setScope(key)}>
            {label}
          </button>
        ))}
      </div>
      {!ego ? (
        <div style={{ height }} className="flex items-center justify-center text-[12px] text-muted">
          Loading…
        </div>
      ) : ego.neighbours.length === 0 ? (
        <div style={{ height: Math.min(height, 60) }} className="flex items-center text-[12px] text-muted">
          {ego.present ? `No connections ${where}.` : `Not mentioned ${where}.`}
        </div>
      ) : (
        <EgoSvg center={center} ego={ego} colors={colors} width={width} height={height} onSelectEntity={onSelectEntity} />
      )}
    </div>
  );
}

interface Spoke {
  node: GraphNode;
  edge: GraphEdge;
}

interface Ego {
  present: boolean;
  neighbours: Spoke[];
  chords: GraphEdge[];
}

/** The centre's strongest links in a graph and the links among those neighbours. */
function egoOf(graph: GraphResponse, centerId: number, size: number): Ego {
  const nodes = new Map(graph.nodes.map((n) => [n.id, n]));
  const spokes = graph.edges
    .filter((e) => e.source === centerId || e.target === centerId)
    .map((edge) => ({ node: nodes.get(edge.source === centerId ? edge.target : edge.source), edge }))
    .filter((s): s is Spoke => s.node !== undefined)
    .sort((a, b) => b.edge.weight - a.edge.weight)
    .slice(0, size);
  const ids = new Set(spokes.map((s) => s.node.id));
  const chords = graph.edges.filter((e) => ids.has(e.source) && ids.has(e.target));
  return { present: nodes.has(centerId), neighbours: spokes, chords };
}

function shorten(text: string, max = 16): string {
  return text.length > max ? `${text.slice(0, max - 1)}…` : text;
}

function EgoSvg({ center, ego, colors, width, height, onSelectEntity }: { center: EntityOut; ego: Ego; colors: ColorMap; width: number; height: number; onSelectEntity: (id: number) => void }) {
  const cx = width / 2;
  const cy = height / 2;
  const R = Math.max(40, Math.min(height / 2 - 22, width / 2 - 72));
  const maxW = Math.max(...ego.neighbours.map((s) => s.edge.weight), 1e-9);
  const placed = ego.neighbours.map((spoke, i) => {
    const angle = -Math.PI / 2 + (2 * Math.PI * i) / ego.neighbours.length;
    const rel = spoke.edge.weight / maxW;
    return { ...spoke, angle, rel, x: cx + R * Math.cos(angle), y: cy + R * Math.sin(angle), r: 3.5 + 3.5 * Math.sqrt(rel) };
  });
  const at = new Map(placed.map((p) => [p.node.id, p]));
  const labelChars = Math.max(8, Math.floor((width / 2 - R - 14) / 5.6)); // names fit beside the circle
  const CENTER_R = 7;
  return (
    <svg viewBox={`0 0 ${width} ${height}`} width={width} height={height} className="block" aria-label={`Entity network of ${center.text}`}>
      {ego.chords.map((e) => {
        const a = at.get(e.source);
        const b = at.get(e.target);
        if (!a || !b) return null;
        return <line key={`${e.source}-${e.target}`} x1={a.x} y1={a.y} x2={b.x} y2={b.y} stroke={INK} strokeOpacity={0.12} strokeWidth={0.8} />;
      })}
      {placed.map((p) => (
        <line key={`spoke-${p.node.id}`} x1={cx} y1={cy} x2={p.x} y2={p.y} stroke={ACCENT} strokeOpacity={0.3 + 0.6 * p.rel} strokeWidth={0.8 + 2.2 * p.rel} />
      ))}
      {placed.map((p) => {
        const cos = Math.cos(p.angle);
        const sin = Math.sin(p.angle);
        const vertical = Math.abs(cos) < 0.35;
        const anchor = vertical ? "middle" : cos > 0 ? "start" : "end";
        const lx = vertical ? p.x : p.x + (cos > 0 ? p.r + 4 : -(p.r + 4));
        const ly = vertical ? p.y + (sin > 0 ? p.r + 11 : -(p.r + 5)) : p.y + 3.5;
        return (
          <g key={p.node.id} className="cursor-pointer" onClick={() => onSelectEntity(p.node.id)}>
            <circle cx={p.x} cy={p.y} r={p.r} fill={colorOf(colors, p.node.label)} stroke="#fff" strokeWidth={1} />
            <text x={lx} y={ly} textAnchor={anchor} fontSize="10" fontFamily="IBM Plex Sans, sans-serif" fill={INK}>
              {shorten(p.node.text, vertical ? 22 : labelChars)}
              <title>
                {p.node.text} · association score {formatWeight(p.edge.weight)} · {p.edge.count} co-occurrences
              </title>
            </text>
          </g>
        );
      })}
      <circle cx={cx} cy={cy} r={CENTER_R} fill={colorOf(colors, center.label)} stroke={INK} strokeWidth={1.5} />
    </svg>
  );
}
