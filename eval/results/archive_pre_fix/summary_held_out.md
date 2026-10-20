# Retrieval Evaluation Report: Keyword vs Vector vs Hybrid

- **Date**: 2026-10-14T21:44:43.662160+00:00
- **Evaluation split**: `held_out` (Original holdout set (previously inspected; not an untouched blind set))
- **Metric**: Recall@5 on reviewed supported cases
- **Embedding Provider / Model**: `fake` / `fake-hash-embedder` (dim=64)
- **Corpus**: `93` chunks (version: `2026-10-12-draft`)

> **What Recall@5 counts**: A query scores a hit (1.0) if any chunk from its `expected_chunk_ids` appears in the top 5 results; otherwise 0.0.
> **Important Distinction**: *Retrieval success is not answer correctness.* A hit proves evidence was supplied to the context window, but does not guarantee the LLM interprets it properly or obeys guardrails.

| Metric | Keyword (BM25) | Vector Search | Hybrid (BM25 + Vector + RRF) |
|---|---|---|---|
| Recall@5 | 11/12 (91.7%) | 1/12 (8.3%) | 5/12 (41.7%) |
| Median Latency | 0.96 ms | 9.42 ms | 10.56 ms |
| p95 Latency | 1.13 ms | 10.33 ms | 11.26 ms |
| Missed cases | held-09 | held-01, held-02, held-03, held-04, held-06, held-07, held-08, held-09, held-10, held-11, held-12 | held-02, held-03, held-04, held-06, held-07, held-08, held-12 |

## Case-by-case Breakdown

| ID | Split | Question | Keyword Hit | Vector Hit | Hybrid Hit | Expected Chunks |
|---|---|---|---|---|---|---|
| held-01 | held_out | How much is the Graduate visa application fee? | PASS | FAIL | PASS | `graduate-costs#1` |
| held-02 | held_out | Can I study while on a Graduate visa? | PASS | FAIL | FAIL | `graduate-overview#11` |
| held-03 | held_out | Do I have to pay the healthcare surcharge on a Graduate visa? | PASS | FAIL | FAIL | `graduate-costs#3, graduate-costs#2, graduate-costs#1` |
| held-04 | held_out | What is the standard salary requirement for a Skilled Worker visa? | PASS | FAIL | FAIL | `skilled-worker-your-job#5, skilled-worker-salary-exceptions#1` |
| held-05 | held_out | How much personal savings do I need to support myself for a Skilled Worker visa? | PASS | PASS | PASS | `skilled-worker-costs#4, skilled-worker-costs#5` |
| held-06 | held_out | How can I prove my knowledge of English for Skilled Worker? | PASS | FAIL | FAIL | `skilled-worker-english#1, skilled-worker-english#5` |
| held-07 | held_out | Who cannot apply to switch to a Skilled Worker visa from inside the UK? | PASS | FAIL | FAIL | `skilled-worker-switching#4` |
| held-08 | held_out | How long does a Skilled Worker visa last before needing extension? | PASS | FAIL | FAIL | `skilled-worker-extend#1, skilled-worker-overview#5, skilled-worker-extend#2, skilled-worker-extend#5` |
| held-09 | held_out | What is the lower salary threshold if I am under 26 or a recent graduate? | FAIL | FAIL | PASS | `skilled-worker-salary-exceptions#1, skilled-worker-salary-exceptions#3` |
| held-10 | held_out | Can I travel outside the UK while my switching application is pending? | PASS | FAIL | PASS | `skilled-worker-switching#1` |
| held-11 | held_out | Can I work as a professional sportsperson on a Graduate visa? | PASS | FAIL | PASS | `graduate-overview#10` |
| held-12 | held_out | How much does an employer pay for a sponsor licence? | PASS | FAIL | FAIL | `skilled-worker-your-job#9` |

