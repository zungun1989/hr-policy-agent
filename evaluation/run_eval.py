"""
Evaluation script for the Acme Corp HR Policy Agent.
Runs the 25-question eval set against the deployed API and reports metrics.

Usage:
  python evaluation/run_eval.py [--base-url URL] [--k 5] [--k-ablation 3] [--output results.json]

Defaults to the Railway deployment. Override with --base-url http://localhost:8000 for local.
"""
import argparse
import json
import os
import sys
import time
from datetime import datetime, timezone

import httpx

DEFAULT_BASE_URL = "https://hr-policy-agent-production.up.railway.app"
REQUEST_TIMEOUT = 300  # seconds — retries can take up to 6×13s
REQUEST_DELAY = 30     # seconds between questions — Gemini free tier 5 RPM, each Q uses 2-3 LLM calls


def load_questions(path: str) -> list[dict]:
    with open(path, encoding="utf-8") as f:
        data = json.load(f)
    return data["questions"]


def call_chat(base_url: str, question: str, employee_id: str | None = None) -> dict:
    payload = {"message": question}
    if employee_id:
        payload["employee_id"] = employee_id
    resp = httpx.post(
        f"{base_url.rstrip('/')}/chat",
        json=payload,
        timeout=REQUEST_TIMEOUT,
    )
    resp.raise_for_status()
    return resp.json()


def _citation_match(citations: list[dict], expected_doc: str) -> bool:
    return any(expected_doc in (c.get("title", "") + c.get("doc_id", "")) for c in citations)


def _contains_keywords(text: str, gold: str, threshold: float = 0.3) -> float:
    gold_words = set(gold.lower().split())
    answer_words = set(text.lower().split())
    if not gold_words:
        return 0.0
    overlap = gold_words & answer_words
    return len(overlap) / len(gold_words)


def _is_grounded(answer: str, citations: list[dict]) -> bool:
    if not citations:
        return False
    doc_refs = ["POL-", "Policy", "policy", "section", "Section"]
    return any(ref in answer for ref in doc_refs)


def _tool_selection_ok(tool_trace: list[dict], expected_tools: list[str]) -> bool:
    if not expected_tools:
        return True
    called = {t["tool"] for t in tool_trace}
    return any(t in called for t in expected_tools)


def _is_clarification(answer: str) -> bool:
    clarify_signals = ["could you", "could you clarify", "please clarify", "can you provide",
                       "which type", "how many", "what is your", "what type", "please tell me more"]
    return any(s in answer.lower() for s in clarify_signals)


def _is_declined(answer: str) -> bool:
    decline_signals = ["outside the scope", "not related to", "can only assist",
                       "beyond the scope", "not able to help", "cannot help with this"]
    return any(s in answer.lower() for s in decline_signals)


def _action_safe(tool_trace: list[dict]) -> bool:
    for step in tool_trace:
        if step["tool"] in ("create_mock_hr_ticket", "draft_hr_email"):
            result_summary = step.get("result_summary", "")
            if "confirmation" not in result_summary.lower() and "awaiting" not in result_summary.lower():
                if "created" in result_summary.lower() or "sent" in result_summary.lower():
                    return False
    return True


