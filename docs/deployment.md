# Deployment

## Railway (single service)

The repository root contains a `Dockerfile` that builds the React app and bakes it into the API
image, and a `railway.json` with the health check and start command. Deploy with the CLI:

```bash
railway login                     # or RAILWAY_TOKEN=<project token>
railway init --name ecce          # once
railway volume add --mount-path /app/data --service ecce
railway variables --service ecce --set ADMIN_PASSWORD=<strong password> \
  --set SECRET_KEY=$(openssl rand -hex 32) --set RAILWAY_RUN_UID=0 --set SEED_DIR=/app/seed
railway domain --service ecce     # public URL
railway up --service ecce
```

Notes:

- `RAILWAY_RUN_UID=0` is required because Railway mounts volumes root-owned while the image runs
  as a non-root user.
- The bundled seed corpora live in `/app/seed` (`SEED_DIR`), outside the volume, and are imported
  into the database on first start.
- The Railway service is connected to the GitHub repository (`julianschelb/ecce`, branch
  `main`): every push to `main` triggers a build of the root `Dockerfile` on Railway, and the
  deploy waits for the GitHub check suite (CI) to pass. `.github/workflows/deploy.yml` remains as
  a manual fallback (`workflow_dispatch`) using the `RAILWAY_TOKEN` secret.
- `main` is protected: changes arrive through pull requests whose CI checks must pass; force
  pushes and branch deletion are blocked.
- Railway is phasing out `railway.json` in favour of `.railway/railway.ts` (Infrastructure as Code);
  `railway config migrate --apply` converts it. The current file keeps working until 2026-12-01.
- Service settings are also stored on Railway itself (Dockerfile path, health check, volume,
  variables, custom domains), so the repository only needs the Dockerfile.

## Dev environment (Railway)

The Railway project has a second environment, **dev**
(<https://ecce-dev-3a20.up.railway.app>), with its own volume and secret key. It deploys the
`dev` branch, so changes can be tried on Railway before they reach `main` and production.

- **Deploy a branch, tag or commit to dev:** run the GitHub workflow *Deploy to dev*
  (Actions → Deploy to dev → Run workflow, or `gh workflow run deploy-dev.yml -f ref=<ref>`).
  It runs the full CI on that ref and then moves the `dev` branch to it; Railway builds and
  deploys it immediately.
- **Push to `dev` directly** to deploy without the CI gate (quick experiments).
- Production is unaffected: it deploys `main` (after CI) as before.

Dev differs from production only in its variables: no `PUBLIC_URL` (so it does not redirect to
the public domain), its own `SECRET_KEY` (production logins are not valid there) and
`ENVIRONMENT=development`. Legal details and the admin password are the same.

## Docker Compose (two services)

```bash
ADMIN_PASSWORD=change-me docker compose up --build
```

- `backend` – FastAPI on port 8000, SQLite in the `ecce-data` volume.
- `frontend` – nginx on port 8080 serving the built SPA and proxying `/api` to the backend
  (`BACKEND_URL`).

## Bare metal / any container host

```bash
docker build -t ecce . && docker run -p 8000:8000 -e ADMIN_PASSWORD=... -v ecce-data:/app/data ecce
```

The image binds to `$PORT` (default 8000) and answers `GET /api/health`.

## Sizing

CPU-only. The default spaCy pipeline (`en_core_web_sm`) processes roughly 10k tokens/s per core;
network construction runs at >1M tokens/s. A 512 MB container is enough for book-sized corpora;
GLiNER (optional `gliner` extra) needs ~2 GB.
