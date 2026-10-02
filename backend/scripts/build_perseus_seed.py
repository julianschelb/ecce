"""Build Latin seed corpora from Perseus Digital Library TEI files (canonical-latinLit).

Perseus' digital editions are licensed CC BY-SA 4.0; the editions they encode are in the public
domain (see ``patch_seed_metadata.py`` for the attribution written into each corpus and
``data/seed/NOTICE.md``). Entities are extracted with a LatinCy spaCy pipeline.

    python scripts/build_perseus_seed.py                          # Vergil (default)
    python scripts/build_perseus_seed.py --corpus cicero-in-catilinam
    python scripts/build_perseus_seed.py --corpus sallust-catilina
"""

from __future__ import annotations

import argparse
import re
import subprocess
import sys
import urllib.request
import xml.etree.ElementTree as ET
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

from app.services.seed import read_seed

ROOT = Path(__file__).resolve().parents[1]
CACHE = ROOT / "data" / "cache" / "perseus"
SEEDS = ROOT / "data" / "seed"
BASE = "https://raw.githubusercontent.com/PerseusDL/canonical-latinLit/master/data/"
NS = {"tei": "http://www.tei-c.org/ns/1.0"}
TEI = "{http://www.tei-c.org/ns/1.0}"

# editorial matter that is not part of the reading text: critical notes, variant readings,
# words the editor deletes as spurious, and section headings (used as document titles)
SKIPPED = {"note", "rdg", "del", "head", "bibl"}
# in <choice>, prefer the expanded / regularised / corrected form
PREFERRED = ("expan", "reg", "corr")
ROMAN = ["I", "II", "III", "IV", "V", "VI", "VII", "VIII", "IX", "X"]


def fetch(path: str) -> str:
    CACHE.mkdir(parents=True, exist_ok=True)
    target = CACHE / Path(path).name
    if not target.exists():
        with urllib.request.urlopen(BASE + path, timeout=60) as response:
            target.write_bytes(response.read())
    return target.read_text(encoding="utf-8")


CHAPTER_MARK = "\x00"


def reading_text(element: ET.Element, mark_chapters: bool = False) -> str:
    """The text of a TEI element without apparatus, notes or deletions.

    With ``mark_chapters``, a ``<milestone unit="chapter" n="…"/>`` inside the element becomes
    ``\x00n\x00`` so callers can split there (Perseus sometimes nests a chapter that way).
    """
    parts: list[str] = []

    def walk(node: ET.Element) -> None:
        tag = node.tag.split("}")[-1]
        if tag in SKIPPED:
            return
        if mark_chapters and tag == "milestone" and node.get("unit") == "chapter":
            parts.append(f" {CHAPTER_MARK}{node.get('n')}{CHAPTER_MARK} ")
            return
        if tag == "choice":
            children = list(node)
            pick = next(
                (c for name in PREFERRED for c in children if c.tag == TEI + name),
                children[0] if children else None,
            )
            if pick is not None:
                walk(pick)
            return
        if tag == "app":  # keep the editor's reading (lemma), not the variants
            lemma = node.find("tei:lem", NS)
            if lemma is not None:
                walk(lemma)
            return
        if node.text:
            parts.append(node.text)
        for child in node:
            walk(child)
            if child.tail:
                parts.append(child.tail)

    walk(element)
    return re.sub(r"\s+", " ", "".join(parts)).strip()


# ---------------------------------------------------------------- verse (Vergil)

VERGIL = [
    ("phi0690/phi001/phi0690.phi001.perseus-lat2.xml", "Eclogues", "Ecloga"),
    ("phi0690/phi002/phi0690.phi002.perseus-lat2.xml", "Georgics", "Georgicon"),
    ("phi0690/phi003/phi0690.phi003.perseus-lat2.xml", "Aeneid", "Aeneis"),
]


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


def vergil_text() -> str:
    parts: list[str] = []
    for path, work, latin in VERGIL:
        sections = books(fetch(path))
        print(f"{work}: {len(sections)} books")
        for number, text in sections:
            heading = (
                f"BOOK {number}.\n{latin} {number}"
                if work == "Aeneid"
                else f"PART {number}.\n{latin} {number}"
            )
            parts.append(f"{heading}\n\n" + text.replace("\n", " ") + "\n")
    return "\n\n".join(parts)


# ---------------------------------------------------------------- prose (Cicero, Sallust)


def textparts(xml: str, subtype: str) -> list[ET.Element]:
    return list(ET.fromstring(xml).iterfind(f".//tei:div[@subtype='{subtype}']", NS))


