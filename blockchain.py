"""Sezione Blockchain - repo blockchain/web3/smart-contract di tendenza.

Usa la GitHub Search API (come agent.py) su topic mirati. Gratis.
Uso CLI: python blockchain.py
"""
import datetime
import json
from pathlib import Path
import requests

GH_API = "https://api.github.com/search/repositories"
CACHE = Path(__file__).parent / "blockchain.json"


def _since(days):
    return (datetime.date.today() - datetime.timedelta(days=days)).isoformat()


def _search(query, token):
    h = {"Accept": "application/vnd.github+json"}
    if token:
        h["Authorization"] = f"Bearer {token}"
    r = requests.get(GH_API, headers=h,
                     params={"q": query, "sort": "stars", "order": "desc", "per_page": 20}, timeout=30)
    if r.status_code != 200:
        return []
    return r.json().get("items", [])


QUERIES = [
    "topic:blockchain stars:>300 pushed:>{d30}",
    "topic:web3 stars:>300 pushed:>{d30}",
    "language:Solidity stars:>80 pushed:>{d45}",
]
# tool di audit / sicurezza smart-contract
AUDIT_QUERIES = [
    "topic:smart-contract-security stars:>60",
    "topic:security topic:ethereum stars:>150",
    "smart contract audit in:name,description stars:>300 pushed:>{d90}",
]


def _collect(queries, token, audit):
    out = []
    for q in queries:
        q = q.format(d30=_since(30), d45=_since(45), d90=_since(90))
        for it in _search(q, token):
            out.append({
                "full_name": it["full_name"], "url": it["html_url"],
                "description": it.get("description") or "",
                "language": it.get("language") or "",
                "stars": it.get("stargazers_count", 0),
                "topics": (it.get("topics") or [])[:4],
                "audit": audit,
            })
    return out


def fetch(token="", n=24):
    seen, out = set(), []
    for it in _collect(QUERIES, token, False) + _collect(AUDIT_QUERIES, token, True):
        if it["full_name"] in seen:
            continue
        seen.add(it["full_name"])
        out.append(it)
    out.sort(key=lambda d: d["stars"], reverse=True)
    return out[:n]


def get(refresh=False, token="", n=24):
    if not refresh and CACHE.exists():
        return json.loads(CACHE.read_text(encoding="utf-8"))
    data = fetch(token, n)
    if data:
        CACHE.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
    return data


if __name__ == "__main__":
    for d in fetch(n=10):
        print(f"{d['stars']:>7}  {d['full_name']}  [{d['language']}]")
