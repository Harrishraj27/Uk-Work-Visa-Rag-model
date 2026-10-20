# Label change log

Labels change only when they contradict the pinned corpus (data/chunks.jsonl, snapshot fetched 2026-10-12). These are
checks of the labels against the stored snapshot, not claims about today's GOV.UK rules. Each change is recorded here.

| Case | Change | Reason (evidence) |
|---|---|---|
| frozen-01 | moved from `supported` to `ambiguous_or_unsupported`; expected chunk removed | The expected chunk `skilled-worker-overview#10` is about fees/savings. No stored chunk or snapshot mentions additional jobs or 20 hours (`grep` over data/snapshots found nothing). The question cannot be answered from the corpus, so the right behaviour is to abstain. |
| frozen-06 | expected chunk `skilled-worker-english#2` -> `#7` | `#2` lists UK school qualifications. The exempt nationalities list is in `#7`. |
| frozen-07 | expected answer £827 -> £943 | The pinned chunk `skilled-worker-costs#2` says £943 for up to 3 years from inside the UK. The old label of £827 appears nowhere in the stored snapshot. Re-check on live GOV.UK before presenting any fee as current. |

Not changed on purpose: frozen-11 (label correct, retrieval misses it: kept as a visible failure), and all dev/held_out labels
(their misses dev-08, dev-12, held-09 stay visible).
`eval/holdout.sha256` pins `questions.frozen_holdout.jsonl` after these edits. The runner refuses a changed file.
This second holdout was written by the same author after the first was inspected, so it is not independent evidence.
