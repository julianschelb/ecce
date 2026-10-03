"""Merge the different names one entity has within a book (alias resolution).

NER output names the same person in many ways: "Prince Andrew", "Andrew", "ANDREW" (a speaker
label), "Pierre" tagged once as PERSON and once as ORG, "Clodius" next to "Publius Clodius".
The implicit network keys entities by ``(name, label)``, so each variant becomes its own node.
This module resolves the variants of one book before the network is built:

1. **Clean spans**: trim lower-case words, quotes and possessives at the edges
   ("Andrew understood" -> "Andrew"), drop spans with digits or "and", and drop the speaker
   labels of plays ("LORD GORING." at the start of a line), which are not mentions.
2. **Comparison key**: case- and accent-folded, titles removed but their gender kept (a title
   right before the span counts too: NER tags "Robert Chiltern" in "Sir Robert Chiltern")
   ("Lady Chiltern" is never merged with "Robert Chiltern").
3. **Short forms** (people only): a one-word name joins the longer name that contains it when that name is
   the only compatible one, or clearly dominant (three times as frequent as the next). A
   different first name or praenomen means a different person ("Gaius Clodius" stays apart
   from "Publius Clodius"); genuinely ambiguous short forms stay separate.
4. **Label vote**: the merged entity takes its most frequent label.

The result maps every mention to a canonical key, label and display name; nothing is merged
across books. Precision over recall: a missed merge is better than a wrong one.
"""

from __future__ import annotations

import dataclasses
import unicodedata
from collections import Counter, defaultdict
from collections.abc import Callable, Iterable
from dataclasses import dataclass, field
from typing import Any

MALE_TITLES = {
    "mr", "sir", "lord", "prince", "count", "baron", "duke", "king", "emperor", "monsieur",
    "herr", "signor", "don", "father", "uncle", "brother", "master", "general", "colonel",
    "captain", "major", "admiral", "abbe", "abbé", "earl", "marquis", "squire",
}  # fmt: skip
FEMALE_TITLES = {
    "mrs", "miss", "ms", "lady", "madame", "mme", "mademoiselle", "mlle", "princess",
    "countess", "baroness", "duchess", "queen", "empress", "frau", "fraulein", "signora",
    "dona", "mother", "aunt", "sister", "mistress", "marchioness",
}  # fmt: skip
NEUTRAL_TITLES = {
    "dr",
    "doctor",
    "professor",
    "saint",
    "st",
    "old",
    "young",
    "little",
    "dear",
    "poor",
    "the",
}
TITLES = MALE_TITLES | FEMALE_TITLES | NEUTRAL_TITLES
# lower-case words allowed inside a name ("Charles de Gaulle", "Duke of York")
PARTICLES = {
    "de",
    "da",
    "di",
    "del",
    "della",
    "von",
    "van",
    "der",
    "du",
    "des",
    "le",
    "la",
    "of",
    "y",
    "d",
    "ibn",
    "bin",
}
DOMINANCE = (
    3.0  # a short form joins the most frequent candidate if it is this many times more frequent
)
PRONOUNS = {
    "i", "me", "my", "you", "your", "he", "him", "his", "she", "her", "it", "its", "we", "us",
    "our", "they", "them", "their", "thou", "thee", "thy", "ye", "who", "whom", "one",
}  # fmt: skip
# stage directions that NER includes in a span ("Exit PHIPPS")
STAGE_WORDS = {"exit", "exeunt", "enter", "re-enter", "manet", "manent"}
_EDGE_JUNK = "\"'“”‘’«»()[]{}.,;:!?—–-_*"


def fold(text: str) -> str:
    """Lower-case, accents removed: "Bolkónski" -> "bolkonski"."""
    text = unicodedata.normalize("NFKD", text)
    return "".join(c for c in text if not unicodedata.combining(c)).lower()


