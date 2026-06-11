# Knowledge Source Manifest — NovaCart Product Finance Reporting Agent

This manifest lists every document feeding the Monthly Financial Standing Report
RAG pipeline, where it lives, and which Pinecone namespace it belongs to.

Pinecone index: **novacart-claudecode** (1024-dim, cosine, `text-embedding-3-large`)

## Ingestion status

✅ **All 7 sources ingested** via `scripts/ingest_pinecone.py` (run 2026-06-11):
- `novacart-int`: 50 vectors (Product Catalog, Annual Report 2024, SKU Sales Epic KAN-196)
- `novacart-ext`: 481 vectors (3 outlook docs + live Deloitte vjra.us page)
- Chunking: 1500 chars, 200 overlap. Re-run the script to refresh/re-embed after source updates.
- **Update-safe / no duplicates**: each doc gets a deterministic `doc_id` (e.g.
  `novacart-product-catalog-docx`). Before upserting, the script deletes any
  existing `{doc_id}-chunk*` vectors in that namespace, then writes fresh
  chunks. Re-running after a source changes (or shrinks) replaces its vectors
  in place — no stale or duplicate vectors are left behind.
- **Traceability**: `output/pinecone_ingestion_manifest.json` records, per
  document, the `doc_id`, namespace, file/URL, chunk count, and full list of
  vector IDs from the most recent run.

## Internal documents → namespace `novacart-int`

| Document | Location | Notes |
|---|---|---|
| NovaCart_Product_Catalog.docx | `internal/NovaCart_Product_Catalog.docx` | Ingested as-is (.docx) |
| NovaCart Company Annual Report 2024.docx | `internal/NovaCart Company Annual Report 2024.docx` | Ingested as-is (.docx) |
| SKU_Weekly_Sales_Conversion_3Y_with_Revenue.docx | **Jira Epic** (see below) — converted, not ingested as a file | Source docx archived at `jira_epics/sku_weekly_sales_conversion_3y_with_revenue.md` |

### Jira Epic (internal)
- **Status:** ✅ LIVE
- **Site:** https://vppuri-vjra.atlassian.net (Confluence not enabled on this site — published as a Jira Epic instead)
- **Project:** KAN
- **Live page URL:** https://vppuri-vjra.atlassian.net/browse/KAN-196
- **Description:** narrative summary (Executive Summary, Product Overview, per-SKU context)
- **Attachment:** `sku_weekly_sales_conversion_3y_with_revenue.md` — full 624-row weekly data tables (156 weeks x 4 SKUs)
- **Source markdown:** `jira_epics/sku_weekly_sales_conversion_3y_with_revenue.md`
- **Ingestion:** point the `novacart-int` ingestion job at the Epic URL above (description + attachment) instead of the .docx
- **Published via:** `scripts/publish_jira_epic.py`

## External documents → namespace `novacart-ext`

| Document | Location | Notes |
|---|---|---|
| global-semiconductor-industry-outlook-2025.docx | `external/global-semiconductor-industry-outlook-2025.docx` | Ingested as-is (.docx) |
| DI_Tech-trends-2026.docx | `external/DI_Tech-trends-2026.docx` | Ingested as-is (.docx) |
| mckinsey-technology-trends-outlook-2025.docx | `external/mckinsey-technology-trends-outlook-2025.docx` | Ingested as-is (.docx) |
| 2026 Semiconductor Industry Outlook \| Deloitte Insights.docx | **External URL on vjra.us** (see below) — converted, not ingested as a file | Source docx archived at `external_site/2026-semiconductor-industry-outlook-deloitte-insights.md` |

### External URL (vjra.us)
- **Status:** ✅ LIVE
- **Site:** https://vjra.us (hosted via GitHub Pages, repo `vppuri-vjra/vjra-research`)
- **Live page URL:** http://vjra.us/research/2026-semiconductor-industry-outlook-deloitte-insights.html
- **Source markdown:** `external_site/2026-semiconductor-industry-outlook-deloitte-insights.md`
- **Ingestion:** point the `novacart-ext` ingestion job at the live vjra.us URL above instead of the .docx

## Summary

| # | Title | Type | Reference |
|---|---|---|---|
| 1 | NovaCart Product Catalog | Internal doc | `internal/NovaCart_Product_Catalog.docx` |
| 2 | NovaCart Company Annual Report 2024 | Internal doc | `internal/NovaCart Company Annual Report 2024.docx` |
| 3 | SKU Weekly Sales & Conversion (3Y, with Revenue) | Internal — Jira Epic (LIVE) | https://vppuri-vjra.atlassian.net/browse/KAN-196 |
| 4 | Global Semiconductor Industry Outlook 2025 | External doc | `external/global-semiconductor-industry-outlook-2025.docx` |
| 5 | Deloitte Tech Trends 2026 | External doc | `external/DI_Tech-trends-2026.docx` |
| 6 | McKinsey Technology Trends Outlook 2025 | External doc | `external/mckinsey-technology-trends-outlook-2025.docx` |
| 7 | 2026 Semiconductor Industry Outlook (Deloitte Insights) | External — vjra.us page (LIVE) | http://vjra.us/research/2026-semiconductor-industry-outlook-deloitte-insights.html |
