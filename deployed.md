# Deployment Information

## Deployed URL

**Application**: https://huggingface.co/spaces/[HF_USERNAME]/hr-policy-agent

> **Note**: Replace `[HF_USERNAME]` with your actual Hugging Face username after deployment.

## Health Endpoint

```
GET https://huggingface.co/spaces/[HF_USERNAME]/hr-policy-agent/health
```

Expected response:
```json
{
  "status": "ok",
  "rag_index": "loaded",
  "rag_chunk_count": 120,
  "mcp": "available",
  "model": "claude-haiku-4-5-20251001"
}
```

## Demo Endpoints

```
POST https://huggingface.co/spaces/[HF_USERNAME]/hr-policy-agent/demo/task1
POST https://huggingface.co/spaces/[HF_USERNAME]/hr-policy-agent/demo/task2
```

## Cold-Start Behavior

**Hugging Face Spaces Docker (free tier) does NOT spin down after inactivity.** The container remains running 24/7. There is no cold-start delay for subsequent requests.

However, the first request after a Space *restart* (e.g., after a new deployment or platform maintenance) may take 10–30 seconds due to:
1. FastAPI application startup
2. ChromaDB collection loading into memory
3. fastembed model loading (~33MB)

The RAG index is pre-built into the Docker image (via `RUN python rag/ingest.py` in the Dockerfile), so no re-indexing occurs at startup.

## Environment Variables Required

Set these as **Hugging Face Space Secrets** (not committed to the repository):

| Variable | Description |
|---|---|
| `ANTHROPIC_API_KEY` | Anthropic API key for Claude claude-haiku-4-5 |

Optional overrides (have defaults):
| Variable | Default | Description |
|---|---|---|
| `CHROMA_DB_PATH` | `/app/rag/chroma_store` | ChromaDB persistence path |
| `CORPUS_PATH` | `/app/corpus` | Policy document directory |
| `MOCK_DATA_PATH` | `/app/mock_data` | Mock JSON data directory |

## CI/CD

GitHub Actions workflow at `.github/workflows/ci.yml`:
- Triggers on push to `main` and all pull requests
- Tests: RAG index build check + pytest suite
- Deploy: pushes to HF Spaces only if tests pass and branch is `main`

Required GitHub Secrets:
- `HF_TOKEN`: Hugging Face write token
- `HF_USERNAME`: Your Hugging Face username
