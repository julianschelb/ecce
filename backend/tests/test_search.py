"""Full-text search, entity filtering and the chunk reader."""

from __future__ import annotations


def test_search_returns_ranked_snippets(client, alice):
    slug = alice["slug"]
    result = client.get(f"/api/corpora/{slug}/search", params={"q": "rabbit hole"}).json()
    assert result["total"] >= 1 and result["hits"]
    first = result["hits"][0]
    assert "<mark>" in first["snippet"]
    assert "rabbit" in first["chunk"]["text"].lower()
    assert first["chunk"]["document_title"].startswith("CHAPTER")
    scores = [hit["score"] for hit in result["hits"]]
    assert scores == sorted(scores, reverse=True)


def test_search_prefix_and_pagination(client, alice):
    slug = alice["slug"]
    page1 = client.get(f"/api/corpora/{slug}/search", params={"q": "rabb", "limit": 2}).json()
    page2 = client.get(
        f"/api/corpora/{slug}/search", params={"q": "rabb", "limit": 2, "offset": 2}
    ).json()
    assert page1["total"] == page2["total"] >= 3  # "Rabbit" via prefix match
    assert {h["chunk"]["id"] for h in page1["hits"]}.isdisjoint(
        {h["chunk"]["id"] for h in page2["hits"]}
    )
    assert client.get(f"/api/corpora/{slug}/search", params={"q": "zzzzqqq"}).json()["total"] == 0
    assert client.get(f"/api/corpora/{slug}/search", params={"q": '"unbalanced'}).status_code == 200


def test_search_cross_referenced_with_entities(client, alice):
    slug = alice["slug"]
    rabbit = client.get(f"/api/corpora/{slug}/entities", params={"q": "rabbit"}).json()[0]
    all_hits = client.get(f"/api/corpora/{slug}/search", params={"q": "watch"}).json()
    filtered = client.get(
        f"/api/corpora/{slug}/search", params={"q": "watch", "entity_id": rabbit["id"]}
    ).json()
    assert 0 < filtered["total"] <= all_hits["total"]
    for hit in filtered["hits"]:
        assert rabbit["id"] in {m["entity_id"] for m in hit["chunk"]["mentions"]}


def test_chunks_by_entity_and_document(client, alice):
    slug = alice["slug"]
    documents = client.get(f"/api/corpora/{slug}/documents").json()
    assert len(documents) == 3 and all(d["n_chunks"] > 0 for d in documents)
    alice_node = client.get(f"/api/corpora/{slug}/entities", params={"q": "alice"}).json()[0]
    page = client.get(
        f"/api/corpora/{slug}/chunks", params={"entity_id": alice_node["id"], "page_size": 10}
    ).json()
    assert page["total"] > 10 and len(page["items"]) == 10
    for chunk in page["items"]:
        spans = [m for m in chunk["mentions"] if m["entity_id"] == alice_node["id"]]
        assert spans
        for span in spans:
            assert chunk["text"][span["start"] : span["end"]].lower().startswith("alice")
    by_doc = client.get(
        f"/api/corpora/{slug}/chunks", params={"document_id": documents[1]["id"], "page_size": 200}
    ).json()
    assert by_doc["total"] == documents[1]["n_chunks"]
    assert all(c["document_id"] == documents[1]["id"] for c in by_doc["items"])
    both = client.get(
        f"/api/corpora/{slug}/chunks",
        params={"document_id": documents[1]["id"], "entity_id": alice_node["id"]},
    ).json()
    assert 0 < both["total"] <= by_doc["total"]
    single = client.get(f"/api/corpora/{slug}/chunks/{page['items'][0]['id']}").json()
    assert single["id"] == page["items"][0]["id"]


def test_entity_lookup(client, alice):
    slug = alice["slug"]
    hits = client.get(f"/api/corpora/{slug}/entities", params={"q": "ALICE", "limit": 5}).json()
    assert hits and hits[0]["text"] == "Alice"
    labelled = client.get(
        f"/api/corpora/{slug}/entities", params={"label": "Entity", "limit": 3}
    ).json()
    assert len(labelled) == 3 and all(e["label"] == "Entity" for e in labelled)
    assert client.get(f"/api/corpora/{slug}/entities", params={"label": "Nope"}).json() == []
