# Sources Audit and Reproducibility Report

> **Caveat (2026-10-14 review):** this table was produced by the project's own tooling (`python -m ingestion.stage`). A separate reviewer inspected the code and saved records but did NOT re-fetch the 12 pages, so treat "live" columns as recorded, not independently confirmed. Re-run the staging command and read the diff before presenting anything as current. The corpus is a snapshot fetched 2026-10-12.

**Audit Date**: 2026-10-14  
**Corpus Version**: `2026-10-12-draft`  
**License**: Open Government Licence v3.0  

---

## 1. Source Audit Table (Official GOV.UK Pages)

All 12 allowlisted sources were audited live against `https://www.gov.uk`. Every page returned HTTP 200.

| Source ID | Official URL | Stored Page Updated | Live Page Updated | Stored Fetch Date | Content Hash Match | Status / Verdict |
|---|---|---|---|---|---|---|
| `graduate-overview` | [/graduate-visa](https://www.gov.uk/graduate-visa) | 2026-09-09 | 2026-09-09 | 2026-10-12 | MATCH (`432271078a06...`) | Active (Identical) |
| `graduate-costs` | [/graduate-visa/how-much-it-costs](https://www.gov.uk/graduate-visa/how-much-it-costs) | 2026-09-09 | 2026-09-09 | 2026-10-12 | MATCH (`68716d308fa5...`) | Active (Identical) |
| `graduate-documents` | [/graduate-visa/documents-youll-need-to-apply](https://www.gov.uk/graduate-visa/documents-youll-need-to-apply) | 2026-09-09 | 2026-09-09 | 2026-10-12 | MATCH (`626cbca77790...`) | Active (Identical) |
| `skilled-worker-overview` | [/skilled-worker-visa](https://www.gov.uk/skilled-worker-visa) | 2026-09-14 | 2026-09-14 | 2026-10-12 | MATCH (`4d4c438f9770...`) | Active (Identical) |
| `skilled-worker-your-job` | [/skilled-worker-visa/your-job](https://www.gov.uk/skilled-worker-visa/your-job) | 2026-09-14 | 2026-09-14 | 2026-10-12 | MATCH (`5cbdee586604...`) | Active (Identical) |
| `skilled-worker-salary-exceptions` | [/skilled-worker-visa/when-you-can-be-paid-less](https://www.gov.uk/skilled-worker-visa/when-you-can-be-paid-less) | 2026-09-14 | 2026-09-14 | 2026-10-12 | MATCH (`056114c2a9ee...`) | Active (Identical) |
| `skilled-worker-switching` | [/skilled-worker-visa/switch-to-this-visa](https://www.gov.uk/skilled-worker-visa/switch-to-this-visa) | 2026-09-14 | 2026-09-14 | 2026-10-12 | MATCH (`041959545fad...`) | Active (Identical) |
| `skilled-worker-costs` | [/skilled-worker-visa/how-much-it-costs](https://www.gov.uk/skilled-worker-visa/how-much-it-costs) | 2026-09-14 | 2026-09-14 | 2026-10-12 | MATCH (`1859609bfb32...`) | Active (Identical) |
| `skilled-worker-english` | [/skilled-worker-visa/knowledge-of-english](https://www.gov.uk/skilled-worker-visa/knowledge-of-english) | 2026-09-14 | 2026-09-14 | 2026-10-12 | MATCH (`b2ce04f25967...`) | Active (Identical) |
| `skilled-worker-extend` | [/skilled-worker-visa/extend-your-visa](https://www.gov.uk/skilled-worker-visa/extend-your-visa) | 2026-09-14 | 2026-09-14 | 2026-10-12 | MATCH (`6b66f9b72e2d...`) | Active (Identical) |
| `skilled-worker-documents` | [/skilled-worker-visa/documents-you-must-provide](https://www.gov.uk/skilled-worker-visa/documents-you-must-provide) | 2026-09-14 | 2026-09-14 | 2026-10-12 | MATCH (`e69d5817598d...`) | Active (Identical) |
| `sponsor-licence` | [/uk-visa-sponsorship-employers](https://www.gov.uk/uk-visa-sponsorship-employers) | 2026-10-12 | 2026-10-14 | 2026-10-12 | MATCH (`cebbf7c88ad4...`) | Date bumped on GOV.UK; text unchanged. Staged in `data/staged/sponsor-licence/`. |

> [!NOTE]
> **Genuine page-updated date vs. fetched date**:
> GOV.UK publishes a metadata tag `govuk:updated-at` indicating when departmental editors last published an official revision to the text. This is strictly separated from `fetched_at` (the timestamp when this scraper fetched the page).
> For `sponsor-licence`, GOV.UK republished the metadata timestamp on 2026-10-14, but the text content hash matches our stored snapshot hash (`cebbf7c88ad4...`). The difference is staged for review under `data/staged/` and the active corpus remains locked to `2026-10-12-draft`.

---

## 2. Clean Clone & Offline Reproducibility

To reproduce all offline tests and benchmark scores on a clean clone without credentials or network access:

### Pinned Checksums (`data/fixtures/checksums.json`)
- `chunks.jsonl`: `81a3999028a0142eb91cd9f0afc4a5cdb8f1964a1e0ae35e5b8a32a7b8fca84d`
- `manifest.json`: `79e96698ffc1ebe4902d00b29a52d6d50f6ff4c342f66c8b66b43f1d41122cac`
- `embeddings.fake.jsonl` (FAKE vectors): `c875e9da17610ead65785372010553c3400ad7fb12c7026d2ef60b8818a71ccd`

### Exact Commands
```powershell
# 1. Install pinned dependencies into venv
py -3 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt

# 2. Verify fixture checksums & setup local working data
.\.venv\Scripts\python.exe -m ingestion.setup_fixtures

# 3. Run all 45 offline unit and integration tests
.\.venv\Scripts\python.exe -m pytest tests/ -v

# 4. Run reproducible dated retrieval benchmark (Keyword BM25 vs Hybrid)
.\.venv\Scripts\python.exe -m eval.run_eval --split all
```

### Actual Benchmark Results
- **Keyword (BM25) Recall@5**: 22/24 (91.7%)
  - Latency: median 0.66 ms | p95 0.99 ms
- **Hybrid (BM25 + Vector + RRF) Recall@5**: 14/24 (58.3%)
  - Note: Evaluated against baseline deterministic hash embeddings. Demonstrates why vector shape alone is not proof of semantic search.
