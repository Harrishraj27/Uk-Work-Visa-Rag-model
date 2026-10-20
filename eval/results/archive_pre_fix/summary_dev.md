# Retrieval Evaluation Report: Keyword vs Vector vs Hybrid

- **Date**: 2026-10-14T21:44:43.112888+00:00
- **Evaluation split**: `dev` (Development tuning set (inspected for error analysis and parameter calibration))
- **Metric**: Recall@5 on reviewed supported cases
- **Embedding Provider / Model**: `fake` / `fake-hash-embedder` (dim=64)
- **Corpus**: `93` chunks (version: `2026-10-12-draft`)

> **What Recall@5 counts**: A query scores a hit (1.0) if any chunk from its `expected_chunk_ids` appears in the top 5 results; otherwise 0.0.
> **Important Distinction**: *Retrieval success is not answer correctness.* A hit proves evidence was supplied to the context window, but does not guarantee the LLM interprets it properly or obeys guardrails.

| Metric | Keyword (BM25) | Vector Search | Hybrid (BM25 + Vector + RRF) |
|---|---|---|---|
| Recall@5 | 11/12 (91.7%) | 2/12 (16.7%) | 9/12 (75.0%) |
| Median Latency | 0.96 ms | 9.47 ms | 10.44 ms |
| p95 Latency | 1.06 ms | 9.89 ms | 10.74 ms |
| Missed cases | dev-08 | dev-01, dev-03, dev-04, dev-05, dev-06, dev-07, dev-08, dev-09, dev-10, dev-12 | dev-05, dev-06, dev-08 |

## Case-by-case Breakdown

| ID | Split | Question | Keyword Hit | Vector Hit | Hybrid Hit | Expected Chunks |
|---|---|---|---|---|---|---|
| dev-01 | dev | What is a certificate of sponsorship? | PASS | FAIL | PASS | `skilled-worker-your-job#11, skilled-worker-overview#2, skilled-worker-documents#1` |
| dev-02 | dev | Does a sponsor licence mean every vacancy sponsors? | PASS | PASS | PASS | `skilled-worker-your-job#9, sponsor-licence#1` |
| dev-03 | dev | Can I extend a Graduate visa? | PASS | FAIL | PASS | `graduate-overview#4` |
| dev-04 | dev | How long can I stay on a Graduate visa? | PASS | FAIL | PASS | `graduate-overview#3` |
| dev-05 | dev | Can I switch from a Graduate visa to Skilled Worker? | PASS | FAIL | FAIL | `graduate-overview#4, skilled-worker-switching#4, skilled-worker-switching#1` |
| dev-06 | dev | When should I apply to switch to a Skilled Worker visa? | PASS | FAIL | FAIL | `skilled-worker-switching#8, skilled-worker-switching#1, skilled-worker-overview#8` |
| dev-07 | dev | What does the Graduate visa allow me to do for work? | PASS | FAIL | PASS | `graduate-overview#10` |
| dev-08 | dev | What does 'your job' need to meet for a Skilled Worker visa? | FAIL | FAIL | FAIL | `skilled-worker-overview#2, skilled-worker-your-job#1` |
| dev-09 | dev | What are occupation codes in the Skilled Worker route? | PASS | FAIL | PASS | `skilled-worker-your-job#3, skilled-worker-your-job#4` |
| dev-10 | dev | What are approved employers for Skilled Worker? | PASS | FAIL | PASS | `skilled-worker-overview#1, skilled-worker-your-job#9` |
| dev-11 | dev | Where do salary exceptions for Skilled Worker apply? | PASS | PASS | PASS | `skilled-worker-your-job#8, skilled-worker-salary-exceptions#1` |
| dev-12 | dev | What documents do I need for a Skilled Worker application? | PASS | FAIL | PASS | `skilled-worker-switching#7, skilled-worker-extend#12, skilled-worker-documents#2, skilled-worker-documents#1` |

