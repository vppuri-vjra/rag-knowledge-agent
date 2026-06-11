#!/usr/bin/env python3
"""Ingest the NovaCart knowledge sources into Pinecone.

Index:      novacart-claudecode (1024-dim, cosine, text-embedding-3-large)
Namespaces: novacart-int  (internal documents + Jira Epic)
            novacart-ext  (external documents + vjra.us page)

Reads OPENAI_API_KEY, PINECONE_API_KEY, JIRA_* from .env in the repo root.
"""
import os
import re
import json
import base64
import urllib.request
import ssl
import certifi

from markitdown import MarkItDown
from openai import OpenAI
from pinecone import Pinecone

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SSL_CTX = ssl.create_default_context(cafile=certifi.where())

EMBED_MODEL = "text-embedding-3-large"
EMBED_DIM = 1024
INDEX_NAME = "novacart-claudecode"
CHUNK_SIZE = 1500   # chars
CHUNK_OVERLAP = 200


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
md = MarkItDown()
oai = OpenAI(api_key=env["OPENAI_API_KEY"])
pc = Pinecone(api_key=env["PINECONE_API_KEY"])
index = pc.Index(INDEX_NAME)


def chunk_text(text, size=CHUNK_SIZE, overlap=CHUNK_OVERLAP):
    text = re.sub(r"\n{3,}", "\n\n", text).strip()
    chunks = []
    start = 0
    while start < len(text):
        end = min(start + size, len(text))
        chunk = text[start:end]
        if chunk.strip():
            chunks.append(chunk.strip())
        if end == len(text):
            break
        start = end - overlap
    return chunks


def embed_batch(texts):
    resp = oai.embeddings.create(model=EMBED_MODEL, input=texts, dimensions=EMBED_DIM)
    return [d.embedding for d in resp.data]


def upsert_doc(namespace, doc_id, title, source_url, text):
    chunks = chunk_text(text)
    print(f"  {doc_id}: {len(chunks)} chunks, {len(text)} chars")

    # Remove any previously-ingested chunks for this doc first, so that if the
    # source shrinks (fewer chunks than before), stale trailing vectors don't
    # linger. New/changed chunks overwrite in place via deterministic IDs
    # (no duplicates are ever created for the same doc_id).
    existing_ids = []
    for page in index.list(prefix=f"{doc_id}-chunk", namespace=namespace):
        existing_ids.extend(item.id for item in page.vectors)
    if existing_ids:
        index.delete(ids=existing_ids, namespace=namespace)

    if not chunks:
        return 0, []

    # batch embed in groups of 50
    vectors = []
    for i in range(0, len(chunks), 50):
        batch = chunks[i:i + 50]
        embeddings = embed_batch(batch)
        for j, (chunk, emb) in enumerate(zip(batch, embeddings)):
            idx = i + j
            vectors.append({
                "id": f"{doc_id}-chunk{idx}",
                "values": emb,
                "metadata": {
                    "title": title,
                    "source": source_url,
                    "chunk_index": idx,
                    "text": chunk,
                },
            })
    for i in range(0, len(vectors), 100):
        index.upsert(vectors=vectors[i:i + 100], namespace=namespace)
    return len(vectors), [v["id"] for v in vectors]


# ---------------------------------------------------------------------------
# Internal sources -> novacart-int
# ---------------------------------------------------------------------------

def jira_api(method, path, headers=None, raw_body=None):
    auth = base64.b64encode(f"{env['JIRA_EMAIL']}:{env['JIRA_API_TOKEN']}".encode()).decode()
    h = {"Authorization": f"Basic {auth}", "Accept": "application/json"}
    if headers:
        h.update(headers)
    req = urllib.request.Request(f"{env['JIRA_BASE_URL']}{path}", data=raw_body, headers=h, method=method)
    with urllib.request.urlopen(req, context=SSL_CTX) as resp:
        return resp.read()


def adf_to_text(node):
    """Flatten an Atlassian Document Format node tree to plain text."""
    out = []
    if isinstance(node, dict):
        if node.get("type") == "text":
            out.append(node.get("text", ""))
        for child in node.get("content", []) or []:
            out.append(adf_to_text(child))
        if node.get("type") in ("paragraph", "heading"):
            out.append("\n")
    elif isinstance(node, list):
        for n in node:
            out.append(adf_to_text(n))
    return "".join(out)


def get_jira_epic_text(issue_key):
    data = json.loads(jira_api("GET", f"/rest/api/3/issue/{issue_key}"))
    summary = data["fields"]["summary"]
    description_text = adf_to_text(data["fields"]["description"])

    # fetch first attachment content
    attachment_text = ""
    for att in data["fields"].get("attachment", []):
        url = att["content"]
        auth = base64.b64encode(f"{env['JIRA_EMAIL']}:{env['JIRA_API_TOKEN']}".encode()).decode()
        req = urllib.request.Request(url, headers={"Authorization": f"Basic {auth}"})
        with urllib.request.urlopen(req, context=SSL_CTX) as resp:
            content = resp.read().decode("utf-8", errors="ignore")
        # strip metadata HTML comment from the markdown attachment
        content = re.sub(r"<!--.*?-->\s*", "", content, flags=re.S)
        attachment_text += "\n\n" + content

    return f"# {summary}\n\n{description_text}\n{attachment_text}"


