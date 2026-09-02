"""Mini-server locale: serve la dashboard e la telemetria hardware LIVE.

Perche esiste: un file HTML aperto con file:// non puo leggere l'hardware ne
fare fetch. Servendo la dashboard da qui (stessa origine), la pagina puo
chiedere /telemetry ogni 2s e mostrare CPU/GPU/RAM/rete in tempo reale.

Avvio:  python server.py         -> http://localhost:8770
        python server.py --open  -> apre anche il browser
"""
import json, os, sqlite3, subprocess, shutil, sys, threading, time, webbrowser
import base64, hashlib, hmac, secrets
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
import psutil
import requests
import yaml
import crypto
import llm
import usage

ROOT = Path(__file__).parent
DASH = ROOT / "dashboard.html"
CFG = yaml.safe_load((ROOT / "config.yaml").read_text(encoding="utf-8"))
PORT = 8770
ALLOWED_HOSTS = {"127.0.0.1", "localhost"}  # solo accesso locale (anti CSRF/DNS-rebinding)
STORE = ROOT / "store.json"  # dati personali (preferiti, liste, config) - piccolo, durevole

# --- Blocco con PIN/password (opzionale) ---
PINF = ROOT / "pin.json"          # {salt, hash} - solo hash salato, mai il PIN in chiaro
_SESS = set()                     # token di sessione validi (in memoria, si azzerano al riavvio)
# path raggiungibili anche a schermata bloccata (la shell mostra il lock, niente dati)
_PUBLIC = {"/app", "/app.html", "/", "/index.html", "/dashboard.html", "/auth-status",
           "/unlock", "/sw.js", "/manifest.webmanifest", "/icon.svg"}


def pin_is_set():
    return PINF.exists()


def pin_set(pin):
    global _KEY
    pin = str(pin or "")
    obj = store_get()                       # legge con la chiave attuale (se cifrato+sbloccato)
    if pin == "":                           # rimuovi PIN: riporta lo store in chiaro
        if PINF.exists():
            PINF.unlink()
        _KEY = None
        store_set(obj)
        return {"ok": True, "locked": False}
    if len(pin) < 4:
        return {"ok": False, "err": "il PIN deve avere almeno 4 caratteri"}
    salt = secrets.token_hex(16)
    h = hashlib.sha256((salt + pin).encode()).hexdigest()
    PINF.write_text(json.dumps({"salt": salt, "hash": h}), encoding="utf-8")
    _set_key_from_pin(pin)                   # nuova chiave dal nuovo PIN
    store_set(obj)                           # ri-cifra lo store con la nuova chiave
    return {"ok": True, "locked": True}


def pin_check(pin):
    if not PINF.exists():
        return True
    try:
        d = json.loads(PINF.read_text(encoding="utf-8"))
        h = hashlib.sha256((d["salt"] + str(pin or "")).encode()).hexdigest()
        return hmac.compare_digest(h, d["hash"])
    except Exception:
        return False


def _cookie_token(handler):
    raw = handler.headers.get("Cookie", "") or ""
    for part in raw.split(";"):
        k, _, v = part.strip().partition("=")
        if k == "miai_sess":
            return v
    return ""


_KEY = None  # chiave di cifratura (Fernet) derivata dal PIN, in memoria dopo lo sblocco


def _derive_key(pin, salt_hex):
    """Chiave a 256 bit dal PIN via scrypt (memory-hard) + salt del PIN."""
    import base64
    dk = hashlib.scrypt(str(pin).encode(), salt=bytes.fromhex(salt_hex), n=16384, r=8, p=1, dklen=32)
    from cryptography.fernet import Fernet
    return Fernet(base64.urlsafe_b64encode(dk))


def _set_key_from_pin(pin):
    global _KEY
    try:
        d = json.loads(PINF.read_text(encoding="utf-8"))
        _KEY = _derive_key(pin, d["salt"])
    except Exception:
        _KEY = None


def _clear_key():
    global _KEY
    _KEY = None


def store_get():
    """Legge lo store; se cifrato (PIN attivo) lo decifra con la chiave in memoria."""
    if not STORE.exists():
        return {}
    raw = STORE.read_bytes()
    try:
        return json.loads(raw)                      # in chiaro (nessun PIN)
    except Exception:
        pass
    if _KEY is not None:                             # cifrato: decifra
        try:
            return json.loads(_KEY.decrypt(raw))
        except Exception:
            return {}
    return {}                                        # cifrato ma non sbloccato


def store_set(obj):
    if not isinstance(obj, dict):
        return {"ok": False, "err": "formato non valido"}
    txt = json.dumps(obj, ensure_ascii=False)
    if len(txt) > 2_000_000:                         # tetto: i dati personali sono piccoli
        return {"ok": False, "err": "dati troppo grandi"}
    if pin_is_set() and _KEY is not None:            # a riposo cifrato se c'e un PIN
        STORE.write_bytes(_KEY.encrypt(txt.encode()))
    else:
        STORE.write_text(txt, encoding="utf-8")
    return {"ok": True}

# --- PWA: manifest, service worker, icona (app installabile e offline) ---
ICON_SVG = ('<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 512 512">'
            '<defs><linearGradient id="g" x1="0" y1="0" x2="1" y2="1">'
            '<stop offset="0" stop-color="#6d6cff"/><stop offset="1" stop-color="#b0a5ff"/></linearGradient></defs>'
            '<rect width="512" height="512" rx="112" fill="#0a0a0d"/>'
            '<rect x="64" y="64" width="384" height="384" rx="96" fill="url(#g)"/>'
            '<g fill="#0a0a0d"><rect x="150" y="150" width="90" height="90" rx="24"/>'
            '<rect x="272" y="150" width="90" height="90" rx="24"/>'
            '<rect x="150" y="272" width="90" height="90" rx="24"/>'
            '<rect x="272" y="272" width="90" height="90" rx="24"/></g></svg>')
MANIFEST = json.dumps({
    "name": "miAi", "short_name": "miAi", "start_url": "/app", "scope": "/",
    "display": "standalone", "background_color": "#0a0a0d", "theme_color": "#0a0a0d",
    "description": "miAi - assistente personale locale",
    "icons": [{"src": "/icon.svg", "sizes": "any", "type": "image/svg+xml", "purpose": "any maskable"}],
})
SW_JS = """const C='miai-v1';
self.addEventListener('install',e=>{e.waitUntil(caches.open(C).then(c=>c.addAll(['/app','/manifest.webmanifest','/icon.svg']).catch(()=>{})).then(()=>self.skipWaiting()));});
self.addEventListener('activate',e=>{e.waitUntil(caches.keys().then(ks=>Promise.all(ks.filter(k=>k!==C).map(k=>caches.delete(k)))).then(()=>self.clients.claim()));});
self.addEventListener('fetch',e=>{const u=new URL(e.request.url);
 if(e.request.mode==='navigate'||u.pathname==='/app'){
  e.respondWith(fetch(e.request).then(r=>{const cp=r.clone();caches.open(C).then(c=>c.put('/app',cp));return r;}).catch(()=>caches.match('/app')));
 }});"""


