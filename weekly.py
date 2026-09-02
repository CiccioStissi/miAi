"""Report settimanale - riassunto degli ultimi 7 giorni.

Incrocia gli snapshot salvati (repo, mercato, idee) e chiede a Ollama una sintesi
in prosa. Se Ollama non risponde, restituisce comunque un riassunto deterministico.

Uso CLI: python weekly.py
"""
import datetime
import json
import sqlite3
from pathlib import Path
import requests
import llm
import yaml

ROOT = Path(__file__).parent
DB = ROOT / "db.sqlite"
CACHE = ROOT / "weekly.json"
CFG = yaml.safe_load((ROOT / "config.yaml").read_text(encoding="utf-8"))


def _data(con, since):
    ideas = con.execute("SELECT DISTINCT titolo,novelta FROM idee_snap WHERE day>=?", (since,)).fetchall()
    ev = con.execute("SELECT topic,COUNT(*) FROM mercato_snap WHERE day>=? GROUP BY topic", (since,)).fetchall()
    repos = con.execute("SELECT full_name,score,reason FROM repos WHERE first_seen>=? "
                        "ORDER BY score DESC LIMIT 10", (since,)).fetchall()
    return ideas, ev, repos


def _facts(ideas, ev, repos):
    L = []
    if repos:
        L.append("Repo emerse: " + "; ".join(f"{f} ({s}/10)" for f, s, _ in repos[:6]))
    if ev:
        L.append("Eventi mercato per settore: " + ", ".join(f"{t}:{n}" for t, n in ev))
    if ideas:
        hi = [t for t, n in ideas if (n or "").lower() == "alta"]
        L.append(f"Idee generate: {len(ideas)} (alta novelta: {len(hi)})")
        if hi:
            L.append("Idee ad alta novelta: " + "; ".join(hi[:5]))
    return "\n".join(L) or "Pochi dati nella settimana."


def generate(ollama_url=None, model=None):
    if not DB.exists():
        return {"testo": "Nessun dato disponibile.", "generato": ""}
    con = sqlite3.connect(DB)
    since = (datetime.date.today() - datetime.timedelta(days=7)).isoformat()
    ideas, ev, repos = _data(con, since)
    facts = _facts(ideas, ev, repos)
    prompt = (
        "Sei un analista. Scrivi un report settimanale in italiano (6-8 frasi, scorrevole) su trend "
        "tecnologici, mercati e opportunita di business, basandoti SOLO sui dati qui sotto. "
        "Chiudi con 1 raccomandazione pratica.\n\n=== DATI SETTIMANA ===\n" + facts
    )
    testo = ""
    try:
        testo = llm.generate(prompt, timeout=180).strip()
    except Exception as e:
        print(f"  ! weekly err: {e}")
    if not testo:  # fallback deterministico
        testo = "Report settimanale (sintesi automatica):\n\n" + facts
    out = {"testo": testo, "facts": facts,
           "generato": datetime.datetime.now().strftime("%Y-%m-%d %H:%M")}
    CACHE.write_text(json.dumps(out, ensure_ascii=False), encoding="utf-8")
    return out


def get():
    return json.loads(CACHE.read_text(encoding="utf-8")) if CACHE.exists() else {"testo": "", "generato": ""}


if __name__ == "__main__":
    print(generate()["testo"])
