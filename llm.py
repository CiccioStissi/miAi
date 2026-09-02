"""Backend LLM configurabile: NON obbliga Ollama.

Ognuno usa il modello che il suo PC (o la sua API) regge:
  - provider "ollama"  -> server Ollama locale  (i dati RESTANO sul PC)
  - provider "openai"  -> qualsiasi endpoint OpenAI-compatibile
                          (LM Studio, llama.cpp server, vLLM, o un'API cloud)

Default = Ollama locale. Se si sceglie un'API cloud i prompt ESCONO dal PC:
l'interfaccia lo avvisa. La scelta si salva in llm.json (config runtime),
con fallback ai valori di config.yaml.

API unica: llm.generate(prompt, fmt="json"|None, forte=False, options={...}).
Restituisce SEMPRE una stringa (il testo del modello).
"""
import json
import threading
from pathlib import Path

import requests
import yaml

# Coda: una sola generazione alla volta. Le chiamate concorrenti (es. CV + chat)
# saturavano la GPU con poca VRAM causando timeout. Con un lock si serializzano.
# ponytail: lock globale; se un giorno servisse parallelismo per-modello, si affina.
_GEN_LOCK = threading.Lock()

ROOT = Path(__file__).parent
CFG = yaml.safe_load((ROOT / "config.yaml").read_text(encoding="utf-8"))
LLMF = ROOT / "llm.json"

DEFAULT = {
    "provider": "ollama",
    "base": CFG.get("ollama_url", "http://127.0.0.1:11434"),
    "model": CFG.get("modello", "llama3.2:3b"),
    "model_forte": CFG.get("modello_forte", CFG.get("modello", "llama3.2:3b")),
    "key": "",
    "lang": "it",
}
_FIELDS = ("provider", "base", "model", "model_forte", "key", "lang")

# Lingua in cui l'AI risponde (l'interfaccia resta in italiano; cambiano i CONTENUTI
# generati: assistente, CV, riscritture, briefing, idee...). "Tutte le lingue" = il
# modello puo' rispondere in qualsiasi lingua; qui le principali, ordinate.
LANGS = [
    ("it", "Italiano"), ("en", "English"), ("es", "Espanol"), ("fr", "Francais"),
    ("de", "Deutsch"), ("pt", "Portugues"), ("nl", "Nederlands"), ("ru", "Russkij"),
    ("uk", "Ukrainska"), ("pl", "Polski"), ("ro", "Romana"), ("el", "Ellinika"),
    ("tr", "Turkce"), ("ar", "Arabic"), ("he", "Hebrew"), ("fa", "Farsi"),
    ("hi", "Hindi"), ("bn", "Bengali"), ("ur", "Urdu"), ("zh", "Chinese"),
    ("ja", "Japanese"), ("ko", "Korean"), ("vi", "Vietnamese"), ("th", "Thai"),
    ("id", "Indonesian"), ("ms", "Malay"), ("sv", "Svenska"), ("no", "Norsk"),
    ("da", "Dansk"), ("fi", "Suomi"), ("cs", "Cestina"), ("sk", "Slovencina"),
    ("hu", "Magyar"), ("bg", "Balgarski"), ("sr", "Srpski"), ("hr", "Hrvatski"),
    ("sl", "Slovenscina"), ("et", "Eesti"), ("lv", "Latviesu"), ("lt", "Lietuviu"),
    ("sw", "Kiswahili"), ("af", "Afrikaans"), ("ca", "Catala"), ("eu", "Euskara"),
    ("gl", "Galego"), ("is", "Islenska"), ("ga", "Gaeilge"), ("cy", "Cymraeg"),
    ("fil", "Filipino"), ("ta", "Tamil"),
]
_LANG_NAME = {c: n for c, n in LANGS}
# Locale Google News (hl,gl,ceid) per la sezione notizie, per lingua nota.
NEWS_LOCALE = {
    "it": ("it", "IT", "IT:it"), "en": ("en-US", "US", "US:en"), "es": ("es", "ES", "ES:es"),
    "fr": ("fr", "FR", "FR:fr"), "de": ("de", "DE", "DE:de"), "pt": ("pt-BR", "BR", "BR:pt-419"),
    "nl": ("nl", "NL", "NL:nl"), "ru": ("ru", "RU", "RU:ru"), "pl": ("pl", "PL", "PL:pl"),
    "tr": ("tr", "TR", "TR:tr"), "ar": ("ar", "EG", "EG:ar"), "hi": ("hi", "IN", "IN:hi"),
    "zh": ("zh-CN", "CN", "CN:zh-Hans"), "ja": ("ja", "JP", "JP:ja"), "ko": ("ko", "KR", "KR:ko"),
    "vi": ("vi", "VN", "VN:vi"), "id": ("id", "ID", "ID:id"), "sv": ("sv", "SE", "SE:sv"),
    "el": ("el", "GR", "GR:el"), "ro": ("ro", "RO", "RO:ro"), "uk": ("uk", "UA", "UA:uk"),
    "cs": ("cs", "CZ", "CZ:cs"), "hu": ("hu", "HU", "HU:hu"), "th": ("th", "TH", "TH:th"),
}


