"""robots.txt, sitemap.xml, per-page metadata in the SPA shell and the canonical-host redirect."""

from __future__ import annotations

import json
import re
from pathlib import Path

import pytest
from app.core.config import Settings
from app.core.database import create_db_engine
from app.main import create_app
from app.services.seo import PageMeta, render_index, shorten
from fastapi.testclient import TestClient

INDEX = """<!doctype html>
<html lang="en">
  <head>
    <!-- seo:start -->
    <title>default</title>
    <!-- seo:end -->
  </head>
  <body>
    <div id="root"></div>
    <!-- seo:noscript -->
  </body>
</html>
"""


@pytest.fixture
def settings(settings: Settings, tmp_path: Path) -> Settings:
    """The shared settings plus a minimal built frontend."""
    dist = tmp_path / "dist"
    (dist / "assets").mkdir(parents=True)
    (dist / "index.html").write_text(INDEX, encoding="utf-8")
    (dist / "assets" / "app-1234.js").write_text("console.log(1)", encoding="utf-8")
    (dist / "favicon.svg").write_text("<svg/>", encoding="utf-8")
    (tmp_path / "secret.txt").write_text("TOP-SECRET-CONTENT", encoding="utf-8")
    return settings.model_copy(update={"frontend_dist": dist})


def json_ld(html: str) -> dict:
    match = re.search(r'<script type="application/ld\+json">(.*?)</script>', html, re.S)
    assert match, html
    return json.loads(match.group(1))


def test_home_page_carries_metadata_and_a_book_list(client, alice):
    response = client.get("/")
    assert response.status_code == 200
    html = response.text
    assert "<title>default</title>" not in html
    assert "<title>ECCE · Entity-centric corpus exploration</title>" in html
    assert '<link rel="canonical" href="http://testserver/" />' in html
    assert 'content="Explore 1 book as networks' in html
    assert json_ld(html)["@type"] == "WebSite"
    assert "<noscript><h1>ECCE" in html and f'href="/corpus/{alice["slug"]}"' in html


def test_corpus_page_describes_the_book(client, alice):
    html = client.get(f"/corpus/{alice['slug']}?page=2").text
    assert f"<title>{alice['title']} · ECCE</title>" in html
    # the canonical URL drops reader state such as ?page=
    assert f'<link rel="canonical" href="http://testserver/corpus/{alice["slug"]}" />' in html
    assert '<meta property="og:type" content="book" />' in html
    data = json_ld(html)
    assert data["@type"] == "WebPage" and data["about"]["name"] == alice["title"]
    description = re.search(r'<meta name="description" content="([^"]*)"', html)
    assert description and "people, places and things" in description.group(1)


def test_unknown_and_private_pages_are_not_indexed(client, admin_headers, alice):
    for path in ("/corpus/missing", "/nothing/here"):
        response = client.get(path)
        assert response.status_code == 404
        assert '<meta name="robots" content="noindex" />' in response.text
        assert 'rel="canonical"' not in response.text
    admin = client.get("/admin")
    assert admin.status_code == 200 and 'content="noindex"' in admin.text
    client.patch(
        f"/api/admin/corpora/{alice['slug']}", json={"visible": False}, headers=admin_headers
    )
    assert client.get(f"/corpus/{alice['slug']}").status_code == 404


def test_robots_and_sitemap(client, admin_headers, alice):
    robots = client.get("/robots.txt")
    assert robots.headers["content-type"].startswith("text/plain")
    assert "Disallow: /admin" in robots.text
    assert "Sitemap: http://testserver/sitemap.xml" in robots.text
    assert "Disallow: /api" not in robots.text  # crawlers render the app, which needs the API

    sitemap = client.get("/sitemap.xml")
    assert sitemap.headers["content-type"] == "application/xml"
    locs = re.findall(r"<loc>(.*?)</loc>", sitemap.text)
    assert locs == ["http://testserver/", f"http://testserver/corpus/{alice['slug']}"]

    client.patch(
        f"/api/admin/corpora/{alice['slug']}", json={"visible": False}, headers=admin_headers
    )
    assert re.findall(r"<loc>(.*?)</loc>", client.get("/sitemap.xml").text) == [
        "http://testserver/"
    ]


def test_static_files_headers_and_head_requests(client):
    asset = client.get("/assets/app-1234.js")
    assert asset.headers["cache-control"] == "public, max-age=31536000, immutable"
    assert client.get("/favicon.svg").text == "<svg/>"
    assert client.get("/api/health").headers["x-robots-tag"] == "noindex"
    assert client.head("/").status_code == 200
    # files outside the build directory are never served
    assert "TOP-SECRET-CONTENT" not in client.get("/..%2Fsecret.txt").text


def test_public_url_sets_canonical_links_and_redirects_other_hosts(settings, alice):
    settings = settings.model_copy(update={"public_url": "https://www.example.org/"})
    app = create_app(settings, create_db_engine(settings.resolved_database_url))
    with TestClient(app, base_url="https://example.org", follow_redirects=False) as other_host:
        response = other_host.get(f"/corpus/{alice['slug']}?page=3")
        assert response.status_code == 301
        assert response.headers["location"] == (
            f"https://www.example.org/corpus/{alice['slug']}?page=3"
        )
        assert other_host.get("/api/health").status_code == 200  # health checks and API stay put
    with TestClient(app, base_url="https://www.example.org") as canonical:
        html = canonical.get("/").text
        assert '<link rel="canonical" href="https://www.example.org/" />' in html
        assert "Sitemap: https://www.example.org/sitemap.xml" in canonical.get("/robots.txt").text


def test_rendering_escapes_untrusted_text():
    meta = PageMeta(
        title='Tom & "Jerry" <b>',
        description="</script><script>alert(1)</script>",
        path="/",
        json_ld={"name": "</script><script>alert(1)</script>"},
        noscript="<p>fallback</p>",
    )
    html = render_index(INDEX, meta, "https://example.org")
    assert "<title>Tom &amp; &quot;Jerry&quot; &lt;b&gt;</title>" in html
    assert html.count("</script>") == 1  # only the JSON-LD block's own closing tag
    assert "<noscript><p>fallback</p></noscript>" in html
    assert render_index("<html></html>", meta, "https://example.org") == "<html></html>"


def test_shorten_cuts_at_word_boundaries():
    assert shorten("short  text") == "short text"
    cut = shorten("word " * 60)
    assert len(cut) <= 160 and cut.endswith("word…")
