"""Verifica web delle idee - ricerca DuckDuckGo (HTML, gratis, senza chiave).

Per ogni idea cerca sul web i concorrenti/riferimenti reali, cosi la "novita"
non e' piu solo stimata dal modello ma ancorata a risultati veri.
Uso CLI: python verify.py "startup che fa X"
"""
import html
import re
import sys
from urllib.parse import parse_qs, unquote, urlparse
import requests

DDG = "https://html.duckduckgo.com/html/"
_RESULT = re.compile(r'result__a"[^>]*href="([^"]+)"[^>]*>(.*?)</a>', re.S)


def _clean(u):
    if "uddg=" in u:
        q = parse_qs(urlparse(u).query)
        return unquote(q.get("uddg", [u])[0])
    return u.lstrip("/") and ("https:" + u if u.startswith("//") else u)


def search(query, n=4):
    try:
        r = requests.post(DDG, data={"q": query},
                         headers={"User-Agent": "Mozilla/5.0"}, timeout=20)
        r.raise_for_status()
    except Exception as e:
        print(f"  ! verify err: {e}")
        return []
    out, seen = [], set()
    for m in _RESULT.finditer(r.text):
        url = _clean(m.group(1))
        title = html.unescape(re.sub(r"<.*?>", "", m.group(2)).strip())
        if not title or url in seen:
            continue
        seen.add(url)
        out.append({"title": title[:110], "url": url})
        if len(out) >= n:
            break
    return out


def enrich(idee, n=4):
    """Aggiunge a ogni idea la lista 'web' (risultati reali) e un flag heuristico."""
    for it in idee:
        q = (it.get("verifica") or it.get("titolo") or "").strip()
        res = search(q, n) if q else []
        it["web"] = res
        # segnale grezzo: il titolo dell'idea compare gia in un risultato?
        t = set(w for w in re.findall(r"\w+", (it.get("titolo", "")).lower()) if len(w) > 3)
        hit = any(len(t & set(re.findall(r"\w+", r["title"].lower()))) >= 2 for r in res)
        it["web_esiste"] = bool(res) and hit
    return idee


if __name__ == "__main__":
    q = " ".join(sys.argv[1:]) or "app AI riprese sportive calcio a 5 automatiche"
    for r in search(q):
        print(f"- {r['title']}\n  {r['url']}")