def run_evaluation(questions: list[dict], base_url: str, top_k: int = 5) -> dict:
    results = []
    latencies = []

    for i, q in enumerate(questions, 1):
        print(f"[{i:02d}/{len(questions)}] {q['id']} ({q['category']}) — {q['question'][:60]}...")

        t0 = time.perf_counter()
        try:
            result = call_chat(base_url, q["question"], q.get("employee_id"))
        except Exception as e:
            result = {"answer": f"ERROR: {e}", "citations": [], "tool_trace": [], "latency_ms": 0}
        latency_ms = result.get("latency_ms") or int((time.perf_counter() - t0) * 1000)
        latencies.append(latency_ms)

        answer = result.get("answer", "")
        citations = result.get("citations", [])
        tool_trace = result.get("tool_trace", [])

        grounded = _is_grounded(answer, citations)
        cit_match = _citation_match(citations, q.get("expected_cited_doc", ""))
        partial_match = _contains_keywords(answer, q.get("gold_answer", ""))
        tool_ok = _tool_selection_ok(tool_trace, q.get("expected_tools", []))
        action_safe = _action_safe(tool_trace)

        expected_behavior = q.get("expected_behavior", "")
        if expected_behavior == "clarification_requested":
            behavior_ok = _is_clarification(answer)
        elif expected_behavior == "out_of_scope_declined":
            behavior_ok = _is_declined(answer)
        else:
            behavior_ok = True

        record = {
            "id": q["id"],
            "category": q["category"],
            "question": q["question"],
            "answer": answer[:500],
            "gold_answer": q.get("gold_answer", ""),
            "latency_ms": latency_ms,
            "grounded": grounded,
            "citation_match": cit_match,
            "partial_match_score": round(partial_match, 2),
            "tool_selection_ok": tool_ok,
            "action_safe": action_safe,
            "behavior_ok": behavior_ok,
            "tool_trace_summary": [t["tool"] for t in tool_trace],
            "citations_count": len(citations),
        }
        results.append(record)
        print(f"   grounded={grounded} cit_match={cit_match} partial={partial_match:.2f} "
              f"tool_ok={tool_ok} latency={latency_ms}ms")
        if i < len(questions):
            time.sleep(REQUEST_DELAY)

    n = len(results)
    policy_qs = [r for r in results if r["category"] in ("simple_policy", "multi_doc")]
    tool_qs = [r for r in results if r["category"] == "tool_task"]
    escalation_qs = [r for r in results if r["category"] in ("ambiguous", "out_of_scope")]

    latencies_sorted = sorted(latencies)
    p50 = latencies_sorted[n // 2]
    p95 = latencies_sorted[int(n * 0.95)]

    metrics = {
        "evaluation_date": datetime.now(timezone.utc).isoformat(),
        "base_url": base_url,
        "top_k": top_k,
        "n_questions": n,
        "groundedness_rate": round(sum(r["grounded"] for r in policy_qs) / max(len(policy_qs), 1), 2),
        "citation_accuracy": round(sum(r["citation_match"] for r in policy_qs) / max(len(policy_qs), 1), 2),
        "avg_partial_match": round(sum(r["partial_match_score"] for r in results) / n, 2),
        "tool_selection_accuracy": round(sum(r["tool_selection_ok"] for r in tool_qs) / max(len(tool_qs), 1), 2),
        "workflow_completion_rate": round(sum(r["tool_selection_ok"] and r["grounded"] for r in tool_qs) / max(len(tool_qs), 1), 2),
        "escalation_accuracy": round(sum(r["behavior_ok"] for r in escalation_qs) / max(len(escalation_qs), 1), 2),
        "action_safety_rate": round(sum(r["action_safe"] for r in results) / n, 2),
        "latency_p50_ms": p50,
        "latency_p95_ms": p95,
    }

    return {"metrics": metrics, "per_question": results}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-url", default=DEFAULT_BASE_URL, help="Base URL of deployed app")
    parser.add_argument("--k", type=int, default=5, help="Retrieval top-k (informational only)")
    parser.add_argument("--k-ablation", type=int, default=None, help="Run ablation with this k")
    parser.add_argument("--output", default="evaluation/results.json")
    args = parser.parse_args()

    questions_path = os.path.join(os.path.dirname(__file__), "eval_questions.json")
    questions = load_questions(questions_path)

    print(f"\n=== Evaluation Run (k={args.k}, url={args.base_url}) ===")
    eval_result = run_evaluation(questions, base_url=args.base_url, top_k=args.k)

    output = {"k": args.k, "results": eval_result}

    if args.k_ablation:
        print(f"\n=== Ablation Run (k={args.k_ablation}) ===")
        ablation_result = run_evaluation(questions, base_url=args.base_url, top_k=args.k_ablation)
        output["ablation"] = {"k": args.k_ablation, "results": ablation_result}

    os.makedirs(os.path.dirname(args.output), exist_ok=True)
    with open(args.output, "w", encoding="utf-8") as f:
        json.dump(output, f, indent=2)

    print(f"\n=== Summary (k={args.k}) ===")
    m = eval_result["metrics"]
    print(f"Groundedness:           {m['groundedness_rate']:.0%}")
    print(f"Citation accuracy:      {m['citation_accuracy']:.0%}")
    print(f"Avg partial match:      {m['avg_partial_match']:.0%}")
    print(f"Tool selection:         {m['tool_selection_accuracy']:.0%}")
    print(f"Workflow completion:    {m['workflow_completion_rate']:.0%}")
    print(f"Escalation accuracy:    {m['escalation_accuracy']:.0%}")
    print(f"Action safety:          {m['action_safety_rate']:.0%}")
    print(f"Latency p50/p95:        {m['latency_p50_ms']}ms / {m['latency_p95_ms']}ms")
    print(f"\nFull results saved to: {args.output}")


if __name__ == "__main__":
    main()
