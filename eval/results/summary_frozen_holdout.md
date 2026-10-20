# Retrieval Evaluation Report: Keyword vs Vector vs Hybrid

- **Date**: 2026-10-14T22:22:08.926256+00:00
- **Evaluation split**: `frozen_holdout` (Second holdout written by the same author after the first was inspected. Hash-pinned (eval/holdout.sha256) but NOT independent proof of generalisation)
- **Metric**: Recall@5 on reviewed supported cases
- **Embedding Provider / Model**: `fake` / `fake-hash-embedder` (dim=1536)
- **Vectors**: Vector and hybrid numbers below use FAKE hash vectors: they measure word overlap, NOT semantic search.
- **Corpus**: `93` chunks (version: `2026-10-12-snapshot`)

> **What Recall@5 counts**: A query scores a hit (1.0) if any chunk from its `expected_chunk_ids` appears in the top 5 results; otherwise 0.0.
> **Important Distinction**: *Retrieval success is not answer correctness.* A hit proves evidence was supplied to the context window, but does not guarantee the LLM interprets it properly or obeys guardrails.

| Metric | Keyword (BM25) | Vector Search | Hybrid (BM25 + Vector + RRF) |
|---|---|---|---|
| Recall@5 | 10/11 (90.9%) | 5/11 (45.5%) | 10/11 (90.9%) |
| Median Latency | 0.64 ms | 4.18 ms | 6.87 ms |
| p95 Latency | 0.71 ms | 62.15 ms | 8.41 ms |
| Missed cases | frozen-11 | frozen-02, frozen-03, frozen-06, frozen-08, frozen-10, frozen-11 | frozen-11 |

## Case-by-case Breakdown

| ID | Split | Question | Keyword Hit | Vector Hit | Hybrid Hit | Expected Chunks |
|---|---|---|---|---|---|---|
| frozen-02 | frozen_holdout | Do I need a criminal record certificate for a Skilled Worker visa? | PASS | FAIL | PASS | `skilled-worker-documents#3` |
| frozen-03 | frozen_holdout | What happens if I want to change my employer on a Skilled Worker visa? | PASS | FAIL | PASS | `skilled-worker-extend#3, skilled-worker-overview#5` |
| frozen-04 | frozen_holdout | What reference number from my university do I need for a Graduate visa? | PASS | PASS | PASS | `graduate-documents#1` |
| frozen-05 | frozen_holdout | Can I stay in the UK while waiting for my Graduate visa decision? | PASS | PASS | PASS | `graduate-overview#7` |
| frozen-06 | frozen_holdout | Which countries are exempt from the English language requirement for Skilled Worker? | PASS | FAIL | PASS | `skilled-worker-english#7` |
| frozen-07 | frozen_holdout | How much is the Skilled Worker application fee from inside the UK for up to 3 years? | PASS | PASS | PASS | `skilled-worker-costs#2` |
| frozen-08 | frozen_holdout | Can I apply for indefinite leave to remain after 5 years on a Skilled Worker visa? | PASS | FAIL | PASS | `skilled-worker-overview#5` |
| frozen-09 | frozen_holdout | Can I get a refund on the healthcare surcharge if I work in public healthcare? | PASS | PASS | PASS | `graduate-costs#3, skilled-worker-costs#1` |
| frozen-10 | frozen_holdout | Can my employer sponsor my visa if their licence application is still pending? | PASS | FAIL | PASS | `skilled-worker-your-job#9, sponsor-licence#1` |
| frozen-11 | frozen_holdout | Can I switch to a Graduate visa from a visitor visa? | FAIL | FAIL | FAIL | `graduate-overview#2` |
| frozen-12 | frozen_holdout | Can I do voluntary work while on a Graduate visa? | PASS | PASS | PASS | `graduate-overview#10` |

