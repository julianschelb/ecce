# Texts and licences of the bundled corpora

The code of ECCE is MIT-licensed (see `LICENSE` at the repository root). The corpora in this
folder are **not** covered by that licence; their status is as follows.

## English works (every corpus whose source is "Project Gutenberg #…")

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

## Latin works from the Perseus Digital Library

Digital editions of the Perseus Digital Library, Tufts University
([PerseusDL/canonical-latinLit](https://github.com/PerseusDL/canonical-latinLit)), licensed under
[Creative Commons Attribution-ShareAlike 4.0 International (CC BY-SA 4.0)](https://creativecommons.org/licenses/by-sa/4.0/).
The printed editions they encode are in the public domain.

| Corpus | Work and edition | Perseus file |
|---|---|---|
| `vergil-opera` | Vergil, *Bucolics, Georgics, Aeneid*, ed. J. B. Greenough (Boston: Ginn & Co., 1881) | `phi0690.phi001–003.perseus-lat2.xml` |
| `cicero-in-catilinam` | Cicero, *In Catilinam I–IV*, ed. A. C. Clark, *M. Tulli Ciceronis Orationes* vol. 1 (Oxford: Clarendon, 1908) | `phi0474.phi013.perseus-lat2.xml` |
| `sallust-catilina` | Sallust, *De Catilinae coniuratione*, ed. A. W. Ahlberg (Leipzig: Teubner, 1919) | `phi0631.phi001.perseus-lat3.xml` |

Changes: the TEI files were converted to plain text (without critical apparatus, notes and
editorial deletions), split into documents (books, speeches or chapters), segmented into
passages, annotated with named entities using LatinCy (`la_core_web_md`, inflected forms merged
by lemma) and turned into an entity network (`backend/scripts/build_perseus_seed.py`). Each
corpus states its source, licence and changes in the reader's Details tab.

These adapted corpora (the text **and** the annotations and network derived from it) are
licensed under the same **CC BY-SA 4.0** licence. Perseus asks that improvements to their
texts be offered back to them.
