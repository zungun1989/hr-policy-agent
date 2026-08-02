"""
RAG ingestion pipeline: parse corpus → chunk → embed → store in ChromaDB.
Run once at build time: python rag/ingest.py
PYTHONHASHSEED=42 is set for reproducibility.
"""
import os
import re
import sys
import json
import hashlib

os.environ.setdefault("PYTHONHASHSEED", "42")

CORPUS_PATH = os.environ.get("CORPUS_PATH", "./corpus")
CHROMA_DB_PATH = os.environ.get("CHROMA_DB_PATH", "./rag/chroma_store")
CHUNK_SIZE_TOKENS = 400
CHUNK_OVERLAP_TOKENS = 64


def _approx_tokens(text: str) -> int:
    return len(text.split())


def _chunk_markdown(text: str, doc_id: str, title: str) -> list[dict]:
    """Heading-aware chunking: split on H1/H2 headings, then by token window."""
    heading_pattern = re.compile(r"^(#{1,2})\s+(.+)$", re.MULTILINE)
    sections = []
    last_pos = 0
    current_section = "Introduction"

    for match in heading_pattern.finditer(text):
        if match.start() > last_pos:
            sections.append((current_section, text[last_pos:match.start()].strip()))
        current_section = match.group(2).strip()
        last_pos = match.end()

    if last_pos < len(text):
        sections.append((current_section, text[last_pos:].strip()))

    chunks = []
    for section, content in sections:
        if not content:
            continue
        words = content.split()
        start = 0
        while start < len(words):
            end = min(start + CHUNK_SIZE_TOKENS, len(words))
            chunk_text = " ".join(words[start:end])
            chunk_id = hashlib.md5(f"{doc_id}:{section}:{start}".encode()).hexdigest()[:12]
            chunks.append({
                "id": chunk_id,
                "doc_id": doc_id,
                "title": title,
                "section": section,
                "text": chunk_text,
                "source_snippet": chunk_text[:200],
            })
            if end == len(words):
                break
            start += CHUNK_SIZE_TOKENS - CHUNK_OVERLAP_TOKENS

    return chunks


def _chunk_pdf(pdf_path: str, doc_id: str, title: str) -> list[dict]:
    """Token window with overlap for PDF text."""
    try:
        from pypdf import PdfReader
    except ImportError:
        print(f"pypdf not installed, skipping {pdf_path}")
        return []

    reader = PdfReader(pdf_path)
    full_text = "\n".join(page.extract_text() or "" for page in reader.pages)

    words = full_text.split()
    chunks = []
    start = 0
    chunk_index = 0
    while start < len(words):
        end = min(start + CHUNK_SIZE_TOKENS, len(words))
        chunk_text = " ".join(words[start:end])
        chunk_id = hashlib.md5(f"{doc_id}:page:{chunk_index}".encode()).hexdigest()[:12]
        chunks.append({
            "id": chunk_id,
            "doc_id": doc_id,
            "title": title,
            "section": f"Page chunk {chunk_index + 1}",
            "text": chunk_text,
            "source_snippet": chunk_text[:200],
        })
        if end == len(words):
            break
        start += CHUNK_SIZE_TOKENS - CHUNK_OVERLAP_TOKENS
        chunk_index += 1

    return chunks


def load_corpus(corpus_path: str) -> list[dict]:
    chunks = []
    doc_map = {
        "pto_policy.md": "POL-001 — PTO Policy",
        "remote_work_policy.md": "POL-002 — Remote Work Policy",
        "expense_policy.md": "POL-003 — Expense Policy",
        "benefits_policy.md": "POL-004 — Benefits Policy",
        "onboarding_policy.md": "POL-005 — Onboarding Policy",
        "data_security_policy.md": "POL-006 — Data Security Policy",
        "workplace_conduct.md": "POL-007 — Workplace Conduct Policy",
        "leave_policy.md": "POL-008 — Leave Policy",
        "equipment_policy.md": "POL-009 — Equipment Policy",
        "travel_policy.md": "POL-010 — Travel Policy",
        "holidays.pdf": "POL-011 — Holiday Calendar",
    }

    for filename, title in doc_map.items():
        filepath = os.path.join(corpus_path, filename)
        if not os.path.exists(filepath):
            print(f"  [SKIP] {filename} not found")
            continue

        doc_id = filename.rsplit(".", 1)[0]
        print(f"  [OK]   {filename}")

        if filename.endswith(".md"):
            with open(filepath, encoding="utf-8") as f:
                text = f.read()
            chunks.extend(_chunk_markdown(text, doc_id, title))
        elif filename.endswith(".pdf"):
            chunks.extend(_chunk_pdf(filepath, doc_id, title))

    return chunks


def build_index(chunks: list[dict], db_path: str) -> None:
    import chromadb
    from chromadb.utils.embedding_functions import EmbeddingFunction

    try:
        from fastembed import TextEmbedding
        embed_model = TextEmbedding("BAAI/bge-small-en-v1.5")
        print("  [OK] Using fastembed BAAI/bge-small-en-v1.5")

        class FastEmbedFn(EmbeddingFunction):
            def __call__(self, input: list[str]):
                return [emb.tolist() for emb in embed_model.embed(input)]

        embedding_fn = FastEmbedFn()

    except ImportError:
        print("  [WARN] fastembed not available, using ChromaDB default")
        embedding_fn = None

    client = chromadb.PersistentClient(path=db_path)

    try:
        client.delete_collection("hr_policies")
    except Exception:
        pass

    kwargs = {"name": "hr_policies", "metadata": {"hnsw:space": "cosine"}}
    if embedding_fn:
        kwargs["embedding_function"] = embedding_fn

    collection = client.create_collection(**kwargs)

    batch_size = 50
    for i in range(0, len(chunks), batch_size):
        batch = chunks[i: i + batch_size]
        collection.add(
            ids=[c["id"] for c in batch],
            documents=[c["text"] for c in batch],
            metadatas=[{
                "doc_id": c["doc_id"],
                "title": c["title"],
                "section": c["section"],
                "source_snippet": c["source_snippet"],
            } for c in batch],
        )
        print(f"  Indexed chunks {i + 1}–{i + len(batch)}")

    print(f"  Total chunks indexed: {collection.count()}")


def main():
    print("=== RAG Ingestion Pipeline ===")

    # Generate holidays PDF if missing
    pdf_path = os.path.join(CORPUS_PATH, "holidays.pdf")
    if not os.path.exists(pdf_path):
        print("[1] Generating holidays.pdf...")
        script = os.path.join(CORPUS_PATH, "create_holidays_pdf.py")
        if os.path.exists(script):
            import subprocess
            subprocess.run([sys.executable, script], check=False)
        else:
            print("  [SKIP] create_holidays_pdf.py not found")
    else:
        print("[1] holidays.pdf already exists")

    print(f"[2] Loading corpus from {CORPUS_PATH}...")
    chunks = load_corpus(CORPUS_PATH)
    print(f"  Loaded {len(chunks)} chunks from corpus")

    print(f"[3] Building ChromaDB index at {CHROMA_DB_PATH}...")
    os.makedirs(CHROMA_DB_PATH, exist_ok=True)
    build_index(chunks, CHROMA_DB_PATH)

    print("=== Ingestion complete ===")


if __name__ == "__main__":
    main()
