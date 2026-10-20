"""Retrieval evaluation runner: compares Keyword baseline (BM25), Vector semantic search,
and Hybrid retrieval (BM25 + Vector + Reciprocal Rank Fusion, k=60) on supported cases.

Usage:
    python -m eval.run_eval [--split dev|held_out|frozen_holdout|all] [--mode keyword|vector|hybrid|all] [--k 5] [--no-save]

Results and comparison reports are saved in eval/results/.
"""
from __future__ import annotations
import argparse, datetime, json, pathlib, statistics, time
from app.retrieval import BM25, HybridRetriever, VectorSearch, load_corpus, load_embeddings
from core.config import load_settings
from core.llm import FakeEmbedder, build_embedder
from core.vectors import compute_file_hash, validate_vector_store
from app.retrieval import FIXTURES_EMBEDDINGS, FIXTURES_CORPUS

ROOT = pathlib.Path(__file__).resolve().parent
RESULTS_DIR = ROOT / "results"

SPLIT_DESCRIPTIONS = {
    "dev": "Development tuning set (inspected for error analysis and parameter calibration)",
    "held_out": "Original holdout set (previously inspected; not an untouched blind set)",
    "frozen_holdout": "Second holdout written by the same author after the first was inspected. Hash-pinned (eval/holdout.sha256) but NOT independent proof of generalisation",
    "all": "Combined baseline benchmark (dev + held_out, 24 supported cases)",
}


def load_cases(split: str) -> list[dict]:
    if split == "all":
        splits = ["dev", "held_out"]
    elif split == "full":
        splits = ["dev", "held_out", "frozen_holdout"]
    else:
        splits = [split]

    cases = []
    for s in splits:
        p = ROOT / f"questions.{s}.jsonl"
        if not p.exists():
            continue
        for line in p.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            case = json.loads(line)
            case["_split"] = s
            cases.append(case)
    return cases


def evaluate_retriever(name: str, retriever, cases: list[dict], k: int = 5) -> dict:
    hits = 0
    latencies = []
    misses = []
    details = []
    for c in cases:
        t0 = time.perf_counter()
        results = retriever.search(c["question"], k=k)
        lat = (time.perf_counter() - t0) * 1000
        latencies.append(lat)
        retrieved_ids = [r["id"] for r in results]
        expected_ids = set(c["expected_chunk_ids"])
        matched = bool(set(retrieved_ids) & expected_ids)
        if matched:
            hits += 1
        else:
            misses.append(c["id"])
        details.append({
            "id": c["id"],
            "split": c.get("_split", "unknown"),
            "question": c["question"],
            "matched": matched,
            "expected_chunk_ids": list(expected_ids),
            "retrieved_chunk_ids": retrieved_ids,
            "latency_ms": round(lat, 2),
        })

    p95 = round(statistics.quantiles(latencies, n=20)[-1], 2) if len(latencies) >= 2 else (round(max(latencies), 2) if latencies else 0.0)
    return {
        "retriever": name,
        "hits": hits,
        "total": len(cases),
        "recall_at_k": round(hits / len(cases), 4) if cases else 0.0,
        "k": k,
        "median_latency_ms": round(statistics.median(latencies), 2) if latencies else 0.0,
        "p95_latency_ms": p95,
        "missed_cases": misses,
        "details": details,
    }


