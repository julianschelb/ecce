# Texts and licences of the bundled corpora

The code of ECCE is MIT-licensed (see `LICENSE` at the repository root). The corpora in this
folder are **not** covered by that licence; their status is as follows.

## English works (`*.json.gz` except `vergil-opera`, and `alice-in-wonderland.*`)

Public-domain texts taken from Project Gutenberg ebooks. A work is only included if every
author **and** translator died in 1955 or earlier and the work was first published before
1931, so it is in the public domain in the European Union (70 years after the death of the
last author) and in the United States (published before 1931). `backend/scripts/verify_catalogue.py`
checks every entry against Project Gutenberg's catalogue metadata and records the names and
death years in `backend/data/catalogue/gutenberg.json`.

The Project Gutenberg licence, header and footer, and everything Project Gutenberg's
volunteers added (production credits, transcriber's notes, end-of-ebook lines) were removed
(`strip_production_notes` in `build_gutenberg_seeds.py`), so the texts carry no Project
Gutenberg trademark. The source field of each corpus ("Project Gutenberg #<id>") only credits
where the text was obtained.

The derived data (paragraph segmentation, entity annotations, network edges) is released
under the MIT licence together with the code.

## Vergil (`vergil-opera.json.gz`)

*Vergil: Bucolics, Aeneid, and Georgics*, edited by J. B. Greenough (Boston: Ginn & Co., 1881),
in the digital edition of the Perseus Digital Library
([PerseusDL/canonical-latinLit](https://github.com/PerseusDL/canonical-latinLit), files
`phi0690.phi001–003.perseus-lat2.xml`), licensed under
[Creative Commons Attribution-ShareAlike 4.0 International (CC BY-SA 4.0)](https://creativecommons.org/licenses/by-sa/4.0/).

Changes: the TEI files were converted to plain text, split into one document per book,
segmented into passages, annotated with named entities using LatinCy (`la_core_web_md`) and
turned into an entity network.

This adapted corpus (the text **and** the annotations and network derived from it) is
licensed under the same **CC BY-SA 4.0** licence. Perseus asks that improvements to their
texts be offered back to them.
