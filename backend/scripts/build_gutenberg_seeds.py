"""Download public-domain works from Project Gutenberg and build precomputed seeds.

Usage::

    python scripts/build_gutenberg_seeds.py            # all works in data/catalogue/gutenberg.json
    python scripts/build_gutenberg_seeds.py --only dracula moby-dick --extractor spacy

Texts are cached in ``data/cache/gutenberg`` (git-ignored); seeds are written to
``data/seed/<slug>.json.gz``. Gutenberg headers/footers and licence boilerplate are removed,
and so is everything Project Gutenberg's volunteers added to the work (end-of-ebook lines,
"Produced by" credits, transcriber's notes, production appendices), so the shipped texts contain
only the public-domain work and no reference to the Project Gutenberg trademark. Chapter
headings become documents. Rebuilding an existing seed (``--force``) bumps its ``revision`` so
running instances replace the corpus on their next start.
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

from app.services.seed import read_seed

ROOT = Path(__file__).resolve().parents[1]
CATALOGUE = ROOT / "data" / "catalogue" / "gutenberg.json"
CACHE = ROOT / "data" / "cache" / "gutenberg"
SEEDS = ROOT / "data" / "seed"

START_RE = re.compile(r"\*\*\*\s*START OF (?:THE|THIS) PROJECT GUTENBERG EBOOK.*?\*\*\*", re.I)
END_RE = re.compile(r"\*\*\*\s*END OF (?:THE|THIS) PROJECT GUTENBERG EBOOK.*?\*\*\*", re.I)
HEADING_RE = re.compile(
    r"^\s*(?:CHAPTER|Chapter|BOOK|Book|PART|Part|LETTER|Letter|STAVE|Stave|ADVENTURE|Adventure|STORY|Story)\s+[A-Z0-9IVXLC]+\b.*$",
    re.M,
)

# additions by Project Gutenberg volunteers (see strip_production_notes)
END_MARK_RE = re.compile(
    r"^\W*(?:End of (?:the )?Project Gutenberg|Project Gutenberg'?s? E-?(?:text|book))", re.I
)
APPENDIX_RE = re.compile(r"^(?:Appendix: )?Production notes for e-?book", re.I)
CREDIT_RE = re.compile(
    r"^(?:(?:This )?E-?(?:text|book) )?(?:was )?(?:Produced|Prepared|Transcribed|Proofread|"
    r"HTML version) by\b",
    re.I,
)
NOTES_HEADING_RE = re.compile(r"^\W*(?:Original )?Transcriber['’]s Notes?\W*$", re.I)
NOTE_PARAGRAPH_RE = re.compile(r"^\W*(?:Original )?Transcriber['’]s Notes?\s*:", re.I)
INLINE_NOTE_RE = re.compile(
    r"\s*\[(?:Transcriber['’]s Notes?|End of tran?scriptions?)[^\]]*\]", re.I
)
MENTION_RE = re.compile(
    r"Project Gutenberg|\be-?texts?\b|\be-?book edition|pgdp\.net|Distributed Proofread|"
    r"[\w.+-]+@[\w-]+\.[\w.]+",
    re.I,
)
TITLE_LIKE_RE = re.compile(r"^[^a-z]{3,}$")  # an all-capitals heading such as "ETYMOLOGY."


def strip_production_notes(text: str) -> str:
    """Remove what Project Gutenberg's volunteers added around and inside the work."""
    paragraphs = [p for p in re.split(r"\n\s*\n", text.strip()) if p.strip()]
    kept: list[str] = []
    index = 0
    while index < len(paragraphs):
        paragraph = INLINE_NOTE_RE.sub("", paragraphs[index]).strip()
        index += 1
        if END_MARK_RE.match(paragraph) or APPENDIX_RE.match(paragraph):
            break  # nothing after an end-of-ebook line or a production appendix is the work
        if NOTES_HEADING_RE.match(paragraph):
            if index > 0.8 * len(paragraphs):
                break  # closing notes run to the end of the file
            # opening notes run until the first heading of the work (a few paragraphs at most)
            ahead = paragraphs[index : index + 8]
            heading = next((i for i, p in enumerate(ahead) if TITLE_LIKE_RE.match(p.strip())), 0)
            index += heading
            continue
        if paragraph.startswith("[") and re.match(r"^\[\s*Transcriber", paragraph, re.I):
            while not paragraph.endswith("]") and index < len(paragraphs):
                paragraph = paragraphs[index].strip()  # a bracketed note over several paragraphs
                index += 1
            continue
        if not paragraph or CREDIT_RE.match(paragraph) or NOTE_PARAGRAPH_RE.match(paragraph):
            continue
        if MENTION_RE.search(paragraph):
            continue
        kept.append(paragraph)
    return "\n\n".join(kept)


