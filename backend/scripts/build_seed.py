"""Build the precomputed seed corpus JSON from a plain-text file.

Usage::

    python scripts/build_seed.py data/seed/alice-in-wonderland.txt \
        --slug alice-in-wonderland --title "Alice's Adventures in Wonderland" \
        --genre Fiction --source "Project Gutenberg #11" --extractor spacy

The output JSON is imported automatically at startup (``SEED_ON_STARTUP``).
"""

from __future__ import annotations

import argparse
import json
import tempfile
from pathlib import Path

from app.core.config import Settings
from app.core.database import create_db_engine, init_db
from app.models.entities import Corpus, Document
from app.services.chunking import split_documents
from app.services.extraction import create_extractor, resolve_extractor_name
from app.services.processing import process_corpus
from app.services.seed import export_corpus
from sqlmodel import Session


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("text", type=Path)
    parser.add_argument("--slug", required=True)
    parser.add_argument("--title", required=True)
    parser.add_argument("--description", default="")
    parser.add_argument("--genre", default="")
    parser.add_argument("--source", default="")
    parser.add_argument("--language", default="en")
    parser.add_argument("--extractor", default="auto")
    parser.add_argument("--window", type=int, default=2)
    parser.add_argument("--split", default="auto", choices=["auto", "headings", "none"])
    parser.add_argument("--output", type=Path, default=None)
    args = parser.parse_args()

    settings = Settings(extractor=args.extractor, window=args.window, seed_on_startup=False)
    name = resolve_extractor_name(settings)
    extractor = create_extractor(settings, name)
    with tempfile.TemporaryDirectory() as tmp:
        engine = create_db_engine(f"sqlite:///{Path(tmp) / 'seed.db'}")
        init_db(engine)
        with Session(engine) as session:
            corpus = Corpus(
                slug=args.slug,
                title=args.title,
                description=args.description,
                genre=args.genre,
                source=args.source,
                language=args.language,
                window=args.window,
            )
            session.add(corpus)
            session.flush()
            parts = split_documents(
                args.text.read_text(encoding="utf-8"), args.split, default_title=args.title
            )
            session.add_all(
                Document(corpus_id=corpus.id, position=i, title=p.title, text=p.text)
                for i, p in enumerate(parts)
            )
            session.commit()
            process_corpus(
                session,
                corpus,
                extractor,
                settings,
                extractor_name=name,
                progress=lambda p, m: print(f"{p:5.0%} {m}"),
            )
            payload = export_corpus(session, corpus)
    output = args.output or args.text.with_suffix(".json")
    output.write_text(
        json.dumps(payload, ensure_ascii=False, separators=(",", ":")), encoding="utf-8"
    )
    print(f"wrote {output} ({output.stat().st_size / 1024:.0f} KB): {payload['corpus']}")
    print(
        f"documents={len(payload['documents'])} chunks={len(payload['chunks'])} entities={len(payload['entities'])} edges={len(payload['edges'])} mentions={len(payload['mentions'])}"
    )


if __name__ == "__main__":
    main()
