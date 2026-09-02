"""Fase 4 - verdetto di compatibilita repo vs PC + comandi install.

Per una repo: legge README + file di dipendenze da GitHub, li confronta col
profilo macchina (Fase 3) via Ollama, ritorna verdetto strutturato.
NON esegue nulla: suggerisce solo comandi, li lanci tu.

Uso CLI: python advisor.py owner/repo
"""
import json
import re
import requests
import llm

import machine

GH = "https://api.github.com"
# file che rivelano lo stack / metodo di installazione
DEP_HINTS = ("requirements.txt", "pyproject.toml", "setup.py", "environment.yml",
             "package.json", "Dockerfile", "docker-compose.yml", "Cargo.toml", "go.mod")


def build_commands(full_name, deps):
    """Comandi install DETERMINISTICI dai file rilevati (Windows PowerShell).
    Piu affidabili di quelli inventati da un LLM piccolo."""
    repo = full_name.split("/")[-1]
    cmds = [f"git clone https://github.com/{full_name}.git", f"cd {repo}"]
    if "environment.yml" in deps:
        cmds.append("conda env create -f environment.yml")
    elif any(f in deps for f in ("requirements.txt", "pyproject.toml", "setup.py")):
        cmds += ["python -m venv .venv", ".\\.venv\\Scripts\\Activate.ps1"]
        if "requirements.txt" in deps:
            cmds.append("pip install -r requirements.txt")
        else:
            cmds.append("pip install .")
    if "package.json" in deps:
        cmds.append("npm install")
    if "Cargo.toml" in deps:
        cmds.append("cargo build --release")
    if "go.mod" in deps:
        cmds.append("go build ./...")
    if "docker-compose.yml" in deps:
        cmds.append("docker compose up -d")
    elif "Dockerfile" in deps:
        cmds += [f"docker build -t {repo} .", f"docker run --rm {repo}"]
    return cmds


def _headers(token):
    h = {"Accept": "application/vnd.github+json"}
    if token:
        h["Authorization"] = f"Bearer {token}"
    return h


def _fetch_context(full_name, token):
    """README (troncato) + lista file dipendenze presenti nella root."""
    o_r = full_name.split("/")
    if len(o_r) != 2:
        return "", []
    owner, repo = o_r
    readme = ""
    try:
        r = requests.get(f"{GH}/repos/{owner}/{repo}/readme",
                         headers={**_headers(token), "Accept": "application/vnd.github.raw"}, timeout=20)
        if r.status_code == 200:
            readme = r.text[:4000]
    except Exception:
        pass
    deps = []
    try:
        r = requests.get(f"{GH}/repos/{owner}/{repo}/contents", headers=_headers(token), timeout=20)
        if r.status_code == 200:
            names = {it["name"] for it in r.json() if it.get("type") == "file"}
            deps = [f for f in DEP_HINTS if f in names]
    except Exception:
        pass
    return readme, deps


def assess(full_name, description="", language="", token="", profile=None, ollama_url="http://localhost:11434", model="llama3.2:3b"):
    """Ritorna dict verdetto: compat/motivo/requisiti/comandi/note."""
    p = profile or machine.get()
    g = p["gpu"]
    readme, deps = _fetch_context(full_name, token)
    profilo = (f"OS Windows. CPU {p['cpu_cores']} thread. RAM {p['ram_gb']} GB. "
               f"GPU {g['name']} con {g['vram_mb']} MB VRAM, CUDA {g['cuda'] or 'n/d'}. "
               f"Disco liberi {p['disco_libero_gb']} GB. "
               f"Installati: python={p['python']}, node={p['node']}, npm={p['npm']}, "
               f"docker={p['docker']}, git={p['git']}.")
    prompt = (
        "Sei un assistente che valuta se una repository GitHub puo girare sul PC dell'utente "
        "e come installarla. Rispondi in italiano.\n\n"
        f"PROFILO PC:\n{profilo}\n\n"
        f"REPO: {full_name} (linguaggio {language}). Descrizione: {description}\n"
        f"File di dipendenze presenti: {', '.join(deps) or 'nessuno rilevato'}\n"
        f"README (estratto):\n{readme or '(non disponibile)'}\n\n"
        "Valuta requisiti (VRAM/RAM/CUDA/tool) contro il PC. I comandi install devono essere "
        "per Windows PowerShell, adattati ai file presenti (pip/npm/docker/conda). "
        "Se serve piu VRAM di quella disponibile, dillo e proponi fallback CPU se esiste.\n"
        "Rispondi SOLO in JSON:\n"
        '{"compat":"si|parziale|no","motivo":"1-2 frasi","requisiti":"cosa serve o non specificati",'
        '"comandi":["comando1","comando2"],"note":"avvertenze o vuoto"}'
    )
    try:
        data = json.loads(llm.generate(prompt, fmt="json", timeout=180))
    except Exception as e:
        return {"compat": "?", "motivo": f"analisi non riuscita: {e}", "requisiti": "",
                "comandi": [], "note": ""}
    # normalizza
    data["compat"] = str(data.get("compat", "?")).lower().strip()
    if data["compat"] not in ("si", "parziale", "no"):
        data["compat"] = "?"
    if not isinstance(data.get("comandi"), list):
        data["comandi"] = [str(data.get("comandi"))] if data.get("comandi") else []
    # comandi deterministici dai file rilevati; l'LLM li usa solo se non abbiamo nulla
    det = build_commands(full_name, deps)
    data["comandi"] = det if deps else [str(c) for c in data.get("comandi", [])][:8]
    for k in ("motivo", "requisiti", "note"):
        data[k] = _flat(data.get(k, ""))
    data["deps"] = deps
    return data


def _flat(v):
    """llama3.2:3b a volte mette dict/list dove serve testo: appiattisci leggibile."""
    if isinstance(v, dict):
        return "; ".join(f"{k}: {w}" for k, w in v.items())
    if isinstance(v, list):
        return "; ".join(str(x) for x in v)
    return str(v).strip()


if __name__ == "__main__":
    import sys
    if len(sys.argv) < 2:
        print("uso: python advisor.py owner/repo")
        sys.exit(1)
    v = assess(sys.argv[1])
    print(f"\nCOMPAT: {v['compat'].upper()}  -  {v['motivo']}")
    print(f"requisiti: {v['requisiti']}")
    if v["comandi"]:
        print("install:")
        for c in v["comandi"]:
            print(f"  {c}")
    if v["note"]:
        print(f"note: {v['note']}")