def clean_surface(text: str) -> str | None:
    """Trim a mention to the name itself, or ``None`` when it is not a usable name."""
    text = " ".join(text.split())
    for dash in ("—", "–", "“", "”"):
        if dash in text:  # 'herself—“Stepan Arkadyevitch' -> the part with capitals
            parts = [p for p in text.split(dash) if any(ch.isupper() for ch in p)]
            text = parts[-1] if parts else text
    text = text.strip(_EDGE_JUNK + " ")
    for possessive in ("’s", "'s", "’", "'"):
        if text.endswith(possessive):
            text = text[: -len(possessive)]
    words = text.split()
    while words and (not words[0][:1].isupper() or words[0].lower() in STAGE_WORDS):
        words.pop(0)
    while words and not words[-1][:1].isupper():
        words.pop()
    if not words or any(ch.isdigit() for ch in text) or len(words) > 6:
        return None
    if any(w.lower() == "and" for w in words):
        return None
    if len(words) == 1 and words[0].lower() in PRONOUNS:  # GLiNER tags "He", "You"
        return None
    inner = [w for w in words[1:-1] if not w[:1].isupper() and w.lower() not in PARTICLES]
    if inner:
        return None
    name = " ".join(words).strip(_EDGE_JUNK)
    for possessive in ("’s", "'s"):  # "Scrooge's nephew" -> "Scrooge's" -> "Scrooge"
        name = name.removesuffix(possessive)
    if len(name) < 2:
        return None
    if name.isupper() and len(name) > 3:  # "ROBERT CHILTERN" -> "Robert Chiltern"
        name = " ".join(w.capitalize() for w in name.split())
    return name


def is_speaker_label(text: str, start: int, end: int) -> bool:
    """A play's speaker attribution: an all-caps name at the start of a line, before a full stop.

    The span may lack the title in front ("MRS. CHEVELEY." tagged as "CHEVELEY").
    """
    surface = text[start:end]
    if not surface.isupper() or len(surface) < 3:
        return False
    line_start = text.rfind("\n", 0, start) + 1
    prefix = text[line_start:start]
    if prefix.strip() and not (prefix.isupper() and len(prefix.split()) <= 2):
        return False
    return text[end : end + 1] in {".", ":"}


def preceding_title(text: str, start: int) -> str | None:
    """A gendered title right before a span ("Sir" in "Sir Robert Chiltern"); NER leaves it out."""
    before = text[max(0, start - 16) : start]
    if not before.endswith(" "):
        return None
    words = before.split()
    word = words[-1] if words else ""
    folded = fold(word).strip(".")
    if word[:1].isupper() and (folded in MALE_TITLES or folded in FEMALE_TITLES):
        return word
    return None


def is_person(label: str) -> bool:
    """PERSON, PER, PERSON_MYTH, person: short forms are only resolved for people."""
    return label.upper().startswith("PER")


@dataclass
class _Variant:
    key: tuple[str, ...]  # folded name words without titles
    gender: str | None  # "m", "f" or None
    count: int = 0
    labels: Counter[str] = field(default_factory=Counter)
    surfaces: Counter[str] = field(default_factory=Counter)  # as written (for the mapping)
    forms: Counter[str] = field(default_factory=Counter)  # as displayed (lemma for Latin)


def split_title(name: str) -> tuple[tuple[str, ...], str | None]:
    """("Lady", "Chiltern") -> (("chiltern",), "f"); titles are removed from the key."""
    words = [fold(w).strip(".") for w in name.split()]
    gender = None
    while len(words) > 1 and words[0] in TITLES:
        if words[0] in MALE_TITLES:
            gender = "m"
        elif words[0] in FEMALE_TITLES:
            gender = "f"
        words.pop(0)
    return tuple(w for w in words if w), gender


