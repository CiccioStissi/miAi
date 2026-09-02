"""Sezione Idee - spunti di startup dai trend rilevati.

Ollama incrocia i segnali (repo GitHub di tendenza + minacce cyber CISA/NIST) e
propone idee di startup innovative. La "novita di mercato" e' STIMATA dal modello,
non una verifica reale: ogni idea include una query per validarla tu su Google.

Uso CLI: python ideas.py   (usa le cache esistenti github/cyber via agent+moduli)
"""
import json
from pathlib import Path
import requests
import llm

CACHE = Path(__file__).parent / "ideas.json"
INTERESTS_FILE = Path(__file__).parent / "interests.json"


# Angolazioni di settore: un batch per angolo => tante idee, spaziando davvero.
# Ricerca continua su TUTTI gli ambiti del mondo, sempre con taglio tecnologico.
ANGOLI = [
    "sanita, biotech e dispositivi medici",
    "energia, clima e sostenibilita",
    "fintech, finanza e pagamenti",
    "AI e software B2B / automazione aziendale",
    "mobilita, automotive e logistica",
    "cybersecurity e difesa",
    "agrifood e materie prime",
    "consumer, creator economy e istruzione",
    "spazio, aerospazio e satelliti",
    "gaming, esports e intrattenimento interattivo",
    "legaltech, regtech e pubblica amministrazione",
    "proptech, immobiliare e smart building",
    "sport, fitness e wellness tech",
    "media, editoria e creator tools",
    "robotica, droni e automazione fisica",
    "industria 4.0, manifattura e IoT",
    "retail, e-commerce e supply chain",
    "travel, ospitalita e turismo",
    "insurtech e gestione del rischio",
    "HR, futuro del lavoro e produttivita",
    "materiali avanzati, chimica e nanotech",
    "quantum computing e crittografia avanzata",
    "musica, audio e podcasting tech",
    "arte, moda e design digitale",
]

# Settori per la modalita 'Scopri' (swipe): etichette brevi per il selettore UI.
SETTORI = [
    "Sanita", "Energia e clima", "Fintech", "AI e software B2B", "Mobilita",
    "Cybersecurity", "Agrifood", "Education", "Spazio", "Gaming", "Legaltech",
    "Proptech", "Sport e wellness", "Media e creator", "Robotica", "Industria 4.0",
    "Retail e commerce", "Travel", "Insurtech", "Lavoro e HR", "Materiali e nanotech",
    "Quantum", "Musica e audio", "Arte e moda",
]


def _slug(s):
    import re
    return re.sub(r"[^a-z0-9]+", "-", s.lower()).strip("-")


# SETTORI e ANGOLI sono paralleli (stesso indice). L'utente sceglie i suoi interessi:
# le idee vengono generate SOLO sugli angoli scelti (in interests.json).
TOPICS = [{"id": _slug(SETTORI[i]), "label": SETTORI[i], "angle": ANGOLI[i]} for i in range(len(ANGOLI))]
_IDS = {t["id"] for t in TOPICS}


def interests():
    """Interessi scelti dall'utente (id in interests.json). Default: tutti."""
    try:
        ids = [i for i in json.loads(INTERESTS_FILE.read_text(encoding="utf-8")) if i in _IDS]
        if ids:
            return ids
    except Exception:
        pass
    return [t["id"] for t in TOPICS]


def set_interests(ids):
    ids = [i for i in ids if i in _IDS]
    INTERESTS_FILE.write_text(json.dumps(ids, ensure_ascii=False), encoding="utf-8")
    return ids


def catalog():
    """Per l'interfaccia: catalogo interessi + selezione corrente."""
    return {"catalog": [{"id": t["id"], "label": t["label"]} for t in TOPICS],
            "selected": interests()}

_ONE_SPEC = ('Rispondi SOLO in JSON, una sola idea:\n{"titolo":"nome breve","descrizione":"cosa fa in 1-2 frasi",'
             '"problema":"quale problema risolve","perche_ora":"perche e il momento giusto",'
             '"novelta":"alta|media|bassa","tam":"dimensione mercato stimata in 1 frase",'
             '"fattibilita":"alta|media|bassa","passi":["passo 1","passo 2","passo 3"],'
             '"settore":"settore principale","verifica":"query google per controllare se esiste gia"}')

_TWIST = [
    "radicale e di nicchia", "B2B enterprise", "consumer di massa", "open-source monetizzabile",
    "AI-first", "hardware + software", "marketplace a due lati", "API/infrastruttura per sviluppatori",
    "sostenibile e a basso impatto", "low-cost per mercati emergenti", "premium e di lusso",
    "community-driven", "data/analytics", "mobile-first",
]


def one(settore, ollama_url="http://localhost:11434", model="llama3.2:3b"):
    """Genera UNA sola idea tech nel settore dato (modalita swipe). Variata a ogni chiamata."""
    import random
    seed = random.randint(1, 10 ** 6)
    prompt = ("Sei un generatore di idee di startup TECH originali. Proponi UNA sola idea, nuova e "
              f"concreta, nel settore: {settore}. Taglio: {random.choice(_TWIST)}. Deve essere "
              "realizzabile da uno sviluppatore full-stack con GPU locale. Evita idee ovvie e gia viste, "
              f"sorprendimi (seed {seed}).\n" + _ONE_SPEC)
    try:
        d = _clean(json.loads(llm.generate(prompt, fmt="json",
                   options={"temperature": 0.95, "top_p": 0.95, "seed": seed}, timeout=120)))
        if not d:
            return {"error": "idea vuota"}
        if not d.get("settore"):
            d["settore"] = settore
        return d
    except Exception as e:
        return {"error": f"Ollama: {e}"[:120]}

