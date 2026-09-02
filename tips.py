"""Sezione PC - suggerimenti di ottimizzazione su misura.

Ollama genera consigli per rendere il PC piu efficiente/performante, basandosi
sul profilo reale (machine.json). Sono SUGGERIMENTI: valuta prima di applicarli.

Uso CLI: python tips.py
"""
import json
from pathlib import Path
import requests
import llm

import machine

CACHE = Path(__file__).parent / "pc_tips.json"


def generate(profile=None, ollama_url="http://localhost:11434", model="llama3.2:3b"):
    p = profile or machine.get()
    g = p["gpu"]
    profilo = (f"Windows. CPU {p['cpu_cores']} thread ({p['cpu_cores_fisici']} core). "
               f"RAM {p['ram_gb']} GB. GPU {g['name']} {g['vram_mb']} MB VRAM CUDA {g['cuda'] or 'n/d'}. "
               f"Disco liberi {p['disco_libero_gb']} GB.")
    prompt = (
        "Sei un tecnico che ottimizza PC Windows. In base a QUESTO hardware, dai consigli "
        "concreti e sicuri per renderlo piu efficiente e performante. Niente consigli rischiosi "
        "(no overclock spinto, no modifiche registro pericolose). Adatta ai limiti reali "
        "(es. poca VRAM, poco disco).\n\n"
        f"HARDWARE:\n{profilo}\n\n"
        "Rispondi SOLO in JSON con 6 consigli:\n"
        '{"tips":[{"area":"GPU|RAM|Disco|Avvio|Driver|Sistema","titolo":"breve",'
        '"consiglio":"1-2 frasi pratiche","impatto":"basso|medio|alto"}]}'
    )
    try:
        tips = json.loads(llm.generate(prompt, fmt="json", timeout=180)).get("tips", [])
    except Exception as e:
        print(f"  ! tips err: {e}")
        return []
    out = []
    for t in tips[:8]:
        if not isinstance(t, dict):
            continue
        out.append({
            "area": str(t.get("area", "Sistema")).strip(),
            "titolo": str(t.get("titolo", "")).strip(),
            "consiglio": str(t.get("consiglio", "")).strip(),
            "impatto": str(t.get("impatto", "medio")).lower().strip(),
        })
    return out


def get(refresh=False):
    """Dalla cache; se manca o refresh, rigenera via Ollama e salva."""
    if not refresh and CACHE.exists():
        return json.loads(CACHE.read_text(encoding="utf-8"))
    data = generate()
    if data:
        CACHE.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
    return data


if __name__ == "__main__":
    for t in generate():
        print(f"[{t['area']}] ({t['impatto']}) {t['titolo']}\n    {t['consiglio']}")
