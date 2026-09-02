"""Prezzi crypto live - CoinGecko API (gratis, senza chiave).

Snapshot salvato nella cache per la dashboard standalone; il server locale
(/crypto) puo rinfrescarli live. Uso CLI: python crypto.py
"""
import json
from pathlib import Path
import requests

CACHE = Path(__file__).parent / "crypto.json"
URL = "https://api.coingecko.com/api/v3/coins/markets"


def fetch(n=12):
    try:
        r = requests.get(URL, headers={"Accept": "application/json"},
                         params={"vs_currency": "usd", "order": "market_cap_desc",
                                 "per_page": n, "page": 1, "price_change_percentage": "24h"},
                         timeout=20)
        r.raise_for_status()
        return [{"sym": c["symbol"].upper(), "name": c["name"],
                 "price": c["current_price"],
                 "chg": round(c.get("price_change_percentage_24h") or 0, 2)}
                for c in r.json()]
    except Exception as e:
        print(f"  ! crypto err: {e}")
        return []


def get(refresh=False, n=12):
    if not refresh and CACHE.exists():
        return json.loads(CACHE.read_text(encoding="utf-8"))
    d = fetch(n)
    if d:
        CACHE.write_text(json.dumps(d, ensure_ascii=False), encoding="utf-8")
    return d


if __name__ == "__main__":
    for c in fetch():
        print(f"{c['sym']:>6}  ${c['price']:<12}  {c['chg']:+}%")
