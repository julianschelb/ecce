"""Print the "Bundled corpora" table for the README from the catalogue and the seeds present."""

from __future__ import annotations

import json
from pathlib import Path

from app.services.seed import read_seed

ROOT = Path(__file__).resolve().parents[1]
CATALOGUE = ROOT / "data" / "catalogue" / "gutenberg.json"
SEEDS = ROOT / "data" / "seed"


def main() -> None:
    catalogue = json.loads(CATALOGUE.read_text(encoding="utf-8"))
    rows = []
    for entry in sorted(catalogue, key=lambda e: (e["author"].split()[-1], e["year"])):
        if (
            not (SEEDS / f"{entry['slug']}.json.gz").exists()
            and not (SEEDS / f"{entry['slug']}.json").exists()
        ):
            continue
        died = ", ".join(f"†{p['died']}" for p in entry.get("people", []) if p.get("died"))
        year = entry["year"]
        shown = f"c. {abs(year)} BCE" if year < 0 else str(year)
        rows.append(
            f"| {entry['title']} | {entry['author']} ({died}) | {shown} | Project Gutenberg #{entry['id']} |"
        )
    perseus = json.loads((ROOT / "data" / "catalogue" / "perseus.json").read_text(encoding="utf-8"))
    for entry in sorted(perseus, key=lambda e: (e["author"], e.get("year") or 0, e["title"])):
        seed = SEEDS / f"{entry['slug']}.json.gz" if entry.get("slug") else None
        if seed is None or not seed.exists():
            continue
        meta = read_seed(seed)["corpus"]  # title, author and year as shown in the gallery
        year = meta.get("year")
        shown = "" if year is None else (f"c. {abs(year)} BCE" if year < 0 else f"c. {year} CE")
        editors = " & ".join(e.split()[-1] for e in entry["editors"])
        rows.append(
            f"| {meta['title']} (Latin) | {meta['author']} | {shown} | "
            f"Perseus, ed. {editors} {entry['edition_year']} (CC BY-SA 4.0) |"
        )
    print("| Title | Author (died) | Year | Source |")
    print("|---|---|---|---|")
    print("\n".join(rows))
    seeds = len(list(SEEDS.glob("*.json.gz"))) + len(list(SEEDS.glob("*.json")))
    print(f"\n{seeds} corpora")


if __name__ == "__main__":
    main()