VBS_LAUNCHER = (
    "' Launcher miAi - avvia il server locale (nascosto) e apre miAi nel browser.\r\n"
    "Set sh = CreateObject(\"WScript.Shell\")\r\n"
    "Set fso = CreateObject(\"Scripting.FileSystemObject\")\r\n"
    "root = fso.GetParentFolderName(WScript.ScriptFullName)\r\n"
    "sh.CurrentDirectory = root\r\n"
    "' avvia Ollama (serve alle funzioni AI); se gia attivo esce da solo, innocuo\r\n"
    "sh.Run \"cmd /c ollama serve\", 0, False\r\n"
    "' avvia il server in finestra nascosta (0 = hidden, False = non aspettare)\r\n"
    "sh.Run \"cmd /c C:\\ProgramData\\miniconda3\\python.exe \"\"\" & root & \"\\server.py\"\"\", 0, False\r\n"
    "WScript.Sleep 1800\r\n"
    "sh.Run \"http://127.0.0.1:8770/app\", 1, False\r\n"
)


def make_desktop_shortcut():
    """Crea un launcher .vbs + un collegamento 'miAi' sul Desktop dell'utente.
    Il collegamento avvia il server (se serve) e apre miAi. Nessuna installazione."""
    try:
        vbs = ROOT / "avvia_miai.vbs"
        vbs.write_text(VBS_LAUNCHER, encoding="utf-8")
        path, err = _make_lnk("miAi.lnk", vbs)
        return {"ok": False, "err": err} if err else {"ok": True, "path": path}
    except Exception as e:
        return {"ok": False, "err": str(e)[:200]}


def _make_lnk(name, vbs):
    """Crea/aggiorna un .lnk sul Desktop che lancia il vbs indicato con l'icona miAi."""
    ico = ROOT / "miai.ico"
    ps = ("$W=New-Object -ComObject WScript.Shell;"
          "$d=[Environment]::GetFolderPath('Desktop');"
          f"$lnk=Join-Path $d '{name}';"
          "$s=$W.CreateShortcut($lnk);"
          "$s.TargetPath='wscript.exe';"
          f"$s.Arguments='\"{vbs}\"';"
          f"$s.WorkingDirectory='{ROOT}';"
          + (f"$s.IconLocation='{ico}';" if ico.exists() else "")
          + "$s.Description='Apri miAi';$s.Save();Write-Output $lnk")
    r = subprocess.run(["powershell", "-NoProfile", "-Command", ps], capture_output=True, text=True)
    if r.returncode != 0:
        return None, (r.stderr or "errore").strip()[:200]
    return r.stdout.strip(), None


def _find_installed_pwa():
    """Cerca il collegamento che i browser creano per la PWA miAi installata.
    Ritorna (browser_exe, args) oppure (None, None)."""
    ps = ("$W=New-Object -ComObject WScript.Shell;"
          "$dirs=@([Environment]::GetFolderPath('Programs'),[Environment]::GetFolderPath('CommonPrograms'))|?{Test-Path $_};"
          "$hit=$null;"
          "Get-ChildItem -Path $dirs -Recurse -Filter *.lnk -ErrorAction SilentlyContinue|%{"
          " try{$s=$W.CreateShortcut($_.FullName);"
          "  if(-not $hit -and $s.Arguments -match 'app-id' -and $s.TargetPath -match 'msedge|chrome' -and $_.BaseName -like '*miAi*'){"
          "   $hit=$s.TargetPath+'||'+$s.Arguments}}catch{}};"
          "if($hit){Write-Output $hit}")
    r = subprocess.run(["powershell", "-NoProfile", "-Command", ps], capture_output=True, text=True)
    out = (r.stdout or "").strip()
    if "||" in out:
        b, a = out.split("||", 1)
        return b.strip(), a.strip()
    return None, None


def make_app_shortcut():
    """Collegamento desktop che avvia il server e apre la PWA miAi INSTALLATA
    (finestra propria), non una scheda del browser."""
    browser, args = _find_installed_pwa()
    if not browser:
        return {"ok": False, "err": "App miAi non ancora installata. Prima premi 'Installa miAi', poi riprova."}
    run_lit = '"""' + browser + '"" ' + args + '"'   # in VBS un " dentro stringa si scrive ""
    vbs = ROOT / "avvia_miai_app.vbs"
    vbs.write_text(
        "' Launcher miAi (app) - avvia il server e apre la PWA installata.\r\n"
        "Set sh = CreateObject(\"WScript.Shell\")\r\n"
        "Set fso = CreateObject(\"Scripting.FileSystemObject\")\r\n"
        "root = fso.GetParentFolderName(WScript.ScriptFullName)\r\n"
        "sh.CurrentDirectory = root\r\n"
        "sh.Run \"cmd /c ollama serve\", 0, False\r\n"
        "sh.Run \"cmd /c C:\\ProgramData\\miniconda3\\python.exe \"\"\" & root & \"\\server.py\"\"\", 0, False\r\n"
        "WScript.Sleep 1800\r\n"
        "sh.Run " + run_lit + ", 1, False\r\n", encoding="utf-8")
    path, err = _make_lnk("miAi.lnk", vbs)
    if err:
        return {"ok": False, "err": err}
    return {"ok": True, "path": path, "browser": os.path.basename(browser)}


def _startup_lnk():
    return Path(os.environ.get("APPDATA", "")) / "Microsoft" / "Windows" / "Start Menu" / "Programs" / "Startup" / "miAi.lnk"


def autostart_status():
    return {"on": _startup_lnk().exists()}


def autostart_set(on):
    """Attiva/disattiva l'avvio automatico di miAi al login (shortcut in shell:startup)."""
    lnk = _startup_lnk()
    try:
        if on:
            vbs = ROOT / "avvia_miai.vbs"
            vbs.write_text(VBS_LAUNCHER, encoding="utf-8")
            ico = ROOT / "miai.ico"
            ps = ("$W=New-Object -ComObject WScript.Shell;"
                  f"$s=$W.CreateShortcut('{lnk}');"
                  "$s.TargetPath='wscript.exe';"
                  f"$s.Arguments='\"{vbs}\"';"
                  f"$s.WorkingDirectory='{ROOT}';"
                  + (f"$s.IconLocation='{ico}';" if ico.exists() else "")
                  + "$s.Description='Avvia miAi al login';$s.Save()")
            r = subprocess.run(["powershell", "-NoProfile", "-Command", ps], capture_output=True, text=True)
            if r.returncode != 0:
                return {"ok": False, "err": (r.stderr or "errore").strip()[:200]}
            return {"ok": True, "on": True}
        if lnk.exists():
            lnk.unlink()
        return {"ok": True, "on": False}
    except Exception as e:
        return {"ok": False, "err": str(e)[:200]}


def server_restart():
    """Riavvia il processo del server (os.execv: stesso PID, socket chiuso su exec).
    Risponde prima, poi si riavvia dopo un attimo."""
    def _do():
        time.sleep(0.5)
        os.execv(sys.executable, [sys.executable, str(ROOT / "server.py")])
    threading.Thread(target=_do, daemon=True).start()
    return {"ok": True}


