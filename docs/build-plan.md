# Build plan (14 days + 1 week buffer, ~2-3 focused hours/day)

**Days 1-2** Repo, README boundary, 8-12 verified URLs with reasons, snapshot manifest, 20 dev questions with expected evidence, `/health`, form showing a real stored excerpt with URL and dates.
**Days 3-4** Fetch + clean + chunk all sources; inspect every snapshot; build corpus; keyword baseline recall@5 on dev set.
**Days 5-6** Supabase: apply migration, load chunks, embed locally (pin model + dimension; same for queries). 
**Days 7-8** Hybrid retrieval (FTS + vector + RRF). Compare with baseline on identical supported questions.
**Days 9-10** Model adapter (pinned model id, usage logging). Evidence-only prompt; answer must cite chunk IDs like `[graduate-overview#3]`.
**Days 11-12** Citation validation wired in; refusal / context-request paths; injection and stale-source cases.
**Days 13-14** UI polish (source dates, OGL attribution), manual review of all dev results, README failures section.
**Week 3 (buffer)** Dockerise, deploy to Lightsail, spending limit and teardown test, fresh held-out run, optional sponsor-register lookup.

Rules: no tuning on the held-out 20; if reused, disclose and write a fresh test set before any new unseen-test claim.
