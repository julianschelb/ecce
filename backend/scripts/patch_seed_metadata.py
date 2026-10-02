"""Update the corpus metadata of seed files from the catalogue.

Covers the descriptive fields (title, author, year, description, genre) and the provenance shown
in the reader's Details tab: source, source URL, licence and a rights statement naming everyone
involved with their life dates (run ``verify_catalogue.py`` first so the catalogue has them).

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
FIELDS = (
    "title",
    "author",
    "year",
    "description",
    "genre",
    "source",
    "source_url",
    "license",
    "license_url",
    "rights",
)
PUBLIC_DOMAIN = {
    "license": "Public domain",
    "license_url": "https://creativecommons.org/publicdomain/mark/1.0/",
}
PERSEUS = "https://github.com/PerseusDL/canonical-latinLit/blob/master/data/"
CC_BY_SA = {
    "license": "CC BY-SA 4.0",
    "license_url": "https://creativecommons.org/licenses/by-sa/4.0/",
}
# MARC relator codes used in Project Gutenberg's catalogue
ROLES = {
    "aut": "Author",
    "trl": "Translator",
    "edt": "Editor",
    "ill": "Illustrator",
    "aui": "Author of introduction",
    "aft": "Author of afterword",
    "ann": "Annotator",
    "cmm": "Commentator",
    "com": "Compiler",
    "ctb": "Contributor",
    "oth": "Contributor",
}
EXTRA = {
    "vergil-opera": {
        "author": "P. Vergilius Maro",
        "year": -19,
        # CC BY-SA 4.0 requires naming the licence wherever the text is shown
        "source": "Perseus Digital Library, canonical-latinLit (ed. J. B. Greenough, 1881) · CC BY-SA 4.0",
        "source_url": "https://github.com/PerseusDL/canonical-latinLit/tree/master/data/phi0690",
        **CC_BY_SA,
        "rights": "\n".join(
            [
                "Latin text: P. Vergilius Maro (70–19 BCE), Bucolics, Georgics and Aeneid, edited by "
                "J. B. Greenough (Boston: Ginn & Co., 1881). The text and the edition are in the "
                "public domain.",
                "Digital edition: Perseus Digital Library, Tufts University (canonical-latinLit, "
                "files phi0690.phi001–003.perseus-lat2.xml), licensed under CC BY-SA 4.0.",
                "Changes: converted to plain text, split into books and passages, and annotated "
                "with named entities (LatinCy la_core_web_md, inflected forms merged by lemma). "
                "This adapted corpus, including its annotations and network, is shared under the "
                "same licence (CC BY-SA 4.0).",
            ]
        ),
    },
    "cicero-in-catilinam": {
        "source": "Perseus Digital Library, canonical-latinLit (ed. A. C. Clark, 1908) · CC BY-SA 4.0",
        "source_url": PERSEUS + "phi0474/phi013/phi0474.phi013.perseus-lat2.xml",
        **CC_BY_SA,
        "rights": "\n".join(
            [
                "Latin text: M. Tullius Cicero (106–43 BCE), In Catilinam I–IV (63 BCE), edited by "
                "A. C. Clark (1859–1937), M. Tulli Ciceronis Orationes, vol. 1 (Oxford: Clarendon "
                "Press, 1908). The text and the edition are in the public domain.",
                "Digital edition: Perseus Digital Library, Tufts University (canonical-latinLit, "
                "file phi0474.phi013.perseus-lat2.xml), licensed under CC BY-SA 4.0.",
                "Changes: converted to plain text without the critical apparatus, one document per "
                "speech with the section numbers in square brackets, and annotated with named "
                "entities (LatinCy la_core_web_md, inflected forms merged by lemma). This adapted "
                "corpus, including its annotations and network, is shared under the same licence "
                "(CC BY-SA 4.0).",
            ]
        ),
    },
    "sallust-catilina": {
        "source": "Perseus Digital Library, canonical-latinLit (ed. A. W. Ahlberg, 1919) · CC BY-SA 4.0",
        "source_url": PERSEUS + "phi0631/phi001/phi0631.phi001.perseus-lat3.xml",
        **CC_BY_SA,
        "rights": "\n".join(
            [
                "Latin text: C. Sallustius Crispus (86–c. 35 BCE), De Catilinae coniuratione "
                "(c. 41 BCE), edited by A. W. Ahlberg, C. Sallusti Crispi Catilina, Iugurtha, "
                "orationes et epistulae excerptae de historiis (Leipzig: Teubner, 1919). The text "
                "and the edition are in the public domain.",
                "Digital edition: Perseus Digital Library, Tufts University (canonical-latinLit, "
                "file phi0631.phi001.perseus-lat3.xml), licensed under CC BY-SA 4.0.",
                "Changes: converted to plain text without the words the editor deletes, one "
                "document per chapter (chapter 54, nested in chapter 53 in the source file, is "
                "its own chapter here), and annotated with named entities (LatinCy "
                "la_core_web_md, inflected forms merged by lemma). This adapted corpus, including "
                "its annotations and network, is shared under the same licence (CC BY-SA 4.0).",
            ]
        ),
    },
    "alice-in-wonderland": {
        "author": "Lewis Carroll",
        "year": 1865,
        "source": "Project Gutenberg #11",
        "source_url": "https://www.gutenberg.org/ebooks/11",
        **PUBLIC_DOMAIN,
        "rights": "\n".join(
            [
                "Author: Lewis Carroll (1832–1898).",
                "First published 1865.",
                "Public domain in the EU (the author died more than 70 years ago) and in the US "
                "(published before 1931).",
            ]
        ),
    },
}


def life(person: dict) -> str:
    born, died = person.get("born"), person.get("died")

    def year(value: int | None) -> str:
        return "?" if value is None else (f"{-value} BCE" if value < 0 else str(value))

    return f"{year(born)}–{year(died)}"


def display_name(name: str) -> str:
    """ "Austen, Jane" -> "Jane Austen" (Gutenberg lists people as "Surname, Given names")."""
    parts = [p.strip() for p in name.split(",")]
    if len(parts) >= 2 and parts[1] and not parts[1][0].isdigit():
        return f"{parts[1]} {parts[0]}"
    return name


def gutenberg_rights(entry: dict) -> dict:
    """Source, licence and rights statement of a verified Project Gutenberg catalogue entry."""
    lines = [
        f"{ROLES.get(p.get('role', 'aut'), 'Contributor')}: {display_name(p['name'])} ({life(p)})."
        for p in entry.get("people", [])
    ]
    year = entry["year"]
    lines.append(f"First published {f'c. {-year} BCE' if year < 0 else year}.")
    lines.append(
        "Public domain in the EU (everyone involved died in 1955 or earlier, more than 70 years "
        "ago) and in the US (published before 1931). The Project Gutenberg licence and the notes "
        "its volunteers added are not part of this text."
    )
    return {
        "source": f"Project Gutenberg #{entry['id']}",
        "source_url": f"https://www.gutenberg.org/ebooks/{entry['id']}",
        **PUBLIC_DOMAIN,
        "rights": "\n".join(lines),
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--only", nargs="*", default=None)
    args = parser.parse_args()
    metadata = {
        e["slug"]: {**e, **gutenberg_rights(e)}
        for e in json.loads(CATALOGUE.read_text(encoding="utf-8"))
    }
    for slug, extra in EXTRA.items():
        metadata.setdefault(slug, {}).update(extra)
    for path in sorted(list(SEEDS.glob("*.json")) + list(SEEDS.glob("*.json.gz"))):
        payload = read_seed(path)
        slug = payload["corpus"]["slug"]
        if args.only and slug not in args.only:
            continue
        entry = metadata.get(slug)
        if not entry:
            continue
        changed = False
        for key in FIELDS:
            if key in entry and payload["corpus"].get(key) != entry[key]:
                payload["corpus"][key] = entry[key]
                changed = True
        if changed:
            write_seed(path, payload)
            print(f"patched {path.name}: {entry.get('author', '')} · {entry.get('license', '')}")


if __name__ == "__main__":
    main()
