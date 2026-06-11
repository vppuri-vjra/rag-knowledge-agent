#!/usr/bin/env python3
"""Publish the SKU Weekly Sales & Conversion content as a Jira Epic.

Creates an Epic in the project (JIRA_PROJECT_KEY) with a narrative summary
in the description, and attaches the full markdown (with the 624-row weekly
data tables) as a file attachment for the novacart-int RAG ingestion job.

Reads JIRA_BASE_URL, JIRA_EMAIL, JIRA_API_TOKEN, JIRA_PROJECT_KEY from .env
in the same directory tree (default: ./.env).
"""
import os
import re
import json
import base64
import urllib.request
import urllib.error
import ssl
import certifi

SSL_CTX = ssl.create_default_context(cafile=certifi.where())

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC_MD = os.path.join(ROOT, "confluence_pages", "sku_weekly_sales_conversion_3y_with_revenue.md")


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
BASE = env["JIRA_BASE_URL"].rstrip("/")
AUTH = base64.b64encode(f"{env['JIRA_EMAIL']}:{env['JIRA_API_TOKEN']}".encode()).decode()
PROJECT = env["JIRA_PROJECT_KEY"]


def api(method, path, data=None, headers=None, raw=False):
    url = f"{BASE}{path}"
    h = {"Authorization": f"Basic {AUTH}", "Accept": "application/json"}
    if headers:
        h.update(headers)
    body = None
    if data is not None and not raw:
        body = json.dumps(data).encode()
        h["Content-Type"] = "application/json"
    elif raw is not None and data is not None:
        body = data
    req = urllib.request.Request(url, data=body, headers=h, method=method)
    try:
        with urllib.request.urlopen(req, context=SSL_CTX) as resp:
            ct = resp.headers.get("Content-Type", "")
            raw_resp = resp.read()
            if "json" in ct:
                return resp.status, json.loads(raw_resp)
            return resp.status, raw_resp
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode()


def text_para(text):
    return {"type": "paragraph", "content": [{"type": "text", "text": text}]}


def heading(text, level=3):
    return {"type": "heading", "attrs": {"level": level}, "content": [{"type": "text", "text": text}]}


def build_description(src):
    # Strip HTML comment metadata block
    src = re.sub(r"<!--.*?-->\s*", "", src, flags=re.S)
    lines = src.split("\n")

    content = []
    para_buf = []

    def flush():
        if para_buf:
            text = " ".join(l.strip() for l in para_buf if l.strip())
            if text:
                content.append(text_para(text))
            para_buf.clear()

    for line in lines:
        stripped = line.strip()
        if stripped.startswith("|"):
            # skip table rows entirely - full data lives in the attachment
            continue
        if stripped.startswith("# "):
            flush()
            content.append(heading(stripped.lstrip("# ").strip("*"), level=2))
            continue
        if stripped.startswith("**") and stripped.endswith("**") and len(stripped) < 100:
            flush()
            content.append(heading(stripped.strip("*"), level=4))
            continue
        if not stripped:
            flush()
            continue
        para_buf.append(stripped)
    flush()

    content.append({"type": "rule"})
    content.append(text_para(
        "Full weekly data tables (156 weeks x 4 SKUs, 624 rows: units sold, "
        "site visits, conversion rate, unit price, weekly revenue) are attached "
        "as sku_weekly_sales_conversion_3y_with_revenue.md on this Epic."
    ))

    return {"type": "doc", "version": 1, "content": content}


def main():
    src = open(SRC_MD).read()
    description = build_description(src)

    payload = {
        "fields": {
            "project": {"key": PROJECT},
            "summary": "SKU Weekly Sales & Conversion - 3Y with Revenue",
            "description": description,
            "issuetype": {"name": "Epic"},
            "labels": ["novacart-int", "rag-knowledge-agent"],
        }
    }

    status, resp = api("POST", "/rest/api/3/issue", data=payload)
    if status not in (200, 201):
        print(f"Failed to create Epic: HTTP {status}")
        print(resp)
        return

    key = resp["key"]
    issue_url = f"{BASE}/browse/{key}"
    print(f"Created Epic: {issue_url}")

    # Attach the full markdown source as a file
    boundary = "----novacartboundary"
    with open(SRC_MD, "rb") as f:
        file_bytes = f.read()
    body = (
        f"--{boundary}\r\n"
        f'Content-Disposition: form-data; name="file"; filename="sku_weekly_sales_conversion_3y_with_revenue.md"\r\n'
        f"Content-Type: text/markdown\r\n\r\n"
    ).encode() + file_bytes + f"\r\n--{boundary}--\r\n".encode()

    status, resp = api(
        "POST",
        f"/rest/api/3/issue/{key}/attachments",
        data=body,
        headers={
            "X-Atlassian-Token": "no-check",
            "Content-Type": f"multipart/form-data; boundary={boundary}",
        },
        raw=True,
    )
    if status not in (200, 201):
        print(f"Failed to attach file: HTTP {status}")
        print(resp)
        return

    print(f"Attached sku_weekly_sales_conversion_3y_with_revenue.md to {key}")
    print(f"\nEpic URL: {issue_url}")


if __name__ == "__main__":
    main()
