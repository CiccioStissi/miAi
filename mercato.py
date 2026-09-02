"""Sezione Mercato - eventi che muovono i mercati, per settore.

Pesca titoli reali da Google News RSS (gratis, senza chiave, XML stdlib) per
ogni topic in config.yaml (medico, geopolitica, automotive, energia...).
Servono da segnale reale per generare le idee di startup (ideas.py).

Uso CLI: python mercato.py
"""
import json
import xml.etree.ElementTree as ET
from pathlib import Path
from urllib.parse import quote
import requests
import llm
import yaml

ROOT = Path(__file__).parent
CACHE = ROOT / "mercato.json"
RSS = "https://news.google.com/rss/search?q={q}&hl=it&gl=IT&ceid=IT:it"

TOPICS_FILE = ROOT / "topics.json"

# Catalogo GENERALE di argomenti: l'utente sceglie quali seguire nel Giornale.
# id: (etichetta, categoria, query Google News IT, e' un tema di mercato?)
CATALOG = {
    # Attualita
    "cronaca": ("Cronaca", "Attualita", "cronaca italia", False),
    "politica": ("Politica", "Attualita", "politica italia governo", False),
    "esteri": ("Esteri", "Attualita", "esteri mondo notizie", False),
    "geopolitica": ("Geopolitica", "Attualita", "geopolitica sanzioni conflitto", False),
    "economia": ("Economia", "Attualita", "economia italia notizie", True),
    # Mercati / finanza
    "mercati": ("Borse e mercati", "Mercati", "borsa mercati azioni indici", True),
    "macro": ("Inflazione e tassi", "Mercati", "inflazione tassi BCE PIL", True),
    "immobiliare": ("Mercato immobiliare", "Mercati", "mercato immobiliare case prezzi affitti", True),
    "energia": ("Energia", "Mercati", "prezzo energia petrolio gas rinnovabili", True),
    "crypto": ("Cripto", "Mercati", "criptovalute bitcoin ethereum", True),
    "lavoro": ("Lavoro", "Mercati", "lavoro occupazione assunzioni", False),
    # Tech
    "tech": ("Tecnologia", "Tech", "tecnologia notizie", False),
    "ai": ("Intelligenza artificiale", "Tech", "intelligenza artificiale AI", False),
    "cyber": ("Cybersecurity", "Tech", "cybersecurity attacchi informatici sicurezza", False),
    "startup": ("Startup", "Tech", "startup innovazione finanziamenti", True),
    "gadget": ("Gadget e smartphone", "Tech", "smartphone gadget recensioni tech", False),
    "gaming": ("Videogiochi", "Tech", "videogiochi gaming novita", False),
    "spazio": ("Spazio", "Tech", "spazio astronomia missioni", False),
    # Salute e scienza
    "salute": ("Salute", "Salute e scienza", "salute medicina benessere", False),
    "scienza": ("Scienza", "Salute e scienza", "scienza ricerca scoperte", False),
    "ambiente": ("Ambiente e clima", "Salute e scienza", "ambiente clima sostenibilita", False),
    "alimentazione": ("Alimentazione", "Salute e scienza", "alimentazione nutrizione cibo salute", False),
    # Sport
    "calcio": ("Calcio", "Sport", "calcio serie A notizie", False),
    "sport": ("Sport (tutti)", "Sport", "sport notizie", False),
    "motori": ("Motori e F1", "Sport", "formula 1 motogp motori", False),
    "tennis": ("Tennis", "Sport", "tennis atp notizie", False),
    # Cultura e intrattenimento
    "cinema": ("Cinema e serie TV", "Cultura", "cinema serie tv streaming", False),
    "musica": ("Musica", "Cultura", "musica concerti classifiche", False),
    "cultura": ("Cultura e libri", "Cultura", "cultura libri arte", False),
    "moda": ("Moda e lifestyle", "Cultura", "moda lifestyle tendenze", False),
    "viaggi": ("Viaggi", "Cultura", "viaggi turismo mete", False),
    "auto": ("Automotive", "Cultura", "auto elettriche case automobilistiche", True),
}
# Set iniziale sensato (finche l'utente non sceglie)
DEFAULT_FOLLOWED = ["cronaca", "politica", "economia", "tech", "ai", "salute", "sport", "esteri"]


def followed():
    """Argomenti scelti dall'utente (topics.json). Fallback a un set di default.
    Filtra via gli id non piu nel catalogo."""
    try:
        ids = json.loads(TOPICS_FILE.read_text(encoding="utf-8"))
        ids = [i for i in ids if i in CATALOG]
        if ids:
            return ids
    except Exception:
        pass
    return DEFAULT_FOLLOWED


def set_followed(ids):
    ids = [i for i in ids if i in CATALOG][:24]  # cap: niente centinaia di fetch RSS
    TOPICS_FILE.write_text(json.dumps(ids, ensure_ascii=False), encoding="utf-8")
    return ids


