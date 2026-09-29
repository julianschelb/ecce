# Architecture

```
┌──────────────┐   /api/*    ┌─────────────────────────────────────────────┐
│  React SPA   │ ──────────▶ │  FastAPI                                     │
│  (Vite,      │             │  api/      auth · corpora · graph · search   │
│  Tailwind,   │ ◀────────── │  services/ chunking · extraction · graph     │
│  force-graph)│  JSON       │            processing · jobs · seed          │
└──────────────┘             │  models/   SQLModel tables · Pydantic schemas│
                             │  core/     settings · security · database    │
                             └───────────────┬─────────────────────────────┘
                                             │ SQLite (+ FTS5)   in-memory GraphCache
                                             ▼
                              corpus · document · chunk · entity · mention · edge · job
```

## Data model

| Table | Content |
|---|---|
| `corpus` | Metadata, status (`empty → queued → processing → ready/failed`), visibility, counts |
| `document` | One row per chapter/file (text kept verbatim) |
| `chunk` | Paragraph-sized passages with character offsets into the document and a reading `page` number; indexed by the `chunk_fts` FTS5 table |
| `entity` | Unique by (normalised name, type); mention count, degree and strength (sum of edge weights) |
| `mention` | Entity occurrences with offsets inside their chunk (for highlighting) |
| `edge` | Single weighted edge per entity pair: ω = Σ exp(−δ) and the cooccurrence count |
| `job` | Background processing status and progress |

## Processing pipeline (`services/processing.py`)

1. **Split** the raw text into documents (`chunking.split_documents`: chapters / Markdown headings) and
   each document into paragraph chunks (`chunk_document`, long paragraphs cut at sentence and word
   boundaries).
2. **Annotate** every document with the configured extractor (`services/extraction.py`): spaCy NER,
   zero-shot GLiNER, or the rule-based fallback. All implement `implicit_word_network`'s
   `BaseEntityExtractor`, so they are interchangeable.
3. **Build the network** with `implicit_word_network.ImplicitNetwork` (window in sentences,
   exponential decay). Entities are merged corpus-wide by normalised name and type
   (`normalize_entity` strips determiners and possessives).
4. **Persist** entities, edges (from the sparse weight matrix), and mentions mapped onto chunks.
   Chunks are grouped into reading pages (`services/pagination.py`: a word budget, default 300,
   over consecutive chunks; documents always start a new page). Pages are deterministic, so seeds
   do not store them and older databases are paginated on start-up (`backfill_pages`).
5. **Serve** graph queries from a per-corpus `GraphCache` (NumPy arrays; filtering by weight, top-N by
   strength, type filters and ego networks run in milliseconds).

Compared with the 2022 prototype, edges are no longer split into context clusters (CIEN); a pair of
entities has exactly one weighted edge, which keeps the graph simple and the queries fast.

## Security

- Read endpoints are public but only expose corpora that are `visible` and `ready`.
- Write endpoints live under `/api/admin` and require a bearer token obtained from
  `POST /api/auth/login` with `ADMIN_PASSWORD` (HS256 JWT, 12 h, constant-time password check,
  login rate limiting).
- Uploads are size-limited (`MAX_UPLOAD_MB`); user text is never rendered as HTML (search snippets
  are split on `<mark>` markers client-side).

## Frontend

- `pages/GalleryView` – public gallery of corpus cards.
- `pages/CorpusExplorer` – reader-first explorer. The middle pane (`components/PageReader`) shows
  one page at a time with mentions highlighted and the entities on the page; the left rail
  (`components/ReaderSidebar`) holds the book index (every entity with its page numbers), the
  table of contents and search results; the right rail (`components/GraphPanel`) is the entity
  network for the whole book or for the current page, with filters and ego networks. Selecting an
  entity or a link lists the pages where it is mentioned, so the graph works as a search tool.
  Page and selected entity are URL parameters (`?page=12&entity=345`).
- `components/AboutDialog` – credits (paper, model, package, code, text sources, author) opened
  from the header; the gallery repeats the main links under its introduction.
- `pages/AdminDashboard` – login modal, corpus table with process/hide/delete, paste and upload
  forms, live job progress.
- Data access through `@tanstack/react-query` hooks (`hooks/useApi.ts`); all requests are relative
  (`/api/...`), so the same bundle works behind FastAPI, nginx or the Vite dev proxy.
