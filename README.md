# RAG Knowledge Agent — NovaCart Product Finance Reporting Agent

Source repo for the knowledge base behind NovaCart's **Monthly Financial Standing Report**
agent (Week 2 — RAG Knowledge Agents assignment).

## Goal

Generate a comprehensive Monthly Financial Standing Report by the 1st of every month,
combining:
- **Internal data**: real-time product sales/performance metrics
- **External data**: industry outlooks and consumer-behavior reports

The agent queries a Pinecone vector index, synthesizes internal vs. external signals,
and emails the final report to stakeholders.

## Pinecone setup

| Setting | Value |
|---|---|
| Index | `novacart-claudecode` |
| Internal namespace | `novacart-int` |
| External namespace | `novacart-ext` |

## Repo structure

```
rag-knowledge-agent/
├── internal/                  # Internal documents (-> novacart-int)
│   ├── NovaCart_Product_Catalog.docx
│   └── NovaCart Company Annual Report 2024.docx
├── external/                  # External documents (-> novacart-ext)
│   ├── global-semiconductor-industry-outlook-2025.docx
│   ├── DI_Tech-trends-2026.docx
│   └── mckinsey-technology-trends-outlook-2025.docx
├── jira_epics/           # Docs converted for internal Jira Epic publishing
│   └── sku_weekly_sales_conversion_3y_with_revenue.md
├── external_site/               # Docs converted for vjra.us external publishing
│   └── 2026-semiconductor-industry-outlook-deloitte-insights.md
├── scripts/                      # Ingestion + publishing scripts
│   ├── ingest_pinecone.py        # Embed + upsert all 7 sources into Pinecone
│   ├── publish_jira_epic.py      # Publish SKU sales doc as a Jira Epic
│   └── list_confluence_spaces.py # Check Confluence space access
├── docs/                        # Pipeline design notes
└── MANIFEST.md                  # Full list of knowledge sources + namespaces + URLs
```

## Pinecone ingestion

Run `scripts/ingest_pinecone.py` to (re-)embed and upsert all 7 sources into
`novacart-claudecode` (1024-dim, cosine, `text-embedding-3-large`; chunking:
1500 chars / 200 overlap). See `MANIFEST.md` → "Ingestion status" for the
latest run's vector counts.

Requires a `.env` file in the repo root (gitignored) with:

```
OPENAI_API_KEY=sk-...
PINECONE_API_KEY=pcsk_...
JIRA_BASE_URL=https://vppuri-vjra.atlassian.net
JIRA_EMAIL=you@example.com
JIRA_API_TOKEN=ATATT3...
JIRA_PROJECT_KEY=KAN
```

```bash
pip3 install pinecone openai "markitdown[docx]"
python3 scripts/ingest_pinecone.py
```

## Generating the Monthly Financial Standing Report

`scripts/generate_monthly_report.py` is the Product Finance Reporting Agent:

1. Retrieves top-k context from `novacart-int` (per-product sales performance)
   and `novacart-ext` (industry outlooks / consumer behavior) for a fixed set
   of finance-relevant queries
2. Synthesizes a structured report (Executive Summary, Internal Performance
   Snapshot, External Market Context, Correlated Insights & Risks,
   Recommendations) via `gpt-4o`
3. Drafts a stakeholder email summarizing the report

Outputs to `output/monthly_financial_standing_report_YYYY-MM.md` and
`output/email_draft_YYYY-MM.txt`. **Sending the email is a separate, manual
step** — review the draft before sending to stakeholders.

```bash
python3 scripts/generate_monthly_report.py
```

## Special-case documents

Two source documents are **not** ingested as files — they're converted to
Markdown and published as web pages, then referenced by URL:

1. **SKU_Weekly_Sales_Conversion_3Y_with_Revenue.docx** → internal Jira Epic
   (`jira_epics/`, published via `scripts/publish_jira_epic.py`) — ✅ **LIVE**:
   https://vppuri-vjra.atlassian.net/browse/KAN-196 (Confluence not enabled on this
   Atlassian site, so published as a Jira Epic with the full data attached).
2. **2026 Semiconductor Industry Outlook | Deloitte Insights.docx** → external page on
   vjra.us (`external_site/`) — ✅ **LIVE**: http://vjra.us/research/2026-semiconductor-industry-outlook-deloitte-insights.html
   (hosted via GitHub Pages, repo `vppuri-vjra/vjra-research`)

See `MANIFEST.md` for full status and the `novacart-int`/`novacart-ext` ingestion
references for each.

## See also

- [`MANIFEST.md`](MANIFEST.md) — full knowledge source list, namespaces, and links