_SPEC = ('Rispondi SOLO in JSON:\n{"idee":[{"titolo":"nome breve","descrizione":"cosa fa in 1-2 frasi",'
         '"problema":"quale problema risolve","perche_ora":"perche e il momento giusto",'
         '"novelta":"alta|media|bassa","tam":"dimensione mercato stimata in 1 frase",'
         '"fattibilita":"alta|media|bassa","passi":["passo 1","passo 2","passo 3"],'
         '"settore":"settore principale","verifica":"query google per controllare se esiste gia"}]}')


def _norm(t):
    import re
    return re.sub(r"[^a-z0-9]+", " ", (t or "").lower()).strip()


def _clean(it):
    if not isinstance(it, dict) or not str(it.get("titolo", "")).strip():
        return None
    d = {k: str(it.get(k, "")).strip() for k in
         ("titolo", "descrizione", "problema", "perche_ora", "novelta", "tam", "fattibilita", "settore", "verifica")}
    passi = it.get("passi")
    d["passi"] = [str(x).strip() for x in passi][:3] if isinstance(passi, list) else []
    return d


def generate(github, cyber, mercato=None, profile=None, ollama_url="http://localhost:11434",
             model="llama3.2:3b", per_angolo=5):
    gh = "\n".join(f"- {d['full_name']}: {d.get('description','')[:120]}" for d in github[:12])
    cy = "\n".join(f"- {d.get('name','')} ({d.get('product','')})" for d in cyber[:8])
    mk = "\n".join(
        f"[{t.get('topic','')}]\n" + "\n".join(f"  - {i.get('title','')}" for i in (t.get('items') or [])[:4])
        for t in (mercato or [])
    )
    p = profile or {}
    skills = ", ".join(filter(None, [
        ", ".join((p.get("dev") or {}).keys()) if isinstance(p.get("dev"), dict) else "",
        "GPU " + (p.get("gpu", {}) or {}).get("name", "") if p.get("gpu") else "",
    ])) or "sviluppatore full-stack Python/TS, blockchain, GPU locale"
    base = (
        "Sei un analista che individua opportunita di startup/business dai trend attuali.\n"
        "Trend GitHub recenti:\n" + (gh or "-") + "\n\nMinacce/temi cyber attuali (CISA/NIST):\n" + (cy or "-") + "\n\n"
        "Eventi di mercato per settore:\n" + (mk or "-") + "\n\n"
        f"Profilo/competenze di chi realizza: {skills}.\n\n"
    )
    out, seen = [], set()
    sel = set(interests())
    angoli = [t["angle"] for t in TOPICS if t["id"] in sel] or ANGOLI
    for angolo in angoli:
        prompt = (base + f"CONCENTRATI sull'angolo: {angolo}. Proponi {per_angolo} idee di startup "
                  "innovative e DIVERSE tra loro, concrete e realizzabili con quel profilo. Per ciascuna "
                  "valuta novelta (mercato affollato?), dimensione mercato, fattibilita, e i primi 3 passi.\n" + _SPEC)
        try:
            idee = json.loads(llm.generate(prompt, fmt="json", timeout=240)).get("idee", [])
        except Exception as e:
            print(f"  ! ideas err [{angolo}]: {e}")
            continue
        for it in idee[:per_angolo + 2]:
            d = _clean(it)
            if not d:
                continue
            k = _norm(d["titolo"])
            if not k or k in seen:
                continue
            seen.add(k)
            if not d.get("settore"):
                d["settore"] = angolo.split(",")[0]
            out.append(d)
        print(f"      idee [{angolo}]: totale {len(out)}")
    if out:
        CACHE.write_text(json.dumps(out, ensure_ascii=False), encoding="utf-8")
    return out




def onepager(idea, ollama_url="http://localhost:11434", model="llama3.2:3b"):
    """Trasforma un'idea/prodotto in un one-pager strutturato pronto per gli investitori."""
    ctx = "\n".join(f"{k}: {v}" for k, v in idea.items()
                    if k in ("titolo", "descrizione", "cosa_fa", "problema", "tam", "target",
                             "modello", "prezzo_eur") and v)
    prompt = ("Sei un consulente che scrive one-pager per startup. Dai il documento sintetico e concreto "
              "per presentare questa idea a un investitore. Tono diretto, niente fuffa.\n\nIDEA:\n" + ctx +
              '\n\nRispondi SOLO in JSON: {"titolo":"","tagline":"una riga che vende","problema":"",'
              '"soluzione":"","mercato":"dimensione e a chi","modello":"come guadagna",'
              '"perche_ora":"","perche_noi":"vantaggio","traction":"come parti e primi obiettivi",'
              '"ask":"quanto raccogli e per cosa"}')
    try:
        d = json.loads(llm.generate(prompt, fmt="json", timeout=150))
        if not str(d.get("titolo", "")).strip():
            d["titolo"] = idea.get("titolo", "One-pager")
        return d
    except Exception as e:
        return {"error": f"Ollama: {e}"[:140]}


def get():
    """Solo lettura cache (la generazione richiede i segnali, fatta nel run)."""
    return json.loads(CACHE.read_text(encoding="utf-8")) if CACHE.exists() else []


if __name__ == "__main__":
    import cyber
    gh = json.loads((Path(__file__).parent / "blockchain.json").read_text(encoding="utf-8")) \
        if (Path(__file__).parent / "blockchain.json").exists() else []
    for it in generate(gh, cyber.get()):
        print(f"[{it['novelta']}] {it['titolo']} - {it['descrizione']}")
