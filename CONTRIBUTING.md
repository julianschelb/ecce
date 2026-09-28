# Contributing

```bash
cd backend && uv venv && uv pip install -e ".[dev,spacy]" && .venv/bin/pytest
cd frontend && npm install && npm run build
```

- Backend: ruff (lint + format) and mypy must pass; add tests under `backend/tests`.
- Frontend: `npm run build` runs the TypeScript type check.
- Conventional Commits (`feat:`, `fix:`, `docs:`, `chore:` …).
- Open a pull request against `main`; CI builds the full-stack image and smoke-tests it. `main`
  is protected: pull requests need passing checks, and merging deploys to Railway automatically.
