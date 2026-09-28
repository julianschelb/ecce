"""Graph construction, edge-weight pruning and graph queries."""

from __future__ import annotations

import math

import numpy as np
from app.services.chunking import chunk_document, split_documents
from app.services.graph import GraphCache


def test_documents_are_split_at_chapters(alice):
    assert alice["n_documents"] == 3
    assert alice["n_chunks"] > 100
    assert alice["n_entities"] > 20
    assert alice["n_edges"] > 20
    assert alice["extractor"] == "rule"


def test_graph_contains_expected_entities(client, alice):
    graph = client.get(f"/api/corpora/{alice['slug']}/graph", params={"max_nodes": 50}).json()
    names = {node["text"] for node in graph["nodes"]}
    assert "Alice" in names
    assert graph["nodes"][0]["text"] == "Alice"  # strongest node first
    ids = {node["id"] for node in graph["nodes"]}
    assert all(edge["source"] in ids and edge["target"] in ids for edge in graph["edges"])
    assert all(edge["weight"] > 0 and edge["count"] >= 1 for edge in graph["edges"])
    assert graph["total_nodes"] >= len(graph["nodes"])
    assert graph["max_weight"] >= max(edge["weight"] for edge in graph["edges"])


def test_edge_weights_follow_the_ien_definition(client, alice):
    """ω = Σ exp(−δ): counts and weights must be consistent and bounded."""
    graph = client.get(f"/api/corpora/{alice['slug']}/graph", params={"max_nodes": 500}).json()
    for edge in graph["edges"]:
        # each cooccurrence contributes at most 1 (δ = 0) and at least exp(−window)
        assert edge["weight"] <= edge["count"] + 1e-9
        assert edge["weight"] >= edge["count"] * math.exp(-alice["window"]) - 1e-9


def test_min_weight_pruning_is_monotonic(client, alice):
    slug = alice["slug"]
    counts = []
    for min_weight in (0.0, 0.5, 1.0, 2.0, 5.0):
        graph = client.get(
            f"/api/corpora/{slug}/graph", params={"min_weight": min_weight, "max_nodes": 500}
        ).json()
        assert all(edge["weight"] >= min_weight for edge in graph["edges"])
        counts.append((graph["total_edges"], graph["total_nodes"]))
    assert counts == sorted(counts, reverse=True)
    assert counts[0][0] == alice["n_edges"]


def test_max_nodes_keeps_strongest(client, alice):
    slug = alice["slug"]
    small = client.get(f"/api/corpora/{slug}/graph", params={"max_nodes": 5}).json()
    large = client.get(f"/api/corpora/{slug}/graph", params={"max_nodes": 50}).json()
    assert len(small["nodes"]) == 5 and len(large["nodes"]) == 50
    assert [n["id"] for n in small["nodes"]] == [n["id"] for n in large["nodes"][:5]]
    strengths = [n["strength"] for n in large["nodes"]]
    assert strengths == sorted(strengths, reverse=True)


def test_focus_returns_ego_network(client, alice):
    slug = alice["slug"]
    alice_node = client.get(f"/api/corpora/{slug}/entities", params={"q": "alice"}).json()[0]
    ego = client.get(
        f"/api/corpora/{slug}/graph", params={"focus": alice_node["id"], "max_nodes": 30}
    ).json()
    ids = {n["id"] for n in ego["nodes"]}
    assert alice_node["id"] in ids
    assert all(edge["source"] in ids and edge["target"] in ids for edge in ego["edges"])
    touching = [e for e in ego["edges"] if alice_node["id"] in (e["source"], e["target"])]
    assert touching


def test_entity_detail_and_edge_provenance(client, alice):
    slug = alice["slug"]
    alice_node = client.get(f"/api/corpora/{slug}/entities", params={"q": "alice"}).json()[0]
    detail = client.get(f"/api/corpora/{slug}/entities/{alice_node['id']}").json()
    assert detail["count"] >= 50 and detail["n_chunks"] >= 20
    assert (
        detail["neighbors"]
        and detail["neighbors"][0]["weight"] >= detail["neighbors"][-1]["weight"]
    )
    neighbour = detail["neighbors"][0]
    edge = client.get(
        f"/api/corpora/{slug}/edges/{alice_node['id']}/{neighbour['entity']['id']}"
    ).json()
    assert edge["weight"] == neighbour["weight"] and edge["count"] == neighbour["count"]
    assert edge["chunks"], "provenance chunks expected"
    for chunk in edge["chunks"]:
        mentioned = {m["entity_id"] for m in chunk["mentions"]}
        assert {alice_node["id"], neighbour["entity"]["id"]} <= mentioned
    assert (
        client.get(f"/api/corpora/{slug}/edges/{alice_node['id']}/{alice_node['id']}").status_code
        == 404
    )
    assert client.get(f"/api/corpora/{slug}/entities/999999").status_code == 404


def test_graph_cache_subgraph_is_consistent():
    ids = np.array([10, 11, 12, 13])
    cache = GraphCache(
        corpus_id=1,
        ids=ids,
        texts=["a", "b", "c", "d"],
        labels=["X", "X", "Y", "Y"],
        counts=np.array([5, 4, 3, 1]),
        degree=np.array([2, 2, 1, 1]),
        strength=np.array([3.0, 2.5, 1.5, 1.0]),
        src=np.array([0, 0, 1]),
        tgt=np.array([1, 2, 3]),
        weight=np.array([2.0, 1.0, 0.5]),
        count=np.array([2, 1, 1]),
    )
    view = cache.subgraph(min_weight=0.6, max_nodes=10)
    assert {(e["source"], e["target"]) for e in view["edges"]} == {(10, 11), (10, 12)}
    assert [n["id"] for n in view["nodes"]] == [10, 11, 12]
    assert cache.subgraph(labels={"X"})["edges"] == [
        {"source": 10, "target": 11, "weight": 2.0, "count": 2}
    ]
    assert cache.edge(11, 13) == (0.5, 1) and cache.edge(12, 13) is None
    assert [n["entity"]["id"] for n in cache.neighbors(10)] == [11, 12]
    assert cache.subgraph(focus=13)["nodes"][0]["id"] in (11, 13)


def test_chunking_offsets_are_exact():
    text = "First paragraph here.\n\nSecond one. " + "Word " * 400 + "end.\n\n\nThird."
    spans = chunk_document(text, max_words=100)
    assert [text[s.start : s.end] for s in spans][0] == "First paragraph here."
    assert all(text[s.start : s.end].strip() == text[s.start : s.end] for s in spans)
    assert len(spans) > 3
    parts = split_documents(
        "Intro\n\nCHAPTER I.\nThe Start\n\nBody one.\n\nCHAPTER II.\n\nBody two.", "auto"
    )
    assert [p.title for p in parts] == ["Preface", "CHAPTER I. The Start", "CHAPTER II."]
    assert split_documents("no headings here", "auto", default_title="T")[0].title == "T"
