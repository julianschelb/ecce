# ECCE backend

FastAPI service that turns text corpora into implicit entity networks and serves the
public gallery, graph, reader, search and the password-protected admin API.

```bash
uv venv && uv pip install -e ".[dev,spacy]"
ADMIN_PASSWORD=change-me uvicorn app.main:app --reload --port 8000
pytest
```

See the repository README for the full documentation.
