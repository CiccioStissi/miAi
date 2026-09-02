"""Traduzione OFFLINE e veloce con argos-translate (rete neurale che gira sul PC).

Sorgente = italiano. Per le lingue diverse dall'inglese si passa dal pivot inglese
(it -> en -> xx). I pacchetti lingua si SCARICANO una volta sola (unica operazione di
rete); dopo e' tutto locale, nessun dato esce dal PC. Cache per stringa su disco
(mt_cache/<lang>.json) -> dopo la prima volta il lookup e' istantaneo.

API: ensure_lang(code) scarica/prepara; is_ready(code); translate_batch(texts, code).
"""
import json
import threading
from pathlib import Path

ROOT = Path(__file__).parent
CACHE = ROOT / "mt_cache"
_LOCK = threading.Lock()
_INDEX_DONE = False


def _argos():
    # argostranslate.sbd fa `import stanza` (che tira dietro torch, ~1.5GB e qui rotto).
    # Non ci serve: usiamo il segmentatore pure-python minisbd. Stub di stanza cosi
    # l'import passa senza torch. Se stanza vero fosse installato, lo usa e basta.
    import sys
    import types
    if "stanza" not in sys.modules:
        try:
            import stanza  # noqa: F401
        except ImportError:
            stub = types.ModuleType("stanza")
            stub.Pipeline = None
            stub.download = lambda *a, **k: None
            sys.modules["stanza"] = stub
    import argostranslate.package
    import argostranslate.settings as _st
    # forza la segmentazione frasi su minisbd (niente spacy/stanza)
    try:
        _st.chunk_type = _st.ChunkType.MINISBD
    except Exception:
        pass
    import argostranslate.translate
    return argostranslate


def _installed_codes():
    return {l.code for l in _argos().translate.get_installed_languages()}


def _install_pair(frm, to):
    a = _argos()
    global _INDEX_DONE
    if not _INDEX_DONE:
        a.package.update_package_index()
        _INDEX_DONE = True
    p = next((x for x in a.package.get_available_packages()
              if x.from_code == frm and x.to_code == to), None)
    if not p:
        return False
    a.package.install_from_path(p.download())
    return True


def ensure_lang(code):
    """Assicura i pacchetti per tradurre it->code (scarica se serve, UNA volta)."""
    code = (code or "it").strip()
    if code == "it":
        return {"ok": True, "ready": True}
    with _LOCK:
        try:
            if "it" not in _installed_codes() or "en" not in _installed_codes():
                _install_pair("it", "en")
            if code != "en" and code not in _installed_codes():
                if not _install_pair("en", code) and not _install_pair("it", code):
                    return {"ok": False, "err": f"nessun pacchetto disponibile per '{code}'"}
            return {"ok": True, "ready": is_ready(code)}
        except Exception as e:
            return {"ok": False, "err": str(e)[:200]}


def is_ready(code):
    code = (code or "it").strip()
    if code == "it":
        return True
    try:
        inst = _installed_codes()
        return "it" in inst and code in inst
    except Exception:
        return False


def _pair(langs, a, b):
    s = next((l for l in langs if l.code == a), None)
    d = next((l for l in langs if l.code == b), None)
    return s.get_translation(d) if s and d else None


def _translator(code):
    """Ritorna una funzione text->tradotto. argos NON auto-pivota: chainiamo
    esplicitamente it->en->code (per 'en' basta it->en)."""
    langs = _argos().translate.get_installed_languages()
    it_en = _pair(langs, "it", "en")
    if it_en is None:
        return None
    if code == "en":
        return lambda t: it_en.translate(t)
    en_x = _pair(langs, "en", code)
    if en_x is None:
        return None
    return lambda t: en_x.translate(it_en.translate(t))


def _cache_file(code):
    return CACHE / (code + ".json")


def _load(code):
    try:
        return json.loads(_cache_file(code).read_text(encoding="utf-8"))
    except Exception:
        return {}


def translate_batch(texts, code):
    """Traduce una lista di stringhe in 'code'. Ritorna {originale: tradotto}.
    Cache-first: traduce solo le nuove, salva su disco."""
    code = (code or "it").strip()
    texts = [t for t in texts if isinstance(t, str)]
    if code == "it":
        return {t: t for t in texts}
    cache = _load(code)
    miss = [t for t in dict.fromkeys(texts) if t.strip() and t not in cache]
    if miss:
        with _LOCK:
            tr = _translator(code)
            if tr is None:
                return {t: cache.get(t, t) for t in texts}
            for t in miss:
                try:
                    cache[t] = tr(t)
                except Exception:
                    cache[t] = t
            CACHE.mkdir(exist_ok=True)
            _cache_file(code).write_text(json.dumps(cache, ensure_ascii=False), encoding="utf-8")
    return {t: cache.get(t, t) for t in texts}


if __name__ == "__main__":
    import sys
    code = sys.argv[1] if len(sys.argv) > 1 else "es"
    print("ensure:", ensure_lang(code))
    print("ready:", is_ready(code))
    demo = ["Idee", "Progetti", "Aggiorna", "Scegli i tuoi interessi", "Impostazioni", "Salva"]
    for k, v in translate_batch(demo, code).items():
        print(f"  {k!r:30} -> {v!r}")
