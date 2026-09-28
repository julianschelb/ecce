"""Build a Latin seed corpus from Perseus Digital Library TEI files (public domain).

Default: Vergil's complete works (Eclogues, Georgics, Aeneid), one document per book,
processed with a LatinCy spaCy pipeline (``--spacy-model la_core_web_md``).

    python scripts/build_perseus_seed.py --spacy-model la_core_web_md
"""

from __future__ import annotations

import argparse
import re
import subprocess
import sys
import urllib.request
import xml.etree.ElementTree as ET
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CACHE = ROOT / "data" / "cache" / "perseus"
SEEDS = ROOT / "data" / "seed"
BASE = "https://raw.githubusercontent.com/PerseusDL/canonical-latinLit/master/data/"
WORKS = [
    ("phi0690/phi001/phi0690.phi001.perseus-lat2.xml", "Eclogues", "Ecloga"),
    ("phi0690/phi002/phi0690.phi002.perseus-lat2.xml", "Georgics", "Georgicon"),
    ("phi0690/phi003/phi0690.phi003.perseus-lat2.xml", "Aeneid", "Aeneis"),
]
NS = {"tei": "http://www.tei-c.org/ns/1.0"}


def fetch(path: str) -> str:
    CACHE.mkdir(parents=True, exist_ok=True)
    target = CACHE / Path(path).name
    if not target.exists():
        with urllib.request.urlopen(BASE + path, timeout=60) as response:
            target.write_bytes(response.read())
    return target.read_text(encoding="utf-8")


def books(xml: str) -> list[tuple[str, str]]:
    """Return (book number, text) pairs; lines are joined so sentences span verses."""
    root = ET.fromstring(xml)
    out = []
    for div in root.iterfind(".//tei:div[@subtype='book']", NS) or []:
        number = div.get("n", "?")
        lines = []
        for element in div.iter():
            tag = element.tag.split("}")[-1]
            if tag == "l":
                verse = "".join(element.itertext()).strip()
                if verse:
                    lines.append(re.sub(r"\s+", " ", verse))
        if lines:
            out.append((number, "\n".join(lines)))
    if not out:  # some files use <div type="textpart" subtype="poem">
        for div in root.iterfind(".//tei:div[@subtype='poem']", NS):
            number = div.get("n", "?")
            lines = [
                re.sub(r"\s+", " ", "".join(line.itertext()).strip())
                for line in div.iterfind(".//tei:l", NS)
            ]
            lines = [line for line in lines if line]
            if lines:
                out.append((number, "\n".join(lines)))
    return out


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--spacy-model", default="la_core_web_md")
    parser.add_argument("--labels", default="PERSON,LOC,NORP,GRP,PERSON_MYTH")
    parser.add_argument("--window", type=int, default=2)
    parser.add_argument("--slug", default="vergil-opera")
    args = parser.parse_args()

    parts: list[str] = []
    for path, work, latin in WORKS:
        sections = books(fetch(path))
        print(f"{work}: {len(sections)} books")
        for number, text in sections:
            heading = (
                f"BOOK {number}.\n{latin} {number}"
                if work == "Aeneid"
                else f"PART {number}.\n{latin} {number}"
            )
            parts.append(f"{heading}\n\n" + text.replace("\n", " ") + "\n")
    text_path = CACHE / "vergil.txt"
    text_path.write_text("\n\n".join(parts), encoding="utf-8")
    print(f"{len(text_path.read_text(encoding='utf-8').split()):,} words")
    SEEDS.mkdir(parents=True, exist_ok=True)
    output = SEEDS / f"{args.slug}.json.gz"
    subprocess.run(
        [
            sys.executable,
            str(ROOT / "scripts" / "build_seed.py"),
            str(text_path),
            "--slug",
            args.slug,
            "--title",
            "Vergil: Eclogues, Georgics, Aeneid",
            "--author",
            "P. Vergilius Maro",
            "--year",
            "-19",
            "--language",
            "la",
            "--genre",
            "Latin poetry · Epic",
            "--source",
            "Perseus Digital Library (canonical-latinLit), Loci Similes source corpus",
            "--description",
            "Vergil's complete works in Latin, one document per book. The Aeneid is the source side of the Loci Similes intertextuality benchmark. Entities extracted with LatinCy (la_core_web_md).",
            "--extractor",
            "spacy",
            "--spacy-model",
            args.spacy_model,
            "--spacy-labels",
            args.labels,
            "--window",
            str(args.window),
            "--gzip",
            "--output",
            str(output),
        ],
        check=True,
        cwd=ROOT,
    )
    print("wrote", output, f"{output.stat().st_size / 1024:.0f} KB")


if __name__ == "__main__":
    main()
