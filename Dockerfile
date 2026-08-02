FROM python:3.12-slim

WORKDIR /app

# Install dependencies first (layer caching)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy all project files
COPY . .

# Build RAG index at image build time
# fastembed will download the model on first run (~33MB)
RUN python rag/ingest.py

# HF Spaces uses port 7860
EXPOSE 7860

ENV PYTHONPATH=/app
ENV CHROMA_DB_PATH=/app/rag/chroma_store
ENV CORPUS_PATH=/app/corpus
ENV MOCK_DATA_PATH=/app/mock_data

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "7860"]
