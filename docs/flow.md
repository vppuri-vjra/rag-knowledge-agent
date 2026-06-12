# RAG Knowledge Agent — Designed Flow

End-to-end flow for the NovaCart Product Finance Reporting Agent (Week 2 — RAG
Knowledge Agents assignment): from raw source documents, through Pinecone
ingestion, to the synthesized Monthly Financial Standing Report and stakeholder
email.

## Flow

```
Raw sources
  ├─ internal/*.docx (Product Catalog, Annual Report 2024)
  ├─ jira_epics/sku_weekly_sales_conversion_3y_with_revenue.md  (-> Jira Epic KAN-196)
  ├─ external/*.docx (Global Semi 2025, Deloitte Tech Trends 2026, McKinsey Tech Trends 2025)
  └─ external_site/2026-semiconductor-industry-outlook-deloitte-insights.md (-> vjra.us page)
        │
        ▼
  1. PUBLISH SPECIAL-CASE SOURCES
     ├─ scripts/publish_jira_epic.py       → Jira Epic KAN-196 (description + .md attachment)
     └─ (manual) GitHub Pages              → https://vjra.us/research/...html
        │
        ▼
  2. INGEST  (scripts/ingest_pinecone.py)
     - Extract text: markitdown for .docx and the vjra.us HTML page;
       Jira REST API (description ADF -> text + attachment) for KAN-196
     - Chunk: 1500 chars, 200 char overlap
     - Embed: OpenAI text-embedding-3-large, dimensions=1024
     - Upsert -> Pinecone index `novacart-claudecode`
         novacart-int  (50 vectors:  Product Catalog, Annual Report 2024, KAN-196)
         novacart-ext  (481 vectors: 3 outlook docs + live vjra.us page)
        │
        ▼
  3. RETRIEVE  (scripts/generate_monthly_report.py)
     - 6 finance queries  -> embed -> query novacart-int  (top_k=5 each, dedup by id)
     - 5 market queries   -> embed -> query novacart-ext  (top_k=5 each, dedup by id)
        │
        ▼
  4. SYNTHESIZE  (gpt-4o, single chat completion)
     - Internal context + external context -> structured Markdown report:
       Executive Summary / Internal Performance Snapshot / External Market
       Context / Correlated Insights & Risks / Recommendations
        │
        ▼
  5. DRAFT EMAIL  (gpt-4o, single chat completion)
     - Report -> short stakeholder email (subject + bullet takeaways)
        │
        ▼
  Output: output/monthly_financial_standing_report_YYYY-MM.md
          output/email_draft_YYYY-MM.txt   (sending is a manual, confirmed step)
```

## What happens technically at each step

