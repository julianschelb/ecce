import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import ForceGraph2D, { type ForceGraphMethods, type LinkObject, type NodeObject } from "react-force-graph-2d";
import type { GraphEdge, GraphNode } from "@/lib/api";
import { colorOf, withAlpha, type ColorMap } from "@/lib/colors";

export interface Selection {
  nodeId: number | null;
  edge: [number, number] | null;
}

interface Props {
  nodes: GraphNode[];
  edges: GraphEdge[];
  colors: ColorMap;
  maxStrength: number;
  selection: Selection;
  onSelectNode: (id: number | null) => void;
  onSelectEdge: (a: number, b: number) => void;
}

type FGNode = NodeObject<GraphNode & { r: number }>;
type FGLink = LinkObject<FGNode, GraphEdge & { w: number }>;

const INK = "#1f2328";
const SURFACE = "#f7f6f2";

export function GraphViewer({ nodes, edges, colors, maxStrength, selection, onSelectNode, onSelectEdge }: Props) {
  const containerRef = useRef<HTMLDivElement>(null);
  const graphRef = useRef<ForceGraphMethods<FGNode, FGLink> | undefined>(undefined);
  const [size, setSize] = useState({ width: 600, height: 500 });
  const [hovered, setHovered] = useState<number | null>(null);

  useEffect(() => {
    const element = containerRef.current;
    if (!element) return;
    const observer = new ResizeObserver((entries) => {
      const rect = entries[0].contentRect;
      setSize({ width: Math.max(200, rect.width), height: Math.max(200, rect.height) });
    });
    observer.observe(element);
    return () => observer.disconnect();
  }, []);

  // Fresh node objects per data change (the force engine mutates them).
  const data = useMemo(() => {
    const maxS = Math.max(maxStrength, ...nodes.map((n) => n.strength), 1e-9);
    const minW = edges.length ? Math.min(...edges.map((e) => e.weight)) : 0;
    const maxW = edges.length ? Math.max(...edges.map((e) => e.weight)) : 1;
    const span = Math.max(maxW - minW, 1e-9);
    return {
      nodes: nodes.map((n) => ({ ...n, r: 3 + 9 * Math.sqrt(n.strength / maxS) })) as FGNode[],
      links: edges.map((e) => ({ ...e, w: (e.weight - minW) / span })) as FGLink[],
    };
  }, [nodes, edges, maxStrength]);

  const neighbours = useMemo(() => {
    const set = new Set<number>();
    if (selection.nodeId !== null) {
      for (const e of edges) {
        if (e.source === selection.nodeId) set.add(e.target);
        if (e.target === selection.nodeId) set.add(e.source);
      }
    }
    return set;
  }, [edges, selection.nodeId]);

  const labelled = useMemo(() => {
    const top = [...nodes].sort((a, b) => b.strength - a.strength).slice(0, 30);
    return new Set(top.map((n) => n.id));
  }, [nodes]);

  useEffect(() => {
    const graph = graphRef.current;
    if (!graph) return;
    graph.d3Force("charge")?.strength(-60);
    graph.d3Force("link")?.distance((link: FGLink) => 40 + 60 * (1 - (link.w ?? 0)));
  }, [data]);

  const endpointId = (end: FGLink["source"]): number => (typeof end === "object" && end !== null ? (end as FGNode).id : (end as number));

  const isDimmed = useCallback(
    (id: number) => {
      const active = selection.nodeId ?? hovered;
      if (active === null) return false;
      if (id === active) return false;
      if (selection.nodeId !== null) return !neighbours.has(id);
      return false;
    },
    [selection.nodeId, hovered, neighbours],
  );

  const drawNode = useCallback(
    (node: FGNode, ctx: CanvasRenderingContext2D, scale: number) => {
      const x = node.x ?? 0;
      const y = node.y ?? 0;
      const dim = isDimmed(node.id);
      const selected = selection.nodeId === node.id;
      const color = colorOf(colors, node.label);
      ctx.beginPath();
      ctx.arc(x, y, node.r, 0, 2 * Math.PI);
      ctx.fillStyle = dim ? withAlpha(color, 0.25) : color;
      ctx.fill();
      ctx.lineWidth = selected ? 2.2 / scale : 1 / scale;
      ctx.strokeStyle = selected ? INK : SURFACE;
      ctx.stroke();
      const showLabel = selected || hovered === node.id || neighbours.has(node.id) || (labelled.has(node.id) && scale > 0.6) || scale > 2.2;
      if (showLabel && !dim) {
        const fontSize = Math.max(11 / scale, 2.5);
        ctx.font = `${selected ? 600 : 500} ${fontSize}px "IBM Plex Sans", sans-serif`;
        ctx.textAlign = "center";
        ctx.textBaseline = "top";
        ctx.lineWidth = 3 / scale;
        ctx.strokeStyle = SURFACE;
        ctx.lineJoin = "round";
        ctx.strokeText(node.text, x, y + node.r + 2 / scale);
        ctx.fillStyle = INK;
        ctx.fillText(node.text, x, y + node.r + 2 / scale);
      }
    },
    [colors, isDimmed, selection.nodeId, hovered, neighbours, labelled],
  );

  const linkColor = useCallback(
    (link: FGLink) => {
      const a = endpointId(link.source);
      const b = endpointId(link.target);
      const active = selection.nodeId;
      const isEdge = selection.edge && ((selection.edge[0] === a && selection.edge[1] === b) || (selection.edge[0] === b && selection.edge[1] === a));
      if (isEdge) return "#33618f";
      if (active !== null) return a === active || b === active ? withAlpha("#33618f", 0.75) : withAlpha(INK, 0.05);
      return withAlpha(INK, 0.1 + 0.4 * (link.w ?? 0));
    },
    [selection],
  );

  return (
    <div ref={containerRef} className="relative h-full w-full">
      <ForceGraph2D
        ref={graphRef}
        width={size.width}
        height={size.height}
        graphData={data}
        backgroundColor={SURFACE}
        nodeId="id"
        nodeRelSize={1}
        nodeVal={(n) => n.r * n.r}
        nodeLabel={(n) => `${n.text} · ${n.label} · ${n.count} mentions`}
        nodeCanvasObject={drawNode}
        nodePointerAreaPaint={(node, color, ctx) => {
          ctx.beginPath();
          ctx.arc(node.x ?? 0, node.y ?? 0, node.r + 2, 0, 2 * Math.PI);
          ctx.fillStyle = color;
          ctx.fill();
        }}
        linkWidth={(l) => 0.6 + 4 * (l.w ?? 0)}
        linkColor={linkColor}
        linkLabel={(l) => `weight ${l.weight.toFixed(2)} · ${l.count} cooccurrences`}
        onNodeClick={(node) => onSelectNode(selection.nodeId === node.id ? null : node.id)}
        onNodeHover={(node) => setHovered(node ? node.id : null)}
        onLinkClick={(link) => onSelectEdge(endpointId(link.source), endpointId(link.target))}
        onBackgroundClick={() => onSelectNode(null)}
        cooldownTicks={150}
        warmupTicks={40}
        onEngineStop={() => graphRef.current?.zoomToFit(500, 40)}
        enableNodeDrag
      />
      <div className="pointer-events-none absolute bottom-2 right-3 font-mono text-[11px] text-muted">
        {nodes.length} nodes · {edges.length} edges
      </div>
    </div>
  );
}
