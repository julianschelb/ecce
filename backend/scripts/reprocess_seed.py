"""Re-run the processing pipeline on bundled seeds without re-downloading their texts.

Reads the documents of existing seed files, processes them again with the current pipeline
(entity extraction, alias merging, network) and writes the result.
By default the seed is replaced and its revision bumped, so running instances re-import it;
with ``--suffix`` a variant is written next to it instead (e.g. to compare extractors).

    python scripts/reprocess_seed.py anna-karenina an-ideal-husband
    python scripts/reprocess_seed.py a-christmas-carol --no-merge --suffix unmerged
"""

from __future__ import annotations

import argparse
import tempfile
import time
from pathlib import Path

from app.core.config import Settings
from app.core.database import create_db_engine, init_db
from app.models.entities import Corpus, Document
from app.services.extraction import create_extractor, resolve_extractor_name
from app.services.processing import process_corpus
from app.services.seed import export_corpus, read_seed, write_seed
from sqlmodel import Session

ROOT = Path(__file__).resolve().parents[1]
SEEDS = ROOT / "data" / "seed"
LATIN = {
    "spacy_model": "la_core_web_md",
    "spacy_labels": ["PERSON", "LOC", "NORP", "GRP", "PERSON_MYTH"],
}
META_FIELDS = (
    "title", "author", "year", "description", "genre", "source", "source_url", "license",
    "license_url", "rights", "language",
)  # fmt: skip


def seed_path(slug: str) -> Path:
    for path in (SEEDS / f"{slug}.json.gz", SEEDS / f"{slug}.json"):
        if path.exists():
            return path
    raise FileNotFoundError(slug)


def reprocess(slug: str, args: argparse.Namespace) -> Path:
    source = seed_path(slug)
    payload = read_seed(source)
    meta = payload["corpus"]
    overrides: dict = (
        dict(LATIN) if meta.get("language") == "la" and args.extractor == "spacy" else {}
    )
    settings = Settings(
        extractor=args.extractor,
        window=meta.get("window") or 2,
        seed_on_startup=False,
        merge_aliases=not args.no_merge,
        **overrides,
    )
    extractor = create_extractor(settings, resolve_extractor_name(settings))
    new_slug = f"{slug}--{args.suffix}" if args.suffix else slug
    output = SEEDS / f"{new_slug}.json.gz"
    previous = read_seed(output)["corpus"] if output.exists() else None
    revision = int(previous.get("revision") or 0) + 1 if previous else 0
    with tempfile.TemporaryDirectory() as tmp:
        engine = create_db_engine(f"sqlite:///{Path(tmp) / 'seed.db'}")
        init_db(engine)
        with Session(engine) as session:
            corpus = Corpus(
                slug=new_slug,
                window=settings.window,
                seed_revision=revision,
                **{k: meta[k] for k in META_FIELDS if meta.get(k) is not None},
            )
            if args.suffix:
                corpus.title = f"{corpus.title} ({args.label or args.suffix})"
            session.add(corpus)
            session.flush()
            session.add_all(
                Document(corpus_id=corpus.id, position=i, title=d["title"], text=d["text"])
                for i, d in enumerate(payload["documents"])
            )
            session.commit()
            started = time.perf_counter()
            process_corpus(
                session,
                corpus,
                extractor,
                settings,
                extractor_name=args.extractor,
                progress=lambda p, m: print(f"  {p:4.0%} {m}", flush=True),
            )
            result = export_corpus(session, corpus)
    write_seed(output, result)
    before, after = len(payload["entities"]), len(result["entities"])
    print(
        f"{new_slug}: {before} -> {after} entities, {len(payload['edges'])} -> "
        f"{len(result['edges'])} edges, {time.perf_counter() - started:.0f}s, revision {revision}"
    )
    return output


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("slugs", nargs="+")
    parser.add_argument("--extractor", default="spacy", choices=["spacy", "gliner", "rule"])
    parser.add_argument("--suffix", default="", help="write a variant <slug>--<suffix>")
    parser.add_argument("--label", default="", help="title suffix of the variant")
    parser.add_argument("--no-merge", action="store_true", help="skip alias merging")
    args = parser.parse_args()
    for slug in args.slugs:
        reprocess(slug, args)


if __name__ == "__main__":
    main()