LOCK_HTML = """<!doctype html><html lang="it"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1"><title>miAi</title>
<style>*{box-sizing:border-box}body{margin:0;height:100vh;display:flex;align-items:center;justify-content:center;
background:#0a0a0d;color:#f2f2f6;font-family:system-ui,-apple-system,'Segoe UI',sans-serif}
.c{text-align:center;width:100%;max-width:340px;padding:20px}
.ic{width:64px;height:64px;border-radius:18px;background:#1c1c2e;color:#8a8cf7;display:flex;align-items:center;
justify-content:center;margin:0 auto 18px}.ic svg{width:30px;height:30px}
h1{font-size:22px;margin:0 0 4px}p{color:#9a9aa8;margin:0 0 18px}
input{width:100%;max-width:220px;padding:12px;border:1px solid #2e2e3c;border-radius:10px;background:#191920;
color:#f2f2f6;font-size:20px;text-align:center;letter-spacing:4px;outline:none}
input:focus{border-color:#8a8cf7}
button{margin-top:16px;padding:10px 20px;border:none;border-radius:10px;background:#8a8cf7;color:#fff;
font-size:15px;font-weight:600;cursor:pointer}#e{color:#f4756b;font-size:13px;margin-top:12px;min-height:16px}</style></head>
<body><div class="c"><div class="ic"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"
stroke-linecap="round"><rect x="4" y="11" width="16" height="10" rx="2"/><path d="M8 11V7a4 4 0 0 1 8 0v4"/></svg></div>
<h1>miAi e bloccato</h1><p>Inserisci il PIN per accedere.</p>
<input id="p" type="password" inputmode="numeric" placeholder="PIN" autocomplete="off" autofocus>
<div id="e"></div><div><button onclick="u()">Sblocca</button></div></div>
<script>
var P=document.getElementById('p');P.addEventListener('keydown',function(e){if(e.key==='Enter')u();});
function u(){fetch('/unlock',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({pin:P.value})})
.then(function(r){return r.json();}).then(function(r){if(r.ok){location.reload();}else{document.getElementById('e').textContent='PIN errato. Riprova.';P.value='';P.focus();}})
.catch(function(){document.getElementById('e').textContent='Errore di rete.';});}
</script></body></html>"""


def _trend_ctx():
    """Trend reali compatti (repo top + temi di mercato) per ancorare i prodotti generati."""
    parts = []
    db = ROOT / "db.sqlite"
    if db.exists():
        try:
            con = sqlite3.connect(db)
            for f, d in con.execute("SELECT full_name,description FROM repos "
                                    "ORDER BY score DESC,stars DESC LIMIT 8").fetchall():
                parts.append(f"- {f}: {(d or '')[:80]}")
        except Exception:
            pass
    try:
        import mercato
        for t in (mercato.get() or [])[:5]:
            parts.append("- mercato: " + str(t.get("topic", "")))
    except Exception:
        pass
    return "\n".join(parts)


def _ctx():
    """Riassunto compatto dei dati raccolti oggi, come contesto per la chat."""
    parts = []
    db = ROOT / "db.sqlite"
    if db.exists():
        con = sqlite3.connect(db)
        rows = con.execute("SELECT full_name,score,reason FROM repos "
                           "ORDER BY first_seen DESC,score DESC LIMIT 15").fetchall()
        if rows:
            parts.append("REPO GITHUB (nome | score | perche):\n" +
                         "\n".join(f"- {f} | {s}/10 | {r}" for f, s, r in rows))
    for fn, label in [("cyber.json", "CYBER (CISA KEV)"), ("blockchain.json", "BLOCKCHAIN"),
                      ("ideas.json", "IDEE STARTUP"), ("crypto.json", "PREZZI CRYPTO")]:
        p = ROOT / fn
        if p.exists():
            parts.append(f"{label}:\n{p.read_text(encoding='utf-8')[:1200]}")
    m = ROOT / "machine.json"
    if m.exists():
        parts.append("PC UTENTE:\n" + m.read_text(encoding="utf-8")[:600])
    return "\n\n".join(parts)[:6000]


_L = " Mantieni la STESSA lingua del testo originale (non tradurre)."
_WRITE_MODES = {
    "correggi": "Correggi errori di grammatica, ortografia e punteggiatura, mantenendo senso e stile. Restituisci solo il testo corretto." + _L,
    "formale": "Riscrivi in tono formale e professionale, chiaro e cortese." + _L,
    "informale": "Riscrivi in tono informale e amichevole, naturale." + _L,
    "accorcia": "Riscrivi piu breve e diretto, mantenendo il significato." + _L,
    "allunga": "Espandi il testo aggiungendo dettagli utili, senza inventare fatti." + _L,
    "email": "Trasforma in una email ben strutturata (oggetto, saluto, corpo, chiusura)." + _L,
    "traduci_en": "Traduci in inglese, naturale e corretto.",
    "traduci_it": "Traduci in italiano, naturale e corretto.",
}


def rewrite(text, mode):
    istr = _WRITE_MODES.get(mode, _WRITE_MODES["correggi"])
    text = str(text)[:6000]
    prompt = ("Sei un assistente di scrittura. " + istr +
              " Rispondi SOLO col testo risultante, senza commenti, virgolette o spiegazioni.\n\nTESTO:\n" + text)
    try:
        return {"out": llm.generate(prompt, timeout=180).strip()}
    except Exception as e:
        return {"error": f"Modello: {e}"[:140]}


def ask_prompt(q):
    return ("Sei miAi, l'assistente personale locale dell'utente. Rispondi in italiano, "
            "conciso e concreto, USANDO SOLO i dati raccolti qui sotto. Se l'informazione "
            "non e' presente, dillo chiaramente.\n\n"
            f"=== DATI RACCOLTI OGGI ===\n{_ctx()}\n\n=== DOMANDA ===\n{q}")


def ask(q):
    prompt = ask_prompt(q)
    try:
        return llm.generate(prompt, timeout=180).strip() or "(nessuna risposta)"
    except Exception as e:
        return f"Errore modello: {e}"

MAPPE = ROOT / "mappe.json"


def _mappe_load():
    if MAPPE.exists():
        try:
            return json.loads(MAPPE.read_text(encoding="utf-8"))
        except Exception:
            pass
    return {}


def mappa(title, ctx, deep=False, regen=False):
    """Mappa concettuale: come trasformare questa risorsa in un business proprio.
    Cache su mappe.json per titolo (istantanea al riapri). deep=modello forte."""
    store = _mappe_load()
    key = f"{'D:' if deep else ''}{title}"
    if not regen and key in store:
        return {**store[key], "cached": True}
    prompt = (
        "Sei uno stratega di business. Crea una MAPPA CONCETTUALE sintetica e concreta "
        "che spieghi come usare la risorsa qui sotto per costruirci un BUSINESS PROPRIO. "
        "Nodo centrale = la risorsa. Genera 4-6 rami tematici (esempi: Problema che risolve, "
        "A chi venderlo, Come monetizzare, MVP minimo, Vantaggio competitivo, Rischi). "
        "Ogni ramo con 2-3 punti brevissimi e concreti, in italiano.\n\n"
        f"RISORSA: {title}\nCONTESTO: {ctx}\n\n"
        'Rispondi SOLO JSON: {"centro":"<nome breve>","rami":['
        '{"nome":"<tema>","punti":["<p1>","<p2>"]}]}')
    try:
        d = json.loads(llm.generate(prompt, fmt="json", forte=deep, timeout=300))
        if not d.get("rami"):
            return {"error": "mappa vuota"}
        out = {"centro": d.get("centro", title)[:60], "rami": d["rami"][:6], "deep": deep}
        store[key] = out
        MAPPE.write_text(json.dumps(store, ensure_ascii=False), encoding="utf-8")
        return out
    except Exception as e:
        return {"error": f"Ollama: {e}"[:120]}


