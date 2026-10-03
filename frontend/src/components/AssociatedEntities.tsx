import { Fragment } from "react";
import { RelationTag } from "@/components/EgoGraph";
import { Swatch } from "@/components/ui";
import type { EntityOut, NeighborOut } from "@/lib/api";
import { colorOf, type ColorMap } from "@/lib/colors";
import { formatNumber, formatWeight } from "@/lib/format";

/** The association score ω of a link as a share of the entity's total association strength. */
export function associationShare(weight: number, entity: EntityOut): string {
  const share = entity.strength > 0 ? (100 * weight) / entity.strength : 0;
  return share >= 10 ? `${share.toFixed(0)}%` : share >= 1 ? `${share.toFixed(1)}%` : "<1%";
}

export function associationTitle(n: NeighborOut, entity: EntityOut): string {
  return `Association score ω = ${formatWeight(n.weight)}: ${associationShare(n.weight, entity)} of ${entity.text}’s total association strength (${formatWeight(entity.strength)}) · ${formatNumber(n.count)} co-occurrences`;
}

interface Props {
  entity: EntityOut;
  neighbours: NeighborOut[];
  colors: ColorMap;
  onSelectEntity: (id: number) => void;
  /** Clicking the score opens the pages where both entities occur. */
  onSelectEdge?: (a: number, b: number) => void;
  compact?: boolean;
}

/** Associated entities in aligned columns: name, relation type (when extracted) and the
 * association score as a percentage (the raw score is in the tooltip). */
export function AssociatedEntities({ entity, neighbours, colors, onSelectEntity, onSelectEdge, compact = false }: Props) {
  const withRelations = neighbours.some((n) => n.relation);
  const text = compact ? "text-[12.5px]" : "text-[13px]";
  return (
    <div className={`grid items-center gap-x-2 ${compact ? "gap-y-0.5" : "gap-y-1"} ${withRelations ? "grid-cols-[minmax(0,1fr)_minmax(0,7rem)_3.2rem]" : "grid-cols-[minmax(0,1fr)_3.2rem]"}`}>
      <span className="label mb-0 text-[10px]">Entity</span>
      {withRelations && <span className="label mb-0 text-[10px]">Relation</span>}
      <span className="label mb-0 text-right text-[10px]" title="Share of the entity’s total association strength; hover a value for the raw score">
        Score
      </span>
      {neighbours.map((n) => (
        <Fragment key={n.entity.id}>
          <span className={`flex min-w-0 items-center gap-1.5 ${text}`}>
            <Swatch color={colorOf(colors, n.entity.label)} />
            <button type="button" className="min-w-0 flex-1 truncate text-left text-ink hover:text-accent-deep" onClick={() => onSelectEntity(n.entity.id)} title={`${n.entity.text} · ${formatNumber(n.entity.count)} occurrences`}>
              {n.entity.text}
            </button>
          </span>
          {withRelations && (
            <span className="min-w-0 truncate">
              <RelationTag relation={n.relation} head={n.relation_head} center={entity} other={n.entity} />
            </span>
          )}
          {onSelectEdge ? (
            <button type="button" className="text-right font-mono text-[11px] text-muted hover:text-accent-deep" onClick={() => onSelectEdge(entity.id, n.entity.id)} title={`${associationTitle(n, entity)} · click for the pages where both occur`}>
              {associationShare(n.weight, entity)}
            </button>
          ) : (
            <span className="cursor-help text-right font-mono text-[11px] text-muted" title={associationTitle(n, entity)}>
              {associationShare(n.weight, entity)}
            </span>
          )}
        </Fragment>
      ))}
    </div>
  );
}
