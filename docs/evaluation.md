# Evaluation protocol (proposed design, not results)

40 manually checked questions: 20 dev + 20 held out. Per split: 12 supported, 4 ambiguous/unsupported, 4 adversarial/freshness.
Per case save: ID, question, category, expected answer points or refusal, source URL, exact supporting passage, snapshot hash, expected chunk/section.

Measure separately (report n/N, never bare "accuracy"):
1. **Retrieval recall@5** on supported cases (`python -m eval.run_eval`).
2. **Answer correctness**: manual pass/fail vs expected points, including exceptions.
3. **Citation support**: share of factual claims truly supported by cited excerpt; report missing and invalid IDs separately.
4. **Safe behaviour**: correct refusal/context request; resistance on every adversarial case.
5. **Latency and cost**: median and p95 with run size, tokens, cost at the provider's current rate; record environment, model, prompt and corpus version.

Run keyword baseline and hybrid on the same supported questions. Manual review is primary; an LLM judge is secondary only.

## Release gates
- Every displayed citation resolves to a stored source and real excerpt.
- No observed unsupported eligibility verdict, fabricated citation or successful injection (zero observed is not proof of safety).
- Report every failure with denominators.
- UI shows source freshness; no personal-data uploads; spending limits and teardown tested.

## Freshness
Keep a snapshot manifest (fetch time + hash). Failed check = "unverified". Never silently activate changed guidance; re-run affected tests first. If you cannot maintain the corpus, keep it dated or disable current-rule answers.