def lang_name(code=None):
    return _LANG_NAME.get(code or get_cfg().get("lang", "it"), "Italiano")


def news_locale():
    return NEWS_LOCALE.get(get_cfg().get("lang", "it"), NEWS_LOCALE["it"])


def get_cfg():
    d = dict(DEFAULT)
    if LLMF.exists():
        try:
            saved = json.loads(LLMF.read_text(encoding="utf-8"))
            d.update({k: v for k, v in saved.items() if k in _FIELDS and isinstance(v, str) and v != ""})
        except Exception:
            pass
    return d


def set_cfg(d):
    cur = get_cfg()
    for k in _FIELDS:
        if k in d and isinstance(d[k], str):
            cur[k] = d[k].strip()
    if cur["provider"] not in ("ollama", "openai"):
        cur["provider"] = "ollama"
    LLMF.write_text(json.dumps(cur, ensure_ascii=False), encoding="utf-8")
    return cur


def is_local():
    c = get_cfg()
    if c["provider"] != "ollama":
        # un endpoint OpenAI-compatibile su localhost e comunque locale
        return "127.0.0.1" in c["base"] or "localhost" in c["base"]
    return True


def generate(prompt, fmt=None, forte=False, options=None, timeout=180):
    c = get_cfg()
    model = (c.get("model_forte") or c["model"]) if forte else c["model"]
    base = c["base"].rstrip("/")
    lang = c.get("lang", "it")
    if lang and lang != "it":                      # forza la lingua di risposta scelta
        name = _LANG_NAME.get(lang, lang)
        # in fondo e con override: batte eventuali "rispondi in italiano" nei prompt
        prompt = prompt + (f"\n\n=== LANGUAGE OVERRIDE ===\nIgnore ANY earlier instruction about the "
                           f"output language. Reply ONLY in {name} ({lang}). Translate all text values "
                           "into that language; keep JSON keys unchanged.")
    if c["provider"] == "openai":
        headers = {"Content-Type": "application/json"}
        if c.get("key"):
            headers["Authorization"] = "Bearer " + c["key"]
        body = {"model": model, "messages": [{"role": "user", "content": prompt}], "stream": False}
        if fmt == "json":
            body["response_format"] = {"type": "json_object"}
        if options and "temperature" in options:
            body["temperature"] = options["temperature"]
        with _GEN_LOCK:
            r = requests.post(base + "/v1/chat/completions", json=body, headers=headers, timeout=timeout)
        r.raise_for_status()
        return r.json()["choices"][0]["message"]["content"]
    # Ollama nativo
    body = {"model": model, "prompt": prompt, "stream": False}
    if fmt == "json":
        body["format"] = "json"
    if options:
        body["options"] = options
    with _GEN_LOCK:
        r = requests.post(base + "/api/generate", json=body, timeout=timeout)
    r.raise_for_status()
    return r.json()["response"]


