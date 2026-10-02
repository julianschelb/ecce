import { Swatch } from "@/components/ui";
import type { CorpusDetail } from "@/lib/api";
import { colorOf, type ColorMap } from "@/lib/colors";
import { LANGUAGE_NAMES, formatNumber, formatYear } from "@/lib/format";

const NOTICE = "https://github.com/julianschelb/ecce/blob/main/backend/data/seed/NOTICE.md";

interface Props {
  corpus: CorpusDetail;
  colors: ColorMap;
  onSelectEntity: (id: number) => void;
}

function Ext({ href, children }: { href: string; children: React.ReactNode }) {
  return (
    <a className="text-accent-deep underline decoration-accent/40 underline-offset-2 hover:decoration-accent-deep" href={href} target="_blank" rel="noreferrer">
      {children}
    </a>
  );
}

function Section({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <section className="border-b border-line-soft px-4 py-3.5">
      <h3 className="label mb-2">{title}</h3>
      {children}
    </section>
  );
}

/** The right rail's Details tab: what the book is, what the network contains, and where the
 * text comes from under which licence (shown wherever the text is shown, as CC BY-SA requires). */
export function BookDetails({ corpus, colors, onSelectEntity }: Props) {
  const stats: Array<[string, number]> = [
    ["Pages", corpus.n_pages],
    ["Passages", corpus.n_chunks],
    ["Chapters", corpus.n_documents],
    ["Entities", corpus.n_entities],
    ["Relations", corpus.n_edges],
    ["Mentions", corpus.n_mentions],
  ];
  const shareAlike = /CC BY-SA/i.test(corpus.license);
  const rights = corpus.rights.split("\n").filter(Boolean);
  return (
    <div className="min-h-0 flex-1 overflow-y-auto">
      <div className="border-b border-line-soft px-4 py-4">
        <div className="font-mono text-[10.5px] uppercase tracking-[0.16em] text-muted">
          {corpus.author || "Anonymous"}
          {corpus.year !== null ? ` · ${formatYear(corpus.year)}` : ""}
        </div>
        <h2 className="mt-1 text-[21px] leading-snug">{corpus.title}</h2>
        <div className="mt-1 font-mono text-[10.5px] uppercase tracking-wider text-muted">
          {[corpus.genre, LANGUAGE_NAMES[corpus.language] ?? corpus.language].filter(Boolean).join(" · ")}
        </div>
        {corpus.description && <p className="mt-2.5 font-serif text-[14.5px] leading-[1.55] text-ink-2">{corpus.description}</p>}
      </div>

      <Section title="Source and licence">
        {corpus.license || corpus.source ? (
          <dl className="space-y-2 text-[13.5px] leading-[1.5]">
            {corpus.source && (
              <div>
                <dt className="font-mono text-[10px] uppercase tracking-wider text-muted">Original source</dt>
                <dd>{corpus.source_url ? <Ext href={corpus.source_url}>{corpus.source}</Ext> : corpus.source}</dd>
              </div>
            )}
            {corpus.license && (
              <div>
                <dt className="font-mono text-[10px] uppercase tracking-wider text-muted">Licence of the text</dt>
                <dd>{corpus.license_url ? <Ext href={corpus.license_url}>{corpus.license}</Ext> : corpus.license}</dd>
              </div>
            )}
            {rights.length > 0 && (
              <div>
                <dt className="font-mono text-[10px] uppercase tracking-wider text-muted">Rights</dt>
                <dd>
                  <ul className="space-y-1 text-ink-2">
                    {rights.map((line) => (
                      <li key={line}>{line}</li>
                    ))}
                  </ul>
                </dd>
              </div>
            )}
            <div>
              <dt className="font-mono text-[10px] uppercase tracking-wider text-muted">Annotations and network</dt>
              <dd className="text-ink-2">
                Entities were recognised automatically ({corpus.extractor || "NER"}) and linked when mentioned within {corpus.window} sentences of each other. This data is licensed{" "}
                {shareAlike ? (
                  <>
                    under the same licence as the text (<Ext href={corpus.license_url}>{corpus.license}</Ext>).
                  </>
                ) : (
                  <>under the MIT licence, like the ECCE code.</>
                )}{" "}
                <Ext href={NOTICE}>Licence notice</Ext>
              </dd>
            </div>
          </dl>
        ) : (
          <p className="text-[13px] text-muted">No source or licence information was provided for this text.</p>
        )}
      </Section>

      <Section title="In numbers">
        <dl className="grid grid-cols-3 gap-x-3 gap-y-2.5">
          {stats.map(([label, value]) => (
            <div key={label}>
              <dt className="font-mono text-[9.5px] uppercase tracking-wider text-muted">{label}</dt>
              <dd className="font-mono text-[15px] text-ink">{formatNumber(value)}</dd>
            </div>
          ))}
        </dl>
      </Section>

      {Object.keys(corpus.label_counts).length > 0 && (
        <Section title="Entity types">
          <ul className="flex flex-wrap gap-1">
            {Object.entries(corpus.label_counts).map(([label, count]) => (
              <li key={label} className="chip">
                <Swatch color={colorOf(colors, label)} />
                {label} · {formatNumber(count)}
              </li>
            ))}
          </ul>
        </Section>
      )}

      {corpus.top_entities.length > 0 && (
        <Section title="Most connected">
          <ol className="flex flex-wrap gap-1">
            {corpus.top_entities.map((entity) => (
              <li key={entity.id}>
                <button type="button" className="chip hover:border-ink-2" onClick={() => onSelectEntity(entity.id)} title={`${formatNumber(entity.count)} mentions · show in the graph`}>
                  <Swatch color={colorOf(colors, entity.label)} />
                  {entity.text}
                </button>
              </li>
            ))}
          </ol>
        </Section>
      )}

    </div>
  );
}
