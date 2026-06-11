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
     └─ (manual) GitHub Pages              → http://vjra.us/research/...html
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
| 1b | Publish external article | (manual, via `vjra-research` repo) | Markdown -> HTML via Python `markdown` lib (`extensions=["tables"]`), styled template, GitHub Pages custom domain (`vjra.us`, A records to GitHub Pages IPs) | http://vjra.us/research/2026-semiconductor-industry-outlook-deloitte-insights.html |
| 2 | Extract + chunk + embed + upsert | `scripts/ingest_pinecone.py` | `MarkItDown().convert()` for `.docx`/HTML -> plain text. Jira: `GET /rest/api/3/issue/KAN-196` -> `adf_to_text()` flattens description, attachment fetched via its `content` URL. `chunk_text()`: sliding window, 1500 chars, 200 overlap. For each `doc_id`, deletes any existing `{doc_id}-chunk*` vectors in the namespace first (no duplicates, handles shrinking docs), then `OpenAI.embeddings.create(model="text-embedding-3-large", dimensions=1024)` in batches of 50, `index.upsert()` in batches of 100, namespace = `novacart-int` or `novacart-ext`, metadata = `{title, source, chunk_index, text}` | 531 vectors total in index `novacart-claudecode` + `output/pinecone_ingestion_manifest.json` |
| 3 | Retrieve | `scripts/generate_monthly_report.py` → `retrieve()` | For each of 11 hardcoded finance/market queries: embed query (same model/dims as ingestion), `index.query(top_k=5, include_metadata=True)` per namespace, dedup matches by vector `id` keeping highest score, sort descending | `internal_chunks` (16), `external_chunks` (18) — counts vary per run as Pinecone/embeddings are not deterministic |
| 4 | Synthesize report | `scripts/generate_monthly_report.py` → `generate_report()` | `format_context()` joins top 12 chunks per side as `[Source: title (source)]\n{text}` blocks, inserted into `REPORT_PROMPT`. Single `oai.chat.completions.create(model="gpt-4o", temperature=0.3)` call. Leading duplicate H1 stripped via regex before writing | `output/monthly_financial_standing_report_YYYY-MM.md` |
| 5 | Draft email | `scripts/generate_monthly_report.py` → `generate_email()` | Report text inserted into `EMAIL_PROMPT`, single `gpt-4o` call (temperature 0.3) producing subject line + plain-text body | `output/email_draft_YYYY-MM.txt` |

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
