#!/usr/bin/env python3
"""Jarvis GitHub Agent - Fase 1: report nuove uscite + tendenze.

Pipeline: fetch (GitHub API) -> filter/dedup (SQLite) -> rank (Ollama) -> render (dashboard.html).
Config in config.yaml. Nessun costo: GitHub API free, Ollama locale.
"""
import os, sys, json, sqlite3, datetime, webbrowser, time
from pathlib import Path
import requests
import llm
import yaml
from auth import get_token
import advisor
import machine

GH_TOKEN = None  # popolato in main() da get_token()
ROOT = Path(__file__).parent
CFG = yaml.safe_load((ROOT / "config.yaml").read_text(encoding="utf-8"))
DB = ROOT / "db.sqlite"
DASH = ROOT / "dashboard.html"
GH_API = "https://api.github.com/search/repositories"


# ---------- storage ----------
def db_init():
    con = sqlite3.connect(DB)
    con.execute("""CREATE TABLE IF NOT EXISTS repos(
        full_name TEXT PRIMARY KEY, url TEXT, description TEXT, language TEXT,
        stars INTEGER, category TEXT, score INTEGER, reason TEXT,
        first_seen TEXT, pushed_at TEXT)""")
    # migrazione: colonna verdetto compatibilita (Fase 4)
    cols = [c[1] for c in con.execute("PRAGMA table_info(repos)")]
    if "verdict" not in cols:
        con.execute("ALTER TABLE repos ADD COLUMN verdict TEXT")
    if "license" not in cols:
        con.execute("ALTER TABLE repos ADD COLUMN license TEXT")
    if "biz" not in cols:
        con.execute("ALTER TABLE repos ADD COLUMN biz INTEGER")
    if "tipo" not in cols:
        con.execute("ALTER TABLE repos ADD COLUMN tipo TEXT")
    # storico stelle per calcolare la VELOCITA (trending reale, non solo totale)
    con.execute("""CREATE TABLE IF NOT EXISTS star_snap(
        full_name TEXT, day TEXT, stars INTEGER, PRIMARY KEY(full_name,day))""")
    # memoria: snapshot giornalieri per il diff "cosa e cambiato da ieri"
    con.execute("""CREATE TABLE IF NOT EXISTS mercato_snap(
        day TEXT, topic TEXT, title TEXT, PRIMARY KEY(day,topic,title))""")
    con.execute("""CREATE TABLE IF NOT EXISTS idee_snap(
        day TEXT, titolo TEXT, novelta TEXT, PRIMARY KEY(day,titolo))""")
    # storico spazio disco per il trend e la previsione "pieno tra N giorni"
    con.execute("""CREATE TABLE IF NOT EXISTS disco_snap(
        day TEXT PRIMARY KEY, free_gb REAL, tot_gb REAL)""")
    con.commit()
    return con


def changes(con, today):
    """Diff vs il giorno precedente registrato: nuovi eventi mercato e nuove idee."""
    def prevday(tbl):
        r = con.execute(f"SELECT MAX(day) FROM {tbl} WHERE day<?", (today,)).fetchone()
        return r[0] if r else None
    pm, pi = prevday("mercato_snap"), prevday("idee_snap")
    ev, idee = [], []
    if pm:
        ev = [{"topic": t, "title": ti} for t, ti in con.execute(
            "SELECT topic,title FROM mercato_snap WHERE day=? AND title NOT IN "
            "(SELECT title FROM mercato_snap WHERE day=?) LIMIT 8", (today, pm)).fetchall()]
    if pi:
        idee = [{"titolo": t, "novelta": n} for t, n in con.execute(
            "SELECT titolo,novelta FROM idee_snap WHERE day=? AND titolo NOT IN "
            "(SELECT titolo FROM idee_snap WHERE day=?)", (today, pi)).fetchall()]
    return {"eventi": ev, "idee": idee, "prima_volta": not (pm or pi)}


def velocity(con, full_name):
    """Stelle guadagnate al giorno tra il primo e l'ultimo snapshot. None se <2 punti."""
    rows = con.execute("SELECT day,stars FROM star_snap WHERE full_name=? ORDER BY day",
                       (full_name,)).fetchall()
    if len(rows) < 2:
        return None
    (d0, s0), (d1, s1) = rows[0], rows[-1]
    days = (datetime.date.fromisoformat(d1) - datetime.date.fromisoformat(d0)).days or 1
    v = round((s1 - s0) / days)
    return v if v > 0 else None


def already_seen(con, full_name):
    return con.execute("SELECT 1 FROM repos WHERE full_name=?", (full_name,)).fetchone() is not None


# ---------- fetch ----------
def gh_search(query, per_page=30):
    headers = {"Accept": "application/vnd.github+json"}
    token = GH_TOKEN or ""
    if token:
        headers["Authorization"] = f"Bearer {token}"
    params = {"q": query, "sort": "stars", "order": "desc", "per_page": per_page}
    r = requests.get(GH_API, headers=headers, params=params, timeout=30)
    if r.status_code == 403 and "rate limit" in r.text.lower():
        print("  ! rate limit GitHub. Aspetta o metti GITHUB_TOKEN (vedi config).")
        return []
    r.raise_for_status()
    return r.json().get("items", [])


def since(days):
    return (datetime.date.today() - datetime.timedelta(days=days)).isoformat()


def fetch_all():
    """Ritorna lista repo grezze (dedup su full_name), taggate nuove/trend."""
    seen, out = set(), []
    langs = CFG["linguaggi"]
    # nuove uscite
    q_new = f"created:>{since(CFG['giorni_nuove'])} stars:>={CFG['stelle_min_nuove']}"
    # tendenza: affermate ma attive di recente
    q_trend = f"pushed:>{since(CFG['giorni_trend'])} stars:>={CFG['stelle_min_trend']}"
    for lang in langs:
        for cat, base in (("nuova", q_new), ("tendenza", q_trend)):
            print(f"  fetch {cat} [{lang}]...")
            for it in gh_search(f"{base} language:{lang}"):
                fn = it["full_name"]
                if fn in seen:
                    continue
                seen.add(fn)
                out.append({
                    "full_name": fn, "url": it["html_url"],
                    "description": it.get("description") or "",
                    "language": it.get("language") or lang,
                    "stars": it.get("stargazers_count", 0),
                    "category": cat, "pushed_at": it.get("pushed_at", ""),
                    "license": (it.get("license") or {}).get("spdx_id") or "",
                })
    return out


# ---------- rank (Ollama) ----------
def rank(repo):
    interessi = "\n".join(f"- {i}" for i in CFG["interessi"])
    prompt = (
        "Sei un filtro che valuta la rilevanza di una repository GitHub per un utente.\n"
        f"Interessi dell'utente:\n{interessi}\n\n"
        f"Repository:\n- nome: {repo['full_name']}\n- linguaggio: {repo['language']}\n"
        f"- stelle: {repo['stars']}\n- descrizione: {repo['description']}\n\n"
        "Rispondi SOLO in JSON: {\"score\": <intero 0-10 rilevanza vs interessi>, "
        "\"biz\": <intero 0-10 quanto e' MONETIZZABILE: si puo costruirci un prodotto/servizio a pagamento>, "
        "\"tipo\": \"<dominio in 1-3 parole: es. computer vision, object detection, LLM/NLP, "
        "machine learning, cybersecurity, blockchain/web3, smart contract, web/frontend, backend/API, "
        "devtools, data engineering, robotica, medicina/health, fintech, gaming, mobile, altro>\", "
        "\"reason\": \"<una frase breve in italiano sul perche puo interessare>\"}"
    )
    try:
        data = json.loads(llm.generate(prompt, fmt="json", timeout=120))
        return (int(data.get("score", 0)), str(data.get("reason", "")).strip(),
                int(data.get("biz", 0)), str(data.get("tipo", "")).strip().lower()[:28])
    except Exception as e:
        print(f"  ! ollama err su {repo['full_name']}: {e}")
        return 0, "", 0, ""


# ---------- render ----------
def _forecast(hist, cur):
    """Stima 'giorni al disco pieno' dal ritmo di consumo recente.
    hist: [(day_iso, free_gb)]. Serve almeno 2 giorni distinti con perdita netta."""
    if len(hist) < 2:
        return {"stato": "raccolta dati", "giorni": None}
    d0 = datetime.date.fromisoformat(hist[0][0])
    dn = datetime.date.fromisoformat(hist[-1][0])
    span = (dn - d0).days
    if span < 1:
        return {"stato": "raccolta dati", "giorni": None}
    delta = hist[-1][1] - hist[0][1]          # + = liberato, - = consumato
    rate = delta / span                        # GB/giorno
    free = cur.get("free_gb") or hist[-1][1]
    if rate >= -0.05:                          # stabile o in miglioramento
        return {"stato": "stabile", "gb_giorno": round(rate, 2), "giorni": None}
    giorni = int(free / -rate)
    return {"stato": "in calo", "gb_giorno": round(rate, 2), "giorni": giorni}


def build_payload(con):
    cutoff = since(max(CFG["giorni_nuove"], CFG["giorni_trend"]))
    rows = con.execute(
        "SELECT full_name,url,description,language,stars,category,score,reason,first_seen,verdict,pushed_at,license,biz,tipo "
        "FROM repos WHERE first_seen>=? ORDER BY score DESC, stars DESC LIMIT ?",
        (cutoff, CFG["max_report"] * 3)).fetchall()
    today = datetime.date.today().isoformat()
    cards = []
    for fn, url, desc, lang, stars, cat, score, reason, seen, verdict, pushed, lic, biz, tipo in rows:
        is_new = seen == today
        cards.append({
            "full_name": fn, "url": url, "description": desc, "language": lang or "",
            "stars": stars, "category": cat, "score": score, "reason": reason,
            "new_today": is_new, "verdict": json.loads(verdict) if verdict else None,
            "vel": velocity(con, fn), "license": lic or "", "biz": biz, "tipo": tipo or "",
            "pushed": (pushed or "")[:10], "seen": seen,
        })
    import cyber, tips, blockchain, ideas, crypto, mercato, weekly, disco
    prof = machine.get()
    payload = {
        "github": cards,
        "cyber": cyber.personalize(cyber.get(), prof),
        "pc": tips.get(),
        "blockchain": blockchain.get(),
        "crypto": crypto.get(),
        "mercato": mercato.get(),
        "disco": disco.get(),
        "idee": ideas.get(),
        "cambiamenti": changes(con, datetime.date.today().isoformat()),
        "weekly": weekly.get(),
        "profile": prof,
        "updated": datetime.datetime.now().strftime("%Y-%m-%d %H:%M"),
    }
    # trend disco + previsione "pieno tra N giorni" dallo storico disco_snap
    try:
        hist = con.execute("SELECT day,free_gb FROM disco_snap ORDER BY day").fetchall()
    except sqlite3.OperationalError:
        hist = []
    if isinstance(payload.get("disco"), dict):
        payload["disco"]["trend"] = [{"day": d, "free_gb": g} for d, g in hist][-30:]
        payload["disco"]["previsione"] = _forecast(hist, payload["disco"].get("disco", {}))
    # freschezza: ore dall'ultimo aggiornamento di ogni sorgente (mtime della cache)
    def _age_h(p):
        return round((time.time() - p.stat().st_mtime) / 3600, 1) if p and p.exists() else None
    srcs = {"github": ROOT / "db.sqlite", "cyber": getattr(cyber, "CACHE", None),
            "pc": getattr(tips, "CACHE", None), "blockchain": getattr(blockchain, "CACHE", None),
            "disco": disco.CACHE, "mercato": mercato.CACHE, "idee": getattr(ideas, "CACHE", None)}
    payload["freshness"] = {k: _age_h(v) for k, v in srcs.items()}
    return payload


def _face(fname, family, weight):
    p = ROOT / fname
    return (f"@font-face{{font-family:'{family}';font-style:normal;font-weight:{weight};"
            f"font-display:swap;src:url(data:font/woff2;base64,{p.read_text().strip()}) format('woff2')}}") if p.exists() else ""


def _font_css():
    return "".join([
        _face("sg-500.b64", "Space Grotesk", "500"),
        _face("sg-600.b64", "Space Grotesk", "600"),
        _face("sg-700.b64", "Space Grotesk", "700"),
    ])


def render(con):
    payload = build_payload(con)
    html = DASH_TEMPLATE.replace("__PAYLOAD__", json.dumps(payload, ensure_ascii=False)) \
                        .replace("__UPDATED__", payload["updated"]) \
                        .replace("/*__FONT__*/", _font_css())
    DASH.write_text(html, encoding="utf-8")


