import { Link } from "react-router-dom";
import { clothFor } from "@/components/BookCard";
import type { CorpusSummary } from "@/lib/api";
import { LANGUAGE_NAMES, formatYear } from "@/lib/format";

export type ListSort = "title" | "author" | "oldest" | "newest";

interface Props {
  books: CorpusSummary[];
  sort: string;
  onSort: (sort: ListSort) => void;
}

/** "Project Gutenberg #2600" -> Project Gutenberg / #2600; Perseus sources -> name / edition. */
export function sourceLabel(source: string): { name: string; detail: string } {
  const gutenberg = /^Project Gutenberg #(\d+)/.exec(source);
  if (gutenberg) return { name: "Project Gutenberg", detail: `#${gutenberg[1]}` };
  if (source.startsWith("Perseus")) {
    const edition = /\((ed\. [^)]*)\)/.exec(source);
    return { name: "Perseus Digital Library", detail: edition ? edition[1] : "" };
  }
  return { name: source, detail: "" };
}

/** A small version of the gallery's book cover: the same cloth colour, rules and language. */
export function MiniCover({ corpus }: { corpus: CorpusSummary }) {
  const [cloth, clothDark] = clothFor(corpus.slug);
  return (
    <span className="mini-cover" style={{ ["--cloth" as string]: cloth, ["--cloth-dark" as string]: clothDark }} aria-hidden="true">
      <span className="mini-cover__rule" />
      <span className="mini-cover__initial">{corpus.title.charAt(0)}</span>
      <span className="mini-cover__rule" />
      <span className="mini-cover__lang">{corpus.language.toUpperCase()}</span>
    </span>
  );
}

function SortHeader({ label, active, onClick, className = "" }: { label: string; active: boolean; onClick: () => void; className?: string }) {
  return (
    <th scope="col" className={`book-list__th ${className}`} aria-sort={active ? "ascending" : "none"}>
      <button type="button" className={`book-list__sort ${active ? "is-active" : ""}`} onClick={onClick}>
        {label}
        {active && <span aria-hidden="true"> ↓</span>}
      </button>
    </th>
  );
}

/** The gallery as a list: one book per row with its cover, metadata, source and licence. */
export function BookList({ books, sort, onSort }: Props) {
  return (
    <table className="book-list">
      <thead>
        <tr>
          <th scope="col" className="book-list__th w-[52px]">
            <span className="sr-only">Cover</span>
          </th>
          <SortHeader label="Title" active={sort === "title"} onClick={() => onSort("title")} />
          <SortHeader label="Author" active={sort === "author"} onClick={() => onSort("author")} className="hidden sm:table-cell" />
          <SortHeader label="Year" active={sort === "oldest" || sort === "newest"} onClick={() => onSort(sort === "oldest" ? "newest" : "oldest")} className="hidden md:table-cell" />
          <th scope="col" className="book-list__th hidden lg:table-cell">
            Language
          </th>
          <th scope="col" className="book-list__th hidden lg:table-cell">
            Source
          </th>
          <th scope="col" className="book-list__th hidden md:table-cell">
            Licence
          </th>
        </tr>
      </thead>
      <tbody>
        {books.map((corpus) => {
          const source = sourceLabel(corpus.source);
          return (
            <tr key={corpus.slug} className="book-list__row">
              <td className="book-list__td">
                <Link to={`/corpus/${corpus.slug}`} tabIndex={-1} aria-hidden="true">
                  <MiniCover corpus={corpus} />
                </Link>
              </td>
              <td className="book-list__td">
                <Link to={`/corpus/${corpus.slug}`} className="book-list__title">
                  {corpus.title}
                </Link>
                <div className="book-list__sub">
                  <span className="sm:hidden">{corpus.author || "Anonymous"} · </span>
                  {corpus.genre}
                </div>
              </td>
              <td className="book-list__td hidden sm:table-cell">{corpus.author || "Anonymous"}</td>
              <td className="book-list__td book-list__mono hidden whitespace-nowrap md:table-cell">{formatYear(corpus.year)}</td>
              <td className="book-list__td hidden lg:table-cell">{LANGUAGE_NAMES[corpus.language] ?? corpus.language}</td>
              <td className="book-list__td hidden lg:table-cell">
                {corpus.source_url ? (
                  <a className="book-list__link" href={corpus.source_url} target="_blank" rel="noreferrer">
                    {source.name}
                  </a>
                ) : (
                  source.name || "—"
                )}
                {source.detail && <div className="book-list__sub">{source.detail}</div>}
              </td>
              <td className="book-list__td hidden whitespace-nowrap md:table-cell">
                {corpus.license_url ? (
                  <a className="book-list__link" href={corpus.license_url} target="_blank" rel="noreferrer">
                    {corpus.license}
                  </a>
                ) : (
                  corpus.license || "—"
                )}
              </td>
            </tr>
          );
        })}
      </tbody>
    </table>
  );
}
