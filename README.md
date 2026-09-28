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
- **Seed data**: *Alice's Adventures in Wonderland* (Project Gutenberg #11) ships precomputed and
  is imported on first start, so the app works immediately.

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

## Building a seed corpus

```bash
cd backend
.venv/bin/python scripts/build_seed.py data/seed/my-text.txt --slug my-text --title "My Text" --extractor spacy
```

The resulting `data/seed/my-text.json` is imported automatically at startup.

## License

MIT. Alice's Adventures in Wonderland is in the public domain (Project Gutenberg).
