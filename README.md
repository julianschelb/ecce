# ECCE — Entity-Centric Corpus Exploration

ECCE turns text corpora into **implicit entity networks** (Spitz & Gertz) and lets you explore
them in the browser: an interactive entity graph, a passage reader with highlighted mentions,
full-text search cross-referenced with entities, and a password-protected admin panel for adding
and processing corpora. This is the modernised successor of the original Flask/Vue/MongoDB
prototype ([ECCE, WWW '22](https://doi.org/10.1145/3487553.3524237)).

```
.
├── backend/      FastAPI · SQLite (SQLModel, FTS5) · implicit-word-network engine
├── frontend/     React 19 · TypeScript · Vite · Tailwind CSS · force-graph canvas
├── Dockerfile    full-stack image (frontend built and served by the API) — used by Railway
├── docker-compose.yml   two-service local deployment (nginx + API)
└── railway.json
```

## Features

- **Public gallery** of precomputed, ready-to-explore corpora with metadata (genre, documents,
  chunks, entities, edges, date). Visitors cannot create collections.
- **Corpus explorer**: force-directed entity network (node size = strength, colour = entity type),
  sliders for edge-weight and node-count pruning, entity-type filters, ego networks; clicking a
  node or edge filters the reader; split-pane chunk reader with entity spans highlighted.
- **Search**: SQLite FTS5 (BM25 ranking, snippets) over passage chunks, optionally restricted to
  chunks mentioning the selected entities.
- **Admin panel** (`/admin`, `ADMIN_PASSWORD`): paste text or upload `.txt`/`.md` files in batch,
  trigger background processing with live job progress, hide/show and delete corpora.
- **Graph engine**: the [`implicit-word-network`](https://pypi.org/project/implicit-word-network/)
  package computes ω(v, w) = Σ exp(−δ) with sparse matrix products; edges are single weighted
  cooccurrence edges (multi-context edge clustering of the prototype was dropped).
- **Swappable extractors**: spaCy (default when installed), zero-shot GLiNER, or a dependency-free
  rule-based fallback — all CPU-only.
- **Seed data**: 27 public-domain corpora ship precomputed (`backend/data/seed/*.json.gz`) and are
  imported on first start, so the app works immediately: *Alice's Adventures in Wonderland* plus 25
  further Project Gutenberg classics processed with spaCy, and Vergil's complete Latin works from
  the Perseus Digital Library processed with the LatinCy `la_core_web_md` pipeline (the Aeneid is
  the source corpus of the Loci Similes intertextuality benchmark).

## Quick start (local development)

```bash
# backend
cd backend
uv venv && uv pip install -e ".[dev,spacy]"        # or: pip install -e ".[dev,spacy]"
ADMIN_PASSWORD=change-me .venv/bin/uvicorn app.main:app --reload --port 8000

# frontend (second terminal; proxies /api to :8000)
cd frontend
npm install && npm run dev                         # http://localhost:5173
```

API docs: http://localhost:8000/api/docs

## Tests and checks

```bash
cd backend && .venv/bin/pytest                     # graph, auth, search, admin, seed round-trip
cd frontend && npm run build                       # type-check + production bundle
```

## Docker

```bash
# two services (nginx frontend on :8080, API on :8000), persistent SQLite volume
ADMIN_PASSWORD=change-me docker compose up --build

# single full-stack image (what Railway runs)
docker build -t ecce . && docker run -p 8000:8000 -e ADMIN_PASSWORD=change-me ecce
```

## Deploying on Railway

The root `Dockerfile` + `railway.json` deploy ECCE as **one service**: the React build is served by
FastAPI, which also exposes the API under `/api`. Steps:

1. Create a project and a service from this repository (or `railway up` with the CLI).
2. Set variables: `ADMIN_PASSWORD` (required for the admin panel), optionally `SECRET_KEY`
   (stable tokens across restarts), `EXTRACTOR` (`auto` → spaCy), `CORS_ORIGINS`.
3. Attach a **volume** mounted at `/app/data` so the SQLite database survives redeploys, and set
   `RAILWAY_RUN_UID=0` (Railway mounts volumes root-owned; the image otherwise runs as a non-root user).
4. Railway injects `PORT`; the image binds to it and reports health at `/api/health`.

## Configuration

| Variable | Default | Purpose |
|---|---|---|
| `ADMIN_PASSWORD` | unset | Enables `/admin` and the write API |
| `SECRET_KEY` | random | Signs admin bearer tokens (HS256, 12 h) |
| `DATA_DIR` | `data` | SQLite database (mount a volume here) |
| `SEED_DIR` | `<DATA_DIR>/seed` | Precomputed `*.json` corpora imported when missing |
| `DATABASE_URL` | `sqlite:///<DATA_DIR>/ecce.db` | SQLAlchemy URL |
| `EXTRACTOR` | `auto` | `rule`, `spacy`, `gliner` |
| `WINDOW` | `2` | Cooccurrence window in sentences |
| `MAX_CHUNK_WORDS` | `180` | Paragraph chunk size |
| `FRONTEND_DIST` | unset | Serve a built SPA from this folder |
| `CORS_ORIGINS` | localhost dev ports | JSON list |
| `SEED_ON_STARTUP` | `true` | Import bundled corpora when missing |
| `SEED_ASYNC` | `false` | Import seeds on a background thread (set in the images) |

## API overview

| Method | Path | Auth | Description |
|---|---|---|---|
| GET | `/api/corpora` | – | Gallery (visible + ready); `?all=1` for admins |
| GET | `/api/corpora/{slug}` | – | Metadata, entity-type counts, top entities |
| GET | `/api/corpora/{slug}/graph` | – | `min_weight`, `max_nodes`, `labels`, `focus` |
| GET | `/api/corpora/{slug}/entities` · `/entities/{id}` | – | Lookup, detail with neighbours |
| GET | `/api/corpora/{slug}/edges/{a}/{b}` | – | Edge weight/count and shared passages |
| GET | `/api/corpora/{slug}/documents` · `/chunks` | – | Reader (filter by document / entities) |
| GET | `/api/corpora/{slug}/search?q=` | – | Full-text search (FTS5, BM25, snippets) |
| POST | `/api/auth/login` | – | Password → bearer token |
| POST | `/api/admin/corpora` · `/corpora/upload` | admin | Create from text / files |
| POST | `/api/admin/corpora/{slug}/process` | admin | Background processing job |
| PATCH/DELETE | `/api/admin/corpora/{slug}` | admin | Edit, hide, delete |
| GET | `/api/admin/jobs` · `/jobs/{id}` | admin | Job status |

## Bundled corpora

| Title | Author | Year | Source |
|---|---|---|---|
| Alice's Adventures in Wonderland | Lewis Carroll | 1865 | #11 |
| Pride and Prejudice | Jane Austen | 1813 | #1342 |
| Frankenstein; or, The Modern Prometheus | Mary Wollstonecraft Shelley | 1818 | #84 |
| Dracula | Bram Stoker | 1897 | #345 |
| Moby-Dick; or, The Whale | Herman Melville | 1851 | #2701 |
| A Tale of Two Cities | Charles Dickens | 1859 | #98 |
| Great Expectations | Charles Dickens | 1861 | #1400 |
| Jane Eyre | Charlotte Brontë | 1847 | #1260 |
| Wuthering Heights | Emily Brontë | 1847 | #768 |
| The Adventures of Sherlock Holmes | Arthur Conan Doyle | 1892 | #1661 |
| The Picture of Dorian Gray | Oscar Wilde | 1890 | #174 |
| Treasure Island | Robert Louis Stevenson | 1883 | #120 |
| The War of the Worlds | H. G. Wells | 1898 | #36 |
| The Time Machine | H. G. Wells | 1895 | #35 |
| Emma | Jane Austen | 1815 | #158 |
| Sense and Sensibility | Jane Austen | 1811 | #161 |
| Little Women | Louisa May Alcott | 1868 | #514 |
| The Adventures of Tom Sawyer | Mark Twain | 1876 | #74 |
| Adventures of Huckleberry Finn | Mark Twain | 1884 | #76 |
| The Strange Case of Dr Jekyll and Mr Hyde | Robert Louis Stevenson | 1886 | #43 |
| Around the World in Eighty Days | Jules Verne | 1873 | #103 |
| Twenty Thousand Leagues under the Sea | Jules Verne | 1870 | #164 |
| The Wonderful Wizard of Oz | L. Frank Baum | 1900 | #55 |
| Peter Pan | J. M. Barrie | 1911 | #16 |
| The Jungle Book | Rudyard Kipling | 1894 | #236 |
| The Odyssey | Homer (translated by Samuel Butler) | c. 700 BCE | #1727 |
| Anne of Green Gables | L. M. Montgomery | 1908 | #45 |
| Vergil: Eclogues, Georgics, Aeneid (Latin) | P. Vergilius Maro | c. 19 BCE | Perseus canonical-latinLit |

All texts are in the public domain. Regenerate the English seeds with
`backend/scripts/build_gutenberg_seeds.py` (catalogue in `backend/data/catalogue/gutenberg.json`) and the
Latin one with `backend/scripts/build_perseus_seed.py` (needs the LatinCy wheel, see below).

## Building a seed corpus

```bash
cd backend
.venv/bin/python scripts/build_seed.py data/seed/my-text.txt --slug my-text --title "My Text" --extractor spacy
```

The resulting `data/seed/my-text.json` (or `.json.gz` with `--gzip`) is imported automatically at startup.

Latin (or other languages) work with any spaCy pipeline that provides NER, e.g. LatinCy:

```bash
uv pip install https://huggingface.co/latincy/la_core_web_md/resolve/main/la_core_web_md-3.9.8-py3-none-any.whl
.venv/bin/python scripts/build_seed.py vergil.txt --slug vergil --title "Aeneid" --language la \
  --extractor spacy --spacy-model la_core_web_md --spacy-labels PERSON,LOC,NORP --gzip
```

## License

MIT. Alice's Adventures in Wonderland is in the public domain (Project Gutenberg).
