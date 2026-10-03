"""Alias resolution within a book: cleaning spans, speaker labels and merging names."""

from __future__ import annotations

from app.services.disambiguation import build_resolver, clean_surface, is_speaker_label


def test_clean_surface_trims_to_the_name():
    assert clean_surface("Andrew understood") == "Andrew"
    assert clean_surface("halfpenny Levin") == "Levin"
    assert clean_surface("herself—“Stepan Arkadyevitch") == "Stepan Arkadyevitch"
    assert clean_surface("Goring’s") == "Goring"
    assert clean_surface("Scrooge's nephew") == "Scrooge"
    assert clean_surface("ROBERT CHILTERN") == "Robert Chiltern"
    assert clean_surface("Duke of York") == "Duke of York"
    assert clean_surface("Anna and Vronsky") is None
    assert clean_surface("Fifth Edition May 1912 THE PERSONS") is None


def test_speaker_labels_are_recognised():
    text = "LORD GORING. My dear Robert!\nMABEL CHILTERN. I met LORD GORING today."
    first = text.index("LORD GORING")
    assert is_speaker_label(text, first, first + len("LORD GORING"))
    mabel = text.index("MABEL CHILTERN")
    assert is_speaker_label(text, mabel, mabel + len("MABEL CHILTERN"))
    inline = text.rindex("LORD GORING")
    assert not is_speaker_label(text, inline, inline + len("LORD GORING"))


def resolve(mentions: list[tuple[str, str, int]]):
    pairs = [(text, label) for text, label, n in mentions for _ in range(n)]
    return build_resolver(pairs)


def test_titles_short_forms_and_label_votes_merge():
    r = resolve(
        [
            ("Prince Andrew", "PERSON", 828),
            ("Andrew", "PERSON", 207),
            ("Prince Andrew Bolkónski", "PERSON", 7),
            ("Pierre", "PERSON", 1587),
            ("Pierre", "ORG", 164),
            ("Pierre Bezúkhov", "PERSON", 2),
        ]
    )
    assert r("Andrew") == r("Prince Andrew") == r("Prince Andrew Bolkónski")
    assert r.display[r("Andrew")] == "Prince Andrew"
    assert r("Pierre") == r("Pierre Bezúkhov")
    assert r.label[r("Pierre")] == "PERSON"  # majority label wins
    assert r.display[r("Pierre")] == "Pierre"  # the rare full name is not displayed


def test_gender_and_first_names_keep_people_apart():
    r = resolve(
        [
            ("Sir Robert Chiltern", "PERSON", 20),
            ("Lady Chiltern", "PERSON", 46),
            ("Gertrude Chiltern", "PERSON", 4),
            ("Publius Clodius", "PERSON", 33),
            ("Gaius Clodius", "PERSON", 1),
            ("Clodius", "PERSON", 44),
        ]
    )
    assert r("Lady Chiltern") != r("Sir Robert Chiltern")  # different gender
    assert r("Gaius Clodius") != r("Publius Clodius")  # different praenomen
    assert r("Clodius") == r("Publius Clodius")  # 33 vs 1: clearly dominant


def test_ambiguous_short_forms_stay_separate():
    r = resolve(
        [
            ("Konstantin Levin", "PERSON", 46),
            ("Konstantin Dmitrievitch Levin", "PERSON", 3),
            ("Nikolay Levin", "PERSON", 16),
            ("Levin", "PERSON", 1493),
            ("Nicholas Rostov", "PERSON", 30),
            ("Natasha Rostov", "PERSON", 25),
            ("Rostov", "PERSON", 200),
        ]
    )
    assert r("Konstantin Levin") == r("Konstantin Dmitrievitch Levin")  # same first and last name
    assert r("Levin") == r("Konstantin Levin")  # 49 vs 16
    assert r("Nikolay Levin") != r("Konstantin Levin")
    assert r("Rostov") not in {r("Nicholas Rostov"), r("Natasha Rostov")}  # a family, ambiguous


def test_titles_before_speaker_labels_and_stage_directions():
    text = "MRS. CHEVELEY.  Good evening.  [Exit PHIPPS.]"
    start = text.index("CHEVELEY")
    assert is_speaker_label(text, start, start + len("CHEVELEY"))
    assert clean_surface("Exit PHIPPS") == "Phipps"


def test_first_name_gender_and_places():
    r = build_resolver(
        [("Robert Chiltern", "PERSON")] * 50
        + [("Sir Robert", "PERSON")] * 10
        + [("Lady Chiltern", "PERSON")] * 40
        + [("Gertrude Chiltern", "PERSON")] * 3
        + [("London", "GPE")] * 20
        + [("London Society", "GPE")] * 2
    )
    assert r("Lady Chiltern") != r("Robert Chiltern")  # Robert is male ("Sir Robert")
    assert r("Lady Chiltern") == r("Gertrude Chiltern")
    assert r("London") != r("London Society")  # places are never shortened


def test_title_before_the_span_is_kept():
    from app.services.disambiguation import preceding_title

    text = "I spoke to Sir Robert Chiltern and to the sir."
    assert preceding_title(text, text.index("Robert")) == "Sir"
    assert preceding_title(text, text.index("Chiltern")) is None


def test_pronouns_are_not_names():
    assert clean_surface("He") is None
    assert clean_surface("You") is None


def test_people_tagged_as_organisations_and_leading_words():
    assert clean_surface("That’s Yashvin") == "Yashvin"
    r = build_resolver(
        [("Stepan Arkadyevitch", "ORG")] * 30
        + [("Stepan Arkadyevitch", "PERSON")] * 20
        + [("Stepan", "PERSON")] * 5
    )
    assert r.label[r("Stepan Arkadyevitch")] == "PERSON"
    assert r("Stepan") == r("Stepan Arkadyevitch")


def test_roman_praenomina_are_expanded():
    from app.services.disambiguation import expand_praenomen

    assert expand_praenomen("P. Clodius") == "Publius Clodius"
    assert expand_praenomen("Cn. Pompeium") == "Gnaeus Pompeium"
    assert expand_praenomen("Milo") == "Milo"
