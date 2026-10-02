"""Check the rights status of every Latin text in the Perseus Digital Library (canonical-latinLit).

Reads the TEI header of each Latin edition (``*-lat*.xml``) and admits a work only when the
header names the editor and a printed edition published before 1931: such an edition is in the
public domain in the US, and the 25-year protection of scientific editions in Germany (§ 70 UrhG)
has long expired; the ancient text itself is free. Perseus' digital edition is licensed
CC BY-SA 4.0 (repository-wide). Files without a documented editor or year are rejected.

Writes ``data/catalogue/perseus_inventory.json`` (one entry per Latin file, with the verdict and
the division structure the seed builder needs). Curated entries for the gallery live in
``data/catalogue/perseus.json``.

    python scripts/verify_perseus.py
"""

from __future__ import annotations

import concurrent.futures
import html
import json
import re
import urllib.request
import xml.etree.ElementTree as ET
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
INVENTORY = ROOT / "data" / "catalogue" / "perseus_inventory.json"
CACHE = ROOT / "data" / "cache" / "perseus"
REPO = "PerseusDL/canonical-latinLit"
RAW = f"https://raw.githubusercontent.com/{REPO}/master/"
LATEST_EDITION_YEAR = 1930
NS = {"tei": "http://www.tei-c.org/ns/1.0"}


def get(url: str, attempts: int = 3) -> bytes:
    for attempt in range(attempts):
        try:
            request = urllib.request.Request(url, headers={"User-Agent": "ecce-perseus-check"})
            with urllib.request.urlopen(request, timeout=120) as response:
                return response.read()
        except Exception:  # noqa: BLE001
            if attempt == attempts - 1:
                raise
    raise RuntimeError("unreachable")


def latin_files() -> list[str]:
    tree = json.loads(get(f"https://api.github.com/repos/{REPO}/git/trees/master?recursive=1"))
    return sorted(
        t["path"]
        for t in tree["tree"]
        if t["type"] == "blob"
        and t["path"].startswith("data/")
        and re.search(r"\.perseus-lat\d+\.xml$", t["path"])
    )


XML_ENTITIES = {"amp", "lt", "gt", "quot", "apos"}


def parse_tei(raw: str) -> ET.Element:
    """Parse a Perseus TEI file; some use HTML entities (&dagger;) that XML does not define."""

    def entity(match: re.Match[str]) -> str:
        name = match.group(1)
        return match.group(0) if name in XML_ENTITIES else html.unescape(match.group(0))

    return ET.fromstring(re.sub(r"&([A-Za-z][A-Za-z0-9]*);", entity, raw))


def text_of(element: ET.Element | None) -> str:
    return re.sub(r"\s+", " ", "".join(element.itertext())).strip() if element is not None else ""


def structure(body: ET.Element) -> list[str]:
    """Division subtypes from the outside in, e.g. ["book", "poem"] or ["speech", "section"]."""
    levels: list[str] = []
    divs = [d for d in body.iter(f"{{{NS['tei']}}}div") if d.get("type") == "textpart"]
    depth: dict[int, Counter[str]] = {}

    def walk(node: ET.Element, level: int) -> None:
        for child in node:
            if child.tag == f"{{{NS['tei']}}}div" and child.get("type") == "textpart":
                depth.setdefault(level, Counter())[child.get("subtype") or "part"] += 1
                walk(child, level + 1)
            else:
                walk(child, level)

    if divs:
        walk(body, 0)
        levels = [depth[k].most_common(1)[0][0] for k in sorted(depth)]
    return levels


def inspect(path: str) -> dict:
    CACHE.mkdir(parents=True, exist_ok=True)
    local = CACHE / Path(path).name
    if not local.exists():
        local.write_bytes(get(RAW + path))
    try:
        root = parse_tei(local.read_text(encoding="utf-8"))
    except ET.ParseError as error:
        return {
            "path": path.removeprefix("data/"),
            "verified": False,
            "problems": [f"unparsable: {error}"],
        }
    header = root.find("tei:teiHeader", NS)
    source = header.find(".//tei:sourceDesc", NS) if header is not None else None
    bibl = source.find(".//tei:biblStruct", NS) if source is not None else None
    scope = bibl if bibl is not None else source
    editors = (
        [text_of(e) for e in scope.iter(f"{{{NS['tei']}}}editor")] if scope is not None else []
    )
    if scope is not None:  # some headers name the editor as <respStmt><resp>editor</resp>
        editors += [
            text_of(r.find("tei:name", NS))
            for r in scope.iter(f"{{{NS['tei']}}}respStmt")
            if "editor" in text_of(r.find("tei:resp", NS)).lower()
        ]
    years = [
        int(y)
        for d in (scope.iter(f"{{{NS['tei']}}}date") if scope is not None else [])
        for y in re.findall(r"\b(1[5-9]\d\d|20\d\d)\b", text_of(d))
    ]
    imprint = (
        ", ".join(
            filter(
                None,
                (text_of(scope.find(f".//tei:{tag}", NS)) for tag in ("pubPlace", "publisher")),
            )
        )
        if scope is not None
        else ""
    )
    title_stmt = header.find(".//tei:titleStmt", NS) if header is not None else None
    body = root.find(".//tei:body", NS)
    edition_year = max(years) if years else None
    problems = []
    if not [e for e in editors if e]:
        problems.append("no editor documented")
    if edition_year is None:
        problems.append("no edition year documented")
    elif edition_year > LATEST_EDITION_YEAR:
        problems.append(f"edition published {edition_year} (after {LATEST_EDITION_YEAR})")
    return {
        "path": path.removeprefix("data/"),
        "title": text_of(title_stmt.find("tei:title", NS)) if title_stmt is not None else "",
        "author": text_of(title_stmt.find("tei:author", NS)) if title_stmt is not None else "",
        "editors": sorted({e for e in editors if e}),
        "edition_year": edition_year,
        "imprint": imprint,
        "structure": structure(body) if body is not None else [],
        "words": len(text_of(body).split()) if body is not None else 0,
        "verified": not problems,
        "problems": problems,
    }


def main() -> None:
    files = latin_files()
    with concurrent.futures.ThreadPoolExecutor(8) as pool:
        entries = list(pool.map(inspect, files))
    INVENTORY.write_text(json.dumps(entries, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    ok = [e for e in entries if e["verified"]]
    print(f"{len(entries)} Latin files, {len(ok)} admitted, {len(entries) - len(ok)} rejected")
    for e in entries:
        if not e["verified"]:
            print(f"  !! {e['path']}: {'; '.join(e['problems'])}")


if __name__ == "__main__":
    main()
