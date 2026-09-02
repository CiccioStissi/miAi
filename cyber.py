"""Sezione Cyber - threat intelligence DIFENSIVA.

Fonte: catalogo ufficiale CISA KEV (Known Exploited Vulnerabilities) - vulnerabilita
sfruttate ATTIVAMENTE in the wild adesso. Gratis, nessuna chiave.
Mostra: CVE, prodotto, cosa fa, uso in ransomware, e cosa fare per difendersi.

Uso CLI: python cyber.py
"""
import json
import re
from pathlib import Path
import requests

KEV = "https://www.cisa.gov/sites/default/files/feeds/known_exploited_vulnerabilities.json"
CACHE = Path(__file__).parent / "cyber.json"


def stack_keywords(profile):
    """Parole chiave del software realmente presente sul PC (da machine.json)."""
    kw = set()
    if "windows" in (profile.get("os", "") or "").lower():
        kw |= {"windows", "microsoft"}
    for tool in ("docker", "node", "npm", "git", "python"):
        if profile.get(tool):
            kw.add(tool)
    if "nvidia" in ((profile.get("gpu") or {}).get("name", "") or "").lower():
        kw.add("nvidia")
    kw |= {"chrome", "chromium", "edge"}  # browser comuni
    return kw


def personalize(items, profile):
    """Tagga ogni vulnerabilita se colpisce software presente sul PC (relevant/match)."""
    kw = stack_keywords(profile)
    for it in items:
        hay = f"{it.get('vendor','')} {it.get('product','')}".lower()
        hit = next((k for k in kw if re.search(rf"\b{re.escape(k)}\b", hay)), "")
        it["relevant"] = bool(hit)
        it["match"] = hit
    return items


def latest(n=24):
    """Le n vulnerabilita piu recenti aggiunte al catalogo, piu recenti prima."""
    try:
        vulns = requests.get(KEV, timeout=30).json().get("vulnerabilities", [])
    except Exception as e:
        print(f"  ! cyber feed err: {e}")
        return []
    vulns.sort(key=lambda v: v.get("dateAdded", ""), reverse=True)
    out = []
    for v in vulns[:n]:
        ransom = str(v.get("knownRansomwareCampaignUse", "")).lower() == "known"
        out.append({
            "cve": v.get("cveID", ""),
            "vendor": v.get("vendorProject", ""),
            "product": v.get("product", ""),
            "name": v.get("vulnerabilityName", ""),
            "desc": v.get("shortDescription", ""),
            "action": v.get("requiredAction", ""),
            "date": v.get("dateAdded", ""),
            "ransomware": ransom,
            "url": f"https://nvd.nist.gov/vuln/detail/{v.get('cveID','')}",
        })
    return out


def get(refresh=False, n=24):
    """Dalla cache; se manca o refresh, riscarica e salva."""
    if not refresh and CACHE.exists():
        return json.loads(CACHE.read_text(encoding="utf-8"))
    data = latest(n)
    if data:
        CACHE.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
    return data


if __name__ == "__main__":
    for v in latest(10):
        flag = "  [RANSOMWARE]" if v["ransomware"] else ""
        print(f"{v['date']}  {v['cve']}  {v['vendor']} {v['product']}{flag}")
        print(f"    {v['name']}")
