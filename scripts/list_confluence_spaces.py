#!/usr/bin/env python3
"""List Confluence spaces accessible with the Jira/Atlassian API token.

Reads JIRA_BASE_URL, JIRA_EMAIL, JIRA_API_TOKEN from a .env file
(defaults to ../../vp_report_generator/.env, override with ENV_FILE).
"""
import os
import sys
import json
import base64
import urllib.request

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

env_file = os.environ.get("ENV_FILE", os.path.expanduser("~/Downloads/vp_report_generator/.env"))
env = load_env(env_file)

base_url = env.get("JIRA_BASE_URL", "").rstrip("/")
email = env.get("JIRA_EMAIL", "")
token = env.get("JIRA_API_TOKEN", "")

if not (base_url and email and token):
    print("Missing JIRA_BASE_URL / JIRA_EMAIL / JIRA_API_TOKEN in", env_file)
    sys.exit(1)

url = f"{base_url}/wiki/rest/api/space?limit=50"
auth = base64.b64encode(f"{email}:{token}".encode()).decode()
req = urllib.request.Request(url, headers={
    "Authorization": f"Basic {auth}",
    "Accept": "application/json",
})

try:
    with urllib.request.urlopen(req) as resp:
        data = json.load(resp)
except urllib.error.HTTPError as e:
    print(f"HTTP {e.code}: {e.read().decode()}")
    sys.exit(1)

print(f"{'Key':<15} {'Name':<40} {'Type':<10}")
for s in data.get("results", []):
    print(f"{s['key']:<15} {s['name']:<40} {s.get('type',''):<10}")

if not data.get("results"):
    print("(no spaces returned)")
