"""Search-engine support: robots.txt, sitemap.xml and per-page metadata in the SPA shell.

The frontend is a single-page app, so every route is served the same ``index.html``. To give
crawlers (and link previews) something page-specific without JavaScript, the backend fills the
``<!-- seo:start -->…<!-- seo:end -->`` block in the head with the page's title, description,
canonical link, Open Graph tags and JSON-LD, and replaces ``<!-- seo:noscript -->`` in the body
with a plain-HTML fallback (the book list, or one book's summary).
"""

from __future__ import annotations

import json
from collections.abc import Sequence
from dataclasses import dataclass
from html import escape
from typing import Any
from urllib.parse import quote, urlsplit
from xml.sax.saxutils import escape as xml_escape

from fastapi import FastAPI, Request, Response
from fastapi.responses import RedirectResponse
from sqlmodel import Session, col, select

from app.models.entities import Corpus

SITE_NAME = "ECCE"
TAGLINE = "Entity-centric corpus exploration"
HEAD_START, HEAD_END = "<!-- seo:start -->", "<!-- seo:end -->"
NOSCRIPT = "<!-- seo:noscript -->"
DESCRIPTION_LENGTH = 160


@dataclass(frozen=True)
class PageMeta:
    """What one route tells search engines about itself."""

    title: str
    description: str
    path: str  # canonical path ("/", "/corpus/<slug>")
    status: int = 200
    noindex: bool = False
    og_type: str = "website"
    json_ld: dict[str, Any] | None = None
    noscript: str = ""  # HTML shown to visitors and crawlers without JavaScript


# ---------------------------------------------------------------- helpers


def site_url(request: Request, public_url: str | None) -> str:
    """Origin used in canonical links and the sitemap (``PUBLIC_URL`` or the request's own)."""
    if public_url:
        return public_url.rstrip("/")
    proto = request.headers.get("x-forwarded-proto", request.url.scheme).split(",")[0].strip()
    return f"{proto}://{request.headers.get('host') or request.url.netloc}"


def corpus_path(slug: str) -> str:
    return f"/corpus/{quote(slug)}"


def format_year(year: int | None) -> str:
    """Same convention as the frontend: negative years are BCE."""
    if year is None:
        return ""
    return f"c. {abs(year)} BCE" if year < 0 else str(year)


def shorten(text: str, limit: int = DESCRIPTION_LENGTH) -> str:
    """Collapse whitespace and cut at a word boundary so snippets are not truncated mid-word."""
    text = " ".join(text.split())
    if len(text) <= limit:
        return text
    return text[: limit - 1].rsplit(" ", 1)[0].rstrip(",;:·—-") + "…"


def public_corpora(session: Session) -> list[Corpus]:
    """Corpora anyone can open: visible and processed (as in the gallery)."""
    query = (
        select(Corpus)
        .where(Corpus.visible == True, Corpus.status == "ready")  # noqa: E712
        .order_by(col(Corpus.title))
    )
    return list(session.exec(query).all())


def byline(corpus: Corpus) -> str:
    year = format_year(corpus.year)
    return " · ".join(part for part in (corpus.author, year) if part)


# ---------------------------------------------------------------- page metadata


def home_meta(corpora: Sequence[Corpus], base: str) -> PageMeta:
    n = len(corpora)
    count = f"{n:,} book{'s' if n != 1 else ''}" if n else "text corpora"
    description = (
        f"Explore {count} as networks of the people, places and things they mention. "
        "Read page by page, search the text and follow every connection."
    )
    items = "".join(
        f'<li><a href="{corpus_path(c.slug)}">{escape(c.title)}</a>'
        + (f" ({escape(byline(c))})" if byline(c) else "")
        + "</li>"
        for c in corpora
    )
    noscript = f"<h1>{SITE_NAME}: {TAGLINE}</h1><p>{escape(description)}</p>" + (
        f"<h2>Book gallery</h2><ul>{items}</ul>" if items else ""
    )
    return PageMeta(
        title=f"{SITE_NAME} · {TAGLINE}",
        description=description,
        path="/",
        json_ld={
            "@context": "https://schema.org",
            "@type": "WebSite",
            "name": SITE_NAME,
            "alternateName": TAGLINE,
            "url": f"{base}/",
            "description": description,
        },
        noscript=noscript,
    )


def corpus_meta(corpus: Corpus, base: str) -> PageMeta:
    by = f" by {corpus.author}" if corpus.author else ""
    network = (
        f"Read {corpus.title}{by} page by page and explore its network of "
        f"{corpus.n_entities:,} people, places and things."
    )
    description = shorten(f"{corpus.description} {network}" if corpus.description else network)
    url = f"{base}{corpus_path(corpus.slug)}"
    book: dict[str, Any] = {"@type": "Book", "name": corpus.title, "inLanguage": corpus.language}
    if corpus.author:
        book["author"] = {"@type": "Person", "name": corpus.author}
    if corpus.year and corpus.year > 0:
        book["datePublished"] = str(corpus.year)
    if corpus.genre:
        book["genre"] = corpus.genre
    noscript = (
        f"<h1>{escape(corpus.title)}</h1>"
        + (f"<p>{escape(byline(corpus))}</p>" if byline(corpus) else "")
        + f"<p>{escape(description)}</p>"
        + (
            f"<blockquote>{escape(shorten(corpus.excerpt, 600))}</blockquote>"
            if corpus.excerpt
            else ""
        )
        + f'<p><a href="/">All books in the {SITE_NAME} gallery</a></p>'
    )
    return PageMeta(
        title=f"{corpus.title}{by} · {SITE_NAME}",
        description=description,
        path=corpus_path(corpus.slug),
        og_type="book",
        json_ld={
            "@context": "https://schema.org",
            "@type": "WebPage",
            "name": corpus.title,
            "url": url,
            "description": description,
            "about": book,
            "isPartOf": {"@type": "WebSite", "name": SITE_NAME, "url": f"{base}/"},
        },
        noscript=noscript,
    )


