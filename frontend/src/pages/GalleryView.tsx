import { Link } from "react-router-dom";
import { CorpusCard } from "@/components/CorpusCard";
import { Empty, ErrorNote, Spinner } from "@/components/ui";
import { useCorpora } from "@/hooks/useApi";
import { useAuth } from "@/hooks/useAuth";

export function GalleryView() {
  const { data, isLoading, error } = useCorpora(false);
  const { isAdmin } = useAuth();
  return (
    <div className="mx-auto max-w-[1200px] px-4 py-8">
      <header className="mb-8 max-w-3xl">
        <h1 className="text-[34px] leading-tight">Corpus gallery</h1>
        <p className="mt-3 text-[16px] text-ink-2">
          Each corpus below has been turned into an <em>implicit entity network</em>: entities that are mentioned close to each
          other are linked, and the strength of a link decays with the distance of their mentions. Open a corpus to explore the
          network, read the passages behind every relation and search the text.
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
        <div className="grid grid-cols-1 gap-4 md:grid-cols-2 xl:grid-cols-3">
          {data.map((corpus) => (
            <CorpusCard key={corpus.slug} corpus={corpus} />
          ))}
        </div>
      )}
    </div>
  );
}
