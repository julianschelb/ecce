"""Typed relations between entities, used to name the edges of the network (experimental).

GLiNER2 proposes relations per text window (:class:`Relation`, head and tail as character
spans). Zero-shot relation scores are poorly calibrated on literary text: the model tends to
fire every type for a pair of characters ("Scrooge friend of / loves / married to Marley").
Aggregation therefore:

1. maps head and tail to the merged entities of the book (mentions overlapping the spans);
2. drops types that do not fit the entity kinds (a place is not "married to" anyone);
3. keeps the single best-scoring type per entity pair and window;
4. ranks the types of a pair by support and *lift* (how much more often the type is seen for
   this pair than in the whole book) and keeps those seen at least ``MIN_SUPPORT`` times.
"""

from __future__ import annotations

import bisect
import json
from collections import Counter
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

# relation type -> description given to the model; direction reads "head <type> tail"
RELATION_TYPES = {
    "married to": "is the husband or wife of",
    "parent of": "is the father or mother of",
    "sibling of": "is the brother or sister of",
    "loves": "is in love with",
    "friend of": "is a friend of",
    "enemy of": "is an enemy or rival of",
    "fights": "fights, attacks or kills",
    "serves": "serves, works for or obeys",
    "works with": "is a colleague or business partner of",
    "rules": "rules, commands or governs",
    "member of": "belongs to a group or organization",
    "lives in": "lives in or comes from a place",
    "travels to": "goes, travels or sails to a place",
}
PERSON, GROUP, PLACE = "person", "group", "place"
KINDS = {
    "PERSON": PERSON,
    "PER": PERSON,
    "PERSON_MYTH": PERSON,
    "ORG": GROUP,
    "NORP": GROUP,
    "GRP": GROUP,
    "LOC": PLACE,
    "GPE": PLACE,
    "FAC": PLACE,
}
_SOCIAL = {(PERSON, PERSON)}
SIGNATURES: dict[str, set[tuple[str, str]]] = {
    "married to": _SOCIAL,
    "parent of": _SOCIAL,
    "sibling of": _SOCIAL,
    "loves": _SOCIAL,
    "friend of": _SOCIAL,
    "works with": _SOCIAL,
    "enemy of": _SOCIAL | {(PERSON, GROUP), (GROUP, PERSON), (GROUP, GROUP)},
    "fights": _SOCIAL | {(PERSON, GROUP), (GROUP, PERSON), (GROUP, GROUP)},
    "serves": _SOCIAL | {(PERSON, GROUP)},
    "rules": _SOCIAL | {(PERSON, GROUP), (PERSON, PLACE), (GROUP, PLACE)},
    "member of": {(PERSON, GROUP)},
    "lives in": {(PERSON, PLACE), (GROUP, PLACE)},
    "travels to": {(PERSON, PLACE), (GROUP, PLACE)},
}
MIN_SUPPORT = 2  # windows in which a type must be the best one for a pair


@dataclass(frozen=True)
class Relation:
    """A typed relation between two spans of a document (character offsets)."""

    label: str
    head: tuple[int, int]
    tail: tuple[int, int]
    score: float
    window: int = 0  # index of the text window it was found in


def _mention_at(mentions: list[Any], starts: list[int], span: tuple[int, int]) -> Any | None:
    """The last mention that overlaps a character span, if any."""
    k = bisect.bisect_right(starts, span[1] - 1) - 1  # last mention starting before the end
    return mentions[k] if k >= 0 and mentions[k].end > span[0] else None


def fits(label: str, head_label: str, tail_label: str) -> bool:
    """Whether a relation type fits the kinds of its two entities."""
    kinds = (KINDS.get(head_label.upper()), KINDS.get(tail_label.upper()))
    return kinds in SIGNATURES.get(label, set())


def aggregate_relations(
    annotated: list[Any],
    found: dict[str, list[Relation]] | None,
    entity_of: Callable[[Any], int | None],
    label_of: Callable[[int], str],
) -> dict[tuple[int, int], list[tuple[str, int, bool]]]:
    """Ranked relation types per entity pair ``(a, b)`` with ``a < b``.

    ``entity_of`` maps a mention to its entity id, ``label_of`` an entity id to its label.
    Each value lists ``(type, support, head is a)``, best first.
    """
    if not found:
        return {}
    best: dict[tuple[int, int, int, int], tuple[float, str, bool]] = {}
    for d, document in enumerate(annotated):
        mentions = sorted(document.mentions, key=lambda m: m.start)
        starts = [m.start for m in mentions]
        for relation in found.get(document.text, []):
            head_mention = _mention_at(mentions, starts, relation.head)
            tail_mention = _mention_at(mentions, starts, relation.tail)
            head = entity_of(head_mention) if head_mention else None
            tail = entity_of(tail_mention) if tail_mention else None
            if head is None or tail is None or head == tail:
                continue
            if not fits(relation.label, label_of(head), label_of(tail)):
                continue
            a, b = min(head, tail), max(head, tail)
            key = (d, relation.window, a, b)
            if key not in best or relation.score > best[key][0]:
                best[key] = (relation.score, relation.label, head == a)

    counts: dict[tuple[int, int], Counter[tuple[str, bool]]] = {}
    for (_, _, a, b), (_, label, forward) in best.items():
        counts.setdefault((a, b), Counter())[(label, forward)] += 1
    type_total: Counter[str] = Counter()
    for pair_counts in counts.values():
        for (label, _), n in pair_counts.items():
            type_total[label] += n
    total = sum(type_total.values())

    result: dict[tuple[int, int], list[tuple[str, int, bool]]] = {}
    for pair, pair_counts in counts.items():
        pair_total = sum(pair_counts.values())
        ranked = []
        for (label, forward), n in pair_counts.items():
            lift = (n / pair_total) / (type_total[label] / total)
            if n >= MIN_SUPPORT:
                ranked.append((n * lift, label, n, forward))
        ranked.sort(reverse=True)
        if ranked:
            result[pair] = [(label, n, forward) for _, label, n, forward in ranked]
    return result


def relation_json(ranked: list[tuple[str, int, bool]] | None, flip: bool = False) -> str:
    """``[[type, support, head is the edge's source], ...]`` best first ("" without any)."""
    if not ranked:
        return ""
    return json.dumps([[label, n, forward != flip] for label, n, forward in ranked])