@dataclass
class AliasResolver:
    """Built from all mentions of one book; maps a surface form to its merged entity."""

    canonical: dict[str, str]  # cleaned surface -> canonical key
    label: dict[str, str]  # canonical key -> majority label
    display: dict[str, str]  # canonical key -> display name

    def __call__(self, surface: str) -> str:
        """Network normaliser: the canonical key of a (cleaned) surface form."""
        return self.canonical.get(surface, fold(surface))


def build_resolver(
    mentions: Iterable[tuple[str, str]], base: Callable[[str], str] | None = None
) -> AliasResolver:
    """Resolve aliases from ``(cleaned surface, label)`` pairs of one book.

    ``base`` turns a surface into the form the key is built from (the Latin lemma, for one).
    """
    variants: dict[tuple[tuple[str, ...], str | None], _Variant] = {}
    surface_variant: dict[str, tuple[tuple[str, ...], str | None]] = {}
    for surface, label in mentions:
        source = base(surface) if base else surface
        key, gender = split_title(source)
        if not key:
            continue
        ident = (key, gender)
        variant = variants.setdefault(ident, _Variant(key, gender))
        variant.count += 1
        variant.labels[label] += 1
        variant.surfaces[surface] += 1
        variant.forms[source] += 1
        surface_variant[surface] = ident

    # 1. variants with the same words and compatible genders form one group
    #    ("Prince Andrew" + "Andrew"; "Lady Chiltern" stays apart from "Sir Robert Chiltern")
    by_key: dict[tuple[str, ...], list[_Variant]] = defaultdict(list)
    for variant in variants.values():
        by_key[variant.key].append(variant)
    group_of: dict[tuple[tuple[str, ...], str | None], tuple[tuple[str, ...], str | None]] = {}
    for key, members in by_key.items():
        genders = {v.gender for v in members if v.gender}
        for v in members:
            # a title-less form joins the gendered group only when there is just one gender
            target = v.gender or (next(iter(genders)) if len(genders) == 1 else None)
            group_of[(v.key, v.gender)] = (key, target)

    totals: Counter[tuple[tuple[str, ...], str | None]] = Counter()
    group_labels: dict[tuple[tuple[str, ...], str | None], Counter[str]] = defaultdict(Counter)
    for ident, variant in variants.items():
        totals[group_of[ident]] += variant.count
        group_labels[group_of[ident]].update(variant.labels)
    people = {g for g, votes in group_labels.items() if is_person(votes.most_common(1)[0][0])}

    # a full name without a title takes the gender its first name has with one
    # ("Robert Chiltern" is male because the book says "Sir Robert")
    first_name_gender: dict[str, set[str]] = defaultdict(set)
    for key, gender in totals:
        if len(key) == 1 and gender:
            first_name_gender[key[0]].add(gender)
    gender_of: dict[tuple[tuple[str, ...], str | None], str | None] = {}
    for key, gender in totals:
        inferred = first_name_gender.get(key[0], set()) if len(key) > 1 else set()
        gender_of[(key, gender)] = gender or (next(iter(inferred)) if len(inferred) == 1 else None)

    # 2. short forms join a unique or clearly dominant longer name containing them
    def compatible(a: str | None, b: str | None) -> bool:
        return a is None or b is None or a == b

    Group = tuple[tuple[str, ...], str | None]
    parent: dict[Group, Group] = {}
    groups = list(totals)

    def root(group: Group) -> Group:
        seen = set()
        while group in parent and group not in seen:
            seen.add(group)
            group = parent[group]
        return group

    def attach(group: Group, candidates: list[Group], weight: Counter[Group]) -> None:
        ranked = sorted(set(candidates), key=lambda c: -weight[c])
        if ranked and (len(ranked) == 1 or weight[ranked[0]] >= DOMINANCE * weight[ranked[1]]):
            parent[group] = ranked[0]

    # 2a. multi-word names join a longer form of the same name: same first and last word
    #     ("Konstantin Levin" -> "Konstantin Dmitrievitch Levin") or extended at the end
    #     ("Anna Arkadyevna" -> "Anna Arkadyevna Karenina"); a different first name or
    #     praenomen is a different person
    persons = [g for g in groups if g in people]
    for group in sorted((g for g in persons if len(g[0]) > 1), key=lambda g: len(g[0])):
        key = group[0]
        attach(
            group,
            [
                other
                for other in persons
                if len(other[0]) > len(key)
                and compatible(gender_of[group], gender_of[other])
                and (
                    other[0][: len(key)] == key
                    or (other[0][0] == key[0] and other[0][-1] == key[-1])
                )
            ],
            totals,
        )
    # 2b. one-word names join the merged multi-word name that contains them, if it is the only
    #     compatible one or clearly dominant (weighed with all its merged forms)
    merged_totals: Counter[Group] = Counter()
    for group in groups:
        merged_totals[root(group)] += totals[group]
    for group in (g for g in persons if len(g[0]) == 1):
        key = group[0]
        attach(
            group,
            [
                root(other)
                for other in persons
                if len(other[0]) > 1
                and key[0] in other[0]
                and compatible(gender_of[group], gender_of[other])
            ],
            merged_totals,
        )

    # 3. canonical key, majority label and display name per merged entity
    merged: dict[tuple[tuple[str, ...], str | None], list[_Variant]] = defaultdict(list)
    for ident, variant in variants.items():
        merged[root(group_of[ident])].append(variant)
    canonical: dict[str, str] = {}
    labels: dict[str, str] = {}
    display: dict[str, str] = {}
    for (key, gender), group_variants in merged.items():
        canon = " ".join(key) + (f"#{gender}" if gender else "")
        label_votes: Counter[str] = Counter()
        surfaces: Counter[str] = Counter()
        for v in group_variants:
            label_votes.update(v.labels)
            surfaces.update(v.forms)
        labels[canon] = label_votes.most_common(1)[0][0]
        # the most frequent multi-word form reads best ("Anna Arkadyevna", "Gnaeus Pompeius")
        full = [s for s, _ in surfaces.most_common() if len(s.split()) > 1 and not _is_titled(s)]
        display[canon] = full[0] if full else surfaces.most_common(1)[0][0]
        for v in group_variants:
            for surface in v.surfaces:
                canonical[surface] = canon
    return AliasResolver(canonical=canonical, label=labels, display=display)


