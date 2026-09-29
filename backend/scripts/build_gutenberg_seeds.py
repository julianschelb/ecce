"""Download public-domain works from Project Gutenberg and build precomputed seeds.

Usage::

    python scripts/build_gutenberg_seeds.py            # all works in data/catalogue/gutenberg.json
    python scripts/build_gutenberg_seeds.py --only dracula moby-dick --extractor spacy

Texts are cached in ``data/cache/gutenberg`` (git-ignored); seeds are written to
``data/seed/<slug>.json.gz``. Gutenberg headers/footers and licence boilerplate are removed;
chapter headings become documents.
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
    return text.strip() + "\n"


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