def not_found_meta(path: str) -> PageMeta:
    return PageMeta(
        title=f"Page not found · {SITE_NAME}",
        description="This page does not exist.",
        path=path,
        status=404,
        noindex=True,
        noscript='<h1>Page not found</h1><p><a href="/">Go to the book gallery</a></p>',
    )


def page_meta(path: str, session: Session, base: str) -> PageMeta:
    """Metadata for an SPA route (``path`` without the leading slash)."""
    parts = [p for p in path.split("/") if p]
    if not parts:
        return home_meta(public_corpora(session), base)
    if parts == ["admin"]:
        return PageMeta(
            title=f"Administration · {SITE_NAME}",
            description="Manage the corpora of this ECCE instance.",
            path="/admin",
            noindex=True,
        )
    if len(parts) == 2 and parts[0] == "corpus":
        corpus = session.exec(select(Corpus).where(Corpus.slug == parts[1])).first()
        if corpus is not None and corpus.visible and corpus.status == "ready":
            return corpus_meta(corpus, base)
    return not_found_meta("/" + "/".join(parts))


# ---------------------------------------------------------------- rendering


def head_tags(meta: PageMeta, base: str) -> str:
    url = f"{base}{meta.path}"
    title, description = escape(meta.title), escape(meta.description)
    tags = [
        f"<title>{title}</title>",
        f'<meta name="description" content="{description}" />',
    ]
    if meta.noindex:
        tags.append('<meta name="robots" content="noindex" />')
    else:
        tags.append(f'<link rel="canonical" href="{escape(url)}" />')
    tags += [
        f'<meta property="og:site_name" content="{SITE_NAME}" />',
        f'<meta property="og:type" content="{meta.og_type}" />',
        f'<meta property="og:title" content="{title}" />',
        f'<meta property="og:description" content="{description}" />',
        f'<meta property="og:url" content="{escape(url)}" />',
        '<meta name="twitter:card" content="summary" />',
        f'<meta name="twitter:title" content="{title}" />',
        f'<meta name="twitter:description" content="{description}" />',
    ]
    if meta.json_ld:
        data = json.dumps(meta.json_ld, ensure_ascii=False).replace("</", "<\\/")
        tags.append(f'<script type="application/ld+json">{data}</script>')
    return "\n    ".join(tags)


def render_index(template: str, meta: PageMeta, base: str) -> str:
    """Fill the SEO placeholders of the built ``index.html`` (unchanged if they are missing)."""
    start, end = template.find(HEAD_START), template.find(HEAD_END)
    html = template
    if 0 <= start < end:
        html = (
            html[: start + len(HEAD_START)]
            + "\n    "
            + head_tags(meta, base)
            + "\n    "
            + html[end:]
        )
    if meta.noscript:
        html = html.replace(NOSCRIPT, f"<noscript>{meta.noscript}</noscript>", 1)
    return html


def robots_txt(base: str) -> str:
    return f"User-agent: *\nDisallow: /admin\n\nSitemap: {base}/sitemap.xml\n"


def sitemap_xml(corpora: Sequence[Corpus], base: str) -> str:
    def entry(path: str, lastmod: str | None) -> str:
        mod = f"<lastmod>{lastmod}</lastmod>" if lastmod else ""
        return f"  <url><loc>{xml_escape(base + path)}</loc>{mod}</url>"

    newest = max((c.updated_at for c in corpora), default=None)
    urls = [entry("/", newest.date().isoformat() if newest else None)]
    urls += [entry(corpus_path(c.slug), c.updated_at.date().isoformat()) for c in corpora]
    return (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
        + "\n".join(urls)
        + "\n</urlset>\n"
    )


# ---------------------------------------------------------------- middleware


def add_seo_middleware(app: FastAPI, public_url: str | None) -> None:
    """Redirect other hosts to ``PUBLIC_URL``, keep the API out of search results and let
    browsers cache the content-hashed build assets."""
    canonical = urlsplit(public_url.rstrip("/")) if public_url else None

    @app.middleware("http")
    async def seo_headers(request: Request, call_next: Any) -> Response:
        path = request.url.path
        if (
            canonical is not None
            and request.method in ("GET", "HEAD")
            and not path.startswith("/api/")
            and request.headers.get("host") != canonical.netloc
        ):
            query = f"?{request.url.query}" if request.url.query else ""
            target = f"{canonical.scheme}://{canonical.netloc}{path}{query}"
            return RedirectResponse(target, status_code=301)
        response: Response = await call_next(request)
        if path.startswith("/api/"):
            response.headers["X-Robots-Tag"] = "noindex"
        elif path.startswith("/assets/") and response.status_code == 200:
            response.headers["Cache-Control"] = "public, max-age=31536000, immutable"
        return response
