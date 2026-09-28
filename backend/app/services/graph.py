"""In-memory graph representation for sub-second graph queries."""

from __future__ import annotations

import threading
from dataclasses import dataclass
from typing import Any

import numpy as np
from sqlalchemy.engine import Engine
from sqlmodel import Session, select

from app.models.entities import Edge, Entity


@dataclass
class GraphCache:
    """Column-oriented copy of one corpus' entity graph."""

    corpus_id: int
    ids: np.ndarray  # entity ids
    texts: list[str]
    labels: list[str]
    counts: np.ndarray
    degree: np.ndarray
    strength: np.ndarray
    src: np.ndarray  # edge endpoints as *positions* into the entity arrays
    tgt: np.ndarray
    weight: np.ndarray
    count: np.ndarray

    def __post_init__(self) -> None:
        self._pos = {int(i): p for p, i in enumerate(self.ids.tolist())}

    # ---------- helpers

    def position(self, entity_id: int) -> int | None:
        return self._pos.get(int(entity_id))

    @property
    def max_weight(self) -> float:
        return float(self.weight.max()) if self.weight.size else 0.0

    @property
    def max_strength(self) -> float:
        return float(self.strength.max()) if self.strength.size else 0.0

    def node(self, position: int) -> dict[str, Any]:
        return {
            "id": int(self.ids[position]),
            "text": self.texts[position],
            "label": self.labels[position],
            "count": int(self.counts[position]),
            "degree": int(self.degree[position]),
            "strength": float(self.strength[position]),
        }

    # ---------- queries

    def subgraph(
        self,
        *,
        min_weight: float = 0.0,
        max_nodes: int = 150,
        labels: set[str] | None = None,
        focus: int | None = None,
    ) -> dict[str, Any]:
        """Filtered view: edges above ``min_weight``, top ``max_nodes`` by strength."""
        keep = self.weight >= min_weight
        if labels:
            allowed = np.array([lbl in labels for lbl in self.labels], dtype=bool)
            keep &= allowed[self.src] & allowed[self.tgt]
        if focus is not None:
            fpos = self.position(focus)
            if fpos is None:
                keep[:] = False
            else:
                touching = keep & ((self.src == fpos) | (self.tgt == fpos))
                ego = set(self.src[touching].tolist()) | set(self.tgt[touching].tolist()) | {fpos}
                member = np.zeros(len(self.ids), dtype=bool)
                member[list(ego)] = True
                keep &= member[self.src] & member[self.tgt]
        src, tgt, weight, count = (
            self.src[keep],
            self.tgt[keep],
            self.weight[keep],
            self.count[keep],
        )
        total_edges = int(src.size)
        strength = np.bincount(src, weights=weight, minlength=len(self.ids)) + np.bincount(
            tgt, weights=weight, minlength=len(self.ids)
        )
        candidates = np.flatnonzero(strength > 0)
        if (
            focus is not None
            and (fpos := self.position(focus)) is not None
            and fpos not in candidates
        ):
            candidates = np.append(candidates, fpos)
        total_nodes = int(candidates.size)
        order = candidates[np.argsort(-strength[candidates], kind="stable")][: max(max_nodes, 1)]
        if focus is not None and (fpos := self.position(focus)) is not None and fpos not in order:
            order = np.append(order[:-1], fpos)
        chosen = np.zeros(len(self.ids), dtype=bool)
        chosen[order] = True
        edge_mask = chosen[src] & chosen[tgt]
        nodes = [self.node(int(p)) for p in order]
        edges = [
            {
                "source": int(self.ids[s]),
                "target": int(self.ids[t]),
                "weight": float(w),
                "count": int(c),
            }
            for s, t, w, c in zip(
                src[edge_mask], tgt[edge_mask], weight[edge_mask], count[edge_mask]
            )
        ]
        return {
            "nodes": nodes,
            "edges": edges,
            "total_nodes": total_nodes,
            "total_edges": total_edges,
            "min_weight": float(min_weight),
            "max_weight": self.max_weight,
            "max_strength": self.max_strength,
        }

    def neighbors(self, entity_id: int, *, k: int | None = 25) -> list[dict[str, Any]]:
        pos = self.position(entity_id)
        if pos is None:
            return []
        as_src = self.src == pos
        as_tgt = self.tgt == pos
        others = np.concatenate([self.tgt[as_src], self.src[as_tgt]])
        weights = np.concatenate([self.weight[as_src], self.weight[as_tgt]])
        counts = np.concatenate([self.count[as_src], self.count[as_tgt]])
        order = np.argsort(-weights, kind="stable")
        if k is not None:
            order = order[:k]
        return [
            {
                "entity": self.node(int(others[i])),
                "weight": float(weights[i]),
                "count": int(counts[i]),
            }
            for i in order
        ]

    def edge(self, a: int, b: int) -> tuple[float, int] | None:
        pa, pb = self.position(a), self.position(b)
        if pa is None or pb is None:
            return None
        lo, hi = min(pa, pb), max(pa, pb)
        hit = np.flatnonzero((self.src == lo) & (self.tgt == hi))
        if hit.size == 0:
            return None
        return float(self.weight[hit[0]]), int(self.count[hit[0]])


def load_graph(session: Session, corpus_id: int) -> GraphCache:
    """Build a :class:`GraphCache` from the database rows of a corpus."""
    entities = session.exec(
        select(Entity).where(Entity.corpus_id == corpus_id).order_by(Entity.id)
    ).all()
    ids = np.array([e.id for e in entities], dtype=np.int64)
    pos = {int(i): p for p, i in enumerate(ids.tolist())}
    edges = session.exec(select(Edge).where(Edge.corpus_id == corpus_id)).all()
    src = np.array([pos[e.source_id] for e in edges], dtype=np.int64)
    tgt = np.array([pos[e.target_id] for e in edges], dtype=np.int64)
    lo, hi = np.minimum(src, tgt), np.maximum(src, tgt)
    weight = np.array([e.weight for e in edges], dtype=np.float64)
    count = np.array([e.count for e in edges], dtype=np.int64)
    order = np.argsort(-weight, kind="stable")
    return GraphCache(
        corpus_id=corpus_id,
        ids=ids,
        texts=[e.text for e in entities],
        labels=[e.label for e in entities],
        counts=np.array([e.count for e in entities], dtype=np.int64),
        degree=np.array([e.degree for e in entities], dtype=np.int64),
        strength=np.array([e.strength for e in entities], dtype=np.float64),
        src=lo[order],
        tgt=hi[order],
        weight=weight[order],
        count=count[order],
    )


class GraphRegistry:
    """Lazily loaded, thread-safe cache of :class:`GraphCache` objects per corpus."""

    def __init__(self, engine: Engine) -> None:
        self._engine = engine
        self._graphs: dict[int, GraphCache] = {}
        self._lock = threading.Lock()

    def get(self, corpus_id: int) -> GraphCache:
        with self._lock:
            graph = self._graphs.get(corpus_id)
        if graph is None:
            with Session(self._engine) as session:
                graph = load_graph(session, corpus_id)
            with self._lock:
                self._graphs[corpus_id] = graph
        return graph

    def invalidate(self, corpus_id: int | None = None) -> None:
        with self._lock:
            if corpus_id is None:
                self._graphs.clear()
            else:
                self._graphs.pop(corpus_id, None)
