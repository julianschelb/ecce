import { BookDetails } from "@/components/BookDetails";
import { Contents } from "@/components/ReaderPanels";
import type { CorpusDetail, DocumentOut } from "@/lib/api";
import type { ColorMap } from "@/lib/colors";

export type SidebarTab = "details" | "contents";

interface Props {
  corpus: CorpusDetail;
  documents: DocumentOut[];
  colors: ColorMap;
  currentDocumentId: number | null;
  tab: SidebarTab;
  onTab: (tab: SidebarTab) => void;
  onGoTo: (page: number, entityId?: number | null) => void;
  onSelectEntity: (id: number) => void;
  onHide: () => void;
  /** Width in pixels (the explorer's drag handle changes it). */
  width: number;
}

/** Left rail of the explorer: the book's details (with source and licence) and its contents. */
export function ReaderSidebar({ corpus, documents, colors, currentDocumentId, tab, onTab, onGoTo, onSelectEntity, onHide, width }: Props) {
  const tabs: Array<[SidebarTab, string]> = [
    ["details", "Details"],
    ["contents", "Contents"],
  ];
  return (
    <aside className="panel-enter flex shrink-0 flex-col border-r border-line bg-surface" style={{ width }} aria-label="Details and contents">
      <div className="flex items-stretch border-b border-line-soft text-[13px]" role="tablist" aria-label="Left panel">
        {tabs.map(([key, label]) => (
          <button key={key} type="button" role="tab" aria-selected={tab === key} className={`flex-1 px-3 py-2 ${tab === key ? "border-b-2 border-accent-deep font-medium text-ink" : "text-muted hover:text-ink"}`} onClick={() => onTab(key)}>
            {label}
          </button>
        ))}
        <button type="button" className="px-2.5 text-muted hover:text-ink" onClick={onHide} title="Hide the details and contents (a tab on the left brings them back)" aria-label="Hide the details and contents">
          ‹
        </button>
      </div>
      {tab === "details" && <BookDetails corpus={corpus} colors={colors} onSelectEntity={onSelectEntity} />}
      {tab === "contents" && <Contents documents={documents} corpus={corpus} currentDocumentId={currentDocumentId} onGoTo={onGoTo} />}
    </aside>
  );
}