def fondi(ideas):
    """Fonde 2+ idee in UNA nuova startup ibrida coerente (Ollama)."""
    ideas = [i for i in ideas if isinstance(i, dict)][:6]
    if len(ideas) < 2:
        return {"error": "seleziona almeno 2 idee"}
    blocchi = "\n".join(f"- {i.get('titolo','')}: {i.get('descrizione','')}" for i in ideas)
    fonti = [i.get("titolo", "") for i in ideas]
    prompt = (
        "Sei un imprenditore. FONDI le idee di startup qui sotto in UNA sola idea IBRIDA, "
        "coerente e piu forte, che sfrutta le sinergie tra loro (non un semplice elenco). "
        "Deve avere senso come singolo prodotto/azienda.\n\nIDEE DA FONDERE:\n" + blocchi + "\n\n"
        'Rispondi SOLO in JSON: {"titolo":"nome breve della startup fusa",'
        '"descrizione":"cosa fa in 1-2 frasi","problema":"quale problema risolve",'
        '"perche_ora":"perche e il momento","novelta":"alta|media|bassa",'
        '"tam":"dimensione mercato in 1 frase","fattibilita":"alta|media|bassa",'
        '"sinergia":"come le idee si rafforzano a vicenda","passi":["passo 1","passo 2","passo 3"]}')
    try:
        d = json.loads(llm.generate(prompt, fmt="json", timeout=240))
        if not d.get("titolo"):
            return {"error": "fusione vuota"}
        d["fonti"] = fonti
        d["passi"] = [str(x).strip() for x in (d.get("passi") or [])][:3]
        return d
    except Exception as e:
        return {"error": f"Ollama: {e}"[:140]}


def search_gh(q, n=15):
    """Ricerca GitHub live on-demand (senza token: rate limit ridotto ma ok per uso saltuario)."""
    try:
        r = requests.get("https://api.github.com/search/repositories",
                         headers={"Accept": "application/vnd.github+json"},
                         params={"q": q, "sort": "stars", "order": "desc", "per_page": n}, timeout=25)
        r.raise_for_status()
        return [{"full_name": it["full_name"], "url": it["html_url"],
                 "description": it.get("description") or "", "stars": it.get("stargazers_count", 0),
                 "language": it.get("language") or ""} for it in r.json().get("items", [])]
    except Exception as e:
        return {"error": str(e)}


def _allowed_paths():
    """Whitelist: SOLO i file gia segnalati dalla scan (freddi + duplicati).
    Impedisce di cancellare percorsi arbitrari via richiesta artefatta."""
    p = ROOT / "disco.json"
    if not p.exists():
        return set()
    d = json.loads(p.read_text(encoding="utf-8"))
    s = set()
    for f in d.get("freddi", []):
        s.add(os.path.normcase(os.path.abspath(f["path"])))
    for x in d.get("duplicati", []):
        for pp in x.get("paths", []):
            s.add(os.path.normcase(os.path.abspath(pp)))
    return s


def trash(path):
    """Sposta UN file nel Cestino (reversibile). Native VisualBasic, nessuna dipendenza."""
    if os.path.normcase(os.path.abspath(path)) not in _allowed_paths():
        return {"ok": False, "err": "percorso non consentito"}
    if not os.path.exists(path):
        return {"ok": True, "gone": True}          # gia sparito: obiettivo raggiunto, non e un errore
    if not os.path.isfile(path):
        return {"ok": False, "err": "non e un file (cartella)"}
    ps = ("Add-Type -AssemblyName Microsoft.VisualBasic;"
          "[Microsoft.VisualBasic.FileIO.FileSystem]::DeleteFile("
          f"'{path.replace(chr(39), chr(39) * 2)}','OnlyErrorDialogs','SendToRecycleBin')")
    r = subprocess.run(["powershell", "-NoProfile", "-Command", ps],
                       capture_output=True, text=True)
    if r.returncode != 0:
        return {"ok": False, "err": (r.stderr or "errore").strip()[:200]}
    du = shutil.disk_usage("C:\\")
    return {"ok": True, "free_gb": round(du.free / 1e9, 1)}


_news_job = {"running": False}


def _refresh_news():
    """Ri-scarica le notizie dei soli argomenti seguiti + le analizza (in background)."""
    import mercato
    _news_job["running"] = True
    try:
        t = mercato.fetch()
        try:
            mercato.analyze(t)   # tagga i temi di mercato; le notizie generali restano titoli
        except Exception:
            pass
        mercato.CACHE.write_text(json.dumps(t, ensure_ascii=False), encoding="utf-8")
    except Exception as e:
        print(f"  ! refresh news err: {e}")
    finally:
        _news_job["running"] = False


def news_get():
    import mercato
    return mercato.get()


_job = {"running": False, "done_at": None, "err": None, "step": ""}


def _run_pipeline():
    """Lancia agent.py leggendo lo stdout riga per riga: _job['step'] = ultima riga
    utile, cosi il reattore mostra a che punto e' ([1/5]...[5/5])."""
    last_err = ""
    try:
        p = subprocess.Popen([sys.executable, "-u", str(ROOT / "agent.py")],
                             stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                             text=True, cwd=str(ROOT), bufsize=1)
        for line in p.stdout:
            line = line.strip()
            if line:
                _job["step"] = line[:80]
                last_err = line            # tengo l'ultima riga per un eventuale errore
        p.wait()
        _job["err"] = None if p.returncode == 0 else (last_err or "errore")[:200]
    except Exception as e:
        _job["err"] = str(e)
    finally:
        _job["running"] = False
        _job["step"] = ""
        _job["done_at"] = time.strftime("%H:%M")


