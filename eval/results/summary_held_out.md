# Retrieval Evaluation Report: Keyword vs Vector vs Hybrid

- **Date**: 2026-10-14T22:22:08.118436+00:00
- **Evaluation split**: `held_out` (Original holdout set (previously inspected; not an untouched blind set))
- **Metric**: Recall@5 on reviewed supported cases
- **Embedding Provider / Model**: `fake` / `fake-hash-embedder` (dim=1536)
- **Vectors**: Vector and hybrid numbers below use FAKE hash vectors: they measure word overlap, NOT semantic search.
- **Corpus**: `93` chunks (version: `2026-10-12-snapshot`)

> **What Recall@5 counts**: A query scores a hit (1.0) if any chunk from its `expected_chunk_ids` appears in the top 5 results; otherwise 0.0.
> **Important Distinction**: *Retrieval success is not answer correctness.* A hit proves evidence was supplied to the context window, but does not guarantee the LLM interprets it properly or obeys guardrails.

| Metric | Keyword (BM25) | Vector Search | Hybrid (BM25 + Vector + RRF) |
|---|---|---|---|
| Recall@5 | 11/12 (91.7%) | 10/12 (83.3%) | 12/12 (100.0%) |
| Median Latency | 0.59 ms | 4.42 ms | 6.58 ms |
| p95 Latency | 0.74 ms | 70.60 ms | 7.20 ms |
| Missed cases | held-09 | held-05, held-08 | None |

## Case-by-case Breakdown

| ID | Split | Question | Keyword Hit | Vector Hit | Hybrid Hit | Expected Chunks |
|---|---|---|---|---|---|---|
| held-01 | held_out | How much is the Graduate visa application fee? | PASS | PASS | PASS | `graduate-costs#1` |
| held-02 | held_out | Can I study while on a Graduate visa? | PASS | PASS | PASS | `graduate-overview#11` |
| held-03 | held_out | Do I have to pay the healthcare surcharge on a Graduate visa? | PASS | PASS | PASS | `graduate-costs#3, graduate-costs#2, graduate-costs#1` |
| held-04 | held_out | What is the standard salary requirement for a Skilled Worker visa? | PASS | PASS | PASS | `skilled-worker-salary-exceptions#1, skilled-worker-your-job#5` |
| held-05 | held_out | How much personal savings do I need to support myself for a Skilled Worker visa? | PASS | FAIL | PASS | `skilled-worker-costs#5, skilled-worker-costs#4` |
| held-06 | held_out | How can I prove my knowledge of English for Skilled Worker? | PASS | PASS | PASS | `skilled-worker-english#5, skilled-worker-english#1` |
| held-07 | held_out | Who cannot apply to switch to a Skilled Worker visa from inside the UK? | PASS | PASS | PASS | `skilled-worker-switching#4` |
| held-08 | held_out | How long does a Skilled Worker visa last before needing extension? | PASS | FAIL | PASS | `skilled-worker-overview#5, skilled-worker-extend#1, skilled-worker-extend#2, skilled-worker-extend#5` |
| held-09 | held_out | What is the lower salary threshold if I am under 26 or a recent graduate? | FAIL | PASS | PASS | `skilled-worker-salary-exceptions#1, skilled-worker-salary-exceptions#3` |
| held-10 | held_out | Can I travel outside the UK while my switching application is pending? | PASS | PASS | PASS | `skilled-worker-switching#1` |
| held-11 | held_out | Can I work as a professional sportsperson on a Graduate visa? | PASS | PASS | PASS | `graduate-overview#10` |
| held-12 | held_out | How much does an employer pay for a sponsor licence? | PASS | PASS | PASS | `skilled-worker-your-job#9` |

