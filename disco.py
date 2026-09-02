"""Sezione Disco - analisi spazio e candidati alla pulizia.

Una sola passata os.walk sulle root configurate (veloce). Raccoglie insieme:
  - cartelle di primo livello per dimensione
  - file "freddi": grossi e non modificati da molto (candidati sicuri)
  - cache note (temp/pip/npm/browser): spazio liberabile senza perdere dati
  - spazio disco libero/totale
Non cancella NULLA: produce solo suggerimenti + comando da lanciare a mano.

Metrica "freddo": usa mtime (ultima modifica). Windows spesso disabilita
l'aggiornamento dell'atime (NtfsDisableLastAccessUpdate), quindi l'ultimo
accesso e' inaffidabile: mtime e' il segnale robusto per "roba dimenticata".

Uso CLI: python disco.py
"""
import hashlib
import json
import os
import shutil
import time
from pathlib import Path
import yaml

ROOT = Path(__file__).parent
CACHE = ROOT / "disco.json"
CFG = yaml.safe_load((ROOT / "config.yaml").read_text(encoding="utf-8"))

HOME = Path.home()
BIG_MB = int(CFG.get("disco_big_mb", 200))          # file "grosso" da >= X MB
COLD_DAYS = int(CFG.get("disco_cold_days", 180))    # "freddo" se piu vecchio
DUP_MIN = int(CFG.get("disco_dup_min_mb", 50)) * 1024 * 1024  # duplicati solo se >= X
ROOTS = [Path(os.path.expandvars(os.path.expanduser(p)))
         for p in CFG.get("disco_roots", [str(HOME)])]

# Cache/temp note: svuotabili senza perdere dati personali.
KNOWN = {
    "Temp utente": os.environ.get("TEMP", str(HOME / "AppData/Local/Temp")),
    "Windows Temp": r"C:\Windows\Temp",
    "pip cache": str(HOME / "AppData/Local/pip/cache"),
    "npm cache": str(HOME / "AppData/Local/npm-cache"),
    "yarn cache": str(HOME / "AppData/Local/Yarn/Cache"),
    "Chrome cache": str(HOME / "AppData/Local/Google/Chrome/User Data/Default/Cache"),
    "Edge cache": str(HOME / "AppData/Local/Microsoft/Edge/User Data/Default/Cache"),
    "Conda pkgs": str(HOME / "AppData/Local/conda/conda/pkgs"),
    "HuggingFace hub": str(HOME / ".cache/huggingface"),
    "Docker (WSL)": str(HOME / "AppData/Local/Docker/wsl"),
}
# Non scendere qui dentro nella scansione dir (rumore, non spazio "tuo")
SKIP = {"Temp", "Cache", "cache", "GPUCache", "Code Cache", "node_modules"}
# I "duplicati" dentro queste directory NON sono spazio sicuro: sono copie
# gestite da tool (venv, cache, build), spesso symlink/hardlink, e cancellarle
# rompe l'ambiente senza liberare nulla. Suggeriamo solo duplicati di file TUOI.
MANAGED = ("site-packages", "\\.cache\\", "\\.gradle\\", "\\.dart_tool\\",
           "\\.conda\\", "\\.venv\\", "\\build\\", "\\.git\\", "huggingface",
           "\\versions\\", "\\node_modules\\", "\\.ollama\\", "\\.vagrant.d\\",
           "\\.vscode\\", "\\extensions\\", "\\.bun\\", "\\plugins\\",
           "\\claude-mem\\", "\\.claude\\")


def _managed(path):
    p = path.lower()
    return any(m in p for m in MANAGED)


def _dir_size(path):
    total = 0
    for dp, dn, fn in os.walk(path, onerror=lambda e: None):
        for f in fn:
            try:
                total += os.stat(os.path.join(dp, f)).st_size
            except OSError:
                pass
    return total


def _sig(path, size):
    """Firma veloce per confermare i duplicati: dimensione + hash dei primi 256KB."""
    try:
        with open(path, "rb") as fh:
            head = fh.read(262144)
    except OSError:
        return None
    return f"{size}:{hashlib.blake2b(head, digest_size=16).hexdigest()}"


