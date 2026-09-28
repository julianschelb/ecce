import { useEntity } from "@/hooks/useApi";
import { colorOf, type ColorMap } from "@/lib/colors";
import { formatNumber, formatWeight } from "@/lib/format";
import { Empty, ErrorNote, Spinner, Swatch } from "@/components/ui";

interface Props {
  slug: string;
  entityId: number;
  colors: ColorMap;
  focused: boolean;
  onSelectEntity: (id: number) => void;
  onSelectEdge: (a: number, b: number) => void;
  onToggleFocus: () => void;
}

export function EntityPanel({ slug, entityId, colors, focused, onSelectEntity, onSelectEdge, onToggleFocus }: Props) {
  const { data, isLoading, error } = useEntity(slug, entityId);
  if (isLoading) return <Spinner label="Loading entity" />;
  if (error) return <ErrorNote error={error} />;
  if (!data) return <Empty>Select an entity in the graph.</Empty>;
  return (
    <div className="flex h-full flex-col">
      <div className="border-b border-line-soft px-4 py-3">
        <div className="flex items-center gap-2">
          <Swatch color={colorOf(colors, data.label)} />
          <h2 className="text-[20px] leading-tight">{data.text}</h2>
        </div>
        <div className="mt-1 flex flex-wrap gap-1.5">
          <span className="chip">{data.label}</span>
          <span className="chip">{formatNumber(data.count)} mentions</span>
          <span className="chip">{formatNumber(data.n_chunks)} passages</span>
          <span className="chip">{data.degree} neighbours</span>
          <span className="chip">strength {formatWeight(data.strength)}</span>
        </div>
        <div className="mt-3 flex gap-2">
          <button type="button" className={`btn btn-sm ${focused ? "btn-primary" : ""}`} onClick={onToggleFocus}>
            {focused ? "Exit ego network" : "Ego network"}
          </button>
        </div>
      </div>
      <div className="panel-head">Strongest relations</div>
      <ul className="flex-1 overflow-y-auto">
        {data.neighbors.map((n) => (
          <li key={n.entity.id} className="flex items-center gap-2 border-b border-line-soft px-4 py-1.5 text-[13px]">
            <Swatch color={colorOf(colors, n.entity.label)} />
            <button type="button" className="flex-1 truncate text-left text-ink hover:text-accent-deep" onClick={() => onSelectEntity(n.entity.id)} title="Select entity">
              {n.entity.text}
            </button>
            <button type="button" className="font-mono text-[11px] text-muted hover:text-accent-deep" onClick={() => onSelectEdge(data.id, n.entity.id)} title="Show cooccurrence passages">
              ω {formatWeight(n.weight)} · {n.count}
            </button>
          </li>
        ))}
        {data.neighbors.length === 0 && <Empty>No cooccurring entities within the window.</Empty>}
      </ul>
    </div>
  );
}
