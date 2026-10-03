"""Entity extractors: swappable backends on top of ``implicit_word_network``.

- ``rule``   – dependency-free capitalised-phrase heuristic (always available)
- ``spacy``  – spaCy NER (``pip install ecce-backend[spacy]``)
- ``gliner`` – zero-shot GLiNER (``pip install ecce-backend[gliner]``)
- ``gliner2`` – GLiNER2 / GLiNER 2.5 (Fastino): entities and typed relations in one pass
  (``pip install "gliner2[local]"``, experimental)
"""

from __future__ import annotations

import importlib.util
import logging
import re
from collections.abc import Sequence

from implicit_word_network import EntitySpan, SpanEntityExtractor
from implicit_word_network.annotation import Sentence
from implicit_word_network.extraction import BaseEntityExtractor

from app.core.config import Settings
from app.services.relations import RELATION_TYPES, Relation

log = logging.getLogger(__name__)

_CAP_PHRASE = re.compile(
    r"(?<![\w’'])(?:[A-Z][a-zA-Z’'\-]+)(?:\s+(?:of|the|de|von|van|del|da|di|and|&)\s+[A-Z][a-zA-Z’'\-]+|\s+[A-Z][a-zA-Z’'\-]+)*"
)
_STOP_FIRST = frozenset(
    [
        "a",
        "an",
        "the",
        "and",
        "but",
        "or",
        "so",
        "yet",
        "for",
        "nor",
        "of",
        "in",
        "on",
        "at",
        "to",
        "by",
        "with",
        "from",
        "as",
        "if",
        "then",
        "than",
        "that",
        "this",
        "these",
        "those",
        "there",
        "here",
        "it",
        "its",
        "he",
        "she",
        "they",
        "we",
        "you",
        "i",
        "me",
        "my",
        "your",
        "his",
        "her",
        "our",
        "their",
        "what",
        "which",
        "who",
        "whom",
        "whose",
        "when",
        "where",
        "why",
        "how",
        "yes",
        "no",
        "oh",
        "ah",
        "well",
        "now",
        "just",
        "very",
        "not",
        "do",
        "does",
        "did",
        "done",
        "have",
        "has",
        "had",
        "be",
        "been",
        "being",
        "was",
        "were",
        "is",
        "are",
        "am",
        "will",
        "would",
        "shall",
        "should",
        "can",
        "could",
        "may",
        "might",
        "must",
        "let",
        "us",
        "one",
        "two",
        "three",
        "first",
        "last",
        "next",
        "again",
        "all",
        "any",
        "some",
        "such",
        "only",
        "more",
        "most",
        "much",
        "many",
        "little",
        "few",
        "every",
        "each",
        "either",
        "neither",
        "both",
        "another",
        "other",
        "same",
        "own",
        "too",
        "also",
        "still",
        "even",
        "ever",
        "never",
        "once",
        "twice",
        "about",
        "after",
        "before",
        "during",
        "while",
        "until",
        "since",
        "because",
        "though",
        "although",
        "whether",
        "i'm",
        "i’m",
        "i'll",
        "i’ll",
        "i've",
        "i’ve",
        "i'd",
        "i’d”“",
    ]
)


class RuleBasedEntityExtractor(SpanEntityExtractor):
    """Capitalised-phrase heuristic: fast, offline, no models.

    Sequences of capitalised words (optionally joined by *of/the/…*) become
    entities of type ``Entity`` unless they start with a common function word
    or are a sentence-initial single common word. Good enough for demos and
    tests; use spaCy or GLiNER for real corpora.
    """

    label = "Entity"

    def __init__(self, *, min_length: int = 2, segmenter=None) -> None:
        super().__init__(segmenter=segmenter)
        self.min_length = min_length

    def extract_spans(
        self, texts: Sequence[str], sentences: Sequence[Sequence[Sentence]]
    ) -> list[list[EntitySpan]]:
        results: list[list[EntitySpan]] = []
        for text, doc_sentences in zip(texts, sentences):
            starts = {s.start for s in doc_sentences}
            spans: list[EntitySpan] = []
            for match in _CAP_PHRASE.finditer(text):
                surface = match.group(0)
                words = surface.split()
                first = words[0].lower().strip("’'")
                if first in _STOP_FIRST and len(words) == 1:
                    continue
                if first in _STOP_FIRST:
                    # drop the leading function word ("The Queen" -> "Queen")
                    offset = len(words[0]) + 1
                    surface = surface[offset:]
                    start = match.start() + offset
                    if not surface or surface.split()[0].lower() in _STOP_FIRST:
                        continue
                else:
                    start = match.start()
                if (
                    len(words) == 1
                    and match.start() in starts
                    and surface.lower() in _COMMON_SENTENCE_STARTERS
                ):
                    continue
                for possessive in ("’s", "'s"):
                    if surface.endswith(possessive) and len(surface) > len(possessive) + 1:
                        surface = surface[: -len(possessive)]
                if len(surface) < self.min_length or surface.lower() in _STOP_FIRST:
                    continue
                spans.append(EntitySpan(start, start + len(surface), self.label, 1.0, surface))
            results.append(spans)
        return results


_COMMON_SENTENCE_STARTERS = frozenset(
    [
        "however",
        "therefore",
        "meanwhile",
        "perhaps",
        "suddenly",
        "presently",
        "indeed",
        "besides",
        "certainly",
        "poor",
        "come",
    ]
)


