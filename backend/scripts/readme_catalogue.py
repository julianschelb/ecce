"""Print the "Bundled corpora" table for the README from the catalogue and the seeds present."""

from __future__ import annotations

import json
from pathlib import Path

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
    print("| Title | Author (died) | Year | Source |")
    print("|---|---|---|---|")
    print("\n".join(rows))
    print(
        "| Vergil: Eclogues, Georgics, Aeneid (Latin) | P. Vergilius Maro | c. 19 BCE | Perseus canonical-latinLit (CC BY-SA 4.0) |"
    )
    print(f"\n{len(rows) + 1} corpora")


if __name__ == "__main__":
    main()
