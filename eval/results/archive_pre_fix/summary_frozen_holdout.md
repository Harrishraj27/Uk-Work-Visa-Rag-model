# Retrieval Evaluation Report: Keyword vs Vector vs Hybrid

- **Date**: 2026-10-14T21:44:45.294939+00:00
- **Evaluation split**: `frozen_holdout` (Newly frozen independent holdout set (SHA-256 pinned; untouched for generalization))
- **Metric**: Recall@5 on reviewed supported cases
- **Embedding Provider / Model**: `fake` / `fake-hash-embedder` (dim=64)
- **Corpus**: `93` chunks (version: `2026-10-12-draft`)

> **What Recall@5 counts**: A query scores a hit (1.0) if any chunk from its `expected_chunk_ids` appears in the top 5 results; otherwise 0.0.
> **Important Distinction**: *Retrieval success is not answer correctness.* A hit proves evidence was supplied to the context window, but does not guarantee the LLM interprets it properly or obeys guardrails.

| Metric | Keyword (BM25) | Vector Search | Hybrid (BM25 + Vector + RRF) |
|---|---|---|---|
| Recall@5 | 9/12 (75.0%) | 2/12 (16.7%) | 5/12 (41.7%) |
| Median Latency | 1.24 ms | 11.19 ms | 12.14 ms |
| p95 Latency | 1.76 ms | 12.35 ms | 14.18 ms |
| Missed cases | frozen-01, frozen-06, frozen-11 | frozen-01, frozen-02, frozen-03, frozen-06, frozen-07, frozen-08, frozen-09, frozen-10, frozen-11, frozen-12 | frozen-01, frozen-02, frozen-03, frozen-06, frozen-08, frozen-10, frozen-11 |

## Case-by-case Breakdown

| ID | Split | Question | Keyword Hit | Vector Hit | Hybrid Hit | Expected Chunks |
|---|---|---|---|---|---|---|
| frozen-01 | frozen_holdout | Can I take on a second job on a Skilled Worker visa? | FAIL | FAIL | FAIL | `skilled-worker-overview#10` |
| frozen-02 | frozen_holdout | Do I need a criminal record certificate for a Skilled Worker visa? | PASS | FAIL | FAIL | `skilled-worker-documents#3` |
| frozen-03 | frozen_holdout | What happens if I want to change my employer on a Skilled Worker visa? | PASS | FAIL | FAIL | `skilled-worker-extend#3, skilled-worker-overview#5` |
| frozen-04 | frozen_holdout | What reference number from my university do I need for a Graduate visa? | PASS | PASS | PASS | `graduate-documents#1` |
| frozen-05 | frozen_holdout | Can I stay in the UK while waiting for my Graduate visa decision? | PASS | PASS | PASS | `graduate-overview#7` |
| frozen-06 | frozen_holdout | Which countries are exempt from the English language requirement for Skilled Worker? | FAIL | FAIL | FAIL | `skilled-worker-english#2` |
| frozen-07 | frozen_holdout | How much is the Skilled Worker application fee from inside the UK for up to 3 years? | PASS | FAIL | PASS | `skilled-worker-costs#2` |
| frozen-08 | frozen_holdout | Can I apply for indefinite leave to remain after 5 years on a Skilled Worker visa? | PASS | FAIL | FAIL | `skilled-worker-overview#5` |
| frozen-09 | frozen_holdout | Can I get a refund on the healthcare surcharge if I work in public healthcare? | PASS | FAIL | PASS | `skilled-worker-costs#1, graduate-costs#3` |
| frozen-10 | frozen_holdout | Can my employer sponsor my visa if their licence application is still pending? | PASS | FAIL | FAIL | `sponsor-licence#1, skilled-worker-your-job#9` |
| frozen-11 | frozen_holdout | Can I switch to a Graduate visa from a visitor visa? | FAIL | FAIL | FAIL | `graduate-overview#2` |
| frozen-12 | frozen_holdout | Can I do voluntary work while on a Graduate visa? | PASS | FAIL | PASS | `graduate-overview#10` |

