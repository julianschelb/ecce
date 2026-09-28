import { Link, useLocation } from "react-router-dom";
import { BookCard } from "@/components/BookCard";
import { Empty, ErrorNote, Spinner } from "@/components/ui";
import { useCorpora } from "@/hooks/useApi";
import { useAuth } from "@/hooks/useAuth";

export function GalleryView() {
  const { data, isLoading, error } = useCorpora(false);
  const { isAdmin } = useAuth();
  const peek = useLocation().hash === "#peek"; // demo/screenshot mode: all books open
  return (
    <div className="mx-auto max-w-[1200px] px-4 py-8">
      <header className="mb-8 max-w-3xl">
        <h1 className="text-[34px] leading-tight">Corpus gallery</h1>
        <p className="mt-3 text-[16px] text-ink-2">
          Each corpus below has been turned into an <em>implicit entity network</em>: entities that are mentioned close to each
          other are linked, and the strength of a link decays with the distance of their mentions. Open a corpus to explore the
          network, read the passages behind every relation and search the text. Hover a book to peek inside.
        </p>
      </header>
      {isLoading && <Spinner label="Loading corpora" />}
      {error && <ErrorNote error={error} />}
      {data && data.length === 0 && (
        <Empty>
          No corpora have been published yet.{" "}
          {isAdmin ? (
            <Link to="/admin" className="text-accent-deep underline">
              Create one in the admin panel.
            </Link>
          ) : (
            "An administrator can add corpora."
          )}
        </Empty>
      )}
      {data && data.length > 0 && (
        <div className="grid grid-cols-[repeat(auto-fill,minmax(230px,1fr))] justify-items-center gap-x-8 gap-y-12 py-4">
          {data.map((corpus) => (
            <BookCard key={corpus.slug} corpus={corpus} open={peek} />
          ))}
        </div>
      )}
    </div>
  );
}
