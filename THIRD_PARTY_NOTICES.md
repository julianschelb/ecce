# Third-party notices

ECCE's own code is MIT-licensed (`LICENSE`). It uses or ships the following third-party
components and material.

## Texts

| Material | Licence | Notes |
|---|---|---|
| English works obtained from [Project Gutenberg](https://www.gutenberg.org/) | Public domain (EU and US) | See [`backend/data/seed/NOTICE.md`](backend/data/seed/NOTICE.md). The Project Gutenberg licence and trademark are not used; the source line only credits where each text was obtained. |
| Latin works in the digital editions of the Perseus Digital Library, Tufts University ([canonical-latinLit](https://github.com/PerseusDL/canonical-latinLit)): Vergil (ed. Greenough, 1881), Cicero's *In Catilinam* (ed. Clark, 1908), Sallust's *De Catilinae coniuratione* (ed. Ahlberg, 1919) | [CC BY-SA 4.0](https://creativecommons.org/licenses/by-sa/4.0/) | Adapted (plain text, documents and passages, entity annotations, network); the adapted corpora are shared under CC BY-SA 4.0. See `backend/data/seed/NOTICE.md`. |

## Models used to build the bundled annotations

The models are not shipped with the corpora; the annotations they produced are distributed as
part of the seed data.

| Component | Licence | Copyright |
|---|---|---|
| [spaCy](https://github.com/explosion/spaCy) | MIT | © Explosion AI GmbH |
| [`en_core_web_sm`](https://github.com/explosion/spacy-models) (English NER) | MIT | © Explosion AI GmbH |
| [LatinCy `la_core_web_md`](https://huggingface.co/latincy/la_core_web_md) (Latin NER) | MIT | © Patrick J. Burns |
| [`implicit-word-network`](https://pypi.org/project/implicit-word-network/) | MIT | © Julian Schelb |

## Bundled with the web frontend

| Component | Licence | Where the licence ships |
|---|---|---|
| IBM Plex Sans, IBM Plex Mono ([Fontsource](https://fontsource.org/)) | SIL Open Font License 1.1 | `/licenses/ibm-plex-*-OFL.txt` in the build |
| Source Serif 4 ([Fontsource](https://fontsource.org/)) | SIL Open Font License 1.1 | `/licenses/source-serif-4-OFL.txt` |
| [Swagger UI](https://github.com/swagger-api/swagger-ui) (API docs at `/api/docs`) | Apache License 2.0 | `/swagger/LICENSE`, `/swagger/NOTICE` |
| React, TanStack Query, React Router, react-force-graph, d3 and every other npm package in the bundle | MIT, ISC, BSD-3-Clause | `/licenses/third-party-npm.txt`, generated at build time (rollup-plugin-license) |