def ingest_internal(manifest):
    print("Internal documents -> novacart-int")
    total = 0
    namespace = "novacart-int"

    docx_files = [
        ("NovaCart_Product_Catalog.docx", "internal/NovaCart_Product_Catalog.docx"),
        ("NovaCart Company Annual Report 2024.docx", "internal/NovaCart Company Annual Report 2024.docx"),
    ]
    for title, relpath in docx_files:
        path = os.path.join(ROOT, relpath)
        text = md.convert(path).text_content
        doc_id = re.sub(r"[^a-z0-9]+", "-", title.lower()).strip("-")
        count, ids = upsert_doc(namespace, doc_id, title, relpath, text)
        total += count
        manifest.append({"doc_id": doc_id, "title": title, "file": relpath, "index": INDEX_NAME,
                          "namespace": namespace, "chunk_count": count, "vector_ids": ids})

    # Jira Epic KAN-196
    doc_id = "sku-weekly-sales-conversion-kan-196"
    title = "SKU Weekly Sales & Conversion - 3Y with Revenue"
    source = "https://vppuri-vjra.atlassian.net/browse/KAN-196"
    epic_text = get_jira_epic_text("KAN-196")
    count, ids = upsert_doc(namespace, doc_id, title, source, epic_text)
    total += count
    manifest.append({"doc_id": doc_id, "title": title, "file": source, "index": INDEX_NAME,
                      "namespace": namespace, "chunk_count": count, "vector_ids": ids})

    return total


# ---------------------------------------------------------------------------
# External sources -> novacart-ext
# ---------------------------------------------------------------------------

def fetch_url_text(url):
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, context=SSL_CTX) as resp:
        html_bytes = resp.read()
    import tempfile
    with tempfile.NamedTemporaryFile(suffix=".html", delete=False) as f:
        f.write(html_bytes)
        tmp_path = f.name
    try:
        text = md.convert(tmp_path).text_content
    finally:
        os.unlink(tmp_path)
    return text


def ingest_external(manifest):
    print("External documents -> novacart-ext")
    total = 0
    namespace = "novacart-ext"

    docx_files = [
        ("Global Semiconductor Industry Outlook 2025", "external/global-semiconductor-industry-outlook-2025.docx"),
        ("Deloitte Tech Trends 2026", "external/DI_Tech-trends-2026.docx"),
        ("McKinsey Technology Trends Outlook 2025", "external/mckinsey-technology-trends-outlook-2025.docx"),
    ]
    for title, relpath in docx_files:
        path = os.path.join(ROOT, relpath)
        text = md.convert(path).text_content
        doc_id = re.sub(r"[^a-z0-9]+", "-", title.lower()).strip("-")
        count, ids = upsert_doc(namespace, doc_id, title, relpath, text)
        total += count
        manifest.append({"doc_id": doc_id, "title": title, "file": relpath, "index": INDEX_NAME,
                          "namespace": namespace, "chunk_count": count, "vector_ids": ids})

    # vjra.us live page
    doc_id = "2026-semiconductor-industry-outlook-deloitte-insights"
    title = "2026 Global Semiconductor Industry Outlook (Deloitte Insights)"
    url = "http://vjra.us/research/2026-semiconductor-industry-outlook-deloitte-insights.html"
    text = fetch_url_text(url)
    count, ids = upsert_doc(namespace, doc_id, title, url, text)
    total += count
    manifest.append({"doc_id": doc_id, "title": title, "file": url, "index": INDEX_NAME,
                      "namespace": namespace, "chunk_count": count, "vector_ids": ids})

    return total


def main():
    manifest = []
    int_count = ingest_internal(manifest)
    ext_count = ingest_external(manifest)
    print(f"\nDone. Upserted {int_count} vectors -> novacart-int, {ext_count} vectors -> novacart-ext")
    stats = index.describe_index_stats()
    print(stats)

    manifest_path = os.path.join(ROOT, "output", "pinecone_ingestion_manifest.json")
    os.makedirs(os.path.dirname(manifest_path), exist_ok=True)
    with open(manifest_path, "w") as f:
        json.dump({
            "index": INDEX_NAME,
            "embedding_model": EMBED_MODEL,
            "embedding_dimensions": EMBED_DIM,
            "chunk_size": CHUNK_SIZE,
            "chunk_overlap": CHUNK_OVERLAP,
            "ingested_at": __import__("datetime").datetime.now().isoformat(),
            "documents": manifest,
        }, f, indent=2)
    print(f"Ingestion manifest written to {manifest_path}")


if __name__ == "__main__":
    main()
