# Deployment Information

## Deployed URL

**Application**: https://hr-policy-agent-production.up.railway.app

## Health Endpoint

```
GET https://hr-policy-agent-production.up.railway.app/health
```

Expected response:
```json
{
  "status": "ok",
  "rag_index": "loaded",
  "rag_chunk_count": 113,
  "mcp": "available",
  "model": "groq/llama-3.3-70b-versatile"
}
```

## Demo Endpoints

```
POST https://hr-policy-agent-production.up.railway.app/demo/task1
POST https://hr-policy-agent-production.up.railway.app/demo/task2
```

## Cold-Start Behavior

Railway free tier keeps the container alive as long as the $5 starter credit lasts.
The first request after a redeploy may take 10–30 seconds due to:
1. FastAPI application startup
2. ChromaDB collection loading into memory
3. fastembed model loading (~33MB)

The RAG index is pre-built into the Docker image (via `RUN python rag/ingest.py` in the Dockerfile), so no re-indexing occurs at startup.

## Environment Variables Required

Set these as **Railway Service Variables**:

| Variable | Description |
|---|---|
| `GROQ_API_KEY` | Groq API key for llama-3.3-70b-versatile |

Optional overrides (have defaults):
| Variable | Default | Description |
|---|---|---|
| `CHROMA_DB_PATH` | `/app/rag/chroma_store` | ChromaDB persistence path |
| `CORPUS_PATH` | `/app/corpus` | Policy document directory |
| `MOCK_DATA_PATH` | `/app/mock_data` | Mock JSON data directory |

## CI/CD

GitHub Actions workflow at `.github/workflows/ci.yml`:
- Triggers on push to `main` and all pull requests
- Tests: RAG index build check + pytest suite (13 tests)
- Railway auto-deploys from GitHub on push to `main` (no separate deploy step needed)
