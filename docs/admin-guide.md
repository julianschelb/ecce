# Admin guide

1. Open `/admin` and sign in with `ADMIN_PASSWORD`. The token is kept in the browser's local
   storage for 12 hours; *Sign out* removes it.
2. **Create a corpus** by pasting text (chapters or Markdown headings become separate documents)
   or by uploading `.txt` / `.md` files (one document per file). Choose whether the corpus is
   visible in the gallery and whether to process it immediately.
3. **Processing** runs in the background: chunking → entity extraction → network construction.
   The job list shows progress and errors; the corpus becomes `ready` when done and only then
   appears in the public gallery.
4. **Reprocess** after changing `EXTRACTOR` or `WINDOW` in the environment; **Hide/Show** toggles
   gallery visibility without deleting data; **Delete** removes documents, entities and edges.

Tips:

- For zero-shot entity types (e.g. `ship`, `disease`), install the `gliner` extra and set
  `EXTRACTOR=gliner` and `GLINER_LABELS='["person","ship","disease"]'`.
- Precompute large corpora offline with `backend/scripts/build_seed.py` and drop the JSON into the
  seed directory to skip live extraction on the server. The bundled catalogue
  (`backend/data/catalogue/gutenberg.json`) lists the Project Gutenberg works; run
  `scripts/verify_catalogue.py` after adding entries (it checks author and translator death years,
  language and the rights statement against Gutenberg's metadata) and then
  `scripts/build_gutenberg_seeds.py`, which skips entries that failed the check.
- Latin corpora: install a LatinCy pipeline (`la_core_web_md`) and build seeds with
  `--spacy-model la_core_web_md --spacy-labels PERSON,LOC,NORP`.
