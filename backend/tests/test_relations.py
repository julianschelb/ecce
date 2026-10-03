"""Aggregating typed relations onto entity pairs."""

from __future__ import annotations

import json
from dataclasses import dataclass, field

from app.services.relations import Relation, aggregate_relations, fits, relation_json


@dataclass
class M:
    text: str
    label: str
    start: int
    end: int


@dataclass
class Doc:
    text: str
    mentions: list[M] = field(default_factory=list)


def test_types_must_fit_the_entity_kinds():
    assert fits("married to", "PERSON", "PERSON")
    assert not fits("married to", "PERSON", "GPE")
    assert fits("lives in", "PERSON", "LOC")
    assert not fits("lives in", "LOC", "PERSON")


def test_best_type_per_window_and_minimum_support():
    text = "Bob and Tim went to London."
    doc = Doc(
        text, [M("Bob", "PERSON", 0, 3), M("Tim", "PERSON", 8, 11), M("London", "GPE", 20, 26)]
    )
    ids = {"Bob": 0, "Tim": 1, "London": 2}
    labels = {0: "PERSON", 1: "PERSON", 2: "GPE"}
    bob, tim, london = (0, 3), (8, 11), (20, 26)
    found = {
        text: [
            # window 0: "parent of" beats "loves"; window 1 and 2: "parent of" again
            Relation("parent of", bob, tim, 0.9, 0),
            Relation("loves", bob, tim, 0.8, 0),
            Relation("parent of", bob, tim, 0.7, 1),
            Relation("parent of", bob, tim, 0.7, 2),
            Relation("loves", tim, bob, 0.6, 3),  # seen once: below the support threshold
            Relation("married to", bob, london, 0.99, 0),  # does not fit
            Relation("travels to", bob, london, 0.5, 0),
            Relation("travels to", bob, london, 0.5, 1),
        ]
    }
    result = aggregate_relations([doc], found, lambda m: ids[m.text], labels.__getitem__)
    assert result[(0, 1)] == [("parent of", 3, True)]
    assert result[(0, 2)] == [("travels to", 2, True)]
    # stored for an edge whose source is Tim: the head (Bob) is the target
    assert json.loads(relation_json(result[(0, 1)], flip=True)) == [["parent of", 3, False]]
