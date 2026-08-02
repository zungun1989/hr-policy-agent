FROM python:3.12-slim

WORKDIR /app

# Install dependencies first (layer caching)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy all project files
COPY . .

# Set env vars BEFORE ingest so fastembed caches to /app (inside the image)
ENV PYTHONPATH=/app
ENV CHROMA_DB_PATH=/app/rag/chroma_store
ENV CORPUS_PATH=/app/corpus
ENV MOCK_DATA_PATH=/app/mock_data
ENV FASTEMBED_CACHE_PATH=/app/rag/.fastembed_cache

# Build RAG index — fastembed model downloaded to FASTEMBED_CACHE_PATH
RUN python rag/ingest.py

EXPOSE 7860

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "7860"]
