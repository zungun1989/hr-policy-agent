"""
RAG-based MCP tools: search policy documents, retrieve sections, check compliance.
"""
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from rag.retriever import search


def search_policy_documents(query: str, top_k: int = 5) -> dict:
    """
    Search the policy corpus for chunks relevant to the query.
    Returns top-k chunks with citations.
    """
    try:
        hits = search(query=query, top_k=top_k)
        return {
            "query": query,
            "results": [
                {
                    "doc_id": h["doc_id"],
                    "title": h["title"],
                    "section": h["section"],
                    "text": h["text"],
                    "source_snippet": h["source_snippet"],
                    "relevance_score": h["score"],
                }
                for h in hits
            ],
            "total_results": len(hits),
        }
    except Exception as e:
        return {"error": str(e), "results": [], "total_results": 0}


def get_policy_section(doc_id: str, section_query: str, top_k: int = 3) -> dict:
    """
    Retrieve specific section(s) from a named policy document.
    doc_id examples: 'pto_policy', 'remote_work_policy', 'benefits_policy'
    """
    try:
        hits = search(query=section_query, top_k=top_k, doc_filter=doc_id)
        if not hits:
            return {
                "doc_id": doc_id,
                "section_query": section_query,
                "found": False,
                "message": f"No matching section found in {doc_id} for query '{section_query}'",
            }
        return {
            "doc_id": doc_id,
            "section_query": section_query,
            "found": True,
            "sections": [
                {
                    "section": h["section"],
                    "title": h["title"],
                    "text": h["text"],
                    "source_snippet": h["source_snippet"],
                }
                for h in hits
            ],
        }
    except Exception as e:
        return {"error": str(e), "found": False}


def check_policy_compliance(situation: str, top_k: int = 5) -> dict:
    """
    Check whether a described situation is compliant with company policies.
    Retrieves relevant policy chunks and returns them for LLM evaluation.
    """
    try:
        compliance_query = f"policy requirements rules approval {situation}"
        hits = search(query=compliance_query, top_k=top_k)

        return {
            "situation": situation,
            "relevant_policies": [
                {
                    "doc_id": h["doc_id"],
                    "title": h["title"],
                    "section": h["section"],
                    "text": h["text"],
                    "source_snippet": h["source_snippet"],
                    "relevance_score": h["score"],
                }
                for h in hits
            ],
            "guidance": (
                "Review the relevant policy sections above to determine compliance. "
                "Cite specific sections when providing your compliance determination."
            ),
        }
    except Exception as e:
        return {"error": str(e), "relevant_policies": []}