DASH_TEMPLATE = r"""<!doctype html><html lang="it"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>J.A.R.V.I.S. - GitHub Radar</title><style>
/*__FONT__*/
:root{--cy:#7c8cff;--cy2:#5b6be0;--gold:#e8b56b;--red:#f2777a;--green:#54dca0;--ink:#0b0d16;
  --pane:rgba(20,22,38,.55);--glass:linear-gradient(158deg,rgba(58,64,104,.26),rgba(14,16,30,.5));
  --line:rgba(140,150,255,.13);--glow:rgba(124,140,255,.20);
  --txt:#e6e8f4;--mut:#9096b4;--tech:'Space Grotesk',"Segoe UI",system-ui,sans-serif;
  --card-r:14px;--sh:0 18px 48px -12px rgba(6,8,22,.7)}
*{box-sizing:border-box}
/* ===== display font (Space Grotesk) su titoli, numeri, etichette ===== */
h1,.name,.gauge span,.gauge b,.badge,.lbl,.status .cur,.stat .n,.sub,.tip-t,.legend b,.cbtn,.status,.title,.cnt,.auto{font-family:var(--tech)}
.badge,.lbl{letter-spacing:.6px}
.name{letter-spacing:-.01em}
.dt td,.stat .n,.gauge span,.ro .v,.ds b,.kc .kn{font-variant-numeric:tabular-nums}
/* ===== animazioni sobrie (fade-up, niente blur/flicker) ===== */
@keyframes materialize{from{opacity:0;transform:translateY(10px)}to{opacity:1;transform:none}}
@keyframes brkpulse{0%,100%{opacity:.55}50%{opacity:.85}}
html,body{margin:0;height:100%;overflow:hidden}
body{color:var(--txt);font:500 15px/1.6 var(--tech);letter-spacing:.1px;
  display:flex;flex-direction:column;height:100%;
  background:
    radial-gradient(52% 46% at 82% 6%,rgba(124,140,255,.16),transparent 62%),
    radial-gradient(46% 42% at 8% 96%,rgba(185,140,255,.13),transparent 64%),
    radial-gradient(60% 55% at 50% 44%,rgba(40,44,82,.30),transparent 72%),
    #0b0d16}
/* grana finissima (rompe la piattezza, niente vignetta pesante) */
.fx{position:fixed;inset:0;pointer-events:none;z-index:1;opacity:.035;mix-blend-mode:overlay;
  background:url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='160' height='160'%3E%3Cfilter id='n'%3E%3CfeTurbulence type='fractalNoise' baseFrequency='0.8' numOctaves='2' stitchTiles='stitch'/%3E%3C/filter%3E%3Crect width='100%25' height='100%25' filter='url(%23n)'/%3E%3C/svg%3E")}
/* overlay HUD slop rimossi (scanline/radar/CRT/reticoli/sweep) */
.radar,.crt,.beam,.hud{display:none}
@keyframes sweep{to{top:110%}}
.mono{font-family:ui-monospace,"Cascadia Code",Consolas,monospace}
@keyframes flick{0%,100%{opacity:1}}
/* header + reattore */
header{position:relative;z-index:3;padding:14px 26px;display:flex;align-items:center;gap:16px;flex-wrap:wrap;flex:none;
  border-bottom:1px solid var(--line);background:linear-gradient(180deg,rgba(16,18,30,.6),rgba(12,14,24,.25));backdrop-filter:blur(14px)}
.reactor{width:46px;height:46px;flex:none}
.reactor .rot{transform-origin:32px 32px;animation:spin 12s linear infinite}
.reactor .rot2{transform-origin:32px 32px;animation:spin 8s linear infinite reverse}
@keyframes spin{to{transform:rotate(360deg)}}
h1{font-size:22px;margin:0;font-weight:600;letter-spacing:.02em;color:#f2f3fb}
.sub{color:var(--mut);font-size:12px;letter-spacing:.16em;margin-top:3px;text-transform:uppercase}
.sub b{color:var(--cy);font-weight:600}
.stats{margin-left:auto;display:flex;gap:22px;text-align:right}
.stat .n{font-size:26px;color:var(--cy);line-height:1;font-weight:600}
.stat .l{font-size:10.5px;letter-spacing:.14em;color:var(--mut);text-transform:uppercase}
/* controlli */
.controls{position:relative;z-index:2;display:flex;gap:12px;flex-wrap:wrap;padding:6px 18px 10px;align-items:center;flex:none;
  border-bottom:1px solid rgba(124,140,255,.1)}
.fld{display:flex;flex-direction:column;gap:3px}
.fld label{font-size:9px;letter-spacing:2px;color:var(--mut);text-transform:uppercase;font-family:var(--tech)}
input,select{background:rgba(255,255,255,.04);color:var(--txt);
  border:1px solid rgba(140,150,255,.18);border-radius:9px;box-shadow:inset 0 1px 0 rgba(255,255,255,.04);
  padding:8px 12px;font-size:13px;font-family:var(--tech);font-weight:500;outline:none;transition:.18s}
input{min-width:220px}
input:focus,select:focus{border-color:color-mix(in srgb,var(--cy) 60%,transparent);box-shadow:0 0 0 3px rgba(124,140,255,.18)}
select{cursor:pointer;letter-spacing:.4px;font-size:12px}
option{background:#12141f}
/* griglia card */
main{position:relative;z-index:2;padding:18px 22px 30px;display:grid;gap:16px;
  grid-template-columns:repeat(auto-fill,minmax(330px,1fr));align-content:start}
.card{position:relative;border:1px solid var(--line);border-radius:var(--card-r);
  background:var(--glass),var(--pane);
  padding:22px 24px 20px;display:flex;flex-direction:column;gap:13px;backdrop-filter:blur(16px) saturate(1.15);
  box-shadow:var(--sh),inset 0 1px 0 rgba(255,255,255,.08),inset 0 0 0 1px rgba(255,255,255,.02);
  transition:border-color .3s,box-shadow .3s,transform .3s;overflow:hidden;
  animation:materialize .5s ease both}
.card:hover{border-color:color-mix(in srgb,var(--acc,var(--cy)) 55%,transparent);transform:translateY(-2px);
  box-shadow:0 24px 56px -14px rgba(6,8,22,.8),0 0 0 1px color-mix(in srgb,var(--acc,var(--cy)) 22%,transparent),inset 0 1px 0 rgba(255,255,255,.1)}
/* filo luce sul bordo alto (rifrazione vetro) invece dei corner bracket */
.card::before{content:"";position:absolute;inset:0 0 auto 0;height:1px;pointer-events:none;
  background:linear-gradient(90deg,transparent,color-mix(in srgb,var(--acc,var(--cy)) 40%,transparent),transparent)}
@keyframes boot{from{opacity:0;transform:translateY(10px)}to{opacity:1}}
.top{display:flex;align-items:flex-start;gap:12px}
.name{font-weight:600;color:#eef0fb;text-decoration:none;font-size:20px;word-break:break-word;flex:1;line-height:1.35;font-family:var(--tech);letter-spacing:.5px}
.name:hover{color:var(--cy);text-shadow:0 0 10px rgba(124,140,255,.6)}
/* gauge score */
.gauge{--p:0;width:52px;height:52px;flex:none;border-radius:50%;display:grid;place-items:center;position:relative;
  background:conic-gradient(var(--gc) calc(var(--p)*3.6deg),rgba(120,180,210,.12) 0)}
.gauge::before{content:"";position:absolute;inset:5px;border-radius:50%;background:var(--ink);box-shadow:inset 0 0 8px rgba(0,0,0,.5)}
.gauge span{position:relative;font-size:15px;font-weight:600;font-family:var(--tech)}
.gauge small{position:relative;font-size:8px;color:var(--mut);display:block;text-align:center;margin-top:-2px}
.g-hi{--gc:var(--cy)}.g-hi span{color:var(--cy)}
.g-mid{--gc:var(--gold)}.g-mid span{color:var(--gold)}
.g-lo{--gc:var(--red)}.g-lo span{color:var(--red)}
.badges{display:flex;gap:6px;flex-wrap:wrap}
.badge{font-size:11px;padding:3px 10px;letter-spacing:1.5px;text-transform:uppercase;border:1px solid;white-space:nowrap;border-radius:2px;
  background:rgba(255,255,255,.02);backdrop-filter:blur(2px)}
::selection{background:rgba(124,140,255,.28);color:#fff}
.b-nuova{color:var(--cy);border-color:rgba(124,140,255,.5)}
.b-tendenza{color:var(--gold);border-color:rgba(232,181,107,.5)}
.b-today{background:var(--cy);color:#03080e;border-color:var(--cy);font-weight:700;box-shadow:0 0 12px rgba(124,140,255,.6)}
.desc{color:#b6d9ea;font-size:15.5px;line-height:1.62}
.desc .lbl,.reason .lbl,.action .lbl{display:inline-block;margin-bottom:2px}
.reason{font-size:15px;color:var(--txt);border-left:2px solid var(--cy);padding-left:12px;padding-top:2px;padding-bottom:2px;background:rgba(124,140,255,.05);line-height:1.6}
.meta{display:flex;gap:16px;color:var(--mut);font-size:13.5px;margin-top:auto;align-items:center;font-family:Consolas,monospace;
  padding-top:8px;border-top:1px solid rgba(124,140,255,.1)}
.meta .lang{color:var(--cy)}
/* pannello compatibilita (Fase 4) */
.cbtn{margin-top:2px;background:rgba(124,140,255,.07);border:1px solid rgba(124,140,255,.3);color:var(--cy);
  font-size:10px;letter-spacing:2px;text-transform:uppercase;padding:6px 10px;cursor:pointer;
  display:flex;align-items:center;gap:8px;font-family:Consolas,monospace;transition:.15s}
.cbtn:hover{background:rgba(124,140,255,.16);box-shadow:0 0 12px rgba(124,140,255,.25)}
.cbtn .dot{width:8px;height:8px;border-radius:50%;box-shadow:0 0 8px currentColor}
.cbtn .arw{margin-left:auto;transition:transform .2s}
.card.open .cbtn .arw{transform:rotate(90deg)}
.compat{display:none;flex-direction:column;gap:9px;padding:13px;margin-top:2px;
  border:1px solid rgba(124,140,255,.18);background:rgba(2,12,20,.6);font-size:14px;line-height:1.55}
.card.open .compat{display:flex;animation:boot .3s ease both}
.v-si{color:var(--cy)}.v-parziale{color:var(--gold)}.v-no{color:var(--red)}.v-q{color:var(--mut)}
.lbl,.compat .lbl{font-size:11px;letter-spacing:2px;color:var(--cy);text-transform:uppercase;opacity:.85}
.compat .cmds{font-family:Consolas,monospace;background:#020a12;border-left:2px solid var(--cy);padding:8px 10px}
.compat .cmds div{white-space:pre-wrap;word-break:break-all;color:#bfe9fb;padding:1px 0}
.compat .cmds div::before{content:"> ";color:var(--mut)}
.compat .cp{align-self:flex-start;background:none;border:1px solid rgba(124,140,255,.3);color:var(--cy);
  font-size:9px;letter-spacing:2px;padding:4px 9px;cursor:pointer;text-transform:uppercase;font-family:Consolas,monospace}
.compat .cp:hover{background:rgba(124,140,255,.14)}
.compat .note{color:var(--gold);font-size:12px}
.empty{grid-column:1/-1;text-align:center;color:var(--mut);padding:70px;letter-spacing:3px;text-transform:uppercase}
#gh-live-bar{padding:7px 14px;margin:0 2px 4px;font-size:13px;color:#9fd8ff;background:rgba(124,140,255,.08);border-left:2px solid var(--cy);letter-spacing:1px}#gh-live-bar a{color:#f0cd9a}
/* nav sezioni */
.nav{display:flex;padding:0 26px;position:relative;z-index:2;border-bottom:1px solid rgba(124,140,255,.15);gap:2px}
.tab{background:none;border:none;border-bottom:2px solid transparent;color:var(--mut);padding:13px 22px;cursor:pointer;
  font:600 12px/1 "Segoe UI",sans-serif;letter-spacing:3px;text-transform:uppercase;transition:.2s}
.tab:hover{color:var(--txt)}
.tab.on{color:var(--cy);border-bottom-color:var(--cy)}
section{display:none}
section.on{display:flex;flex-direction:column;height:100%;min-height:0;animation:swoop .42s cubic-bezier(.16,.84,.28,1) both}
@keyframes swoop{from{opacity:0;transform:translateY(14px)}to{opacity:1;transform:none}}
/* viewport scorrevole (marquee automatico, scrollbar nascosta) */
.reel-vp{flex:1;min-height:0;width:100%;overflow:auto;scrollbar-width:none}
.reel-vp::-webkit-scrollbar{display:none}
.gbar{height:8px;border-radius:2px;background:rgba(255,255,255,.07);margin:8px 0;overflow:hidden}
.gbar>span{display:block;height:100%;border-radius:2px;transition:width .6s}
.path{font-size:11px;color:var(--mut);word-break:break-all}
.spark{width:100%;height:40px;margin-top:6px;display:block}
.cp.mini{font-size:11px;padding:1px 8px;height:auto}
.cp.warn{background:#ff5a5a22;color:#ff5a5a;border-color:#ff5a5a}
.dupline{display:flex;align-items:center;gap:8px;margin-top:3px}
.keep{font-size:11px;color:#42e39b;border:1px solid #42e39b55;border-radius:2px;padding:1px 8px;white-space:nowrap}
.age{font-size:11px;color:var(--mut);margin-left:10px;letter-spacing:.04em;opacity:.75}
.age.stale{color:#e0975a;opacity:1}
/* cyber */
.cve{font-family:Consolas,monospace;color:var(--cy);font-size:15px;font-weight:700;text-decoration:none;flex:1}
.cve:hover{text-shadow:0 0 10px rgba(124,140,255,.6)}
.b-ransom{color:var(--red);border-color:rgba(255,90,90,.6);box-shadow:0 0 10px rgba(255,90,90,.3)}
.b-date{color:var(--mut);border-color:rgba(120,180,210,.3)}
.action{border-left:2px solid var(--gold);background:rgba(232,181,107,.06);padding-left:11px;font-size:12.5px;color:var(--txt)}
.card.crit{border-color:rgba(255,90,90,.4)}
.card.crit::before,.card.crit::after{border-color:var(--red)}
.b-rel{color:#42e39b;border-color:rgba(66,227,155,.6);box-shadow:0 0 10px rgba(66,227,155,.3)}
.card.mine{border-color:rgba(66,227,155,.5)}
.card.mine::before,.card.mine::after{border-color:#42e39b}
.b-vel{color:var(--gold);border-color:rgba(232,181,107,.6);box-shadow:0 0 8px rgba(232,181,107,.25)}
/* licenza / uso commerciale */
.l-ok{color:var(--green);border-color:rgba(66,227,155,.55)}
.l-cl{color:#e8b56b;border-color:rgba(232,181,107,.55)}
.l-no{color:var(--red);border-color:rgba(255,90,90,.55)}
.l-un{color:var(--mut);border-color:rgba(123,160,181,.45)}
.b-biz{color:var(--green);border-color:rgba(66,227,155,.6);box-shadow:0 0 8px rgba(66,227,155,.22);font-weight:700}
.ghsum{font:600 12.5px var(--tech);letter-spacing:.6px;color:var(--mut);padding:2px 2px 10px;opacity:.9}
.ghsum b{font-weight:700}
.wnote{width:100%;margin-top:8px;background:rgba(124,140,255,.06);border:1px solid var(--line);border-radius:3px;
  color:var(--txt);font:500 13px 'Rajdhani',sans-serif;padding:5px 9px;outline:none}
.wnote:focus{border-color:var(--cy);box-shadow:0 0 8px rgba(124,140,255,.25)}
/* ===== sezione a KPI + tabella compatta (HUD ordinato) ===== */
#grid-gh,#grid-cy,#grid-bc,#grid-pc,#grid-mk,#grid-idee,#grid-disco{display:block;padding:16px 20px 26px}
.discohead{margin-bottom:16px}
.discohead .gbar{height:10px}
.dhrow{display:flex;align-items:center;gap:12px;flex-wrap:wrap;margin:10px 0}
.dhrow .spark{width:200px;height:34px;margin:0}
.dt td.tp{color:var(--cy);font-size:13px;white-space:normal}
.tg.tp2{color:var(--cy);border-color:rgba(124,140,255,.5)}
.tg.au{color:var(--gold);border-color:rgba(232,181,107,.55)}
.tg.rel{color:var(--green);border-color:rgba(66,227,155,.55)}
.tg.rn{color:var(--red);border-color:rgba(255,90,90,.55)}
.tg.fu{color:#b98cff;border-color:rgba(185,140,255,.6)}
.fusebar{display:flex;align-items:center;gap:12px;flex-wrap:wrap;margin-bottom:14px;padding:10px 14px;border:1px solid rgba(185,140,255,.35);border-radius:6px;background:rgba(185,140,255,.06);font:600 13px var(--tech);letter-spacing:.5px;color:var(--mut)}
.fusebar b{color:#b98cff;font-size:16px}
.fusebar .dim{font-family:'Rajdhani',sans-serif;letter-spacing:0}
.idsel{accent-color:#b98cff;width:16px;height:16px;cursor:pointer;vertical-align:middle}
.cp:disabled{opacity:.4;cursor:not-allowed}
.dt tr.dr.mine td.nm{box-shadow:inset 3px 0 var(--green)}
.dt tr.dr.crit td.nm{box-shadow:inset 3px 0 var(--red)}
.mkbanner{margin:0 0 14px;padding:10px 14px;border-left:3px solid #e0975a;background:rgba(255,138,60,.08);border-radius:0 6px 6px 0;color:var(--txt);font-size:13.5px}
.mkbanner b{color:#e0975a;font-family:var(--tech);letter-spacing:1px;margin-right:8px}
.nrow{padding:5px 0;border-bottom:1px solid rgba(124,140,255,.06);font-size:14px;color:var(--txt);line-height:1.5}
.nrow .cve{font-size:14px}
/* ===== griglia di CARD GRANDI (voci leggibili, 2 colonne) ===== */
.gcards{display:grid;grid-template-columns:repeat(auto-fill,minmax(520px,1fr));gap:18px;margin-top:4px}
@media(max-width:1120px){.gcards{grid-template-columns:1fr}}
.gcard{position:relative;border:1px solid var(--line);border-radius:16px;padding:22px 24px;cursor:pointer;overflow:hidden;
  background:var(--glass),rgba(255,255,255,.02);backdrop-filter:blur(16px) saturate(1.15);
  box-shadow:var(--sh),inset 0 1px 0 rgba(255,255,255,.07);
  display:flex;flex-direction:column;gap:14px;transition:border-color .25s,box-shadow .25s,transform .25s;
  animation:materialize .5s ease both}
.gcard::before{content:"";position:absolute;left:0;top:0;bottom:0;width:3px;background:var(--acc,var(--cy));opacity:.55}
.gcard:hover{transform:translateY(-3px);border-color:color-mix(in srgb,var(--acc,var(--cy)) 50%,transparent);
  box-shadow:0 26px 60px -16px rgba(6,8,22,.85),0 0 0 1px color-mix(in srgb,var(--acc,var(--cy)) 22%,transparent),inset 0 1px 0 rgba(255,255,255,.1)}
.gc-h{display:flex;align-items:flex-start;justify-content:space-between;gap:16px}
.gc-t{font:600 21px/1.25 var(--tech);letter-spacing:-.01em;color:#f2f3fb;word-break:break-word;flex:1}
.gc-r{flex:none;font:600 26px/1 var(--tech);color:var(--acc,var(--cy));font-variant-numeric:tabular-nums}
.gc-tags{display:flex;gap:8px;flex-wrap:wrap}
.gc-meta{display:flex;gap:18px;flex-wrap:wrap;align-items:center;color:var(--txt);font-size:15px;font-variant-numeric:tabular-nums}
.gc-meta .v{color:var(--gold);font-weight:600}.gc-meta .dim{color:var(--mut)}
.gc-foot{display:flex;gap:10px;align-items:center;flex-wrap:wrap;margin-top:2px;padding-top:12px;border-top:1px solid var(--line)}
.gc-foot .wt,.gc-foot .fv{margin-left:auto}
.gc-foot .idsel{margin:0}
.gcard .tg{font-size:12px;padding:3px 10px}
.gcard.crit{--acc:var(--red)}
.gcard.mine{--acc:var(--green)}
.gcard.au{--acc:var(--gold)}
.gcard.fu{--acc:#b98cff}
.idpick{display:inline-flex;align-items:center;gap:7px;font-size:13px;color:var(--mut);cursor:pointer;user-select:none}
.idpick input{width:16px;height:16px;accent-color:#b98cff;cursor:pointer}
.kpi{display:flex;gap:12px;flex-wrap:wrap;margin-bottom:18px}
.kc{flex:1;min-width:96px;padding:15px 18px;border:1px solid var(--line);border-radius:12px;
  background:var(--glass),rgba(255,255,255,.02);backdrop-filter:blur(12px);
  box-shadow:inset 0 1px 0 rgba(255,255,255,.06);position:relative;overflow:hidden}
.kc::before{content:"";position:absolute;left:0;top:0;bottom:0;width:3px;background:var(--kc)}
.kc .kn{font:600 28px var(--tech);color:var(--kc);line-height:1;letter-spacing:-.02em}
.kc .kl{font:500 11px var(--tech);letter-spacing:.1em;text-transform:uppercase;color:var(--mut);margin-top:5px}
.dtable{border:1px solid var(--line);border-radius:14px;overflow:hidden;background:var(--glass),rgba(16,18,30,.4);backdrop-filter:blur(14px);box-shadow:var(--sh)}
table.dt{width:100%;border-collapse:collapse;font-size:14px}
.dt thead th{position:sticky;top:0;z-index:3;background:rgba(18,20,32,.9);backdrop-filter:blur(8px);text-align:right;padding:12px 15px;font:600 11px var(--tech);letter-spacing:.08em;text-transform:uppercase;color:var(--mut);border-bottom:1px solid var(--line);white-space:nowrap}
.dt th.l{text-align:left}.dt th.c{text-align:center}
.dt th.so{cursor:pointer;color:var(--cy)}.dt th.so:hover{color:#eef0fb}.dt th .ar{color:var(--gold)}
.dt tbody tr.dr{cursor:pointer;transition:background .12s}
.dt tbody tr.dr:hover{background:rgba(124,140,255,.09)}
.dt td{padding:10px 14px;text-align:right;border-bottom:1px solid rgba(124,140,255,.06);white-space:nowrap}
.dt td.nm{text-align:left;color:#eef0fb;font-weight:600;white-space:normal;min-width:200px}
.dt td.c{text-align:center}.dt td.dim{color:var(--mut)}.dt td.v{color:var(--gold)}
.dt tbody tr:last-child td{border-bottom:none}
.scb{display:inline-block;min-width:26px;padding:2px 6px;border-radius:3px;font-weight:700;font-family:var(--tech)}
.g-hi{color:var(--green)}.g-mid{color:var(--gold)}.g-lo{color:var(--mut)}
.scb.g-hi{background:rgba(66,227,155,.14)}.scb.g-mid{background:rgba(232,181,107,.14)}.scb.g-lo{background:rgba(123,160,181,.12)}
.tg{display:inline-block;padding:2px 8px;border:1px solid;border-radius:3px;font:700 10px var(--tech);letter-spacing:1px}
.tg.nw{color:var(--cy);border-color:var(--cy);margin-left:8px}
.tg.b-nuova{color:var(--cy);border-color:rgba(124,140,255,.5)}.tg.b-tendenza{color:var(--gold);border-color:rgba(232,181,107,.5)}
.wt{background:none;border:none;color:#5a7089;font-size:18px;cursor:pointer;line-height:1;padding:0}.wt.on{color:var(--gold)}.wt:hover{color:var(--gold)}
.thint{color:var(--mut);font:italic 12px Consolas,monospace;padding:9px 4px 0}
/* scheda dettaglio a tutta sezione (clic riga) */
#detail{position:fixed;inset:0;z-index:44;display:none;background:rgba(8,9,18,.72);backdrop-filter:blur(10px);overflow-y:auto}
#detail.on{display:block}
.detail-card{max-width:1080px;margin:44px auto;background:var(--glass),rgba(18,20,32,.72);border:1px solid var(--line);border-radius:18px;box-shadow:0 40px 90px -20px rgba(4,6,16,.85),inset 0 1px 0 rgba(255,255,255,.08);backdrop-filter:blur(24px)}
.detail-body{padding:24px 28px 30px}
.dh{display:flex;justify-content:space-between;align-items:flex-start;gap:16px;border-bottom:1px solid var(--line);padding-bottom:16px}
.dtitle{font:700 26px var(--tech);color:#eef0fb;text-decoration:none;letter-spacing:.5px;word-break:break-word}
.dtitle:hover{color:var(--cy);text-shadow:0 0 14px var(--glow)}
.dtags{display:flex;gap:8px;flex-wrap:wrap;margin-top:10px}
.dx{cursor:pointer;font-size:30px;line-height:1;color:var(--mut)}.dx:hover{color:var(--red)}
.dstats{display:flex;gap:12px;flex-wrap:wrap;padding:18px 0;border-bottom:1px solid var(--line)}
.ds{flex:1;min-width:92px;text-align:center;padding:8px;border:1px solid var(--line);border-radius:6px;background:rgba(124,140,255,.04)}
.ds b{display:block;font:800 22px var(--tech);color:#eef0fb}
.ds span{font:600 10px var(--tech);letter-spacing:1px;text-transform:uppercase;color:var(--mut)}
.dgrid{display:grid;grid-template-columns:1fr 1fr;gap:26px;padding-top:22px}
@media(max-width:820px){.dgrid{grid-template-columns:1fr}}
.dblk{margin-bottom:18px}
.dblk .lbl{display:block;margin-bottom:6px}
.dblk .lbl.gold{color:var(--gold)}
.dblk p{margin:0;color:var(--txt);line-height:1.6;font-size:14.5px}
.wt2{background:transparent;border:1px solid var(--gold);color:var(--gold);border-radius:4px;padding:8px 14px;font:600 12px var(--tech);letter-spacing:1px;text-transform:uppercase;cursor:pointer}
.wt2.on{background:rgba(232,181,107,.14)}
.dblk.map{border:1px solid var(--line);border-radius:8px;padding:16px;background:rgba(232,181,107,.03)}
/* bottone + modale mappa concettuale business */
.mapb{margin-top:9px;background:transparent;color:var(--gold);border:1px solid rgba(232,181,107,.5);
  border-radius:3px;padding:5px 11px;font:600 12px var(--tech);letter-spacing:1px;cursor:pointer;
  text-transform:uppercase;transition:background .15s,box-shadow .15s}
.mapb:hover{background:rgba(232,181,107,.14);box-shadow:0 0 12px rgba(232,181,107,.3)}
#map-modal{position:fixed;inset:0;z-index:40;display:none;place-items:center;
  background:rgba(2,7,13,.72);backdrop-filter:blur(3px)}
#map-modal.on{display:grid}
.map-card{width:min(760px,94vw);max-height:86vh;overflow:auto;background:var(--pane);
  border:1px solid var(--line);border-radius:8px;box-shadow:0 0 44px var(--glow);
  background-image:var(--glass)}
.map-head{display:flex;justify-content:space-between;align-items:center;gap:12px;padding:13px 18px;
  border-bottom:1px solid var(--line);font:600 15px var(--tech);letter-spacing:.6px;color:var(--txt)}
.map-head b{color:var(--gold)}
#map-x{cursor:pointer;font-size:24px;line-height:1;color:var(--mut)}#map-x:hover{color:var(--red)}
.map-body{padding:20px}
.mapwait{color:var(--mut);font-family:Consolas,monospace;text-align:center;padding:26px}
.mapc{margin:0 auto 20px;max-width:340px;text-align:center;padding:14px 18px;border:2px solid var(--gold);
  border-radius:50px;color:var(--gold);font:700 17px var(--tech);letter-spacing:.6px;
  box-shadow:0 0 20px rgba(232,181,107,.28);background:rgba(232,181,107,.06)}
.mapr{display:grid;grid-template-columns:repeat(auto-fit,minmax(210px,1fr));gap:14px}
.mapnode{border:1px solid var(--line);border-left:3px solid var(--cy);border-radius:5px;padding:11px 13px;
  background:rgba(124,140,255,.05)}
.mapnode b{display:block;color:var(--cy);font:600 14px var(--tech);letter-spacing:.5px;margin-bottom:7px}
.mapnode span{display:block;color:var(--txt);font-size:14px;padding:3px 0 3px 14px;position:relative}
.mapnode span::before{content:"\25B8";position:absolute;left:0;color:var(--gold)}
.map-foot{display:flex;align-items:center;gap:10px;padding:12px 18px;border-top:1px solid var(--line);flex-wrap:wrap}
.map-foot button{background:transparent;color:var(--cy);border:1px solid var(--line);border-radius:3px;
  padding:6px 13px;font:600 12px var(--tech);letter-spacing:.8px;text-transform:uppercase;cursor:pointer;transition:background .15s}
.map-foot button:hover{background:rgba(124,140,255,.12);box-shadow:0 0 10px var(--glow)}
#map-deep{color:var(--gold);border-color:rgba(232,181,107,.5)}#map-deep:hover{background:rgba(232,181,107,.12)}
.mapcache{margin-left:auto;color:var(--mut);font-family:Consolas,monospace;font-size:12px}
/* pc */
.chip{align-self:flex-start;font-size:10px;letter-spacing:2px;text-transform:uppercase;padding:3px 10px;border:1px solid var(--cy);color:var(--cy)}
.imp-alto{color:var(--red);border-color:rgba(255,90,90,.6)}.imp-medio{color:var(--gold);border-color:rgba(232,181,107,.6)}.imp-basso{color:var(--cy)}
.tip-t{font-weight:600;color:#eef0fb;font-size:17px}
.fav{position:absolute;top:10px;right:12px;background:none;border:none;color:#5a7089;font-size:22px;cursor:pointer;line-height:1;padding:0}.fav.on{color:var(--gold)}.fav:hover{color:var(--gold)}
.action{border-left:2px solid var(--gold);background:rgba(232,181,107,.06);padding-left:11px;font-size:14px;color:var(--txt);line-height:1.55}
.prof{display:flex;gap:20px;flex-wrap:wrap;padding:6px 18px 2px;color:var(--mut);font-family:Consolas,monospace;font-size:13px;position:relative;z-index:2;flex:none}
.prof b{color:var(--cy);font-weight:400}
/* ===== layout control-room a schermo fisso (no scroll pagina) ===== */
.stage{position:relative;z-index:2;flex:1;min-height:0;display:flex;flex-direction:column;padding:6px 0 0}
.grid3{display:grid;grid-template-columns:238px minmax(0,1fr) 238px;gap:14px;flex:1;min-height:0;padding:6px 16px 8px}
.center{display:flex;flex-direction:column;min-height:0;align-items:stretch;gap:6px}
.hub{width:min(576px,72vh);height:min(576px,72vh);flex:none;align-self:center;animation:hubin 1s ease both;transition:width .55s cubic-bezier(.7,0,.2,1),height .55s cubic-bezier(.7,0,.2,1)}
body.viewing .hub{display:none}
body.viewing header{display:none}
body.viewing .grid3{padding-top:50px}
.hint{align-self:center;color:var(--mut);font:12px/1 Consolas,monospace;letter-spacing:4px;text-transform:uppercase;margin-top:8px;animation:flick 5s infinite}
/* HOME (nessuna sezione): reattore grande, colonne visibili, feed/status nascosti.
   VIEWING (sezione aperta): reattore piccolo, colonne nascoste, sezione a tutto schermo. */
body:not(.viewing) .center{justify-content:center}
.feed,.status,body.viewing .hint{display:none}
body.viewing .feed{display:block}
body.viewing .status{display:flex}
body.viewing .tele{display:none;opacity:0}
body.viewing .grid3{grid-template-columns:minmax(0,1fr)}
@keyframes hubin{from{opacity:0;transform:scale(.85)}to{opacity:1}}
.sector{cursor:pointer}
.sector path{fill:none;stroke:var(--cy);stroke-width:11;opacity:.5;transition:.25s;filter:drop-shadow(0 0 4px rgba(124,140,255,.4))}
.sector:hover path{opacity:1;stroke-width:15;filter:drop-shadow(0 0 12px rgba(124,140,255,.9))}
.sector.act path{stroke:var(--gold);opacity:1;stroke-width:15;filter:drop-shadow(0 0 14px rgba(232,181,107,.9))}
.sector text{fill:var(--cy);font:600 16px/1 "Segoe UI",sans-serif;letter-spacing:3px;text-transform:uppercase;pointer-events:none;transition:.25s}
.sector:hover text,.sector.act text{fill:#eef0fb}
.arc-draw{stroke-dasharray:1;stroke-dashoffset:1;animation:draw 1.2s .3s ease forwards}
@keyframes draw{to{stroke-dashoffset:0}}
.hub .spin{transform-origin:210px 210px;animation:spin 16s linear infinite}
.hub .spin2{transform-origin:210px 210px;animation:spin 10s linear infinite reverse}
.core{cursor:pointer;filter:drop-shadow(0 0 10px rgba(232,181,107,.55)) drop-shadow(0 0 22px rgba(124,140,255,.4))}
.core .pulse{transform-origin:210px 210px;animation:pulse 2.4s ease-in-out infinite}
@keyframes pulse{0%,100%{opacity:.35;transform:scale(1)}50%{opacity:.7;transform:scale(1.12)}}
/* aura cinematografica dietro il reattore + orbita particelle */
.hub{position:relative}
.hub::before{content:"";position:absolute;inset:-8%;z-index:-1;border-radius:50%;pointer-events:none;
  background:radial-gradient(circle,rgba(124,140,255,.22),rgba(232,181,107,.10) 42%,transparent 68%);
  animation:aura 3.6s ease-in-out infinite}
@keyframes aura{0%,100%{opacity:.5;transform:scale(.96)}50%{opacity:1;transform:scale(1.06)}}
body.viewing .hub::before{animation-duration:2.2s}
.hub .orbit{transform-origin:210px 210px;animation:spin 9s linear infinite}
.hub .orbit.rev{animation:spin 14s linear infinite reverse}
.hub .orbit circle{fill:#a2aaff;filter:drop-shadow(0 0 5px #7c8cff)}
.hub .orbit .g{fill:#f0cd9a;filter:drop-shadow(0 0 5px #e8b56b)}
.status{align-items:center;gap:10px;padding:7px 14px;font:600 12px/1 Consolas,monospace;letter-spacing:2px;text-transform:uppercase;color:var(--mut);
  border:1px solid rgba(124,140,255,.15);background:rgba(3,12,20,.45);border-bottom:2px solid var(--acc,var(--cy));transition:border-color .4s}
body.viewing .status{display:flex}
.status .nv{background:none;border:1px solid rgba(124,140,255,.3);color:var(--cy);cursor:pointer;padding:6px 11px;font-size:12px;transition:.15s}
.status .nv:hover{background:rgba(124,140,255,.16);box-shadow:0 0 10px rgba(124,140,255,.25)}
.status .title{flex:1;text-align:center;display:flex;gap:11px;justify-content:center;align-items:baseline}
.status .cur{color:var(--acc,var(--gold));font-size:18px;letter-spacing:4px;text-shadow:0 0 12px currentColor}
.status .cnt{color:var(--mut);font-size:11px}
.status .auto{cursor:pointer;border:1px solid rgba(124,140,255,.35);padding:6px 11px;color:var(--cy);display:flex;gap:7px;align-items:center;user-select:none}
.status .auto:hover{background:rgba(124,140,255,.1)}
.status .auto .d{width:7px;height:7px;border-radius:50%;background:var(--gold);box-shadow:0 0 8px var(--gold);animation:pulse 1.4s infinite}
.status .auto.off{color:var(--mut);border-color:rgba(120,180,210,.25)}
.status .auto.off .d{background:var(--mut);box-shadow:none;animation:none}
.feed{--acc:#7c8cff;flex:1;width:100%;min-height:0;position:relative;overflow:hidden;
  border:1px solid rgba(124,140,255,.12);border-top:none;background:rgba(2,10,17,.35)}
.panel-wrap{width:100%;height:100%}
.motes{position:fixed;inset:0;z-index:1;pointer-events:none;overflow:hidden}
.motes i{position:absolute;bottom:-10px;width:2px;height:2px;background:var(--cy);border-radius:50%;opacity:.5;box-shadow:0 0 6px var(--cy);animation:float linear infinite}
@keyframes float{to{transform:translateY(-105vh)}}
/* ===== pannelli telemetria: colonne fisse ai lati ===== */
.tele{display:flex;flex-direction:column;gap:10px;padding:8px 9px;height:100%;overflow:hidden auto;scrollbar-width:none;
  border:1px solid rgba(124,140,255,.12);background:rgba(3,12,20,.4);animation:hubin 1.2s ease both}
.tele::-webkit-scrollbar{display:none}
.tele .htitle{font:600 12px/1 Consolas,monospace;letter-spacing:3px;color:var(--cy);text-transform:uppercase;border-bottom:1px solid rgba(124,140,255,.22);padding-bottom:7px}
.tele.r{text-align:right}
.ro{display:flex;flex-direction:column;gap:3px}
.ro .k{font:10px/1 Consolas,monospace;letter-spacing:2px;color:var(--mut);text-transform:uppercase}
.ro .v{font:600 18px/1.2 Consolas,monospace;color:var(--cy);text-shadow:0 0 8px rgba(124,140,255,.5);word-break:break-word}
.ro .v small{color:var(--mut);font-weight:400;font-size:12px}
.ro .v.warn{color:var(--gold);text-shadow:0 0 8px rgba(232,181,107,.5)}
.ro .v.hot{color:var(--red);text-shadow:0 0 8px rgba(255,90,90,.5)}
.bar{height:6px;background:rgba(120,180,210,.15);position:relative;overflow:hidden;margin-top:4px}
.bar i{position:absolute;left:0;top:0;bottom:0;width:0;background:linear-gradient(90deg,var(--cy2),var(--cy));box-shadow:0 0 8px var(--cy);transition:width .5s}
.tele.r .bar i{left:auto;right:0}
.bar.hi i{background:linear-gradient(90deg,var(--gold),var(--red))}
.cores{display:flex;gap:3px;align-items:flex-end;height:26px;margin-top:4px;justify-content:flex-end}
.cores b{flex:1;min-width:4px;background:linear-gradient(var(--cy),var(--cy2));box-shadow:0 0 5px rgba(124,140,255,.5);height:8%;transition:height .4s;align-self:flex-end}
.live{display:inline-block;width:7px;height:7px;border-radius:50%;background:var(--gold);box-shadow:0 0 8px var(--gold);animation:pulse 1.6s infinite;margin-left:6px}
.telenote{font:10px/1.4 Consolas,monospace;color:var(--mut);letter-spacing:1px;border-top:1px dashed rgba(124,140,255,.2);padding-top:8px}
.telenote a{color:var(--cy);text-decoration:none}
/* legenda "cosa mostra" per sezione */
.legend{color:#bcdcec;font-size:13.5px;line-height:1.55;margin:10px 18px 2px;padding:10px 16px;position:relative;z-index:2;flex:none;
  border-left:3px solid var(--acc,var(--cy));background:linear-gradient(90deg,color-mix(in srgb,var(--acc,var(--cy)) 9%,transparent),transparent 80%);
  border-radius:0 4px 4px 0}
.legend b{color:var(--acc,var(--cy));font-weight:600;font-family:var(--tech);letter-spacing:.4px}
/* ticker prezzi crypto - barra fissa in basso */
.ticker{position:relative;z-index:3;flex:none;border-top:1px solid rgba(124,140,255,.2);background:rgba(2,12,20,.65);
  overflow:hidden;display:flex;align-items:center}
.ticker .lbl{flex:none;padding:9px 14px;border-right:1px solid rgba(124,140,255,.2);background:rgba(124,140,255,.07);
  font:600 11px/1 Consolas,monospace;letter-spacing:2px;color:var(--cy);text-transform:uppercase;display:flex;align-items:center;gap:7px}
.ticker .track{display:flex;gap:26px;padding:9px 20px;white-space:nowrap;font-family:Consolas,monospace;font-size:14px;
  animation:tick 40s linear infinite}
.ticker:hover .track{animation-play-state:paused}
@keyframes tick{from{transform:translateX(0)}to{transform:translateX(-50%)}}
.ticker .c{display:inline-flex;gap:7px;align-items:baseline}
.ticker .c b{color:#eef0fb;font-weight:700}.ticker .c .p{color:var(--txt)}
.ticker .up{color:#42e39b}.ticker .dn{color:var(--red)}
.b-audit{color:var(--gold);border-color:rgba(232,181,107,.6);box-shadow:0 0 8px rgba(232,181,107,.25)}
/* ===== mini-reattori laterali: report (sx) e chat (dx) affiancano il reattore ===== */
.rfab{position:fixed;top:50%;z-index:20;width:76px;height:76px;border-radius:50%;cursor:pointer;
  border:2px solid var(--rc);color:#eef7ff;font:700 16px/1 var(--tech,'Orbitron'),sans-serif;
  display:grid;place-items:center;transition:transform .2s,box-shadow .2s;
  background:
    radial-gradient(circle at 50% 50%, color-mix(in srgb,var(--rc) 80%,#fff) 0 13%, transparent 15%),
    radial-gradient(circle at 50% 50%, transparent 0 33%, color-mix(in srgb,var(--rc) 55%,transparent) 34% 39%, transparent 41%),
    radial-gradient(circle at 40% 33%, rgba(255,255,255,.16), transparent 55%),
    radial-gradient(circle at 50% 50%, #0a1c28, #05101a);
  box-shadow:0 0 22px var(--rg),inset 0 0 16px rgba(0,0,0,.7),inset 0 0 3px var(--rc)}
.rfab::before{content:"";position:absolute;inset:5px;border-radius:50%;
  border:1.5px dashed color-mix(in srgb,var(--rc) 60%,transparent);animation:spin 9s linear infinite}
.rfab::after{content:"";position:absolute;inset:15px;border-radius:50%;
  border:1px solid color-mix(in srgb,var(--rc) 38%,transparent)}
.rfab>span{position:relative;z-index:1;text-shadow:0 0 7px var(--rc)}
#week-fab{left:calc(50% - min(288px,36vh) - 46px);transform:translate(-50%,-50%);--rc:#b98cff;--rg:rgba(185,140,255,.55)}
#ask-fab{left:calc(50% + min(288px,36vh) + 46px);transform:translate(-50%,-50%);--rc:#e8b56b;--rg:rgba(232,181,107,.55)}
#week-fab:hover,#ask-fab:hover{transform:translate(-50%,-50%) scale(1.09);box-shadow:0 0 36px var(--rg),inset 0 0 16px rgba(0,0,0,.7)}
/* reattore Ollama: al centro, sopra il settore GitHub (in cima all'anello) */
#sync-fab{left:50%;top:calc(50% - min(288px,36vh) - 44px);bottom:auto;transform:translate(-50%,-50%);--rc:#3fd8c0;--rg:rgba(63,216,192,.55)}
#sync-fab:hover{transform:translate(-50%,-50%) scale(1.09);box-shadow:0 0 36px var(--rg),inset 0 0 16px rgba(0,0,0,.7)}
#sync-fab.syncing{pointer-events:none}
#sync-fab.syncing::before{animation-duration:.9s}
#sync-fab.syncing>span{animation:pulse 1s ease-in-out infinite}
@keyframes pulse{50%{opacity:.35}}
#sync-step{position:fixed;left:50%;top:calc(50% - min(288px,36vh) - 98px);transform:translate(-50%,-50%);
  z-index:20;display:none;max-width:min(360px,80vw);padding:5px 12px;border:1px solid rgba(63,216,192,.5);
  border-radius:20px;background:rgba(3,20,26,.85);color:#3fd8c0;font:600 11.5px var(--tech);letter-spacing:.6px;
  white-space:nowrap;overflow:hidden;text-overflow:ellipsis;box-shadow:0 0 14px rgba(63,216,192,.3)}
#sync-step.on{display:block}
body.viewing #sync-step{display:none}
/* health strip (solo home) */
#health{position:fixed;left:50%;bottom:52px;transform:translateX(-50%);z-index:15;display:flex;gap:16px;
  flex-wrap:wrap;justify-content:center;padding:7px 16px;border:1px solid var(--line);border-radius:22px;
  background:rgba(3,16,24,.6);backdrop-filter:blur(4px);font:600 12px var(--tech);letter-spacing:.5px;color:var(--mut)}
#health .hi{display:flex;align-items:center;gap:6px}
#health .dot{width:8px;height:8px;border-radius:50%;background:var(--mut);box-shadow:0 0 6px currentColor}
#health .dot.ok{background:var(--green);color:var(--green)}
#health .dot.no{background:var(--red);color:var(--red)}
#health b{color:var(--txt);font-weight:700}
#health .warn{color:var(--gold)}
body.viewing #health{display:none}
/* i tre mini-reattori esistono SOLO nella schermata principale (hub) */
body.viewing .rfab{display:none}
#week-panel{position:fixed;left:22px;bottom:84px;z-index:20;width:min(460px,92vw);max-height:64vh;display:none;flex-direction:column;
  background:rgba(10,8,20,.97);border:1px solid rgba(185,140,255,.5);border-radius:12px;box-shadow:0 12px 50px rgba(0,0,0,.6);overflow:hidden}
#week-panel.on{display:flex}
#week-panel .wh{display:flex;align-items:center;gap:10px;padding:11px 14px;border-bottom:1px solid rgba(185,140,255,.3);color:#d8c4ff;font-weight:600}
#week-panel .wh .g{flex:1;font-size:12px;color:var(--mut);font-weight:400}
#week-panel .wb{padding:14px 16px;overflow:auto;white-space:pre-wrap;line-height:1.6;font-size:14.5px;color:#e8e0f5}
#week-panel button{background:none;border:1px solid rgba(185,140,255,.5);color:#d8c4ff;border-radius:6px;cursor:pointer;padding:3px 9px;font-size:12px}
#ask-panel{position:fixed;right:22px;bottom:90px;z-index:20;width:min(400px,92vw);height:480px;
  background:rgba(4,14,22,.97);border:1px solid rgba(124,140,255,.35);backdrop-filter:blur(6px);
  display:none;flex-direction:column;box-shadow:0 0 40px rgba(124,140,255,.22)}
#ask-panel.on{display:flex;animation:swoop .35s ease both}
.ask-head{padding:13px 15px;border-bottom:1px solid rgba(124,140,255,.25);color:var(--cy);
  font:600 12px/1 Consolas,monospace;letter-spacing:2px;display:flex;justify-content:space-between;align-items:center}
.ask-head span{cursor:pointer;font-size:22px;color:var(--mut)}
.ask-head span:hover{color:var(--cy)}
.ask-log{flex:1;overflow-y:auto;padding:14px;display:flex;flex-direction:column;gap:10px}
.ask-log .m{font-size:14.5px;line-height:1.55;padding:10px 12px;max-width:88%;white-space:pre-wrap;word-break:break-word}
.ask-log .u{align-self:flex-end;background:rgba(124,140,255,.12);border:1px solid rgba(124,140,255,.3);color:#eef0fb}
.ask-log .j{align-self:flex-start;border-left:2px solid var(--gold);background:rgba(232,181,107,.06);color:var(--txt)}
.ask-log .j.wait{color:var(--mut);font-style:italic}
.ask-in{display:flex;border-top:1px solid rgba(124,140,255,.25)}
.ask-in input{flex:1;border:none;background:rgba(6,20,30,.6);color:var(--txt);padding:13px;font-size:14px;min-width:0}
.ask-in button{border:none;background:rgba(124,140,255,.15);color:var(--cy);padding:0 18px;cursor:pointer;font-size:16px}
.ask-in button:hover{background:rgba(124,140,255,.3)}
/* pulsante 'indietro': torna alla home hub (visibile solo dentro una sezione) */
#home-fab{display:none;position:fixed;top:12px;left:18px;z-index:24;width:auto;height:auto;
  align-items:center;gap:8px;padding:9px 16px 9px 13px;border-radius:22px;cursor:pointer;
  border:1px solid var(--line);color:var(--txt);font:600 13px/1 var(--tech);letter-spacing:.4px;
  background:var(--pane);backdrop-filter:blur(8px);box-shadow:var(--sh);transition:.16s}
#home-fab .bk{font-size:16px;line-height:1;color:var(--cy)}
body.viewing #home-fab{display:inline-flex}
#home-fab:hover{border-color:var(--cy);color:var(--cy);box-shadow:0 0 16px var(--glow)}
/* pulsante accendi/spegni Ollama (sempre visibile) */
#ollama-btn{position:fixed;left:20px;bottom:16px;z-index:22;display:flex;align-items:center;gap:8px;
  padding:8px 14px;border-radius:22px;cursor:pointer;border:1px solid rgba(123,160,181,.4);
  background:rgba(3,16,24,.72);backdrop-filter:blur(4px);color:var(--mut);font:700 12px var(--tech);letter-spacing:1px;
  text-transform:uppercase;transition:.18s}
#ollama-btn .pw{font-size:16px;line-height:1}
#ollama-btn.on{color:var(--green);border-color:rgba(66,227,155,.6);box-shadow:0 0 14px rgba(66,227,155,.25)}
#ollama-btn.off{color:var(--red);border-color:rgba(255,90,90,.55)}
#ollama-btn.busy{opacity:.6;pointer-events:none}
#ollama-btn:hover{background:rgba(6,26,38,.9)}
body:not(.viewing) #ollama-btn{left:20px;bottom:74px}  /* in home non copre la health strip */
</style></head><body>
<div class="radar"></div>
<div class="crt"></div>
<div class="beam"></div>
<div class="fx"></div>
<svg class="hud tr" viewBox="0 0 200 200"><g class="r"><circle cx="100" cy="100" r="94" stroke-dasharray="3 9"/><circle cx="100" cy="100" r="72" stroke-width="2" stroke-dasharray="40 14 8 14"/></g><g class="r2"><circle cx="100" cy="100" r="54" stroke-dasharray="2 12"/></g></svg>
<svg class="hud bl" viewBox="0 0 200 200"><g class="r2"><circle cx="100" cy="100" r="96" stroke-dasharray="2 10"/><circle cx="100" cy="100" r="78" stroke-width="2" stroke-dasharray="30 12 6 12"/></g><g class="r"><circle cx="100" cy="100" r="60" stroke-dasharray="3 9"/></g></svg>
<header>
<svg class="reactor" viewBox="0 0 64 64" fill="none" stroke="#7c8cff">
  <circle cx="32" cy="32" r="5" fill="#f4dcae"/><circle cx="32" cy="32" r="9" fill="#e8b56b" opacity=".35"/>
  <circle cx="32" cy="32" r="9" stroke="#f0cd9a" stroke-width="2"/>
  <g class="rot" stroke-width="1.5" opacity=".9"><circle cx="32" cy="32" r="16" stroke-dasharray="4 6"/><path d="M32 4v8M32 52v8M4 32h8M52 32h8"/></g>
  <g class="rot2" stroke-width="1"><circle cx="32" cy="32" r="22" stroke-dasharray="2 10" opacity=".7"/></g>
  <circle cx="32" cy="32" r="28" stroke-width="1" opacity=".3"/>
</svg>
<div><h1>J.A.R.V.I.S.</h1><div class="sub">SYSTEM <b>ONLINE</b> // sync __UPDATED__</div></div>
<div class="stats">
  <div class="stat"><div class="n" id="s-tot">0</div><div class="l">repo</div></div>
  <div class="stat"><div class="n" id="s-cy">0</div><div class="l">minacce</div></div>
  <div class="stat"><div class="n" id="s-new">0</div><div class="l">new oggi</div></div>
</div>
</header>
<div class="motes" id="motes"></div>
<div class="stage">
<div class="grid3">
<aside class="tele l" id="tele-l"><div class="htitle">// sistema</div></aside>
<div class="center">
<svg class="hub" viewBox="0 0 420 420" fill="none">
  <g class="spin" stroke="#7c8cff" opacity=".4"><circle cx="210" cy="210" r="150" stroke-dasharray="2 14"/></g>
  <g class="spin2" stroke="#7c8cff" opacity=".28"><circle cx="210" cy="210" r="178" stroke-dasharray="1 18"/></g>
  <circle cx="210" cy="210" r="120" stroke="#7c8cff" stroke-width="1" opacity=".15"/>
  <!-- 7 settori -->
  <g class="sector" data-s="github"><path class="arc-draw" pathLength="1" d="M156.9 69.7 A150 150 0 0 1 263.1 69.7"/><text x="210.0" y="82.0" text-anchor="middle">GitHub</text></g>
  <g class="sector" data-s="cyber"><path class="arc-draw" pathLength="1" d="M286.6 81.0 A150 150 0 0 1 352.8 164.0"/><text x="313.2" y="131.7" text-anchor="middle">Cyber</text></g>
  <g class="sector" data-s="blockchain"><path class="arc-draw" pathLength="1" d="M358.6 189.5 A150 150 0 0 1 335.0 292.9"/><text x="338.7" y="243.4" text-anchor="middle">Blockchain</text></g>
  <g class="sector" data-s="pc"><path class="arc-draw" pathLength="1" d="M318.7 313.4 A150 150 0 0 1 223.1 359.4"/><text x="267.3" y="332.9" text-anchor="middle">PC</text></g>
  <g class="sector" data-s="disco"><path class="arc-draw" pathLength="1" d="M196.9 359.4 A150 150 0 0 1 101.3 313.4"/><text x="152.7" y="332.9" text-anchor="middle">Disco</text></g>
  <g class="sector" data-s="mercato"><path class="arc-draw" pathLength="1" d="M85.0 292.9 A150 150 0 0 1 61.4 189.5"/><text x="81.3" y="243.4" text-anchor="middle">Mercato</text></g>
  <g class="sector" data-s="idee"><path class="arc-draw" pathLength="1" d="M67.2 164.0 A150 150 0 0 1 133.4 81.0"/><text x="106.8" y="131.7" text-anchor="middle">Idee</text></g>
  <!-- reattore tech: esagono + esagramma coil + core -->
  <g class="core" data-core="1">
    <g class="spin"><circle cx="210" cy="210" r="66" stroke="#7c8cff" stroke-width="1" stroke-dasharray="1 7" opacity=".7"/></g>
    <g class="spin"><g opacity=".6" stroke="#7c8cff" stroke-width="3">
      <path d="M210 152 l4 0"/><path d="M260 181 l3 2"/><path d="M260 239 l3 -2"/><path d="M210 268 l4 0"/><path d="M160 239 l-3 -2"/><path d="M160 181 l-3 2"/></g></g>
    <g class="spin2"><polygon points="210,148 263.7,179 263.7,241 210,272 156.3,241 156.3,179" stroke="#7c8cff" stroke-width="1.5" fill="none" opacity=".85"/></g>
    <polygon points="210,164 249.8,187 249.8,233 210,256 170.2,233 170.2,187" stroke="#f0cd9a" stroke-width="2" fill="rgba(232,181,107,.06)"/>
    <g class="spin">
      <polygon points="210,182 234.2,224 185.8,224" stroke="#7c8cff" stroke-width="1.5" fill="none" opacity=".9"/>
      <polygon points="210,238 185.8,196 234.2,196" stroke="#7c8cff" stroke-width="1.5" fill="none" opacity=".9"/>
    </g>
    <circle class="pulse" cx="210" cy="210" r="16" fill="#e8b56b"/>
    <circle cx="210" cy="210" r="16" stroke="#f4dcae" stroke-width="2"/>
    <circle cx="210" cy="210" r="7" fill="#fff7e0"/>
  </g>
  <g class="orbit"><circle cx="406" cy="210" r="3.4"/><circle cx="112" cy="379.7" r="3.4"/><circle cx="112" cy="40.3" r="3.4"/></g>
  <g class="orbit rev"><circle class="g" cx="301" cy="367.6" r="3"/><circle class="g" cx="28" cy="210" r="3"/><circle class="g" cx="301" cy="52.4" r="3"/></g>
</svg>
<div class="hint">// seleziona un settore o avvia AUTO dal reattore //</div>
<div class="status">
  <button class="nv" id="prev-sec" title="settore precedente">&#9664;</button>
  <div class="title"><span class="cur" id="cur-sec">--</span><span class="cnt" id="sec-cnt"></span><span class="age" id="sec-age"></span></div>
  <button class="nv" id="next-sec" title="settore successivo">&#9654;</button>
  <div class="auto" id="auto-btn" title="rotazione automatica"><span class="d"></span><span id="auto-lbl">AUTO</span></div>
</div>
<div class="feed">
<div class="panel-wrap">
<section id="sec-github">
<div class="legend"><b>Cosa mostra:</b> repository appena uscite o di tendenza su GitHub, filtrate per i tuoi interessi. In ogni scheda il <b>gauge 0-10</b> e la rilevanza stimata dall'AI; il tasto <b>ANALISI</b> dice se la repo gira sul tuo PC e fornisce i comandi di installazione.</div>
<div class="controls">
<div class="fld"><label>ricerca</label><input id="q" placeholder="nome / parola chiave..."></div>
<div class="fld"><label>categoria</label><select id="cat"><option value="">tutte</option><option value="nuova">nuove uscite</option><option value="tendenza">tendenza</option></select></div>
<div class="fld"><label>linguaggio</label><select id="lang"></select></div>
<div class="fld"><label>periodo (aggiornata)</label><select id="per"><option value="">sempre</option><option value="1">ultime 24h</option><option value="3">ultimi 3 giorni</option><option value="7">ultima settimana</option><option value="30">ultimo mese</option></select></div>
<div class="fld"><label>ordina</label><select id="sort"><option value="score">rilevanza</option><option value="biz">business (monetizzabilita)</option><option value="recent">piu recenti</option><option value="vel">velocita (trending)</option><option value="stars">stelle</option></select></div>
<div class="fld"><label>uso commerciale</label><select id="ghlic"><option value="">qualsiasi licenza</option><option value="ok">commerciale OK</option><option value="copyleft">copyleft (con obblighi)</option><option value="no">no / senza licenza</option></select></div>
<div class="fld"><label>mostra</label><select id="ghshow"><option value="">tutte</option><option value="save">solo salvati &#9733;</option></select></div>
<div class="fld"><label>cerca live su GitHub</label><input id="ghlive" placeholder="scrivi e premi Invio..."></div>
</div>
<div id="gh-live-bar" style="display:none"></div>
<div id="gh-sum" class="ghsum"></div>
<div class="reel-vp"><main id="grid-gh"></main></div>
</section>

<section id="sec-cyber">
<div class="legend"><b>Cosa mostra:</b> vulnerabilita sfruttate <b>attivamente ora</b> dagli attaccanti (catalogo CISA KEV). Per ognuna: cosa colpisce, se e usata da ransomware, e l'<b>azione difensiva</b> da applicare. Le falle che colpiscono software presente sul <b>tuo</b> PC hanno il badge <span style="color:#42e39b">TI RIGUARDA</span> e finiscono in cima.</div>
<div class="controls">
<div class="fld"><label>threat intel</label><select id="cyf"><option value="">tutte le minacce</option><option value="rel">rilevanti per il tuo PC</option><option value="ransom">solo ransomware</option></select></div>
<div class="fld"><label>periodo (aggiunta CISA)</label><select id="cyper"><option value="">sempre</option><option value="3">ultimi 3 giorni</option><option value="7">ultima settimana</option><option value="30">ultimo mese</option></select></div>
<div class="fld"><label>fonte</label><input value="CISA KEV - sfruttate in the wild" disabled style="min-width:240px;opacity:.7"></div>
</div>
<div class="reel-vp"><main id="grid-cy"></main></div>
</section>

<section id="sec-pc">
<div class="legend"><b>Cosa mostra:</b> consigli su misura generati sul <b>tuo hardware reale</b> per rendere il PC piu veloce ed efficiente. Il badge <b>impatto</b> stima quanto incide ogni intervento. Sono suggerimenti sicuri: valutali prima di applicarli.</div>
<div class="prof" id="prof"></div>
<div class="reel-vp"><main id="grid-pc"></main></div>
</section>

<section id="sec-blockchain">
<div class="legend"><b>Cosa mostra:</b> progetti blockchain/web3/smart-contract (Solidity) di tendenza su GitHub e i <b>tool di audit e sicurezza</b> per smart-contract (badge <span style="color:var(--gold)">SICUREZZA</span>). I prezzi crypto live scorrono nella barra in basso. I tag indicano l'ambito, le stelle la popolarita.</div>
<div class="controls">
<div class="fld"><label>ricerca</label><input id="bcq" placeholder="nome / topic..."></div>
<div class="fld"><label>tipo</label><select id="bcf"><option value="">tutti i progetti</option><option value="proj">solo blockchain/web3</option><option value="audit">solo audit & sicurezza</option></select></div>
</div>
<div class="reel-vp"><main id="grid-bc"></main></div>
</section>

<section id="sec-disco">
<div class="legend"><b>Cosa mostra:</b> lo stato del disco e come liberarlo. <b>Cache svuotabili</b> (dati rigenerabili, zero perdita) con il comando pronto da copiare, <b>file grossi e dimenticati</b> (grandi e non toccati da mesi) e le <b>cartelle piu pesanti</b>. Jarvis non cancella nulla da solo: copi il comando e lo lanci tu. Soglie in <b>config.yaml</b> (disco_big_mb, disco_cold_days).</div>
<div class="reel-vp"><main id="grid-disco"></main></div>
</section>

<section id="sec-mercato">
<div class="legend"><b>Cosa mostra:</b> eventi reali che possono muovere i mercati, per settore (medico, geopolitica, automotive, energia, tech, macro). Titoli live da Google News. Questi segnali <b>alimentano la sezione Idee</b>: le startup proposte nascono da qui. I topic si cambiano in <b>config.yaml</b> (mercato_topics).</div>
<div class="controls">
<div class="fld"><label>settore</label><select id="mkf"><option value="">tutti i settori</option></select></div>
</div>
<div class="reel-vp"><main id="grid-mk"></main></div>
</section>

<section id="sec-idee">
<div class="controls">
<div class="fld"><label>filtro</label><select id="idf"><option value="">tutte le idee</option><option value="fav">solo preferite &#9733;</option></select></div>
<div class="fld"><label>&nbsp;</label><button id="dossier-btn" class="cp" style="height:34px">&#8595; esporta dossier</button></div>
</div>
<div class="legend">Idee generate incrociando trend GitHub + minacce cyber + <b>eventi di mercato</b> (medico, geopolitica, automotive, energia, tech, macro). Ogni idea ha <b>mercato stimato</b>, <b>fattibilita</b> sul tuo profilo e <b>primi passi</b>. Clicca la <b>stella</b> per salvarla. La novita e stimata dal modello ma ora <b>verificata sul web</b> (DuckDuckGo): sotto ogni idea trovi <b>concorrenti e riferimenti reali</b>. Se compaiono progetti simili, il mercato e gia presidiato.</div>
<div class="reel-vp"><main id="grid-idee"></main></div>
</section>
</div>
</div>
</div>
<aside class="tele r" id="tele-r"><div class="htitle">telemetria <span class="live"></span></div></aside>
</div>
</div>
<div class="ticker"><div class="track" id="crypto-track"></div></div>

<button id="home-fab" title="Torna alla home"><span class="bk">&#8592;</span><span>Indietro</span></button>
<button id="ollama-btn" class="off" title="Accendi/spegni Ollama"><span class="pw">&#9211;</span><span id="ollama-lbl">Ollama</span></button>
<button id="week-fab" class="rfab" title="Report settimanale"><span>7g</span></button>
<div id="week-panel"><div class="wh"><span>Report settimanale</span><span class="g" id="week-when"></span><button id="week-dl">scarica</button><button id="week-x">chiudi</button></div><div class="wb" id="week-body"></div></div>
<button id="sync-fab" class="rfab" title="Acquisisci le conoscenze di oggi"><span>&#8635;</span></button>
<div id="sync-step" class="syncstep"></div>
<div id="health"></div>
<button id="ask-fab" class="rfab" title="Chiedi a Jarvis"><span>J</span></button>
<div id="ask-panel">
  <div class="ask-head">CHIEDI A J.A.R.V.I.S.<span id="ask-x">&times;</span></div>
  <div class="ask-log" id="ask-log"></div>
  <div class="ask-in"><input id="ask-q" placeholder="chiedi sui dati di oggi..."><button id="ask-send">&#9654;</button></div>
</div>
<div id="detail"><div class="detail-card"><div class="detail-body" id="detail-body"></div></div></div>
<div id="map-modal"><div class="map-card"><div class="map-head"><span>Mappa business &middot; <b id="map-title"></b></span><span id="map-x">&times;</span></div><div class="map-body" id="map-body"></div><div class="map-foot"><button id="map-deep" title="rigenera col modello forte">analisi profonda</button><button id="map-regen" title="rigenera da zero">rigenera</button><button id="map-md" title="scarica in markdown">scarica .md</button><span id="map-cache" class="mapcache"></span></div></div></div>

<script>
const P=__PAYLOAD__;
function esc(s){return (s||'').replace(/[&<>]/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;'}[c]))}
function escA(s){return esc(s).replace(/"/g,'&quot;')}
const mapBtn=(t,c)=>`<button class="mapb" data-t="${escA(t)}" data-c="${escA(c)}" title="mappa: come farci un business proprio">&#9671; mappa business</button>`;
/* ===== mappa concettuale business (on-demand via Ollama, cache lato server) ===== */
let MAP={title:'',ctx:'',data:null};
function renderMap(){
  const d=MAP.data;
  document.getElementById('map-body').innerHTML='<div class="mapc">'+esc(d.centro||MAP.title)+'</div><div class="mapr">'+
    d.rami.map(r=>`<div class="mapnode"><b>${esc(r.nome)}</b>${(r.punti||[]).map(p=>`<span>${esc(p)}</span>`).join('')}</div>`).join('')+'</div>';
}
async function fetchMap(deep,regen){
  const body=document.getElementById('map-body');
  body.innerHTML='<div class="mapwait">genero la mappa... ('+(deep?'modello forte, piu lento':'veloce')+')</div>';
  document.getElementById('map-cache').textContent='';
  try{
    const r=await fetch('/mappa',{method:'POST',headers:{'Content-Type':'application/json'},
      body:JSON.stringify({title:MAP.title,ctx:MAP.ctx,deep:!!deep,regen:!!regen})});
    const d=await r.json();
    if(d.error||!d.rami){body.innerHTML='<div class="empty">// '+esc(d.error||'nessuna mappa')+' //</div>';return}
    MAP.data=d;renderMap();
    document.getElementById('map-cache').textContent=d.cached?'da cache (rigenera per aggiornare)':(d.deep?'modello forte':'modello veloce');
  }catch(e){body.innerHTML='<div class="empty">// errore: server non raggiungibile //</div>'}
}
function mapMd(){
  const d=MAP.data;if(!d)return;
  const md='# '+(d.centro||MAP.title)+'\n\n'+d.rami.map(r=>'## '+r.nome+'\n'+(r.punti||[]).map(p=>'- '+p).join('\n')).join('\n\n')+'\n';
  const b=new Blob([md],{type:'text/markdown'}),a=document.createElement('a');
  a.href=URL.createObjectURL(b);a.download='mappa-'+(MAP.title||'business').replace(/[^a-z0-9]+/gi,'_').slice(0,40)+'.md';a.click();URL.revokeObjectURL(a.href);
}
function openMap(title,ctx){
  MAP={title,ctx,data:null};
  document.getElementById('map-modal').classList.add('on');
  document.getElementById('map-title').textContent=title;
  document.getElementById('map-cache').textContent='';
  if(!(location.protocol==='http:'||location.protocol==='https:')){
    document.getElementById('map-body').innerHTML='<div class="empty">// serve il server locale attivo: python server.py //</div>';return}
  fetchMap(false,false);
}
document.addEventListener('click',e=>{
  const b=e.target.closest('.mapb');if(b){openMap(b.dataset.t,b.dataset.c);return}
  if(e.target.id==='map-deep'){fetchMap(true,false);return}
  if(e.target.id==='map-regen'){fetchMap(!!(MAP.data&&MAP.data.deep),true);return}
  if(e.target.id==='map-md'){mapMd();return}
  if(e.target.id==='map-x'||e.target.id==='map-modal')document.getElementById('map-modal').classList.remove('on');
});
function gcls(s){return s>=7?'g-hi':s>=4?'g-mid':'g-lo'}
function dly(i){return `animation-delay:${Math.min(i*40,600)}ms`}
/* ===== GITHUB ===== */
const DATA=P.github||[];
const langs=[...new Set(DATA.map(d=>d.language).filter(Boolean))].sort();
document.getElementById('lang').innerHTML='<option value="">tutti</option>'+langs.map(l=>`<option>${l}</option>`).join('');
const VCOL={si:'var(--cy)',parziale:'var(--gold)',no:'var(--red)','?':'var(--mut)'};
const VTXT={si:'GIRA SUL TUO PC',parziale:'PARZIALE / LIMITI',no:'NON COMPATIBILE','?':'NON ANALIZZATA'};
function compatHtml(v){
  if(!v)return'';
  const c=v.compat||'?',col=VCOL[c]||VCOL['?'];
  const cmds=(v.comandi||[]).map(x=>`<div>${esc(x)}</div>`).join('');
  return `<button class="cbtn" onclick="this.parentNode.classList.toggle('open')">
    <span class="dot" style="color:${col}"></span>
    <span class="v-${c}">${VTXT[c]||''}</span><span class="arw">&#9656;</span></button>
    <div class="compat">
      <div><span class="lbl">verdetto</span><br><span class="v-${c}" style="font-weight:700">${c.toUpperCase()}</span> &mdash; ${esc(v.motivo)}</div>
      ${v.requisiti?`<div><span class="lbl">requisiti</span><br>${esc(v.requisiti)}</div>`:''}
      ${cmds?`<div><span class="lbl">installazione (powershell)</span>
        <div class="cmds">${cmds}</div>
        <button class="cp" onclick="navigator.clipboard.writeText(${JSON.stringify((v.comandi||[]).join('\n'))});this.textContent='copiato'">copia comandi</button></div>`:''}
      ${v.note?`<div class="note">! ${esc(v.note)}</div>`:''}
    </div>`;
}
function daysAgo(n){const d=new Date();d.setDate(d.getDate()-n);return d.toISOString().slice(0,10);}
// licenza -> uso commerciale proprio. Permissiva=OK, copyleft=ok ma con obblighi, assente=no.
const LIC_OK=['MIT','APACHE-2.0','BSD-2-CLAUSE','BSD-3-CLAUSE','ISC','UNLICENSE','0BSD','MPL-2.0','CC0-1.0','ZLIB','BSL-1.0','WTFPL','POSTGRESQL','ECL-2.0'];
const LIC_CL=['GPL-2.0','GPL-3.0','AGPL-3.0','LGPL-2.1','LGPL-3.0','EPL-2.0','EUPL-1.2','OSL-3.0'];
function licInfo(spdx){
  const s=(spdx||'').toUpperCase();
  if(!s||s==='NOASSERTION')return{use:'no',cls:'l-no',txt:'nessuna licenza: tutti i diritti riservati, non riutilizzabile'};
  if(LIC_OK.includes(s))return{use:'ok',cls:'l-ok',txt:s+': uso commerciale libero'};
  if(LIC_CL.includes(s))return{use:'copyleft',cls:'l-cl',txt:s+': commerciale SI ma copyleft (devi rilasciare le modifiche)'};
  return{use:'?',cls:'l-un',txt:s+': verifica i termini prima di usarla'};
}
// dominio/tipo: usa quello dell'AI, altrimenti indovina dai termini (finche non ri-ranki)
const TYPE_KW=[['computer vision',['opencv','image ','vision','segmentation','detection','yolo','ocr','face']],
  ['LLM / NLP',['llm','gpt','language model','nlp','transformer','chatbot','rag','prompt','embedding']],
  ['machine learning',['machine learning','ml ','pytorch','tensorflow','neural','training','dataset','model']],
  ['cybersecurity',['security','exploit','vulnerab','malware','pentest','cve','ransomware','forensic']],
  ['blockchain / web3',['blockchain','web3','ethereum','solidity','smart contract','crypto','defi','wallet']],
  ['web / frontend',['react','vue','svelte','frontend','css','tailwind','next.js','ui component']],
  ['backend / API',['api','fastapi','backend','server','microservice','graphql','rest','nestjs']],
  ['devtools',['cli','devtool','build','compiler','lint','debug','framework','sdk','plugin']],
  ['data engineering',['data','etl','sql','database','analytics','pipeline','warehouse','spark']],
  ['robotica',['robot','ros ','drone','embedded','iot','arduino','firmware']],
  ['medicina / health',['medical','health','clinic','patient','bio','genom','diagnos']],
  ['fintech',['fintech','payment','trading','finance','bank','invoice','accounting']],
  ['gaming',['game','godot','unity','unreal','engine 3d']],
  ['mobile',['android','ios','flutter','react native','mobile app']]];
function guessType(d){
  const t=((d.full_name||'')+' '+(d.description||'')).toLowerCase();
  for(const[name,kw]of TYPE_KW)if(kw.some(k=>t.includes(k)))return name;
  return d.language||'altro';
}
const typeOf=d=>d.tipo||guessType(d);
let WATCH=JSON.parse(localStorage.getItem('jarvis_watch')||'{}');
function saveWatch(){localStorage.setItem('jarvis_watch',JSON.stringify(WATCH))}
function toggleWatch(t){if(WATCH[t]!==undefined)delete WATCH[t];else WATCH[t]='';saveWatch();renderGh();}
let ghRows=[];
const GH_SMAP={score:'score',biz:'biz',stars:'stars',vel:'vel',updated:'recent'};
function renderGh(){
  const q=document.getElementById('q').value.toLowerCase();
  const cat=document.getElementById('cat').value, lang=document.getElementById('lang').value;
  const sort=document.getElementById('sort').value, per=document.getElementById('per').value;
  const lic=document.getElementById('ghlic').value, show=document.getElementById('ghshow').value;
  const lim=per?daysAgo(+per):'';
  let rows=DATA.filter(d=>(!cat||d.category===cat)&&(!lang||d.language===lang)&&
    (!lim||(d.pushed&&d.pushed>=lim))&&(!lic||licInfo(d.license).use===lic)&&
    (!show||WATCH[d.full_name]!==undefined)&&
    (!q||d.full_name.toLowerCase().includes(q)||(d.description||'').toLowerCase().includes(q)));
  rows.sort((a,b)=>sort==='stars'?b.stars-a.stars:sort==='biz'?((b.biz||0)-(a.biz||0)||b.score-a.score):sort==='recent'?((b.pushed||'').localeCompare(a.pushed||'')||b.score-a.score):sort==='vel'?((b.vel||0)-(a.vel||0)||b.stars-a.stars):(b.score-a.score||b.stars-a.stars));
  ghRows=rows;
  const cnt={ok:0,copyleft:0,no:0,'?':0};rows.forEach(d=>cnt[licInfo(d.license).use]++);
  const kpis=[['repo',rows.length,''],['new oggi',rows.filter(d=>d.new_today).length,'var(--cy)'],
    ['comm OK',cnt.ok,'var(--green)'],['copyleft',cnt.copyleft,'#e8b56b'],['no licenza',cnt.no,'var(--red)']];
  const kpiH=`<div class="kpi">${kpis.map(k=>`<div class="kc" style="--kc:${k[2]||'var(--txt)'}"><div class="kn">${k[1]}</div><div class="kl">${k[0]}</div></div>`).join('')}</div>`;
  const cards=rows.map((d,i)=>{const li=licInfo(d.license),wOn=WATCH[d.full_name]!==undefined;
    const luse=li.use==='ok'?'COMM OK':li.use==='copyleft'?'COPYLEFT':li.use==='no'?'NO LICENZA':'LIC ?';
    return bigCard({i,cls:d.new_today?'nw':'',
      title:esc(d.full_name)+(d.new_today?'<span class="tg nw">NEW</span>':''),
      right:`<span class="scb ${gcls(d.score)}">${d.score}</span>`,
      tags:`<span class="tg tp2">${esc(typeOf(d))}</span><span class="tg b-${d.category}">${esc(d.category)}</span>`,
      meta:`<span>&#9733; ${d.stars.toLocaleString()}</span>`+(d.vel?`<span class="v">&#9650; ${d.vel}/g</span>`:'')+(d.biz?`<span>business ${d.biz}/10</span>`:'')+`<span class="dim">agg. ${esc(d.pushed)||'-'}</span>`,
      foot:`<span class="tg ${li.cls}" title="${esc(li.txt)}">${luse}</span><button class="wt${wOn?' on':''}" data-w="${escA(d.full_name)}" title="salva">${wOn?'★':'☆'}</button>`});
  }).join('');
  document.getElementById('grid-gh').innerHTML=kpiH+cardsHTML(cards,'clic su una card per la scheda completa + mappa business');
}
['q','cat','lang','sort','per','ghlic','ghshow'].forEach(id=>document.getElementById(id).addEventListener('input',renderGh));
// salva la nota della watchlist mentre scrivi (event delegation, non blocca)
document.addEventListener('input',e=>{const w=e.target.closest?.('.wnote');if(w){WATCH[w.dataset.w]=w.value;saveWatch();}});
// tabella GitHub: ordina da header, salva watch, apri scheda dettaglio
document.getElementById('grid-gh').addEventListener('click',e=>{
  const wt=e.target.closest('.wt');if(wt){e.stopPropagation();toggleWatch(wt.dataset.w);return;}
  const c=e.target.closest('.gcard');if(c)openDetailGh(+c.dataset.i);
});
async function detailMap(box,title,ctx){
  if(!(location.protocol==='http:'||location.protocol==='https:')){box.innerHTML='<div class="empty">// avvia il server per la mappa: python server.py //</div>';return}
  box.innerHTML='<div class="mapwait">genero la mappa business... (Ollama)</div>';
  try{
    const d=await(await fetch('/mappa',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({title,ctx})})).json();
    if(d.error||!d.rami){box.innerHTML='<div class="empty">// '+esc(d.error||'nessuna mappa')+' &middot; accendi Ollama //</div>';return}
    box.innerHTML='<div class="mapc">'+esc(d.centro||title)+'</div><div class="mapr">'+
      d.rami.map(r=>`<div class="mapnode"><b>${esc(r.nome)}</b>${(r.punti||[]).map(p=>`<span>${esc(p)}</span>`).join('')}</div>`).join('')+'</div>'+
      (d.cached?'<div class="mapcache" style="margin-top:8px">da cache</div>':'');
  }catch(e){box.innerHTML='<div class="empty">// server non raggiungibile //</div>'}
}
function openDetailGh(i){
  const d=ghRows[i];if(!d)return;
  const li=licInfo(d.license),wOn=WATCH[d.full_name]!==undefined;
  const st=(v,l)=>`<div class="ds"><b>${v}</b><span>${l}</span></div>`;
  document.getElementById('detail-body').innerHTML=`
    <div class="dh">
      <div><a class="dtitle" href="${d.url}" target="_blank">${esc(d.full_name)}</a>
      <div class="dtags"><span class="tg tp2">${esc(typeOf(d))}</span>${d.new_today?'<span class="tg nw">NEW</span>':''}<span class="tg b-${d.category}">${esc(d.category)}</span><span class="tg ${li.cls}">${li.use==='ok'?'COMM OK':li.use==='copyleft'?'COPYLEFT':li.use==='no'?'NO LICENZA':'LIC ?'}</span></div></div>
      <span class="dx" id="detail-x">&times;</span>
    </div>
    <div class="dstats">${st('<span class="'+gcls(d.score)+'">'+d.score+'</span>','rilevanza')}${st(d.biz||'-','business')}${st(d.stars.toLocaleString(),'stelle')}${st(d.vel?('&#9650;'+d.vel+'/g'):'-','trend')}${st(esc(d.language)||'-','linguaggio')}${st(esc(d.pushed)||'-','aggiornata')}</div>
    <div class="dgrid">
      <div class="dcol">
        ${d.description?`<div class="dblk"><span class="lbl">cosa fa</span><p>${esc(d.description)}</p></div>`:''}
        ${d.reason?`<div class="dblk"><span class="lbl">perche puo interessarti</span><p>${esc(d.reason)}</p></div>`:''}
        <div class="dblk"><span class="lbl">licenza / uso commerciale</span><p>${esc(li.txt)}</p></div>
        ${d.verdict?`<div class="dblk"><span class="lbl">compatibilita col tuo PC</span>${compatHtml(d.verdict)}</div>`:''}
        <div class="dblk"><button class="wt2${wOn?' on':''}" data-w="${escA(d.full_name)}">${wOn?'★ salvato':'☆ salva in watchlist'}</button>${wOn?`<input class="wnote" data-w="${escA(d.full_name)}" value="${escA(WATCH[d.full_name]||'')}" placeholder="nota personale...">`:''}</div>
      </div>
      <div class="dcol">
        <div class="dblk map"><span class="lbl gold">come farci un business</span><div id="detail-map"></div></div>
      </div>
    </div>`;
  document.getElementById('detail').classList.add('on');
  detailMap(document.getElementById('detail-map'),d.full_name,(d.description||'')+' '+(d.reason||''));
}
document.addEventListener('click',e=>{
  if(e.target.id==='detail-x'||e.target.id==='detail'){document.getElementById('detail').classList.remove('on');return}
  const w2=e.target.closest('.wt2');if(w2){const t=w2.dataset.w;if(WATCH[t]!==undefined)delete WATCH[t];else WATCH[t]='';saveWatch();
    w2.classList.toggle('on');w2.textContent=WATCH[t]!==undefined?'★ salvato':'☆ salva in watchlist';}
});
/* ===== engine generico: KPI + tabella + scheda dettaglio per tutte le sezioni ===== */
function kpiHTML(kpis){return `<div class="kpi">${kpis.map(k=>`<div class="kc" style="--kc:${k[2]||'var(--txt)'}"><div class="kn">${k[1]}</div><div class="kl">${esc(k[0])}</div></div>`).join('')}</div>`;}
function tableHTML(headers,body,hint){return body?`<div class="dtable"><table class="dt"><thead><tr>${headers}</tr></thead><tbody>${body}</tbody></table></div>${hint?`<div class="thint">${esc(hint)}</div>`:''}`:'<div class="empty">// nessun dato con questi filtri //</div>';}
/* card GRANDE (voce leggibile) - title/right/tags/meta/foot sono HTML RAW (il chiamante fa esc) */
function bigCard(o){return `<div class="gcard ${o.cls||''}" data-i="${o.i}" style="${dly(o.i)}">
  <div class="gc-h"><div class="gc-t">${o.title}</div>${o.right!=null&&o.right!==''?`<div class="gc-r">${o.right}</div>`:''}</div>
  ${o.tags?`<div class="gc-tags">${o.tags}</div>`:''}
  ${o.meta?`<div class="gc-meta">${o.meta}</div>`:''}
  ${o.foot?`<div class="gc-foot">${o.foot}</div>`:''}
</div>`;}
function cardsHTML(cards,hint){return cards?`<div class="gcards">${cards}</div>${hint?`<div class="thint">${esc(hint)}</div>`:''}`:'<div class="empty">// nessun dato con questi filtri //</div>';}
function detailView(o){
  const stats=(o.stats||[]).map(s=>`<div class="ds"><b>${s[0]}</b><span>${esc(s[1])}</span></div>`).join('');
  const tags=(o.tags||[]).filter(Boolean).map(t=>`<span class="tg ${t.cls||''}">${esc(t.txt)}</span>`).join('');
  const blocks=(o.blocks||[]).filter(Boolean).map(b=>`<div class="dblk"><span class="lbl ${b.gold?'gold':''}">${esc(b.lbl)}</span>${b.html}</div>`).join('');
  const mapBlk=o.map?`<div class="dblk map"><span class="lbl gold">come farci un business</span><div id="detail-map"></div></div>`:'';
  document.getElementById('detail-body').innerHTML=
    `<div class="dh"><div>${o.url?`<a class="dtitle" href="${o.url}" target="_blank">${esc(o.title)}</a>`:`<span class="dtitle">${esc(o.title)}</span>`}<div class="dtags">${tags}</div></div><span class="dx" id="detail-x">&times;</span></div>`+
    (stats?`<div class="dstats">${stats}</div>`:'')+
    `<div class="dgrid"><div class="dcol">${blocks}</div><div class="dcol">${mapBlk}</div></div>`;
  document.getElementById('detail').classList.add('on');
  if(o.map)detailMap(document.getElementById('detail-map'),o.map.title,o.map.ctx);
}
function bindGrid(id,opener){const g=document.getElementById(id);if(!g)return;g.addEventListener('click',e=>{const c=e.target.closest('.gcard');if(c)opener(+c.dataset.i,e);});}
const th0=(l,cl)=>`<th class="${cl||''}">${l}</th>`;
/* ricerca live GitHub on-demand (solo con server) */
(function(){
  const inp=document.getElementById('ghlive'),bar=document.getElementById('gh-live-bar'),grid=document.getElementById('grid-gh');
  const LIVE=location.protocol==='http:'||location.protocol==='https:';
  if(!inp)return;
  if(!LIVE){inp.placeholder='avvia server.py per la ricerca live';inp.disabled=true;return;}
  function reset(){bar.style.display='none';renderGh();}
  inp.addEventListener('keydown',async e=>{
    if(e.key!=='Enter')return;const q=inp.value.trim();if(!q){reset();return;}
    bar.style.display='block';bar.innerHTML='// cerco "'+esc(q)+'" su GitHub... //';
    try{
      const r=await fetch('/search?q='+encodeURIComponent(q),{cache:'no-store'});const res=await r.json();
      if(res.error||!res.length){bar.innerHTML='// nessun risultato per "'+esc(q)+'" '+(res.error?'('+esc(res.error)+')':'')+' &middot; <a href="#" onclick="return false" id="ghreset">torna a oggi</a> //';document.getElementById('ghreset').onclick=()=>{inp.value='';reset();return false};grid.innerHTML='';return;}
      bar.innerHTML='// '+res.length+' risultati live per "'+esc(q)+'" &middot; <a href="#" id="ghreset">torna ai segnali di oggi</a> //';
      document.getElementById('ghreset').onclick=()=>{inp.value='';reset();return false};
      grid.innerHTML=res.map((d,i)=>`<div class="card" style="${dly(i)}">
        <div class="top"><a class="name" href="${d.url}" target="_blank">${esc(d.full_name)}</a></div>
        ${d.description?`<div class="desc"><span class="lbl">cosa fa</span><br>${esc(d.description)}</div>`:''}
        <div class="meta"><span>&#9733; ${d.stars.toLocaleString()}</span><span class="lang">${esc(d.language)||'--'}</span></div>
      </div>`).join('');
    }catch(err){bar.innerHTML='// errore ricerca: '+esc(String(err))+' //';}
  });
})();
/* ===== CYBER ===== */
const CY=P.cyber||[];
let cyRows=[];
function renderCy(){
  const f=document.getElementById('cyf').value, per=document.getElementById('cyper').value;
  const lim=per?daysAgo(+per):'';
  let rows=CY.filter(d=>(!f||(f==='ransom'&&d.ransomware)||(f==='rel'&&d.relevant))&&(!lim||(d.date&&d.date>=lim)));
  rows.sort((a,b)=>((b.relevant?1:0)-(a.relevant?1:0))||(b.date||'').localeCompare(a.date||''));
  cyRows=rows;
  const kpis=[['minacce',rows.length,''],['ti riguarda',rows.filter(d=>d.relevant).length,'var(--green)'],
    ['ransomware',rows.filter(d=>d.ransomware).length,'var(--red)'],['vendor',new Set(rows.map(d=>d.vendor).filter(Boolean)).size,'var(--cy)']];
  const cards=rows.map((d,i)=>bigCard({i,cls:(d.ransomware?'crit ':'')+(d.relevant?'mine':''),
    title:esc(d.cve),
    tags:`${d.relevant?'<span class="tg rel">TI RIGUARDA</span>':''}${d.ransomware?'<span class="tg rn">RANSOMWARE</span>':''}${d.vendor?`<span class="tg tp2">${esc(d.vendor)}</span>`:''}`,
    meta:`${d.name?`<span>${esc(d.name)}</span>`:''}${d.product?`<span class="dim">${esc(d.product)}</span>`:''}`,
    foot:`<span class="dim">rilevata ${esc(d.date)||'-'}</span>`})).join('');
  document.getElementById('grid-cy').innerHTML=kpiHTML(kpis)+cardsHTML(cards,'clic su una card per dettagli e difesa');
}
['cyf','cyper'].forEach(id=>document.getElementById(id).addEventListener('input',renderCy));
bindGrid('grid-cy',i=>{const d=cyRows[i];if(!d)return;detailView({
  title:d.cve,url:d.url,
  tags:[d.relevant&&{txt:'TI RIGUARDA'+(d.match?' · '+d.match:''),cls:'rel'},d.ransomware&&{txt:'RANSOMWARE',cls:'rn'},d.vendor&&{txt:d.vendor,cls:'tp2'}],
  stats:[[esc(d.product)||'-','prodotto'],[esc(d.vendor)||'-','vendor'],[esc(d.date)||'-','data']],
  blocks:[d.name&&{lbl:'nome',html:'<p>'+esc(d.name)+'</p>'},
    d.desc&&{lbl:"cos'e la vulnerabilita",html:'<p>'+esc(d.desc)+'</p>'},
    d.action&&{lbl:'difesa / azione richiesta',gold:true,html:'<p>'+esc(d.action)+'</p>'}]});
});
/* ===== PC ===== */
const PC=P.pc||[], pr=P.profile||{}, g=pr.gpu||{};
document.getElementById('prof').innerHTML=
  `CPU <b>${pr.cpu_cores||'?'} thread</b>`+
  ` &middot; RAM <b>${pr.ram_gb||'?'} GB</b>`+
  ` &middot; GPU <b>${esc(g.name||'?')} ${g.vram_mb||0}MB</b>`+
  ` &middot; CUDA <b>${g.cuda||'n/d'}</b>`+
  ` &middot; DISCO <b>${pr.disco_libero_gb||'?'} GB liberi</b>`;
const PIMP={alto:'l-no',medio:'l-cl',basso:'l-ok'};
let pcRows=[];
function renderPc(){
  pcRows=PC;
  const kpis=[['suggerimenti',PC.length,''],['impatto alto',PC.filter(t=>t.impatto==='alto').length,'var(--red)'],
    ['impatto medio',PC.filter(t=>t.impatto==='medio').length,'#e8b56b'],['aree',new Set(PC.map(t=>t.area).filter(Boolean)).size,'var(--cy)']];
  const cards=PC.map((t,i)=>bigCard({i,
    title:esc(t.titolo),
    tags:`${t.area?`<span class="tg tp2">${esc(t.area)}</span>`:''}<span class="tg ${PIMP[t.impatto]||'l-un'}">impatto ${esc(t.impatto)||'-'}</span>`,
    meta:t.consiglio?`<span class="dim">${esc((t.consiglio||'').slice(0,130))}${(t.consiglio||'').length>130?'…':''}</span>`:''})).join('');
  document.getElementById('grid-pc').innerHTML=kpiHTML(kpis)+cardsHTML(cards,'clic su una card per il consiglio completo');
}
bindGrid('grid-pc',i=>{const t=pcRows[i];if(!t)return;detailView({
  title:t.titolo,
  tags:[t.area&&{txt:t.area,cls:'tp2'},t.impatto&&{txt:'impatto '+t.impatto,cls:PIMP[t.impatto]||'l-un'}],
  blocks:[{lbl:'consiglio',html:'<p>'+esc(t.consiglio)+'</p>'}]});
});
/* ===== BLOCKCHAIN ===== */
const BC=P.blockchain||[];
let bcRows=[];
function renderBc(){
  const q=document.getElementById('bcq').value.toLowerCase();
  const f=document.getElementById('bcf').value;
  let rows=BC.filter(d=>(!f||(f==='audit'&&d.audit)||(f==='proj'&&!d.audit))&&
    (!q||d.full_name.toLowerCase().includes(q)||(d.description||'').toLowerCase().includes(q)||(d.topics||[]).join(' ').includes(q)));
  bcRows=rows;
  const kpis=[['progetti',rows.length,''],['audit & sicurezza',rows.filter(d=>d.audit).length,'var(--gold)'],
    ['web3 / dapp',rows.filter(d=>!d.audit).length,'var(--cy)']];
  const cards=rows.map((d,i)=>bigCard({i,cls:d.audit?'au':'',
    title:esc(d.full_name),
    right:`&#9733; ${d.stars.toLocaleString()}`,
    tags:`${d.audit?'<span class="tg au">SICUREZZA</span>':''}${d.language?`<span class="tg tp2">${esc(d.language)}</span>`:''}`,
    meta:`<span class="dim">${(d.topics||[]).slice(0,4).map(esc).join(' · ')||'nessun topic'}</span>`})).join('');
  document.getElementById('grid-bc').innerHTML=kpiHTML(kpis)+cardsHTML(cards,'clic su una card per dettagli + mappa business');
}
document.getElementById('bcq').addEventListener('input',renderBc);
document.getElementById('bcf').addEventListener('input',renderBc);
bindGrid('grid-bc',i=>{const d=bcRows[i];if(!d)return;detailView({
  title:d.full_name,url:d.url,
  tags:[d.audit&&{txt:'SICUREZZA',cls:'au'},d.language&&{txt:d.language,cls:'tp2'},...(d.topics||[]).slice(0,4).map(t=>({txt:t,cls:'b-nuova'}))],
  stats:[[d.stars.toLocaleString(),'stelle'],[esc(d.language)||'-','linguaggio']],
  blocks:[d.description&&{lbl:d.audit?'tool di sicurezza':'cosa fa',html:'<p>'+esc(d.description)+'</p>'}],
  map:{title:d.full_name,ctx:(d.description||'')+' '+(d.topics||[]).join(' ')}});
});
/* ticker prezzi crypto (snapshot dal payload; live via /crypto se servito) */
function renderCrypto(list){
  const c=list||P.crypto||[];const tr=document.getElementById('crypto-track');
  if(!c.length){tr.innerHTML='<span class="p">prezzi non disponibili</span>';return}
  const fmt=p=>p>=1?p.toLocaleString('en-US',{maximumFractionDigits:2}):p.toPrecision(3);
  const one=d=>`<span class="c"><b>${esc(d.sym)}</b><span class="p">$${fmt(d.price)}</span><span class="${d.chg>=0?'up':'dn'}">${d.chg>=0?'▲':'▼'}${Math.abs(d.chg)}%</span></span>`;
  tr.innerHTML=(c.map(one).join('')+c.map(one).join(''));/* doppio = scorrimento continuo */
}
renderCrypto();
if(location.protocol==='http:'||location.protocol==='https:'){
  const pc=()=>fetch('/crypto',{cache:'no-store'}).then(r=>r.json()).then(renderCrypto).catch(()=>{});
  setInterval(pc,60000);
}
/* ===== MERCATO ===== */
const MERCATO=P.mercato||[];
(function(){const s=document.getElementById('mkf');if(s)MERCATO.forEach(t=>{const o=document.createElement('option');o.value=t.topic;o.textContent=t.topic;s.appendChild(o)})})();
const MKDIR={rialzo:['#42e39b','&#9650; RIALZO','l-ok'],ribasso:['#ff5a5a','&#9660; RIBASSO','l-no'],rischio:['#e0975a','&#9670; RISCHIO','l-cl'],neutro:['#8fa6c0','&#9679; NEUTRO','l-un']};
let mkRows=[];
function renderMk(){
  const f=(document.getElementById('mkf')||{}).value||'';
  const rows=MERCATO.filter(t=>!f||t.topic===f);
  mkRows=rows;
  const dc=dir=>rows.filter(t=>((t.analisi||{}).direzione||'')===dir).length;
  const kpis=[['settori',rows.length,''],['rialzo',dc('rialzo'),'var(--green)'],['ribasso',dc('ribasso'),'var(--red)'],['rischio',dc('rischio'),'#e0975a']];
  const CH=P.cambiamenti||{};let banner='';
  if(!f&&((CH.eventi&&CH.eventi.length)||(CH.idee&&CH.idee.length)))
    banner=`<div class="mkbanner"><b>&#9670; cambiato da ieri</b> ${(CH.eventi||[]).slice(0,4).map(e=>esc(e.title)).join(' &middot; ')}${(CH.idee||[]).map(d=>' &middot; + idea: '+esc(d.titolo)).join('')}</div>`;
  const cards=rows.map((t,i)=>{const a=t.analisi||{},dd=MKDIR[(a.direzione||'').toLowerCase()];const first=(t.items||[])[0];
    return bigCard({i,
      title:esc(t.topic),
      right:`${(t.items||[]).length}`,
      tags:`${dd?`<span class="tg ${dd[2]}">${dd[1]}</span>`:''}${a.impatto?`<span class="tg tp2">impatto ${esc(a.impatto)}</span>`:''}`,
      meta:first?`<span class="dim">&#9656; ${esc(first.title)}</span>`:'<span class="dim">nessuna notizia</span>'});
  }).join('');
  document.getElementById('grid-mk').innerHTML=banner+kpiHTML(kpis)+cardsHTML(cards,'clic su un settore per le notizie + mappa business');
}
(function(){const s=document.getElementById('mkf');if(s)s.addEventListener('input',renderMk)})();
bindGrid('grid-mk',i=>{const t=mkRows[i];if(!t)return;const a=t.analisi||{},d=MKDIR[(a.direzione||'').toLowerCase()];
  detailView({title:t.topic,
    tags:[d&&{txt:d[1].replace(/&#\d+;/g,'').trim(),cls:d[2]},a.impatto&&{txt:'impatto '+a.impatto,cls:'tp2'}],
    blocks:[a.significa&&{lbl:'cosa significa per aziende/investitori',html:'<p>'+esc(a.significa)+'</p>'},
      {lbl:'notizie che muovono il settore',html:((t.items||[]).map(n=>`<div class="nrow"><a class="cve" href="${n.url}" target="_blank">&#9656; ${esc(n.title)}</a>${n.source?` <span class="dim">${esc(n.source)}</span>`:''}</div>`).join('')||'<p class="dim">nessuna notizia</p>')}],
    map:{title:t.topic,ctx:(a.significa||'')+' '+(t.items||[]).map(n=>n.title).join('; ')}});
});
/* ===== DISCO ===== */
const DISCO=P.disco||{};
const DCMD={'Docker (WSL)':'docker system prune -a --volumes','pip cache':'pip cache purge','npm cache':'npm cache clean --force','yarn cache':'yarn cache clean','Conda pkgs':'conda clean --all -y','HuggingFace hub':'huggingface-cli delete-cache'};
function copyCmd(el,t){if(navigator.clipboard){navigator.clipboard.writeText(t);const o=el.textContent;el.textContent='copiato';setTimeout(()=>el.textContent=o,1200)}}
function genPulizia(){
  const cmds=(DISCO.cache||[]).map(c=>DCMD[c.nome]).filter(Boolean);
  let bat='@echo off\r\nchcp 65001>nul\r\ntitle Pulizia disco - Jarvis\r\necho Pulizia cache sicure (dati rigenerabili). Chiudi se non vuoi procedere.\r\npause\r\n';
  cmds.forEach(c=>{bat+=`echo.\r\necho ^> ${c}\r\n${c}\r\n`});
  bat+='echo.\r\necho Fatto. Svuota anche il Cestino se vuoi.\r\npause\r\n';
  const blob=new Blob([bat],{type:'text/plain'});const a=document.createElement('a');
  a.href=URL.createObjectURL(blob);a.download='pulizia.bat';a.click();URL.revokeObjectURL(a.href);
}
function trashFile(el){
  if(el.dataset.confirm!=='1'){el.dataset.confirm='1';el.dataset.o=el.textContent;el.textContent='conferma?';el.classList.add('warn');
    setTimeout(()=>{if(el.dataset.confirm==='1'){el.dataset.confirm='';el.textContent=el.dataset.o;el.classList.remove('warn')}},3000);return}
  el.textContent='...';el.disabled=true;el.classList.remove('warn');
  fetch('/trash',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({path:el.dataset.p})})
   .then(r=>r.json()).then(j=>{
     if(j.ok){const row=el.closest('tr')||el.closest('.reason')||el.closest('.dupline');if(row)row.style.opacity=.4;el.textContent=j.gone?'gia assente':'nel Cestino';}
     else{el.textContent=(j.err||'errore').slice(0,22);el.title=j.err||'';el.classList.add('warn');el.disabled=false;el.dataset.confirm='';}
   }).catch(()=>{el.textContent='errore rete';el.disabled=false;el.dataset.confirm='';});
}
function emptyBin(el){
  if(el.dataset.confirm!=='1'){el.dataset.confirm='1';el.dataset.o=el.textContent;el.textContent='SICURO? irreversibile - riclicca';el.classList.add('warn');
    setTimeout(()=>{if(el.dataset.confirm==='1'){el.dataset.confirm='';el.textContent=el.dataset.o;el.classList.remove('warn')}},4000);return}
  el.textContent='svuoto...';el.classList.remove('warn');
  fetch('/emptybin',{method:'POST'}).then(r=>r.json()).then(j=>{el.textContent=j.ok?`fatto - ${j.free_gb} GB liberi`:'errore';el.dataset.confirm='';}).catch(()=>{el.textContent='errore rete';el.dataset.confirm='';});
}
function spark(pts,col){
  if(!pts||pts.length<2)return '';
  const vs=pts.map(p=>p.free_gb),mn=Math.min(...vs),mx=Math.max(...vs),rng=(mx-mn)||1,W=260,H=40;
  const d=pts.map((p,i)=>`${(i/(pts.length-1)*W).toFixed(1)},${(H-(p.free_gb-mn)/rng*H).toFixed(1)}`).join(' ');
  return `<svg class="spark" viewBox="0 0 ${W} ${H}" preserveAspectRatio="none"><polyline points="${d}" fill="none" stroke="${col}" stroke-width="2"/></svg>`;
}
const DKC={cache:'l-cl',freddo:'l-no',dup:'tp2'},DKL={cache:'cache',freddo:'freddo',dup:'duplicato'};
const dbase=p=>(p||'').split(/[\\/]/).pop();
let discoItems=[];
function renderDisco(){
  const g=document.getElementById('grid-disco');if(!g)return;
  const d=DISCO.disco||{},caches=DISCO.cache||[],cold=DISCO.freddi||[];
  const dup=DISCO.duplicati||[],tr=DISCO.trend||[],pv=DISCO.previsione||{};
  const pct=d.free_pct||0,col=pct<10?'#ff5a5a':pct<20?'#e0975a':'#42e39b';
  let items=[];
  caches.forEach(c=>items.push({kind:'cache',label:c.nome,gb:c.gb,path:c.path,cmd:DCMD[c.nome]||''}));
  cold.forEach(f=>items.push({kind:'freddo',label:dbase(f.path),gb:f.gb,path:f.path,eta:f.eta}));
  dup.forEach(x=>x.paths.forEach((p,i)=>items.push({kind:'dup',label:dbase(p),gb:x.gb,path:p,keep:i===0})));
  items.sort((a,b)=>b.gb-a.gb);
  discoItems=items;
  const kpis=[['GB liberi',(d.free_gb??'-'),col],['spazio',pct+'%',col],['liberabile','~'+(DISCO.liberabile_gb??'-')+' GB','var(--gold)'],['duplicati',dup.length,'var(--red)']];
  let prev='';
  if(pv.stato==='in calo'&&pv.giorni!=null)prev=`<span class="tg l-no">pieno tra ~${pv.giorni}g (${pv.gb_giorno} GB/g)</span>`;
  else if(pv.stato==='stabile')prev='<span class="tg l-ok">spazio stabile</span>';
  const head=`<div class="discohead"><div class="gbar"><span style="width:${Math.max(2,100-pct)}%;background:${col}"></span></div>
    <div class="dhrow">${tr.length>1?spark(tr,col):''}${prev}
      <button class="cp" onclick="genPulizia()">&#8595; pulizia.bat</button>
      <button class="cp" data-confirm="" onclick="emptyBin(this)">Svuota Cestino (libera davvero)</button></div>
    <div class="thint">Cestino = recuperabile; lo spazio si libera davvero solo svuotando il Cestino.</div></div>`;
  const act=it=>it.kind==='cache'?(it.cmd?`<button class="cp mini" onclick="event.stopPropagation();copyCmd(this,'${it.cmd}')">copia cmd</button>`:'<span class="dim">a mano</span>')
    :(it.keep?'<span class="keep">tieni</span>':`<button class="cp mini" data-p="${escA(it.path)}" onclick="event.stopPropagation();trashFile(this)">Cestino</button>`);
  const cards=items.map((it,i)=>bigCard({i,cls:(it.kind==='freddo'||it.kind==='dup')?'crit':'',
    title:esc(it.label),
    right:`${it.gb}`,
    tags:`<span class="tg ${DKC[it.kind]}">${DKL[it.kind]}</span>${it.eta?`<span class="tg l-un">${it.eta}g fermo</span>`:''}${it.keep?'<span class="tg rel">copia da tenere</span>':''}`,
    meta:`<span class="dim path">${esc(it.path)}</span>`,
    foot:act(it)})).join('');
  g.innerHTML=kpiHTML(kpis)+head+cardsHTML(cards,'clic su una card per il percorso completo');
}
bindGrid('grid-disco',i=>{const it=discoItems[i];if(!it)return;detailView({
  title:it.label,
  tags:[{txt:DKL[it.kind],cls:DKC[it.kind]},it.eta&&{txt:it.eta+' giorni fermo',cls:'l-un'}],
  stats:[[it.gb+' GB','dimensione'],[DKL[it.kind],'categoria']],
  blocks:[{lbl:'percorso completo',html:'<p class="path">'+esc(it.path)+'</p>'},
    (it.kind==='cache'&&it.cmd)&&{lbl:'comando pulizia (copia e lancia)',html:`<button class="cp" onclick="copyCmd(this,'${it.cmd}')">${esc(it.cmd)}</button>`},
    (it.kind!=='cache'&&!it.keep)&&{lbl:'azione',html:`<button class="cp mini" data-p="${escA(it.path)}" onclick="trashFile(this)">Sposta nel Cestino</button>`},
    (it.kind==='dup'&&it.keep)&&{lbl:'nota',html:'<p class="dim">questa e la copia da tenere</p>'}]});
});
/* ===== IDEE ===== */
const IDEE=P.idee||[];
let FAV=JSON.parse(localStorage.getItem('jarvis_fav')||'[]');
function toggleFav(t){FAV=FAV.includes(t)?FAV.filter(x=>x!==t):[...FAV,t];localStorage.setItem('jarvis_fav',JSON.stringify(FAV));renderIdee();}
function exportDossier(){
  const fav=IDEE.filter(d=>FAV.includes(d.titolo));const pick=fav.length?fav:IDEE;
  const dt=new Date().toISOString().slice(0,10);
  let md=`# Dossier idee - Jarvis\n\n_Generato il ${dt}${fav.length?' - solo preferite':' - tutte le idee'}_\n\n`;
  pick.forEach((d,i)=>{
    md+=`## ${i+1}. ${d.titolo}\n\n`;
    if(d.descrizione)md+=`${d.descrizione}\n\n`;
    if(d.problema)md+=`**Problema:** ${d.problema}\n\n`;
    if(d.perche_ora)md+=`**Perche ora:** ${d.perche_ora}\n\n`;
    if(d.tam)md+=`**Mercato stimato:** ${d.tam}\n\n`;
    if(d.fattibilita)md+=`**Fattibilita:** ${d.fattibilita}\n\n`;
    if(d.novelta)md+=`**Novelta:** ${d.novelta}\n\n`;
    if(d.passi&&d.passi.length)md+=`**Primi passi:**\n`+d.passi.map((s,n)=>`${n+1}. ${s}`).join('\n')+`\n\n`;
    if(d.web&&d.web.length)md+=`**Riferimenti/concorrenti reali:**\n`+d.web.map(w=>`- [${w.title}](${w.url})`).join('\n')+`\n\n`;
    else if(d.verifica)md+=`**Query verifica:** ${d.verifica}\n\n`;
    md+=`---\n\n`;
  });
  const blob=new Blob([md],{type:'text/markdown'});const a=document.createElement('a');
  a.href=URL.createObjectURL(blob);a.download='dossier-idee-'+dt+'.md';a.click();URL.revokeObjectURL(a.href);
}
const IDLV={alta:'l-ok',media:'l-cl',bassa:'l-no'};
let idRows=[];
const nvl=v=>(v||'').toLowerCase();
let FUSED=JSON.parse(localStorage.getItem('jarvis_fused')||'[]');
const idSel=new Set();
const idAll=()=>FUSED.concat(IDEE);
function renderIdee(){
  const fb=(document.getElementById('idf')||{}).value||'';
  let list=idAll();
  if(fb==='fav')list=list.filter(d=>FAV.includes(d.titolo));
  list.sort((a,b)=>(FAV.includes(b.titolo)-FAV.includes(a.titolo)));
  idRows=list;
  const kpis=[['idee',list.length,''],['preferite',list.filter(d=>FAV.includes(d.titolo)).length,'var(--gold)'],
    ['fuse',FUSED.length,'#b98cff'],['novita alta',list.filter(d=>nvl(d.novelta)==='alta').length,'var(--green)']];
  const cards=list.map((d,i)=>{const on=FAV.includes(d.titolo),sel=idSel.has(d.titolo);
    return bigCard({i,cls:d.fused?'fu':'',
      title:esc(d.titolo)+(d.fused?'<span class="tg fu">FUSA</span>':''),
      tags:`${d.settore?`<span class="tg tp2">${esc(d.settore)}</span>`:''}<span class="tg ${IDLV[nvl(d.fattibilita)]||'l-un'}">fattib. ${esc(d.fattibilita)||'-'}</span><span class="tg ${IDLV[nvl(d.novelta)]||'l-un'}">novita ${esc(d.novelta)||'-'}</span>`,
      meta:d.descrizione?`<span class="dim">${esc((d.descrizione||'').slice(0,150))}${(d.descrizione||'').length>150?'…':''}</span>`:'',
      foot:`<label class="idpick" onclick="event.stopPropagation()"><input type="checkbox" class="idsel" data-t="${escA(d.titolo)}"${sel?' checked':''}> fondi</label><button class="fv" data-t="${escA(d.titolo)}" title="salva idea">${on?'★':'☆'}</button>`});
  }).join('');
  const bar=`<div class="fusebar"><span>selezionate <b id="fuse-n">${idSel.size}</b></span><button id="fuse-go" class="cp"${idSel.size<2?' disabled':''}>&#10022; fondi in una nuova idea</button><span class="dim">spunta 2+ idee e fondile in una startup ibrida</span></div>`;
  document.getElementById('grid-idee').innerHTML=kpiHTML(kpis)+bar+cardsHTML(cards,'clic su una card per il piano completo + mappa business');
}
document.getElementById('grid-idee').addEventListener('click',e=>{
  const cb=e.target.closest('.idsel');if(cb){e.stopPropagation();cb.checked?idSel.add(cb.dataset.t):idSel.delete(cb.dataset.t);
    const n=document.getElementById('fuse-n');if(n)n.textContent=idSel.size;const g=document.getElementById('fuse-go');if(g)g.disabled=idSel.size<2;return;}
  const fv=e.target.closest('.fv');if(fv){e.stopPropagation();toggleFav(fv.dataset.t);return;}
  if(e.target.closest('#fuse-go')){fuse();return;}
  const c=e.target.closest('.gcard');if(c)openIdea(+c.dataset.i);
});
async function fuse(){
  const picked=idRows.filter(d=>idSel.has(d.titolo));if(picked.length<2)return;
  const go=document.getElementById('fuse-go');
  if(!(location.protocol==='http:'||location.protocol==='https:')){if(go)go.textContent='serve il server locale';return;}
  if(go){go.disabled=true;go.textContent='fondo le idee... (Ollama)';}
  try{
    const r=await fetch('/fondi',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({ideas:picked})});
    const d=await r.json();
    if(d.error){if(go){go.textContent='errore: '+d.error.slice(0,34);}return;}
    d.fused=true;d.settore='fusione';FUSED.unshift(d);localStorage.setItem('jarvis_fused',JSON.stringify(FUSED));
    idSel.clear();renderIdee();ideaDetail(d);
  }catch(e){if(go)go.textContent='errore rete';}
}
function delFused(t){FUSED=FUSED.filter(x=>x.titolo!==t);localStorage.setItem('jarvis_fused',JSON.stringify(FUSED));document.getElementById('detail').classList.remove('on');renderIdee();}
function openIdea(i){ideaDetail(idRows[i]);}
function ideaDetail(d){if(!d)return;const on=FAV.includes(d.titolo);
  const web=(d.web&&d.web.length)?`<span class="lbl" style="color:${d.web_esiste?'var(--red)':'var(--green)'}">${d.web_esiste?'concorrenti simili gia presenti':'pochi riscontri diretti'}</span>`+d.web.map(w=>`<div class="nrow"><a class="cve" href="${w.url}" target="_blank">&#9656; ${esc(w.title)}</a></div>`).join(''):(d.verifica?`<a class="cve" href="https://www.google.com/search?q=${encodeURIComponent(d.verifica)}" target="_blank">&#9656; verifica: ${esc(d.verifica)}</a>`:'');
  detailView({title:d.titolo,
    tags:[d.fused&&{txt:'IDEA FUSA',cls:'fu'},{txt:on?'★ preferita':'idea',cls:on?'l-cl':'tp2'},d.settore&&{txt:d.settore,cls:'tp2'},d.tam&&{txt:'mercato '+d.tam,cls:'tp2'},d.fattibilita&&{txt:'fattib. '+d.fattibilita,cls:IDLV[nvl(d.fattibilita)]||'l-un'},d.novelta&&{txt:'novita '+d.novelta,cls:IDLV[nvl(d.novelta)]||'l-un'}],
    blocks:[d.descrizione&&{lbl:'idea',html:'<p>'+esc(d.descrizione)+'</p>'},
      d.sinergia&&{lbl:'sinergia tra le idee fuse',html:'<p>'+esc(d.sinergia)+'</p>'},
      (d.fonti&&d.fonti.length)&&{lbl:'fusa da',html:'<p class="dim">'+d.fonti.map(esc).join('  +  ')+'</p>'},
      d.problema&&{lbl:'problema che risolve',html:'<p>'+esc(d.problema)+'</p>'},
      d.perche_ora&&{lbl:'perche ora',html:'<p>'+esc(d.perche_ora)+'</p>'},
      (d.passi&&d.passi.length)&&{lbl:'primi passi',html:d.passi.map((s,n)=>`<div class="nrow">${n+1}. ${esc(s)}</div>`).join('')},
      web&&{lbl:'verifica sul web (concorrenti reali)',html:web},
      d.fused&&{lbl:'gestione',html:`<button class="cp mini" onclick="delFused('${(d.titolo||'').replace(/'/g,"\\\\'")}')">rimuovi idea fusa</button>`}],
    map:{title:d.titolo,ctx:(d.descrizione||'')+' '+(d.problema||'')}});
}
/* ===== hub: navigazione a pagine + rotazione automatica (dwell) ===== */
const SECTIONS=['github','cyber','blockchain','pc','disco','mercato','idee'];
const SNAME={github:'GitHub',cyber:'Cyber',blockchain:'Blockchain',pc:'PC',disco:'Disco',mercato:'Mercato',idee:'Idee'};
const SACC={github:'#7c8cff',cyber:'#ff5a5a',blockchain:'#e8b56b',pc:'#42e39b',disco:'#6ad0c0',mercato:'#e0975a',idee:'#b98cff'};
const DWELL=7500;
let cur=0,auto=false,paused=false,hold=0;  // default MANUALE: scrolli tu, niente rotazione automatica
function pager(sec){
  clearTimeout(hold);
  const vp=sec.querySelector('.reel-vp');if(!vp)return;
  vp.scrollTop=0;
  function advance(){
    if(!auto)return;
    if(paused){hold=setTimeout(advance,1200);return}
    const max=vp.scrollHeight-vp.clientHeight;
    if(max<=6||vp.scrollTop>=max-6){next();return}
    vp.scrollTo({top:Math.min(max,vp.scrollTop+vp.clientHeight*0.9),behavior:'smooth'});
    hold=setTimeout(advance,DWELL);
  }
  if(auto)hold=setTimeout(advance,DWELL);
}
function show(i){
  cur=(i+SECTIONS.length)%SECTIONS.length;const s=SECTIONS[cur];
  document.querySelectorAll('.sector').forEach(x=>x.classList.toggle('act',x.dataset.s===s));
  document.querySelectorAll('section').forEach(x=>x.classList.remove('on'));
  const sec=document.getElementById('sec-'+s);sec.classList.add('on');
  document.getElementById('cur-sec').textContent=SNAME[s];
  document.getElementById('sec-cnt').textContent=(cur+1)+' / '+SECTIONS.length;
  const ah=(P.freshness||{})[s],ae=document.getElementById('sec-age');
  if(ae){if(ah==null)ae.textContent='';else{const t=ah<1?'aggiornato ora':ah<24?`aggiornato ${Math.round(ah)}h fa`:`aggiornato ${Math.round(ah/24)}g fa`;ae.textContent=t;ae.classList.toggle('stale',ah>36)}}
  document.querySelector('.status').style.setProperty('--acc',SACC[s]);
  document.querySelector('.feed').style.setProperty('--acc',SACC[s]);
  requestAnimationFrame(()=>pager(sec));
}
function next(){if(paused){hold=setTimeout(next,1500);return}enterSection(cur+1,auto)}
function prev(){enterSection(cur-1,false)}
function lbl(){const b=document.getElementById('auto-btn');b.classList.toggle('off',!auto);document.getElementById('auto-lbl').textContent=auto?'AUTO':'MANUALE'}
function enterHome(){
  document.body.classList.remove('viewing');auto=false;clearTimeout(hold);
  document.querySelectorAll('.sector').forEach(x=>x.classList.remove('act'));
  document.querySelectorAll('section').forEach(x=>x.classList.remove('on'));
}
function enterSection(i,autoMode){
  document.body.classList.add('viewing');auto=!!autoMode;lbl();show(i);
}
function setAuto(on){if(on){enterSection(cur,true)}else{auto=false;clearTimeout(hold);lbl()}}
function goHub(){document.body.classList.remove('viewing');enterHome();window.scrollTo(0,0);}
document.querySelectorAll('.sector').forEach(g=>g.addEventListener('click',()=>enterSection(SECTIONS.indexOf(g.dataset.s),false)));
document.querySelector('.core').addEventListener('click',()=>document.body.classList.contains('viewing')?enterHome():enterSection(cur,false));
document.getElementById('auto-btn').addEventListener('click',()=>setAuto(!auto));
document.getElementById('prev-sec').addEventListener('click',prev);
document.getElementById('next-sec').addEventListener('click',next);
const feedEl=document.querySelector('.feed');
feedEl.addEventListener('mouseenter',()=>paused=true);
feedEl.addEventListener('mouseleave',()=>paused=false);
let mh='';for(let i=0;i<26;i++){mh+=`<i style="left:${(Math.random()*100).toFixed(1)}%;animation-duration:${(9+Math.random()*15).toFixed(1)}s;animation-delay:${(-Math.random()*22).toFixed(1)}s"></i>`}
document.getElementById('motes').innerHTML=mh;
function countup(el,to,dec){let n=0,step=Math.max(1,Math.ceil(to/24));const t=setInterval(()=>{n+=step;if(n>=to){n=to;clearInterval(t)}el.textContent=dec?(n/10).toFixed(1):n},22)}
countup(document.getElementById('s-tot'),DATA.length);
countup(document.getElementById('s-cy'),CY.length);
countup(document.getElementById('s-new'),DATA.filter(d=>d.new_today).length);
/* ===== telemetria: hardware+software (snapshot) SX + live DX ===== */
(function(){
  const pf=P.profile||{},gp=pf.gpu||{};
  const ro=(k,v,s,id)=>`<div class="ro"><div class="k">${k}</div><div class="v"${id?` id="${id}"`:''}>${v}${s?` <small>${s}</small>`:''}</div></div>`;
  const rob=(k,id,bid,s)=>`<div class="ro"><div class="k">${k}</div><div class="v" id="${id}">--</div>${s?`<div class="bar"><i id="${bid}"></i></div>`:`<div class="bar"><i id="${bid}"></i></div>`}</div>`;
  const osv=(pf.os||'').replace('Microsoft Windows [Versione','Win').replace(']','').trim()||'n/d';
  const v=x=>String(x||'').replace(/^v/,'').split(' ').slice(-1)[0]||x||'n/d';
  /* --- SINISTRA: profilo statico (hardware + ambiente sviluppo) --- */
  document.getElementById('tele-l').innerHTML='<div class="htitle">// sistema</div>'+
    ro('OS',esc(osv))+
    ro('CPU',(pf.cpu_cores||'?'),'thread / '+(pf.cpu_cores_fisici||'?')+' core')+
    ro('RAM',(pf.ram_gb||'?'),'GB')+
    ro('GPU',esc(gp.name||'?'))+
    ro('VRAM',(gp.vram_mb||0),'MB · CUDA '+esc(gp.cuda||'n/d'))+
    ro('DRIVER',esc(gp.driver||'n/d'))+
    ro('DISCO',(pf.disco_libero_gb||'?'),'GB liberi')+
    '<div class="htitle">// ambiente dev</div>'+
    ro('PYTHON',esc(v(pf.python)))+
    ro('NODE',esc(v(pf.node)))+
    ro('NPM',esc(pf.npm||'n/d'))+
    ro('DOCKER',esc((pf.docker||'').replace('Docker version','').split(',')[0].trim()||'n/d'))+
    ro('GIT',esc((pf.git||'').replace('git version','').trim()||'n/d'));
  /* --- DESTRA: live. Se serviamo da server -> hardware reale; altrimenti browser --- */
  const R=document.getElementById('tele-r');
  const LIVE=location.protocol==='http:'||location.protocol==='https:';
  const cls=p=>p>=85?' hot':p>=60?' warn':'';
  if(LIVE){
    R.innerHTML='<div class="htitle">live hardware <span class="live"></span></div>'+
      ro('ORA','--',null,'t-clock')+
      ro('ATTIVO','--',null,'t-up')+
      rob('CPU','t-cpu','t-cpub')+
      `<div class="ro"><div class="k">CORE</div><div class="cores" id="t-cores"></div></div>`+
      rob('RAM','t-ram','t-ramb')+
      rob('GPU','t-gpu','t-gpub')+
      ro('GPU TEMP','--',null,'t-gtemp')+
      rob('DISCO C:','t-disk','t-diskb')+
      ro('RETE','--',null,'t-net')+
      rob('BATTERIA','t-bat','t-batb')+
      ro('PROCESSI','--',null,'t-proc')+
      `<div class="telenote">dati reali via server locale</div>`;
    const $=id=>document.getElementById(id);
    const setb=(id,bid,txt,pct,fmt)=>{const e=$(id);e.textContent=txt;e.className='v'+cls(pct);const b=$(bid);b.style.width=Math.min(100,pct)+'%';b.parentNode.className='bar'+(pct>=60?' hi':'')};
    const hms=s=>`${Math.floor(s/86400)}g ${Math.floor(s%86400/3600)}h ${Math.floor(s%3600/60)}m`;
    async function poll(){
      try{
        const d=await(await fetch('/telemetry',{cache:'no-store'})).json();
        $('t-clock').textContent=d.ts;
        $('t-up').textContent=hms(d.uptime);
        setb('t-cpu','t-cpub',d.cpu_pct+'% '+(d.cpu_ghz?d.cpu_ghz+'GHz':''),d.cpu_pct);
        $('t-cores').innerHTML=(d.cpu_cores||[]).map(p=>`<b style="height:${Math.max(6,p)}%"></b>`).join('');
        setb('t-ram','t-ramb',d.ram_used+'/'+d.ram_tot+' GB · '+d.ram_pct+'%',d.ram_pct);
        const g=d.gpu||{};
        if(g.util!=null){setb('t-gpu','t-gpub',g.util+'% · '+g.vram_used+'/'+g.vram_tot+'MB'+(g.power?' · '+g.power+'W':''),g.util);
          const gt=$('t-gtemp');gt.textContent=g.temp+' °C';gt.className='v'+cls(g.temp);}
        else{$('t-gpu').textContent='n/d';$('t-gtemp').textContent='n/d';}
        setb('t-disk','t-diskb',d.disk_used+'/'+d.disk_tot+' GB · '+d.disk_pct+'%',d.disk_pct);
        $('t-net').innerHTML='&#9660; '+d.net_down+' &#9650; '+d.net_up+' <small>Mb/s</small>';
        const b=d.battery||{};
        setb('t-bat','t-batb',(b.pct!=null?b.pct+'%':'n/d')+(b.charging?' ⚡':''),100-(b.pct||0));
        $('t-bat').className='v';$('t-batb').style.width=(b.pct||0)+'%';
        $('t-proc').textContent=d.procs;
      }catch(e){$('t-clock').textContent='server offline';}
    }
    poll();setInterval(poll,2000);
  }else{
    R.innerHTML='<div class="htitle">telemetria <span class="live"></span></div>'+
      ro('ORA','--',null,'t-clock')+
      ro('STATO','--',null,'t-net')+
      ro('RETE','--',null,'t-conn')+
      rob('BATTERIA','t-bat','t-batb')+
      rob('MEMORIA JS','t-mem','t-memb')+
      `<div class="telenote">telemetria browser. Per CPU/GPU/RAM reali avvia<br><b>python server.py --open</b></div>`;
    const fmtMB=b=>(b/1048576).toFixed(0);
    let bat=null;
    if(navigator.getBattery)navigator.getBattery().then(b=>bat=b).catch(()=>{});
    function tick(){
      document.getElementById('t-clock').textContent=new Date().toLocaleTimeString('it-IT');
      document.getElementById('t-net').textContent=navigator.onLine?'ONLINE':'OFFLINE';
      const c=navigator.connection;
      document.getElementById('t-conn').textContent=c?`${(c.effectiveType||'?').toUpperCase()} ${c.downlink||'?'}Mb`:'n/d';
      const be=document.getElementById('t-bat'),bb=document.getElementById('t-batb');
      if(bat){const p=Math.round(bat.level*100);be.innerHTML=p+'% '+(bat.charging?'<small>in carica</small>':'');bb.style.width=p+'%'}
      else{be.textContent='n/d';bb.style.width='0'}
      const m=performance.memory,me=document.getElementById('t-mem'),mb=document.getElementById('t-memb');
      if(m){me.innerHTML=fmtMB(m.usedJSHeapSize)+' <small>MB</small>';mb.style.width=(m.usedJSHeapSize/m.jsHeapSizeLimit*100).toFixed(1)+'%'}
      else{me.textContent='n/d'}
    }
    tick();setInterval(tick,1000);
  }
})();
(function(){const s=document.getElementById('idf');if(s)s.addEventListener('input',renderIdee);const b=document.getElementById('dossier-btn');if(b)b.onclick=exportDossier;})();
/* ===== report settimanale ===== */
(function(){
  const fab=document.getElementById('week-fab'),pan=document.getElementById('week-panel');if(!fab)return;
  const W=P.weekly||{};const txt=W.testo||'Report non ancora generato. Viene creato ogni lunedi (o con: python weekly.py).';
  document.getElementById('week-body').textContent=txt;
  document.getElementById('week-when').textContent=W.generato?('agg. '+W.generato):'';
  fab.onclick=()=>pan.classList.toggle('on');
  document.getElementById('week-x').onclick=()=>pan.classList.remove('on');
  document.getElementById('week-dl').onclick=()=>{
    const b=new Blob([txt],{type:'text/markdown'}),a=document.createElement('a');
    a.href=URL.createObjectURL(b);a.download='report-settimanale.md';a.click();URL.revokeObjectURL(a.href);
  };
})();
renderGh();renderCy();renderPc();renderBc();renderDisco();renderMk();renderIdee();
enterHome();  // (nav hub non usata in modalita piatta, resta per compatibilita)
/* ===== DASHBOARD PIATTA: mostra tutte le sezioni impilate con titolo ===== */
(function(){
  const hf=document.getElementById('home-fab');if(hf)hf.onclick=goHub;
})();
/* ===== chat Chiedi a Jarvis ===== */
(function(){
  const fab=document.getElementById('ask-fab'),pan=document.getElementById('ask-panel');
  const log=document.getElementById('ask-log'),q=document.getElementById('ask-q');
  const LIVE=location.protocol==='http:'||location.protocol==='https:';
  fab.onclick=()=>{pan.classList.toggle('on');if(pan.classList.contains('on'))q.focus()};
  document.getElementById('ask-x').onclick=()=>pan.classList.remove('on');
  function add(cls,txt){const d=document.createElement('div');d.className='m '+cls;d.textContent=txt;log.appendChild(d);log.scrollTop=log.scrollHeight;return d}
  add('j',LIVE?'Ciao. Chiedimi delle repo, minacce cyber, crypto o idee di oggi.':'Per usarmi avvia il server locale: python server.py --open');
  let busy=false;
  async function send(){
    const t=q.value.trim();if(!t||busy)return;
    if(!LIVE){add('j','Chat disponibile solo col server locale attivo.');return}
    q.value='';add('u',t);const w=add('j wait','...sto pensando');busy=true;
    try{const r=await fetch('/ask',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({q:t})});
      const d=await r.json();w.className='m j';w.textContent=d.answer||'(nessuna risposta)';}
    catch(e){w.className='m j';w.textContent='Errore: server non raggiungibile.'}
    busy=false;log.scrollTop=log.scrollHeight;
  }
  document.getElementById('ask-send').onclick=send;
  q.addEventListener('keydown',e=>{if(e.key==='Enter')send()});
})();
/* ===== reattore: acquisisci conoscenze del giorno ===== */
(function(){
  const fab=document.getElementById('sync-fab');if(!fab)return;
  const step=document.getElementById('sync-step');
  const LIVE=location.protocol==='http:'||location.protocol==='https:';
  const on=()=>{fab.classList.add('syncing');fab.title='Acquisizione in corso...';step.classList.add('on');step.textContent='avvio...'};
  const off=t=>{fab.classList.remove('syncing');fab.title=t||'Acquisisci le conoscenze di oggi';step.classList.remove('on');step.textContent=''};
  async function poll(){
    try{const d=await(await fetch('/refresh')).json();
      if(d.running){if(d.step)step.textContent=d.step;setTimeout(poll,2500);return}
      if(d.err){off('Errore: '+d.err.slice(0,60))}
      else{step.textContent='fatto';off('Aggiornato '+(d.done_at||''));setTimeout(()=>location.reload(),700)}
    }catch(e){setTimeout(poll,4000)}
  }
  fab.onclick=async()=>{
    if(!LIVE){off('Serve il server: python server.py --open');fab.classList.add('syncing');setTimeout(()=>off(),1800);return}
    if(fab.classList.contains('syncing'))return;
    on();
    try{await fetch('/refresh',{method:'POST'});setTimeout(poll,3000);}
    catch(e){off('Errore: server non raggiungibile')}
  };
  // se una acquisizione era gia in corso quando apro, riaggancio lo stato
  if(LIVE)fetch('/refresh').then(r=>r.json()).then(d=>{if(d.running){on();setTimeout(poll,3000)}}).catch(()=>{});
})();
/* ===== health strip (Ollama / disco / freschezza) ===== */
(function(){
  const el=document.getElementById('health');if(!el)return;
  if(!(location.protocol==='http:'||location.protocol==='https:')){el.style.display='none';return}
  async function upd(){
    try{const h=await(await fetch('/health',{cache:'no-store'})).json();
      const low=h.disk_free_pct<12;
      el.style.display='';
      el.innerHTML=
        `<span class="hi"><span class="dot ${h.ollama?'ok':'no'}"></span>Ollama ${h.ollama?'attivo':'spento'}</span>`+
        `<span class="hi">disco <b class="${low?'warn':''}">${h.disk_free_gb}GB &middot; ${h.disk_free_pct}%</b></span>`+
        `<span class="hi">GitHub <b>${h.github_age_h==null?'--':h.github_age_h+'h fa'}</b></span>`+
        `<span class="hi">scan disco <b>${h.disco_age_h==null?'--':h.disco_age_h+'h fa'}</b></span>`+
        (h.last_run?`<span class="hi">ultimo run <b>${esc(h.last_run)}</b></span>`:'');
    }catch(e){el.style.display='none'}
  }
  upd();setInterval(upd,30000);
})();
/* ===== accendi/spegni Ollama ===== */
(function(){
  const b=document.getElementById('ollama-btn');if(!b)return;
  const lbl=document.getElementById('ollama-lbl');
  if(!(location.protocol==='http:'||location.protocol==='https:')){b.style.display='none';return}
  let on=false;
  function paint(){b.classList.toggle('on',on);b.classList.toggle('off',!on);lbl.textContent=on?'Ollama ON':'Ollama OFF';}
  async function refresh(){try{const h=await(await fetch('/health',{cache:'no-store'})).json();on=!!h.ollama;paint();}catch(e){}}
  b.onclick=async()=>{
    b.classList.add('busy');lbl.textContent=on?'spengo...':'accendo...';
    try{await fetch('/ollama',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({on:!on})});}catch(e){}
    setTimeout(async()=>{await refresh();b.classList.remove('busy');},2600);  // Ollama impiega qualche secondo a salire
  };
  refresh();setInterval(refresh,15000);
})();
</script></body></html>"""


