"""Reading pages, the page graph, page lists for graph selections and the book index."""

from __future__ import annotations

from app.services.pagination import PAGE_WORDS, assign_pages, count_words


def test_assign_pages_respects_budget_and_document_boundaries():
    # (document, words) in reading order; budget 100 words
    chunks = [(0, 60), (0, 30), (0, 30), (0, 150), (0, 10), (1, 10), (1, 10), (2, 5)]
    assert assign_pages(chunks, page_words=100) == [1, 1, 2, 3, 4, 5, 5, 6]
    assert assign_pages([]) == []
    assert assign_pages([(7, 1)]) == [1]
    assert count_words("  two   words\nhere ") == 3


def test_pages_cover_every_chunk_in_reading_order(client, alice):
    slug = alice["slug"]
    n_pages = alice["n_pages"]
    assert n_pages > 3
    documents = client.get(f"/api/corpora/{slug}/documents").json()
    assert [d["first_page"] for d in documents] == sorted(d["first_page"] for d in documents)
    assert documents[0]["first_page"] == 1

    seen: list[int] = []
    for number in range(1, n_pages + 1):
        page = client.get(f"/api/corpora/{slug}/pages/{number}").json()
        assert page["number"] == number and page["n_pages"] == n_pages
        assert page["chunks"], "every page holds at least one passage"
        assert {c["document_id"] for c in page["chunks"]} == {page["document_id"]}
        assert all(c["page"] == number for c in page["chunks"])
        words = sum(count_words(c["text"]) for c in page["chunks"])
        assert words <= PAGE_WORDS or len(page["chunks"]) == 1
        assert page["opens_document"] == (page["chunks"][0]["position"] == 0)
        seen.extend(c["id"] for c in page["chunks"])
    assert len(seen) == alice["n_chunks"] and len(set(seen)) == len(seen)
    # chapter starts open a new page
    opens = [client.get(f"/api/corpora/{slug}/pages/{d['first_page']}").json() for d in documents]
    assert all(
        p["opens_document"] and p["document_id"] == d["id"] for p, d in zip(opens, documents)
    )
    assert client.get(f"/api/corpora/{slug}/pages/0").status_code == 404
    assert client.get(f"/api/corpora/{slug}/pages/{n_pages + 1}").status_code == 404


def test_page_entities_and_page_graph(client, alice):
    slug = alice["slug"]
    page = client.get(f"/api/corpora/{slug}/pages/2").json()
    mentioned = {m["entity_id"] for c in page["chunks"] for m in c["mentions"]}
    assert {e["id"] for e in page["entities"]} == mentioned
    assert sum(e["page_mentions"] for e in page["entities"]) == sum(
        len(c["mentions"]) for c in page["chunks"]
    )
    counts = [e["page_mentions"] for e in page["entities"]]
    assert counts == sorted(counts, reverse=True)

    graph = client.get(f"/api/corpora/{slug}/pages/2/graph").json()
    ids = {n["id"] for n in graph["nodes"]}
    assert ids == mentioned and graph["total_nodes"] == len(mentioned)
    assert all(e["source"] in ids and e["target"] in ids for e in graph["edges"])
    assert graph["total_edges"] == len(graph["edges"])
    strengths = [n["strength"] for n in graph["nodes"]]
    assert strengths == sorted(strengths, reverse=True)
    assert client.get(f"/api/corpora/{slug}/pages/9999/graph").status_code == 404
    limited = client.get(f"/api/corpora/{slug}/pages/2/graph", params={"max_nodes": 2}).json()
    assert len(limited["nodes"]) == 2 and limited["total_nodes"] == len(mentioned)


def test_chapter_graph(client, alice):
    """The graph of one document: every entity mentioned in it, corpus-wide weights."""
    slug = alice["slug"]
    documents = client.get(f"/api/corpora/{slug}/documents").json()
    first = documents[0]
    mentioned: set[int] = set()
    last_page = documents[1]["first_page"] - 1 if len(documents) > 1 else alice["n_pages"]
    for number in range(first["first_page"], last_page + 1):
        page = client.get(f"/api/corpora/{slug}/pages/{number}").json()
        if page["document_id"] == first["id"]:
            mentioned |= {m["entity_id"] for c in page["chunks"] for m in c["mentions"]}
    graph = client.get(f"/api/corpora/{slug}/documents/{first['id']}/graph").json()
    assert {n["id"] for n in graph["nodes"]} == mentioned
    assert graph["total_nodes"] == len(mentioned) > 0
    ids = {n["id"] for n in graph["nodes"]}
    assert all(e["source"] in ids and e["target"] in ids for e in graph["edges"])
    assert client.get(f"/api/corpora/{slug}/documents/999999/graph").status_code == 404