def scan():
    now = time.time()
    cold_cut = now - COLD_DAYS * 86400
    big_bytes = BIG_MB * 1024 * 1024
    top = {}       # "root/sub" -> bytes
    cold = []      # file grossi e vecchi
    ext = {}       # ".mp4" -> bytes
    by_size = {}   # size -> [path]  (solo candidati grossi, per i duplicati)

    for root in ROOTS:
        if not root.exists():
            continue
        base = str(root)
        for dp, dn, fn in os.walk(base, onerror=lambda e: None):
            dn[:] = [d for d in dn if d not in SKIP]  # potatura in-place
            rel = os.path.relpath(dp, base)
            key = rel.split(os.sep)[0] if rel != "." else "(root)"
            bucket = f"{root.name}/{key}"
            for f in fn:
                fp = os.path.join(dp, f)
                try:
                    st = os.stat(fp)
                except OSError:
                    continue
                sz = st.st_size
                top[bucket] = top.get(bucket, 0) + sz
                e = (os.path.splitext(f)[1] or "(senza)").lower()
                ext[e] = ext.get(e, 0) + sz
                if sz >= big_bytes and st.st_mtime < cold_cut:
                    cold.append({"path": fp, "gb": round(sz / 1e9, 2),
                                 "eta": int((now - st.st_mtime) / 86400)})
                # duplicati: solo file TUOI (no symlink, no cartelle gestite da tool)
                if sz >= DUP_MIN and not os.path.islink(fp) and not _managed(fp):
                    by_size.setdefault(sz, []).append(fp)

    top_list = [{"dir": k, "gb": round(v / 1e9, 2)}
                for k, v in sorted(top.items(), key=lambda kv: -kv[1]) if v > 1e8][:15]
    cold.sort(key=lambda c: -c["gb"])

    per_tipo = [{"ext": k, "gb": round(v / 1e9, 2)}
                for k, v in sorted(ext.items(), key=lambda kv: -kv[1]) if v > 1e8][:12]

    # duplicati: conferma con firma solo i file che condividono la stessa size
    groups = {}
    for sz, paths in by_size.items():
        if len(paths) < 2:
            continue
        for p in paths:
            s = _sig(p, sz)
            if s:
                groups.setdefault(s, []).append(p)
    dupes = []
    for s, paths in groups.items():
        if len(paths) < 2:
            continue
        sz = int(s.split(":")[0])
        dupes.append({"gb": round(sz / 1e9, 2), "n": len(paths),
                      "spreco_gb": round(sz * (len(paths) - 1) / 1e9, 2),
                      "paths": paths[:5]})
    dupes.sort(key=lambda d: -d["spreco_gb"])

    caches = []
    for name, p in KNOWN.items():
        if os.path.isdir(p):
            b = _dir_size(p)
            if b > 5e7:  # >50MB vale la pena mostrarla
                caches.append({"nome": name, "path": p, "gb": round(b / 1e9, 2)})
    caches.sort(key=lambda c: -c["gb"])

    du = shutil.disk_usage(str(ROOTS[0].anchor or "C:\\"))
    reclaim = round(sum(c["gb"] for c in caches) + sum(c["gb"] for c in cold[:20])
                    + sum(d["spreco_gb"] for d in dupes), 1)
    return {
        "disco": {"tot_gb": round(du.total / 1e9), "free_gb": round(du.free / 1e9),
                  "free_pct": round(du.free / du.total * 100, 1)},
        "top": top_list,
        "freddi": cold[:20],
        "cache": caches,
        "per_tipo": per_tipo,
        "duplicati": dupes[:15],
        "liberabile_gb": reclaim,
        "soglie": {"big_mb": BIG_MB, "cold_days": COLD_DAYS},
        "generato": time.strftime("%Y-%m-%d %H:%M"),
    }


def get(refresh=False, max_age_h=None):
    """Riusa la cache se recente (max_age_h) anche con refresh: evita di ri-walkare
    tutto il disco a ogni giro se e' gia stato fatto da poco (efficienza)."""
    if CACHE.exists():
        cached = json.loads(CACHE.read_text(encoding="utf-8"))
        fresh = (time.time() - CACHE.stat().st_mtime) / 3600
        if not refresh or (max_age_h is not None and fresh < max_age_h):
            return cached
    d = scan()
    CACHE.write_text(json.dumps(d, ensure_ascii=False), encoding="utf-8")
    return d


def _demo():
    d = scan()
    assert d["disco"]["tot_gb"] > 0 and 0 <= d["disco"]["free_pct"] <= 100
    assert all(c["gb"] >= 0 for c in d["cache"])
    assert all(f["eta"] >= COLD_DAYS for f in d["freddi"])  # freddi = davvero vecchi
    print("ok: disco scan coerente")


if __name__ == "__main__":
    import sys
    if "--demo" in sys.argv:
        _demo()
    else:
        d = get(refresh=True)
        x = d["disco"]
        print(f"Disco: {x['free_gb']}/{x['tot_gb']} GB liberi ({x['free_pct']}%)  "
              f"| liberabile ~{d['liberabile_gb']} GB\n")
        print("== Cartelle piu pesanti ==")
        for t in d["top"]:
            print(f"  {t['gb']:6.2f} GB  {t['dir']}")
        print("\n== Cache svuotabili ==")
        for c in d["cache"]:
            print(f"  {c['gb']:6.2f} GB  {c['nome']}")
        print(f"\n== File grossi e vecchi (>{d['soglie']['big_mb']}MB, >{d['soglie']['cold_days']}gg) ==")
        for f in d["freddi"][:12]:
            print(f"  {f['gb']:6.2f} GB  {f['eta']}gg  {f['path']}")