# ---------- main ----------
def main():
    global GH_TOKEN
    GH_TOKEN = get_token(force="--token" in sys.argv)
    if not GH_TOKEN:
        print("  ! nessun token: proseguo senza (rate limit ridotto).")
    con = db_init()
    today = datetime.date.today().isoformat()
    print("[1/4] fetch GitHub...")
    repos = fetch_all()
    # snapshot stelle di oggi (serve a calcolare la velocita = trending reale)
    for r in repos:
        con.execute("INSERT OR REPLACE INTO star_snap(full_name,day,stars) VALUES(?,?,?)",
                    (r["full_name"], today, r["stars"]))
    con.commit()
    fresh = [r for r in repos if not already_seen(con, r["full_name"])]
    print(f"      {len(repos)} trovate, {len(fresh)} nuove da valutare")
    # budget shortlist diviso per categoria: i giganti "tendenza" non devono
    # mangiare tutti gli slot alle "nuove uscite" (poche stelle).
    half = CFG["max_shortlist"] // 2
    by_cat = {"nuova": [], "tendenza": []}
    for r in sorted(fresh, key=lambda r: r["stars"], reverse=True):
        by_cat[r["category"]].append(r)
    fresh = by_cat["nuova"][:half] + by_cat["tendenza"][:CFG["max_shortlist"] - half]

    print(f"[2/4] rank con Ollama ({CFG['modello']})...")
    for i, r in enumerate(fresh, 1):
        score, reason, biz, tipo = rank(r)
        print(f"      [{i}/{len(fresh)}] {r['full_name']} -> {score}/10 (biz {biz}, {tipo})")
        con.execute("""INSERT OR REPLACE INTO repos
            (full_name,url,description,language,stars,category,score,reason,first_seen,pushed_at,license,biz,tipo)
            VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (r["full_name"], r["url"], r["description"], r["language"], r["stars"],
             r["category"], score, reason, today, r["pushed_at"], r.get("license", ""), biz, tipo))
    con.commit()

    print("[3/5] verdetto compatibilita (repo rilevanti)...")
    profile = machine.get()
    thr = CFG.get("verdict_min_score", 5)
    todo = con.execute(
        "SELECT full_name,description,language FROM repos "
        "WHERE first_seen=? AND score>=? AND (verdict IS NULL OR verdict='') "
        "ORDER BY score DESC LIMIT ?", (today, thr, CFG["max_report"])).fetchall()
    for i, (fn, desc, lang) in enumerate(todo, 1):
        v = advisor.assess(fn, desc or "", lang or "", token=GH_TOKEN, profile=profile,
                           ollama_url=CFG["ollama_url"], model=CFG["modello"])
        print(f"      [{i}/{len(todo)}] {fn} -> {v['compat'].upper()}")
        con.execute("UPDATE repos SET verdict=? WHERE full_name=?",
                    (json.dumps(v, ensure_ascii=False), fn))
    con.commit()

    print("[4/5] aggiorno cyber + PC + blockchain + crypto + mercato + idee...")
    import cyber, tips, blockchain, ideas, crypto, mercato, weekly, disco
    cy = cyber.get(refresh=True)
    tips.get(refresh=True)
    blockchain.get(refresh=True, token=GH_TOKEN)
    crypto.get(refresh=True)
    print("      scan disco...")
    dk = disco.get(refresh=True, max_age_h=20)   # riusa se scansionato da <20h
    dd = dk.get("disco", {})
    if dd.get("free_gb") is not None:
        con.execute("INSERT OR REPLACE INTO disco_snap(day,free_gb,tot_gb) VALUES(?,?,?)",
                    (today, dd["free_gb"], dd["tot_gb"]))
        con.commit()
    mk = mercato.get(refresh=True)
    mk = mercato.analyze(mk, ollama_url=CFG["ollama_url"], model=CFG["modello"])
    mercato.CACHE.write_text(json.dumps(mk, ensure_ascii=False), encoding="utf-8")
    gh_cards = con.execute("SELECT full_name,reason FROM repos WHERE first_seen=? ORDER BY score DESC LIMIT 12",
                           (today,)).fetchall()
    idee = ideas.generate([{"full_name": f, "description": r} for f, r in gh_cards], cy, mercato=mk,
                          profile=profile, ollama_url=CFG["ollama_url"], model=CFG["modello"],
                          per_angolo=CFG.get("idee_per_angolo", 5))
    if idee:
        import verify
        print(f"      {len(idee)} idee generate; verifico sul web le prime 15...")
        verify.enrich(idee[:15])   # cap: la verifica web e' lenta, il resto resta senza check
        ideas.CACHE.write_text(json.dumps(idee, ensure_ascii=False), encoding="utf-8")

    # memoria: snapshot di oggi (mercato + idee) per il diff "cosa e cambiato"
    for t in mk:
        for it in (t.get("items") or []):
            con.execute("INSERT OR IGNORE INTO mercato_snap(day,topic,title) VALUES(?,?,?)",
                        (today, t["topic"], it.get("title", "")))
    for d in (idee or ideas.get()):
        con.execute("INSERT OR IGNORE INTO idee_snap(day,titolo,novelta) VALUES(?,?,?)",
                    (today, d.get("titolo", ""), d.get("novelta", "")))
    con.commit()

    if datetime.date.today().weekday() == 0:  # lunedi: report settimanale
        print("      report settimanale...")
        weekly.generate(ollama_url=CFG["ollama_url"], model=CFG["modello"])

    print("[5/5] render dashboard...")
    render(con)
    print(f"    fatto -> {DASH}")

    # notifiche desktop: repo top di oggi + minacce che ti riguardano
    import notify
    top = con.execute("SELECT full_name FROM repos WHERE first_seen=? AND score>=8 "
                      "ORDER BY score DESC LIMIT 3", (today,)).fetchall()
    ransom = [c for c in cy if c.get("ransomware") and c.get("date", "") >= since(3)]
    relevant = [c for c in cyber.personalize(cy, profile) if c.get("relevant")]
    lines = []
    if top:
        lines.append(f"{len(top)} repo top: " + ", ".join(f.split('/')[-1] for (f,) in top))
    if ransom:
        lines.append(f"{len(ransom)} ransomware attivi")
    if relevant:
        lines.append(f"{len(relevant)} vulnerabilita sul tuo software")
    ch = changes(con, today)
    KW = ("crollo", "crolla", "record", "sanzion", "guerra", "allarme", "default", "falliment", "boom", "impenna")
    strong = [e for e in ch["eventi"] if any(k in e["title"].lower() for k in KW)]
    newhi = [d for d in ch["idee"] if d.get("novelta", "").lower() == "alta"]
    if strong:
        lines.append(f"evento forte: {strong[0]['title'][:45]}")
    if newhi:
        lines.append(f"{len(newhi)} nuove idee ad alta novita")
    alert_pct = CFG.get("disco_alert_pct", 12)
    if dd.get("free_pct") is not None and dd["free_pct"] < alert_pct:
        lines.insert(0, f"DISCO BASSO: {dd['free_pct']}% liberi ({dd['free_gb']}GB) - liberabili ~{dk.get('liberabile_gb')}GB")
    if lines:
        notify.toast("J.A.R.V.I.S. - report", "  |  ".join(lines))

    if "--open" in sys.argv or "-o" in sys.argv:
        webbrowser.open(DASH.as_uri())


if __name__ == "__main__":
    main()
