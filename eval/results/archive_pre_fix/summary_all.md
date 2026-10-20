# Retrieval Evaluation Report: Keyword vs Vector vs Hybrid

- **Date**: 2026-10-14T21:44:44.615047+00:00
- **Evaluation split**: `all` (Combined baseline benchmark (dev + held_out, 24 supported cases))
- **Metric**: Recall@5 on reviewed supported cases
- **Embedding Provider / Model**: `fake` / `fake-hash-embedder` (dim=64)
- **Corpus**: `93` chunks (version: `2026-10-12-draft`)

> **What Recall@5 counts**: A query scores a hit (1.0) if any chunk from its `expected_chunk_ids` appears in the top 5 results; otherwise 0.0.
> **Important Distinction**: *Retrieval success is not answer correctness.* A hit proves evidence was supplied to the context window, but does not guarantee the LLM interprets it properly or obeys guardrails.

| Metric | Keyword (BM25) | Vector Search | Hybrid (BM25 + Vector + RRF) |
|---|---|---|---|
| Recall@5 | 22/24 (91.7%) | 3/24 (12.5%) | 14/24 (58.3%) |
| Median Latency | 1.04 ms | 10.46 ms | 12.86 ms |
| p95 Latency | 1.18 ms | 13.88 ms | 14.75 ms |
| Missed cases | dev-08, held-09 | dev-01, dev-03, dev-04, dev-05, dev-06, dev-07, dev-08, dev-09, dev-10, dev-12, held-01, held-02, held-03, held-04, held-06, held-07, held-08, held-09, held-10, held-11, held-12 | dev-05, dev-06, dev-08, held-02, held-03, held-04, held-06, held-07, held-08, held-12 |

## Case-by-case Breakdown

| ID | Split | Question | Keyword Hit | Vector Hit | Hybrid Hit | Expected Chunks |
|---|---|---|---|---|---|---|
| dev-01 | dev | What is a certificate of sponsorship? | PASS | FAIL | PASS | `skilled-worker-overview#2, skilled-worker-documents#1, skilled-worker-your-job#11` |
| dev-02 | dev | Does a sponsor licence mean every vacancy sponsors? | PASS | PASS | PASS | `skilled-worker-your-job#9, sponsor-licence#1` |
| dev-03 | dev | Can I extend a Graduate visa? | PASS | FAIL | PASS | `graduate-overview#4` |
| dev-04 | dev | How long can I stay on a Graduate visa? | PASS | FAIL | PASS | `graduate-overview#3` |
| dev-05 | dev | Can I switch from a Graduate visa to Skilled Worker? | PASS | FAIL | FAIL | `skilled-worker-switching#4, skilled-worker-switching#1, graduate-overview#4` |
| dev-06 | dev | When should I apply to switch to a Skilled Worker visa? | PASS | FAIL | FAIL | `skilled-worker-switching#8, skilled-worker-switching#1, skilled-worker-overview#8` |
| dev-07 | dev | What does the Graduate visa allow me to do for work? | PASS | FAIL | PASS | `graduate-overview#10` |
| dev-08 | dev | What does 'your job' need to meet for a Skilled Worker visa? | FAIL | FAIL | FAIL | `skilled-worker-your-job#1, skilled-worker-overview#2` |
| dev-09 | dev | What are occupation codes in the Skilled Worker route? | PASS | FAIL | PASS | `skilled-worker-your-job#3, skilled-worker-your-job#4` |
| dev-10 | dev | What are approved employers for Skilled Worker? | PASS | FAIL | PASS | `skilled-worker-your-job#9, skilled-worker-overview#1` |
| dev-11 | dev | Where do salary exceptions for Skilled Worker apply? | PASS | PASS | PASS | `skilled-worker-salary-exceptions#1, skilled-worker-your-job#8` |
| dev-12 | dev | What documents do I need for a Skilled Worker application? | PASS | FAIL | PASS | `skilled-worker-documents#2, skilled-worker-extend#12, skilled-worker-documents#1, skilled-worker-switching#7` |
| held-01 | held_out | How much is the Graduate visa application fee? | PASS | FAIL | PASS | `graduate-costs#1` |
| held-02 | held_out | Can I study while on a Graduate visa? | PASS | FAIL | FAIL | `graduate-overview#11` |
| held-03 | held_out | Do I have to pay the healthcare surcharge on a Graduate visa? | PASS | FAIL | FAIL | `graduate-costs#1, graduate-costs#3, graduate-costs#2` |
| held-04 | held_out | What is the standard salary requirement for a Skilled Worker visa? | PASS | FAIL | FAIL | `skilled-worker-salary-exceptions#1, skilled-worker-your-job#5` |
| held-05 | held_out | How much personal savings do I need to support myself for a Skilled Worker visa? | PASS | PASS | PASS | `skilled-worker-costs#5, skilled-worker-costs#4` |
| held-06 | held_out | How can I prove my knowledge of English for Skilled Worker? | PASS | FAIL | FAIL | `skilled-worker-english#1, skilled-worker-english#5` |
| held-07 | held_out | Who cannot apply to switch to a Skilled Worker visa from inside the UK? | PASS | FAIL | FAIL | `skilled-worker-switching#4` |
| held-08 | held_out | How long does a Skilled Worker visa last before needing extension? | PASS | FAIL | FAIL | `skilled-worker-extend#5, skilled-worker-overview#5, skilled-worker-extend#1, skilled-worker-extend#2` |
| held-09 | held_out | What is the lower salary threshold if I am under 26 or a recent graduate? | FAIL | FAIL | PASS | `skilled-worker-salary-exceptions#1, skilled-worker-salary-exceptions#3` |
| held-10 | held_out | Can I travel outside the UK while my switching application is pending? | PASS | FAIL | PASS | `skilled-worker-switching#1` |
| held-11 | held_out | Can I work as a professional sportsperson on a Graduate visa? | PASS | FAIL | PASS | `graduate-overview#10` |
| held-12 | held_out | How much does an employer pay for a sponsor licence? | PASS | FAIL | FAIL | `skilled-worker-your-job#9` |