def _is_titled(surface: str) -> bool:
    return fold(surface.split()[0]).strip(".") in TITLES


def resolve_aliases(
    documents: list[Any], base: Callable[[str], str] | None = None
) -> tuple[list[Any], AliasResolver]:
    """Clean the mentions of a book's annotated documents and merge their aliases.

    Drops speaker labels and unusable spans, trims the rest to the name (adjusting the offsets),
    builds the resolver and gives every mention the label of its merged entity.
    """
    cleaned_docs = []
    for document in documents:
        text = document.text
        kept = []
        for mention in document.mentions:
            if is_speaker_label(text, mention.start, mention.end):
                continue
            name = clean_surface(mention.text)
            if name is None:
                continue
            offset = text[mention.start : mention.end].lower().find(name.lower())
            start = mention.start + offset if offset >= 0 else mention.start
            end = start + len(name) if offset >= 0 else mention.end
            title = preceding_title(text, start) if is_person(mention.label) else None
            if title and not _is_titled(name):  # keep the gender: "Sir" + "Robert Chiltern"
                start = text.rfind(title, 0, start)
                name = f"{title.capitalize() if title.isupper() else title} {name}"
            kept.append(dataclasses.replace(mention, text=name, start=start, end=end))
        document.mentions = kept
        cleaned_docs.append(document)
    resolver = build_resolver(
        ((m.text, m.label) for d in cleaned_docs for m in d.mentions), base=base
    )
    for document in cleaned_docs:
        document.mentions = [
            dataclasses.replace(m, label=resolver.label.get(resolver(m.text), m.label))
            for m in document.mentions
        ]
    return cleaned_docs, resolver