def save_reports(results: dict, split: str, k: int, config_info: dict) -> None:
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    ts = datetime.datetime.now(datetime.timezone.utc).isoformat()
    results["timestamp"] = ts
    results["split"] = split
    results["split_description"] = SPLIT_DESCRIPTIONS.get(split, "Evaluation split")
    results["configuration"] = config_info
    results["metric_explanation"] = (
        f"Recall@{k} measures whether AT LEAST ONE expected evidence chunk ID was present in the top {k} "
        "retrieved passages for each reviewed supported question. Retrieval success is NOT answer correctness: "
        "retrieving relevant context is necessary for evidence grounding, but generating an accurate, compliant "
        "answer still requires strict citation formatting, guardrail validation, and refusal of out-of-scope queries."
    )

    # Save JSON report
    report_file = RESULTS_DIR / f"comparison_{split}.json"
    report_file.write_text(json.dumps(results, indent=2), encoding="utf-8")

    # Generate Markdown report
    lines = [
        f"# Retrieval Evaluation Report: Keyword vs Vector vs Hybrid",
        f"",
        f"- **Date**: {ts}",
        f"- **Evaluation split**: `{split}` ({SPLIT_DESCRIPTIONS.get(split, 'Evaluation set')})",
        f"- **Metric**: Recall@{k} on reviewed supported cases",
        f"- **Embedding Provider / Model**: `{config_info.get('embedding_provider')}` / `{config_info.get('embedding_model')}` (dim={config_info.get('embedding_dim')})",
        f"- **Vectors**: {config_info.get('retrieval_note')}",
        f"- **Corpus**: `{config_info.get('corpus_chunks')}` chunks (version: `{config_info.get('corpus_version')}`)",
        f"",
        f"> **What Recall@{k} counts**: A query scores a hit (1.0) if any chunk from its `expected_chunk_ids` appears in the top {k} results; otherwise 0.0.",
        f"> **Important Distinction**: *Retrieval success is not answer correctness.* A hit proves evidence was supplied to the context window, but does not guarantee the LLM interprets it properly or obeys guardrails.",
        f"",
        f"| Metric | Keyword (BM25) | Vector Search | Hybrid (BM25 + Vector + RRF) |",
        f"|---|---|---|---|",
    ]

    kw = results.get("keyword")
    vec = results.get("vector")
    hy = results.get("hybrid")

    def format_rec(m):
        return f"{m['hits']}/{m['total']} ({m['recall_at_k']*100:.1f}%)" if m else "N/A"

    def format_lat(m, key):
        return f"{m[key]:.2f} ms" if m else "N/A"

    def format_misses(m):
        return (", ".join(m["missed_cases"]) or "None") if m else "N/A"

    lines.append(f"| Recall@{k} | {format_rec(kw)} | {format_rec(vec)} | {format_rec(hy)} |")
    lines.append(f"| Median Latency | {format_lat(kw, 'median_latency_ms')} | {format_lat(vec, 'median_latency_ms')} | {format_lat(hy, 'median_latency_ms')} |")
    lines.append(f"| p95 Latency | {format_lat(kw, 'p95_latency_ms')} | {format_lat(vec, 'p95_latency_ms')} | {format_lat(hy, 'p95_latency_ms')} |")
    lines.append(f"| Missed cases | {format_misses(kw)} | {format_misses(vec)} | {format_misses(hy)} |")

    lines.append("")
    lines.append("## Case-by-case Breakdown")
    lines.append("")
    lines.append("| ID | Split | Question | Keyword Hit | Vector Hit | Hybrid Hit | Expected Chunks |")
    lines.append("|---|---|---|---|---|---|---|")

    primary_details = (kw or hy or vec)["details"]
    kw_map = {d["id"]: d["matched"] for d in kw["details"]} if kw else {}
    vec_map = {d["id"]: d["matched"] for d in vec["details"]} if vec else {}
    hy_map = {d["id"]: d["matched"] for d in hy["details"]} if hy else {}

    for d in primary_details:
        qid = d["id"]
        q_esc = d["question"].replace("|", "&#124;")
        kw_status = "PASS" if kw_map.get(qid) else ("FAIL" if qid in kw_map else "-")
        vec_status = "PASS" if vec_map.get(qid) else ("FAIL" if qid in vec_map else "-")
        hy_status = "PASS" if hy_map.get(qid) else ("FAIL" if qid in hy_map else "-")
        lines.append(f"| {qid} | {d['split']} | {q_esc} | {kw_status} | {vec_status} | {hy_status} | `{', '.join(d['expected_chunk_ids'])}` |")

    lines.append("")
    summary_file = RESULTS_DIR / f"summary_{split}.md"
    summary_file.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"Saved evaluation results to {report_file} and {summary_file}")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--split", choices=["dev", "held_out", "frozen_holdout", "all", "full"], default="all")
    ap.add_argument("--mode", choices=["keyword", "vector", "hybrid", "both", "all"], default="all")
    ap.add_argument("--k", type=int, default=5)
    ap.add_argument("--no-save", action="store_true", help="Do not save results to eval/results/")
    a = ap.parse_args()

    raw_cases = load_cases(a.split)
    cases = [c for c in raw_cases if c.get("category") == "supported" and c.get("reviewed") and c.get("expected_chunk_ids")]
    docs = load_corpus()

    if not docs or not cases:
        print(f"Nothing to score: corpus chunks={len(docs)}, reviewed supported cases={len(cases)}. Fill and review cases first.")
        return

    settings = load_settings()
    provider = settings.embedding_provider or "fake"
    chunks_path = pathlib.Path(settings.chunks_path)
    if not chunks_path.exists():
        chunks_path = FIXTURES_CORPUS
    emb_path = pathlib.Path(settings.embeddings_path)
    if provider == "fake":
        embedder = FakeEmbedder(dim=settings.embedding_dim)
        if not emb_path.exists():
            emb_path = FIXTURES_EMBEDDINGS
    else:
        embedder = build_embedder(settings)
    need_vectors = a.mode in ("vector", "hybrid", "both", "all")
    embeddings, vmeta = {}, {}
    if need_vectors:
        try:   # validates EVERY vector: dimension, provider/model, corpus hash, full checksum; rejects fake in real mode
            vmeta, embeddings = validate_vector_store(settings, emb_path, chunks_path)
        except Exception as exc:
            print(f"STOPPED: vectors are not usable: {exc}")
            raise SystemExit(2)
    is_fake_vectors = bool(vmeta.get("is_fake")) or provider == "fake"
    holdout_pin = ROOT / "holdout.sha256"
    if a.split in ("frozen_holdout", "full") and holdout_pin.exists():
        want = holdout_pin.read_text().split()[0]
        got = compute_file_hash(ROOT / "questions.frozen_holdout.jsonl")
        if want != got:
            print(f"STOPPED: questions.frozen_holdout.jsonl changed after it was pinned ({got[:12]} != {want[:12]}). Record why, then re-pin.")
            raise SystemExit(2)

    config_info = {
        "k": a.k,
        "corpus_chunks": len(docs),
        "corpus_hash": compute_file_hash(chunks_path),
        "corpus_version": settings.corpus_version or "unversioned",
        "embedding_provider": provider,
        "embedding_model": getattr(embedder, "model", settings.embedding_model or "unknown"),
        "embedding_dim": settings.embedding_dim,
        "vector_file": str(emb_path.name) if need_vectors else None,
        "vector_checksum": vmeta.get("checksum"),
        "vectors_are_fake": is_fake_vectors if need_vectors else None,
        "rrf_k": 60,
        "retrieval_note": ("Vector and hybrid numbers below use FAKE hash vectors: they measure word overlap, NOT semantic search."
                           if (need_vectors and is_fake_vectors) else "Real embedding model vectors."),
    }

    results = {}
    print(f"=== Evaluating on {len(cases)} supported cases (split: {a.split}, k={a.k}) ===")
    print(f"Configuration: provider={config_info['embedding_provider']}, model={config_info['embedding_model']} (dim={config_info['embedding_dim']})")

    # Run Keyword
    if a.mode in ("keyword", "both", "all"):
        bm25 = BM25(docs)
        kw_res = evaluate_retriever("keyword_bm25", bm25, cases, k=a.k)
        results["keyword"] = kw_res
        print(f"Keyword (BM25) Recall@{a.k}: {kw_res['hits']}/{kw_res['total']} ({kw_res['recall_at_k']*100:.1f}%)")
        print(f"  Latency: median {kw_res['median_latency_ms']:.2f} ms | p95 {kw_res['p95_latency_ms']:.2f} ms")
        print(f"  Misses: {kw_res['missed_cases'] or 'none'}")

    # Run Vector
    if a.mode in ("vector", "all"):
        vs = VectorSearch(docs, embeddings=embeddings, embedder=embedder)
        vec_res = evaluate_retriever("vector_search", vs, cases, k=a.k)
        results["vector"] = vec_res
        print(f"Vector Search Recall@{a.k}: {vec_res['hits']}/{vec_res['total']} ({vec_res['recall_at_k']*100:.1f}%)")
        print(f"  Latency: median {vec_res['median_latency_ms']:.2f} ms | p95 {vec_res['p95_latency_ms']:.2f} ms")
        print(f"  Misses: {vec_res['missed_cases'] or 'none'}")

    # Run Hybrid
    if a.mode in ("hybrid", "both", "all"):
        vs = VectorSearch(docs, embeddings=embeddings, embedder=embedder)
        hybrid = HybridRetriever(docs, bm25=BM25(docs), vector_search=vs, rrf_k=60)
        hy_res = evaluate_retriever("hybrid_rrf", hybrid, cases, k=a.k)
        results["hybrid"] = hy_res
        print(f"Hybrid (BM25 + Vector + RRF) Recall@{a.k}: {hy_res['hits']}/{hy_res['total']} ({hy_res['recall_at_k']*100:.1f}%)")
        print(f"  Latency: median {hy_res['median_latency_ms']:.2f} ms | p95 {hy_res['p95_latency_ms']:.2f} ms")
        print(f"  Misses: {hy_res['missed_cases'] or 'none'}")

    if not a.no_save:
        save_reports(results, a.split, a.k, config_info)


if __name__ == "__main__":
    main()