def test_page_refs_follow_graph_selections(client, alice):
    slug = alice["slug"]
    alice_node = client.get(f"/api/corpora/{slug}/entities", params={"q": "alice"}).json()[0]
    refs = client.get(f"/api/corpora/{slug}/pages", params={"entity_id": alice_node["id"]}).json()
    assert refs["total"] == len(refs["items"]) > 3
    numbers = [r["number"] for r in refs["items"]]
    assert numbers == sorted(set(numbers))
    for ref in refs["items"][:3]:
        page = client.get(f"/api/corpora/{slug}/pages/{ref['number']}").json()
        assert alice_node["id"] in {e["id"] for e in page["entities"]}
        assert page["document_title"] == ref["document_title"]
        assert 1 <= ref["hits"] <= len(page["chunks"])

    neighbour = client.get(f"/api/corpora/{slug}/entities/{alice_node['id']}").json()["neighbors"][
        0
    ]
    both = client.get(
        f"/api/corpora/{slug}/pages",
        params={"entity_id": [alice_node["id"], neighbour["entity"]["id"]]},
    ).json()
    assert 0 < both["total"] <= refs["total"]
    assert {r["number"] for r in both["items"]} <= set(numbers)

    documents = client.get(f"/api/corpora/{slug}/documents").json()
    in_doc = client.get(
        f"/api/corpora/{slug}/pages", params={"document_id": documents[1]["id"], "limit": 2}
    ).json()
    assert len(in_doc["items"]) == 2 and in_doc["total"] >= 2
    assert in_doc["items"][0]["number"] == documents[1]["first_page"]


def test_index_lists_every_entity_with_its_pages(client, alice):
    slug = alice["slug"]
    index = client.get(f"/api/corpora/{slug}/index").json()
    assert index["total"] == alice["n_entities"] == len(index["entries"])
    assert index["n_pages"] == alice["n_pages"]
    first = index["entries"][0]
    assert first["entity"]["text"] == "Alice"
    counts = [e["entity"]["count"] for e in index["entries"]]
    assert counts == sorted(counts, reverse=True)
    for entry in index["entries"]:
        assert entry["pages"] == sorted(set(entry["pages"]))
        assert entry["pages"] and 1 <= entry["pages"][0] and entry["pages"][-1] <= alice["n_pages"]
    refs = client.get(
        f"/api/corpora/{slug}/pages", params={"entity_id": first["entity"]["id"]}
    ).json()
    assert [r["number"] for r in refs["items"]] == first["pages"]

    rabbit = client.get(f"/api/corpora/{slug}/index", params={"q": "rabbit"}).json()
    assert rabbit["entries"] and all(
        "rabbit" in e["entity"]["text"].lower() for e in rabbit["entries"]
    )
    label = first["entity"]["label"]
    typed = client.get(f"/api/corpora/{slug}/index", params={"label": label, "limit": 5}).json()
    assert len(typed["entries"]) == 5 and all(
        e["entity"]["label"] == label for e in typed["entries"]
    )
    assert typed["total"] >= 5


def test_search_hits_and_edge_passages_carry_page_numbers(client, alice):
    slug = alice["slug"]
    hits = client.get(f"/api/corpora/{slug}/search", params={"q": "rabbit hole"}).json()["hits"]
    assert hits and all(1 <= h["chunk"]["page"] <= alice["n_pages"] for h in hits)
    alice_node = client.get(f"/api/corpora/{slug}/entities", params={"q": "alice"}).json()[0]
    detail = client.get(f"/api/corpora/{slug}/entities/{alice_node['id']}").json()
    edge = client.get(
        f"/api/corpora/{slug}/edges/{alice_node['id']}/{detail['neighbors'][0]['entity']['id']}"
    ).json()
    assert all(c["page"] >= 1 for c in edge["chunks"])