| # | Step | Script | Technical detail | Output |
|---|------|--------|-------------------|--------|
| 1a | Publish internal SKU data | `scripts/publish_jira_epic.py` | Strips metadata HTML comment from the source markdown, splits narrative text from data tables, builds an Atlassian Document Format (ADF) description (headings + paragraphs), `POST /rest/api/3/issue` (issuetype=Epic, project=KAN), then `POST /rest/api/3/issue/{key}/attachments` (multipart) with the full markdown (incl. 624-row weekly tables) | Jira Epic [KAN-196](https://vppuri-vjra.atlassian.net/browse/KAN-196) |
| 1b | Publish external article | (manual, via `vjra-research` repo) | Markdown -> HTML via Python `markdown` lib (`extensions=["tables"]`), styled template, GitHub Pages custom domain (`vjra.us`, A records to GitHub Pages IPs) | https://vjra.us/research/2026-semiconductor-industry-outlook-deloitte-insights.html |
| 2 | Extract + chunk + embed + upsert | `scripts/ingest_pinecone.py` | `MarkItDown().convert()` for `.docx`/HTML -> plain text. Jira: `GET /rest/api/3/issue/KAN-196` -> `adf_to_text()` flattens description, attachment fetched via its `content` URL. `chunk_text()`: sliding window, 1500 chars, 200 overlap. For each `doc_id`, deletes any existing `{doc_id}-chunk*` vectors in the namespace first (no duplicates, handles shrinking docs), then `OpenAI.embeddings.create(model="text-embedding-3-large", dimensions=1024)` in batches of 50, `index.upsert()` in batches of 100, namespace = `novacart-int` or `novacart-ext`, metadata = `{title, source, chunk_index, text}` | 531 vectors total in index `novacart-claudecode` + `output/pinecone_ingestion_manifest.json` |
| 3 | Retrieve | `scripts/generate_monthly_report.py` → `retrieve()` | For each of 11 hardcoded finance/market queries: embed query (same model/dims as ingestion), `index.query(top_k=5, include_metadata=True)` per namespace, dedup matches by vector `id` keeping highest score, sort descending | `internal_chunks` (16), `external_chunks` (18) — counts vary per run as Pinecone/embeddings are not deterministic |
| 4 | Synthesize report | `scripts/generate_monthly_report.py` → `generate_report()` | `format_context()` joins top 12 chunks per side as `[Source: title (source)]\n{text}` blocks, inserted into `REPORT_PROMPT`. Single `oai.chat.completions.create(model="gpt-4o", temperature=0.3)` call. Leading duplicate H1 stripped via regex before writing | `output/monthly_financial_standing_report_YYYY-MM.md` |
| 5 | Draft email | `scripts/generate_monthly_report.py` → `generate_email()` | Report text inserted into `EMAIL_PROMPT`, single `gpt-4o` call (temperature 0.3) producing subject line + plain-text body | `output/email_draft_YYYY-MM.txt` |

## Document ingestion paths: .docx vs. Jira Epic vs. vjra.us

All 7 documents end up in the same Pinecone index via the same chunk/embed/
upsert/idempotency logic, but they take different paths to get there:

| | Plain `.docx` (5 docs) | Jira Epic (KAN-196) | vjra.us page |
|---|---|---|---|
| **Source** | Local files in `internal/` and `external/` | Markdown in `jira_epics/sku_weekly_sales_conversion_3y_with_revenue.md`, published as a Jira Epic | Markdown in `external_site/2026-...html`, published to GitHub Pages |
| **Publishing step** | None — ingested directly | `scripts/publish_jira_epic.py`: ADF description (narrative) via `POST /rest/api/3/issue` (project=KAN, issuetype=Epic) + full markdown attached via `POST /rest/api/3/issue/{key}/attachments` | Manual: markdown → HTML (Python `markdown` lib, `extensions=["tables"]`) → committed to `vppuri-vjra/vjra-research`, served via GitHub Pages custom domain `vjra.us` |
| **Extraction in `ingest_pinecone.py`** | `MarkItDown().convert(path).text_content` | `get_jira_epic_text("KAN-196")`: `GET /rest/api/3/issue/KAN-196` → `adf_to_text()` flattens description to plain text, then fetches the attachment via its `content` URL (Basic auth) and concatenates | `fetch_url_text(url)`: `urllib` GET of the live HTML page, written to a temp file, then `MarkItDown().convert()` |
| **doc_id** | e.g. `novacart-product-catalog-docx`, `global-semiconductor-industry-outlook-2025` | `sku-weekly-sales-conversion-kan-196` | `2026-semiconductor-industry-outlook-deloitte-insights` |
| **Namespace** | `novacart-int` or `novacart-ext` per source | `novacart-int` | `novacart-ext` |
| **From here on (chunk/embed/upsert/idempotency)** | Identical for all — `chunk_text()` (1500/200), `OpenAI.embeddings.create(text-embedding-3-large, dim=1024)`, delete-then-upsert by `{doc_id}-chunk*`, recorded in `pinecone_ingestion_manifest.json` | Same | Same |
| **Auth/credentials needed** | None | `JIRA_BASE_URL`, `JIRA_EMAIL`, `JIRA_API_TOKEN` (Basic auth, `.env`) | None (public page) |

**Why this matters**: re-running `ingest_pinecone.py` always pulls the
**current live content** for KAN-196 and vjra.us (not a stale local copy) —
so editing the Jira Epic description/attachment or updating the vjra.us page
and re-running ingestion picks up those changes automatically, with the same
no-duplicate/no-orphan guarantees as the local `.docx` files.

## Cost & token estimate (per full run)

Based on the 2026-06-11 ingestion (531 chunks / 685K chars total) and one
report+email generation cycle. OpenAI pricing: `text-embedding-3-large`
$0.13/1M tokens; `gpt-4o` $2.50/1M input tokens, $10.00/1M output tokens.
Pinecone (`novacart-claudecode`, serverless, ~2MB of vectors) and Jira/GitHub
Pages publishing are effectively free at this scale.

| Step | Script | Calls | Approx. tokens | Approx. cost |
|---|---|---|---|---|
| 1a. Publish SKU data to Jira Epic | `publish_jira_epic.py` | 2 REST calls (issue create + attachment) | n/a | $0 (Jira API, free tier) |
| 1b. Publish article to vjra.us | manual / GitHub Pages | n/a | n/a | $0 (GitHub Pages hosting) |
| 2. Ingest: embed 531 chunks | `ingest_pinecone.py` | ~11 embedding batches (≤50 chunks each) | ~171K input tokens | ~$0.022 |
| 2. Ingest: Pinecone upsert/delete/list | `ingest_pinecone.py` | ~6 upsert batches + list/delete per doc | n/a | ~$0 (serverless free tier covers this volume) |
| 3. Retrieve: embed 11 queries | `generate_monthly_report.py` | 11 embedding calls | ~165 input tokens | <$0.001 |
| 3. Retrieve: Pinecone queries | `generate_monthly_report.py` | 11 query calls (top_k=5) | n/a | ~$0 |
| 4. Synthesize report | `generate_monthly_report.py` | 1 `gpt-4o` call | ~9.4K input / ~0.9K output | ~$0.033 |
| 5. Draft email | `generate_monthly_report.py` | 1 `gpt-4o` call | ~1.0K input / ~0.2K output | ~$0.005 |
| **Total (re-ingest all + generate report)** | | | ~182K tokens | **~$0.06** |
| **Total (report-only run, no re-ingest)** | `generate_monthly_report.py` only | | ~10.6K tokens | **~$0.04** |

Notes:
- Embedding cost dominates total cost and scales with re-ingestion volume — since
  ingestion is now incremental/idempotent (see below), re-running after a small
  doc edit only re-embeds that doc's chunks, not all 531.
- Token counts are estimated from character counts (~4 chars/token); actual
  `gpt-4o` token usage is available per-call via `resp.usage` if exact
  tracking is wanted.

## Notes / known limitations

- Retrieval queries (steps 3) are static/hardcoded, not dynamically generated from
  the report month or recent changes — same 11 queries run every time.
- `ingest_pinecone.py` is update-safe: for each `doc_id`, it first deletes any
  existing `{doc_id}-chunk*` vectors in the target namespace, then re-embeds
  and re-upserts. This prevents duplicates and also clears stale trailing
  chunks if a source document shrinks. Each run writes
  `output/pinecone_ingestion_manifest.json` (doc_id, namespace, file/URL,
  chunk count, vector IDs) for traceability.
- Email sending is intentionally **not automated** — `output/email_draft_*.txt`
  is for human review before sending via your own email client/tooling.
- Confluence is not enabled on the Atlassian site used, so the internal SKU
  sales source is a Jira Epic (KAN-196) rather than a Confluence page — see
  `MANIFEST.md` for details.