def catalog():
    """Per l'interfaccia: catalogo + selezione corrente."""
    return {"catalog": [{"id": k, "label": v[0], "cat": v[1]} for k, v in CATALOG.items()],
            "followed": followed()}


def _news(query, n=5):
    hl, gl, ceid = llm.news_locale()
    url = f"https://news.google.com/rss/search?q={quote(query)}&hl={hl}&gl={gl}&ceid={ceid}"
    try:
        r = requests.get(url, headers={"User-Agent": "Mozilla/5.0"}, timeout=20)
        r.raise_for_status()
        root = ET.fromstring(r.content)
    except Exception as e:
        print(f"  ! mercato err ({query}): {e}")
        return []
    out = []
    for it in root.iter("item"):
        title = (it.findtext("title") or "").strip()
        # Google News mette " - Fonte" in coda al titolo
        src = it.findtext("{http://news.google.com/rss}source") or ""
        if not src and " - " in title:
            title, src = title.rsplit(" - ", 1)
        out.append({"title": title.strip(), "url": (it.findtext("link") or "").strip(),
                    "date": (it.findtext("pubDate") or "")[:16], "source": src.strip()})
        if len(out) >= n:
            break
    return out


def _norm(title):
    """Chiave per de-duplicare la stessa notizia tra settori diversi.
    ponytail: match su prime 7 parole normalizzate, non semantico (embeddings se servisse)."""
    import re
    w = re.sub(r"[^a-z0-9 ]", " ", title.lower()).split()
    return " ".join(w[:7])


def fetch(n=5):
    seen, out = set(), []
    for tid in followed():
        label, cat, q, market = CATALOG[tid]
        items = []
        for it in _news(q, n + 3):          # pesco qualcuno in piu, poi filtro i doppioni
            k = _norm(it["title"])
            if not k or k in seen:
                continue
            seen.add(k)
            items.append(it)
            if len(items) >= n:
                break
        out.append({"id": tid, "topic": label, "cat": cat, "query": q, "market": market, "items": items})
    return out


def analyze(topics, ollama_url="http://localhost:11434", model="llama3.2:3b"):
    """Ollama tagga i temi di MERCATO: direzione, impatto, 'cosa significa'.
    Le notizie generali (cronaca, sport...) restano senza analisi: sono solo titoli.
    Degrada senza errori se il modello non risponde."""
    blocks = "\n\n".join(
        f"[{t['topic']}]\n" + "\n".join(f"- {i['title']}" for i in (t.get('items') or [])[:5])
        for t in topics if t.get('items') and t.get('market')
    )
    if not blocks:
        return topics
    prompt = (
        "Sei un analista di mercato. Per OGNI settore qui sotto valuta l'effetto probabile "
        "sui mercati dalle notizie.\n\n" + blocks + "\n\n"
        "Rispondi SOLO in JSON:\n"
        '{"analisi":[{"topic":"nome esatto del settore",'
        '"direzione":"rialzo|ribasso|rischio|neutro",'
        '"impatto":"alto|medio|basso",'
        '"significa":"1 frase: cosa implica per aziende/investitori"}]}'
    )
    try:
        a = {x.get("topic", "").strip(): x for x in json.loads(llm.generate(prompt, fmt="json", timeout=240)).get("analisi", [])}
    except Exception as e:
        print(f"  ! mercato analyze err: {e}")
        return topics
    for t in topics:
        x = a.get(t["topic"])
        if isinstance(x, dict):
            t["analisi"] = {k: str(x.get(k, "")).strip() for k in ("direzione", "impatto", "significa")}
            t["analisi"]["direzione"] = _dir(t["analisi"]["direzione"])
    return topics


def _dir(v):
    """Snap la direzione ai 4 valori validi (il modello a volte inventa parole)."""
    v = (v or "").lower()
    if "rial" in v or "rialz" in v or "cresc" in v or "posit" in v:
        return "rialzo"
    if "ribas" in v or "cal" in v or "negat" in v or "scend" in v:
        return "ribasso"
    if "risch" in v or "volat" in v or "incert" in v:
        return "rischio"
    return v if v in ("rialzo", "ribasso", "rischio", "neutro") else "neutro"


def get(refresh=False, n=5):
    if not refresh and CACHE.exists():
        return json.loads(CACHE.read_text(encoding="utf-8"))
    d = fetch(n)
    if any(t["items"] for t in d):
        CACHE.write_text(json.dumps(d, ensure_ascii=False), encoding="utf-8")
    return d


if __name__ == "__main__":
    for t in fetch():
        print(f"\n== {t['topic']} ==")
        for i in t["items"]:
            print(f"- {i['title']}  [{i['source']}]")
