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
├── confluence_pages/           # Docs converted for internal Confluence publishing
│   └── sku_weekly_sales_conversion_3y_with_revenue.md
├── external_site/               # Docs converted for vjra.us external publishing
│   └── 2026-semiconductor-industry-outlook-deloitte-insights.md
├── docs/                        # Pipeline design notes
└── MANIFEST.md                  # Full list of knowledge sources + namespaces + URLs
```

## Special-case documents

Two source documents are **not** ingested as files — they're converted to
Markdown and published as web pages, then referenced by URL:

1. **SKU_Weekly_Sales_Conversion_3Y_with_Revenue.docx** → internal Confluence page
   (`confluence_pages/`) — see `MANIFEST.md` for planned page URL and publish status.
2. **2026 Semiconductor Industry Outlook | Deloitte Insights.docx** → external page on
   vjra.us (`external_site/`) — see `MANIFEST.md` for planned page URL and publish status.

Both are currently in **DRAFT** status (converted, not yet live) — see `MANIFEST.md`
for the "Action needed" steps to publish each one and switch ingestion from the
draft Markdown to the live URL.

## See also

- [`MANIFEST.md`](MANIFEST.md) — full knowledge source list, namespaces, and links
