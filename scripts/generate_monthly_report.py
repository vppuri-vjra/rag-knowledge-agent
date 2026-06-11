#!/usr/bin/env python3
"""NovaCart Product Finance Reporting Agent.

Generates the Monthly Financial Standing Report by:
  1. Querying novacart-int (internal product sales) for performance signals
  2. Querying novacart-ext (industry outlooks / consumer behavior) for market context
  3. Synthesizing both into a structured leadership report via an LLM
  4. Writing the report + a draft stakeholder email to output/

Does NOT send the email — that requires explicit user confirmation (see
output/email_draft.md and report_email.py).
"""
import os
import re
import datetime

from openai import OpenAI
from pinecone import Pinecone

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUTPUT_DIR = os.path.join(ROOT, "output")
EMBED_MODEL = "text-embedding-3-large"
EMBED_DIM = 1024
INDEX_NAME = "novacart-claudecode"
CHAT_MODEL = "gpt-4o"
TOP_K = 5


def load_env(path):
    env = {}
    with open(path) as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            k, v = line.split("=", 1)
            env[k.strip()] = v.strip()
    return env


env = load_env(os.path.join(ROOT, ".env"))
oai = OpenAI(api_key=env["OPENAI_API_KEY"])
pc = Pinecone(api_key=env["PINECONE_API_KEY"])
index = pc.Index(INDEX_NAME)

# ---------------------------------------------------------------------------
# Retrieval
# ---------------------------------------------------------------------------

INTERNAL_QUERIES = [
    "NovaPhone X1 weekly units sold revenue and conversion rate trends",
    "NovaHome SmartHub Pro weekly sales performance and revenue",
    "NovaFit Active Watch weekly sales performance and revenue",
    "NovaCart Essentials Subscription weekly revenue and conversion trends",
    "NovaCart product catalog overview and product portfolio",
    "NovaCart Company Annual Report 2024 financial highlights and strategy",
]

EXTERNAL_QUERIES = [
    "2026 semiconductor industry outlook AI chip demand and revenue growth",
    "memory chip pricing shortage impact on smartphones and PCs in 2026",
    "AI data center capital expenditure and power constraints risk 2026",
    "consumer electronics demand trends smartphones wearables 2026",
    "technology industry trends 2026 predictions for hardware and devices",
]


def embed(text):
    return oai.embeddings.create(model=EMBED_MODEL, input=text, dimensions=EMBED_DIM).data[0].embedding


def retrieve(queries, namespace, top_k=TOP_K):
    seen = {}
    for q in queries:
        emb = embed(q)
        res = index.query(vector=emb, top_k=top_k, namespace=namespace, include_metadata=True)
        for m in res["matches"]:
            key = m["id"]
            if key not in seen or m["score"] > seen[key]["score"]:
                seen[key] = {
                    "score": m["score"],
                    "title": m["metadata"]["title"],
                    "source": m["metadata"]["source"],
                    "text": m["metadata"]["text"],
                }
    # sort by score desc, return top results
    return sorted(seen.values(), key=lambda x: -x["score"])


def format_context(chunks, max_chunks=12):
    out = []
    for c in chunks[:max_chunks]:
        out.append(f"[Source: {c['title']} ({c['source']})]\n{c['text']}")
    return "\n\n---\n\n".join(out)


# ---------------------------------------------------------------------------
# Synthesis
# ---------------------------------------------------------------------------

REPORT_PROMPT = """You are the AI Finance Reporting Agent for NovaCart's Product Finance team.

Generate the **Monthly Financial Standing Report** for {month_year}, combining internal
product performance data with external market intelligence. This report goes to
NovaCart leadership and must be a clear, data-driven snapshot enabling fast strategic
decisions.

## Internal product performance data (from novacart-int, NovaCart's vector DB of
real-time product sales numbers):

{internal_context}

## External market intelligence (from novacart-ext, industry outlooks and consumer
behavior reports):

{external_context}

---

Write the report in Markdown with these sections:

1. **Executive Summary** — 3-5 sentence top-line synthesis of NovaCart's position
   relative to the broader market this month.
2. **Internal Performance Snapshot** — per product line (NovaPhone X1, NovaHome
   SmartHub Pro, NovaFit Active Watch, NovaCart Essentials Subscription): recent
   revenue/units/conversion trend direction, with specific numbers from the data.
3. **External Market Context** — key industry signals (semiconductor/AI chip demand,
   memory pricing, consumer electronics demand) relevant to NovaCart's portfolio.
4. **Correlated Insights & Risks** — explicitly connect internal performance to
   external conditions (e.g., memory price spikes -> margin pressure on NovaHome
   SmartHub Pro; smartphone demand softness -> NovaPhone X1 outlook). Call out
   risks and opportunities.
5. **Recommendations for Leadership** — 3-5 concrete, prioritized action items.

Be specific and cite numbers from the provided context where available. Do not
invent data not present in the context. Keep it concise enough for a leadership
read (under 700 words).
"""


def generate_report(internal_chunks, external_chunks, month_year):
    prompt = REPORT_PROMPT.format(
        month_year=month_year,
        internal_context=format_context(internal_chunks),
        external_context=format_context(external_chunks),
    )
    resp = oai.chat.completions.create(
        model=CHAT_MODEL,
        messages=[{"role": "user", "content": prompt}],
        temperature=0.3,
    )
    return resp.choices[0].message.content


EMAIL_PROMPT = """Based on the following Monthly Financial Standing Report, write a
short stakeholder email (plain text, not markdown) that:
- Has a subject line (prefix with "Subject: ")
- Opens with 1-2 sentence framing
- Summarizes the 2-3 most important takeaways as bullet points
- Notes the full report is attached/below
- Closes professionally, signed "NovaCart Product Finance Reporting Agent"

Report:

{report}
"""


def generate_email(report):
    resp = oai.chat.completions.create(
        model=CHAT_MODEL,
        messages=[{"role": "user", "content": EMAIL_PROMPT.format(report=report)}],
        temperature=0.3,
    )
    return resp.choices[0].message.content


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    today = datetime.date.today()
    month_year = today.strftime("%B %Y")

    print("Retrieving internal context (novacart-int)...")
    internal_chunks = retrieve(INTERNAL_QUERIES, "novacart-int")
    print(f"  {len(internal_chunks)} unique chunks")

    print("Retrieving external context (novacart-ext)...")
    external_chunks = retrieve(EXTERNAL_QUERIES, "novacart-ext")
    print(f"  {len(external_chunks)} unique chunks")

    print("Synthesizing report...")
    report = generate_report(internal_chunks, external_chunks, month_year)

    # Strip a leading H1 from the LLM output if present, to avoid a duplicate title
    report = re.sub(r"^#\s+.*\n+", "", report.strip(), count=1)

    report_path = os.path.join(OUTPUT_DIR, f"monthly_financial_standing_report_{today.strftime('%Y-%m')}.md")
    with open(report_path, "w") as f:
        f.write(f"# NovaCart Monthly Financial Standing Report — {month_year}\n\n")
        f.write(report)
    print(f"Report written to {report_path}")

    print("Drafting stakeholder email...")
    email = generate_email(report)
    email_path = os.path.join(OUTPUT_DIR, f"email_draft_{today.strftime('%Y-%m')}.txt")
    with open(email_path, "w") as f:
        f.write(email)
    print(f"Email draft written to {email_path}")

    print("\nDone. Review the report and email draft before sending.")


if __name__ == "__main__":
    main()