def ollama_power(on):
    """Accende (ollama serve staccato) o spegne (taskkill ollama.exe) Ollama."""
    exe = shutil.which("ollama")
    if not exe:
        return {"ok": False, "err": "ollama non trovato nel PATH"}
    try:
        if on:
            # CREATE_NO_WINDOW (0x08000000): niente console. FONDAMENTALE: DETACHED_PROCESS
            # lasciava i sottoprocessi 'runner' di Ollama senza console => ognuno ne apriva
            # una propria (200 pop-up di terminale). CREATE_NO_WINDOW li tiene tutti nascosti.
            # Il figlio sopravvive comunque alla chiusura del server (Windows non lo termina).
            subprocess.Popen([exe, "serve"], creationflags=0x08000000,
                             stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            return {"ok": True, "running": True}
        # "ollama app.exe" e' la tray-app: se resta viva RIAVVIA subito ollama.exe.
        # Va uccisa PRIMA del server, altrimenti lo spegnimento non ha effetto.
        for img in ("ollama app.exe", "ollama.exe"):
            subprocess.run(["taskkill", "/IM", img, "/F"], capture_output=True, text=True)
        return {"ok": True, "running": False}
    except Exception as e:
        return {"ok": False, "err": str(e)[:150]}


def claude_usage():
    """Aggrega i consumi di token di Claude Code dai transcript locali (~/.claude/projects/*.jsonl).
    NB: i token 'rimanenti' non sono nei file locali; la percentuale usa un budget impostato dall'utente."""
    base = Path.home() / ".claude" / "projects"
    if not base.exists():
        return {"error": "nessun transcript trovato in ~/.claude/projects"}
    def _first_user_text(o):
        m = o.get("message") or {}
        if m.get("role") != "user":
            return None
        c = m.get("content")
        if isinstance(c, str):
            txt = c
        elif isinstance(c, list):
            txt = " ".join(b.get("text", "") for b in c if isinstance(b, dict) and b.get("type") == "text")
        else:
            return None
        txt = " ".join((txt or "").split())
        if not txt or txt.startswith("<") or txt.startswith("Caveat") or txt.startswith("[System"):
            return None
        return txt[:100]

    tot = {"input": 0, "output": 0, "cache_w": 0, "cache_r": 0}
    per_day, per_proj, models, sess = {}, {}, {}, {}
    msgs, files = 0, 0
    sessions = set()
    first = last = None
    for f in base.rglob("*.jsonl"):
        files += 1
        proj = f.parent.name
        try:
            lines = f.read_text(encoding="utf-8", errors="ignore").splitlines()
        except Exception:
            continue
        for line in lines:
            try:
                o = json.loads(line)
            except Exception:
                continue
            m = o.get("message") or {}
            sid = o.get("sessionId") or o.get("session_id") or f.stem
            s = sess.setdefault(sid, {"id": sid, "tok": 0, "msgs": 0, "first": None,
                                      "last": None, "cwd": "", "fu": ""})
            ts_full = o.get("timestamp") or ""
            if ts_full:
                s["first"] = ts_full if s["first"] is None or ts_full < s["first"] else s["first"]
                s["last"] = ts_full if s["last"] is None or ts_full > s["last"] else s["last"]
            if not s["cwd"] and o.get("cwd"):
                s["cwd"] = o["cwd"]
            if not s["fu"]:
                fu = _first_user_text(o)
                if fu:
                    s["fu"] = fu
            u = m.get("usage")
            if not isinstance(u, dict):
                continue
            it, ot = u.get("input_tokens", 0) or 0, u.get("output_tokens", 0) or 0
            cw = u.get("cache_creation_input_tokens", 0) or 0
            cr = u.get("cache_read_input_tokens", 0) or 0
            tot["input"] += it; tot["output"] += ot; tot["cache_w"] += cw; tot["cache_r"] += cr
            msgs += 1
            tt = it + ot + cw + cr
            bil = it + ot + cw  # token "che pesano": esclude la cache riletta (riuso, costo ~nullo)
            sessions.add(sid)
            s["tok"] += tt; s["msgs"] += 1
            ts = ts_full[:10]
            if ts:
                pd = per_day.setdefault(ts, [0, 0])
                pd[0] += tt; pd[1] += bil
                first = ts if first is None or ts < first else first
                last = ts if last is None or ts > last else last
            per_proj[proj] = per_proj.get(proj, 0) + tt
            mdl = m.get("model")
            if mdl:
                models[mdl] = models.get(mdl, 0) + tt
    sess_list = sorted(sess.values(), key=lambda x: x["last"] or "", reverse=True)
    for s in sess_list:
        s["cwd"] = (s["cwd"] or "").replace("\\", "/").rstrip("/").split("/")[-1]
        s["first"] = (s["first"] or "")[:10]
        s["last"] = (s["last"] or "")[:10]
    return {
        "sessions_list": sess_list[:40],
        "tot": tot, "total": sum(tot.values()),
        "billable": tot["input"] + tot["output"] + tot["cache_w"],
        "messages": msgs,
        "sessions": len(sessions) or files, "files": files,
        "per_day": [{"day": d, "tok": v[0], "bil": v[1]} for d, v in sorted(per_day.items())],
        "per_proj": sorted([{"proj": k, "tok": v} for k, v in per_proj.items()], key=lambda x: -x["tok"])[:8],
        "models": sorted([{"model": k, "tok": v} for k, v in models.items()], key=lambda x: -x["tok"]),
        "first": first, "last": last,
    }


def health():
    """Colpo d'occhio: Ollama attivo? ultimo run? spazio disco? freschezza dati."""
    ok = llm.status()
    lc = llm.get_cfg()
    du = shutil.disk_usage("C:\\")
    dj = ROOT / "disco.json"
    disco_age = round((time.time() - dj.stat().st_mtime) / 3600, 1) if dj.exists() else None
    db = ROOT / "db.sqlite"
    gh_age = round((time.time() - db.stat().st_mtime) / 3600, 1) if db.exists() else None
    return {"ollama": ok, "modello": lc["model"], "provider": lc["provider"], "local": llm.is_local(),
            "disk_free_gb": round(du.free / 1e9), "disk_free_pct": round(du.free / du.total * 100, 1),
            "github_age_h": gh_age, "disco_age_h": disco_age,
            "last_run": _job.get("done_at"), "running": _job["running"]}


def refresh_start():
    """Avvia l'acquisizione delle conoscenze del giorno se non gia in corso."""
    if _job["running"]:
        return {"ok": True, "running": True}
    _job["running"] = True
    _job["err"] = None
    threading.Thread(target=_run_pipeline, daemon=True).start()
    return {"ok": True, "running": True}


def empty_bin():
    """Svuota il Cestino: QUI lo spazio viene liberato davvero (irreversibile)."""
    r = subprocess.run(["powershell", "-NoProfile", "-Command",
                        "Clear-RecycleBin -Force -ErrorAction SilentlyContinue"],
                       capture_output=True, text=True)
    du = shutil.disk_usage("C:\\")
    return {"ok": r.returncode == 0, "free_gb": round(du.free / 1e9, 1)}


_net0 = psutil.net_io_counters()
_t0 = time.time()
psutil.cpu_percent(percpu=True)  # primo campione (il primo ritorna 0)


def _gpu():
    exe = shutil.which("nvidia-smi")
    if not exe:
        return {}
    try:
        out = subprocess.run(
            [exe, "--query-gpu=utilization.gpu,temperature.gpu,memory.used,memory.total,power.draw",
             "--format=csv,noheader,nounits"],
            capture_output=True, text=True, timeout=5).stdout.strip()
        p = [x.strip() for x in out.splitlines()[0].split(",")]
        return {"util": int(float(p[0])), "temp": int(float(p[1])),
                "vram_used": int(float(p[2])), "vram_tot": int(float(p[3])),
                "power": round(float(p[4])) if p[4].replace(".", "").isdigit() else None}
    except Exception:
        return {}


def telemetry():
    global _net0, _t0
    vm = psutil.virtual_memory()
    sw = psutil.swap_memory()
    du = psutil.disk_usage("C:\\")
    n1 = psutil.net_io_counters()
    t1 = time.time()
    dt = max(.001, t1 - _t0)
    down = (n1.bytes_recv - _net0.bytes_recv) / dt / 125000.0  # Mbit/s
    up = (n1.bytes_sent - _net0.bytes_sent) / dt / 125000.0
    _net0, _t0 = n1, t1
    freq = psutil.cpu_freq()
    bat = psutil.sensors_battery()
    return {
        "cpu_pct": psutil.cpu_percent(),
        "cpu_cores": psutil.cpu_percent(percpu=True),
        "cpu_ghz": round(freq.current / 1000, 2) if freq else None,
        "ram_pct": vm.percent, "ram_used": round(vm.used / 1e9, 1), "ram_tot": round(vm.total / 1e9, 1),
        "swap_pct": sw.percent,
        "disk_pct": du.percent, "disk_used": round(du.used / 1e9), "disk_tot": round(du.total / 1e9),
        "net_down": round(down, 2), "net_up": round(up, 2),
        "gpu": _gpu(),
        "battery": {"pct": round(bat.percent) if bat else None,
                    "charging": bat.power_plugged if bat else None,
                    "secsleft": bat.secsleft if bat and bat.secsleft > 0 else None},
        "procs": len(psutil.pids()),
        "uptime": int(time.time() - psutil.boot_time()),
        "ts": time.strftime("%H:%M:%S"),
    }


class H(BaseHTTPRequestHandler):
    def _send(self, body, ctype):
        self.send_response(200)
        self.send_header("Content-Type", ctype)
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        # CSP: connect-src 'self' impedisce che un eventuale XSS mandi i dati FUORI dal PC.
        # L'app non carica nulla di esterno (solo link <a> a github, che restano navigabili).
        self.send_header("Content-Security-Policy",
                         "default-src 'self'; script-src 'self' 'unsafe-inline'; "
                         "style-src 'self' 'unsafe-inline'; img-src 'self' data:; "
                         "font-src 'self' data:; connect-src 'self'; object-src 'none'; "
                         "base-uri 'none'; form-action 'self'; frame-ancestors 'none'")
        self.send_header("Referrer-Policy", "no-referrer")
        self.end_headers()
        self.wfile.write(body)

    def _local_only(self):
        """Difesa CSRF + DNS-rebinding: accetta solo richieste il cui Host e la cui
        Origin (se presente) puntano a 127.0.0.1/localhost. Blocca un sito malevolo
        aperto nel browser dal raggiungere o leggere i dati personali via 127.0.0.1."""
        host = (self.headers.get("Host", "").rsplit(":", 1)[0] or "").lower()
        if host and host not in ALLOWED_HOSTS:
            self.send_error(403, "host non consentito")
            return False
        origin = self.headers.get("Origin")
        if origin:
            from urllib.parse import urlparse
            if (urlparse(origin).hostname or "").lower() not in ALLOWED_HOSTS:
                self.send_error(403, "origine non consentita")
                return False
        return True

    def log_message(self, *a):
        pass  # niente log su console (privacy: i path possono contenere query)

    def _send_cookie(self, body, ctype, cookie):
        self.send_response(200)
        self.send_header("Content-Type", ctype)
        self.send_header("Cache-Control", "no-store")
        self.send_header("Set-Cookie", cookie)
        self.end_headers()
        self.wfile.write(body)

    def _auth_ok(self):
        """Se e' impostato un PIN, blocca gli endpoint dati finche non si sblocca."""
        if not pin_is_set():
            return True
        if self.path.split("?")[0] in _PUBLIC:
            return True
        if _cookie_token(self) in _SESS:
            return True
        self.send_error(401, "bloccato: inserisci il PIN")
        return False

    def do_GET(self):
        if not self._local_only() or not self._auth_ok():
            return
        if self.path.startswith("/telemetry"):
            self._send(json.dumps(telemetry()).encode(), "application/json")
        elif self.path.startswith("/crypto"):
            self._send(json.dumps(crypto.get(refresh=True)).encode(), "application/json")
        elif self.path.startswith("/search"):
            from urllib.parse import parse_qs, urlparse
            q = (parse_qs(urlparse(self.path).query).get("q", [""])[0]).strip()
            res = search_gh(q) if q else []
            self._send(json.dumps(res).encode(), "application/json")
        elif self.path.startswith("/refresh"):
            self._send(json.dumps(_job).encode(), "application/json")
        elif self.path.startswith("/health"):
            self._send(json.dumps(health()).encode(), "application/json")
        elif self.path.startswith("/weekly"):
            p = ROOT / "weekly.json"
            body = p.read_text(encoding="utf-8") if p.exists() else '{"testo":""}'
            self._send(body.encode(), "application/json")
        elif self.path.split("?")[0] == "/manifest.webmanifest":
            self._send(MANIFEST.encode(), "application/manifest+json")
        elif self.path.split("?")[0] == "/sw.js":
            self._send(SW_JS.encode(), "text/javascript")
        elif self.path.split("?")[0] == "/icon.svg":
            self._send(ICON_SVG.encode(), "image/svg+xml")
        elif self.path.startswith("/claude-usage"):
            self._send(json.dumps(claude_usage(), ensure_ascii=False).encode(), "application/json")
        elif self.path.startswith("/usage"):
            self._send(json.dumps(usage.all_usage(), ensure_ascii=False).encode(), "application/json")
        elif self.path.split("?")[0] == "/store":
            self._send(json.dumps(store_get(), ensure_ascii=False).encode(), "application/json")
        elif self.path.split("?")[0] == "/auth-status":
            self._send(json.dumps({"locked": pin_is_set(), "authed": _cookie_token(self) in _SESS}).encode(), "application/json")
        elif self.path.split("?")[0] == "/topics":
            import mercato
            self._send(json.dumps(mercato.catalog(), ensure_ascii=False).encode(), "application/json")
        elif self.path.split("?")[0] == "/interests":
            import ideas
            self._send(json.dumps(ideas.catalog(), ensure_ascii=False).encode(), "application/json")
        elif self.path.split("?")[0] == "/autostart":
            self._send(json.dumps(autostart_status()).encode(), "application/json")
        elif self.path.split("?")[0] == "/mt-status":
            from urllib.parse import urlparse, parse_qs
            import mt
            lang = (parse_qs(urlparse(self.path).query).get("lang", ["it"])[0]).strip() or "it"
            self._send(json.dumps({"ready": mt.is_ready(lang)}).encode(), "application/json")
        elif self.path.split("?")[0] == "/news":
            self._send(json.dumps(news_get(), ensure_ascii=False).encode(), "application/json")
        elif self.path.split("?")[0] == "/news-status":
            self._send(json.dumps(_news_job).encode(), "application/json")
        elif self.path.split("?")[0] == "/llm-config":
            c = llm.get_cfg()
            out = {"provider": c["provider"], "base": c["base"], "model": c["model"],
                   "model_forte": c["model_forte"], "has_key": bool(c.get("key")),
                   "lang": c.get("lang", "it"), "langs": [{"code": a, "name": b} for a, b in llm.LANGS],
                   "local": llm.is_local(), "online": llm.status(), "models": llm.list_models()}
            self._send(json.dumps(out, ensure_ascii=False).encode(), "application/json")
        elif self.path.split("?")[0] == "/cyber-seed":
            import cybergame
            self._send(json.dumps(cybergame.get(), ensure_ascii=False).encode(), "application/json")
        elif self.path.startswith("/idea"):
            from urllib.parse import urlparse, parse_qs
            import ideas
            settore = (parse_qs(urlparse(self.path).query).get("settore", ["tech"])[0]).strip() or "tech"
            out = ideas.one(settore, ollama_url=CFG["ollama_url"], model=CFG["modello"])
            self._send(json.dumps(out, ensure_ascii=False).encode(), "application/json")
        elif self.path.split("?")[0] in ("/app", "/app.html"):
            # bloccato + non sbloccato: NON servire app.html (contiene il payload dati);
            # mostro solo la schermata di sblocco. I dati arrivano dopo l'unlock.
            if pin_is_set() and _cookie_token(self) not in _SESS:
                self._send(LOCK_HTML.encode(), "text/html; charset=utf-8")
                return
            app = ROOT / "app.html"
            if not app.exists():
                self.send_error(404, "app.html mancante: lancia prima ui.py")
                return
            self._send(app.read_bytes(), "text/html; charset=utf-8")
        elif self.path.split("?")[0] in ("/", "/index.html", "/dashboard.html"):
            if pin_is_set() and _cookie_token(self) not in _SESS:
                self._send(LOCK_HTML.encode(), "text/html; charset=utf-8")
                return
            if not DASH.exists():
                self.send_error(404, "dashboard.html mancante: lancia prima agent.py")
                return
            self._send(DASH.read_bytes(), "text/html; charset=utf-8")
        else:
            self.send_error(404)

    def do_POST(self):
        if not self._local_only() or not self._auth_ok():
            return
        ln = int(self.headers.get("Content-Length", 0))
        if ln > 12_000_000:                      # tetto: PDF/testi grandi ok, non oltre
            self.send_error(413, "richiesta troppo grande")
            return
        try:
            data = json.loads(self.rfile.read(ln) or b"{}")
        except Exception:
            data = {}
        if self.path.startswith("/ask-stream"):
            q = str(data.get("q", "")).strip()
            self.send_response(200)
            self.send_header("Content-Type", "text/event-stream; charset=utf-8")
            self.send_header("Cache-Control", "no-store")
            self.send_header("X-Content-Type-Options", "nosniff")
            self.end_headers()
            try:
                for ch in (llm.stream(ask_prompt(q)) if q else iter(())):
                    self.wfile.write(("data: " + json.dumps(ch) + "\n\n").encode())
                    self.wfile.flush()
            except Exception as e:
                try:
                    self.wfile.write(("data: " + json.dumps({"err": str(e)[:120]}) + "\n\n").encode())
                except Exception:
                    pass
            try:
                self.wfile.write(b"event: done\ndata: {}\n\n")
                self.wfile.flush()
            except Exception:
                pass
        elif self.path.startswith("/ask"):
            q = str(data.get("q", "")).strip()
            self._send(json.dumps({"answer": ask(q) if q else "Fai una domanda."}).encode(),
                       "application/json")
        elif self.path.startswith("/rewrite"):
            self._send(json.dumps(rewrite(data.get("text", ""), str(data.get("mode", "correggi"))), ensure_ascii=False).encode(),
                       "application/json")
        elif self.path.startswith("/fondi"):
            self._send(json.dumps(fondi(data.get("ideas") or [])).encode(), "application/json")
        elif self.path.startswith("/onepager"):
            import ideas
            out = ideas.onepager(data.get("idea") or {}, ollama_url=CFG["ollama_url"], model=CFG["modello"])
            self._send(json.dumps(out, ensure_ascii=False).encode(), "application/json")
        elif self.path.startswith("/cyber-gen"):
            import cybergame
            try:
                out = cybergame.gen(str(data.get("chapter", "phishing")), int(data.get("diff", 1)),
                                    avoid=data.get("avoid") or [], ollama_url=CFG["ollama_url"], model=CFG["modello"])
            except Exception as e:
                out = {"error": f"Generazione fallita: {e}"[:160]}
            self._send(json.dumps(out, ensure_ascii=False).encode(), "application/json")
        elif self.path.startswith("/cv-latex"):
            import cv
            try:
                text = str(data.get("text", "") or "")
                sugg = str(data.get("suggestions", "") or "")
                if data.get("pdf"):
                    text = cv.extract_text(base64.b64decode(str(data["pdf"])))
                elif data.get("analysis"):
                    a = data["analysis"]
                    text = cv.analysis_to_text(a)
                    if not sugg:
                        sugg = cv.suggestions_from(a)
                if not text.strip():
                    out = {"error": "Nessun testo di partenza: incolla un CV o analizzane uno."}
                else:
                    tex, cvj = cv.build_latex(text, sugg)
                    out = {"ok": True, "tex": tex, "cv": cvj, "latex": cv.latex_available()}
            except ValueError as e:
                out = {"error": str(e)}
            except Exception as e:
                out = {"error": f"Generazione LaTeX fallita: {e}"[:160]}
            self._send(json.dumps(out, ensure_ascii=False).encode(), "application/json")
        elif self.path.startswith("/cv-extract"):
            import cv
            try:
                text = str(data.get("text", "") or "")
                if data.get("pdf"):
                    text = cv.extract_text(base64.b64decode(str(data["pdf"])))
                if not text.strip():
                    out = {"error": "Nessun testo: carica un PDF con testo o incolla il CV."}
                else:
                    out = {"ok": True, "model": cv.cv_extract_structured(text), "latex": cv.latex_available()}
            except ValueError as e:
                out = {"error": str(e)}
            except Exception as e:
                out = {"error": f"Estrazione fallita: {e}"[:160]}
            self._send(json.dumps(out, ensure_ascii=False).encode(), "application/json")
        elif self.path.startswith("/cv-improve"):
            import cv
            try:
                out = {"ok": True, "text": cv.improve_text(str(data.get("text", "")), str(data.get("ruolo", "")))}
            except Exception as e:
                out = {"error": f"Migliora fallito: {e}"[:160]}
            self._send(json.dumps(out, ensure_ascii=False).encode(), "application/json")
        elif self.path.startswith("/cv-render"):
            import cv
            try:
                out = {"ok": True, "tex": cv.render_latex_generic(data.get("model") or {}), "latex": cv.latex_available()}
            except Exception as e:
                out = {"error": f"Render fallito: {e}"[:160]}
            self._send(json.dumps(out, ensure_ascii=False).encode(), "application/json")
        elif self.path.startswith("/cv-pdf"):
            import cv
            pdf, err = cv.compile_pdf(str(data.get("tex", "")))
            if pdf:
                out = {"ok": True, "pdf": base64.b64encode(pdf).decode()}
            else:
                out = {"ok": False, "err": err}
            self._send(json.dumps(out, ensure_ascii=False).encode(), "application/json")
        elif self.path.startswith("/cv"):
            import cv
            try:
                out = cv.analyze_b64(str(data.get("pdf", "")), ollama_url=CFG["ollama_url"], model=CFG["modello"])
            except ValueError as e:
                out = {"error": str(e)}
            except Exception as e:
                out = {"error": f"Analisi fallita: {e}"[:160]}
            self._send(json.dumps(out, ensure_ascii=False).encode(), "application/json")
        elif self.path.startswith("/pdfsum"):
            import cv
            try:
                out = cv.pdf_summary_b64(str(data.get("pdf", "")), ollama_url=CFG["ollama_url"], model=CFG["modello"])
            except ValueError as e:
                out = {"error": str(e)}
            except Exception as e:
                out = {"error": f"Riassunto fallito: {e}"[:160]}
            self._send(json.dumps(out, ensure_ascii=False).encode(), "application/json")
        elif self.path.startswith("/interview"):
            import cv
            try:
                out = cv.interview(data.get("cv") or {}, str(data.get("ruolo", "")), ollama_url=CFG["ollama_url"], model=CFG["modello"])
            except Exception as e:
                out = {"error": f"Ollama: {e}"[:160]}
            self._send(json.dumps(out, ensure_ascii=False).encode(), "application/json")
        elif self.path.startswith("/jobmatch"):
            import cv
            url = str(data.get("url", "")).strip()
            try:
                if url:
                    out = cv.jobmatch_url(data.get("cv") or {}, url, ollama_url=CFG["ollama_url"], model=CFG["modello"])
                else:
                    out = cv.jobmatch(data.get("cv") or {}, str(data.get("annuncio", "")), ollama_url=CFG["ollama_url"], model=CFG["modello"])
            except ValueError as e:
                out = {"error": str(e)}
            except Exception as e:
                out = {"error": f"Ollama: {e}"[:160]}
            self._send(json.dumps(out, ensure_ascii=False).encode(), "application/json")
        elif self.path.startswith("/app-shortcut"):
            self._send(json.dumps(make_app_shortcut(), ensure_ascii=False).encode(), "application/json")
        elif self.path.startswith("/unlock"):
            if pin_check(data.get("pin", "")):
                _set_key_from_pin(data.get("pin", ""))   # deriva la chiave per decifrare lo store
                tok = secrets.token_hex(24); _SESS.add(tok)
                self._send_cookie(json.dumps({"ok": True}).encode(), "application/json",
                                  f"miai_sess={tok}; Path=/; SameSite=Strict; HttpOnly; Max-Age=2592000")
            else:
                self._send(json.dumps({"ok": False, "err": "PIN errato"}).encode(), "application/json")
        elif self.path.startswith("/set-pin"):
            # per cambiare/togliere un PIN gia impostato serve essere sbloccati (gestito da _auth_ok);
            # se ne stai impostando uno nuovo, ti do subito una sessione valida.
            r = pin_set(data.get("pin", ""))
            if r.get("ok") and r.get("locked"):
                tok = secrets.token_hex(24); _SESS.add(tok)
                self._send_cookie(json.dumps(r).encode(), "application/json",
                                  f"miai_sess={tok}; Path=/; SameSite=Strict; HttpOnly; Max-Age=2592000")
            else:
                self._send(json.dumps(r).encode(), "application/json")
        elif self.path.startswith("/lock"):
            _SESS.discard(_cookie_token(self))
            if not _SESS:
                _clear_key()
            self._send_cookie(json.dumps({"ok": True}).encode(), "application/json",
                              "miai_sess=; Path=/; SameSite=Strict; HttpOnly; Max-Age=0")
        elif self.path.startswith("/topics"):
            import mercato
            ids = mercato.set_followed(data.get("followed") or [])
            if not _news_job["running"]:
                threading.Thread(target=_refresh_news, daemon=True).start()
            self._send(json.dumps({"ok": True, "followed": ids}, ensure_ascii=False).encode(), "application/json")
        elif self.path.startswith("/interests"):
            import ideas
            ids = ideas.set_interests(data.get("selected") or [])
            self._send(json.dumps({"ok": True, "selected": ids}, ensure_ascii=False).encode(), "application/json")
        elif self.path.startswith("/llm-config"):
            c = llm.set_cfg(data)
            self._send(json.dumps({"ok": True, "provider": c["provider"], "model": c["model"], "online": llm.status()}, ensure_ascii=False).encode(), "application/json")
        elif self.path.startswith("/desktop-shortcut"):
            self._send(json.dumps(make_desktop_shortcut(), ensure_ascii=False).encode(), "application/json")
        elif self.path.startswith("/autostart"):
            self._send(json.dumps(autostart_set(bool(data.get("on"))), ensure_ascii=False).encode(), "application/json")
        elif self.path.startswith("/mt-install"):
            import mt
            self._send(json.dumps(mt.ensure_lang(str(data.get("lang", "it"))), ensure_ascii=False).encode(), "application/json")
        elif self.path.startswith("/translate"):
            import mt
            self._send(json.dumps(mt.translate_batch(data.get("texts") or [], str(data.get("lang", "it"))),
                                  ensure_ascii=False).encode(), "application/json")
        elif self.path.startswith("/server-restart"):
            self._send(json.dumps(server_restart()).encode(), "application/json")
        elif self.path.startswith("/store"):
            self._send(json.dumps(store_set(data)).encode(), "application/json")
        elif self.path.startswith("/ollama"):
            self._send(json.dumps(ollama_power(bool(data.get("on")))).encode(), "application/json")
        elif self.path.startswith("/mappa"):
            self._send(json.dumps(mappa(str(data.get("title", "")), str(data.get("ctx", "")),
                                        deep=bool(data.get("deep")), regen=bool(data.get("regen")))).encode(),
                       "application/json")
        elif self.path.startswith("/trash"):
            self._send(json.dumps(trash(str(data.get("path", "")))).encode(), "application/json")
        elif self.path.startswith("/emptybin"):
            self._send(json.dumps(empty_bin()).encode(), "application/json")
        elif self.path.startswith("/refresh"):
            self._send(json.dumps(refresh_start()).encode(), "application/json")
        elif self.path.startswith("/update"):
            # ricarica a caldo ui.py/agent.py e rigenera app.html (aggiorna UI + dati
            # senza riavviare il processo: evita i conflitti di porta su Windows).
            out = {"ok": True}
            try:
                import importlib
                import agent as _agent
                import ui as _ui
                importlib.reload(_agent)
                importlib.reload(_ui)
                _ui.render_ui()
            except Exception as e:
                out = {"ok": False, "err": str(e)[:200]}
            self._send(json.dumps(out).encode(), "application/json")
        else:
            self.send_error(404)

    def log_message(self, *a):
        pass


if __name__ == "__main__":
    url = f"http://localhost:{PORT}/"
    print(f"Jarvis server -> {url}  (Ctrl+C per fermare)")
    if "--open" in sys.argv or "-o" in sys.argv:
        webbrowser.open(url)
    try:
        ThreadingHTTPServer(("127.0.0.1", PORT), H).serve_forever()
    except KeyboardInterrupt:
        print("\nstop.")