def download(gutenberg_id: int, attempts: int = 3) -> str:
    """Fetch the plain-text ebook (cached); retries with a pause on transient errors."""
    CACHE.mkdir(parents=True, exist_ok=True)
    target = CACHE / f"pg{gutenberg_id}.txt"
    if target.exists():
        return target.read_text(encoding="utf-8")
    shelf = "/".join(str(gutenberg_id)[:-1]) or "0"
    urls = (
        f"https://www.gutenberg.org/cache/epub/{gutenberg_id}/pg{gutenberg_id}.txt",
        f"https://www.gutenberg.org/files/{gutenberg_id}/{gutenberg_id}-0.txt",
        # official mirrors, used when the main site is overloaded
        f"https://gutenberg.pglaf.org/{shelf}/{gutenberg_id}/{gutenberg_id}-0.txt",
        f"http://mirrors.xmission.com/gutenberg/{shelf}/{gutenberg_id}/{gutenberg_id}-0.txt",
        f"https://gutenberg.pglaf.org/{shelf}/{gutenberg_id}/{gutenberg_id}.txt",
    )
    for attempt in range(1, attempts + 1):
        for url in urls:
            try:
                with urllib.request.urlopen(
                    urllib.request.Request(url, headers={"User-Agent": "ecce-seed-builder"}),
                    timeout=90,
                ) as response:
                    raw = response.read().decode("utf-8-sig", errors="replace")
                target.write_text(raw, encoding="utf-8")
                time.sleep(1.5)  # be polite to Gutenberg's mirrors
                return raw
            except Exception as error:  # noqa: BLE001
                print(f"  download failed from {url}: {error}")
        if attempt < attempts:
            time.sleep(10 * attempt)
    raise RuntimeError(f"could not download Gutenberg #{gutenberg_id}")


def clean(raw: str) -> str:
    """Strip Gutenberg boilerplate, unwrap paragraphs, drop the table of contents."""
    start = START_RE.search(raw)
    end = END_RE.search(raw)
    body = raw[start.end() if start else 0 : end.start() if end else len(raw)]
    body = body.replace("\r\n", "\n")
    # drop everything before the first heading that is followed by real text (skips contents lists)
    headings = list(HEADING_RE.finditer(body))
    if len(headings) >= 2:
        first_real = None
        for index, match in enumerate(headings):
            nxt = headings[index + 1].start() if index + 1 < len(headings) else len(body)
            if len(body[match.end() : nxt].split()) > 120:
                first_real = match.start()
                break
        if first_real is not None:
            body = body[first_real:]
    paragraphs = re.split(r"\n\s*\n", body.strip())
    cleaned = []
    for paragraph in paragraphs:
        lines = [line.strip() for line in paragraph.split("\n")]
        if HEADING_RE.match(lines[0]):
            cleaned.append("\n".join(lines))
        else:
            cleaned.append(" ".join(lines))
    text = "\n\n".join(cleaned)
    text = re.sub(r"_+", "", text)  # Gutenberg italics markers
    return strip_production_notes(text) + "\n"


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--only", nargs="*", default=None, help="slugs to build")
    parser.add_argument("--extractor", default="spacy")
    parser.add_argument("--window", type=int, default=2)
    parser.add_argument("--force", action="store_true", help="rebuild existing seeds")
    parser.add_argument(
        "--download-only",
        action="store_true",
        help="only fetch the texts into the cache (one polite connection), build later",
    )
    args = parser.parse_args()

    catalogue = json.loads(CATALOGUE.read_text(encoding="utf-8"))
    SEEDS.mkdir(parents=True, exist_ok=True)
    failures: list[str] = []
    for entry in catalogue:
        if args.only and entry["slug"] not in args.only:
            continue
        output = SEEDS / f"{entry['slug']}.json.gz"
        if output.exists() and not args.force:
            print(f"skip {entry['slug']} (exists)")
            continue
        if entry.get("verified") is False:
            print(f"skip {entry['slug']} (rights check failed, see verify_catalogue.py)")
            continue
        print(f"== {entry['title']} (#{entry['id']})")
        try:
            text = clean(download(entry["id"]))
        except RuntimeError as error:
            print(f"  !! {error}; continuing with the next work")
            failures.append(entry["slug"])
            continue
        if args.download_only:
            print(f"  cached ({len(text.split()):,} words)")
            continue
        text_path = CACHE / f"{entry['slug']}.txt"
        text_path.write_text(text, encoding="utf-8")
        print(f"  {len(text.split()):,} words, {len(HEADING_RE.findall(text))} headings")
        command = [
            sys.executable,
            str(ROOT / "scripts" / "build_seed.py"),
            str(text_path),
            "--slug",
            entry["slug"],
            "--title",
            entry["title"],
            "--author",
            entry["author"],
            "--genre",
            entry["genre"],
            "--source",
            f"Project Gutenberg #{entry['id']}",
            "--description",
            entry["description"],
            "--extractor",
            args.extractor,
            "--window",
            str(args.window),
            "--gzip",
            "--output",
            str(output),
        ]
        if output.exists():  # a rebuild: running instances replace the corpus
            revision = int(read_seed(output)["corpus"].get("revision", 0) or 0) + 1
            command += ["--revision", str(revision)]
        if entry.get("year") is not None:
            command += ["--year", str(entry["year"])]
        started = time.perf_counter()
        result = subprocess.run(command, cwd=ROOT, stdout=subprocess.DEVNULL)
        if result.returncode != 0 or not output.exists():
            print(f"  !! build of {entry['slug']} failed (exit {result.returncode})")
            failures.append(entry["slug"])
            continue
        print(
            f"  -> {output.name} ({output.stat().st_size / 1024:.0f} KB) in {time.perf_counter() - started:.0f}s"
        )
    if failures:
        print(f"\nFAILED ({len(failures)}): {' '.join(failures)}")
        sys.exit(1)


if __name__ == "__main__":
    main()