class Gliner2EntityExtractor(SpanEntityExtractor):
    """GLiNER2 / GLiNER 2.5: zero-shot entities and, optionally, relations between them.

    Long documents are cut into windows of whole sentences (``window_words`` at most) that are
    sent through the model in batches; entity types and relation types are extracted in the
    same pass. Relations of the last annotated documents are kept in :attr:`relations`, keyed by
    the document text, for the pipeline to attach to the network's edges.
    """

    def __init__(
        self,
        model: str,
        labels: dict[str, str],
        *,
        relation_types: dict[str, str] | None = None,
        threshold: float = 0.5,
        relation_threshold: float = 0.5,
        window_words: int = 220,
        batch_size: int = 8,
        segmenter=None,
    ) -> None:
        super().__init__(segmenter=segmenter)
        from gliner2 import AutoExtractor

        self.model = AutoExtractor.from_pretrained(model)
        self.labels = labels  # model label -> stored label (PERSON, LOC, ...)
        self.relation_types = relation_types or {}
        self.threshold = threshold
        self.relation_threshold = relation_threshold
        self.window_words = window_words
        self.batch_size = batch_size
        self.relations: dict[str, list[Relation]] = {}

    def _windows(self, text: str, sentences: Sequence[Sentence]) -> list[tuple[int, int]]:
        windows: list[tuple[int, int]] = []
        start: int | None = None
        end = words = 0
        for sentence in sentences or [Sentence(0, 0, len(text))]:
            n = len(text[sentence.start : sentence.end].split())
            if start is not None and words + n > self.window_words:
                windows.append((start, end))
                start, words = None, 0
            if start is None:
                start = sentence.start
            end, words = sentence.end, words + n
        if start is not None:
            windows.append((start, end))
        return windows

    def _schema(self):  # noqa: ANN202
        schema = self.model.create_schema().entities(
            {name: GLINER2_LABEL_DESCRIPTIONS.get(name, name) for name in self.labels},
            threshold=self.threshold,
        )
        if self.relation_types:
            schema = schema.relations(self.relation_types, threshold=self.relation_threshold)
        return schema

    def extract_spans(
        self, texts: Sequence[str], sentences: Sequence[Sequence[Sentence]]
    ) -> list[list[EntitySpan]]:
        schema = self._schema()
        results: list[list[EntitySpan]] = []
        for text, doc_sentences in zip(texts, sentences):
            windows = self._windows(text, doc_sentences)
            outputs = self.model.batch_extract(
                [text[a:b] for a, b in windows],
                schema,
                batch_size=self.batch_size,
                threshold=self.threshold,
                include_confidence=True,
                include_spans=True,
            )
            spans: list[EntitySpan] = []
            relations: list[Relation] = []
            for index, ((offset, _), output) in enumerate(zip(windows, outputs)):
                for name, found in (output.get("entities") or {}).items():
                    for e in found:
                        spans.append(
                            EntitySpan(
                                offset + e["start"],
                                offset + e["end"],
                                self.labels.get(name, name),
                                float(e.get("confidence", 1.0)),
                                e["text"],
                            )
                        )
                for name, found in (output.get("relation_extraction") or {}).items():
                    for r in found:
                        head, tail = r["head"], r["tail"]
                        relations.append(
                            Relation(
                                name,
                                (offset + head["start"], offset + head["end"]),
                                (offset + tail["start"], offset + tail["end"]),
                                float(min(head.get("confidence", 1), tail.get("confidence", 1))),
                                index,
                            )
                        )
            spans.sort(key=lambda span: (span.start, -span.end))
            kept: list[EntitySpan] = []
            for span in spans:  # overlapping spans of different types: the first, longest wins
                if kept and span.start < kept[-1].end:
                    continue
                kept.append(span)
            results.append(kept)
            self.relations[text] = relations
        return results


GLINER2_LABEL_DESCRIPTIONS = {
    "person": "a named person or character",
    "location": "a named place: city, country, region, river, mountain or building",
    "organization": "a named organization, institution, company or army",
    "group": "a named people, nationality, tribe, family or religious group",
    "deity": "a god, goddess or mythological figure",
}
GLINER2_LABELS = {
    "person": "PERSON",
    "location": "LOC",
    "organization": "ORG",
    "group": "NORP",
    "deity": "PERSON_MYTH",
}


def available_extractors() -> dict[str, bool]:
    """Which extractor backends are importable."""
    return {
        "rule": True,
        "spacy": importlib.util.find_spec("spacy") is not None,
        "gliner": importlib.util.find_spec("gliner") is not None,
        "gliner2": importlib.util.find_spec("gliner2") is not None,
    }


def resolve_extractor_name(settings: Settings) -> str:
    """Resolve ``auto`` to the best installed backend."""
    name = settings.extractor.lower()
    available = available_extractors()
    if name == "auto":
        if available["spacy"]:
            return "spacy"
        if available["gliner"]:
            return "gliner"
        return "rule"
    if name not in available:
        raise ValueError(f"Unknown extractor {name!r}; choose one of {sorted(available)}")
    if not available[name]:
        log.warning("Extractor %r is not installed, falling back to the rule-based extractor", name)
        return "rule"
    return name


def create_extractor(settings: Settings, name: str | None = None) -> BaseEntityExtractor:
    """Instantiate the configured extractor (lazily loading models)."""
    name = name or resolve_extractor_name(settings)
    if name == "spacy":
        from implicit_word_network import SpacyEntityExtractor

        return SpacyEntityExtractor(
            settings.spacy_model, labels=settings.spacy_labels, max_length=5_000_000
        )
    if name == "gliner":
        from implicit_word_network import GLiNEREntityExtractor

        return GLiNEREntityExtractor(
            settings.gliner_model, labels=settings.gliner_labels, threshold=0.45, device="cpu"
        )
    if name == "gliner2":
        return Gliner2EntityExtractor(
            settings.gliner2_model,
            GLINER2_LABELS,
            relation_types=RELATION_TYPES if settings.relation_types else None,
            threshold=settings.gliner2_threshold,
        )
    return RuleBasedEntityExtractor()