def _lang_suffix(c):
    lang = c.get("lang", "it")
    if lang and lang != "it":
        name = _LANG_NAME.get(lang, lang)
        return (f"\n\n=== LANGUAGE OVERRIDE ===\nIgnore ANY earlier instruction about the output "
                f"language. Reply ONLY in {name} ({lang}).")
    return ""


def stream(prompt, forte=False, timeout=240):
    """Genera in streaming: restituisce (yield) i pezzi di testo man mano.
    Serializzata dallo stesso lock (una generazione alla volta)."""
    c = get_cfg()
    model = (c.get("model_forte") or c["model"]) if forte else c["model"]
    base = c["base"].rstrip("/")
    prompt = prompt + _lang_suffix(c)
    with _GEN_LOCK:
        if c["provider"] == "openai":
            headers = {"Content-Type": "application/json"}
            if c.get("key"):
                headers["Authorization"] = "Bearer " + c["key"]
            body = {"model": model, "messages": [{"role": "user", "content": prompt}], "stream": True}
            r = requests.post(base + "/v1/chat/completions", json=body, headers=headers, stream=True, timeout=timeout)
            r.raise_for_status()
            for line in r.iter_lines():
                if not line:
                    continue
                s = line.decode("utf-8", "ignore")
                if s.startswith("data: "):
                    s = s[6:]
                if s.strip() == "[DONE]":
                    break
                try:
                    ch = json.loads(s)["choices"][0].get("delta", {}).get("content", "")
                except Exception:
                    continue
                if ch:
                    yield ch
        else:
            body = {"model": model, "prompt": prompt, "stream": True}
            r = requests.post(base + "/api/generate", json=body, stream=True, timeout=timeout)
            r.raise_for_status()
            for line in r.iter_lines():
                if not line:
                    continue
                try:
                    j = json.loads(line)
                except Exception:
                    continue
                if j.get("response"):
                    yield j["response"]
                if j.get("done"):
                    break


def status():
    """True se il backend risponde (per la spia stato nell'interfaccia)."""
    c = get_cfg()
    base = c["base"].rstrip("/")
    try:
        if c["provider"] == "openai":
            h = {"Authorization": "Bearer " + c["key"]} if c.get("key") else {}
            requests.get(base + "/v1/models", headers=h, timeout=4).raise_for_status()
        else:
            requests.get(base + "/api/tags", timeout=4).raise_for_status()
        return True
    except Exception:
        return False


def list_models():
    """Elenco modelli disponibili sul backend (per il menu a tendina)."""
    c = get_cfg()
    base = c["base"].rstrip("/")
    try:
        if c["provider"] == "openai":
            h = {"Authorization": "Bearer " + c["key"]} if c.get("key") else {}
            data = requests.get(base + "/v1/models", headers=h, timeout=5).json()
            return [m["id"] for m in data.get("data", [])]
        data = requests.get(base + "/api/tags", timeout=5).json()
        return [m["name"] for m in data.get("models", [])]
    except Exception:
        return []


def _demo():
    d = get_cfg()
    assert d["provider"] in ("ollama", "openai") and d["base"] and d["model"]
    # set_cfg valida il provider
    import tempfile
    assert set_cfg({"provider": "xyz"})["provider"] == "ollama"
    print("ok: llm config coerente ->", get_cfg())


if __name__ == "__main__":
    import sys
    if "--demo" in sys.argv:
        _demo()
    elif "--status" in sys.argv:
        print("backend raggiungibile:", status(), "| modelli:", list_models()[:5])
    else:
        print(json.dumps(get_cfg(), ensure_ascii=False, indent=2))
