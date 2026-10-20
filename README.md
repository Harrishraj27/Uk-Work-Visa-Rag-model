# UK Work Visa Evidence Assistant

A portfolio prototype that shows **passages from official GOV.UK pages** about the UK Graduate visa and switching to Skilled Worker, with citations, page dates and fetch dates. With a real language model connected it also writes a short cited answer.

**Boundary:** general information only. Not legal advice, not a UK government service, not an eligibility checker. Its knowledge is a **snapshot fetched 2026-10-12** (93 passages from 12 pages). It is not live. Always check the official page.

Contains public sector information licensed under the Open Government Licence v3.0.

## Honest status (read this first)

| Area | Status | Evidence |
|---|---|---|
| Offline demo (no keys, no cost) | Works | `python -m pytest` -> 90 passed; `/health`, `/`, `/ask` tested with the test client |
| Offline answers | **Not written.** Offline mode shows the top passage word for word and says so | `core/llm.py` (`offline_evidence_answer`), regression test through `/ask` |
| Real language model answers | **NOT TESTED.** No key was used in building this | run Step 5 below, then review answers by hand |
| Real embeddings / hybrid with real vectors | **NOT TESTED.** Saved vectors are FAKE (hash of words), labelled so | `data/fixtures/embeddings.fake.jsonl` metadata `is_fake: true` |
| Supabase | **NOT TESTED against a live project.** SQL and upload script are written | `supabase/schema.sql`, `ingestion/upload_supabase.py` |
| Docker | **NOT BUILT** in the build environment (no Docker there). Files checked statically | `tests/test_release_files.py` |
| Deployment / demo link | None | n/a |
| Source freshness | Snapshot only; audit tooling and saved records exist, not independently re-fetched | `docs/source_audit.md` caveat |

## Quick start (offline, free)

```bash
python -m venv .venv
# Windows: .venv\Scripts\activate      Linux/macOS: source .venv/bin/activate
pip install -r requirements.txt
python -m pytest                       # expect: 90 passed
uvicorn app.main:app                   # open http://localhost:8000
```
`.env` ships with blank key fields and offline defaults (`LLM_PROVIDER=fake`, `RETRIEVAL_MODE=keyword`). The page shows an **OFFLINE DEMO MODE** banner.
Check: `curl localhost:8000/health` -> `"status":"ok"`, `"answer_mode":"offline"`, all `live_verified:false`.

## Step 5: use a real model (you choose and pay; nothing here does it for you)

1. Edit `.env` yourself. **Adding a key alone changes nothing**: the default `LLM_PROVIDER=fake` stays offline. Change the switches too:

   | Goal | Settings you must change |
   |---|---|
   | Real answers | `LLM_PROVIDER=openai` (or `anthropic`), `LLM_MODEL=...`, `LLM_API_KEY=...` |
   | Real vectors | `EMBEDDING_PROVIDER=openai`, `EMBEDDING_MODEL=...`, `EMBEDDING_API_KEY=...`, then `python -m ingestion.embed --force` |
   | Search with vectors | `RETRIEVAL_MODE=hybrid` (after the vectors exist) |
   | Supabase | `STORE=supabase`, `SUPABASE_URL`, `SUPABASE_ANON_KEY` (after the SQL and upload) |

   The app warns (page banner and `/health` -> `config_warnings`) if a key is filled but its provider is still off. Keys stay in `.env`; never paste them in chat or commit them.
2. Check current provider pricing and terms yourself. Set `PRICE_IN_PER_MTOK` / `PRICE_OUT_PER_MTOK` from their pricing page so costs show.
3. Real vectors (optional, only needed for `RETRIEVAL_MODE=hybrid`): `python -m ingestion.embed --force` (stops and writes nothing if the provider fails; never falls back to fake).
4. Real answers: `python -m eval.run_answer_eval --split all --yes-spend` (`--yes-spend` is required because it costs money). Open `eval/results/answer_eval_all.json`, read every answer against its passage, then record your judgement in `eval/reviews/all.json` (format in the script header). The release gate only says PASS when every answer is reviewed.

## Supabase (dev project only)

1. Supabase dashboard > SQL editor: paste and run `supabase/schema.sql` (tables, RRF function, row level security).
2. `.env`: `SUPABASE_URL`, `SUPABASE_ANON_KEY` (web app, read-only via RLS), `SUPABASE_SERVICE_ROLE_KEY` (ingestion only, your machine only).
3. `python -m ingestion.upload_supabase --dry-run`, then without `--dry-run`. Then `STORE=supabase RETRIEVAL_MODE=hybrid`.
4. If Supabase fails the app shows an error. It does not silently search locally (set `SUPABASE_FALLBACK_LOCAL=true` to allow that).
Vector size is 1536 (`text-embedding-3-small`). Another size means changing `vector(1536)` in the SQL (2 places) and `EMBEDDING_DIM`.

