"""Check the rights status of every catalogue entry against Project Gutenberg metadata.

Reads the RDF record Project Gutenberg publishes for every ebook
(``https://www.gutenberg.org/ebooks/<id>.rdf``). An entry passes when the record says
"Public domain in the USA", the language is English, the title matches, and every
author, translator *and other contributor* the record names (editor, illustrator, author of an
introduction or notes, ...) died in ``--died-before`` or earlier (70 years of protection
after death have expired in the EU). Names and death years are written back into the
catalogue (``people``) so the check is auditable offline.

Usage::

    python scripts/verify_catalogue.py            # verify and annotate
    python scripts/verify_catalogue.py --strict   # exit 1 if any entry fails
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import time
import unicodedata
import urllib.request
import xml.etree.ElementTree as ET
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CATALOGUE = ROOT / "data" / "catalogue" / "gutenberg.json"
RDF_URLS = (
    "https://www.gutenberg.org/ebooks/{id}.rdf",
    "https://gutenberg.pglaf.org/cache/epub/{id}/pg{id}.rdf",  # official mirror
)
NS = {
    "dcterms": "http://purl.org/dc/terms/",
    "pgterms": "http://www.gutenberg.org/2009/pgterms/",
    "marcrel": "http://id.loc.gov/vocabulary/relators/",
    "rdf": "http://www.w3.org/1999/02/22-rdf-syntax-ns#",
}


def fold(text: str) -> str:
    text = unicodedata.normalize("NFKD", text)
    text = "".join(c for c in text if not unicodedata.combining(c))
    return re.sub(r"\s+", " ", re.sub(r"[^a-z0-9 ]+", " ", text.lower())).strip()


def _agents(ebook: ET.Element, tag: str) -> list[dict]:
    people = []
    for agent in ebook.findall(f"{tag}/pgterms:agent", NS):
        name = agent.findtext("pgterms:name", default="", namespaces=NS)
        born = agent.findtext("pgterms:birthdate", default=None, namespaces=NS)
        died = agent.findtext("pgterms:deathdate", default=None, namespaces=NS)
        people.append(
            {
                "name": name,
                "birth_year": int(born) if born and born.lstrip("-").isdigit() else None,
                "death_year": int(died) if died and died.lstrip("-").isdigit() else None,
            }
        )
    return people


def fetch(gutenberg_id: int) -> dict:
    """The Gutenberg RDF record reduced to the fields the check needs."""
    root = None
    for url in RDF_URLS:
        request = urllib.request.Request(
            url.format(id=gutenberg_id), headers={"User-Agent": "ecce-catalogue-check"}
        )
        try:
            with urllib.request.urlopen(request, timeout=60) as response:
                root = ET.fromstring(response.read())
            break
        except Exception as error:  # noqa: BLE001
            last_error = error
    if root is None:
        raise RuntimeError(f"all RDF sources failed: {last_error}")
    ebook = root.find("pgterms:ebook", NS)
    if ebook is None:
        raise ValueError("no ebook element in RDF")
    languages = [
        (value.text or "").strip()
        for value in ebook.findall("dcterms:language/rdf:Description/rdf:value", NS)
    ]
    rights = ebook.findtext("dcterms:rights", default="", namespaces=NS)
    return {
        "title": ebook.findtext("dcterms:title", default="", namespaces=NS),
        "authors": _agents(ebook, "dcterms:creator"),
        "translators": _agents(ebook, "marcrel:trl"),
        # every other MARC relator (edt editor, ill illustrator, aui author of introduction,
        # ann annotator, com compiler, ...): their contributions can be protected on their own
        "contributors": [
            {**person, "role": role}
            for role in sorted(
                {
                    child.tag.rsplit("}", 1)[-1]
                    for child in ebook
                    if child.tag.startswith("{" + NS["marcrel"] + "}")
                }
                - {"trl"}
            )
            for person in _agents(ebook, f"marcrel:{role}")
        ],
        "languages": languages,
        "copyright": not rights.lower().startswith("public domain"),
        "rights": rights,
    }


def check(entry: dict, record: dict, died_before: int) -> list[str]:
    problems: list[str] = []
    if record.get("copyright") is not False:
        problems.append(f"rights statement: {record.get('rights')!r}")
    if record.get("languages") != ["en"]:
        problems.append(f"languages {record.get('languages')}")
    want, got = fold(entry["title"]), fold(record.get("title", ""))
    if want not in got and got not in want:
        problems.append(f"title mismatch: {record.get('title')!r}")
    people = [
        *record.get("authors", []),
        *record.get("translators", []),
        *record.get("contributors", []),
    ]
    if not people:
        problems.append("no author metadata")
    surname = fold(entry["author"].split("(")[0]).split()[-1][:5]
    anonymous = (
        surname.startswith("anony") and not record.get("authors") and record.get("translators")
    )
    if not anonymous and not any(surname in fold(p["name"]) for p in record.get("authors", [])):
        problems.append(f"author mismatch: {[p['name'] for p in record.get('authors', [])]}")
    for person in people:
        died = person.get("death_year")
        if died is None:
            problems.append(f"{person['name']}: death year unknown")
        elif died > died_before:
            problems.append(f"{person['name']} died {died} (> {died_before})")
    return problems


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--died-before", type=int, default=1955, help="latest acceptable death year"
    )
    parser.add_argument("--only", nargs="*", default=None)
    parser.add_argument("--strict", action="store_true")
    args = parser.parse_args()
    catalogue = json.loads(CATALOGUE.read_text(encoding="utf-8"))
    failed: list[str] = []
    checked = 0
    for entry in catalogue:
        if args.only and entry["slug"] not in args.only:
            continue
        checked += 1
        try:
            record = fetch(entry["id"])
        except Exception as error:  # noqa: BLE001
            print(f"?? {entry['slug']}: lookup failed ({error})")
            failed.append(entry["slug"])
            continue
        problems = check(entry, record, args.died_before)
        people = [
            {"name": p["name"], "born": p.get("birth_year"), "died": p.get("death_year")}
            | ({"role": p["role"]} if p.get("role") else {})
            for p in [
                *record.get("authors", []),
                *record.get("translators", []),
                *record.get("contributors", []),
            ]
        ]
        entry["people"] = people
        entry["verified"] = not problems
        entry["gutenberg_title"] = record.get("title")
        entry["rights"] = record.get("rights")
        mark = "ok" if not problems else "!!"
        deaths = ", ".join(f"{p['name'].split(',')[0]} †{p['died']}" for p in people)
        print(f"{mark} {entry['slug']:45s} #{entry['id']:<6} {deaths}")
        for problem in problems:
            print(f"     - {problem}")
        if problems:
            failed.append(entry["slug"])
        time.sleep(0.3)
    CATALOGUE.write_text(
        json.dumps(catalogue, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(f"\n{checked - len(failed)} verified, {len(failed)} flagged: {', '.join(failed) or '-'}")
    if args.strict and failed:
        sys.exit(1)


if __name__ == "__main__":
    main()