def cicero_in_catilinam_text() -> str:
    """One document per speech; each section is a paragraph starting with its number."""
    xml = fetch("phi0474/phi013/phi0474.phi013.perseus-lat2.xml")
    documents = []
    for index, speech in enumerate(textparts(xml, "speech")):
        sections = [
            f"[{section.get('n')}] {reading_text(section)}"
            for section in speech.iterfind("tei:div[@subtype='section']", NS)
        ]
        documents.append(f"# In Catilinam {ROMAN[index]}\n\n" + "\n\n".join(sections))
    print(f"In Catilinam: {len(documents)} speeches")
    return "\n\n".join(documents) + "\n"


def sallust_catilina_text() -> str:
    """One document per chapter (cited as Sall. Cat. 1, 2, ...)."""
    xml = fetch("phi0631/phi001/phi0631.phi001.perseus-lat3.xml")
    chapters = []
    for chapter in textparts(xml, "chapter"):
        # a chapter milestone inside a division starts another chapter (Cat. 54 is nested in 53)
        pieces = reading_text(chapter, mark_chapters=True).split(CHAPTER_MARK)
        numbered = [(chapter.get("n"), pieces[0])] + list(zip(pieces[1::2], pieces[2::2]))
        chapters += [f"# Caput {n}\n\n{text.strip()}" for n, text in numbered if text.strip()]
    print(f"Catilinae coniuratio: {len(chapters)} chapters")
    return "\n\n".join(chapters) + "\n"


# ---------------------------------------------------------------- corpora


@dataclass(frozen=True)
class PerseusCorpus:
    text: Callable[[], str]
    title: str
    author: str
    year: int
    genre: str
    description: str
    source: str


CORPORA = {
    "vergil-opera": PerseusCorpus(
        text=vergil_text,
        title="Vergil: Eclogues, Georgics, Aeneid",
        author="P. Vergilius Maro",
        year=-19,
        genre="Latin poetry · Epic",
        description="Vergil's complete works in Latin, one document per book. The Aeneid is the source side of the Loci Similes intertextuality benchmark. Entities extracted with LatinCy (la_core_web_md).",
        source="Perseus Digital Library, canonical-latinLit (ed. J. B. Greenough, 1881) · CC BY-SA 4.0",
    ),
    "cicero-in-catilinam": PerseusCorpus(
        text=cicero_in_catilinam_text,
        title="Cicero: In Catilinam I–IV",
        author="M. Tullius Cicero",
        year=-63,
        genre="Latin prose · Speech",
        description="Cicero's four speeches against Catiline (63 BCE) in Latin, one document per speech; section numbers are given in square brackets. Entities extracted with LatinCy (la_core_web_md).",
        source="Perseus Digital Library, canonical-latinLit (ed. A. C. Clark, 1908) · CC BY-SA 4.0",
    ),
    "sallust-catilina": PerseusCorpus(
        text=sallust_catilina_text,
        title="Sallust: De Catilinae coniuratione",
        author="C. Sallustius Crispus",
        year=-41,
        genre="Latin prose · History",
        description="Sallust's monograph on the Catilinarian conspiracy (written c. 41 BCE) in Latin, one document per chapter. Entities extracted with LatinCy (la_core_web_md).",
        source="Perseus Digital Library, canonical-latinLit (ed. A. W. Ahlberg, 1919) · CC BY-SA 4.0",
    ),
}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--corpus", choices=sorted(CORPORA), default="vergil-opera")
    parser.add_argument("--spacy-model", default="la_core_web_md")
    parser.add_argument("--labels", default="PERSON,LOC,NORP,GRP,PERSON_MYTH")
    parser.add_argument("--window", type=int, default=2)
    args = parser.parse_args()

    corpus = CORPORA[args.corpus]
    text_path = CACHE / f"{args.corpus}.txt"
    text_path.write_text(corpus.text(), encoding="utf-8")
    print(f"{len(text_path.read_text(encoding='utf-8').split()):,} words")
    SEEDS.mkdir(parents=True, exist_ok=True)
    output = SEEDS / f"{args.corpus}.json.gz"
    # a rebuild bumps the seed revision, so running instances replace the corpus
    revision = (
        int(read_seed(output)["corpus"].get("revision", 0) or 0) + 1 if output.exists() else 0
    )
    subprocess.run(
        [
            sys.executable,
            str(ROOT / "scripts" / "build_seed.py"),
            str(text_path),
            "--slug",
            args.corpus,
            "--title",
            corpus.title,
            "--author",
            corpus.author,
            "--year",
            str(corpus.year),
            "--language",
            "la",
            "--genre",
            corpus.genre,
            "--source",
            corpus.source,
            "--description",
            corpus.description,
            "--extractor",
            "spacy",
            "--spacy-model",
            args.spacy_model,
            "--spacy-labels",
            args.labels,
            "--window",
            str(args.window),
            "--split",
            "headings",
            "--gzip",
            "--output",
            str(output),
            "--revision",
            str(revision),
        ],
        check=True,
        cwd=ROOT,
    )
    print("wrote", output, f"{output.stat().st_size / 1024:.0f} KB")


if __name__ == "__main__":
    main()
