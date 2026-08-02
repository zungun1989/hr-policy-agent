"""
RAG retriever: query ChromaDB, return top-k chunks with metadata.
"""
import os
from typing import Optional

CHROMA_DB_PATH = os.environ.get("CHROMA_DB_PATH", "./rag/chroma_store")

_client = None
_collection = None
_embed_model = None


def _get_collection():
    global _client, _collection, _embed_model

    if _collection is not None:
        return _collection

    import chromadb
    from chromadb.utils.embedding_functions import EmbeddingFunction

    try:
        from fastembed import TextEmbedding
        _embed_model = TextEmbedding("BAAI/bge-small-en-v1.5")

        class FastEmbedFn(EmbeddingFunction):
            def __call__(self, input: list[str]):
                return [emb.tolist() for emb in _embed_model.embed(input)]

        embedding_fn = FastEmbedFn()
    except ImportError:
        embedding_fn = None

    _client = chromadb.PersistentClient(path=CHROMA_DB_PATH)

    kwargs = {"name": "hr_policies"}
    if embedding_fn:
        kwargs["embedding_function"] = embedding_fn

    _collection = _client.get_collection(**kwargs)
    return _collection


def search(
    query: str,
    top_k: int = 5,
    doc_filter: Optional[str] = None,
) -> list[dict]:
    """
    Search the policy index for the most relevant chunks.

    Returns a list of dicts with keys:
      text, doc_id, title, section, source_snippet, score (distance)
    """
    collection = _get_collection()

    where = {"doc_id": doc_filter} if doc_filter else None

    results = collection.query(
        query_texts=[query],
        n_results=min(top_k, collection.count()),
        where=where,
        include=["documents", "metadatas", "distances"],
    )

    hits = []
    if not results["ids"] or not results["ids"][0]:
        return hits

    for doc, meta, dist in zip(
        results["documents"][0],
        results["metadatas"][0],
        results["distances"][0],
    ):
        hits.append({
            "text": doc,
            "doc_id": meta.get("doc_id", ""),
            "title": meta.get("title", ""),
            "section": meta.get("section", ""),
            "source_snippet": meta.get("source_snippet", doc[:200]),
            "score": round(1 - dist, 4),  # convert cosine distance to similarity
        })

    return hits


def is_index_loaded() -> bool:
    try:
        col = _get_collection()
        return col.count() > 0
    except Exception:
        return False


def get_collection_count() -> int:
    try:
        return _get_collection().count()
    except Exception:
        return 0
