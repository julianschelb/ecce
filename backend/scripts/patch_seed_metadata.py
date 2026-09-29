"""Update corpus metadata (title, author, year, description, genre, source) of seed files from the catalogue.

python scripts/patch_seed_metadata.py [--only slug ...]
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from app.services.seed import read_seed, write_seed

ROOT = Path(__file__).resolve().parents[1]
CATALOGUE = ROOT / "data" / "catalogue" / "gutenberg.json"
SEEDS = ROOT / "data" / "seed"
EXTRA = {
    "vergil-opera": {
        "author": "P. Vergilius Maro",
        "year": -19,
        # CC BY-SA 4.0 requires naming the licence wherever the text is shown
        "source": "Perseus Digital Library, canonical-latinLit (ed. J. B. Greenough, 1881) · CC BY-SA 4.0",
    },
    "alice-in-wonderland": {"author": "Lewis Carroll", "year": 1865},
}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--only", nargs="*", default=None)
    args = parser.parse_args()
    metadata = {e["slug"]: e for e in json.loads(CATALOGUE.read_text(encoding="utf-8"))}
    for slug, extra in EXTRA.items():
        metadata.setdefault(slug, {}).update(extra)
    for path in sorted(list(SEEDS.glob("*.json")) + list(SEEDS.glob("*.json.gz"))):
        payload = read_seed(path)
        slug = payload["corpus"]["slug"]
        if args.only and slug not in args.only:
            continue
        entry = dict(metadata.get(slug) or {})
        if "id" in entry:
            entry.setdefault("source", f"Project Gutenberg #{entry['id']}")
        if not entry:
            continue
        changed = False
        for key in ("title", "author", "year", "description", "genre", "source"):
            if key in entry and payload["corpus"].get(key) != entry[key]:
                payload["corpus"][key] = entry[key]
                changed = True
        if changed:
            write_seed(path, payload)
            print(f"patched {path.name}: {entry.get('author', '')} {entry.get('year', '')}")


if __name__ == "__main__":
    main()
