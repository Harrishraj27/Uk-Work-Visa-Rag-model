# Retrieval Evaluation Report: Keyword vs Vector vs Hybrid

- **Date**: 2026-10-14T22:22:08.570026+00:00
- **Evaluation split**: `all` (Combined baseline benchmark (dev + held_out, 24 supported cases))
- **Metric**: Recall@5 on reviewed supported cases
- **Embedding Provider / Model**: `fake` / `fake-hash-embedder` (dim=1536)
- **Vectors**: Vector and hybrid numbers below use FAKE hash vectors: they measure word overlap, NOT semantic search.
- **Corpus**: `93` chunks (version: `2026-10-12-snapshot`)

> **What Recall@5 counts**: A query scores a hit (1.0) if any chunk from its `expected_chunk_ids` appears in the top 5 results; otherwise 0.0.
> **Important Distinction**: *Retrieval success is not answer correctness.* A hit proves evidence was supplied to the context window, but does not guarantee the LLM interprets it properly or obeys guardrails.

| Metric | Keyword (BM25) | Vector Search | Hybrid (BM25 + Vector + RRF) |
|---|---|---|---|
| Recall@5 | 22/24 (91.7%) | 19/24 (79.2%) | 23/24 (95.8%) |
| Median Latency | 0.56 ms | 4.20 ms | 4.92 ms |
| p95 Latency | 0.83 ms | 35.31 ms | 5.46 ms |
| Missed cases | dev-08, held-09 | dev-08, dev-11, dev-12, held-05, held-08 | dev-12 |

## Case-by-case Breakdown

| ID | Split | Question | Keyword Hit | Vector Hit | Hybrid Hit | Expected Chunks |
|---|---|---|---|---|---|---|
| dev-01 | dev | What is a certificate of sponsorship? | PASS | PASS | PASS | `skilled-worker-your-job#11, skilled-worker-documents#1, skilled-worker-overview#2` |
| dev-02 | dev | Does a sponsor licence mean every vacancy sponsors? | PASS | PASS | PASS | `sponsor-licence#1, skilled-worker-your-job#9` |
| dev-03 | dev | Can I extend a Graduate visa? | PASS | PASS | PASS | `graduate-overview#4` |
| dev-04 | dev | How long can I stay on a Graduate visa? | PASS | PASS | PASS | `graduate-overview#3` |
| dev-05 | dev | Can I switch from a Graduate visa to Skilled Worker? | PASS | PASS | PASS | `skilled-worker-switching#1, skilled-worker-switching#4, graduate-overview#4` |
| dev-06 | dev | When should I apply to switch to a Skilled Worker visa? | PASS | PASS | PASS | `skilled-worker-overview#8, skilled-worker-switching#1, skilled-worker-switching#8` |
| dev-07 | dev | What does the Graduate visa allow me to do for work? | PASS | PASS | PASS | `graduate-overview#10` |
| dev-08 | dev | What does 'your job' need to meet for a Skilled Worker visa? | FAIL | FAIL | PASS | `skilled-worker-your-job#1, skilled-worker-overview#2` |
| dev-09 | dev | What are occupation codes in the Skilled Worker route? | PASS | PASS | PASS | `skilled-worker-your-job#4, skilled-worker-your-job#3` |
| dev-10 | dev | What are approved employers for Skilled Worker? | PASS | PASS | PASS | `skilled-worker-your-job#9, skilled-worker-overview#1` |
| dev-11 | dev | Where do salary exceptions for Skilled Worker apply? | PASS | FAIL | PASS | `skilled-worker-your-job#8, skilled-worker-salary-exceptions#1` |
| dev-12 | dev | What documents do I need for a Skilled Worker application? | PASS | FAIL | FAIL | `skilled-worker-switching#7, skilled-worker-documents#2, skilled-worker-documents#1, skilled-worker-extend#12` |
| held-01 | held_out | How much is the Graduate visa application fee? | PASS | PASS | PASS | `graduate-costs#1` |
| held-02 | held_out | Can I study while on a Graduate visa? | PASS | PASS | PASS | `graduate-overview#11` |
| held-03 | held_out | Do I have to pay the healthcare surcharge on a Graduate visa? | PASS | PASS | PASS | `graduate-costs#2, graduate-costs#1, graduate-costs#3` |
| held-04 | held_out | What is the standard salary requirement for a Skilled Worker visa? | PASS | PASS | PASS | `skilled-worker-your-job#5, skilled-worker-salary-exceptions#1` |
| held-05 | held_out | How much personal savings do I need to support myself for a Skilled Worker visa? | PASS | FAIL | PASS | `skilled-worker-costs#4, skilled-worker-costs#5` |
| held-06 | held_out | How can I prove my knowledge of English for Skilled Worker? | PASS | PASS | PASS | `skilled-worker-english#1, skilled-worker-english#5` |
| held-07 | held_out | Who cannot apply to switch to a Skilled Worker visa from inside the UK? | PASS | PASS | PASS | `skilled-worker-switching#4` |
| held-08 | held_out | How long does a Skilled Worker visa last before needing extension? | PASS | FAIL | PASS | `skilled-worker-extend#5, skilled-worker-overview#5, skilled-worker-extend#2, skilled-worker-extend#1` |
| held-09 | held_out | What is the lower salary threshold if I am under 26 or a recent graduate? | FAIL | PASS | PASS | `skilled-worker-salary-exceptions#3, skilled-worker-salary-exceptions#1` |
| held-10 | held_out | Can I travel outside the UK while my switching application is pending? | PASS | PASS | PASS | `skilled-worker-switching#1` |
| held-11 | held_out | Can I work as a professional sportsperson on a Graduate visa? | PASS | PASS | PASS | `graduate-overview#10` |
| held-12 | held_out | How much does an employer pay for a sponsor licence? | PASS | PASS | PASS | `skilled-worker-your-job#9` |