## Docker (not built here)

```bash
docker build -t uk-work-visa-rag .
docker run --env-file .env -p 8000:8000 uk-work-visa-rag
curl localhost:8000/health
```

## What changed in the last fix round

- Offline answers used a large question-specific extractor that dropped negation (it told users they could work as a professional sportsperson on a Graduate visa, when the source says "You cannot"). It is gone. Offline mode quotes the passage whole.
- One shared pipeline (`app/pipeline.py`) is used by `/ask` and by the answer evaluation. Scope guard before every model call (`core/guard.py`). Answers with invalid or missing citations are withheld. A provider failure shows evidence only, never a fake answer.
- The answer evaluator no longer treats "valid citation ID" as correct. Correctness needs a matching human review. Offline runs report NOT_EVALUATED.
- Vector validation checks every vector, the full checksum, provider/model/dimension/corpus hash. Cosine search now normalises document vectors too.
- SQL: candidate lists are ordered before `limit 20`; RLS added. `/health` separates process health from provider readiness.
- Three frozen-holdout labels contradicted the stored passages; fixed with reasons in `eval/label_changes.md`.

## Observed retrieval results (Recall@5, k=5, snapshot 2026-10-12)

Command: `python -m eval.run_eval --split <dev|held_out|all|frozen_holdout>`. Saved in `eval/results/`.
**Vector and hybrid use FAKE hash vectors, so they measure word overlap, not meaning. They are not evidence of semantic search.**

| Split | Keyword (BM25) | Vector (fake) | Hybrid (fake vectors + RRF) |
|---|---|---|---|
| dev (12) | 11/12 (miss dev-08) | 9/12 | 11/12 (miss dev-12) |
| held_out (12) | 11/12 (miss held-09) | 10/12 | 12/12 |
| dev + held_out (24) | **22/24** | 19/24 | **23/24** |
| frozen_holdout (11 supported) | 10/11 (miss frozen-11) | 5/11 | 10/11 (miss frozen-11) |

- Recall@5 counts a question as a hit if at least one expected chunk ID is in the top 5. It says nothing about whether an answer is right.
- The old README claim of keyword 24/24 was wrong. 22/24 and fake-hybrid 23/24 are the correct historical figures and match today's rerun.
- The first holdout (held_out) was already inspected, so it is not untouched. `frozen_holdout` was written by the same author afterwards, is hash-pinned (`eval/holdout.sha256`) and is **not independent proof of generalisation**. Its numbers moved after three labels were corrected (see `eval/label_changes.md`), so do not compare them with the earlier 9/12.
- Tuning: BM25 has hand-set route weights in `app/retrieval.py`. They were not re-tuned this round.

## Observed answer evaluation (40 cases)

Command: `python -m eval.run_answer_eval --split all` (offline fake model). Result: **release gate NOT_EVALUATED**. 11 of the 16 safety/scope questions are refused by the guard before any model call; 29 cases need a real model and a human reviewer. Automatic hard gates (no secrets, no invalid citations, no guarantee claims) found 0 problems, but that covers offline output only. **No real model answer has been generated or reviewed.**

## Known failures and limits

- Retrieval misses: dev-08, dev-12 (hybrid), held-09 (keyword), frozen-11 (all modes).
- Five safety/scope cases (dev-16, dev-20, held-13, held-14, held-15) need a real model to answer or abstain properly.
- The guard uses patterns; a cleverly worded personal-eligibility question can get past it to the model. The citation gate does not prove a cited sentence is true.
- The UI was checked as HTML and via the test client, and its mobile layout was seen in a screenshot during review; it was not re-screenshotted after this round.
- Live provider, Supabase and Docker behaviour are unverified.

## Layout

| Path | Purpose |
|---|---|
| `core/` | config, model/embedding adapters, guard, vector validation, budget, prompts |
| `app/` | FastAPI app, shared answer pipeline, retrieval (BM25, vector, RRF hybrid), citations |
| `ingestion/` | fetch, chunk, corpus build, embeddings, staging audit, Supabase upload |
| `data/` | corpus, manifest, snapshots, `fixtures/` (checksummed, includes FAKE vectors) |
| `eval/` | question sets, retrieval and answer runners, results, `label_changes.md`, `reviews/` |
| `supabase/schema.sql` | paste-ready SQL (same content as `migrations/001` + `002`) |
| `scripts/package_clean_zip.py` | builds and scans the shareable zip |
