"""Nuovo cruscotto pulito (riparto da zero, look moderno/calmo, anti-slop).
Riusa la pipeline dati di agent.py (build_payload) e i font embeddati.
Genera app.html, servito da server.py su /app.

Design Read: dashboard prodotto, centro comando personale per un power-user.
Vibe Linear/Vercel-clean con taglio warm-tech. Dial VARIANCE 3 / MOTION 3 / DENSITY 5.
Un accento (indaco), un sistema di raggi (container 14 / controlli 10 / pill full),
un font (Space Grotesk), auto light/dark, motion sottile + reduced-motion.

I tool personali (Spesa, Nutrizione, Investimenti) sono client-side (localStorage):
single-user locale = zero backend, zero migrazioni DB.
ponytail: localStorage; se un giorno servisse multi-device, si aggiunge un endpoint.
"""
import json
import sqlite3
import agent


# ---- Generatore temi (DRY): da poche tinte deriva l'intero set di token ----
def _hx(c):
    c = c.lstrip("#")
    return tuple(int(c[i:i + 2], 16) for i in (0, 2, 4))


def _mix(a, b, t):
    return "#%02x%02x%02x" % tuple(round(x + (y - x) * t) for x, y in zip(_hx(a), _hx(b)))


def _dark_theme(id_, label, tag, bg, acc, accp, extra="", txt="#f0f0f5"):
    W, K = "#ffffff", "#000000"
    d = {"bg": bg, "panel": _mix(bg, W, .05), "panel2": _mix(bg, W, .09), "hover": _mix(bg, W, .13),
         "inset": _mix(bg, K, .35), "line": _mix(bg, W, .12), "line2": _mix(bg, W, .19),
         "txt": txt, "mut": _mix(txt, bg, .42), "faint": _mix(txt, bg, .60),
         "acc": acc, "acc-press": accp, "acc-soft": _mix(bg, acc, .16), "acc-line": _mix(bg, acc, .36)}
    css = f":root[data-theme={id_}]{{" + "".join(f"--{k}:{v};" for k, v in d.items()) + extra + "}"
    js = "{id:'%s',label:'%s',dots:['%s','%s','%s']%s}" % (id_, label, bg, acc, txt, (",tag:'%s'" % tag if tag else ""))
    return css, js


# (id, label, tag, bg, acc, acc-press[, extra-css])
_XTHEMES = [
    ("oceano", "Oceano", "", "#071019", "#29b6f6", "#4fc3f7"),
    ("foresta", "Foresta", "", "#0a140d", "#4caf50", "#66bb6a"),
    ("rubino", "Rubino", "acceso", "#150a0c", "#e53957", "#ff5c78"),
    ("ametista", "Ametista", "", "#100a18", "#9c5cff", "#b388ff"),
    ("oro", "Oro", "", "#14110a", "#d4af37", "#e6c65a"),
    ("menta", "Menta", "", "#07130f", "#26c6a5", "#4fd8bd"),
    ("corallo", "Corallo", "", "#16100c", "#ff7a59", "#ff9776"),
    ("ciano", "Ciano", "acceso", "#06121a", "#00d0ff", "#52e0ff"),
    ("rosa", "Rosa", "", "#160a12", "#ff5fa2", "#ff86bb"),
    ("lime", "Lime", "acceso", "#0d1407", "#a8e05f", "#c2ec86"),
    ("cielo", "Cielo notturno", "", "#080c18", "#6c8cff", "#93a8ff"),
    ("terracotta", "Terracotta", "", "#140f0b", "#c17a4a", "#d99a6e"),
    ("grafite", "Grafite", "", "#101012", "#8b93a0", "#a6adba"),
    ("lavanda", "Lavanda", "", "#0e0c15", "#b39ddb", "#cbb8e8"),
    ("acquamarina", "Acquamarina", "", "#071312", "#1de9b6", "#52efc7"),
    ("mezzanotte", "Mezzanotte", "", "#05060a", "#5865f2", "#7b86f6"),
    ("caffe", "Caffe", "", "#120d0a", "#b5835a", "#cfa07a"),
    ("ghiaccio", "Ghiaccio", "", "#0a1116", "#7fd4e8", "#a6e5f2"),
    ("vulcano", "Vulcano", "dinamico", "#140806", "#ff5722", "#ff7d4d"),
    ("minecraft", "Minecraft", "gioco", "#0c1207", "#5d9c3c", "#7cc04f",
     "--rc:3px;--rk:3px;--line:#3a2a1a;--line2:#5a4028;--panel:#161d10;--panel2:#1e2915;--acc-soft:#20300f;--acc-line:#3e5c22"),
]


def _themes_css():
    return "\n".join(_dark_theme(*t)[0] for t in _XTHEMES)


def _themes_js():
    return ",".join(_dark_theme(*t)[1] for t in _XTHEMES)


def render_ui(con=None):
    if con is None:
        con = sqlite3.connect(agent.DB)
    payload = agent.build_payload(con)
    html = (TEMPLATE
            .replace("__PAYLOAD__", json.dumps(payload, ensure_ascii=False))
            .replace("__UPDATED__", payload.get("updated", ""))
            .replace("/*__XTHEMES_CSS__*/", _themes_css())
            .replace("/*__XTHEMES_JS__*/", _themes_js())
            .replace("/*__FONT__*/", agent._font_css()))
    out = agent.ROOT / "app.html"
    out.write_text(html, encoding="utf-8")
    return out


TEMPLATE = r"""<!doctype html><html lang="it"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>miAi</title>
<link rel="manifest" href="/manifest.webmanifest">
<meta name="theme-color" content="#0a0a0d">
<link rel="apple-touch-icon" href="/icon.svg">
<script>(function(){try{var t=JSON.parse(localStorage.getItem('theme'));var m={dark:'scuro',light:'chiaro'};t=m[t]||t;document.documentElement.setAttribute('data-theme',t||'scuro');}catch(e){document.documentElement.setAttribute('data-theme','scuro');}})();</script>
<style>
/*__FONT__*/
/* ===== TOKEN CONTRACT: ogni tema ridefinisce questi. Base = Scuro. ===== */
:root{
  --bg:#0a0a0d;--panel:#131318;--panel2:#191920;--hover:#20202a;--inset:#101015;
  --line:#242430;--line2:#2e2e3c;--txt:#f2f2f6;--mut:#9a9aa8;--faint:#63636f;
  --acc:#8a8cf7;--acc-press:#a0a2fb;--acc-soft:#1c1c2e;--acc-line:#31314e;
  --green:#43d391;--green-soft:#122019;--red:#f4756b;--red-soft:#221315;--amber:#e0a63a;--amber-soft:#221c10;
  --rc:14px;--rk:10px;--pill:999px;--font:'Space Grotesk',system-ui,-apple-system,'Segoe UI',sans-serif;
  --ease:cubic-bezier(.16,1,.3,1);
  --sh1:0 1px 2px rgba(0,0,0,.4);
  --sh2:0 1px 2px rgba(0,0,0,.4),0 16px 34px -18px rgba(0,0,0,.7);
  --ring:0 0 0 3px var(--acc-soft)}
/* 1. Chiaro */
:root[data-theme=chiaro]{
  --bg:#fafafb;--panel:#fff;--panel2:#f4f4f6;--hover:#f0f0f3;--inset:#f7f7f9;
  --line:#e8e8ee;--line2:#dedee6;--txt:#141419;--mut:#6d6d78;--faint:#a0a0ad;
  --acc:#5b5ef0;--acc-press:#4a4ce0;--acc-soft:#edeefe;--acc-line:#d6d8fb;
  --green:#0f9d63;--green-soft:#e6f6ee;--red:#e0483f;--red-soft:#fceceb;--amber:#c07807;--amber-soft:#fbf0dd;
  --sh1:0 1px 2px rgba(24,24,40,.05);--sh2:0 1px 3px rgba(24,24,40,.06),0 12px 28px -14px rgba(24,24,40,.16)}
/* 2. Scuro = base, nessun override */
/* 3. Indaco (acceso) */
:root[data-theme=indaco]{--bg:#0a0a16;--panel:#141423;--panel2:#1b1b2e;--hover:#23233d;--inset:#0f0f1c;
  --line:#262640;--line2:#333356;--txt:#f0f0fb;--mut:#9d9dc0;--faint:#63637f;
  --acc:#7c7bff;--acc-press:#9d9cff;--acc-soft:#1a1a3a;--acc-line:#3a3a6a}
/* 4. Smeraldo (acceso) */
:root[data-theme=smeraldo]{--bg:#07110c;--panel:#0e1b14;--panel2:#12241a;--hover:#193227;--inset:#0a1610;
  --line:#193026;--line2:#245038;--txt:#e9f6ef;--mut:#8caf9d;--faint:#587567;
  --acc:#1fd982;--acc-press:#38ef99;--acc-soft:#0c251a;--acc-line:#1d4d37}
/* 5. Tramonto (dinamico) */
:root[data-theme=tramonto]{--bg:#140c0d;--panel:#20140f;--panel2:#2a1a13;--hover:#382018;--inset:#180f0e;
  --line:#3a2019;--line2:#5a3124;--txt:#fbeee7;--mut:#c19a8b;--faint:#82635a;
  --acc:#ff6a3d;--acc-press:#ff875f;--acc-soft:#2c1610;--acc-line:#5a2b1c;
  --red:#ff5470;--red-soft:#2a1218;--amber:#ffb454;--amber-soft:#2a1d0f}
/* 6. Aurora (dinamico) */
:root[data-theme=aurora]{--bg:#070912;--panel:#101421;--panel2:#161c2e;--hover:#1f2740;--inset:#0b0e18;
  --line:#1e2740;--line2:#2c3a5c;--txt:#eaf0fb;--mut:#92a2c2;--faint:#5c6c8a;
  --acc:#39e0cb;--acc-press:#63f0dc;--acc-soft:#0c2028;--acc-line:#1d4a4a}
/* 7. Neon (acceso) */
:root[data-theme=neon]{--bg:#04050a;--panel:#0b0d15;--panel2:#11131f;--hover:#181b2b;--inset:#080a11;
  --line:#181c2c;--line2:#26304a;--txt:#eafcff;--mut:#84a6c2;--faint:#4e6a82;
  --acc:#00e5ff;--acc-press:#5cf0ff;--acc-soft:#07202a;--acc-line:#0e4a5c;
  --green:#3dffb0;--green-soft:#04231a;--red:#ff5c8a;--red-soft:#25101a;--amber:#ffd84d;--amber-soft:#231e08}
/* 8. Vetro (3D) */
:root[data-theme=vetro]{--bg:#0b1020;--panel:rgba(255,255,255,.06);--panel2:rgba(255,255,255,.05);--hover:rgba(255,255,255,.1);--inset:rgba(255,255,255,.04);
  --line:rgba(255,255,255,.13);--line2:rgba(255,255,255,.2);--txt:#eef2fb;--mut:#b3bdd6;--faint:#828db0;
  --acc:#8ab0ff;--acc-press:#a9c6ff;--acc-soft:rgba(138,176,255,.16);--acc-line:rgba(138,176,255,.42)}
/* 9. Ambra (3D) */
:root[data-theme=ambra]{--bg:#14100a;--panel:#1f1810;--panel2:#291f14;--hover:#38291a;--inset:#191307;
  --line:#352a1a;--line2:#4d3d24;--txt:#f8efdc;--mut:#bba884;--faint:#7d6e50;
  --acc:#f5a524;--acc-press:#ffbe4d;--acc-soft:#251a0c;--acc-line:#4d3a1c;
  --sh1:0 2px 4px rgba(0,0,0,.5);--sh2:8px 8px 22px rgba(0,0,0,.55),-5px -5px 14px rgba(255,255,255,.03)}
/* 10. Spider-Man (eroe) */
:root[data-theme=spiderman]{--bg:#0a0e18;--panel:#111726;--panel2:#161d30;--hover:#1f2942;--inset:#0c1120;
  --line:#20293f;--line2:#2e3b58;--txt:#f2f5fc;--mut:#93a2c4;--faint:#5a6a8c;
  --acc:#e01b2c;--acc-press:#ff2f42;--acc-soft:#220a10;--acc-line:#5a1a24;
  --green:#37d38a;--green-soft:#0c2119;--red:#ff4d5e;--red-soft:#241216;--amber:#ffb43a;--amber-soft:#241a0d}
/*__XTHEMES_CSS__*/

*{box-sizing:border-box}
html,body{margin:0;height:100%}
body{background:var(--bg);color:var(--txt);font-family:var(--font);font-size:14.5px;line-height:1.5;letter-spacing:-.006em;position:relative;
  -webkit-font-smoothing:antialiased;text-rendering:optimizeLegibility;transition:background .35s ease,color .35s ease}
.fx{position:fixed;inset:0;z-index:-1;pointer-events:none;background:var(--bg)}
.num{font-variant-numeric:tabular-nums;font-feature-settings:"tnum" 1}
a{color:inherit;text-decoration:none}
svg{width:18px;height:18px;flex:none;stroke-width:1.75}
:focus-visible{outline:none;box-shadow:var(--ring);border-radius:8px}
::-webkit-scrollbar{width:11px;height:11px}
::-webkit-scrollbar-thumb{background:var(--line2);border-radius:20px;border:3px solid var(--bg);background-clip:padding-box}
::-webkit-scrollbar-thumb:hover{background:var(--faint)}
@keyframes rise{from{opacity:0;transform:translateY(9px)}to{opacity:1;transform:none}}
@media (prefers-reduced-motion:no-preference){
  .kpis,.grid,.two,.panel,.soon,.section-lead{animation:rise .5s var(--ease) both}
  .kpi{animation:rise .5s var(--ease) both}
  .kpi:nth-child(2){animation-delay:.05s}.kpi:nth-child(3){animation-delay:.1s}.kpi:nth-child(4){animation-delay:.15s}
  .grid .card{animation:rise .55s var(--ease) both}
  .grid .card:nth-child(2){animation-delay:.03s}.grid .card:nth-child(3){animation-delay:.06s}
  .grid .card:nth-child(4){animation-delay:.09s}.grid .card:nth-child(5){animation-delay:.12s}
  .grid .card:nth-child(6){animation-delay:.15s}.grid .card:nth-child(7){animation-delay:.17s}
  .grid .card:nth-child(8){animation-delay:.19s}
}

/* ---------- layout ---------- */
.app{display:grid;grid-template-columns:256px minmax(0,1fr);min-height:100vh}
.side{position:sticky;top:0;height:100vh;display:flex;flex-direction:column;gap:2px;
  padding:20px 14px 16px;background:var(--panel);border-right:1px solid var(--line);overflow-y:auto}
.brand{display:flex;align-items:center;gap:12px;padding:4px 8px 18px}
.brand .logo{width:36px;height:36px;border-radius:11px;flex:none;display:grid;place-items:center;color:#fff;
  background:linear-gradient(145deg,var(--acc),color-mix(in srgb,var(--acc) 55%,#c9b7ff));box-shadow:0 6px 18px -7px var(--acc)}
.brand .logo svg{width:19px;height:19px;stroke-width:2.1}
.brand b{font-size:15.5px;font-weight:600;letter-spacing:-.01em;display:block}
.brand small{color:var(--faint);font-size:10.5px;font-weight:600;letter-spacing:.09em;text-transform:uppercase}
.navgrp{margin:14px 0 4px;padding:0 10px;color:var(--faint);font-size:10.5px;font-weight:600;letter-spacing:.11em;text-transform:uppercase}
.nav{position:relative;display:flex;align-items:center;gap:12px;width:100%;padding:9px 12px;border:none;border-radius:var(--rk);
  background:none;color:var(--mut);font:inherit;font-size:14px;cursor:pointer;text-align:left;transition:background .15s,color .15s}
.nav svg{width:18px;height:18px;color:var(--faint);transition:color .15s}
.nav:hover{background:var(--hover);color:var(--txt)}.nav:hover svg{color:var(--mut)}
.nav.on{background:var(--acc-soft);color:var(--acc);font-weight:600}
.nav.on svg{color:var(--acc)}
.nav.on::before{content:"";position:absolute;left:-14px;top:50%;transform:translateY(-50%);width:3px;height:20px;
  border-radius:0 3px 3px 0;background:var(--acc)}
.nav .cnt{margin-left:auto;font-size:11.5px;font-weight:600;color:var(--faint);background:var(--panel2);
  padding:2px 9px;border-radius:var(--pill);min-width:24px;text-align:center;transition:.15s}
.nav:hover .cnt{background:var(--panel)}
.nav.on .cnt{color:var(--acc);background:color-mix(in srgb,var(--acc) 12%,transparent)}
.side-foot{margin-top:auto;padding-top:16px;display:flex;flex-direction:column;gap:8px}
.chip{display:flex;align-items:center;gap:10px;width:100%;padding:10px 12px;border:1px solid var(--line);
  border-radius:var(--rk);background:var(--panel2);color:var(--mut);font:inherit;font-size:13px;cursor:pointer;transition:.15s}
.chip:hover{background:var(--hover);border-color:var(--line2)}
.chip svg{width:16px;height:16px}
.chip .dot{width:8px;height:8px;border-radius:50%;background:var(--faint);flex:none;transition:.2s}
.chip.on .dot{background:var(--green);box-shadow:0 0 0 3px var(--green-soft)}
.chip.off .dot{background:var(--red);box-shadow:0 0 0 3px var(--red-soft)}
.chip .sw{margin-left:auto;font-size:10.5px;font-weight:600;letter-spacing:.05em;color:var(--faint);text-transform:uppercase}

.main{min-width:0;display:flex;flex-direction:column}
.topbar{position:sticky;top:0;z-index:5;display:flex;align-items:center;gap:14px;padding:18px 32px;
  background:color-mix(in srgb,var(--bg) 80%,transparent);backdrop-filter:saturate(180%) blur(14px);border-bottom:1px solid var(--line)}
.topbar h1{margin:0;font-size:20px;font-weight:600;letter-spacing:-.02em}
.topbar .desc{color:var(--mut);font-size:13px;margin-top:3px;max-width:60ch}
.topbar .sp{flex:1}
.langwrap{position:relative}
.langbtn{border-radius:50%!important;font-size:18px;line-height:1;overflow:hidden}
.langpop{position:absolute;top:46px;right:0;z-index:40;width:230px;max-height:60vh;overflow-y:auto;
  background:var(--panel);border:1px solid var(--line);border-radius:14px;box-shadow:var(--sh2,0 12px 40px rgba(0,0,0,.4));
  padding:6px;display:none}
.langpop.on{display:block}
.langpop .lopt{display:flex;align-items:center;gap:10px;width:100%;padding:9px 11px;border:0;background:none;
  color:var(--txt);border-radius:9px;cursor:pointer;font-size:13.5px;text-align:left}
.langpop .lopt:hover{background:var(--hover,rgba(127,127,127,.12))}
.langpop .lopt.on{background:var(--acc);color:#fff}
.langpop .lopt .fl{font-size:17px}
.langpop .lsearch{width:100%;padding:8px 11px;margin-bottom:6px;border:1px solid var(--line);border-radius:9px;
  background:var(--bg);color:var(--txt);font-size:13px}
.search{display:flex;align-items:center;gap:9px;padding:9px 14px;border:1px solid var(--line);border-radius:var(--pill);
  background:var(--panel);min-width:250px;box-shadow:var(--sh1);transition:.15s}
.search:focus-within{border-color:var(--acc-line);box-shadow:var(--ring)}
.search svg{width:16px;height:16px;color:var(--faint)}
.search input{border:none;background:none;color:var(--txt);font:inherit;font-size:14px;width:100%;outline:none}
.search input::placeholder{color:var(--faint)}
.iconbtn{display:grid;place-items:center;width:42px;height:42px;border:1px solid var(--line);border-radius:var(--rk);
  background:var(--panel);color:var(--mut);cursor:pointer;transition:.15s;box-shadow:var(--sh1)}
.iconbtn:hover{color:var(--acc);border-color:var(--acc-line);background:var(--panel)}
.iconbtn:active{transform:translateY(1px)}.iconbtn svg{width:18px;height:18px}
.iconbtn.spin svg{animation:spin .8s linear infinite}
@keyframes spin{to{transform:rotate(360deg)}}
.content{padding:28px 32px 72px;max-width:1360px;width:100%}

/* ---------- KPI ---------- */
.kpis{display:grid;grid-template-columns:repeat(auto-fit,minmax(190px,1fr));gap:16px;margin-bottom:26px}
.kpi{background:var(--panel);border:1px solid var(--line);border-radius:var(--rc);padding:18px 20px;box-shadow:var(--sh1)}
.kpi .k{color:var(--mut);font-size:12.5px;font-weight:500}
.kpi .v{font-size:31px;font-weight:600;margin-top:7px;letter-spacing:-.03em;line-height:1}
.kpi .v small{font-size:14px;color:var(--faint);font-weight:500;letter-spacing:0}
.kpi.a .v{color:var(--acc)}.kpi.g .v{color:var(--green)}.kpi.r .v{color:var(--red)}.kpi.am .v{color:var(--amber)}

/* ---------- toolbar / controls ---------- */
.toolbar{display:flex;flex-wrap:wrap;gap:12px;margin-bottom:22px;align-items:flex-end}
.fld{display:flex;flex-direction:column;gap:6px}
.fld label{font-size:11px;color:var(--faint);font-weight:600;letter-spacing:.04em;text-transform:uppercase;padding-left:2px}
.inp,select.inp{padding:9px 13px;border:1px solid var(--line);border-radius:var(--rk);background:var(--panel);
  color:var(--txt);font:inherit;font-size:14px;outline:none;transition:.15s;min-width:150px}
.inp::placeholder{color:var(--faint)}
.inp:focus{border-color:var(--acc-line);box-shadow:var(--ring)}
select.inp{cursor:pointer;appearance:none;padding-right:34px;
  background-image:url("data:image/svg+xml;utf8,<svg xmlns='http://www.w3.org/2000/svg' width='16' height='16' fill='none' stroke='%23a0a0ad' stroke-width='1.9' stroke-linecap='round' stroke-linejoin='round'><path d='m4 6 4 4 4-4'/></svg>");
  background-repeat:no-repeat;background-position:right 11px center}

/* ---------- cards ---------- */
.grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(440px,1fr));gap:16px}
@media(max-width:1560px){.grid{grid-template-columns:repeat(auto-fill,minmax(380px,1fr))}}
.card{background:var(--panel);border:1px solid var(--line);border-radius:var(--rc);padding:20px 22px;
  box-shadow:var(--sh1);transition:transform .18s var(--ease),box-shadow .18s,border-color .18s;display:flex;flex-direction:column;gap:13px}
.card:hover{box-shadow:var(--sh2);border-color:var(--line2);transform:translateY(-3px)}
.card .ch{display:flex;align-items:flex-start;gap:14px}
.card .ct{font-size:16.5px;font-weight:600;line-height:1.32;letter-spacing:-.015em;word-break:break-word}
.card .ct a:hover{color:var(--acc)}
.card .score{margin-left:auto;flex:none;display:grid;place-items:center;width:46px;height:46px;border-radius:12px;
  font-size:18px;font-weight:600;letter-spacing:-.02em;background:var(--acc-soft);color:var(--acc)}
.card .score.hi{background:var(--green-soft);color:var(--green)}
.card .desc{color:var(--mut);font-size:13.5px;line-height:1.55;display:-webkit-box;-webkit-line-clamp:2;-webkit-box-orient:vertical;overflow:hidden}
.tags{display:flex;flex-wrap:wrap;gap:7px}
.tag{font-size:11.5px;font-weight:500;padding:3px 11px;border-radius:var(--pill);background:var(--panel2);color:var(--mut);border:1px solid transparent}
.tag.acc{background:var(--acc-soft);color:var(--acc)}
.tag.g{background:var(--green-soft);color:var(--green)}
.tag.r{background:var(--red-soft);color:var(--red)}
.tag.am{background:var(--amber-soft);color:var(--amber)}
.meta{display:flex;flex-wrap:wrap;gap:18px;color:var(--mut);font-size:13px}
.meta b{color:var(--txt);font-weight:600}
.cfoot{display:flex;align-items:center;gap:10px;margin-top:auto;padding-top:14px;border-top:1px solid var(--line)}
.btn{display:inline-flex;align-items:center;gap:7px;padding:8px 14px;border:1px solid var(--line);border-radius:var(--rk);
  background:var(--panel);color:var(--txt);font:inherit;font-size:13.5px;font-weight:500;cursor:pointer;transition:.15s}
.btn:hover{border-color:var(--acc-line);color:var(--acc);background:var(--panel)}
.btn:active{transform:translateY(1px)}
.btn.pri{background:var(--acc);border-color:var(--acc);color:#fff}
.btn.pri:hover{background:var(--acc-press);border-color:var(--acc-press);color:#fff}
.btn svg{width:15px;height:15px}
.star{margin-left:auto;background:none;border:none;color:var(--faint);cursor:pointer;padding:5px;display:grid;place-items:center;border-radius:9px;transition:.15s}
.star:hover{background:var(--hover);color:var(--amber)}
.star svg{width:20px;height:20px}.star.on{color:var(--amber)}.star.on svg{fill:currentColor}
.section-lead{color:var(--mut);font-size:14px;line-height:1.6;margin:-6px 0 22px;max-width:70ch}
.section-lead b{color:var(--txt);font-weight:600}
.empty{padding:64px 20px;text-align:center;color:var(--faint);font-size:14.5px}
.soon{margin-top:6px;padding:60px 34px;text-align:center;background:var(--panel);border:1px dashed var(--line2);border-radius:var(--rc)}
.soon .ic{width:52px;height:52px;margin:0 auto;border-radius:15px;display:grid;place-items:center;background:var(--acc-soft);color:var(--acc)}
.soon .ic svg{width:24px;height:24px}
.soon h3{margin:18px 0 7px;font-size:19px;font-weight:600;letter-spacing:-.02em;color:var(--txt)}
.soon p{margin:0 auto;color:var(--mut);max-width:460px;line-height:1.6}

/* ---------- Spesa ---------- */
.two{display:grid;grid-template-columns:minmax(0,1fr) 330px;gap:20px;align-items:start}
@media(max-width:880px){.two{grid-template-columns:1fr}}
.panel{background:var(--panel);border:1px solid var(--line);border-radius:var(--rc);box-shadow:var(--sh1);overflow:hidden}
.panel-h{display:flex;align-items:center;gap:11px;padding:17px 22px;border-bottom:1px solid var(--line);font-weight:600;font-size:15px;letter-spacing:-.01em}
.panel-h svg{width:18px;height:18px;color:var(--acc)}
.panel-h .cnt{margin-left:auto;color:var(--faint);font-size:13px;font-weight:500;letter-spacing:0}
.panel-b{padding:16px 22px 22px}
.addrow{display:flex;gap:10px;margin-bottom:10px}
.addrow .inp{flex:1;min-width:0}
.slist{list-style:none;margin:0;padding:0}
.sitem{display:flex;align-items:center;gap:13px;padding:12px 4px;border-bottom:1px solid var(--line)}
.sitem:last-child{border-bottom:none}
.sitem .cb{width:21px;height:21px;flex:none;border:2px solid var(--line2);border-radius:7px;cursor:pointer;display:grid;place-items:center;color:#fff;transition:.15s}
.sitem .cb:hover{border-color:var(--acc)}
.sitem.done .cb{background:var(--acc);border-color:var(--acc)}
.sitem .cb svg{width:13px;height:13px;opacity:0;stroke-width:3}.sitem.done .cb svg{opacity:1}
.sitem .nm{flex:1;font-size:14.5px;transition:.15s}.sitem.done .nm{color:var(--faint);text-decoration:line-through}
.sitem .qty{color:var(--mut);font-size:13px}
.sitem .del{background:none;border:none;color:var(--faint);cursor:pointer;padding:5px;border-radius:8px;opacity:0;transition:.15s}
.sitem:hover .del{opacity:1}.sitem .del:hover{color:var(--red);background:var(--red-soft)}.sitem .del svg{width:16px;height:16px}
.sactions{display:flex;gap:10px;margin-top:18px;flex-wrap:wrap}
.tpl{display:flex;align-items:center;gap:10px;padding:12px 14px;border:1px solid var(--line);border-radius:var(--rk);margin-bottom:10px;background:var(--inset)}
.tpl .tn{flex:1;font-weight:500;font-size:14px}.tpl .tc{color:var(--faint);font-size:12.5px;margin-top:2px}
.tpl button{background:none;border:none;color:var(--mut);cursor:pointer;font:inherit;font-size:13px;font-weight:500;padding:6px 10px;border-radius:8px;transition:.15s}
.tpl button:hover{background:var(--hover);color:var(--acc)}
.mini{font-size:12.5px;color:var(--faint);line-height:1.6}

/* note azione (cyber), liste (mercato/disco) */
.note{border-left:2px solid var(--acc);padding:3px 0 3px 12px;color:var(--txt);font-size:13.5px;line-height:1.55}
.note b{color:var(--acc);font-weight:600}
.mlist{list-style:none;margin:0;padding:0;display:flex;flex-direction:column;gap:9px}
.mlist a{display:block;color:var(--mut);font-size:13.5px;line-height:1.45;padding-left:15px;position:relative}
.mlist a::before{content:"";position:absolute;left:0;top:7px;width:5px;height:5px;border-radius:50%;background:var(--acc)}
.mlist a:hover{color:var(--acc)}
.frow{display:flex;align-items:center;gap:14px;padding:12px 4px;border-bottom:1px solid var(--line)}
.frow:last-child{border-bottom:none}
.frow .fmain{flex:1;min-width:0}
.frow .fn{font-size:14px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;font-weight:500}
.frow .fp{color:var(--faint);font-size:12px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;margin-top:2px}
.frow .fg{color:var(--txt);font-weight:600;font-size:14px;flex:none}
.dbar{height:6px;border-radius:6px;background:var(--panel2);overflow:hidden;margin-top:7px}
.dbar i{display:block;height:100%;background:var(--acc);border-radius:6px}
.cvdrop{border:1.5px dashed var(--line2);border-radius:var(--rk);padding:40px 20px;text-align:center;cursor:pointer;transition:.2s;color:var(--mut)}
.cvdrop:hover{border-color:var(--acc);background:var(--hover);color:var(--txt)}
.cvdrop svg{width:34px;height:34px;stroke-width:1.5;margin-bottom:10px;color:var(--acc)}
.cvdrop b{display:block;font-size:15px;color:var(--txt);margin-bottom:4px}
.cvhead{display:flex;align-items:center;gap:24px;flex-wrap:wrap}
.cvscore{flex:none;width:120px;height:120px;border-radius:50%;display:flex;flex-direction:column;align-items:center;justify-content:center;font-weight:700;background:conic-gradient(var(--sc) calc(var(--p)*1%),var(--panel2) 0)}
.cvscore .in{width:96px;height:96px;border-radius:50%;background:var(--panel);display:flex;flex-direction:column;align-items:center;justify-content:center}
.cvscore .n{font-size:32px;line-height:1;color:var(--sc)}
.cvscore .l{font-size:10px;color:var(--faint);letter-spacing:.08em;text-transform:uppercase;margin-top:3px}
.cvsub{display:grid;grid-template-columns:repeat(auto-fit,minmax(160px,1fr));gap:12px;margin-top:16px}
.cvsub .s .k{display:flex;justify-content:space-between;font-size:12.5px;color:var(--mut);margin-bottom:2px}
.cvrw{padding:12px 4px;border-bottom:1px solid var(--line)}
.cvrw:last-child{border-bottom:none}
.cvrw .pre{color:var(--red);font-size:13px;text-decoration:line-through;opacity:.75}
.cvrw .post{color:var(--green);font-size:13.5px;margin-top:4px;font-weight:500}
.cvprob .g{font-size:13px;color:var(--faint);margin-top:3px}
/* CyberQuest */
.cgnote{display:flex;gap:12px;align-items:flex-start;padding:14px 16px;margin-bottom:16px;border-radius:12px;background:var(--acc-soft);border:1px solid var(--acc-line);color:var(--txt);font-size:13.5px;line-height:1.5}
.cgnote svg{width:20px;height:20px;flex:none;color:var(--acc);margin-top:1px}
.cgtop{display:flex;align-items:center;gap:18px;flex-wrap:wrap;margin-bottom:20px}
.cgrank{flex:none;display:flex;align-items:center;gap:12px}
.cgrank .rico{width:52px;height:52px;border-radius:14px;display:flex;align-items:center;justify-content:center;background:var(--acc-soft);color:var(--acc)}
.cgrank .rico svg{width:26px;height:26px}
.cgrank .rn{font-size:16px;font-weight:600}.cgrank .rx{font-size:12px;color:var(--faint)}
.cgxp{flex:1;min-width:160px}
.cgxp .xt{display:flex;justify-content:space-between;font-size:12px;color:var(--mut);margin-bottom:4px}
.cgstat{flex:none;display:flex;gap:16px}
.cgstat .st{display:flex;align-items:center;gap:6px;font-weight:600;font-size:15px}
.cgstat .st svg{width:18px;height:18px}
.cgstat .st.hp{color:var(--red)}.cgstat .st.fl{color:var(--amber)}
.cgpath{position:relative;max-width:640px;margin:0 auto;padding:6px 0}
.cgworld{margin:26px 0 6px;display:flex;align-items:center;gap:10px;color:var(--txt)}
.cgworld .wi{width:32px;height:32px;border-radius:9px;display:flex;align-items:center;justify-content:center;flex:none}
.cgworld .wi svg{width:18px;height:18px}
.cgworld b{font-size:15px}.cgworld span{font-size:12px;color:var(--faint)}
.cgrow{display:flex;justify-content:center;padding:9px 0}
.cgnode{width:62px;height:62px;border-radius:50%;border:none;cursor:pointer;position:relative;display:flex;align-items:center;justify-content:center;
 background:var(--panel2);color:var(--faint);font-weight:700;font-size:16px;transition:transform .12s;box-shadow:0 3px 0 var(--line)}
.cgnode:hover{transform:translateY(-2px)}
.cgnode.done{background:var(--green);color:#fff;box-shadow:0 3px 0 rgba(0,0,0,.25)}
.cgnode.cur{background:var(--acc);color:#fff;box-shadow:0 0 0 4px var(--acc-soft),0 3px 0 rgba(0,0,0,.25);animation:cgpulse 1.6s infinite}
.cgnode.lock{opacity:.5;cursor:not-allowed}
.cgnode.gen{border:2px dashed var(--line2)}
.cgnode svg{width:24px;height:24px}
.cgnode .stars{position:absolute;bottom:-9px;left:50%;transform:translateX(-50%);font-size:9px;color:var(--amber);white-space:nowrap;letter-spacing:-1px}
@keyframes cgpulse{0%,100%{box-shadow:0 0 0 4px var(--acc-soft),0 3px 0 rgba(0,0,0,.25)}50%{box-shadow:0 0 0 9px transparent,0 3px 0 rgba(0,0,0,.25)}}
.cgq-opt{display:block;width:100%;text-align:left;padding:14px 16px;margin-bottom:10px;border:1.5px solid var(--line);border-radius:var(--rk);
 background:var(--panel);color:var(--txt);cursor:pointer;font-size:14.5px;transition:.15s}
.cgq-opt:hover{border-color:var(--acc);background:var(--hover)}
.cgq-opt.ok{border-color:var(--green);background:var(--green-soft);color:var(--green)}
.cgq-opt.no{border-color:var(--red);background:var(--red-soft);color:var(--red)}
.cgq-opt:disabled{cursor:default}
.cgfb{margin-top:6px;padding:14px 16px;border-radius:var(--rk);font-size:13.5px;line-height:1.5}
.cgfb.ok{background:var(--green-soft);color:var(--green)}.cgfb.no{background:var(--red-soft);color:var(--red)}
.cgfb b{display:block;margin-bottom:3px}
#cgov{position:fixed;inset:0;z-index:70;display:none;align-items:center;justify-content:center;padding:24px;background:rgba(0,0,0,.55)}
#cgov.on{display:flex}
.cgcard{width:100%;max-width:560px;background:var(--panel);border:1px solid var(--line);border-radius:var(--rl,18px);padding:24px;max-height:90vh;overflow:auto}
.cgcard .ch{display:flex;align-items:center;gap:10px;font-size:12px;color:var(--faint);text-transform:uppercase;letter-spacing:.06em;margin-bottom:12px}
.cgcard .qq{font-size:17px;font-weight:600;line-height:1.4;margin-bottom:18px}
.cginp{width:100%;padding:13px 15px;border:1.5px solid var(--line);border-radius:var(--rk);background:var(--panel2);color:var(--txt);font-size:15px}
.cgta{font-family:Consolas,ui-monospace,monospace;font-size:13.5px;line-height:1.5;resize:vertical;white-space:pre}
.cgcode{border:1px solid var(--line);border-radius:var(--rk);overflow:hidden;font-family:Consolas,ui-monospace,monospace;font-size:13px}
.cgline{display:flex;gap:12px;align-items:flex-start;padding:5px 12px;cursor:pointer;border-left:3px solid transparent}
.cgline:hover{background:var(--hover)}
.cgline .ln{color:var(--faint);user-select:none;min-width:20px;text-align:right;flex:none}
.cgline code{white-space:pre-wrap;word-break:break-word;color:var(--txt)}
.cgline.sel{background:var(--acc-soft);border-left-color:var(--acc)}
.cgline.good{background:var(--green-soft);border-left-color:var(--green)}
.cgline.wrong{background:var(--red-soft);border-left-color:var(--red)}
.cgord{display:flex;flex-direction:column;gap:8px}
.cgoi{display:flex;align-items:center;gap:12px;padding:11px 14px;border:1.5px solid var(--line);border-radius:var(--rk);background:var(--panel2)}
.cgoi .gr{color:var(--faint);display:flex}.cgoi .gr svg{width:15px;height:15px}
.cgoi .ot{flex:1;font-size:14px}
.cgoi .ob button{background:var(--panel);border:1px solid var(--line);color:var(--mut);border-radius:6px;width:26px;height:24px;cursor:pointer;font-size:10px;margin-left:4px}
.cgoi .ob button:hover{border-color:var(--acc);color:var(--acc)}
.cgoi.good{border-color:var(--green);background:var(--green-soft)}
.cgoi.wrong{border-color:var(--red);background:var(--red-soft)}
/* Assistente chat */
.chatwrap{display:flex;flex-direction:column;height:calc(100vh - 150px);min-height:420px}
.chatlog{flex:1;overflow-y:auto;padding:4px 2px 12px;display:flex;flex-direction:column;gap:12px}
.msg{max-width:80%;padding:11px 14px;border-radius:14px;font-size:14px;line-height:1.5;white-space:pre-wrap;word-break:break-word}
.msg.u{align-self:flex-end;background:var(--acc);color:#fff;border-bottom-right-radius:4px}
.msg.a{align-self:flex-start;background:var(--panel2);border:1px solid var(--line);border-bottom-left-radius:4px}
.msg.a.wait{color:var(--faint)}
.chatchips{display:flex;gap:8px;flex-wrap:wrap;margin-bottom:10px}
.chatchips .tag{cursor:pointer}.chatchips .tag:hover{background:var(--acc-soft);color:var(--acc)}
.chatin{display:flex;gap:10px;align-items:flex-end;border-top:1px solid var(--line);padding-top:12px}
.chatin textarea{flex:1;resize:none;min-height:44px;max-height:140px}
/* Agenda */
.agrow{display:flex;align-items:center;gap:14px;padding:12px 6px;border-radius:12px;transition:background .15s}
.agrow:hover{background:var(--hover)}
.agrow.done .agt{text-decoration:line-through;color:var(--faint)}
.agrow.late .agd{color:var(--red);font-weight:600}
.agmain{flex:1;min-width:0}
.agt{font-size:15px;font-weight:500}.agd{font-size:12.5px;color:var(--mut);margin-top:3px}
/* check grande */
.agck{width:30px;height:30px;border-radius:9px;border:2px solid var(--line2);background:var(--panel);cursor:pointer;flex:none;display:flex;align-items:center;justify-content:center;color:transparent;transition:.15s}
.agck:hover{border-color:var(--green)}
.agrow.done .agck,.pjtask.done .agck,.tkrow.done .agck{background:var(--green);border-color:var(--green);color:#fff}
.agck svg{width:18px;height:18px;stroke-width:3}
/* delete grande */
.agdel{width:30px;height:30px;border-radius:9px;border:1.5px solid var(--line);background:var(--panel);color:var(--faint);cursor:pointer;flex:none;display:flex;align-items:center;justify-content:center;transition:.15s}
.agdel:hover{border-color:var(--red);color:var(--red);background:var(--red-soft)}
.agdel svg{width:16px;height:16px;stroke-width:2.4}
/* Calendario */
.calbar{display:flex;align-items:center;gap:12px;margin-bottom:14px}
.calbar b{font-size:18px;flex:1;text-transform:capitalize}
.calnav{width:36px;height:36px;border-radius:10px;border:1px solid var(--line);background:var(--panel);color:var(--txt);cursor:pointer;display:flex;align-items:center;justify-content:center;font-size:18px}
.calnav:hover{border-color:var(--acc);color:var(--acc)}
.calwk{display:grid;grid-template-columns:repeat(7,1fr);gap:8px;margin-bottom:8px}
.calwk span{text-align:center;font-size:11.5px;text-transform:uppercase;letter-spacing:.05em;color:var(--faint);font-weight:600}
.calgrid{display:grid;grid-template-columns:repeat(7,1fr);gap:8px}
.calcell{min-height:88px;border:1px solid var(--line);border-radius:11px;padding:7px 8px;background:var(--panel);cursor:pointer;display:flex;flex-direction:column;gap:4px;transition:.12s;overflow:hidden}
.calcell:hover{border-color:var(--acc);background:var(--hover)}
.calcell.off{opacity:.4}
.calcell.today{border-color:var(--acc);box-shadow:inset 0 0 0 1px var(--acc)}
.calcell.sel{background:var(--acc-soft)}
.calnum{font-size:13px;font-weight:600;align-self:flex-end;color:var(--mut)}
.calcell.today .calnum{color:var(--acc)}
.calev{font-size:11px;padding:2px 6px;border-radius:6px;background:var(--acc-soft);color:var(--acc);white-space:nowrap;overflow:hidden;text-overflow:ellipsis;line-height:1.4;border-left:3px solid var(--acc)}
.calev.done{background:var(--green-soft);color:var(--green);border-left-color:var(--green);text-decoration:line-through;opacity:.8}
.calev.late{background:var(--red-soft);color:var(--red);border-left-color:var(--red)}
.calmore{font-size:10.5px;color:var(--faint);padding-left:4px}
@media(max-width:640px){.calcell{min-height:62px}.calev{display:none}.calcell::after{content:attr(data-n);font-size:9px;color:var(--acc)}}
/* Progetti & Task */
.pjgrid{display:grid;grid-template-columns:repeat(auto-fill,minmax(320px,1fr));gap:16px;margin-top:18px}
.pjcard{border:1px solid var(--line);border-radius:var(--rc,14px);padding:16px 18px;background:var(--panel);position:relative}
.pjcard.done{opacity:.75}
.pjh{display:flex;align-items:center;gap:10px;margin-bottom:6px}
.pjh b{font-size:16px;flex:1;min-width:0;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
.pjdesc{color:var(--mut);font-size:13px;line-height:1.5;margin-bottom:12px;white-space:normal}
.pjbar{height:7px;border-radius:6px;background:var(--panel2);overflow:hidden;margin:10px 0 6px}
.pjbar i{display:block;height:100%;background:var(--acc);border-radius:6px}
.pjmeta{display:flex;justify-content:space-between;font-size:12px;color:var(--faint)}
.pjtasks{margin-top:12px;border-top:1px solid var(--line);padding-top:10px}
.pjtask{display:flex;align-items:center;gap:11px;padding:7px 0;font-size:14px}
.pjtask .agck{width:26px;height:26px;border-radius:8px}.pjtask.done span{text-decoration:line-through;color:var(--faint)}
.pjtask .agck svg{width:16px;height:16px}
.pjtask span{flex:1;min-width:0}
.pjadd{display:flex;gap:8px;margin-top:10px}
.pjact{position:absolute;top:12px;right:12px;display:flex;gap:6px}
.pjact button{background:none;border:none;color:var(--faint);cursor:pointer;padding:2px}
.pjact button:hover{color:var(--acc)}.pjact svg{width:15px;height:15px}
.tkrow{display:flex;align-items:center;gap:13px;padding:13px 8px;border-radius:12px;transition:background .15s}
.tkrow:hover{background:var(--hover)}.tkrow.done .tkt{text-decoration:line-through;color:var(--faint)}
.tkmain{flex:1;min-width:0}.tkt{font-size:15px;font-weight:500}.tkp{font-size:12px;color:var(--faint);margin-top:3px;display:flex;align-items:center;gap:5px}
.tkp svg{width:13px;height:13px}
.prio{width:11px;height:11px;border-radius:50%;flex:none;display:inline-block}
.prio.alta{background:var(--red)}.prio.media{background:var(--amber)}.prio.bassa{background:var(--green)}
.priobtn{width:28px;height:28px;border-radius:8px;border:1px solid var(--line);background:var(--panel);cursor:pointer;flex:none;display:flex;align-items:center;justify-content:center;transition:.15s}
.priobtn:hover{border-color:var(--acc);background:var(--hover)}
/* Temi (pagina) */
.thgrid{display:grid;grid-template-columns:repeat(auto-fill,minmax(200px,1fr));gap:14px}
.thcard{border:1.5px solid var(--line);border-radius:14px;overflow:hidden;cursor:pointer;background:var(--panel);transition:transform .12s,border-color .12s}
.thcard:hover{transform:translateY(-3px);border-color:var(--acc)}
.thcard.on{border-color:var(--acc);box-shadow:0 0 0 3px var(--acc-soft)}
.thprev{height:88px;padding:12px;display:flex;flex-direction:column;justify-content:space-between}
.thprev .bar{height:8px;border-radius:4px}
.thprev .row{display:flex;gap:6px;align-items:center}
.thprev .dot{width:14px;height:14px;border-radius:50%}
.thprev .mini{flex:1;height:22px;border-radius:6px}
.thmeta{display:flex;align-items:center;gap:8px;padding:10px 12px;border-top:1px solid var(--line)}
.thmeta b{font-size:13.5px;flex:1}
.thmeta .chk{color:var(--acc);display:none}.thcard.on .thmeta .chk{display:block}
.thmeta .chk svg{width:16px;height:16px}
/* Impostazioni sezioni */
.setrow{display:flex;align-items:center;gap:12px;padding:11px 4px;border-bottom:1px solid var(--line)}
.setrow:last-child{border-bottom:none}
.setrow .sic{color:var(--mut);display:flex}.setrow .sic svg{width:17px;height:17px}
.setrow .sm{flex:1;min-width:0}.setrow .sm b{font-size:14px}.setrow .sm div{font-size:12px;color:var(--faint);white-space:normal}
.sw{width:42px;height:24px;border-radius:999px;background:var(--panel2);border:1px solid var(--line2);position:relative;cursor:pointer;flex:none;transition:.2s}
.sw::after{content:'';position:absolute;top:2px;left:2px;width:18px;height:18px;border-radius:50%;background:var(--faint);transition:.2s}
.sw.on{background:var(--acc);border-color:var(--acc)}.sw.on::after{left:20px;background:#fff}
.sw.lock{opacity:.45;cursor:not-allowed}
/* Onboarding */
#onbov{position:fixed;inset:0;z-index:80;display:none;align-items:center;justify-content:center;padding:24px;background:rgba(0,0,0,.6)}
#onbov.on{display:flex}
.onbcard{width:100%;max-width:640px;max-height:90vh;overflow:auto;background:var(--panel);border:1px solid var(--line);border-radius:18px;padding:28px}
.onbcard h2{margin:0 0 4px;font-size:24px}.onbcard .sub{color:var(--mut);margin-bottom:18px}
.onbsec{display:flex;align-items:center;gap:10px;padding:9px 10px;border-radius:10px;cursor:pointer}
.onbsec:hover{background:var(--hover)}
.onbsec .cb{width:20px;height:20px;border-radius:6px;border:1.5px solid var(--line2);display:flex;align-items:center;justify-content:center;color:transparent;flex:none}
.onbsec.on .cb{background:var(--acc);border-color:var(--acc);color:#fff}.onbsec .cb svg{width:13px;height:13px}
.onbsec .oi{color:var(--mut);display:flex}.onbsec .oi svg{width:16px;height:16px}
.onbgrp{font-size:11px;text-transform:uppercase;letter-spacing:.06em;color:var(--faint);margin:14px 0 4px}
/* Lock screen */
#lockov{position:fixed;inset:0;z-index:200;display:none;align-items:center;justify-content:center;padding:24px;background:var(--bg)}
#lockov.on{display:flex}
.lockcard{text-align:center;max-width:360px;width:100%}
.lockic{width:64px;height:64px;border-radius:18px;background:var(--acc-soft);color:var(--acc);display:flex;align-items:center;justify-content:center;margin:0 auto 18px}
.lockic svg{width:30px;height:30px}
.lockcard h2{margin:0 0 4px;font-size:24px}.lockcard .sub{color:var(--mut);margin-bottom:18px}
.grid .card{cursor:pointer}

/* dettaglio voce + mappa business */
#detail{position:fixed;inset:0;z-index:60;display:none;align-items:flex-start;justify-content:center;padding:44px 20px;
  background:rgba(4,6,12,.55);backdrop-filter:blur(5px);overflow:auto}
#detail.on{display:flex;animation:fade .2s ease}
@keyframes fade{from{opacity:0}to{opacity:1}}
.dcard{width:min(780px,100%);background:var(--panel);border:1px solid var(--line2);border-radius:var(--rc);box-shadow:var(--sh2);animation:rise .32s var(--ease) both}
.dhead{display:flex;align-items:flex-start;gap:14px;padding:22px 24px;border-bottom:1px solid var(--line)}
.dhead .dt{flex:1;min-width:0;font-size:20px;font-weight:600;letter-spacing:-.02em;line-height:1.3;word-break:break-word}
.dx{background:none;border:none;color:var(--faint);cursor:pointer;padding:6px;border-radius:9px;transition:.13s}
.dx:hover{background:var(--hover);color:var(--red)}.dx svg{width:20px;height:20px}
.dbody{padding:22px 24px}
.dtags{margin-bottom:18px}
.drow{display:flex;gap:16px;padding:13px 0;border-bottom:1px solid var(--line)}
.drow:last-child{border-bottom:none}
.drow .dk{flex:none;width:130px;color:var(--faint);font-size:12px;font-weight:600;text-transform:uppercase;letter-spacing:.05em;padding-top:2px}
.drow .dv{flex:1;min-width:0;font-size:14.5px;line-height:1.6;color:var(--txt)}
.drow .dv ul{margin:0;padding-left:2px;list-style:none}
.drow .dv ul li{position:relative;padding:3px 0 3px 16px}
.drow .dv ul li::before{content:"";position:absolute;left:0;top:11px;width:5px;height:5px;border-radius:50%;background:var(--acc)}
.dsec-t{font-size:12px;font-weight:600;text-transform:uppercase;letter-spacing:.07em;color:var(--mut);margin:26px 0 14px}
.dmap-actions{display:flex;gap:10px;flex-wrap:wrap;align-items:center}
.dcenter{margin:2px auto 16px;max-width:380px;text-align:center;padding:14px 20px;border:1.5px solid var(--acc);border-radius:var(--pill);
  color:var(--acc);font-weight:600;font-size:16px;letter-spacing:-.01em;background:var(--acc-soft)}
.drami{display:grid;grid-template-columns:repeat(auto-fit,minmax(220px,1fr));gap:12px}
.dnode{border:1px solid var(--line);border-left:3px solid var(--acc);border-radius:var(--rk);padding:13px 16px;background:var(--inset)}
.dnode b{display:block;color:var(--acc);font-size:14px;font-weight:600;margin-bottom:9px;letter-spacing:-.01em}
.dnode span{display:block;color:var(--txt);font-size:13.5px;line-height:1.5;padding:3px 0 3px 15px;position:relative}
.dnode span::before{content:"";position:absolute;left:0;top:9px;width:5px;height:5px;border-radius:50%;background:var(--acc);opacity:.7}
.dwait{color:var(--mut);text-align:center;padding:28px 20px;font-size:14px;line-height:1.6}

/* segmented control + swipe (Idee: Lista / Scopri) */
.seg{display:inline-flex;padding:3px;gap:3px;background:var(--panel2);border:1px solid var(--line);border-radius:var(--pill)}
.segb{padding:7px 17px;border:none;border-radius:var(--pill);background:none;color:var(--mut);font:inherit;font-size:13.5px;font-weight:500;cursor:pointer;transition:.13s}
.segb:hover{color:var(--txt)}
.segb.on{background:var(--acc);color:#fff}
.gioseg .segb{display:inline-flex;align-items:center;gap:7px}
.gioseg .segb svg{width:16px;height:16px}
.giotop{margin:18px 0 12px}
.newsbar{margin-bottom:16px;gap:10px;flex-wrap:wrap}
.newsbar #nb-reset{padding:8px 12px}
.swipe-wrap{max-width:560px;margin:0 auto}
.swipe-stage{position:relative;min-height:344px;margin-top:2px}
.swipe-card{background:var(--panel);border:1px solid var(--line2);border-radius:var(--rc);box-shadow:var(--sh2);padding:26px 26px 22px;display:flex;flex-direction:column;gap:13px;min-height:344px}
.swipe-card.in{animation:rise .4s var(--ease) both}
.swipe-card.fly-l{animation:flyL .3s var(--ease) forwards}
.swipe-card.fly-r{animation:flyR .3s var(--ease) forwards}
@keyframes flyL{to{transform:translateX(-120%) rotate(-7deg);opacity:0}}
@keyframes flyR{to{transform:translateX(120%) rotate(7deg);opacity:0}}
.sc-t{font-size:22px;font-weight:600;letter-spacing:-.02em;line-height:1.25}
.sc-d{color:var(--mut);font-size:15px;line-height:1.6}
.sc-rows{display:flex;flex-direction:column;gap:11px;margin-top:2px}
.sc-r{font-size:14px;line-height:1.55}.sc-r b{color:var(--acc);font-weight:600}
.swipe-actions{display:flex;align-items:center;justify-content:center;gap:18px;margin-top:22px}
.swbtn{display:grid;place-items:center;border:1px solid var(--line2);background:var(--panel);color:var(--txt);font:inherit;cursor:pointer;transition:.15s;box-shadow:var(--sh1)}
.swbtn:active{transform:scale(.93)}
.swbtn.no,.swbtn.yes{width:60px;height:60px;border-radius:50%}
.swbtn.no{color:var(--red)}.swbtn.no:hover{border-color:var(--red);background:var(--red-soft)}
.swbtn.yes{color:var(--amber)}.swbtn.yes:hover{border-color:var(--amber);background:var(--amber-soft)}
.swbtn.no svg,.swbtn.yes svg{width:26px;height:26px}
.swbtn.skip{padding:0 18px;height:44px;border-radius:var(--pill);font-size:13.5px;font-weight:500;color:var(--mut)}
.swbtn.skip:hover{color:var(--acc);border-color:var(--acc-line)}
.sk{background:linear-gradient(90deg,var(--panel2),var(--hover),var(--panel2));background-size:200% 100%;animation:shim 1.2s linear infinite;border-radius:8px}
@keyframes shim{to{background-position:-200% 0}}

/* nutrizione */
.mrow{margin-bottom:15px}
.mhead{display:flex;justify-content:space-between;font-size:13.5px;margin-bottom:7px}
.mhead span:first-child{color:var(--mut)}.mhead .num{font-weight:600}
.mbar{height:9px;border-radius:6px;background:var(--panel2);overflow:hidden}
.mbar i{display:block;height:100%;border-radius:6px;background:var(--acc);transition:width .45s var(--ease)}
.mbar.kcal i{background:var(--green)}.mbar.p i{background:#5b8def}.mbar.c i{background:var(--amber)}.mbar.f i{background:#d879c8}
.mbar.over i{background:var(--red)}
.nprofile{display:grid;grid-template-columns:1fr 1fr;gap:12px}
.nprofile .fld{width:100%}.nprofile .inp{width:100%;min-width:0}
.needbox{margin-top:16px;padding:14px 16px;border:1px solid var(--line);border-radius:var(--rk);background:var(--inset)}
.needbox .nn{display:flex;justify-content:space-between;align-items:center;padding:6px 0;font-size:14px;border-bottom:1px solid var(--line)}
.needbox .nn:last-child{border-bottom:none}.needbox .nn span{color:var(--mut)}
/* investimenti */
.chart{width:100%;height:230px;display:block;margin-top:4px}
.chart polyline{vector-effect:non-scaling-stroke}
.varea{fill:var(--acc);opacity:.12;stroke:none}
.vline{fill:none;stroke:var(--acc);stroke-width:2.5}
.cline{fill:none;stroke:var(--faint);stroke-width:1.5;stroke-dasharray:5 5}
.leg{display:flex;gap:20px;margin-top:12px;font-size:13px;color:var(--mut)}
.leg i{display:inline-block;width:15px;height:3px;border-radius:2px;vertical-align:middle;margin-right:7px}
.mcband{display:grid;grid-template-columns:repeat(3,1fr);gap:12px;margin-top:14px}
.mccell{text-align:center;padding:13px 10px;border:1px solid var(--line);border-radius:var(--rk);background:var(--inset)}
.mccell .l{font-size:11px;color:var(--faint);text-transform:uppercase;letter-spacing:.04em}
.mccell .v{font-size:18px;font-weight:600;margin-top:5px;letter-spacing:-.02em}
.seg2{margin-bottom:20px}

/* ===== effetti per-tema ===== */
/* dinamici: blob animati sullo sfondo */
[data-theme=tramonto] .fx{background:
  radial-gradient(46% 55% at 16% 22%,rgba(255,106,61,.30),transparent 62%),
  radial-gradient(44% 52% at 84% 30%,rgba(255,60,120,.24),transparent 62%),
  radial-gradient(60% 60% at 60% 92%,rgba(150,60,210,.22),transparent 62%),var(--bg);
  background-size:180% 180%,180% 180%,190% 190%,100% 100%;animation:drift 22s ease-in-out infinite alternate}
[data-theme=aurora] .fx{background:
  radial-gradient(44% 52% at 20% 18%,rgba(57,224,203,.28),transparent 62%),
  radial-gradient(46% 54% at 82% 26%,rgba(138,108,255,.26),transparent 62%),
  radial-gradient(56% 60% at 55% 96%,rgba(60,120,255,.22),transparent 62%),var(--bg);
  background-size:180% 180%,185% 185%,190% 190%,100% 100%;animation:drift 26s ease-in-out infinite alternate}
@keyframes drift{from{background-position:0% 0%,100% 0%,50% 100%,0 0}to{background-position:38% 34%,64% 40%,34% 62%,0 0}}
/* vetro (3D): sfondo ricco statico + pannelli translucidi sfocati */
[data-theme=vetro] .fx{background:
  radial-gradient(50% 55% at 12% 14%,rgba(120,150,255,.35),transparent 60%),
  radial-gradient(46% 52% at 88% 22%,rgba(70,220,210,.28),transparent 60%),
  radial-gradient(60% 60% at 70% 96%,rgba(150,90,255,.3),transparent 60%),var(--bg)}
[data-theme=vetro] .card,[data-theme=vetro] .panel,[data-theme=vetro] .kpi,[data-theme=vetro] .side,[data-theme=vetro] .topbar,[data-theme=vetro] .search,[data-theme=vetro] .inp,[data-theme=vetro] .btn,[data-theme=vetro] .iconbtn,[data-theme=vetro] .chip{backdrop-filter:blur(18px) saturate(150%);-webkit-backdrop-filter:blur(18px) saturate(150%)}
[data-theme=vetro] .card,[data-theme=vetro] .panel,[data-theme=vetro] .kpi{box-shadow:0 22px 52px -20px rgba(0,0,0,.75),inset 0 1px 0 rgba(255,255,255,.18)}
/* ambra (3D): rilievo marcato */
[data-theme=ambra] .card,[data-theme=ambra] .kpi,[data-theme=ambra] .panel{box-shadow:7px 7px 18px rgba(0,0,0,.5),-4px -4px 12px rgba(255,255,255,.035),inset 0 1px 0 rgba(255,255,255,.05)}
[data-theme=ambra] .card:hover{box-shadow:10px 10px 26px rgba(0,0,0,.55),-5px -5px 14px rgba(255,255,255,.045),inset 0 1px 0 rgba(255,255,255,.06)}
/* neon (acceso): bagliori mirati */
[data-theme=neon] .btn.pri{box-shadow:0 0 18px rgba(0,229,255,.45)}
[data-theme=neon] .nav.on{box-shadow:inset 0 0 0 1px rgba(0,229,255,.3),0 0 14px -4px rgba(0,229,255,.4)}
[data-theme=neon] .kpi.a .v,[data-theme=neon] .card .score{text-shadow:0 0 16px rgba(0,229,255,.5)}
[data-theme=neon] .brand .logo{box-shadow:0 0 20px -4px var(--acc)}
/* Spider-Man: ragnatela sottile + bagliori rosso/blu, logo bicolore */
[data-theme=spiderman] .fx{background:
  radial-gradient(40% 50% at 8% 6%,rgba(224,27,44,.22),transparent 58%),
  radial-gradient(42% 52% at 94% 10%,rgba(26,75,255,.22),transparent 58%),var(--bg);
  background-repeat:no-repeat}
[data-theme=spiderman] .fx::after{content:"";position:absolute;inset:0;opacity:.05;
  background-image:
    repeating-conic-gradient(from 0deg at 50% 40%,transparent 0 14deg,rgba(255,255,255,.6) 14deg 14.4deg),
    radial-gradient(circle at 50% 40%,transparent 0,transparent 8%,rgba(255,255,255,.5) 8.05%,transparent 8.4%,transparent 16%,rgba(255,255,255,.5) 16.05%,transparent 16.4%,transparent 26%,rgba(255,255,255,.5) 26.05%,transparent 26.4%,transparent 38%,rgba(255,255,255,.5) 38.05%,transparent 38.4%,transparent 52%,rgba(255,255,255,.5) 52.05%,transparent 52.4%)}
[data-theme=spiderman] .brand .logo{background:linear-gradient(140deg,#e01b2c 45%,#1a4bff)}
[data-theme=spiderman] .nav.on .cnt{color:#5c7cff;background:rgba(26,75,255,.16)}
@media (prefers-reduced-motion:reduce){.fx{animation:none!important}}

/* ===== selettore temi (popover) ===== */
.side-foot{position:relative}
.chip .tsw{width:15px;height:15px;border-radius:5px;flex:none;background:var(--acc);box-shadow:inset 0 0 0 1px rgba(255,255,255,.18)}
.tpop{position:absolute;left:0;right:0;bottom:calc(100% + 8px);z-index:30;padding:7px;border:1px solid var(--line2);
  border-radius:var(--rc);background:var(--panel);box-shadow:var(--sh2);display:none;flex-direction:column;gap:3px;
  max-height:min(440px,70vh);overflow:auto}
.tpop.on{display:flex;animation:rise .25s var(--ease) both}
.topt{display:flex;align-items:center;gap:9px;padding:9px 10px;border:1px solid transparent;border-radius:var(--rk);
  background:none;color:var(--txt);font:inherit;font-size:12.5px;cursor:pointer;text-align:left;transition:.13s}
.topt:hover{background:var(--hover)}
.topt.on{border-color:var(--acc-line);background:var(--acc-soft)}
.topt .sws{display:flex;flex:none}
.topt .sws i{width:13px;height:13px;border-radius:50%;margin-left:-4px;box-shadow:0 0 0 2px var(--panel)}
.topt .sws i:first-child{margin-left:0}
.topt .tl{flex:1;min-width:0;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;font-weight:500}
.topt .tg{font-size:9.5px;font-weight:600;letter-spacing:.05em;text-transform:uppercase;color:var(--faint)}

/* Home Oggi (bento) */
.hero{margin-bottom:24px}
.hero h2{font-size:26px;font-weight:600;letter-spacing:-.03em;margin:0}
.hero p{color:var(--mut);margin:7px 0 0;font-size:14.5px}
.bento{display:grid;grid-template-columns:repeat(3,1fr);gap:16px}
@media(max-width:1100px){.bento{grid-template-columns:repeat(2,1fr)}}
@media(max-width:680px){.bento{grid-template-columns:1fr}}
.bcell{background:var(--panel);border:1px solid var(--line);border-radius:var(--rc);padding:18px 20px;box-shadow:var(--sh1);cursor:pointer;transition:transform .16s var(--ease),box-shadow .16s,border-color .16s;display:flex;flex-direction:column;gap:9px;min-height:118px}
.bcell:hover{transform:translateY(-3px);box-shadow:var(--sh2);border-color:var(--line2)}
.bcell .bh{display:flex;align-items:center;gap:9px;color:var(--mut);font-size:12px;font-weight:600;text-transform:uppercase;letter-spacing:.05em}
.bcell .bh svg{width:16px;height:16px;color:var(--acc)}
.bcell .bt{font-size:17px;font-weight:600;letter-spacing:-.01em;line-height:1.3;word-break:break-word}
.bcell .bm{color:var(--mut);font-size:13.5px;line-height:1.5}
.bcell .bbig{font-size:29px;font-weight:600;letter-spacing:-.03em;line-height:1}
.bcell .bbig small{font-size:14px;color:var(--faint);font-weight:500}
.bcell.wide{grid-column:span 2}
@media(max-width:680px){.bcell.wide{grid-column:span 1}}
.brief{grid-column:1 / -1;background:linear-gradient(135deg,var(--acc-soft),transparent 70%);border-color:var(--acc-line)}
.brief .bt2{font-size:14.5px;line-height:1.7;color:var(--txt);white-space:pre-wrap}

/* Investitori */
.road{margin:6px 0 8px}
.rstep{position:relative;padding:0 0 24px 30px;border-left:2px solid var(--line);margin-left:8px}
.rstep:last-child{border-left-color:transparent;padding-bottom:2px}
.rstep::before{content:"";position:absolute;left:-9px;top:1px;width:16px;height:16px;border-radius:50%;background:var(--panel);border:3px solid var(--acc)}
.rstep .rt{font-size:16px;font-weight:600;letter-spacing:-.01em}
.rstep .rtag{display:inline-block;margin-left:9px;font-size:11px;font-weight:600;color:var(--acc);background:var(--acc-soft);padding:2px 9px;border-radius:var(--pill);vertical-align:middle}
.rstep .rd{color:var(--mut);font-size:14px;line-height:1.6;margin-top:6px}
.rstep .rd b{color:var(--txt);font-weight:600}
.chk{list-style:none;margin:4px 0 0;padding:0}
.chk li{position:relative;padding:6px 0 6px 27px;font-size:14px;line-height:1.5;color:var(--txt)}
.chk li::before{content:"";position:absolute;left:0;top:8px;width:16px;height:16px;border-radius:5px;background:var(--acc-soft)}
.chk li::after{content:"";position:absolute;left:5px;top:11px;width:6px;height:3px;border-left:2px solid var(--acc);border-bottom:2px solid var(--acc);transform:rotate(-45deg)}
.src{display:flex;flex-direction:column;gap:7px}
.src .amt{color:var(--acc);font-weight:600;font-size:13.5px}
.gloss{display:grid;grid-template-columns:repeat(auto-fill,minmax(250px,1fr));gap:12px}
.gterm{border:1px solid var(--line);border-radius:var(--rk);padding:13px 15px;background:var(--inset)}
.gterm b{display:block;color:var(--txt);font-weight:600;margin-bottom:5px;font-size:14px}
.gterm span{color:var(--mut);font-size:13px;line-height:1.5}

/* Command palette */
#cmd{position:fixed;inset:0;z-index:80;display:none;align-items:flex-start;justify-content:center;padding:13vh 20px 20px;background:rgba(4,6,12,.5);backdrop-filter:blur(5px)}
#cmd.on{display:flex;animation:fade .15s ease}
.cmdbox{width:min(620px,100%);background:var(--panel);border:1px solid var(--line2);border-radius:var(--rc);box-shadow:var(--sh2);overflow:hidden;animation:rise .25s var(--ease) both}
.cmdin{display:flex;align-items:center;gap:11px;padding:16px 18px;border-bottom:1px solid var(--line)}
.cmdin svg{width:19px;height:19px;color:var(--faint)}
.cmdin input{flex:1;border:none;background:none;color:var(--txt);font:inherit;font-size:16px;outline:none}
.cmdres{max-height:56vh;overflow:auto;padding:6px}
.cmdi{display:flex;align-items:center;gap:12px;padding:11px 13px;border-radius:var(--rk);cursor:pointer}
.cmdi svg{width:17px;height:17px;color:var(--mut)}
.cmdi.sel,.cmdi:hover{background:var(--acc-soft)}.cmdi.sel svg,.cmdi:hover svg{color:var(--acc)}
.cmdi .ci-t{flex:1;font-size:14.5px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.cmdi .ci-s{font-size:12px;color:var(--faint);flex:none}
.cmdempty{padding:30px;text-align:center;color:var(--faint);font-size:14px}
.kbd{font-size:11px;color:var(--faint);border:1px solid var(--line);border-radius:6px;padding:2px 7px;background:var(--panel2)}

/* Fusione idee */
.card{position:relative}
.icheck{position:absolute;top:14px;right:14px;width:23px;height:23px;border:2px solid var(--line2);border-radius:6px;cursor:pointer;display:grid;place-items:center;color:#fff;background:var(--panel);transition:.13s;z-index:2}
.icheck:hover{border-color:var(--acc)}.icheck.on{background:var(--acc);border-color:var(--acc)}
.icheck svg{width:13px;height:13px;opacity:0;stroke-width:3}.icheck.on svg{opacity:1}
.fuse-bar{position:sticky;bottom:16px;z-index:20;display:flex;align-items:center;gap:14px;margin:20px auto 0;padding:11px 12px 11px 20px;border:1px solid var(--acc-line);border-radius:var(--pill);background:var(--panel);box-shadow:var(--sh2);width:fit-content}
.fuse-bar span{font-size:14px;font-weight:500}

/* Consumi Claude */
.usebar{display:flex;height:14px;border-radius:7px;overflow:hidden;background:var(--panel2);margin:8px 0 16px}
.usebar i{height:100%}
.uselegend{display:flex;flex-wrap:wrap;gap:18px;font-size:13px;color:var(--mut)}
.uselegend .d{display:inline-block;width:12px;height:12px;border-radius:3px;vertical-align:middle;margin-right:7px}
.uselegend b{color:var(--txt);font-weight:600}
.srow{display:flex;align-items:center;gap:14px;padding:10px 2px;border-bottom:1px solid var(--line)}
.srow:last-child{border-bottom:none}
.srow .sname{flex:1;min-width:0;border:1px solid transparent;background:none;color:var(--txt);font:inherit;font-size:14px;font-weight:500;padding:6px 9px;border-radius:8px;outline:none;text-overflow:ellipsis}
.srow .sname:hover{border-color:var(--line)}
.srow .sname:focus{border-color:var(--acc-line);box-shadow:var(--ring);background:var(--panel)}
.srow .sright{flex:none;text-align:right}
.srow .stok{font-weight:600;font-size:14px;font-variant-numeric:tabular-nums}
.srow .smeta{color:var(--faint);font-size:11.5px;margin-top:2px;white-space:nowrap}

/* Confronto multi-asset */
.cmpline{fill:none;stroke-width:2.5}
.cmp0{stroke:var(--acc)}.cmp1{stroke:#f0883e}.cmp2{stroke:#3fb96b}
.cmpleg{display:flex;gap:20px;flex-wrap:wrap;margin-top:12px;font-size:13.5px;color:var(--mut)}
.cmpleg i{display:inline-block;width:16px;height:3px;border-radius:2px;vertical-align:middle;margin-right:7px}
.cmpleg b{color:var(--txt);font-weight:600}

/* Classifica asset */
.rank{width:100%;border-collapse:collapse}
.rank th{text-align:left;font-size:11px;text-transform:uppercase;letter-spacing:.05em;color:var(--faint);font-weight:600;padding:10px 12px;border-bottom:1px solid var(--line)}
.rank td{padding:12px;border-bottom:1px solid var(--line);font-size:14px;font-variant-numeric:tabular-nums}
.rank tr:last-child td{border-bottom:none}.rank tbody tr:hover td{background:var(--hover)}
.rank .r-n{color:var(--faint);width:30px}.rank .r-m{font-weight:600;color:var(--green)}.rank .r-a{font-weight:600}.rank .r-cat{font-size:12px;color:var(--mut)}
.rank .r-neg{color:var(--red)}

/* Stato agente + freschezza (Home Oggi) */
.statebar{display:flex;align-items:center;gap:16px;flex-wrap:wrap;margin-bottom:22px;padding:12px 18px;border:1px solid var(--line);border-radius:var(--rc);background:var(--panel);box-shadow:var(--sh1)}
.statebar .sb-l{display:flex;align-items:center;gap:9px;font-size:13.5px;color:var(--mut)}
.statebar .sb-l svg{width:16px;height:16px;color:var(--acc)}.statebar .sb-l b{color:var(--txt);font-weight:600}
.fchips{display:flex;gap:8px;flex-wrap:wrap;flex:1}
.fchip{font-size:12px;color:var(--mut);background:var(--panel2);border:1px solid var(--line);padding:3px 10px;border-radius:var(--pill)}
.fchip b{font-variant-numeric:tabular-nums}
.fchip.g{color:var(--green);border-color:transparent;background:var(--green-soft)}
.fchip.am{color:var(--amber);border-color:transparent;background:var(--amber-soft)}
.fchip.r{color:var(--red);border-color:transparent;background:var(--red-soft)}

/* Prodotti da reddito */
.card .euro-day{margin-left:auto;flex:none;text-align:right}
.card .euro-day .v{font-size:24px;font-weight:600;letter-spacing:-.02em;color:var(--green);line-height:1;font-variant-numeric:tabular-nums}
.card .euro-day .l{font-size:11px;color:var(--faint);text-transform:uppercase;letter-spacing:.04em;margin-top:3px}
.prodmath{border:1px solid var(--line);border-radius:var(--rk);background:var(--inset);padding:6px 16px;margin-top:2px}
.prodmath .pm{display:flex;justify-content:space-between;padding:8px 0;font-size:14px;border-bottom:1px solid var(--line)}
.prodmath .pm:last-child{border-bottom:none}
.prodmath .pm span{color:var(--mut)}.prodmath .pm b{font-variant-numeric:tabular-nums}
.prodmath .pm.tot b{color:var(--green);font-size:17px}
.tag.radar{background:linear-gradient(90deg,#ff6a3d,#ff3c78);color:#fff;border-color:transparent;font-weight:600}
/* one-pager */
.op-tag{font-size:16px;font-weight:600;color:var(--txt);font-style:italic;margin-bottom:16px;padding-left:12px;border-left:3px solid var(--acc);line-height:1.4}
.op-sec{margin-bottom:14px}
.op-sec b{display:block;font-size:12px;text-transform:uppercase;letter-spacing:.05em;color:var(--acc);margin-bottom:4px}
.op-sec span{font-size:14.5px;line-height:1.6;color:var(--txt)}
</style></head><body>
<div class="fx" id="fx"></div>
<div class="app">
  <aside class="side">
    <div class="brand">
      <div class="logo"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-linecap="round" stroke-linejoin="round"><path d="M12 3 4 7.5v9L12 21l8-4.5v-9L12 3Z"/><path d="M12 12 4 7.5M12 12v9M12 12l8-4.5"/></svg></div>
      <div><b>miAi</b><small>assistente personale</small></div>
    </div>
    <nav id="nav"></nav>
    <div class="side-foot">
      <button class="chip off" id="ollama"><span class="dot"></span><span id="ollama-lbl">Ollama</span><span class="sw" id="ollama-sw">off</span></button>
      <button class="chip" id="notif"><span class="dot"></span><span id="notif-lbl">Avvisi</span><span class="sw" id="notif-sw">off</span></button>
      <button class="chip" id="theme"><span class="tsw" id="theme-sw2"></span><span id="theme-lbl">Tema</span><span class="sw">scegli</span></button>
      <div class="tpop" id="tpop"></div>
    </div>
  </aside>
  <main class="main">
    <div class="topbar">
      <div><h1 id="pt">GitHub</h1><div class="desc" id="pd"></div></div>
      <div class="sp"></div>
      <label class="search" id="searchbox"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-linecap="round"><circle cx="11" cy="11" r="7"/><path d="m21 21-4-4"/></svg><input id="q" placeholder="Cerca..."></label>
      <div class="langwrap"><button class="iconbtn langbtn" id="langbtn" title="Lingua">🌐</button><div class="langpop" id="langpop"></div></div>
      <button class="iconbtn" id="refresh" title="Aggiorna dati"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-linecap="round" stroke-linejoin="round"><path d="M21 12a9 9 0 1 1-3-6.7L21 8"/><path d="M21 3v5h-5"/></svg></button>
      <button class="iconbtn" id="update" title="Aggiorna la app dal server (rigenera)"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-linecap="round" stroke-linejoin="round"><path d="M12 13V4"/><path d="M8 7l4-4 4 4"/><path d="M20 16.5A5 5 0 0 0 18 7h-1.3A8 8 0 1 0 4 15"/></svg></button>
    </div>
    <div class="content" id="view"></div>
  </main>
</div>
<div id="detail"></div>
<div id="cmd"></div>
<div id="onbov"></div>
<div id="lockov"></div>
<script>
const P=__PAYLOAD__;
const $=s=>document.querySelector(s),el=(t,c,h)=>{const e=document.createElement(t);if(c)e.className=c;if(h!=null)e.innerHTML=h;return e;};
const esc=s=>String(s==null?'':s).replace(/[&<>"]/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c]));
const nfmt=n=>n>=1000?(n/1000).toFixed(n>=10000?0:1)+'k':String(n);
const demoji=s=>String(s==null?'':s).replace(/[\u{1F000}-\u{1FAFF}\u{2600}-\u{27BF}\u{2190}-\u{21FF}\u{2B00}-\u{2BFF}�️‍]/gu,'').replace(/\s{2,}/g,' ').trim();
const PERSIST=['idee_fav','prod_fav','gh_saved','spesa_items','spesa_tpl','nutri_profile','inv_cfg','claude_titles','claude_budget','claude_plan','theme','prod_set','notif_on','cv_last','cyber_prog','agenda','projects','tasks','sections_on','onboarded','oggi_tiles','autolock_min'];
const isPersist=k=>PERSIST.includes(k)||(''+k).indexOf('nutri_')===0;
let _syncT=null;
function pushStore(){const o={};for(let i=0;i<localStorage.length;i++){const k=localStorage.key(i);if(isPersist(k))o[k]=localStorage.getItem(k);}
 clearTimeout(_syncT);_syncT=setTimeout(()=>{fetch('/store',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(o)}).catch(()=>{});},600);}
const LS={get:(k,d)=>{try{return JSON.parse(localStorage.getItem(k))??d}catch(e){return d}},
 set:(k,v)=>{localStorage.setItem(k,JSON.stringify(v));if(isPersist(k))pushStore();}};
async function loadStore(){try{const o=await (await fetch('/store')).json();if(o&&typeof o==='object')for(const k in o){if(isPersist(k)&&o[k]!=null)localStorage.setItem(k,o[k]);}}catch(e){}}
const ICON={
 github:'<path d="M9 19c-5 1.5-5-2.5-7-3m14 6v-3.9a3.4 3.4 0 0 0-.9-2.6c3-.3 6.2-1.5 6.2-6.7A5.2 5.2 0 0 0 20 4.8 4.8 4.8 0 0 0 19.9 1S18.7.6 16 2.5a13.4 13.4 0 0 0-7 0C6.3.6 5.1 1 5.1 1A4.8 4.8 0 0 0 5 4.8 5.2 5.2 0 0 0 3.7 8.4c0 5.2 3.2 6.4 6.2 6.7a3.4 3.4 0 0 0-.9 2.5V22"/>',
 shield:'<path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z"/><path d="m9 12 2 2 4-4"/>',
 box:'<path d="M21 8V16a2 2 0 0 1-1 1.7l-7 4a2 2 0 0 1-2 0l-7-4A2 2 0 0 1 3 16V8a2 2 0 0 1 1-1.7l7-4a2 2 0 0 1 2 0l7 4A2 2 0 0 1 21 8z"/><path d="m3.3 7 8.7 5 8.7-5"/><path d="M12 22V12"/>',
 trend:'<path d="M22 7 13.5 15.5 8.5 10.5 2 17"/><path d="M16 7h6v6"/>',
 bulb:'<path d="M9 18h6"/><path d="M10 22h4"/><path d="M12 2a7 7 0 0 0-4 12.7c.6.5 1 1.3 1 2.1V18h6v-1.2c0-.8.4-1.6 1-2.1A7 7 0 0 0 12 2z"/>',
 cpu:'<rect x="4" y="4" width="16" height="16" rx="2"/><rect x="9" y="9" width="6" height="6"/><path d="M9 1v3M15 1v3M9 20v3M15 20v3M20 9h3M20 15h3M1 9h3M1 15h3"/>',
 disk:'<line x1="22" y1="12" x2="2" y2="12"/><path d="M5.5 5h13l3.5 7v6a1 1 0 0 1-1 1H3a1 1 0 0 1-1-1v-6z"/><line x1="6" y1="16" x2="6.01" y2="16"/><line x1="10" y1="16" x2="10.01" y2="16"/>',
 cart:'<circle cx="8" cy="21" r="1.5"/><circle cx="19" cy="21" r="1.5"/><path d="M2 3h2l2.6 12.4a2 2 0 0 0 2 1.6h8.7a2 2 0 0 0 2-1.6L23 7H6"/>',
 food:'<path d="M3 2v7a3 3 0 0 0 3 3 3 3 0 0 0 3-3V2"/><path d="M6 2v20"/><path d="M18 2c-1.7 0-3 1.8-3 5v6h3v9"/>',
 chart:'<path d="M3 3v16a2 2 0 0 0 2 2h16"/><path d="M7 15l3.5-4 3 2.5L20 7"/>',
 sun:'<circle cx="12" cy="12" r="4"/><path d="M12 2v2M12 20v2M4.9 4.9l1.4 1.4M17.7 17.7l1.4 1.4M2 12h2M20 12h2M4.9 19.1l1.4-1.4M17.7 6.3l1.4-1.4"/>',
 moon:'<path d="M21 12.8A9 9 0 1 1 11.2 3a7 7 0 0 0 9.8 9.8z"/>',
 star:'<path d="M12 2l3 6.9 7.5.6-5.7 4.9 1.8 7.3L12 17.8 5.4 21.7l1.8-7.3L1.5 9.5 9 8.9z"/>',
 ext:'<path d="M15 3h6v6M10 14 21 3M18 13v6a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h6"/>',
 plus:'<path d="M12 5v14M5 12h14"/>',
 check:'<path d="M20 6 9 17l-5-5"/>',
 x:'<path d="M18 6 6 18M6 6l12 12"/>',
 home:'<path d="M3 10.5 12 3l9 7.5"/><path d="M5 9.5V21h14V9.5"/><path d="M9.5 21v-6h5v6"/>',
 hand:'<rect x="2" y="7" width="20" height="14" rx="2"/><path d="M8 7V5a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"/><path d="M2 13h20"/>',
 merge:'<circle cx="6" cy="6" r="2.5"/><circle cx="6" cy="18" r="2.5"/><circle cx="18" cy="8" r="2.5"/><path d="M6 8.5v7"/><path d="M18 10.5a7 7 0 0 1-7 7H8.5"/>',
 spark:'<path d="M12 3v4M12 17v4M3 12h4M17 12h4M6 6l2.5 2.5M15.5 15.5 18 18M18 6l-2.5 2.5M8.5 15.5 6 18"/>',
 activity:'<path d="M22 12h-4l-3 9L9 3l-3 9H2"/>',
 download:'<path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/><path d="M7 10l5 5 5-5"/><path d="M12 15V3"/>',
 update:'<path d="M12 13V4"/><path d="M8 7l4-4 4 4"/><path d="M20 16.5A5 5 0 0 0 18 7h-1.3A8 8 0 1 0 4 15"/>',
 euro:'<circle cx="12" cy="12" r="9"/><path d="M15.5 9A4.5 4.5 0 0 0 8 12a4.5 4.5 0 0 0 7.5 3"/><path d="M7 11h6M7 13h5"/>',
 fire:'<path d="M12 2s5 4 5 9a5 5 0 0 1-10 0c0-1.5.5-2.8 1.2-3.8C8 8 9 9 9 9s-.5-3 3-7z"/><path d="M12 22a4 4 0 0 0 4-4c0-2-2-3-2-5 0 0-3 2-3 5a2 2 0 0 1-2-2"/>',
 doc:'<path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><path d="M14 2v6h6"/><path d="M8 13h8M8 17h8M8 9h2"/>',
 mail:'<rect x="2" y="4" width="20" height="16" rx="2"/><path d="m2 7 10 6 10-6"/>',
 lock:'<rect x="4" y="11" width="16" height="10" rx="2"/><path d="M8 11V7a4 4 0 0 1 8 0v4"/>',
 wifi:'<path d="M5 12.5a10 10 0 0 1 14 0"/><path d="M8.5 15.8a5 5 0 0 1 7 0"/><path d="M2 9a15 15 0 0 1 20 0"/><line x1="12" y1="19" x2="12.01" y2="19"/>',
 globe:'<circle cx="12" cy="12" r="9"/><path d="M3 12h18"/><path d="M12 3a14 14 0 0 1 0 18 14 14 0 0 1 0-18z"/>',
 bug:'<rect x="8" y="6" width="8" height="12" rx="4"/><path d="M8 10H4M8 14H4M20 10h-4M20 14h-4M12 2v4M9 4l1 2M15 4l-1 2M9 20l1-2M15 20l-1-2"/>',
 eye:'<path d="M2 12s4-7 10-7 10 7 10 7-4 7-10 7-10-7-10-7z"/><circle cx="12" cy="12" r="3"/>',
 code:'<path d="m16 18 6-6-6-6M8 6l-6 6 6 6"/>',
 heart:'<path d="M12 21s-7-4.5-9.5-9A5 5 0 0 1 12 6a5 5 0 0 1 9.5 6C19 16.5 12 21 12 21z"/>',
 trophy:'<path d="M8 21h8M12 17v4M7 4h10v5a5 5 0 0 1-10 0z"/><path d="M7 6H4v2a3 3 0 0 0 3 3M17 6h3v2a3 3 0 0 1-3 3"/>',
 play:'<path d="M6 4l14 8-14 8z"/>',
 game:'<rect x="2" y="7" width="20" height="12" rx="3"/><path d="M7 12h4M9 10v4M15.5 11.5h.01M18 13.5h.01"/>',
 book:'<path d="M4 5a2 2 0 0 1 2-2h13v16H6a2 2 0 0 0-2 2z"/><path d="M4 19a2 2 0 0 1 2-2h13"/>',
 chat:'<path d="M21 15a2 2 0 0 1-2 2H8l-4 4V5a2 2 0 0 1 2-2h13a2 2 0 0 1 2 2z"/><path d="M8 9h8M8 13h5"/>',
 send:'<path d="M22 2 11 13"/><path d="M22 2 15 22l-4-9-9-4z"/>',
 layout:'<rect x="3" y="3" width="18" height="18" rx="2"/><path d="M3 9h18M9 21V9"/>',
 monitor:'<rect x="2" y="3" width="20" height="14" rx="2"/><path d="M8 21h8M12 17v4"/>',
 pen:'<path d="M12 20h9"/><path d="M16.5 3.5a2.1 2.1 0 0 1 3 3L7 19l-4 1 1-4z"/>',
 calendar:'<rect x="3" y="4" width="18" height="18" rx="2"/><path d="M3 10h18M8 2v4M16 2v4"/>',
 robot:'<rect x="4" y="8" width="16" height="12" rx="3"/><path d="M12 8V4M9 4h6"/><circle cx="9" cy="14" r="1.2"/><circle cx="15" cy="14" r="1.2"/><path d="M2 13v3M22 13v3"/>',
 folder:'<path d="M3 7a2 2 0 0 1 2-2h4l2 2h8a2 2 0 0 1 2 2v8a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2z"/>',
 tasklist:'<path d="M9 6h11M9 12h11M9 18h11"/><path d="M4 6l1 1 2-2M4 12l1 1 2-2M4 18l1 1 2-2"/>',
 palette:'<circle cx="13.5" cy="6.5" r="1.5"/><circle cx="17.5" cy="10.5" r="1.5"/><circle cx="8.5" cy="7.5" r="1.5"/><circle cx="6.5" cy="12.5" r="1.5"/><path d="M12 2a10 10 0 1 0 0 20 2.5 2.5 0 0 0 2-4 2.5 2.5 0 0 1 2-4h1a5 5 0 0 0 5-5c0-4.4-4.5-7-10-7z"/>',
 news:'<path d="M4 4h13a1 1 0 0 1 1 1v13a2 2 0 0 0 2 2H5a2 2 0 0 1-2-2V5a1 1 0 0 1 1-1z"/><path d="M18 8h2a1 1 0 0 1 1 1v9a2 2 0 0 1-2 2"/><path d="M7 8h7M7 12h7M7 16h4"/>',
 settings:'<circle cx="12" cy="12" r="3"/><path d="M19.4 15a1.6 1.6 0 0 0 .3 1.8l.1.1a2 2 0 1 1-2.8 2.8l-.1-.1a1.6 1.6 0 0 0-2.7 1.1V21a2 2 0 1 1-4 0v-.1A1.6 1.6 0 0 0 7 19.4a1.6 1.6 0 0 0-1.8.3l-.1.1a2 2 0 1 1-2.8-2.8l.1-.1a1.6 1.6 0 0 0-1.1-2.7H1a2 2 0 1 1 0-4h.1A1.6 1.6 0 0 0 2.6 7a1.6 1.6 0 0 0-.3-1.8l-.1-.1a2 2 0 1 1 2.8-2.8l.1.1a1.6 1.6 0 0 0 1.8.3H7a1.6 1.6 0 0 0 1-1.5V1a2 2 0 1 1 4 0v.1a1.6 1.6 0 0 0 2.7 1.1l.1-.1a2 2 0 1 1 2.8 2.8l-.1.1a1.6 1.6 0 0 0-.3 1.8V7a1.6 1.6 0 0 0 1.5 1H23a2 2 0 1 1 0 4h-.1a1.6 1.6 0 0 0-1.5 1z"/>'};
const svg=(n,w)=>`<svg viewBox="0 0 24 24" fill="none" stroke="currentColor"${w?` stroke-width="${w}"`:''} stroke-linecap="round" stroke-linejoin="round">${ICON[n]||''}</svg>`;

const NAV=[
 {g:'Panoramica'},
 {id:'oggi',label:'Oggi',icon:'home',desc:'Il meglio di tutte le sezioni, in un colpo d\'occhio.'},
 {id:'assistente',label:'Assistente',icon:'robot',desc:'Chiedi a miAi: vede i tuoi dati e ti aiuta a orientarti tra le sezioni.'},
 {id:'preferiti',label:'Preferiti',icon:'star',desc:'Tutto quello che hai salvato: repo, idee e prodotti.'},
 {g:'Scout'},
 {id:'github',label:'GitHub',icon:'github',desc:'Repository nuove e di tendenza filtrate per i tuoi interessi.',cnt:()=>P.github.length},
 {id:'giornale',label:'Giornale',icon:'news',desc:'Le notizie degli argomenti che scegli tu (cronaca, sport, tech, immobiliare...), piu Cyber e Blockchain.',cnt:()=>P.cyber.length+P.blockchain.length},
 {id:'idee',label:'Idee',icon:'bulb',desc:'Idee di business che incrociano trend, minacce e mercato.',cnt:()=>P.idee.length},
 {id:'investitori',label:'Investitori',icon:'hand',desc:'Dove trovare capitali, come contattarli e la roadmap della startup.'},
 {g:'Progetti'},
 {id:'progetti',label:'Progetti',icon:'folder',desc:'I tuoi progetti attivi, con avanzamento e task collegati.'},
 {id:'task',label:'Task',icon:'tasklist',desc:'Le tue attivita, collegate ai progetti: cosa fare adesso.'},
 {g:'Sistema'},
 {id:'pc',label:'PC',icon:'cpu',desc:'Consigli su misura per il tuo hardware reale.',cnt:()=>P.pc.length},
 {id:'disco',label:'Disco',icon:'disk',desc:'Spazio, file freddi e quanto puoi liberare.'},
 {id:'consumi',label:'Consumi AI',icon:'activity',desc:'Token usati dai tuoi agenti AI (Claude Code, Codex, Gemini...), combinati e per singolo agente.'},
 {g:'Personale'},
 {id:'spesa',label:'Lista spesa',icon:'cart',desc:'La tua spesa, con modelli riutilizzabili.'},
 {id:'nutrizione',label:'Nutrizione',icon:'food',desc:'Calorie e macro di oggi, con il tuo fabbisogno stimato.'},
 {id:'investimenti',label:'Investimenti',icon:'chart',desc:'Simulazione PAC e PIC con crescita composta.'},
 {id:'cv',label:'Analisi CV',icon:'doc',desc:'Carichi il CV in PDF: lo leggo, estraggo i dati e ti dico cosa migliorare con un punteggio.'},
 {id:'cyberquest',label:'CyberQuest',icon:'game',desc:'Percorso a livelli per imparare la cybersecurity difensiva giocando: XP, ranghi e sfide.'},
 {id:'riassunto',label:'Riassunto PDF',icon:'book',desc:'Carichi un PDF (paper, dispensa, contratto): ne ricavo sintesi, punti chiave e domande.'},
 {id:'colloquio',label:'Palestra colloquio',icon:'chat',desc:'Dal tuo CV e dal ruolo target: domande di colloquio realistiche con tracce di risposta.'},
 {id:'jobmatch',label:'Lettera & Match',icon:'send',desc:'Incolli un annuncio: punteggio di compatibilita col tuo CV e lettera di presentazione su misura.'},
 {id:'agenda',label:'Agenda',icon:'calendar',desc:'Scadenze e promemoria: esami, consegne, colloqui, con avvisi sul desktop.'},
 {id:'scrittura',label:'Scrittura',icon:'pen',desc:'Riscrivi, correggi, accorcia o traduci testi, email e messaggi con miAi.'},
 {id:'widget',label:'Widget desktop',icon:'monitor',desc:'Metti miAi sul desktop del PC per aprirlo con un clic, o installalo come app.'},
 {g:'Personalizza'},
 {id:'temi',label:'Temi',icon:'palette',desc:'Scegli l\'aspetto di miAi: oltre 30 temi, dal minimale al Minecraft.'},
 {id:'modello',label:'Modello AI',icon:'spark',desc:'Scegli il modello che usa miAi: Ollama locale o qualsiasi endpoint compatibile.'},
 {id:'impostazioni',label:'Impostazioni',icon:'settings',desc:'Scegli quali sezioni mostrare nel menu.'}];

// ---- sidebar (rispetta le sezioni scelte) ----
const SEC_ALWAYS=['oggi','temi','modello','impostazioni'];      // sempre visibili
const SEC_LOCKED=['oggi','temi','modello','impostazioni'];      // non disattivabili
function secOn(id){if(SEC_ALWAYS.includes(id))return true;const m=LS.get('sections_on',null);return !m||m[id]!==false;}
function buildNav(){const nav=$('#nav');nav.innerHTML='';let pending=null;
 NAV.forEach(n=>{
  if(n.g){pending=n.g;return;}
  if(!secOn(n.id))return;
  if(pending){nav.appendChild(el('div','navgrp',pending));pending=null;}
  const b=el('button','nav');b.dataset.view=n.id;
  const c=n.cnt?n.cnt():null;
  b.innerHTML=svg(n.icon)+`<span>${n.label}</span>`+(c!=null?`<span class="cnt num">${c}</span>`:'');
  b.onclick=()=>go(n.id);
  nav.appendChild(b);
 });}
buildNav();

// ---- temi ----
const THEMES=[
 {id:'scuro',label:'Scuro',dots:['#0a0a0d','#8a8cf7','#f2f2f6']},
 {id:'chiaro',label:'Chiaro',dots:['#ffffff','#5b5ef0','#141419']},
 {id:'indaco',label:'Indaco',dots:['#0a0a16','#7c7bff','#9d9cff'],tag:'acceso'},
 {id:'smeraldo',label:'Smeraldo',dots:['#07110c','#1fd982','#38ef99'],tag:'acceso'},
 {id:'tramonto',label:'Tramonto',dots:['#140c0d','#ff6a3d','#ff3c78'],tag:'dinamico'},
 {id:'aurora',label:'Aurora',dots:['#070912','#39e0cb','#8a6cff'],tag:'dinamico'},
 {id:'neon',label:'Neon',dots:['#04050a','#00e5ff','#ff5c8a'],tag:'acceso'},
 {id:'vetro',label:'Vetro',dots:['#0b1020','#8ab0ff','#46dcd2'],tag:'3D'},
 {id:'ambra',label:'Ambra',dots:['#14100a','#f5a524','#ffbe4d'],tag:'3D'},
 {id:'spiderman',label:'Spider-Man',dots:['#0a0e18','#e01b2c','#1a4bff'],tag:'eroe'},
 /*__XTHEMES_JS__*/];
const MIGRATE={dark:'scuro',light:'chiaro'};
let theme=LS.get('theme','scuro');theme=MIGRATE[theme]||theme;if(!THEMES.some(t=>t.id===theme))theme='scuro';
function applyTheme(id){theme=id;document.documentElement.setAttribute('data-theme',id);LS.set('theme',id);
 const t=THEMES.find(x=>x.id===id)||THEMES[0];
 $('#theme-sw2').style.background=t.dots[1];$('#theme-lbl').textContent=t.label;
 document.querySelectorAll('.topt').forEach(b=>b.classList.toggle('on',b.dataset.t===id));}
const pop=$('#tpop');
pop.innerHTML=THEMES.map(t=>`<button class="topt" data-t="${t.id}">
  <span class="sws">${t.dots.map(d=>`<i style="background:${d}"></i>`).join('')}</span>
  <span class="tl">${t.label}</span>${t.tag?`<span class="tg">${t.tag}</span>`:''}</button>`).join('');
pop.querySelectorAll('.topt').forEach(b=>b.onclick=()=>{applyTheme(b.dataset.t);pop.classList.remove('on');});
$('#theme').onclick=e=>{e.stopPropagation();pop.classList.toggle('on');};
document.addEventListener('click',e=>{if(!pop.contains(e.target)&&!$('#theme').contains(e.target))pop.classList.remove('on');});
applyTheme(theme);

// ---- ollama ----
let __llmLocal=true,__llmModel='';
async function ollamaStatus(){try{const h=await (await fetch('/health')).json();__llmLocal=h.local!==false;__llmModel=h.modello||'';setOllama(h.ollama);}catch(e){setOllama(null);}}
function setOllama(on){const c=$('#ollama');c.className='chip '+(on?'on':'off');$('#ollama-sw').textContent=on?'on':'off';
 const name=__llmModel?(' '+__llmModel.split(':')[0]):'';
 $('#ollama-lbl').textContent=(on?'Modello attivo':'Modello spento')+(name&&on?'':'');
 $('#ollama').title=(__llmModel||'modello')+(__llmLocal?' (locale)':' (remoto)')+' - clic: '+(__llmLocal?'accendi/spegni':'impostazioni');}
$('#ollama').onclick=async()=>{
 if(!__llmLocal){go('modello');return;}   // backend remoto: apri le impostazioni, non c'e nulla da avviare
 const on=$('#ollama').classList.contains('on');$('#ollama').style.opacity='.6';
 try{const r=await (await fetch('/ollama',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({on:!on})})).json();setOllama(r.running);}
 catch(e){}finally{$('#ollama').style.opacity='';}};
ollamaStatus();setInterval(ollamaStatus,20000);

// ---- lingua + traduzione UI (chrome), offline via modello locale, in cache su disco ----
const FLAG={it:'\u{1F1EE}\u{1F1F9}',en:'\u{1F1EC}\u{1F1E7}',es:'\u{1F1EA}\u{1F1F8}',fr:'\u{1F1EB}\u{1F1F7}',de:'\u{1F1E9}\u{1F1EA}',pt:'\u{1F1F5}\u{1F1F9}',nl:'\u{1F1F3}\u{1F1F1}',ru:'\u{1F1F7}\u{1F1FA}',uk:'\u{1F1FA}\u{1F1E6}',pl:'\u{1F1F5}\u{1F1F1}',ro:'\u{1F1F7}\u{1F1F4}',el:'\u{1F1EC}\u{1F1F7}',tr:'\u{1F1F9}\u{1F1F7}',ar:'\u{1F1F8}\u{1F1E6}',he:'\u{1F1EE}\u{1F1F1}',fa:'\u{1F1EE}\u{1F1F7}',hi:'\u{1F1EE}\u{1F1F3}',bn:'\u{1F1E7}\u{1F1E9}',ur:'\u{1F1F5}\u{1F1F0}',zh:'\u{1F1E8}\u{1F1F3}',ja:'\u{1F1EF}\u{1F1F5}',ko:'\u{1F1F0}\u{1F1F7}',vi:'\u{1F1FB}\u{1F1F3}',th:'\u{1F1F9}\u{1F1ED}',id:'\u{1F1EE}\u{1F1E9}',ms:'\u{1F1F2}\u{1F1FE}',sv:'\u{1F1F8}\u{1F1EA}',no:'\u{1F1F3}\u{1F1F4}',da:'\u{1F1E9}\u{1F1F0}',fi:'\u{1F1EB}\u{1F1EE}',cs:'\u{1F1E8}\u{1F1FF}',sk:'\u{1F1F8}\u{1F1F0}',hu:'\u{1F1ED}\u{1F1FA}',bg:'\u{1F1E7}\u{1F1EC}',sr:'\u{1F1F7}\u{1F1F8}',hr:'\u{1F1ED}\u{1F1F7}',sl:'\u{1F1F8}\u{1F1EE}',et:'\u{1F1EA}\u{1F1EA}',lv:'\u{1F1F1}\u{1F1FB}',lt:'\u{1F1F1}\u{1F1F9}',sw:'\u{1F1F0}\u{1F1EA}',af:'\u{1F1FF}\u{1F1E6}',ca:'\u{1F1E6}\u{1F1E9}',eu:'\u{1F1EA}\u{1F1F8}',gl:'\u{1F1EA}\u{1F1F8}',is:'\u{1F1EE}\u{1F1F8}',ga:'\u{1F1EE}\u{1F1EA}',cy:'\u{1F3F4}',fil:'\u{1F1F5}\u{1F1ED}',ta:'\u{1F1EE}\u{1F1F3}'};
const flagOf=c=>FLAG[c]||'\u{1F310}';
// Traduzione OFFLINE e ISTANTANEA con argos-translate (server /translate): copre
// OGNI testo a schermo. __TC = cache origine->tradotto della sessione; un
// MutationObserver ritraduce a ogni render (istantaneo per cio che e gia in cache,
// e chiede al motore solo le stringhe nuove). NIENTE dati fuori dal PC.
let __lang='it',__langs=[],__TC={},__transT=null;
const _translatable=t=>!!t&&t.length<=200&&/[A-Za-zÀ-ɏ]/.test(t);
function collectNew(){const s=new Set();
 const w=document.createTreeWalker(document.body,NodeFilter.SHOW_TEXT);
 while(w.nextNode()){const t=(w.currentNode.nodeValue||'').trim();if(_translatable(t)&&!(t in __TC))s.add(t);}
 document.querySelectorAll('[placeholder]').forEach(e=>{const t=(e.getAttribute('placeholder')||'').trim();if(_translatable(t)&&!(t in __TC))s.add(t);});
 document.querySelectorAll('#langpop .lopt,[title]').forEach(e=>{const t=(e.getAttribute('title')||'').trim();if(_translatable(t)&&!(t in __TC))s.add(t);});
 return [...s];}
function applyTC(){if(__lang==='it')return;__transObs.disconnect();
 const w=document.createTreeWalker(document.body,NodeFilter.SHOW_TEXT);const chg=[];
 while(w.nextNode()){const n=w.currentNode;const t=(n.nodeValue||'').trim();if(t&&__TC[t]&&__TC[t]!==t)chg.push([n,n.nodeValue.replace(t,__TC[t])]);}
 chg.forEach(([n,v])=>{n.nodeValue=v;});
 document.querySelectorAll('[placeholder]').forEach(e=>{const t=(e.getAttribute('placeholder')||'').trim();if(__TC[t])e.setAttribute('placeholder',__TC[t]);});
 document.querySelectorAll('[title]').forEach(e=>{const t=(e.getAttribute('title')||'').trim();if(__TC[t])e.setAttribute('title',__TC[t]);});
 __transObs.observe(document.body,{childList:true,subtree:true,characterData:true});}
async function fetchNew(){if(__lang==='it')return;const miss=collectNew();if(!miss.length)return;
 try{const r=await (await fetch('/translate',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({lang:__lang,texts:miss})})).json();
  Object.assign(__TC,r||{});applyTC();}catch(e){}}
function scheduleTrans(){if(__lang==='it')return;applyTC();clearTimeout(__transT);__transT=setTimeout(fetchNew,80);}
const __transObs=new MutationObserver(scheduleTrans);
function startTrans(){__transObs.observe(document.body,{childList:true,subtree:true,characterData:true});}
function buildLangBtn(){const b=$('#langbtn');if(b)b.textContent=flagOf(__lang);}
function renderLangList(filter){const f=(filter||'').toLowerCase();
 const items=__langs.filter(l=>!f||l.name.toLowerCase().includes(f)||l.code.includes(f));
 const box=$('#llist');if(!box)return;
 box.innerHTML=items.map(l=>`<button class="lopt ${l.code===__lang?'on':''}" data-c="${l.code}"><span class="fl">${flagOf(l.code)}</span><span>${esc(l.name)}</span></button>`).join('');
 box.querySelectorAll('.lopt').forEach(b=>b.onclick=()=>{$('#langpop').classList.remove('on');setLang(b.dataset.c);});}
function buildLangPop(){const pop=$('#langpop');pop.innerHTML=`<input class="lsearch" id="lsearch" placeholder="Cerca lingua..."><div id="llist"></div>`;
 renderLangList('');const se=$('#lsearch');se.oninput=()=>renderLangList(se.value);}
async function setLang(code){const b=$('#langbtn');
 if(code!=='it'){if(b){b.classList.add('spin');b.textContent='…';b.title='Preparo la lingua (scarico una volta il pacchetto, poi e istantaneo)...';}
   let st;try{st=await (await fetch('/mt-install',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({lang:code})})).json();}catch(e){st={ok:false,err:'rete'};}
   if(b){b.classList.remove('spin');b.title='Lingua';}
   if(!st||!st.ok){buildLangBtn();alert('Lingua non disponibile offline ('+((st&&st.err)||'errore')+'). Serve un pacchetto per questa lingua.');return;}}
 __lang=code;__TC={};
 await fetch('/llm-config',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({lang:code})}).catch(()=>{});
 buildLangBtn();
 if(__lang!=='it'){startTrans();await fetchNew();}
 try{go(cur);}catch(e){}}
$('#langbtn').onclick=e=>{e.stopPropagation();const pop=$('#langpop');if(pop.classList.contains('on')){pop.classList.remove('on');return;}buildLangPop();pop.classList.add('on');const se=$('#lsearch');if(se)se.focus();};
document.addEventListener('click',e=>{const pop=$('#langpop');if(pop&&!pop.contains(e.target)&&e.target.id!=='langbtn')pop.classList.remove('on');});
(async()=>{try{const c=await (await fetch('/llm-config')).json();__lang=c.lang||'it';__langs=c.langs||[];}catch(e){__langs=[{code:'it',name:'Italiano'}];}
 buildLangBtn();if(__lang!=='it'){startTrans();await fetchNew();}})();

// ---- PWA + notifiche desktop ----
if('serviceWorker' in navigator){navigator.serviceWorker.register('/sw.js').catch(()=>{});}
let __pwaPrompt=null;
window.addEventListener('beforeinstallprompt',e=>{e.preventDefault();__pwaPrompt=e;});
function computeAlerts(){
 const a=[];
 const cy=P.cyber.filter(r=>r.relevant);
 if(cy.length)a.push({id:'cy'+cy.length,t:cy.length+' minacce ti riguardano',b:(cy[0].product||cy[0].name||cy[0].cve||'')});
 const d=P.disco||{},info=d.disco||{};
 if(info.free_pct!=null&&info.free_pct<15)a.push({id:'disk'+info.free_gb,t:'Disco quasi pieno',b:info.free_gb+' GB liberi ('+info.free_pct+'%)'});
 const nw=P.github.filter(r=>r.new_today);
 if(nw.length)a.push({id:'gh'+nw.length,t:nw.length+' nuove repo oggi',b:(nw[0]?nw[0].full_name:'')});
 const rise=ghRadar();
 if(rise.length)a.push({id:'rise'+rise.length,t:rise.length+' repo in forte crescita',b:(rise[0]?rise[0].full_name:'')});
 const today=new Date().toISOString().slice(0,10);
 (LS.get('agenda',[])||[]).forEach(it=>{if(!it.done&&it.date<=today)a.push({id:'ag'+it.id,t:it.date<today?'Scaduto: '+it.title:'Oggi: '+it.title,b:it.time||''});});
 return a;
}
function fireAlerts(force){
 if(!('Notification' in window)||Notification.permission!=='granted')return;
 const day=new Date().toISOString().slice(0,10);const seen=LS.get('notif_seen',{});
 computeAlerts().forEach(a=>{const k=day+':'+a.id;if(!force&&seen[k])return;seen[k]=1;
   try{new Notification('miAi · '+a.t,{body:a.b,icon:'/icon.svg'});}catch(e){}});
 LS.set('notif_seen',seen);
}
function setNotif(on){const c=$('#notif');c.className='chip '+(on?'on':'off');$('#notif-sw').textContent=on?'on':'off';$('#notif-lbl').textContent=on?'Avvisi attivi':'Avvisi';}
let notifOn=LS.get('notif_on',false)&&('Notification' in window)&&Notification.permission==='granted';
setNotif(notifOn);
$('#notif').onclick=async()=>{
 if(!('Notification' in window)){alert('Il browser non supporta le notifiche.');return;}
 if(notifOn){notifOn=false;LS.set('notif_on',false);setNotif(false);return;}
 let p=Notification.permission;if(p!=='granted')p=await Notification.requestPermission();
 if(p==='granted'){notifOn=true;LS.set('notif_on',true);setNotif(true);fireAlerts(true);}
};
if(notifOn)setTimeout(()=>fireAlerts(false),1500);
function spark(vals,w,h){w=w||130;h=h||32;if(!vals||vals.length<2)return '';
 const max=Math.max(...vals),min=Math.min(...vals),rng=(max-min)||1;
 const pts=vals.map((v,i)=>((i/(vals.length-1))*w).toFixed(1)+','+(h-((v-min)/rng)*(h-4)-2).toFixed(1)).join(' ');
 return `<svg width="${w}" height="${h}" viewBox="0 0 ${w} ${h}" style="display:block;margin-top:6px"><polyline points="${pts}" fill="none" stroke="var(--acc)" stroke-width="2" vector-effect="non-scaling-stroke" stroke-linecap="round" stroke-linejoin="round"/></svg>`;}

$('#refresh').onclick=async()=>{const b=$('#refresh');b.classList.add('spin');try{await fetch('/refresh',{method:'POST'});}catch(e){}
 setTimeout(()=>b.classList.remove('spin'),1800);};
$('#update').onclick=async()=>{const b=$('#update');b.classList.add('spin');
 try{const r=await (await fetch('/update',{method:'POST'})).json();
   if(r&&r.ok===false){b.classList.remove('spin');alert('Aggiornamento fallito: '+(r.err||'errore'));return;}
   location.reload();}
 catch(e){location.reload();}};

// ---- router ----
let cur='github',query='',viewRows=[],detailCtx={},detailObj=null;
const RENDER={};
const DIFF={alta:'r',media:'am',bassa:'g'};
function go(id){
 if(id==='cyber'||id==='blockchain'||id==='mercato'||id==='notizie'){window.__gioTab=(id==='mercato'?'notizie':id);id='giornale';}  // sezioni unite nel Giornale
 cur=id;query='';$('#q').value='';
 document.querySelectorAll('.nav').forEach(b=>b.classList.toggle('on',b.dataset.view===id));
 const n=NAV.find(x=>x.id===id)||{label:id,desc:''};$('#pt').textContent=n.label;$('#pd').textContent=n.desc||'';
 $('#searchbox').style.display=(id==='idee')?'flex':'none';
 (RENDER[id]||soon)(id);}
$('#q').oninput=e=>{query=e.target.value.toLowerCase();(RENDER[cur]||soon)(cur);};
$('#view').addEventListener('click',e=>{
 if(e.target.closest('a,button,select,input,label,.star'))return;
 const c=e.target.closest('.grid .card');if(!c)return;
 const idx=[...$('#view').querySelectorAll('.grid .card')].indexOf(c);
 const dk=(cur==='giornale')?(window.__gioTab||'notizie'):cur;
 if(idx>=0&&DETAIL[dk])openDetail(dk,idx);
});

function soon(id){const n=NAV.find(x=>x.id===id);
 $('#view').innerHTML=`<div class="soon"><div class="ic">${svg(n.icon)}</div><h3>${esc(n.label)}</h3><p>${esc(n.desc||'')} Questa sezione entra nella prossima fase: lo scheletro e pronto, i dati sono gia raccolti dall'agente.</p></div>`;}

function kpis(arr){return `<div class="kpis">${arr.map(k=>`<div class="kpi ${k.cls||''}"><div class="k">${esc(k.k)}</div><div class="v num">${k.v}${k.sub?` <small>${esc(k.sub)}</small>`:''}</div></div>`).join('')}</div>`;}

// ================= GitHub =================
const saved=()=>LS.get('gh_saved',[]);
function toggleSave(fn){const s=saved();const i=s.indexOf(fn);i<0?s.push(fn):s.splice(i,1);LS.set('gh_saved',s);RENDER.github('github');}
function ghRadar(){const vels=P.github.map(r=>r.vel||0).filter(v=>v>0).sort((a,b)=>b-a);
 if(!vels.length)return [];const th=Math.max(15,vels[Math.floor(vels.length*0.15)]||vels[0]);
 return P.github.filter(r=>(r.vel||0)>=th);}
function ghCards(rows){const hot=new Set(ghRadar().map(r=>r.full_name));
 return rows.map(r=>{
  const on=saved().includes(r.full_name);const hi=(r.score||0)>=8;
  const lic=r.license?`<span class="tag ${/mit|apache|bsd|isc|mpl/i.test(r.license)?'g':(/gpl|agpl/i.test(r.license)?'am':'')}">${esc(r.license)}</span>`:'<span class="tag r">senza licenza</span>';
  return `<div class="card">
   <div class="ch"><div class="ct"><a href="${esc(r.url)}" target="_blank" rel="noopener">${esc(r.full_name)}</a>${r.new_today?' <span class="tag g">nuova</span>':''}${hot.has(r.full_name)?' <span class="tag radar">in forte crescita</span>':''}</div><div class="score ${hi?'hi':''} num">${r.score??'-'}</div></div>
   ${r.description?`<div class="desc">${esc(demoji(r.description))}</div>`:''}
   <div class="tags">${r.tipo?`<span class="tag acc">${esc(r.tipo)}</span>`:''}${r.category?`<span class="tag">${esc(r.category)}</span>`:''}${r.language?`<span class="tag">${esc(r.language)}</span>`:''}</div>
   <div class="meta"><span>&#9733; <b class="num">${nfmt(r.stars||0)}</b></span>${r.vel?`<span>&#9650; <b class="num">${r.vel}</b>/g</span>`:''}${r.pushed?`<span>agg. <b class="num">${esc(r.pushed)}</b></span>`:''}</div>
   <div class="cfoot">${lic}<a class="btn" href="${esc(r.url)}" target="_blank" rel="noopener">${svg('ext')} Apri</a>
    <button class="star ${on?'on':''}" title="salva" onclick="toggleSave('${r.full_name.replace(/'/g,"\\'")}')">${svg('star')}</button></div>
  </div>`;}).join('');}
RENDER.github=function(){
 const rows=applyNews(P.github.slice(),'github');viewRows=rows;
 const hot=new Set(ghRadar().map(r=>r.full_name));
 const K=[
  {k:'Repository',v:P.github.length,cls:'a'},
  {k:'Nuove oggi',v:P.github.filter(r=>r.new_today).length,cls:'g'},
  {k:'In forte crescita',v:hot.size,cls:'am'},
  {k:'Commerciale OK',v:P.github.filter(r=>/mit|apache|bsd|isc|mpl/i.test(r.license||'')).length},
  {k:'Salvate',v:saved().length}];
 $('#view').innerHTML=kpis(K)+newsBar('github')+(rows.length?`<div class="grid">${ghCards(rows)}</div>`:'<div class="empty">Nessun risultato per questi filtri.</div>');
 wireBar('github',()=>RENDER.github('github'));
};

// ================= Lista spesa =================
RENDER.spesa=function(){
 const list=LS.get('spesa_items',[]);const tpls=LS.get('spesa_tpl',[]);
 const done=list.filter(i=>i.done).length;
 $('#view').innerHTML=`
 ${kpis([{k:'Articoli',v:list.length,cls:'a'},{k:'Presi',v:done,cls:'g'},{k:'Da prendere',v:list.length-done,cls:'am'},{k:'Modelli salvati',v:tpls.length}])}
 <div class="two">
  <div class="panel">
   <div class="panel-h">${svg('cart')} La mia spesa <span class="cnt num">${list.length-done} da prendere</span></div>
   <div class="panel-b">
    <div class="addrow">
     <input class="inp" id="sp-nm" placeholder="Aggiungi articolo, es. Latte">
     <input class="inp" id="sp-qty" placeholder="q.ta" style="max-width:92px;min-width:0">
     <button class="btn pri" id="sp-add">${svg('plus')} Aggiungi</button>
    </div>
    <ul class="slist" id="sp-list"></ul>
    ${list.length?`<div class="sactions">
      <button class="btn" id="sp-savetpl">Salva come modello</button>
      <button class="btn" id="sp-cleardone">Rimuovi presi</button>
      <button class="btn" id="sp-clear">Svuota</button></div>`:''}
   </div>
  </div>
  <div class="panel">
   <div class="panel-h">Modelli</div>
   <div class="panel-b">
    <p class="mini" style="margin-top:0;margin-bottom:14px">Salva una spesa ricorrente e richiamala con un clic.</p>
    <div id="sp-tpls"></div>
    ${tpls.length?'':'<div class="mini">Ancora nessun modello.</div>'}
   </div>
  </div>
 </div>`;
 const listEl=$('#sp-list');
 listEl.innerHTML=list.map((it,i)=>`<li class="sitem ${it.done?'done':''}">
   <div class="cb" data-i="${i}">${svg('check')}</div>
   <span class="nm">${esc(it.nm)}</span>${it.qty?`<span class="qty num">${esc(it.qty)}</span>`:''}
   <button class="del" data-i="${i}">${svg('x')}</button></li>`).join('')||'<div class="mini" style="padding:14px 0">Lista vuota. Aggiungi il primo articolo.</div>';
 const save=l=>{LS.set('spesa_items',l);RENDER.spesa();};
 const add=()=>{const nm=$('#sp-nm').value.trim();if(!nm)return;const qty=$('#sp-qty').value.trim();
  const l=LS.get('spesa_items',[]);l.push({nm,qty,done:false});save(l);};
 $('#sp-add').onclick=add;
 $('#sp-nm').onkeydown=e=>{if(e.key==='Enter')add();};$('#sp-qty').onkeydown=e=>{if(e.key==='Enter')add();};
 listEl.querySelectorAll('.cb').forEach(c=>c.onclick=()=>{const l=LS.get('spesa_items',[]);l[c.dataset.i].done=!l[c.dataset.i].done;save(l);});
 listEl.querySelectorAll('.del').forEach(d=>d.onclick=()=>{const l=LS.get('spesa_items',[]);l.splice(d.dataset.i,1);save(l);});
 const sc=$('#sp-clear');if(sc)sc.onclick=()=>{if(confirm('Svuotare la lista?'))save([]);};
 const cd=$('#sp-cleardone');if(cd)cd.onclick=()=>save(LS.get('spesa_items',[]).filter(i=>!i.done));
 const st=$('#sp-savetpl');if(st)st.onclick=()=>{const nm=prompt('Nome del modello:','Spesa settimanale');if(!nm)return;
  const t=LS.get('spesa_tpl',[]);t.push({nm,items:LS.get('spesa_items',[]).map(i=>({nm:i.nm,qty:i.qty}))});LS.set('spesa_tpl',t);RENDER.spesa();};
 const te=$('#sp-tpls');
 te.innerHTML=tpls.map((t,i)=>`<div class="tpl"><div style="flex:1"><div class="tn">${esc(t.nm)}</div><div class="tc num">${t.items.length} articoli</div></div>
   <button data-load="${i}">Carica</button><button data-del="${i}">Elimina</button></div>`).join('');
 te.querySelectorAll('[data-load]').forEach(b=>b.onclick=()=>{const t=LS.get('spesa_tpl',[])[b.dataset.load];
  LS.set('spesa_items',t.items.map(i=>({nm:i.nm,qty:i.qty,done:false})));RENDER.spesa();});
 te.querySelectorAll('[data-del]').forEach(b=>b.onclick=()=>{const t=LS.get('spesa_tpl',[]);t.splice(b.dataset.del,1);LS.set('spesa_tpl',t);RENDER.spesa();});
};

// ================= Filtri condivisi (Giornale + GitHub) =================
const FILT={};
function filt(k){return FILT[k]||(FILT[k]={q:'',sort:'',period:'',stars:0});}
function newsDate(x,kind){let d=(kind==='github')?x.pushed:(kind==='cyber')?x.date:null;
 if(!d)return 0;const t=Date.parse((''+d).length<=10?d+'T00:00':d);return isNaN(t)?0:t;}
function newsText(x,kind){
 if(kind==='github')return (x.full_name+' '+(x.description||'')+' '+(x.tipo||'')+' '+(x.category||'')+' '+(x.language||'')).toLowerCase();
 if(kind==='cyber')return ((x.product||'')+' '+(x.name||'')+' '+(x.cve||'')+' '+(x.vendor||'')+' '+(x.desc||'')).toLowerCase();
 if(kind==='blockchain')return (x.full_name+' '+(x.description||'')+' '+(x.topics||[]).join(' ')).toLowerCase();
 return '';}
const PERIODS=[['','sempre'],['7','ultimi 7 giorni'],['30','ultimi 30 giorni'],['90','ultimi 90 giorni'],['365','ultimo anno']];
const STARSOPT=[['0','stelle: tutte'],['100','100+ stelle'],['500','500+ stelle'],['1000','1k+ stelle'],['5000','5k+ stelle'],['20000','20k+ stelle']];
const NSORTS={github:[['','consigliati'],['recenti','piu recenti'],['stelle','piu stelle'],['vel','in crescita'],['az','A-Z']],
 blockchain:[['','consigliati'],['stelle','piu stelle'],['az','A-Z']],
 cyber:[['','consigliati'],['recenti','piu recenti'],['pop','popolarita']],
 mercato:[['','consigliati'],['pop','piu notizie'],['impatto','impatto']]};
function newsBar(kind){const f=filt(kind);
 const dated=(kind==='github'||kind==='cyber'||kind==='mercato');const starred=(kind==='github'||kind==='blockchain');
 const S=NSORTS[kind]||[['','consigliati']];const active=f.q||f.sort||f.period||(+f.stars);
 return `<div class="toolbar newsbar">
   <label class="search" style="flex:1;min-width:170px"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-linecap="round"><circle cx="11" cy="11" r="7"/><path d="m21 21-4-4"/></svg><input id="nb-q" placeholder="Cerca..." value="${escA(f.q)}"></label>
   <select class="inp" id="nb-sort" style="max-width:160px" title="ordina">${S.map(s=>`<option value="${s[0]}" ${f.sort===s[0]?'selected':''}>${esc(s[1])}</option>`).join('')}</select>
   ${dated?`<select class="inp" id="nb-per" style="max-width:160px" title="periodo">${PERIODS.map(p=>`<option value="${p[0]}" ${f.period===p[0]?'selected':''}>${esc(p[1])}</option>`).join('')}</select>`:''}
   ${starred?`<select class="inp" id="nb-star" style="max-width:150px" title="stelle minime">${STARSOPT.map(s=>`<option value="${s[0]}" ${(''+f.stars)===s[0]?'selected':''}>${esc(s[1])}</option>`).join('')}</select>`:''}
   ${active?`<button class="btn" id="nb-reset" title="azzera filtri">${svg('x')}</button>`:''}</div>`;}
function wireBar(kind,rerender){const f=filt(kind);
 const q=$('#nb-q');if(q){q.oninput=()=>{f.q=q.value.trim().toLowerCase();clearTimeout(f._t);f._t=setTimeout(rerender,200);};}
 const s=$('#nb-sort');if(s)s.onchange=()=>{f.sort=s.value;rerender();};
 const p=$('#nb-per');if(p)p.onchange=()=>{f.period=p.value;rerender();};
 const st=$('#nb-star');if(st)st.onchange=()=>{f.stars=+st.value;rerender();};
 const r=$('#nb-reset');if(r)r.onclick=()=>{FILT[kind]={q:'',sort:'',period:'',stars:0};rerender();};}
function applyNews(rows,kind){const f=filt(kind);let r=rows.slice();
 if(f.q)r=r.filter(x=>newsText(x,kind).includes(f.q));
 if(f.period&&(kind==='github'||kind==='cyber')){const cut=Date.now()-(+f.period)*864e5;r=r.filter(x=>{const d=newsDate(x,kind);return d&&d>=cut;});}
 if(+f.stars)r=r.filter(x=>(x.stars||0)>=+f.stars);
 const by=f.sort;
 if(by==='stelle')r.sort((a,b)=>(b.stars||0)-(a.stars||0));
 else if(by==='recenti')r.sort((a,b)=>newsDate(b,kind)-newsDate(a,kind));
 else if(by==='vel')r.sort((a,b)=>(b.vel||0)-(a.vel||0));
 else if(by==='az')r.sort((a,b)=>(''+(a.full_name||a.product||a.name||'')).localeCompare(b.full_name||b.product||b.name||''));
 else if(by==='pop'&&kind==='cyber')r.sort((a,b)=>((b.ransomware?2:0)+(b.relevant?1:0))-((a.ransomware?2:0)+(a.relevant?1:0)));
 return r;}

// ================= Giornale (Cyber + Blockchain + Mercato) =================
function cyberCards(rows){return rows.map(r=>`<div class="card">
   <div class="ch"><div class="ct">${esc(r.product||r.name||r.cve)}</div></div>
   <div class="tags">${r.cve?`<span class="tag">${esc(r.cve)}</span>`:''}${r.vendor&&r.vendor!==r.product?`<span class="tag">${esc(r.vendor)}</span>`:''}${r.ransomware?'<span class="tag r">ransomware</span>':''}${r.relevant?'<span class="tag g">ti riguarda</span>':''}</div>
   ${r.desc?`<div class="desc">${esc(demoji(r.desc))}</div>`:''}
   ${r.action?`<div class="note"><b>Azione:</b> ${esc(demoji(r.action))}</div>`:''}
   <div class="cfoot">${r.date?`<span class="tag">agg. ${esc(r.date)}</span>`:''}${r.url?`<a class="btn" href="${esc(r.url)}" target="_blank" rel="noopener">${svg('ext')} Dettagli</a>`:''}</div>
  </div>`).join('');}
function blockCards(rows){return rows.map(r=>`<div class="card">
   <div class="ch"><div class="ct"><a href="${esc(r.url)}" target="_blank" rel="noopener">${esc(r.full_name)}</a></div>
    ${r.audit?'<span class="tag g">audit</span>':'<span class="tag am">no audit</span>'}</div>
   ${r.description?`<div class="desc">${esc(demoji(r.description))}</div>`:''}
   <div class="tags">${(r.topics||[]).slice(0,4).map(t=>`<span class="tag">${esc(t)}</span>`).join('')}</div>
   <div class="cfoot"><span class="meta"><span>&#9733; <b class="num">${nfmt(r.stars||0)}</b></span></span>
    ${r.language?`<span class="tag acc">${esc(r.language)}</span>`:''}
    <a class="btn" href="${esc(r.url)}" target="_blank" rel="noopener" style="margin-left:auto">${svg('ext')} Apri</a></div>
  </div>`).join('');}
function mercatoCards(rows){return rows.map(r=>{
  const items=(r.items||[]).slice(0,4);const a=r.analisi||{};
  const dirCls=/ribass|calo|negativ/i.test(a.direzione||'')?'r':(/rialz|cresc|positiv/i.test(a.direzione||'')?'g':'');
  return `<div class="card">
   <div class="ch"><div class="ct">${esc(r.topic)}</div><span class="tag" style="margin-left:auto">${(r.items||[]).length} notizie</span></div>
   <div class="tags">${r.cat?`<span class="tag">${esc(r.cat)}</span>`:''}${a.direzione?`<span class="tag ${dirCls}">${esc(a.direzione)}</span>`:''}${a.impatto?`<span class="tag ${IMP[(a.impatto||'').toLowerCase()]||''}">impatto ${esc(a.impatto)}</span>`:''}</div>
   ${a.significa?`<div class="note"><b>Lettura:</b> ${esc(demoji(a.significa))}</div>`:''}
   ${items.length?`<ul class="mlist">${items.map(it=>`<li><a href="${esc(it.url)}" target="_blank" rel="noopener">${esc(demoji(it.title))}</a></li>`).join('')}</ul>`:''}
  </div>`;}).join('');}
let __newsData=null,__newsTopic='';
async function loadNews(force){
 if(__newsData!==null&&!force)return __newsData;
 try{__newsData=await (await fetch('/news')).json();}catch(e){__newsData=[];}
 return __newsData;}
function newsFiltered(){const f=filt('mercato');let rows=(__newsData||[]).slice();
 if(__newsTopic)rows=rows.filter(r=>r.id===__newsTopic);
 rows=rows.map(r=>{let items=(r.items||[]);
   if(f.q)items=items.filter(it=>(it.title||'').toLowerCase().includes(f.q));
   if(f.period){const cut=Date.now()-(+f.period)*864e5;items=items.filter(it=>{const t=Date.parse(it.date||'');return isNaN(t)?true:t>=cut;});}
   return Object.assign({},r,{items});});
 if(f.q||f.period||__newsTopic)rows=rows.filter(r=>(r.items||[]).length);
 if(f.sort==='pop')rows.sort((a,b)=>(b.items||[]).length-(a.items||[]).length);
 return rows;}
const GIO_TABS=[['notizie','Notizie','news'],['cyber','Cyber','shield'],['blockchain','Blockchain','box']];
function gioGo(t){window.__gioTab=t;RENDER.giornale('giornale');}
function gioTabbar(tab){return `<div class="giotop"><div class="seg gioseg">${GIO_TABS.map(t=>`<button class="segb ${tab===t[0]?'on':''}" onclick="gioGo('${t[0]}')">${svg(t[2])} ${t[1]}</button>`).join('')}</div></div>`;}
RENDER.giornale=async function(){
 const tab=window.__gioTab||'notizie';
 if(tab==='notizie'){
  if(__newsData===null){$('#view').innerHTML=gioTabbar(tab)+'<div class="dwait">Carico le notizie...</div>';await loadNews();}
  return renderNotizie();
 }
 let K,rows,body;
 if(tab==='cyber'){
  rows=applyNews(P.cyber.slice(),'cyber');
  K=[{k:'Minacce',v:P.cyber.length,cls:'a'},{k:'Ransomware',v:P.cyber.filter(r=>r.ransomware).length,cls:'r'},{k:'Ti riguarda',v:P.cyber.filter(r=>r.relevant).length,cls:'g'},{k:'Mostrate',v:rows.length,cls:'am'}];
  body=rows.length?`<div class="grid">${cyberCards(rows)}</div>`:'<div class="empty">Nessuna minaccia con questi filtri.</div>';
 }else{
  rows=applyNews(P.blockchain.slice(),'blockchain');
  K=[{k:'Progetti',v:P.blockchain.length,cls:'a'},{k:'Con audit',v:P.blockchain.filter(r=>r.audit).length,cls:'g'},{k:'Senza audit',v:P.blockchain.filter(r=>!r.audit).length,cls:'am'},{k:'Mostrati',v:rows.length}];
  body=rows.length?`<div class="grid">${blockCards(rows)}</div>`:'<div class="empty">Nessun progetto con questi filtri.</div>';
 }
 viewRows=rows;
 $('#view').innerHTML=kpis(K)+gioTabbar(tab)+newsBar(tab)+body;
 wireBar(tab,()=>RENDER.giornale('giornale'));
};
function renderNotizie(){
 const rows=newsFiltered();viewRows=rows;
 const tot=rows.reduce((s,r)=>s+((r.items||[]).length),0);
 const K=[{k:'Argomenti seguiti',v:(__newsData||[]).length,cls:'a'},{k:'Notizie',v:tot,cls:'am'},{k:'Mostrati',v:rows.length}];
 const chips=`<div class="chatchips" style="margin:0 0 12px"><span class="tag ${__newsTopic?'':'acc'}" onclick="newsTopic('')">Tutti</span>${(__newsData||[]).map(r=>`<span class="tag ${__newsTopic===r.id?'acc':''}" onclick="newsTopic('${r.id}')">${esc(r.topic)}</span>`).join('')}<span class="tag" style="border:1px dashed var(--line2);cursor:pointer" onclick="newsPicker()">${svg('plus')} Gestisci argomenti</span></div>`;
 const body=(__newsData||[]).length?(rows.length?`<div class="grid">${mercatoCards(rows)}</div>`:'<div class="empty">Nessuna notizia con questi filtri.</div>')
   :`<div class="empty">Nessun argomento seguito. <br><br><button class="btn pri" onclick="newsPicker()">${svg('plus')} Scegli gli argomenti</button></div>`;
 $('#view').innerHTML=kpis(K)+gioTabbar('notizie')+chips+newsBar('mercato')+body;
 wireBar('mercato',()=>renderNotizie());
}
function newsTopic(id){__newsTopic=id;renderNotizie();}
function ovClose(){$('#onbov').classList.remove('on');$('#onbov').innerHTML='';}
async function newsPicker(){
 const ov=$('#onbov');ov.classList.add('on');ov.innerHTML='<div class="onbcard"><div class="dwait">Carico gli argomenti...</div></div>';
 let d;try{d=await (await fetch('/topics')).json();}catch(e){ov.innerHTML='<div class="onbcard"><div class="empty">Errore nel leggere gli argomenti.</div></div>';return;}
 const foll=new Set(d.followed||[]);const cats={};
 (d.catalog||[]).forEach(t=>{(cats[t.cat]=cats[t.cat]||[]).push(t);});
 let body='';Object.keys(cats).forEach(c=>{body+=`<div class="onbgrp">${esc(c)}</div>`;
   cats[c].forEach(t=>{body+=`<div class="onbsec ${foll.has(t.id)?'on':''}" data-id="${t.id}" onclick="this.classList.toggle('on')"><span class="cb">${svg('check')}</span><div><b style="font-size:14px">${esc(t.label)}</b></div></div>`;});});
 ov.innerHTML=`<div class="onbcard"><h2>Scegli gli argomenti</h2><div class="sub">Il Giornale mostrera le notizie degli argomenti che segui. Cambiali quando vuoi.</div>
  ${body}<div style="display:flex;gap:10px;justify-content:flex-end;margin-top:18px"><button class="btn" onclick="ovClose()">Annulla</button><button class="btn pri" onclick="newsSave()">${svg('check')} Salva</button></div></div>`;
}
async function newsSave(){
 const ids=[...document.querySelectorAll('#onbov .onbsec.on')].map(e=>e.dataset.id);
 ovClose();__newsData=null;__newsTopic='';
 $('#view').innerHTML=gioTabbar('notizie')+'<div class="dwait">Aggiorno le notizie sugli argomenti scelti... (puo volerci qualche secondo)</div>';
 try{await fetch('/topics',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({followed:ids})});}catch(e){}
 await newsWait();await loadNews(true);renderNotizie();
}
async function newsWait(max){max=max||20;
 for(let i=0;i<max;i++){try{const s=await (await fetch('/news-status')).json();if(!s.running&&i>0)return;}catch(e){}await new Promise(r=>setTimeout(r,1500));}}

// ================= Idee =================
const LIV={alta:'g',media:'am',bassa:'r'};
const SECTORS=["Sanita","Energia e clima","Fintech","AI e software B2B","Mobilita","Cybersecurity","Agrifood","Education","Spazio","Gaming","Legaltech","Proptech","Sport e wellness","Media e creator","Robotica","Industria 4.0","Retail e commerce","Travel","Insurtech","Lavoro e HR","Materiali e nanotech","Quantum","Musica e audio","Arte e moda"];
const favs=()=>LS.get('idee_fav',[]);
function toggleFav(obj){if(!obj||!obj.titolo)return;const f=favs();const i=f.findIndex(x=>x.titolo===obj.titolo);
 if(i>=0)f.splice(i,1);else f.push(obj);LS.set('idee_fav',f);}
function toggleFavIdx(i){toggleFav(viewRows[i]);RENDER.idee('idee');}
let ideeMode='lista',swCur=null;
const fuseSel=new Set();
function toggleFuse(t){fuseSel.has(t)?fuseSel.delete(t):fuseSel.add(t);RENDER.idee('idee');}
async function fuseGo(){
 const ideas=viewRows.filter(r=>fuseSel.has(r.titolo)).map(r=>({titolo:r.titolo,descrizione:r.descrizione}));
 if(ideas.length<2)return;
 $('#detail').innerHTML=`<div class="dcard"><div class="dbody"><div class="dwait">Fondo ${ideas.length} idee con Ollama...</div></div></div>`;
 $('#detail').classList.add('on');
 try{
  const d=await (await fetch('/fondi',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({ideas})})).json();
  if(d.error){$('#detail').innerHTML=`<div class="dcard"><div class="dhead"><div class="dt">Fusione</div><button class="dx" onclick="closeDetail()">${svg('x')}</button></div><div class="dbody"><div class="dwait">Ollama non disponibile (${esc(d.error)}). Accendilo e riprova.</div></div></div>`;return;}
  const fav=favs();const on=fav.some(x=>x.titolo===d.titolo);
  window.__fused=d;
  $('#detail').innerHTML=`<div class="dcard">
    <div class="dhead"><div class="dt">${esc(d.titolo)} <span class="tag am">idea fusa</span></div><button class="dx" onclick="closeDetail()">${svg('x')}</button></div>
    <div class="dbody">
     <div class="tags dtags">${(d.fonti||[]).map(f=>`<span class="tag">${esc(f)}</span>`).join('')}${d.fattibilita?`<span class="tag ${LIV[(d.fattibilita||'').toLowerCase()]||''}">fattibilita ${esc(d.fattibilita)}</span>`:''}</div>
     ${drow('Descrizione',esc(demoji(d.descrizione||'')))}
     ${drow('Sinergia',esc(demoji(d.sinergia||'')))}
     ${drow('Problema',esc(demoji(d.problema||'')))}
     ${drow('Mercato',esc(demoji(d.tam||'')))}
     ${drow('Primi passi',ulH(d.passi))}
     <div class="dmap-actions" style="margin-top:22px"><button class="btn pri" id="fuse-save">${svg('star')} ${on?'Salvata':'Salva nei preferiti'}</button><button class="btn" onclick="dlFused()">${svg('download')} .md</button></div>
    </div></div>`;
  $('#fuse-save').onclick=()=>{const f=favs();if(!f.some(x=>x.titolo===d.titolo)){d._swipe=true;f.push(d);LS.set('idee_fav',f);}$('#fuse-save').innerHTML=svg('check')+' Salvata';fuseSel.clear();};
 }catch(e){$('#detail').innerHTML=`<div class="dcard"><div class="dbody"><div class="dwait">Errore di rete.</div></div></div>`;}
}
RENDER.idee=function(){
 const f=favs();const favT=new Set(f.map(x=>x.titolo));
 const custom=f.filter(x=>x._swipe&&!P.idee.some(p=>p.titolo===x.titolo));
 let rows=[...custom,...P.idee];
 if(query)rows=rows.filter(r=>(r.titolo+' '+(r.descrizione||'')+' '+(r.settore||'')).toLowerCase().includes(query));
 viewRows=rows;
 const K=[{k:'Idee',v:P.idee.length,cls:'a'},
  {k:'Alta fattibilita',v:P.idee.filter(r=>/alta/i.test(r.fattibilita||'')).length,cls:'g'},
  {k:'Preferite',v:f.length,cls:'am'},
  {k:'Gia presidiate',v:P.idee.filter(r=>r.web_esiste).length,cls:'r'}];
 const modeBar=`<div class="toolbar" style="margin-bottom:20px;justify-content:space-between"><div class="seg">
   <button class="segb ${ideeMode==='lista'?'on':''}" data-m="lista">Lista</button>
   <button class="segb ${ideeMode==='scopri'?'on':''}" data-m="scopri">Scopri (swipe)</button></div>
   <button class="btn" onclick="ideePicker()">${svg('settings')} Scegli i tuoi interessi</button></div>`;
 if(ideeMode==='scopri'){renderSwipe(K,modeBar);return;}
 const cards=rows.map((r,i)=>{
  const on=favT.has(r.titolo);const fc=LIV[(r.fattibilita||'').toLowerCase()]||'';
  return `<div class="card">
   <div class="icheck ${fuseSel.has(r.titolo)?'on':''}" title="seleziona per fondere" onclick="event.stopPropagation();toggleFuse('${(r.titolo||'').replace(/'/g,"\\'")}')">${svg('check')}</div>
   <div class="ch" style="padding-right:30px"><div class="ct">${esc(r.titolo)}${r._swipe?' <span class="tag am">scoperta</span>':''}</div></div>
   ${r.descrizione?`<div class="desc">${esc(demoji(r.descrizione))}</div>`:''}
   <div class="tags">${r.settore?`<span class="tag acc">${esc(r.settore)}</span>`:''}${r.fattibilita?`<span class="tag ${fc}">fattibilita ${esc(r.fattibilita)}</span>`:''}${r.novelta?`<span class="tag">novita ${esc(r.novelta)}</span>`:''}</div>
   ${r.tam?`<div class="meta"><span>Mercato: <b>${esc(demoji(r.tam))}</b></span></div>`:''}
   <div class="cfoot">${r.web_esiste?'<span class="tag r">gia presidiato</span>':'<span class="tag g">campo libero</span>'}
    <button class="star ${on?'on':''}" title="preferiti" onclick="event.stopPropagation();toggleFavIdx(${i})">${svg('star')}</button></div>
  </div>`;}).join('');
 const fbar=fuseSel.size>=2?`<div class="fuse-bar"><span>${fuseSel.size} idee selezionate</span><button class="btn pri" onclick="fuseGo()">${svg('merge')} Fondi in una startup</button><button class="btn" onclick="fuseSel.clear();RENDER.idee('idee')">Annulla</button></div>`:'';
 $('#view').innerHTML=kpis(K)+modeBar+(cards?`<div class="grid">${cards}</div>`:'<div class="empty">Nessuna idea per questa ricerca.</div>')+fbar;
 document.querySelectorAll('.segb').forEach(b=>b.onclick=()=>{ideeMode=b.dataset.m;RENDER.idee('idee');});
};
async function ideePicker(){
 const ov=$('#onbov');ov.classList.add('on');ov.innerHTML='<div class="onbcard"><div class="dwait">Carico gli argomenti...</div></div>';
 let d;try{d=await (await fetch('/interests')).json();}catch(e){ov.innerHTML='<div class="onbcard"><div class="empty">Errore nel leggere gli argomenti.</div></div>';return;}
 const sel=new Set(d.selected||[]);
 const body=(d.catalog||[]).map(t=>`<div class="onbsec ${sel.has(t.id)?'on':''}" data-id="${t.id}" onclick="this.classList.toggle('on')"><span class="cb">${svg('check')}</span><div><b style="font-size:14px">${esc(t.label)}</b></div></div>`).join('');
 ov.innerHTML=`<div class="onbcard"><h2>Scegli i tuoi interessi</h2><div class="sub">Le idee seguiranno gli argomenti che scegli tu. Al prossimo aggiornamento verranno generate solo su questi settori.</div>
  <div style="display:grid;grid-template-columns:repeat(2,1fr);gap:4px">${body}</div><div style="display:flex;gap:10px;justify-content:flex-end;margin-top:18px"><button class="btn" onclick="ovClose()">Annulla</button><button class="btn pri" onclick="ideeSaveInterests()">${svg('check')} Salva</button></div></div>`;
}
async function ideeSaveInterests(){
 const ids=[...document.querySelectorAll('#onbov .onbsec.on')].map(e=>e.dataset.id);
 ovClose();
 try{await fetch('/interests',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({selected:ids})});}catch(e){}
 const lead=document.createElement('div');lead.className='section-lead';lead.textContent='Interessi salvati. Premi Aggiorna (in alto) per rigenerare le idee sui tuoi settori.';
 const v=$('#view');v.insertBefore(lead,v.firstChild);
}
function renderSwipe(K,modeBar){
 $('#view').innerHTML=kpis(K)+modeBar+`<div class="swipe-wrap">
   <div class="toolbar" style="justify-content:center;margin-bottom:14px"><div class="fld"><label>settore</label>
     <select class="inp" id="sw-set">${SECTORS.map(s=>`<option>${esc(s)}</option>`).join('')}</select></div></div>
   <div class="swipe-stage" id="sw-stage"></div>
   <div class="swipe-actions">
     <button class="swbtn no" id="sw-no" title="cestina (freccia sinistra)">${svg('x')}</button>
     <button class="swbtn skip" id="sw-skip">Altra idea</button>
     <button class="swbtn yes" id="sw-yes" title="preferiti (freccia destra)">${svg('star')}</button>
   </div>
   <p class="mini" style="text-align:center;margin-top:14px">Idee tech generate al momento nel settore scelto. Freccia sinistra cestina, destra salva nei preferiti. Richiede Ollama attivo.</p>
  </div>`;
 document.querySelectorAll('.segb').forEach(b=>b.onclick=()=>{ideeMode=b.dataset.m;RENDER.idee('idee');});
 $('#sw-no').onclick=()=>swAct(false);$('#sw-yes').onclick=()=>swAct(true);
 $('#sw-skip').onclick=()=>loadSwipe();$('#sw-set').onchange=()=>loadSwipe();
 loadSwipe();
}
function swSkeleton(){return `<div class="swipe-card"><div class="sk" style="height:26px;width:55%"></div>
  <div class="sk" style="height:15px;width:92%;margin-top:6px"></div><div class="sk" style="height:15px;width:78%"></div>
  <div class="sk" style="height:15px;width:45%;margin-top:10px"></div>
  <div class="sk" style="height:15px;width:88%"></div><div class="sk" style="height:15px;width:66%"></div></div>`;}
async function loadSwipe(){
 const stage=$('#sw-stage');if(!stage)return;const set=$('#sw-set').value;swCur=null;stage.innerHTML=swSkeleton();
 try{
  const r=await (await fetch('/idea?settore='+encodeURIComponent(set))).json();
  if(r.error){stage.innerHTML=`<div class="swipe-card" style="justify-content:center;text-align:center;color:var(--mut)">Ollama non disponibile (${esc(r.error)}).<br>Accendi Ollama in basso a sinistra, poi premi "Altra idea".</div>`;return;}
  swCur=r;const fc=LIV[(r.fattibilita||'').toLowerCase()]||'';
  stage.innerHTML=`<div class="swipe-card in" id="sw-card">
    <div class="sc-t">${esc(r.titolo)}</div>
    <div class="tags">${r.settore?`<span class="tag acc">${esc(r.settore)}</span>`:''}${r.fattibilita?`<span class="tag ${fc}">fattibilita ${esc(r.fattibilita)}</span>`:''}${r.novelta?`<span class="tag">novita ${esc(r.novelta)}</span>`:''}</div>
    <div class="sc-d">${esc(demoji(r.descrizione||''))}</div>
    <div class="sc-rows">
     ${r.problema?`<div class="sc-r"><b>Problema.</b> ${esc(demoji(r.problema))}</div>`:''}
     ${r.tam?`<div class="sc-r"><b>Mercato.</b> ${esc(demoji(r.tam))}</div>`:''}
     ${(r.passi&&r.passi.length)?`<div class="sc-r"><b>Primo passo.</b> ${esc(demoji(r.passi[0]))}</div>`:''}
    </div></div>`;
 }catch(e){stage.innerHTML='<div class="swipe-card" style="justify-content:center;text-align:center;color:var(--mut)">Errore di rete. Il server e attivo?</div>';}
}
function swAct(save){
 const card=$('#sw-card');
 if(save&&swCur){swCur._swipe=true;const f=favs();if(!f.some(x=>x.titolo===swCur.titolo)){f.push(swCur);LS.set('idee_fav',f);}}
 if(card){card.classList.add(save?'fly-r':'fly-l');setTimeout(loadSwipe,300);}else loadSwipe();
}
document.addEventListener('keydown',e=>{if(cur==='idee'&&ideeMode==='scopri'){if(e.key==='ArrowLeft')swAct(false);else if(e.key==='ArrowRight')swAct(true);}});

// ================= PC =================
const IMP={alto:'r',medio:'am',basso:'acc'};
RENDER.pc=function(){
 const rows=P.pc.slice();viewRows=rows;
 const K=[{k:'Consigli',v:rows.length,cls:'a'},{k:'Alto impatto',v:rows.filter(r=>/alto/i.test(r.impatto||'')).length,cls:'r'}];
 const cards=rows.map(r=>`<div class="card">
   <div class="ch"><div class="ct">${esc(r.titolo)}</div><span class="tag ${IMP[(r.impatto||'').toLowerCase()]||''}" style="margin-left:auto">impatto ${esc(r.impatto||'-')}</span></div>
   ${r.area?`<div class="tags"><span class="tag acc">${esc(r.area)}</span></div>`:''}
   ${r.consiglio?`<div class="desc" style="-webkit-line-clamp:5">${esc(demoji(r.consiglio))}</div>`:''}
  </div>`).join('');
 $('#view').innerHTML=kpis(K)+(cards?`<div class="grid">${cards}</div>`:'<div class="empty">Nessun consiglio disponibile.</div>');
};

// ================= Disco =================
function baseName(p){return (''+p).replace(/[\\/]+$/,'').split(/[\\/]/).pop();}
function escA(s){return (''+s).replace(/&/g,'&amp;').replace(/"/g,'&quot;');}
async function trashFile(btn){const path=btn.getAttribute('data-p');if(!path)return;
 if(!confirm('Spostare nel Cestino di Windows? (reversibile)\n\n'+path))return;
 const old=btn.textContent;btn.disabled=true;btn.textContent='...';
 try{const r=await (await fetch('/trash',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({path})})).json();
  if(r.ok){const row=btn.closest('.frow');if(row)row.style.opacity='.45';btn.className='tag g';btn.textContent=r.gone?'gia rimosso':'nel Cestino';}
  else{alert('Non rimosso: '+(r.err||'errore'));btn.disabled=false;btn.textContent=old;}}
 catch(e){alert('Errore di rete');btn.disabled=false;btn.textContent=old;}}
function copyCmd(btn){const path=btn.getAttribute('data-p');const cmd='Remove-Item -Recurse -Force "'+path+'"';
 (navigator.clipboard?navigator.clipboard.writeText(cmd):Promise.reject()).then(()=>{const o=btn.textContent;btn.textContent='copiato';setTimeout(()=>btn.textContent=o,1500);}).catch(()=>{prompt('Copia il comando:',cmd);});}
RENDER.disco=function(){
 const d=P.disco||{};const info=d.disco||{};const top=d.top||[];const cache=d.cache||[];const freddi=d.freddi||[];const dupes=d.duplicati||[];
 const prev=d.previsione||{};
 const K=[{k:'Spazio libero',v:(info.free_gb??'-'),sub:'GB'+(info.free_pct!=null?' - '+info.free_pct+'%':''),cls:'a'},
  {k:'Liberabile',v:(d.liberabile_gb??'-'),sub:'GB',cls:'g'},
  {k:'File freddi',v:freddi.length,cls:'am'},
  {k:'Duplicati',v:dupes.length,cls:'r'}];
 const maxTop=Math.max(1,...top.map(t=>t.gb||0));
 const topRows=top.slice(0,8).map(t=>`<div class="frow"><div class="fmain"><div class="fn">${esc(t.dir)}</div><div class="dbar"><i style="width:${Math.round((t.gb||0)/maxTop*100)}%"></i></div></div><div class="fg num">${(t.gb||0).toFixed(1)} GB</div></div>`).join('')||'<div class="mini" style="padding:12px 0">Nessun dato.</div>';
 const cacheRows=cache.slice(0,8).map(c=>`<div class="frow"><div class="fmain"><div class="fn">${esc(c.nome)}</div><div class="fp">${esc(c.path)}</div></div><div class="fg num">${(c.gb||0).toFixed(1)} GB</div><button class="btn" style="padding:6px 11px" data-p="${escA(c.path)}" onclick="copyCmd(this)">copia comando</button></div>`).join('')||'<div class="mini" style="padding:12px 0">Nessuna cache trovata.</div>';
 const freddiRows=freddi.slice(0,15).map(f=>`<div class="frow"><div class="fmain"><div class="fn">${esc(baseName(f.path))}</div><div class="fp">${esc(f.path)}</div></div><div class="fg num">${(f.gb||0).toFixed(2)} GB</div><button class="btn" style="padding:6px 11px" data-p="${escA(f.path)}" onclick="trashFile(this)">Cestino</button></div>`).join('')||'<div class="mini" style="padding:12px 0">Nessun file freddo.</div>';
 const dupRows=dupes.length?dupes.map(g=>`<div style="padding:8px 0;border-bottom:1px solid var(--line)"><div style="display:flex;justify-content:space-between;align-items:baseline;margin-bottom:4px"><b>${g.n} copie &middot; spreco ${g.spreco_gb} GB</b><span class="mini">${(g.gb||0).toFixed(2)} GB l'una</span></div>${(g.paths||[]).map((p,idx)=>`<div class="frow" style="padding:8px 0"><div class="fmain"><div class="fn">${esc(baseName(p))}</div><div class="fp">${esc(p)}</div></div>${idx===0?'<span class="tag g">tieni</span>':`<button class="btn" style="padding:6px 11px" data-p="${escA(p)}" onclick="trashFile(this)">Cestino</button>`}</div>`).join('')}</div>`).join(''):'<div class="mini" style="padding:12px 0">Nessun duplicato trovato.</div>';
 const prevNote=prev.stato?`<div class="note" style="margin-bottom:22px"><b>Andamento:</b> ${esc(prev.stato)}${prev.giorni?`, spazio esaurito tra ~${prev.giorni} giorni`:''}${prev.gb_giorno!=null?` (${prev.gb_giorno} GB/giorno)`:''}.</div>`:'';
 $('#view').innerHTML=kpis(K)+prevNote+`
   <div class="two" style="grid-template-columns:1fr 1fr">
    <div class="panel"><div class="panel-h">${svg('disk')} Cartelle piu grandi</div><div class="panel-b">${topRows}</div></div>
    <div class="panel"><div class="panel-h">${svg('fire')} Cache pulibili <span class="cnt num">${cache.length}</span></div><div class="panel-b"><p class="mini" style="margin-top:0;margin-bottom:8px">Sono cartelle: non le rimuovo in automatico. Copia il comando ed eseguilo tu.</p>${cacheRows}</div></div>
   </div>
   <div class="panel" style="margin-top:18px"><div class="panel-h">${svg('fire')} File freddi (non usati da tempo) <span class="cnt num">${freddi.length}</span></div><div class="panel-b"><p class="mini" style="margin-top:0;margin-bottom:8px">"Cestino" li sposta nel Cestino di Windows: reversibile, solo file gia segnalati.</p>${freddiRows}</div></div>
   <div class="panel" style="margin-top:18px"><div class="panel-h">${svg('disk')} Duplicati <span class="cnt num">${dupes.length}</span></div><div class="panel-b"><p class="mini" style="margin-top:0;margin-bottom:8px">Tengo la prima copia, le altre le puoi mandare nel Cestino.</p>${dupRows}</div></div>`;
};

// ================= Dettaglio voce + mappa business =================
const BUSINESS=new Set(['github','blockchain','mercato','idee','prodotti']);
const ONEPAGER=new Set(['idee','prodotti']);
function tagH(t){return t&&t[0]?`<span class="tag ${t[1]||''}">${esc(t[0])}</span>`:'';}
function drow(k,v){return v?`<div class="drow"><div class="dk">${esc(k)}</div><div class="dv">${v}</div></div>`:'';}
function ulH(arr){return arr&&arr.length?`<ul>${arr.map(x=>`<li>${esc(demoji(x))}</li>`).join('')}</ul>`:'';}
function webList(w){if(!w)return '';if(Array.isArray(w))return w.length?`<ul class="mlist" style="margin-top:2px">${w.slice(0,5).map(x=>`<li><a href="${esc(x.url||'#')}" target="_blank" rel="noopener">${esc(demoji(x.title||x.name||x))}</a></li>`).join('')}</ul>`:'';return esc(demoji(w));}
function prodStats(p){
 const ads=/ads|affiliate|pubblic|traffic/i.test(p.modello||'')||((!(p.prezzo_eur>0)||!(p.utenti_mese>0))&&p.visite_mese>0&&p.rpm_eur>0);
 let rev=ads?(p.visite_mese/1000)*(p.rpm_eur||0):(p.prezzo_eur||0)*(p.utenti_mese||0);
 if(!rev&&p.ricavo_mese_eur)rev=p.ricavo_mese_eur;
 const prof=rev-(p.costi_mese_eur||0);return {rev,prof,day:prof/30,ads};}
const DETAIL={
 github:r=>({title:r.full_name,url:r.url,
   tags:[[r.tipo,'acc'],[r.category],[r.language],[r.license||'senza licenza',/mit|apache|bsd|isc|mpl/i.test(r.license||'')?'g':(r.license?'am':'r')]],
   rows:[['Descrizione',esc(demoji(r.description||''))],['Perche rilevante',esc(demoji(r.reason||''))],
     ['Metriche',`&#9733; ${nfmt(r.stars||0)} stelle${r.vel?` &middot; &#9650; ${r.vel}/g`:''}${r.pushed?` &middot; agg. ${esc(r.pushed)}`:''}`],
     ['Punteggio',`${r.score??'-'} / 10`]],
   ctx:`${r.description||''}. ${r.reason||''}`}),
 cyber:r=>({title:r.product||r.name||r.cve,url:r.url,
   tags:[[r.cve],[r.vendor],[r.ransomware?'ransomware':'','r'],[r.relevant?'ti riguarda':'','g']],
   rows:[['Nome',esc(r.name||'')],['Descrizione',esc(demoji(r.desc||''))],['Azione difensiva',esc(demoji(r.action||''))],['Aggiunta',esc(r.date||'')]],
   ctx:r.desc||''}),
 blockchain:r=>({title:r.full_name,url:r.url,
   tags:[[r.language,'acc'],[r.audit?'audit':'no audit',r.audit?'g':'am'],...(r.topics||[]).slice(0,5).map(t=>[t])],
   rows:[['Descrizione',esc(demoji(r.description||''))],['Stelle',nfmt(r.stars||0)]],
   ctx:r.description||''}),
 mercato:r=>{const a=r.analisi||{};return{title:r.topic,
   tags:[[a.direzione],[a.impatto?'impatto '+a.impatto:'']],
   rows:[['Lettura',esc(demoji(a.significa||''))],
     ['Notizie',(r.items||[]).length?`<ul class="mlist" style="margin-top:2px">${(r.items||[]).map(it=>`<li><a href="${esc(it.url)}" target="_blank" rel="noopener">${esc(demoji(it.title))}</a></li>`).join('')}</ul>`:'']],
   ctx:`${r.topic}: ${a.significa||''}`};},
 idee:r=>({title:r.titolo,
   tags:[[r.settore,'acc'],[r.fattibilita?'fattibilita '+r.fattibilita:'',LIV[(r.fattibilita||'').toLowerCase()]||''],[r.novelta?'novita '+r.novelta:''],[r.web_esiste?'gia presidiato':'campo libero',r.web_esiste?'r':'g']],
   rows:[['Descrizione',esc(demoji(r.descrizione||''))],['Problema',esc(demoji(r.problema||''))],['Perche ora',esc(demoji(r.perche_ora||''))],
     ['Mercato',esc(demoji(r.tam||''))],['Primi passi',ulH(r.passi)],['Concorrenti / riferimenti',webList(r.web)],['Verifica',r.verifica?esc(demoji(r.verifica)):'']],
   ctx:`${r.titolo}: ${r.descrizione||''}. Problema: ${r.problema||''}`}),
 pc:r=>({title:r.titolo,
   tags:[[r.area,'acc'],[r.impatto?'impatto '+r.impatto:'',IMP[(r.impatto||'').toLowerCase()]||'']],
   rows:[['Consiglio',esc(demoji(r.consiglio||''))]],ctx:r.consiglio||''}),
 prodotti:p=>{const s=prodStats(p);return{title:p.titolo,
   tags:[[p.settore,'acc'],[p.modello],[p.difficolta?'difficolta '+p.difficolta:'',DIFF[(p.difficolta||'').toLowerCase()]||'']],
   rows:[['Cosa fa',esc(demoji(p.cosa_fa||''))],['Per chi',esc(demoji(p.target||''))],['Problema',esc(demoji(p.problema||''))],
     ['Guadagno stimato',`<div class="prodmath">${s.ads?`<div class="pm"><span>Visite / mese</span><b>${nfmt(p.visite_mese||0)}</b></div><div class="pm"><span>RPM (ricavo per 1000 visite)</span><b>${eur(p.rpm_eur||0)}</b></div>`:`<div class="pm"><span>Prezzo</span><b>${eur(p.prezzo_eur||0)}${p.modello==='una tantum'?'':' /mese'}</b></div><div class="pm"><span>Clienti paganti stimati</span><b>${Math.round(p.utenti_mese||0)}</b></div>`}<div class="pm"><span>Ricavo / mese</span><b>${eur(s.rev)}</b></div><div class="pm"><span>Costi / mese</span><b>-${eur(p.costi_mese_eur||0)}</b></div><div class="pm tot"><span>Guadagno al giorno</span><b>${eur(s.day)}</b></div></div>`],
     ['Stack',(p.stack||[]).join(', ')],['Canali',(p.canali||[]).join(', ')],['Tempo (settimane)',(p.tempo_settimane||0)+' sett.'],['Rischio',esc(demoji(p.rischi||''))],['Primi passi',ulH(p.passi)],['Ispirato da',esc(demoji(p.fonte||''))]],
   ctx:`${p.titolo}: ${p.cosa_fa||''}. Modello ${p.modello||''}, target ${p.target||''}`};}};

function openDetail(sec,i){
 const b=DETAIL[sec];const r=(viewRows||[])[i];if(!b||!r)return;
 const d=b(r);const biz=BUSINESS.has(sec);const onep=ONEPAGER.has(sec);
 detailCtx={title:d.title,ctx:d.ctx};detailObj=r;
 $('#detail').innerHTML=`<div class="dcard">
   <div class="dhead"><div class="dt">${esc(d.title)}</div>
    ${d.url?`<a class="btn" href="${esc(d.url)}" target="_blank" rel="noopener">${svg('ext')} Apri</a>`:''}
    <button class="dx" onclick="closeDetail()" title="chiudi">${svg('x')}</button></div>
   <div class="dbody">
    ${d.tags.some(t=>t&&t[0])?`<div class="tags dtags">${d.tags.map(tagH).join('')}</div>`:''}
    ${d.rows.map(x=>drow(x[0],x[1])).join('')}
    ${biz?`<div class="dsec-t">Mappa concettuale e piano business</div>
      <div id="dmap"><div class="dmap-actions"><button class="btn pri" id="dmap-gen">${svg('bulb')} Genera mappa e report</button></div>
      <p class="mini" style="margin-top:11px">Con Ollama attivo: trasforma questa voce in un piano (problema, a chi vendere, come monetizzare, MVP, vantaggio, rischi).</p></div>`:''}
    ${onep?`<div class="dsec-t">One-pager per investitori</div>
      <div id="onep"><div class="dmap-actions"><button class="btn" id="onep-gen">${svg('spark')} Genera one-pager</button></div>
      <p class="mini" style="margin-top:11px">Un documento sintetico e pronto da presentare (problema, soluzione, mercato, modello, ask). Esportabile in .md.</p></div>`:''}
   </div></div>`;
 $('#detail').classList.add('on');
 if(biz)$('#dmap-gen').onclick=()=>genMap(false);
 if(onep)$('#onep-gen').onclick=()=>genOnepager();
}
async function genOnepager(){const box=$('#onep');if(!box)return;box.innerHTML='<div class="dwait">Scrivo il one-pager con Ollama...</div>';
 try{const d=await (await fetch('/onepager',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({idea:detailObj||{}})})).json();
  if(d.error){box.innerHTML=`<div class="dwait">Ollama non disponibile (${esc(d.error)}).</div><div class="dmap-actions"><button class="btn" onclick="genOnepager()">Riprova</button></div>`;return;}
  window.__onep=d;
  const S=[['Problema',d.problema],['Soluzione',d.soluzione],['Mercato',d.mercato],['Modello',d.modello],['Perche ora',d.perche_ora],['Perche noi',d.perche_noi],['Traction',d.traction],['Richiesta',d.ask]];
  box.innerHTML=`${d.tagline?`<div class="op-tag">${esc(demoji(d.tagline))}</div>`:''}${S.map(x=>x[1]?`<div class="op-sec"><b>${esc(x[0])}</b><span>${esc(demoji(x[1]))}</span></div>`:'').join('')}
    <div class="dmap-actions"><button class="btn" onclick="genOnepager()">Rigenera</button><button class="btn" onclick="dlOnep()">${svg('download')} .md</button></div>`;
 }catch(e){box.innerHTML='<div class="dwait">Errore di rete.</div>';}
}
function dlOnep(){const d=window.__onep;if(!d)return;
 const S=[['Problema',d.problema],['Soluzione',d.soluzione],['Mercato',d.mercato],['Modello di business',d.modello],['Perche ora',d.perche_ora],['Perche noi',d.perche_noi],['Traction',d.traction],['Richiesta',d.ask]];
 let md=`# ${d.titolo||'One-pager'}\n\n${d.tagline?'> '+d.tagline+'\n\n':''}`+S.filter(x=>x[1]).map(x=>`## ${x[0]}\n${x[1]}\n`).join('\n');
 downloadMd((d.titolo||'onepager').replace(/[^\w\-]+/g,'_').slice(0,50)+'.md',md);}
function closeDetail(){$('#detail').classList.remove('on');}
async function genMap(regen){
 const box=$('#dmap');if(!box)return;
 box.innerHTML='<div class="dwait">Genero la mappa con Ollama, un momento...</div>';
 try{
  const r=await (await fetch('/mappa',{method:'POST',headers:{'Content-Type':'application/json'},
    body:JSON.stringify({title:detailCtx.title,ctx:detailCtx.ctx,regen:!!regen})})).json();
  if(r.error){box.innerHTML=`<div class="dwait">Ollama non disponibile (${esc(r.error)}).<br>Accendi Ollama dal pulsante in basso a sinistra e riprova.</div>
    <div class="dmap-actions"><button class="btn" onclick="genMap(true)">Riprova</button></div>`;return;}
  const rami=(r.rami||[]).map(n=>`<div class="dnode"><b>${esc(n.nome||'')}</b>${(n.punti||[]).map(p=>`<span>${esc(demoji(p))}</span>`).join('')}</div>`).join('');
  window.__map={title:detailCtx.title,r};
  box.innerHTML=`<div class="dcenter">${esc(r.centro||detailCtx.title)}</div><div class="drami">${rami}</div>
    <div class="dmap-actions" style="margin-top:15px"><button class="btn" onclick="genMap(true)">Rigenera</button><button class="btn" onclick="dlMap()">${svg('download')} .md</button>${r.cached?'<span class="mini">dalla cache</span>':''}</div>`;
 }catch(e){box.innerHTML='<div class="dwait">Errore di rete. Il server e attivo?</div><div class="dmap-actions"><button class="btn" onclick="genMap(true)">Riprova</button></div>';}
}
$('#detail').addEventListener('click',e=>{if(e.target.id==='detail')closeDetail();});
document.addEventListener('keydown',e=>{if(e.key==='Escape')closeDetail();});

// ================= Nutrizione (dietologo simulato) =================
const FOODS=[
 {n:"Petto di pollo",kcal:165,c:0,p:31,f:3.6},{n:"Fesa di tacchino",kcal:135,c:0,p:29,f:1},
 {n:"Manzo magro",kcal:250,c:0,p:26,f:15},{n:"Uovo",kcal:143,c:1.1,p:13,f:9.5},
 {n:"Salmone",kcal:208,c:0,p:20,f:13},{n:"Tonno al naturale",kcal:116,c:0,p:26,f:1},
 {n:"Merluzzo",kcal:82,c:0,p:18,f:0.7},{n:"Gamberi",kcal:99,c:0.2,p:24,f:0.3},
 {n:"Tonno sott'olio",kcal:190,c:0,p:25,f:10},{n:"Pasta secca",kcal:371,c:75,p:13,f:1.5},
 {n:"Pane",kcal:265,c:49,p:9,f:3.2},{n:"Pane integrale",kcal:247,c:41,p:9,f:4},
 {n:"Riso (cotto)",kcal:130,c:28,p:2.7,f:0.3},{n:"Riso crudo",kcal:358,c:79,p:7,f:0.6},
 {n:"Patate",kcal:77,c:17,p:2,f:0.1},{n:"Patate dolci",kcal:86,c:20,p:1.6,f:0.1},
 {n:"Fiocchi d'avena",kcal:389,c:66,p:17,f:7},{n:"Farina 00",kcal:364,c:76,p:10,f:1},
 {n:"Pizza margherita",kcal:266,c:33,p:11,f:10},{n:"Cornetto",kcal:400,c:45,p:8,f:20},
 {n:"Fette biscottate",kcal:408,c:72,p:11,f:6},{n:"Biscotti",kcal:450,c:68,p:7,f:16},
 {n:"Latte intero",kcal:61,c:4.8,p:3.2,f:3.3},{n:"Latte scremato",kcal:34,c:5,p:3.4,f:0.1},
 {n:"Yogurt greco",kcal:59,c:3.6,p:10,f:0.4},{n:"Yogurt bianco",kcal:61,c:4.7,p:3.5,f:3.3},
 {n:"Mozzarella",kcal:280,c:2.2,p:18,f:22},{n:"Parmigiano",kcal:392,c:0,p:38,f:29},
 {n:"Ricotta",kcal:174,c:3,p:11,f:13},{n:"Feta",kcal:264,c:4,p:14,f:21},
 {n:"Prosciutto crudo",kcal:268,c:0.5,p:26,f:18},{n:"Prosciutto cotto",kcal:215,c:1,p:20,f:15},
 {n:"Bresaola",kcal:151,c:0.4,p:32,f:2},{n:"Salame",kcal:384,c:1,p:23,f:32},
 {n:"Fagioli (cotti)",kcal:91,c:12,p:6,f:0.5},{n:"Ceci (cotti)",kcal:164,c:27,p:9,f:2.6},
 {n:"Lenticchie (cotte)",kcal:116,c:20,p:9,f:0.4},{n:"Piselli",kcal:81,c:14,p:5,f:0.4},
 {n:"Tofu",kcal:76,c:1.9,p:8,f:4.8},{n:"Mandorle",kcal:579,c:22,p:21,f:49},
 {n:"Noci",kcal:654,c:14,p:15,f:65},{n:"Burro d'arachidi",kcal:588,c:20,p:25,f:50},
 {n:"Olio d'oliva",kcal:884,c:0,p:0,f:100},{n:"Burro",kcal:717,c:0.1,p:0.9,f:81},
 {n:"Avocado",kcal:160,c:9,p:2,f:15},{n:"Banana",kcal:89,c:23,p:1.1,f:0.3},
 {n:"Mela",kcal:52,c:14,p:0.3,f:0.2},{n:"Arancia",kcal:47,c:12,p:0.9,f:0.1},
 {n:"Fragole",kcal:32,c:7.7,p:0.7,f:0.3},{n:"Uva",kcal:69,c:18,p:0.7,f:0.2},
 {n:"Kiwi",kcal:61,c:15,p:1.1,f:0.5},{n:"Pomodoro",kcal:18,c:3.9,p:0.9,f:0.2},
 {n:"Insalata",kcal:15,c:2.9,p:1.4,f:0.2},{n:"Zucchine",kcal:17,c:3.1,p:1.2,f:0.3},
 {n:"Broccoli",kcal:34,c:7,p:2.8,f:0.4},{n:"Spinaci",kcal:23,c:3.6,p:2.9,f:0.4},
 {n:"Carote",kcal:41,c:10,p:0.9,f:0.2},{n:"Cioccolato fondente",kcal:546,c:61,p:7.8,f:31},
 {n:"Nutella",kcal:539,c:57,p:6.3,f:31},{n:"Zucchero",kcal:387,c:100,p:0,f:0},
 {n:"Miele",kcal:304,c:82,p:0.3,f:0},{n:"Birra",kcal:43,c:3.6,p:0.5,f:0},
 {n:"Vino rosso",kcal:85,c:2.6,p:0.1,f:0},{n:"Coca cola",kcal:42,c:10.6,p:0,f:0}];
const foodBy=n=>{n=(n||'').trim().toLowerCase();return FOODS.find(f=>f.n.toLowerCase()===n);};
function tdee(p){
 if(!p.weight||!p.height||!p.age)return null;
 const bmr=10*p.weight+6.25*p.height-5*p.age+(p.sex==='f'?-161:5);
 const AF={sed:1.2,leg:1.375,mod:1.55,int:1.725,extra:1.9};
 const t=bmr*(AF[p.act]||1.2);
 const adj={perdi:-450,mant:0,aumenta:350}[p.goal]||0;
 const target=t+adj;
 const prot=Math.round(1.8*p.weight),fat=Math.round(0.9*p.weight);
 const carb=Math.max(0,Math.round((target-prot*4-fat*9)/4));
 return {bmr:Math.round(bmr),tdee:Math.round(t),target:Math.round(target),prot,fat,carb};
}
function macroBar(label,val,target,cls){
 const pct=target?Math.min(100,Math.round(val/target*100)):0;const over=target&&val>target;
 const unit=cls==='kcal'?'kcal':'g';
 return `<div class="mrow"><div class="mhead"><span>${label}</span><span class="num">${Math.round(val)}${target?' / '+target:''} ${unit}</span></div>
   <div class="mbar ${cls} ${over?'over':''}"><i style="width:${pct}%"></i></div></div>`;
}
RENDER.nutrizione=function(){
 const prof=LS.get('nutri_profile',{sex:'m',age:30,weight:75,height:178,act:'mod',goal:'mant'});
 const today=new Date().toISOString().slice(0,10);
 const meals=LS.get('nutri_'+today,[]);
 const tot=meals.reduce((s,m)=>({kcal:s.kcal+m.kcal,c:s.c+m.c,p:s.p+m.p,f:s.f+m.f}),{kcal:0,c:0,p:0,f:0});
 const nd=tdee(prof);
 const K=[{k:'Calorie oggi',v:Math.round(tot.kcal),sub:nd?'/ '+nd.target+' kcal':'',cls:'a'},
   {k:'Proteine',v:Math.round(tot.p)+'g',cls:'g'},{k:'Carboidrati',v:Math.round(tot.c)+'g',cls:'am'},{k:'Grassi',v:Math.round(tot.f)+'g'}];
 $('#view').innerHTML=kpis(K)+`<div class="two">
   <div class="panel"><div class="panel-h">${svg('food')} Oggi <span class="cnt num">${today}</span></div><div class="panel-b">
     <div class="addrow"><input class="inp" id="nf-nm" list="foods" placeholder="Alimento, es. Petto di pollo" style="flex:1;min-width:0">
       <input class="inp" id="nf-g" type="number" placeholder="grammi" style="max-width:96px;min-width:0">
       <button class="btn pri" id="nf-add">${svg('plus')} Aggiungi</button></div>
     <datalist id="foods">${FOODS.map(f=>`<option value="${esc(f.n)}"></option>`).join('')}</datalist>
     <ul class="slist" id="nf-list"></ul>
     ${nd?`<div style="margin-top:18px">${macroBar('Calorie',tot.kcal,nd.target,'kcal')}${macroBar('Proteine',tot.p,nd.prot,'p')}${macroBar('Carboidrati',tot.c,nd.carb,'c')}${macroBar('Grassi',tot.f,nd.fat,'f')}</div>`
       :'<p class="mini" style="margin-top:14px">Compila il profilo a destra per vedere gli obiettivi.</p>'}
   </div></div>
   <div class="panel"><div class="panel-h">Profilo e fabbisogno</div><div class="panel-b">
     <div class="nprofile">
      <div class="fld"><label>sesso</label><select class="inp np" id="np-sex"><option value="m">Uomo</option><option value="f">Donna</option></select></div>
      <div class="fld"><label>eta</label><input class="inp np" id="np-age" type="number"></div>
      <div class="fld"><label>peso (kg)</label><input class="inp np" id="np-weight" type="number"></div>
      <div class="fld"><label>altezza (cm)</label><input class="inp np" id="np-height" type="number"></div>
      <div class="fld"><label>attivita</label><select class="inp np" id="np-act"><option value="sed">Sedentario</option><option value="leg">Leggera</option><option value="mod">Moderata</option><option value="int">Intensa</option><option value="extra">Molto intensa</option></select></div>
      <div class="fld"><label>obiettivo</label><select class="inp np" id="np-goal"><option value="perdi">Dimagrire</option><option value="mant">Mantenere</option><option value="aumenta">Aumentare</option></select></div>
     </div>
     ${nd?`<div class="needbox">
       <div class="nn"><span>Metabolismo basale</span><b class="num">${nd.bmr} kcal</b></div>
       <div class="nn"><span>Fabbisogno (TDEE)</span><b class="num">${nd.tdee} kcal</b></div>
       <div class="nn"><span>Obiettivo giornaliero</span><b class="num" style="color:var(--acc)">${nd.target} kcal</b></div>
       <div class="nn"><span>Proteine / Carbo / Grassi</span><b class="num">${nd.prot} / ${nd.carb} / ${nd.fat} g</b></div>
     </div><p class="mini" style="margin-top:11px">Stima con formula Mifflin-St Jeor. Indicativa, non sostituisce un dietologo.</p>`:''}
   </div></div></div>`;
 ['sex','age','weight','height','act','goal'].forEach(k=>{const e=$('#np-'+k);if(e)e.value=prof[k];});
 document.querySelectorAll('.np').forEach(e=>e.onchange=()=>{
   LS.set('nutri_profile',{sex:$('#np-sex').value,age:+$('#np-age').value,weight:+$('#np-weight').value,height:+$('#np-height').value,act:$('#np-act').value,goal:$('#np-goal').value});
   RENDER.nutrizione();});
 const listEl=$('#nf-list');
 listEl.innerHTML=meals.map((m,i)=>`<li class="sitem"><span class="nm">${esc(m.n)} <span class="qty num">${m.g}g</span></span><span class="qty num">${Math.round(m.kcal)} kcal</span><button class="del" data-i="${i}">${svg('x')}</button></li>`).join('')||'<div class="mini" style="padding:12px 0">Niente ancora. Aggiungi cosa hai mangiato oggi.</div>';
 const addF=()=>{const f=foodBy($('#nf-nm').value);const g=+$('#nf-g').value;if(!f||!g)return;
   const l=LS.get('nutri_'+today,[]);l.push({n:f.n,g,kcal:f.kcal*g/100,c:f.c*g/100,p:f.p*g/100,f:f.f*g/100});
   LS.set('nutri_'+today,l);RENDER.nutrizione();};
 $('#nf-add').onclick=addF;$('#nf-g').onkeydown=e=>{if(e.key==='Enter')addF();};$('#nf-nm').onkeydown=e=>{if(e.key==='Enter')$('#nf-g').focus();};
 listEl.querySelectorAll('.del').forEach(d=>d.onclick=()=>{const l=LS.get('nutri_'+today,[]);l.splice(d.dataset.i,1);LS.set('nutri_'+today,l);RENDER.nutrizione();});
};

// ================= Investimenti (simulatore) =================
const eur=n=>Math.round(n).toLocaleString('it-IT')+' €';
function calcPAC(P0,PM,years,annual){
 const months=Math.max(1,Math.round(years*12));const rm=Math.pow(1+annual,1/12)-1;
 const val=[P0],con=[P0];let v=P0,c=P0;
 for(let m=1;m<=months;m++){v=v*(1+rm)+PM;c+=PM;val.push(v);con.push(c);}
 return {val,con,fv:v,contrib:c};
}
function calcPIC(P0,years,annual){
 const steps=Math.max(1,Math.round(years));const val=[],con=[];
 for(let y=0;y<=steps;y++){val.push(P0*Math.pow(1+annual,y));con.push(P0);}
 return {val,con,fv:P0*Math.pow(1+annual,steps),contrib:P0};
}
function gauss(){let u=0,v=0;while(!u)u=Math.random();while(!v)v=Math.random();return Math.sqrt(-2*Math.log(u))*Math.cos(2*Math.PI*v);}
function monteCarlo(mode,P0,PM,years,annual,vol,paths){
 paths=paths||400;const yrs=Math.max(1,Math.round(years));const finals=[];
 for(let i=0;i<paths;i++){let v=P0;
   for(let y=0;y<yrs;y++){const yr=Math.max(-0.95,annual+vol*gauss());const rm=Math.pow(1+yr,1/12)-1;
     for(let m=0;m<12;m++)v=v*(1+rm)+(mode==='pac'?PM:0);}
   finals.push(v);}
 finals.sort((a,b)=>a-b);const q=p=>finals[Math.floor(p*(finals.length-1))];
 return {p10:q(0.1),p50:q(0.5),p90:q(0.9)};
}
function chartSVG(val,con){
 const W=600,H=230,pad=8;const max=Math.max(...val,1);const n=val.length-1;
 const x=i=>pad+(i/n)*(W-2*pad);const y=v=>H-pad-(v/max)*(H-2*pad);
 const pts=arr=>arr.map((v,i)=>x(i).toFixed(1)+','+y(v).toFixed(1)).join(' ');
 return `<svg class="chart" viewBox="0 0 ${W} ${H}" preserveAspectRatio="none">
   <polygon class="varea" points="${x(0).toFixed(1)},${H-pad} ${pts(val)} ${x(n).toFixed(1)},${H-pad}"/>
   <polyline class="cline" points="${pts(con)}"/><polyline class="vline" points="${pts(val)}"/></svg>`;
}
function chartMulti(series){
 const W=600,H=230,pad=8;const maxV=Math.max(1,...series.flatMap(s=>s.val));
 const allY=series.flatMap(s=>s.labels);const minY=Math.min(...allY),maxY=Math.max(...allY);const span=Math.max(1,maxY-minY);
 const x=y=>pad+((y-minY)/span)*(W-2*pad);const yv=v=>H-pad-(v/maxV)*(H-2*pad);
 const lines=series.map(s=>`<polyline class="cmpline ${s.cls}" points="${s.labels.map((yy,i)=>x(yy).toFixed(1)+','+yv(s.val[i]).toFixed(1)).join(' ')}"/>`).join('');
 return `<svg class="chart" viewBox="0 0 ${W} ${H}" preserveAspectRatio="none">${lines}</svg>`;
}
function chartLine(vals){
 const W=600,H=200,pad=8;const max=Math.max(1,...vals);const n=Math.max(1,vals.length-1);
 const x=i=>pad+(i/n)*(W-2*pad);const y=v=>H-pad-(v/max)*(H-2*pad);
 const pts=vals.map((v,i)=>x(i).toFixed(1)+','+y(v).toFixed(1)).join(' ');
 return `<svg class="chart" style="height:200px" viewBox="0 0 ${W} ${H}" preserveAspectRatio="none"><polygon class="varea" points="${x(0).toFixed(1)},${H-pad} ${pts} ${x(n).toFixed(1)},${H-pad}"/><polyline class="vline" points="${pts}"/></svg>`;
}
function downloadMd(name,text){const b=new Blob([text],{type:'text/markdown;charset=utf-8'});const a=document.createElement('a');a.href=URL.createObjectURL(b);a.download=name;document.body.appendChild(a);a.click();a.remove();setTimeout(()=>URL.revokeObjectURL(a.href),1500);}
function fmtTok(n){return n>=1e9?(n/1e9).toFixed(2)+'B':n>=1e6?(n/1e6).toFixed(1)+'M':n>=1e3?(n/1e3).toFixed(0)+'k':String(n);}
// prezzi storici indicativi di fine anno (fonte pubblica, arrotondati; azioni split-adjusted; USD ~ EUR)
const HIST={
 BTC:{2015:430,2016:960,2017:14000,2018:3700,2019:7200,2020:29000,2021:47000,2022:16500,2023:42000,2024:94000,2025:88000},
 ETH:{2015:1,2016:8,2017:750,2018:130,2019:130,2020:730,2021:3700,2022:1200,2023:2300,2024:3300,2025:2900},
 SOL:{2020:1.5,2021:170,2022:10,2023:100,2024:190,2025:150},
 BNB:{2017:8,2018:6,2019:14,2020:37,2021:530,2022:245,2023:310,2024:700,2025:600},
 XRP:{2017:2.3,2018:0.36,2019:0.19,2020:0.22,2021:0.83,2022:0.34,2023:0.62,2024:2.1,2025:2.4},
 ADA:{2017:0.72,2018:0.04,2019:0.033,2020:0.18,2021:1.31,2022:0.25,2023:0.59,2024:0.85,2025:0.6},
 DOGE:{2017:0.009,2018:0.002,2019:0.002,2020:0.0047,2021:0.17,2022:0.07,2023:0.09,2024:0.32,2025:0.2},
 AVAX:{2020:3.6,2021:110,2022:11,2023:38,2024:38,2025:20},
 LINK:{2017:0.5,2018:0.3,2019:1.8,2020:11,2021:20,2022:5.7,2023:15,2024:20,2025:15},
 LTC:{2015:3.5,2016:4.4,2017:225,2018:31,2019:41,2020:125,2021:146,2022:70,2023:73,2024:100,2025:85},
 NVDA:{2015:0.83,2016:2.66,2017:4.83,2018:3.34,2019:5.88,2020:13.05,2021:29.4,2022:14.6,2023:49.5,2024:134,2025:140},
 AAPL:{2015:26,2016:29,2017:42,2018:39,2019:73,2020:132,2021:177,2022:130,2023:192,2024:250,2025:230},
 TSLA:{2015:16,2016:14,2017:21,2018:22,2019:28,2020:235,2021:352,2022:123,2023:248,2024:405,2025:350},
 AMZN:{2015:34,2016:38,2017:59,2018:75,2019:92,2020:163,2021:167,2022:84,2023:152,2024:220,2025:210},
 MSFT:{2015:55,2016:62,2017:85,2018:100,2019:157,2020:222,2021:336,2022:239,2023:376,2024:421,2025:430},
 SP500:{2015:2044,2016:2239,2017:2674,2018:2507,2019:3231,2020:3756,2021:4766,2022:3840,2023:4770,2024:5880,2025:6100},
 NASDAQ:{2015:5007,2016:5383,2017:6903,2018:6635,2019:8973,2020:12888,2021:15645,2022:10466,2023:15011,2024:19311,2025:20200},
 MSCIW:{2015:1663,2016:1751,2017:2103,2018:1884,2019:2358,2020:2690,2021:3232,2022:2603,2023:3169,2024:3700,2025:3850},
 ORO:{2015:1060,2016:1150,2017:1300,2018:1280,2019:1520,2020:1900,2021:1830,2022:1825,2023:2065,2024:2620,2025:2700},
 ARGENTO:{2015:13.8,2016:16,2017:17,2018:15.5,2019:18,2020:26.4,2021:23.3,2022:24,2023:24,2024:29,2025:31},
 PETROLIO:{2015:37,2016:54,2017:60,2018:45,2019:61,2020:48,2021:75,2022:80,2023:72,2024:72,2025:68}};
const ASSETS=[
 ['BTC','Bitcoin','Crypto'],['ETH','Ethereum','Crypto'],['SOL','Solana','Crypto'],['BNB','BNB','Crypto'],
 ['XRP','XRP','Crypto'],['ADA','Cardano','Crypto'],['DOGE','Dogecoin','Crypto'],['AVAX','Avalanche','Crypto'],
 ['LINK','Chainlink','Crypto'],['LTC','Litecoin','Crypto'],
 ['NVDA','Nvidia','Azioni'],['AAPL','Apple','Azioni'],['TSLA','Tesla','Azioni'],['AMZN','Amazon','Azioni'],['MSFT','Microsoft','Azioni'],
 ['SP500','S&P 500','Indici'],['NASDAQ','Nasdaq 100','Indici'],['MSCIW','MSCI World','Indici'],
 ['ORO','Oro','Materie prime'],['ARGENTO','Argento','Materie prime'],['PETROLIO','Petrolio (WTI)','Materie prime']];
function calcBacktest(asset,annual,startYear){
 const px=HIST[asset]||HIST.BTC;
 const years=Object.keys(px).map(Number).sort((a,b)=>a-b).filter(y=>y>=startYear);
 let units=0,invested=0;const val=[],con=[],labels=[];
 years.forEach(y=>{const p=px[y];units+=annual/p;invested+=annual;val.push(units*p);con.push(invested);labels.push(y);});
 const last=years[years.length-1]||startYear;const now=units*(px[last]||1);
 return {val,con,labels,fv:now,contrib:invested,mult:invested?now/invested:0,endYear:last};
}
RENDER.investimenti=function(){
 const c=LS.get('inv_cfg',{mode:'pac',p0:1000,pm:200,years:15,ret:6,vol:12,asset:'BTC',bta:1200,bts:2018});
 const seg3=`<div class="seg seg2"><button class="segb ${c.mode==='pac'?'on':''}" data-im="pac">PAC</button><button class="segb ${c.mode==='pic'?'on':''}" data-im="pic">PIC</button><button class="segb ${c.mode==='back'?'on':''}" data-im="back">Backtest</button><button class="segb ${c.mode==='cmp'?'on':''}" data-im="cmp">Confronto</button><button class="segb ${c.mode==='rank'?'on':''}" data-im="rank">Classifica</button></div>`;
 const wireSeg=()=>{document.querySelectorAll('.segb[data-im]').forEach(b=>b.onclick=()=>{c.mode=b.dataset.im;LS.set('inv_cfg',c);RENDER.investimenti();});};
 const yrsOpt=[2015,2016,2017,2018,2019,2020,2021,2022];
 if(c.mode==='back'){
  const bt=calcBacktest(c.asset||'BTC',c.bta||1200,c.bts||2018);
  const gain=bt.fv-bt.contrib,roi=bt.contrib?gain/bt.contrib*100:0;
  const nm=(ASSETS.find(a=>a[0]===(c.asset||'BTC'))||['BTC','Bitcoin'])[1];
  const K=[{k:'Valore oggi',v:eur(bt.fv),cls:'a'},{k:'Totale versato',v:eur(bt.contrib)},
    {k:'Moltiplicatore',v:bt.mult.toFixed(1)+'x',cls:'g'},{k:'Rendimento',v:(roi>=0?'+':'')+Math.round(roi)+'%',cls:roi>=0?'g':'r'}];
  $('#view').innerHTML=kpis(K)+seg3+`<div class="two" style="grid-template-columns:320px minmax(0,1fr)">
    <div class="panel"><div class="panel-h">Parametri</div><div class="panel-b">
      <div class="fld" style="margin-bottom:13px"><label>asset</label><select class="inp bv" id="bv-asset" style="width:100%">${['Crypto','Azioni','Indici','Materie prime'].map(cat=>`<optgroup label="${cat}">${ASSETS.filter(a=>a[2]===cat).map(a=>`<option value="${a[0]}" ${c.asset===a[0]?'selected':''}>${a[1]}</option>`).join('')}</optgroup>`).join('')}</select></div>
      <div class="fld" style="margin-bottom:13px"><label>versamento annuo (EUR)</label><input class="inp bv" id="bv-a" type="number" style="width:100%" value="${c.bta||1200}"></div>
      <div class="fld"><label>dall'anno</label><select class="inp bv" id="bv-s" style="width:100%">${yrsOpt.map(y=>`<option ${(c.bts||2018)===y?'selected':''}>${y}</option>`).join('')}</select></div>
      <p class="mini" style="margin-top:13px">"Se avessi versato ${eur(c.bta||1200)} l'anno in ${esc(nm)} dal ${bt.labels[0]||c.bts}". Prezzi storici indicativi (fine anno); azioni rettificate per gli split. Il passato non predice il futuro.</p>
    </div></div>
    <div class="panel"><div class="panel-h">${esc(nm)}: ${bt.labels[0]||c.bts} - ${bt.endYear}</div><div class="panel-b">
      ${chartSVG(bt.val,bt.con)}
      <div class="leg"><span><i style="background:var(--acc)"></i>Valore</span><span><i style="background:var(--faint)"></i>Versato</span></div>
    </div></div></div>`;
  wireSeg();
  document.querySelectorAll('.bv').forEach(e=>e.onchange=()=>{c.asset=$('#bv-asset').value;c.bta=+$('#bv-a').value||0;c.bts=+$('#bv-s').value||2018;LS.set('inv_cfg',c);RENDER.investimenti();});
  return;
 }
 if(c.mode==='cmp'){
  const sel=c.cmp||['BTC','NVDA','SP500'];const ann=c.bta||1200,st=c.bts||2018;const cc=['var(--acc)','#f0883e','#3fb96b'];
  const series=sel.map((k,i)=>{const bt=calcBacktest(k,ann,st);return {k,name:(ASSETS.find(a=>a[0]===k)||[k,k])[1],bt,cls:'cmp'+i};});
  const K=series.map((s,i)=>({k:s.name,v:eur(s.bt.fv),cls:i===0?'a':(i===1?'am':'g')}));
  $('#view').innerHTML=kpis(K)+seg3+`<div class="two" style="grid-template-columns:320px minmax(0,1fr)">
    <div class="panel"><div class="panel-h">Parametri</div><div class="panel-b">
      ${[0,1,2].map(i=>`<div class="fld" style="margin-bottom:13px"><label>asset ${i+1}</label><select class="inp cv" data-i="${i}" style="width:100%">${['Crypto','Azioni','Indici','Materie prime'].map(cat=>`<optgroup label="${cat}">${ASSETS.filter(a=>a[2]===cat).map(a=>`<option value="${a[0]}" ${sel[i]===a[0]?'selected':''}>${a[1]}</option>`).join('')}</optgroup>`).join('')}</select></div>`).join('')}
      <div class="fld" style="margin-bottom:13px"><label>versamento annuo (EUR)</label><input class="inp cv2" id="cv-a" type="number" style="width:100%" value="${ann}"></div>
      <div class="fld"><label>dall'anno</label><select class="inp cv2" id="cv-s" style="width:100%">${yrsOpt.map(y=>`<option ${st===y?'selected':''}>${y}</option>`).join('')}</select></div>
    </div></div>
    <div class="panel"><div class="panel-h">Confronto a parita di versamento</div><div class="panel-b">
      ${chartMulti(series.map(s=>({labels:s.bt.labels,val:s.bt.val,cls:s.cls})))}
      <div class="cmpleg">${series.map((s,i)=>`<span><i style="background:${cc[i]}"></i><b>${esc(s.name)}</b> ${eur(s.bt.fv)} (${s.bt.mult.toFixed(1)}x)</span>`).join('')}</div>
    </div></div></div>`;
  wireSeg();
  document.querySelectorAll('.cv').forEach(e=>e.onchange=()=>{c.cmp=[...document.querySelectorAll('.cv')].map(x=>x.value);LS.set('inv_cfg',c);RENDER.investimenti();});
  document.querySelectorAll('.cv2').forEach(e=>e.onchange=()=>{c.bta=+$('#cv-a').value||0;c.bts=+$('#cv-s').value||2018;LS.set('inv_cfg',c);RENDER.investimenti();});
  return;
 }
 if(c.mode==='rank'){
  const ann=c.bta||1200,st=c.bts||2018;
  const rows=ASSETS.map(a=>{const bt=calcBacktest(a[0],ann,st);const roi=bt.contrib?(bt.fv-bt.contrib)/bt.contrib*100:0;return {name:a[1],cat:a[2],fv:bt.fv,mult:bt.mult,roi,start:bt.labels[0],contrib:bt.contrib};}).sort((x,y)=>y.mult-x.mult);
  const best=rows[0],worst=rows[rows.length-1];
  const K=[{k:'Versato',v:eur(best.contrib)},{k:'Vincitore',v:best.name,cls:'g'},{k:'Miglior valore',v:eur(best.fv),cls:'a'},{k:'Peggiore',v:worst.name,cls:'r'}];
  $('#view').innerHTML=kpis(K)+seg3+`<div class="toolbar" style="margin-bottom:16px">
    <div class="fld"><label>versamento annuo (EUR)</label><input class="inp rv" id="rv-a" type="number" value="${ann}"></div>
    <div class="fld"><label>dall'anno</label><select class="inp rv" id="rv-s">${yrsOpt.map(y=>`<option ${st===y?'selected':''}>${y}</option>`).join('')}</select></div></div>
   <div class="panel"><div class="panel-b" style="padding:4px 10px"><table class="rank"><thead><tr><th class="r-n">#</th><th>Asset</th><th>Categoria</th><th>Dal</th><th>Valore oggi</th><th>Rendimento</th><th>Moltiplic.</th></tr></thead><tbody>
    ${rows.map((r,i)=>`<tr><td class="r-n">${i+1}</td><td class="r-a">${esc(r.name)}</td><td class="r-cat">${esc(r.cat)}</td><td>${r.start}</td><td>${eur(r.fv)}</td><td class="${r.roi<0?'r-neg':''}">${(r.roi>=0?'+':'')}${Math.round(r.roi)}%</td><td class="r-m">${r.mult.toFixed(1)}x</td></tr>`).join('')}
   </tbody></table></div></div>
   <p class="mini" style="margin-top:12px">Stesso versamento annuo su ogni asset dallo stesso anno. Prezzi storici indicativi; il passato non predice il futuro.</p>`;
  wireSeg();
  document.querySelectorAll('.rv').forEach(e=>e.onchange=()=>{c.bta=+$('#rv-a').value||0;c.bts=+$('#rv-s').value||2018;LS.set('inv_cfg',c);RENDER.investimenti();});
  return;
 }
 const annual=(c.ret||0)/100,vol=(c.vol||0)/100;
 const res=c.mode==='pac'?calcPAC(c.p0||0,c.pm||0,c.years||1,annual):calcPIC(c.p0||0,c.years||1,annual);
 const gain=res.fv-res.contrib,roi=res.contrib?gain/res.contrib*100:0;
 const mc=monteCarlo(c.mode,c.p0||0,c.pm||0,c.years||1,annual,vol);
 const K=[{k:'Valore finale stimato',v:eur(res.fv),cls:'a'},{k:'Totale versato',v:eur(res.contrib)},
   {k:'Guadagno',v:eur(gain),cls:'g'},{k:'Rendimento totale',v:(roi>=0?'+':'')+Math.round(roi)+'%',cls:roi>=0?'g':'r'}];
 $('#view').innerHTML=kpis(K)+seg3+`
   <div class="two" style="grid-template-columns:320px minmax(0,1fr)">
    <div class="panel"><div class="panel-h">Parametri</div><div class="panel-b">
      <div class="fld" style="margin-bottom:13px"><label>versamento iniziale (EUR)</label><input class="inp iv" id="iv-p0" type="number" style="width:100%"></div>
      ${c.mode==='pac'?`<div class="fld" style="margin-bottom:13px"><label>versamento mensile (EUR)</label><input class="inp iv" id="iv-pm" type="number" style="width:100%"></div>`:''}
      <div class="fld" style="margin-bottom:13px"><label>durata (anni)</label><input class="inp iv" id="iv-years" type="number" style="width:100%"></div>
      <div class="fld" style="margin-bottom:13px"><label>rendimento annuo atteso (%)</label><input class="inp iv" id="iv-ret" type="number" style="width:100%"></div>
      <div class="fld"><label>volatilita annua (%)</label><input class="inp iv" id="iv-vol" type="number" style="width:100%"></div>
      <p class="mini" style="margin-top:13px">Simulazione what-if, non un consiglio d'investimento. I rendimenti passati non garantiscono quelli futuri.</p>
    </div></div>
    <div class="panel"><div class="panel-h">Proiezione a ${c.years} anni</div><div class="panel-b">
      ${chartSVG(res.val,res.con)}
      <div class="leg"><span><i style="background:var(--acc)"></i>Valore</span><span><i style="background:var(--faint)"></i>Versato</span></div>
      <div class="dsec-t" style="margin:22px 0 0">Scenari possibili (Monte Carlo, volatilita ${c.vol}%)</div>
      <div class="mcband">
        <div class="mccell"><div class="l">Pessimistico p10</div><div class="v" style="color:var(--red)">${eur(mc.p10)}</div></div>
        <div class="mccell"><div class="l">Mediano p50</div><div class="v">${eur(mc.p50)}</div></div>
        <div class="mccell"><div class="l">Ottimistico p90</div><div class="v" style="color:var(--green)">${eur(mc.p90)}</div></div>
      </div>
    </div></div>
   </div>`;
 ['p0','pm','years','ret','vol'].forEach(k=>{const e=$('#iv-'+k);if(e)e.value=c[k];});
 document.querySelectorAll('.segb[data-im]').forEach(b=>b.onclick=()=>{c.mode=b.dataset.im;LS.set('inv_cfg',c);RENDER.investimenti();});
 document.querySelectorAll('.iv').forEach(e=>e.onchange=()=>{
   const n={...c,p0:+$('#iv-p0').value||0,years:Math.max(1,+$('#iv-years').value||1),ret:+$('#iv-ret').value||0,vol:Math.max(0,+$('#iv-vol').value||0)};
   const pm=$('#iv-pm');if(pm)n.pm=+pm.value||0;LS.set('inv_cfg',n);RENDER.investimenti();});
};

// ================= Home "Oggi" =================
const OGGI_TILES=[['notizie','Notizie di oggi'],['repo','Repo nuove di oggi'],['cyber','Minacce di oggi'],['agenda','Agenda di oggi'],['crypto','Mercato crypto'],['nutrizione','Nutrizione oggi'],['idea','Idea migliore'],['disco','Disco'],['investimenti','Investimenti'],['investitori','Startup & capitali'],['briefing','Briefing del giorno']];
function oggiOn(id){const m=LS.get('oggi_tiles',null);return !m||m[id]!==false;}
function _isToday(dstr){if(!dstr)return false;const t=Date.parse(dstr);if(isNaN(t))return false;return _ymd(new Date(t))===_agToday();}
RENDER.oggi=async function(){
 const today=_agToday();
 // notizie di oggi: carico il feed se serve
 if(oggiOn('notizie')&&__newsData===null){await loadNews();}
 const newsToday=[];(__newsData||[]).forEach(r=>(r.items||[]).forEach(it=>{if(_isToday(it.date))newsToday.push(Object.assign({topic:r.topic},it));}));
 const repoToday=P.github.filter(r=>r.new_today).sort((a,b)=>(b.score||0)-(a.score||0));
 const cyToday=P.cyber.filter(r=>_isToday(r.date));
 const agToday=(LS.get('agenda',[])||[]).filter(x=>x.date===today).sort((a,b)=>(a.time||'').localeCompare(b.time||''));
 const idea=P.idee[0];
 const d=P.disco||{},info=d.disco||{};
 const cr=(P.crypto||[]).slice().sort((a,b)=>Math.abs(b.chg||0)-Math.abs(a.chg||0)).slice(0,3);
 const meals=LS.get('nutri_'+today,[]);const kcal=Math.round(meals.reduce((s,m)=>s+m.kcal,0));
 const prof=LS.get('nutri_profile',{});const nd=tdee(prof);
 const ic=LS.get('inv_cfg',{mode:'pac',p0:1000,pm:200,years:15,ret:6});
 const invRes=ic.mode==='pic'?calcPIC(ic.p0||0,ic.years||1,(ic.ret||0)/100):calcPAC(ic.p0||0,ic.pm||0,ic.years||1,(ic.ret||0)/100);
 const cell=(go_,cls,icon,head,body)=>`<div class="bcell ${cls||''}" onclick="${go_}"><div class="bh">${svg(icon)} ${esc(head)}</div>${body}</div>`;
 const dt=new Date().toLocaleDateString('it-IT',{weekday:'long',day:'numeric',month:'long'});
 const statebar=`<div class="statebar"><div class="sb-l">${svg('activity')} ${esc(dt.charAt(0).toUpperCase()+dt.slice(1))} &middot; solo cose di oggi</div><button class="btn" onclick="oggiPicker()">${svg('settings')} Scegli tessere</button><button class="btn" onclick="$('#refresh').click()">${svg('chart')} Aggiorna</button></div>`;
 const T={};
 T.notizie=cell("go('notizie')",'wide','news','Notizie di oggi',newsToday.length?`<ul class="mlist" style="margin-top:4px">${newsToday.slice(0,6).map(it=>`<li><a href="${esc(it.url)}" target="_blank" rel="noopener" onclick="event.stopPropagation()">${esc(demoji(it.title))}</a> <span class="bm" style="opacity:.7">${esc(it.topic)}</span></li>`).join('')}</ul>`:'<div class="bm">Nessuna notizia di oggi tra i tuoi argomenti. Aggiorna o aggiungine.</div>');
 T.repo=cell("go('github')",'','github','Repo nuove di oggi',repoToday.length?`<div class="bt">${esc(repoToday[0].full_name)}</div><div class="bm">${repoToday.length} nuove oggi &middot; &#9733; ${nfmt(repoToday[0].stars||0)}</div>`:'<div class="bm">Nessuna repo nuova oggi.</div>');
 T.cyber=cell("go('cyber')",'','shield','Minacce di oggi',cyToday.length?`<div class="bt">${esc(cyToday[0].product||cyToday[0].name||cyToday[0].cve)}</div><div class="bm">${cyToday.length} aggiunte oggi${cyToday.some(r=>r.relevant)?' &middot; una ti riguarda':''}</div>`:'<div class="bm">Nessuna nuova minaccia oggi.</div>');
 T.agenda=cell("go('agenda')",'','calendar','Agenda di oggi',agToday.length?`<ul class="mlist" style="margin-top:4px">${agToday.slice(0,5).map(x=>`<li>${x.time?`<b>${esc(x.time)}</b> `:''}${esc(demoji(x.title))}</li>`).join('')}</ul>`:'<div class="bm">Nessun impegno per oggi.</div>');
 T.crypto=cr.length?cell("go('notizie')",'','trend','Mercato crypto',`<div class="bm" style="display:flex;gap:20px;flex-wrap:wrap;margin-top:2px">${cr.map(c=>`<span><b style="color:var(--txt)">${esc(c.sym)}</b> ${(c.chg>=0?'+':'')}${(c.chg||0).toFixed(1)}%</span>`).join('')}</div>`):'';
 T.nutrizione=cell("go('nutrizione')",'','food','Nutrizione oggi',`<div class="bbig num">${kcal} <small>/ ${nd?nd.target:'?'} kcal</small></div><div class="bm">${nd?(kcal<=nd.target?'Sei in linea':'Sopra obiettivo'):'Imposta il profilo'}</div>`);
 T.idea=cell("go('idee')",'','bulb','Idea migliore',idea?`<div class="bt">${esc(idea.titolo)}</div><div class="bm">${esc(idea.settore||'')} &middot; fattibilita ${esc(idea.fattibilita||'-')}</div>`:'<div class="bm">Nessuna.</div>');
 T.disco=cell("go('disco')",'','disk','Disco',`<div class="bbig num">${info.free_gb??'-'} <small>GB liberi</small></div><div class="bm">Liberabili ${d.liberabile_gb??0} GB</div>`);
 T.investimenti=cell("go('investimenti')",'','chart','Investimenti',`<div class="bbig num">${eur(invRes.fv)}</div><div class="bm">Proiezione a ${ic.years} anni (${ic.mode.toUpperCase()})</div>`);
 T.investitori=cell("go('investitori')",'','hand','Startup & capitali',`<div class="bt">Come finanziarti</div><div class="bm">Roadmap, VC, business angel, bandi.</div>`);
 T.briefing=`<div class="bcell brief" style="grid-column:1/-1;cursor:default"><div class="bh">${svg('spark')} Briefing del giorno</div><div id="brief-body" class="bt2" style="color:var(--mut)">Un riassunto di oggi scritto dal tuo modello AI.</div><div style="margin-top:4px"><button class="btn pri" id="brief-gen">${svg('spark')} Genera briefing</button></div></div>`;
 const tiles=OGGI_TILES.filter(t=>oggiOn(t[0])&&T[t[0]]).map(t=>T[t[0]]).join('');
 $('#view').innerHTML=`<div class="hero"><h2>Oggi.</h2><p>${esc(dt.charAt(0).toUpperCase()+dt.slice(1))} &middot; notizie, repo ed eventi di giornata.</p></div>
  ${statebar}<div class="bento">${tiles||'<div class="empty">Nessuna tessera attiva. Premi "Scegli tessere".</div>'}</div>`;
 const bg=$('#brief-gen');if(bg)bg.onclick=async()=>{const b=$('#brief-body');b.textContent='Scrivo il briefing...';
   try{const r=await (await fetch('/ask',{method:'POST',headers:{'Content-Type':'application/json'},
     body:JSON.stringify({q:"Fammi un briefing di massimo 4 frasi sui dati di oggi (repo, minacce, idee, mercato): cosa merita la mia attenzione e una mossa concreta. Tono diretto."})})).json();
   b.style.color='var(--txt)';b.textContent=r.answer||'Nessuna risposta.';}
   catch(e){b.textContent='Modello non disponibile. Controlla la sezione Modello AI (in basso a sinistra).';}};
};
function oggiPicker(){const ov=$('#onbov');ov.classList.add('on');
 let body=OGGI_TILES.map(t=>`<div class="onbsec ${oggiOn(t[0])?'on':''}" data-id="${t[0]}" onclick="this.classList.toggle('on')"><span class="cb">${svg('check')}</span><div><b style="font-size:14px">${esc(t[1])}</b></div></div>`).join('');
 ov.innerHTML=`<div class="onbcard"><h2>Tessere di Oggi</h2><div class="sub">Scegli cosa vedere nella schermata Oggi. I feed (notizie, repo, minacce, agenda) mostrano solo le cose di giornata.</div>
  ${body}<div style="display:flex;gap:10px;justify-content:flex-end;margin-top:18px"><button class="btn" onclick="ovClose()">Annulla</button><button class="btn pri" onclick="oggiSave()">${svg('check')} Salva</button></div></div>`;
}
function oggiSave(){const on={};document.querySelectorAll('#onbov .onbsec').forEach(e=>{on[e.dataset.id]=e.classList.contains('on');});
 LS.set('oggi_tiles',on);ovClose();RENDER.oggi('oggi');}

// ================= Investitori =================
RENDER.investitori=function(){
 const ROAD=[
  ['Idea e validazione','pre-seed',"Trasforma l'intuizione in un problema reale e misurabile. <b>Parla con 20-30 potenziali clienti</b> prima di scrivere codice. Obiettivo: prova che il problema esiste e che qualcuno pagherebbe."],
  ['MVP e primi utenti','pre-seed',"Costruisci il minimo che risolve il problema. Cerca <b>segnali di trazione</b>: utenti attivi, retention, prime revenue. Qui bastano risparmi, <b>FFF</b> (Family, Friends, Fools) e bandi."],
  ['Product-market fit','seed',"Gli utenti tornano e crescono da soli (passaparola). Metriche che contano: <b>retention, CAC, LTV, crescita MoM</b>. Raccogli il <b>seed</b> da business angel e fondi seed per accelerare."],
  ['Scala e crescita','Series A/B',"Il modello funziona, ora si spinge sull'acceleratore: assunzioni, mercati, canali. I <b>VC</b> entrano quando vedono crescita ripetibile e un mercato grande (TAM)."],
  ['Espansione','Series C+',"Dominare la categoria, nuovi prodotti/geografie. Round grandi da fondi late-stage, growth equity, venture debt."],
  ['Uscita','exit',"<b>Acquisizione</b> o <b>IPO</b>: gli investitori (e tu) monetizzano. Oppure resti indipendente con un business profittevole (bootstrap forever)."]];
 const SRC=[
  ['Bootstrapping','I tuoi soldi e i ricavi','0 - risparmi',"Nessuna diluizione, controllo totale, ma crescita piu lenta. Ideale finche non serve capitale per scalare."],
  ['FFF + Grant/Bandi','Family, Friends, Fools e fondi pubblici','5k - 150k',"Bandi EU/regionali (es. EIC Accelerator, Smart&Start, bandi regionali), non diluitivi. Servono documenti ma sono 'soldi gratis'."],
  ['Business Angel','Privati che investono i propri soldi','20k - 300k',"Oltre ai soldi portano esperienza e contatti. Si trovano su reti (IBAN, Italian Angels for Growth, Club degli Investitori) e LinkedIn."],
  ['Acceleratori / Incubatori','Programmi intensivi con piccolo capitale','20k - 150k + equity',"Es. Y Combinator, Techstars, in Italia LVenture, B4i, PoliHub. Danno mentorship, network e un demo day davanti agli investitori."],
  ['Venture Capital','Fondi che investono capitale di terzi','300k - 10M+',"Cercano crescita e mercati enormi. In Italia: CDP Venture, United Ventures, P101, Italian Founders Fund. Vogliono ritorni 10x+."],
  ['Equity Crowdfunding','Tanti piccoli investitori online','50k - 1M',"Piattaforme come Mamacrowd, Crowdfundme. Ottimo anche come marketing e validazione pubblica."],
  ['Venture Debt','Prestito per startup gia finanziate','variabile',"Capitale senza cedere equity, ma va restituito. Utile tra un round e l'altro."]];
 const GLOSS=[
  ['Term sheet',"Il documento (non vincolante) con le condizioni principali dell'investimento: valutazione, quota, diritti."],
  ['Valutazione pre/post',"Pre-money = valore prima dei soldi; post-money = pre + investimento. Definisce quanta % cedi."],
  ['Cap table',"La tabella di chi possiede cosa (fondatori, dipendenti, investitori) e le percentuali."],
  ['Diluizione',"La riduzione della tua % quando entrano nuovi investitori. Normale: si punta a una fetta piu piccola di una torta molto piu grande."],
  ['SAFE / Convertible',"Strumenti per raccogliere in fretta rimandando la valutazione a un round futuro."],
  ['Vesting',"Le quote (tue e del team) maturano nel tempo (tipico: 4 anni con 1 anno di cliff). Trattiene le persone."],
  ['Liquidation preference',"Chi viene pagato prima in caso di vendita. 1x = l'investitore recupera almeno quanto messo."],
  ['Runway',"Per quanti mesi hai cassa al ritmo di spesa attuale. Sotto i 6 mesi = raccogli o taglia."],
  ['TAM / SAM / SOM',"Mercato totale / servibile / che puoi realisticamente ottenere. I VC vogliono un TAM grande."],
  ['Traction',"La prova concreta che funziona: utenti, revenue, crescita. E la cosa che convince davvero."]];
 $('#view').innerHTML=`
  <div class="section-lead">Come finanziare una startup: <b>dove</b> trovare capitali, <b>come</b> avvicinarli e <b>quando</b> nel ciclo di vita. Sintesi pratica, non consulenza finanziaria o legale.</div>
  <div class="two" style="grid-template-columns:minmax(0,1fr) minmax(0,1fr);align-items:start">
   <div class="panel"><div class="panel-h">${svg('trend')} Roadmap del ciclo di vita</div><div class="panel-b"><div class="road">
     ${ROAD.map(s=>`<div class="rstep"><span class="rt">${esc(s[0])}</span><span class="rtag">${esc(s[1])}</span><div class="rd">${s[2]}</div></div>`).join('')}
   </div></div></div>
   <div class="panel"><div class="panel-h">${svg('hand')} Dove trovare i soldi</div><div class="panel-b">
     ${SRC.map(s=>`<div style="padding:12px 0;border-bottom:1px solid var(--line)"><div style="display:flex;justify-content:space-between;gap:12px;align-items:baseline"><b style="font-size:15px">${esc(s[0])}</b><span class="amt num">${esc(s[2])} EUR</span></div><div class="bm" style="color:var(--mut);font-size:13px;margin-top:3px">${esc(s[1])}</div><div class="rd" style="margin-top:6px;font-size:13.5px">${s[3]}</div></div>`).join('')}
   </div></div>
  </div>
  <div class="two" style="grid-template-columns:minmax(0,1fr) minmax(0,1fr);align-items:start;margin-top:20px">
   <div class="panel"><div class="panel-h">${svg('check')} Come contattarli (e farti dire di si)</div><div class="panel-b">
     <ul class="chk">
      <li><b>Warm intro</b>: la via migliore. Fatti presentare da un founder gia finanziato o da un altro angel.</li>
      <li><b>Cold email che funziona</b>: 5 righe. Cosa fai, trazione (numeri), quanto raccogli, perche proprio loro, un link al deck.</li>
      <li><b>Deck (10-12 slide)</b>: problema, soluzione, mercato, prodotto, trazione, business model, team, competitor, ask.</li>
      <li><b>Demo day</b>: entra in un acceleratore e presenta a decine di investitori insieme.</li>
      <li><b>Dove cercarli</b>: LinkedIn, Crunchbase, reti angel (IBAN, IAG), Twitter/X dei fondi, eventi (SftS, EU-Startups).</li>
      <li><b>Fai due diligence anche tu</b>: chiedi ad altri founder com'e stato lavorare con quel fondo.</li>
     </ul></div></div>
   <div class="panel"><div class="panel-h">${svg('bulb')} Cosa guardano gli investitori</div><div class="panel-b">
     <ul class="chk">
      <li><b>Team</b>: sanno eseguire? Perche proprio voi? (spesso conta piu dell'idea)</li>
      <li><b>Trazione</b>: crescita e retention reali battono qualsiasi proiezione.</li>
      <li><b>Mercato (TAM)</b>: abbastanza grande da giustificare un ritorno 10x+.</li>
      <li><b>Vantaggio</b>: perche non vi copiano in 6 mesi? (tech, dati, rete, brand)</li>
      <li><b>Uso dei fondi</b>: cosa fai coi soldi e quali milestone raggiungi.</li>
     </ul>
     <p class="mini" style="margin-top:12px">Regola d'oro: raccogli quando <b>non</b> ne hai bisogno disperato. La forza negoziale nasce dalla trazione e da piu opzioni sul tavolo.</p>
   </div></div>
  </div>
  <div class="dsec-t" style="margin:26px 0 14px">Glossario essenziale</div>
  <div class="gloss">${GLOSS.map(g=>`<div class="gterm"><b>${esc(g[0])}</b><span>${esc(g[1])}</span></div>`).join('')}</div>`;
};

// ================= Consumi Claude =================
const AGENT_ICON={claude:'robot',codex:'code',gemini:'spark'};
RENDER.consumi=function(){
 $('#view').innerHTML='<div class="empty">Leggo i consumi dei tuoi agenti AI...</div>';
 fetch('/usage').then(r=>r.json()).then(u=>{
  const src=u.sources||[];const det=src.filter(s=>s.present);const c=u.combined||{tot:{},per_day:[],models:[]};
  const t=c.tot||{input:0,output:0,cache_w:0,cache_r:0},total=c.total||1,bilTot=c.billable||1;
  const month=new Date().toISOString().slice(0,7),today=new Date().toISOString().slice(0,10);
  const pd=c.per_day||[];const todayTok=(pd.find(d=>d.day===today)||{bil:0}).bil;
  const mdays=pd.filter(d=>d.day.startsWith(month));const monthTok=mdays.reduce((s,d)=>s+(d.bil||0),0);
  const avgDayM=Math.round(monthTok/(mdays.length||1));
  const nowd=new Date();const dim=new Date(nowd.getFullYear(),nowd.getMonth()+1,0).getDate();const proj=avgDayM*dim;
  const PLANS=[['pro','Piano ~20 EUR/mese',20e6],['max5','Piano ~90 EUR/mese',100e6],['max20','Piano ~180 EUR/mese',400e6],['custom','Personalizzato',0]];
  const plan=LS.get('claude_plan','custom');const budget=plan==='custom'?LS.get('claude_budget',0):(PLANS.find(p=>p[0]===plan)||['','',0])[2];
  const parts=[['Input',t.input||0,'#5b8def'],['Output',t.output||0,'#3fb96b'],['Cache scritta',t.cache_w||0,'#f0883e'],['Cache riletta',t.cache_r||0,'#8a8cf7']];
  const K=[{k:'Token che pesano (tutti)',v:fmtTok(bilTot),cls:'a'},{k:'Oggi',v:fmtTok(todayTok),cls:'am'},{k:'Media / giorno (mese)',v:fmtTok(avgDayM),cls:'g'},{k:'Agenti attivi',v:det.length}];
  // card per agente rilevato
  const agentCard=s=>`<div class="card"><div class="ch"><div class="ct">${svg(AGENT_ICON[s.id]||'activity')} ${esc(s.label)}</div><div class="score num">${fmtTok(s.billable)}</div></div>
    <div class="meta"><span>${s.messages} msg</span><span>${s.days} giorni</span>${s.last?`<span>ult. ${esc(s.last)}</span>`:''}</div>
    ${s.per_day.length?chartLine(s.per_day.map(d=>d.bil||0)):''}
    <div class="tags" style="margin-top:8px">${(s.models[0]?`<span class="tag acc">${esc(s.models[0].model)}</span>`:'')}<span class="tag">${s.sessions} sessioni</span></div>
    <div class="mini" style="margin-top:6px">totale ${fmtTok(s.total)} &middot; token che pesano ${fmtTok(s.billable)}</div></div>`;
  const notDet=(u.not_detected||[]).map(x=>`<span class="tag" style="opacity:.7">${esc(x.label)}</span>`).join('');
  $('#view').innerHTML=kpis(K)+
   `<div class="panel" style="margin-bottom:20px"><div class="panel-h">${svg('robot')} I tuoi agenti AI <span class="cnt num">${det.length}</span></div><div class="panel-b">
     ${det.length?`<div class="grid">${det.map(agentCard).join('')}</div>`:'<div class="mini">Nessun agente con log locali rilevato. Le CLI come Claude Code, Codex o Gemini salvano i transcript in locale e vengono lette qui.</div>'}
     ${notDet?`<div class="mini" style="margin-top:16px;white-space:normal">Non tracciabili in automatico (l'uso sta sui server del provider, nessun log sul PC): ${notDet}. Per questi puoi controllare i consumi dal loro sito.</div>`:''}
   </div></div>
   <div class="two">
    <div class="panel"><div class="panel-h">${svg('activity')} Token che pesano, per giorno (tutti gli agenti)</div><div class="panel-b">
      ${chartLine(pd.map(d=>d.bil||0))}
      <div class="mini" style="margin-top:8px">${esc(c.first||'')} - ${esc(c.last||'')} &middot; ${c.days||0} giorni attivi (esclusa cache riletta)</div></div></div>
    <div class="panel"><div class="panel-h">Consumo e soglia mensile</div><div class="panel-b">
      <div class="fld" style="margin-bottom:12px"><label>soglia / budget mensile (combinato)</label>
        <select class="inp" id="cplan" style="width:100%">${PLANS.map(p=>`<option value="${p[0]}" ${plan===p[0]?'selected':''}>${p[1]}${p[2]?' &middot; '+fmtTok(p[2])+' tok':''}</option>`).join('')}</select></div>
      ${plan==='custom'?`<div class="fld" style="margin-bottom:14px"><label>budget token / mese</label><input class="inp" id="cb" type="number" placeholder="es. 100000000" value="${LS.get('claude_budget',0)||''}" style="width:100%"></div>`:''}
      ${budget?`<div class="mhead"><span>Usati questo mese (${month})</span><span class="num">${fmtTok(monthTok)} / ${fmtTok(budget)}</span></div>
        <div class="mbar ${monthTok>budget?'over':'kcal'}"><i style="width:${Math.min(100,Math.round(monthTok/budget*100))}%"></i></div>
        <div class="mini" style="margin-top:10px">${monthTok<budget?('Ti restano ~'+fmtTok(budget-monthTok)+' ('+Math.round((1-monthTok/budget)*100)+'%). Proiezione fine mese: '+fmtTok(proj)+(proj>budget?' &mdash; oltre soglia':' &mdash; entro soglia')):'Soglia superata di '+fmtTok(monthTok-budget)}</div>`
        :'<p class="mini">Scegli una soglia o un budget per vedere la percentuale usata su tutti gli agenti.</p>'}
      <p class="mini" style="margin-top:12px">Le soglie dei piani sono <b>stime</b> indicative in token: gli abbonamenti reali hanno limiti d'uso, non una quota fissa.</p></div></div>
   </div>
   <div class="two" style="margin-top:20px">
    <div class="panel"><div class="panel-h">Composizione dei token (tutti)</div><div class="panel-b">
      <div class="usebar">${parts.map(p=>`<i style="width:${(p[1]/total*100).toFixed(1)}%;background:${p[2]}"></i>`).join('')}</div>
      <div class="uselegend">${parts.map(p=>`<span><i class="d" style="background:${p[2]}"></i>${p[0]} <b>${fmtTok(p[1])}</b></span>`).join('')}</div>
      <p class="mini" style="margin-top:14px">La <b>cache riletta</b> e contesto riusato: domina il totale ma costa poco. A pesare sono input, output e cache scritta.</p></div></div>
    <div class="panel"><div class="panel-h">Per modello (tutti)</div><div class="panel-b">
      ${(c.models||[]).map(m=>`<div class="frow"><div class="fmain"><div class="fn">${esc(m.model)}</div></div><div class="fg num">${fmtTok(m.tok)}</div></div>`).join('')||'<div class="mini">Nessun dato.</div>'}</div></div>
   </div>${consumiSessions(u)}`;
  const cp=$('#cplan');if(cp)cp.onchange=()=>{LS.set('claude_plan',cp.value);RENDER.consumi();};
  const cb=$('#cb');if(cb)cb.onchange=()=>{LS.set('claude_budget',+cb.value||0);RENDER.consumi();};
  document.querySelectorAll('.sname').forEach(inp=>inp.onchange=()=>{const t=LS.get('claude_titles',{});t[inp.dataset.id]=inp.value.trim();LS.set('claude_titles',t);});
 }).catch(e=>{$('#view').innerHTML='<div class="empty">Errore nel leggere i consumi. Il server e attivo?</div>';});
};
function consumiSessions(u){const titles=LS.get('claude_titles',{});const by=u.sessions_by||{};let h='';
 (u.sources||[]).filter(s=>s.present&&(by[s.id]||[]).length).forEach(s=>{const list=by[s.id];
  h+=`<div class="panel" style="margin-top:20px"><div class="panel-h">${svg(AGENT_ICON[s.id]||'activity')} Sessioni &middot; ${esc(s.label)} <span class="cnt num">${list.length}</span></div><div class="panel-b">
   ${list.map(x=>{const title=titles[x.id]||x.fu||('Sessione '+String(x.id).slice(0,8));return `<div class="srow">
     <input class="sname" data-id="${esc(x.id)}" value="${esc(title)}" placeholder="Titolo sessione">
     <div class="sright"><div class="stok">${fmtTok(x.tok)}</div><div class="smeta">${x.msgs} msg${x.first?' &middot; '+esc(x.first):''}${x.last&&x.last!==x.first?' &rarr; '+esc(x.last):''}</div></div></div>`;}).join('')}</div></div>`;});
 return h;}
function dlMap(){const m=window.__map;if(!m)return;const r=m.r;
 let md=`# Mappa business: ${m.title}\n\n**${r.centro||m.title}**\n\n`;
 (r.rami||[]).forEach(n=>{md+=`## ${n.nome||''}\n`+(n.punti||[]).map(p=>`- ${p}`).join('\n')+`\n\n`;});
 downloadMd((m.title||'mappa').replace(/[^\w\-]+/g,'_').slice(0,50)+'.md',md);}
function dlFused(){const d=window.__fused;if(!d)return;
 let md=`# ${d.titolo}\n\n${d.descrizione||''}\n\n**Sinergia:** ${d.sinergia||''}\n\n**Problema:** ${d.problema||''}\n\n**Perche ora:** ${d.perche_ora||''}\n\n**Mercato:** ${d.tam||''}\n\n## Primi passi\n`+(d.passi||[]).map(p=>`- ${p}`).join('\n')+`\n\n_Fusione di: ${(d.fonti||[]).join(', ')}_\n`;
 downloadMd((d.titolo||'idea').replace(/[^\w\-]+/g,'_').slice(0,50)+'.md',md);}


// ================= Preferiti =================
function favRemove(kind,key){
 if(kind==='gh'){const s=LS.get('gh_saved',[]);const i=s.indexOf(key);if(i>=0)s.splice(i,1);LS.set('gh_saved',s);}
 else if(kind==='idee'){LS.set('idee_fav',LS.get('idee_fav',[]).filter(x=>x.titolo!==key));}
 else if(kind==='prod'){LS.set('prod_fav',LS.get('prod_fav',[]).filter(x=>x.titolo!==key));}
 RENDER.preferiti('preferiti');
}
RENDER.preferiti=function(){
 const idFav=LS.get('idee_fav',[]),prFav=LS.get('prod_fav',[]),ghF=LS.get('gh_saved',[]);
 const ghItems=ghF.map(fn=>P.github.find(r=>r.full_name===fn)||{full_name:fn,url:'https://github.com/'+fn});
 const tot=idFav.length+prFav.length+ghItems.length;
 const K=[{k:'Preferiti totali',v:tot,cls:'a'},{k:'Repo',v:ghItems.length},{k:'Idee',v:idFav.length,cls:'am'},{k:'Prodotti',v:prFav.length,cls:'g'}];
 if(!tot){$('#view').innerHTML=kpis(K)+'<div class="empty">Nessun preferito. Metti la stellina su repo, idee o prodotti per ritrovarli qui.</div>';return;}
 const esq=s=>(s||'').replace(/'/g,"\\'");
 const row=(title,sub,onRemove,href)=>`<div class="frow"><div class="fmain"><div class="fn">${href?`<a href="${esc(href)}" target="_blank" rel="noopener">${esc(title)}</a>`:esc(title)}</div>${sub?`<div class="fp">${sub}</div>`:''}</div><button class="star on" title="rimuovi dai preferiti" onclick="${onRemove}">${svg('star')}</button></div>`;
 let html=kpis(K);
 if(ghItems.length)html+=`<div class="panel" style="margin-bottom:18px"><div class="panel-h">${svg('github')} Repository <span class="cnt num">${ghItems.length}</span></div><div class="panel-b">${ghItems.map(r=>row(r.full_name,(r.tipo?esc(r.tipo):'')+(r.stars?' &middot; &#9733; '+nfmt(r.stars):''),`favRemove('gh','${esq(r.full_name)}')`,r.url)).join('')}</div></div>`;
 if(idFav.length)html+=`<div class="panel" style="margin-bottom:18px"><div class="panel-h">${svg('bulb')} Idee <span class="cnt num">${idFav.length}</span></div><div class="panel-b">${idFav.map(r=>row(r.titolo,esc(demoji(r.descrizione||'')),`favRemove('idee','${esq(r.titolo)}')`)).join('')}</div></div>`;
 if(prFav.length)html+=`<div class="panel"><div class="panel-h">${svg('euro')} Prodotti <span class="cnt num">${prFav.length}</span></div><div class="panel-b">${prFav.map(p=>{const s=prodStats(p);return row(p.titolo,(p.modello?esc(p.modello):'')+' &middot; '+eur(s.day)+'/giorno',`favRemove('prod','${esq(p.titolo)}')`);}).join('')}</div></div>`;
 $('#view').innerHTML=html;
};

// ================= Analisi CV =================
const scColor=p=>p>=75?'var(--green)':p>=50?'var(--amber)':'var(--red)';
function cvUploader(){
 return `<div class="panel" style="margin-bottom:18px"><div class="panel-b">
   <div class="cvdrop" id="cvdrop">${svg('doc')}<b>Trascina qui il CV in PDF o clicca per sceglierlo</b>
   <span>Resta tutto in locale: leggo il PDF e l'analisi la fa Ollama. Serve Ollama acceso.</span></div>
   <input type="file" id="cvfile" accept="application/pdf,.pdf" hidden></div></div><div id="cvout"></div>`;
}
function wireCv(){
 const drop=$('#cvdrop'),inp=$('#cvfile');if(!drop||!inp)return;
 drop.onclick=()=>inp.click();
 inp.onchange=()=>{if(inp.files[0])cvAnalyze(inp.files[0]);};
 drop.ondragover=e=>{e.preventDefault();drop.style.borderColor='var(--acc)';};
 drop.ondragleave=()=>drop.style.borderColor='';
 drop.ondrop=e=>{e.preventDefault();drop.style.borderColor='';const f=e.dataTransfer.files[0];if(f)cvAnalyze(f);};
}
async function cvAnalyze(file){
 const out=$('#cvout');
 if(file.type!=='application/pdf'&&!/\.pdf$/i.test(file.name)){out.innerHTML='<div class="empty">Serve un file PDF.</div>';return;}
 if(file.size>8e6){out.innerHTML='<div class="empty">PDF troppo grande (max 8 MB).</div>';return;}
 out.innerHTML='<div class="dwait">Leggo il PDF e chiedo l\'analisi a Ollama... (puo\' volerci qualche secondo)</div>';
 try{
  const b64=await new Promise((res,rej)=>{const r=new FileReader();r.onload=()=>res(r.result.split(',')[1]);r.onerror=rej;r.readAsDataURL(file);});
  const d=await (await fetch('/cv',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({pdf:b64})})).json();
  if(d.error){out.innerHTML=`<div class="empty">${esc(d.error)}<br><br>Se e' Ollama, accendilo in basso a sinistra e riprova.</div>`;return;}
  d._file=file.name;d._when=new Date().toLocaleDateString('it-IT');
  LS.set('cv_last',d);
  out.innerHTML=cvResult(d);
 }catch(e){out.innerHTML='<div class="empty">Errore di rete. Il server e\' attivo?</div>';}
}
function cvResult(d){
 const p=d.punteggio||0,det=d.dettaglio||{};
 const dl=[['struttura','Struttura'],['contenuto','Contenuto'],['impatto','Impatto'],['leggibilita','Leggibilita']];
 const grav={alta:'r',media:'am',bassa:'g'};
 const list=(a,f)=>(Array.isArray(a)?a:[]).map(f).join('');
 let h=`<div class="panel" style="margin-bottom:18px"><div class="panel-b"><div class="cvhead">
   <div class="cvscore" style="--p:${p};--sc:${scColor(p)}"><div class="in"><div class="n num">${p}</div><div class="l">su 100</div></div></div>
   <div style="flex:1;min-width:220px"><div style="font-size:19px;font-weight:600">${esc(d.nome||'CV')}</div>
   <div style="color:var(--acc);font-size:14px;margin-top:2px">${esc(d.ruolo||'')}</div>
   ${d.sintesi?`<div style="color:var(--mut);font-size:13.5px;margin-top:8px">${esc(demoji(d.sintesi))}</div>`:''}
   <div class="fp" style="margin-top:8px">${esc(d._file||'')}${d._when?' &middot; '+esc(d._when):''}</div></div></div>
   <div class="cvsub">${dl.map(x=>`<div class="s"><div class="k"><span>${x[1]}</span><span class="num" style="color:${scColor(det[x[0]]||0)}">${det[x[0]]||0}</span></div><div class="dbar"><i style="width:${det[x[0]]||0}%;background:${scColor(det[x[0]]||0)}"></i></div></div>`).join('')}</div>
   </div></div>`;
 // dati estratti
 const contatti=d.contatti||{};const cvals=[contatti.email,contatti.telefono,contatti.link].filter(Boolean);
 let dati='';
 if((d.competenze||[]).length)dati+=`<div style="margin-bottom:14px"><div class="fp" style="margin-bottom:6px">Competenze</div>${list(d.competenze,c=>`<span class="tag acc" style="margin:0 6px 6px 0;display:inline-block">${esc(demoji(c))}</span>`)}</div>`;
 if((d.esperienze||[]).length)dati+=`<div style="margin-bottom:14px"><div class="fp" style="margin-bottom:6px">Esperienze</div>${list(d.esperienze,e=>`<div class="frow"><div class="fmain"><div class="fn">${esc(e.ruolo||'')}${e.dove?' &middot; '+esc(e.dove):''}</div>${(e.punti||[]).length?`<div class="fp" style="white-space:normal">${(e.punti||[]).map(pt=>esc(demoji(pt))).join(' &middot; ')}</div>`:''}</div><span class="tag">${esc(e.periodo||'')}</span></div>`)}</div>`;
 if((d.istruzione||[]).length)dati+=`<div><div class="fp" style="margin-bottom:6px">Istruzione</div>${list(d.istruzione,i=>`<div class="frow"><div class="fmain"><div class="fn">${esc(i.titolo||'')}</div><div class="fp">${esc(i.dove||'')}</div></div><span class="tag">${esc(i.anno||'')}</span></div>`)}</div>`;
 if(cvals.length||dati)h+=`<div class="panel" style="margin-bottom:18px"><div class="panel-h">${svg('doc')} Dati estratti${cvals.length?`<span class="fp" style="margin-left:auto;font-weight:400">${cvals.map(esc).join(' &middot; ')}</span>`:''}</div><div class="panel-b">${dati||'<div class="fp">Nessun dato strutturato.</div>'}</div></div>`;
 // punti forti
 if((d.punti_forti||[]).length)h+=`<div class="panel" style="margin-bottom:18px"><div class="panel-h">${svg('check')} Punti forti <span class="cnt num">${d.punti_forti.length}</span></div><div class="panel-b">${list(d.punti_forti,x=>`<div class="frow"><div class="fmain"><div class="fn" style="white-space:normal;font-weight:400">${esc(demoji(x))}</div></div><span class="tag g">ok</span></div>`)}</div></div>`;
 // problemi: cosa + come + gravita
 if((d.problemi||[]).length)h+=`<div class="panel cvprob" style="margin-bottom:18px"><div class="panel-h">${svg('spark')} Cosa migliorare <span class="cnt num">${d.problemi.length}</span></div><div class="panel-b">${list(d.problemi,pb=>`<div class="frow"><div class="fmain"><div class="fn" style="white-space:normal">${esc(demoji(pb.cosa||''))}</div><div class="g"><b style="color:var(--green)">Come:</b> ${esc(demoji(pb.come||''))}</div></div><span class="tag ${grav[(pb.gravita||'').toLowerCase()]||''}">${esc(pb.gravita||'')}</span></div>`)}</div></div>`;
 // riscritture prima/dopo
 if((d.riscritture||[]).length)h+=`<div class="panel"><div class="panel-h">${svg('doc')} Riscritture suggerite <span class="cnt num">${d.riscritture.length}</span></div><div class="panel-b">${list(d.riscritture,rw=>`<div class="cvrw"><div class="pre">${esc(demoji(rw.prima||''))}</div><div class="post">${esc(demoji(rw.dopo||''))}</div></div>`)}</div></div>`;
 return h;
}
RENDER.cv=function(){
 $('#view').innerHTML=cvUploader();
 const last=LS.get('cv_last',null);
 if(last)$('#cvout').innerHTML=cvResult(last);
 wireCv();
};

// ================= CyberQuest =================
const CG_TOTAL=520;               // lunghezza del percorso (>500 livelli)
let cg=null;                      // banca+capitoli+ranghi dal server
const cgGenCache={};              // livelli generati da Ollama, in memoria (non persistiti)
const _today=()=>new Date().toISOString().slice(0,10);
function cgLoadProg(){
 const p=LS.get('cyber_prog',null)||{xp:0,done:{},vite:5,viteDay:'',streak:0,streakDay:''};
 if(p.viteDay!==_today()){p.vite=5;p.viteDay=_today();LS.set('cyber_prog',p);} // vite si ricaricano ogni giorno
 return p;
}
function cgRankOf(xp){let r=cg.ranks[0];cg.ranks.forEach(x=>{if(xp>=x.xp)r=x;});return r;}
function cgNextRank(xp){return cg.ranks.find(x=>x.xp>xp)||null;}
function cgChap(id){return cg.chapters.find(c=>c.id===id)||{nome:id,icon:'shield',col:'var(--acc)'};}
function cgLevelAt(i){                        // definizione del livello all'indice i
 if(i<cg.levels.length)return Object.assign({idx:i},cg.levels[i]);
 const ch=cg.chapters[i%cg.chapters.length]; // oltre la banca: capitoli ciclati, difficolta crescente
 return {idx:i,cap:ch.id,diff:Math.min(3,1+Math.floor((i-cg.levels.length)/70)),gen:true,_needgen:true};
}
function cgCurrent(p){let i=0;while(p.done[i]!=null&&i<CG_TOTAL)i++;return i;}
RENDER.cyberquest=async function(){
 const view=$('#view');
 if(!cg){view.innerHTML='<div class="dwait">Carico il percorso...</div>';
  try{cg=await (await fetch('/cyber-seed')).json();}catch(e){view.innerHTML='<div class="empty">Impossibile caricare il percorso. Il server e attivo?</div>';return;}}
 if(!$('#cgov')){const o=el('div');o.id='cgov';o.onclick=e=>{if(e.target===o)cgClose();};document.body.appendChild(o);}
 cgRenderPath();
};
function cgRenderPath(){
 const p=cgLoadProg(),cur=cgCurrent(p),rk=cgRankOf(p.xp),nx=cgNextRank(p.xp);
 const base=rk.xp,top=nx?nx.xp:rk.xp,pct=nx?Math.round((p.xp-base)/(top-base)*100):100;
 let h=`<div class="cgnote">${svg('shield')}<span>Percorso pensato per farti usare i tuoi dispositivi e le tue informazioni nel modo piu sicuro possibile, imparando strada facendo molti concetti di CyberSecurity. Si parte da zero: nessuna competenza richiesta.</span></div>
  <div class="cgtop">
  <div class="cgrank"><div class="rico">${svg('trophy')}</div><div><div class="rn">${esc(rk.nome)}</div><div class="rx">${p.xp} XP${nx?' &middot; '+(nx.xp-p.xp)+' al prossimo grado':' &middot; grado massimo'}</div></div></div>
  <div class="cgxp"><div class="xt"><span>${esc(rk.nome)}</span><span>${nx?esc(nx.nome):''}</span></div><div class="dbar" style="height:9px"><i style="width:${pct}%"></i></div></div>
  <div class="cgstat"><div class="st hp" title="Vite (si ricaricano ogni giorno)">${svg('heart')}${p.vite}</div><div class="st fl" title="Giorni di fila">${svg('fire')}${p.streak||0}</div><div class="st" title="Livelli completati">${svg('check')}${Object.keys(p.done).length}</div></div></div>`;
 h+='<div class="cgpath">';
 let lastCap=null,cnt=0;
 for(let i=0;i<CG_TOTAL;i++){
  const lv=cgLevelAt(i);
  if(lv.cap!==lastCap){                       // intestazione mondo/capitolo
   const c=cgChap(lv.cap);lastCap=lv.cap;
   const gen=i>=cg.levels.length;
   h+=`<div class="cgworld"><div class="wi" style="background:${c.col}22;color:${c.col}">${svg(c.icon)}</div><div><b>${esc(c.nome)}</b> <span>${gen?'allenamento generato':'campagna'}</span></div></div>`;
  }
  const st=p.done[i]!=null?'done':(i===cur?'cur':(i<cur?'done':'lock'));
  const stars=p.done[i]!=null?'&#9733;'.repeat(p.done[i]):'';
  const off=(cnt%2?28:-28);cnt++;
  const inner=st==='done'?svg('check'):st==='lock'?svg('lock'):(lv._needgen?svg('game'):svg('play'));
  h+=`<div class="cgrow"><button class="cgnode ${st}${lv._needgen?' gen':''}" style="margin-left:${off}px" ${st==='lock'?'disabled':''} onclick="cgOpen(${i})">${inner}${stars?`<span class="stars">${stars}</span>`:''}</button></div>`;
 }
 h+='</div>';
 $('#view').innerHTML=h;
}
async function cgOpen(i){
 const p=cgLoadProg(),cur=cgCurrent(p);
 if(i>cur){return;}                            // ancora bloccato
 let lv=cgLevelAt(i);
 const ov=$('#cgov');ov.classList.add('on');
 if(lv._needgen){
  if(cgGenCache[i]){lv=cgGenCache[i];}
  else{
   ov.innerHTML=`<div class="cgcard"><div class="dwait">Genero il livello con Ollama...</div></div>`;
   try{
    const avoid=Object.values(cgGenCache).filter(x=>x.cap===lv.cap).map(x=>x.q).slice(-5);
    const d=await (await fetch('/cyber-gen',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({chapter:lv.cap,diff:lv.diff,avoid})})).json();
    if(d.error){ov.innerHTML=`<div class="cgcard"><div class="empty">${esc(d.error)}<br><br>Serve Ollama acceso (in basso a sinistra).</div><div style="text-align:center"><button class="btn" onclick="cgOpen(${i})">Riprova</button> <button class="btn" onclick="cgClose()">Chiudi</button></div></div>`;return;}
    lv=Object.assign({idx:i},d);cgGenCache[i]=lv;
   }catch(e){ov.innerHTML=`<div class="cgcard"><div class="empty">Errore di rete.</div><div style="text-align:center"><button class="btn" onclick="cgClose()">Chiudi</button></div></div>`;return;}
  }
 }
 cgPlay(lv);
}
let _cgAtt=0;
function cgPlay(lv){
 _cgAtt=0;
 const c=cgChap(lv.cap);
 let body;
 if(lv.tipo==='input'){
  body=`<input class="cginp" id="cginp" placeholder="Scrivi la risposta..." autocomplete="off"><div style="margin-top:12px;text-align:right"><button class="btn" onclick="cgAnswerInput(${lv.idx})">${svg('check')} Conferma</button></div>`;
 }else if(lv.tipo==='spot'){
  body=`<div class="cgcode">${(lv.code||[]).map((ln,j)=>`<div class="cgline" data-j="${j}" onclick="this.classList.toggle('sel')"><span class="ln">${j+1}</span><code>${esc(ln)}</code></div>`).join('')}</div>
   <div style="margin-top:12px;text-align:right"><button class="btn" onclick="cgAnswerSpot(${lv.idx})">${svg('check')} Conferma</button></div>`;
 }else if(lv.tipo==='fix'){
  body=`<textarea class="cginp cgta" id="cgta" spellcheck="false" rows="4">${esc(lv.start||'')}</textarea>
   <div style="margin-top:12px;text-align:right"><button class="btn" onclick="cgAnswerFix(${lv.idx})">${svg('check')} Verifica il codice</button></div>`;
 }else if(lv.tipo==='order'){
  const sh=cgShuffle((lv.items||[]).map((t,j)=>[t,j]));
  body=`<div class="cgord" id="cgord">${sh.map(([t,orig])=>`<div class="cgoi" data-o="${orig}"><span class="gr">${svg('code')}</span><span class="ot">${esc(t)}</span><span class="ob"><button onclick="cgMove(this,-1)" title="su">&#9650;</button><button onclick="cgMove(this,1)" title="giu">&#9660;</button></span></div>`).join('')}</div>
   <div style="margin-top:12px;text-align:right"><button class="btn" onclick="cgAnswerOrder(${lv.idx})">${svg('check')} Conferma ordine</button></div>`;
 }else{
  body=(lv.opts||[]).map((o,j)=>`<button class="cgq-opt" data-j="${j}" onclick="cgAnswerScelta(${lv.idx},${j})">${esc(demoji(o))}</button>`).join('');
 }
 $('#cgov').innerHTML=`<div class="cgcard"><div class="ch"><span style="color:${c.col}">${svg(c.icon)}</span> ${esc(c.nome)} &middot; livello ${lv.idx+1} &middot; difficolta ${lv.diff||1}/3${lv.gen?' &middot; generato':''}</div>
  <div class="qq">${esc(demoji(lv.q))}</div><div id="cgbody">${body}</div><div id="cgfb"></div></div>`;
 window.__cglv=lv;
 setTimeout(()=>{const inp=$('#cginp');if(inp)inp.focus();},50);
}
function _norm(s){return (''+s).toLowerCase().normalize('NFD').replace(/[̀-ͯ]/g,'').replace(/[^a-z0-9]/g,'');}
function cgAnswerScelta(i,j){
 const lv=window.__cglv;if(!lv)return;const ok=(j===lv.a);
 document.querySelectorAll('.cgq-opt').forEach(b=>{const bj=+b.dataset.j;
  if(bj===lv.a)b.classList.add('ok');if(bj===j&&!ok)b.classList.add('no');b.disabled=true;});
 cgResolve(i,ok);
}
function cgAnswerInput(i){
 const lv=window.__cglv;if(!lv)return;const v=$('#cginp').value;
 const ok=_norm(v)===_norm(lv.a);
 const inp=$('#cginp');inp.disabled=true;inp.style.borderColor=ok?'var(--green)':'var(--red)';
 document.querySelector('#cgbody .btn').disabled=true;
 cgResolve(i,ok);
}
function cgShuffle(a){for(let i=a.length-1;i>0;i--){const j=Math.floor(Math.random()*(i+1));[a[i],a[j]]=[a[j],a[i]];}
 // evita (raramente) che esca gia ordinato
 if(a.every((x,k)=>x[1]===k)&&a.length>1){[a[0],a[1]]=[a[1],a[0]];}return a;}
function cgMove(btn,dir){const it=btn.closest('.cgoi'),box=it.parentNode;
 if(dir<0&&it.previousElementSibling)box.insertBefore(it,it.previousElementSibling);
 if(dir>0&&it.nextElementSibling)box.insertBefore(it.nextElementSibling,it);}
function cgAnswerSpot(i){
 const lv=window.__cglv;if(!lv)return;
 const sel=new Set([...document.querySelectorAll('.cgline.sel')].map(e=>+e.dataset.j));
 const bad=new Set(lv.bad||[]);
 const ok=sel.size===bad.size&&[...bad].every(b=>sel.has(b));
 document.querySelectorAll('.cgline').forEach(e=>{const j=+e.dataset.j;e.onclick=null;
  if(bad.has(j))e.classList.add('good');else if(sel.has(j))e.classList.add('wrong');e.classList.remove('sel');});
 document.querySelector('#cgbody .btn').disabled=true;
 cgResolve(i,ok);
}
function cgAnswerFix(i){
 const lv=window.__cglv;if(!lv)return;const code=$('#cgta').value;
 const must=(lv.must||[]).every(p=>{try{return new RegExp(p,'i').test(code)}catch(e){return false}});
 const forbid=(lv.forbid||[]).some(p=>{try{return new RegExp(p,'i').test(code)}catch(e){return false}});
 const ok=must&&!forbid;
 const ta=$('#cgta');ta.disabled=true;ta.style.borderColor=ok?'var(--green)':'var(--red)';
 document.querySelector('#cgbody .btn').disabled=true;
 cgResolve(i,ok);
}
function cgAnswerOrder(i){
 const lv=window.__cglv;if(!lv)return;
 const cur=[...document.querySelectorAll('.cgoi')].map(e=>+e.dataset.o);
 const ok=cur.every((v,k)=>v===k);
 document.querySelectorAll('.cgoi').forEach((e,k)=>{e.classList.add(+e.dataset.o===k?'good':'wrong');
  e.querySelectorAll('button').forEach(b=>b.disabled=true);});
 document.querySelector('#cgbody .btn').disabled=true;
 cgResolve(i,ok);
}
function cgResolve(i,ok){
 _cgAtt++;
 const lv=window.__cglv,p=cgLoadProg(),fb=$('#cgfb');
 const first=p.done[i]==null;
 if(ok){
  const stars=_cgAtt<=1?3:(_cgAtt===2?2:1);
  if(first){p.xp+=10*(lv.diff||1);}                 // XP solo la prima volta (niente farming)
  p.done[i]=Math.max(p.done[i]||0,stars);
  // streak: primo completamento del giorno
  if(p.streakDay!==_today()){const y=new Date(Date.now()-864e5).toISOString().slice(0,10);p.streak=(p.streakDay===y?(p.streak||0)+1:1);p.streakDay=_today();}
  LS.set('cyber_prog',p);
  fb.className='cgfb ok';fb.innerHTML=`<b>${svg('check')} Giusto! ${'&#9733;'.repeat(stars)} ${first?'+'+(10*(lv.diff||1))+' XP':'(gia completato)'}</b>${esc(demoji(lv.perche||''))}<div style="margin-top:12px;text-align:right"><button class="btn" onclick="cgClose(true)">${svg('play')} Continua</button></div>`;
 }else{
  p.vite=Math.max(0,(p.vite||0)-1);LS.set('cyber_prog',p);
  let sol='';
  if(lv.tipo==='input')sol=esc(lv.a);
  else if(lv.tipo==='scelta')sol=esc(demoji((lv.opts||[])[lv.a]||''));
  else if(lv.tipo==='fix')sol='<code style="display:block;margin-top:4px;white-space:pre-wrap">'+esc(lv.sol||'')+'</code>';
  else if(lv.tipo==='spot')sol='righe '+(lv.bad||[]).map(b=>b+1).join(', ')+' (evidenziate)';
  else if(lv.tipo==='order')sol='vedi ordine corretto evidenziato';
  fb.className='cgfb no';fb.innerHTML=`<b>${svg('x')} Non giusto. Vite rimaste: ${p.vite}</b>Soluzione: <b style="display:inline;color:var(--green)">${sol}</b><br>${esc(demoji(lv.perche||''))}
   <div style="margin-top:12px;text-align:right">${p.vite>0?`<button class="btn" onclick="cgPlay(window.__cglv)">Riprova</button> `:''}<button class="btn" onclick="cgClose(true)">Chiudi</button></div>`;
 }
}
function cgClose(refresh){$('#cgov').classList.remove('on');$('#cgov').innerHTML='';window.__cglv=null;if(refresh)cgRenderPath();}

// ================= Riassunto PDF =================
RENDER.riassunto=function(){
 $('#view').innerHTML=`<div class="panel" style="margin-bottom:18px"><div class="panel-b">
   <div class="cvdrop" id="rsdrop">${svg('book')}<b>Trascina qui un PDF o clicca per sceglierlo</b>
   <span>Paper, dispensa, contratto, articolo. Resta in locale; la sintesi la fa Ollama.</span></div>
   <input type="file" id="rsfile" accept="application/pdf,.pdf" hidden></div></div><div id="rsout"></div>`;
 const drop=$('#rsdrop'),inp=$('#rsfile');
 drop.onclick=()=>inp.click();
 inp.onchange=()=>{if(inp.files[0])rsAnalyze(inp.files[0]);};
 drop.ondragover=e=>{e.preventDefault();drop.style.borderColor='var(--acc)';};
 drop.ondragleave=()=>drop.style.borderColor='';
 drop.ondrop=e=>{e.preventDefault();drop.style.borderColor='';const f=e.dataTransfer.files[0];if(f)rsAnalyze(f);};
};
async function rsAnalyze(file){
 const out=$('#rsout');
 if(file.type!=='application/pdf'&&!/\.pdf$/i.test(file.name)){out.innerHTML='<div class="empty">Serve un file PDF.</div>';return;}
 if(file.size>10e6){out.innerHTML='<div class="empty">PDF troppo grande (max 10 MB).</div>';return;}
 out.innerHTML='<div class="dwait">Leggo il PDF e riassumo con Ollama...</div>';
 try{
  const b64=await new Promise((res,rej)=>{const r=new FileReader();r.onload=()=>res(r.result.split(',')[1]);r.onerror=rej;r.readAsDataURL(file);});
  const d=await (await fetch('/pdfsum',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({pdf:b64})})).json();
  if(d.error){out.innerHTML=`<div class="empty">${esc(d.error)}<br><br>Se e' Ollama, accendilo in basso a sinistra.</div>`;return;}
  const L=(a,f)=>(Array.isArray(a)?a:[]).map(f).join('');
  let h=`<div class="panel" style="margin-bottom:18px"><div class="panel-b">
   <div style="font-size:19px;font-weight:600">${esc(d.titolo||file.name)}</div>
   ${d.tipo?`<span class="tag acc" style="margin-top:6px;display:inline-block">${esc(d.tipo)}</span>`:''}
   <div style="color:var(--mut);font-size:14px;margin-top:10px;line-height:1.5">${esc(demoji(d.sintesi||''))}</div></div></div>`;
  if((d.punti_chiave||[]).length)h+=`<div class="panel" style="margin-bottom:18px"><div class="panel-h">${svg('check')} Punti chiave</div><div class="panel-b">${L(d.punti_chiave,x=>`<div class="frow"><div class="fmain"><div class="fn" style="white-space:normal;font-weight:400">${esc(demoji(x))}</div></div></div>`)}</div></div>`;
  if((d.termini||[]).length)h+=`<div class="panel" style="margin-bottom:18px"><div class="panel-h">${svg('book')} Termini</div><div class="panel-b">${L(d.termini,t=>`<div class="frow"><div class="fmain"><div class="fn">${esc(t.t||'')}</div><div class="fp" style="white-space:normal">${esc(demoji(t.d||''))}</div></div></div>`)}</div></div>`;
  if((d.domande||[]).length)h+=`<div class="panel"><div class="panel-h">${svg('chat')} Domande di verifica</div><div class="panel-b">${L(d.domande,x=>`<div class="frow"><div class="fmain"><div class="fn" style="white-space:normal;font-weight:400">${esc(demoji(x))}</div></div></div>`)}</div></div>`;
  out.innerHTML=h;
 }catch(e){out.innerHTML='<div class="empty">Errore di rete.</div>';}
}

// ================= Palestra colloquio =================
function _needCv(){const cv=LS.get('cv_last',null);
 if(!cv)return {ok:false,html:`<div class="empty">Prima analizza il tuo CV nella sezione <b>Analisi CV</b>: mi serve per personalizzare.<br><br><button class="btn pri" onclick="go('cv')">${svg('doc')} Vai ad Analisi CV</button></div>`};
 return {ok:true,cv};}
RENDER.colloquio=function(){
 const g=_needCv();
 if(!g.ok){$('#view').innerHTML=g.html;return;}
 const ruolo=g.cv.ruolo||'';
 $('#view').innerHTML=`<div class="panel" style="margin-bottom:18px"><div class="panel-b">
   <div class="toolbar"><input class="inp" id="ivrole" placeholder="Ruolo target (es. Frontend Developer)" value="${esc(ruolo)}" style="flex:1">
   <button class="btn pri" id="ivgen" onclick="ivGen()">${svg('chat')} Genera domande</button></div>
   <div class="fp" style="margin-top:8px">Uso il tuo CV (${esc(g.cv.nome||'profilo')}) per personalizzare.</div></div></div><div id="ivout"></div>`;
};
async function ivGen(){
 const g=_needCv();if(!g.ok)return;
 const ruolo=$('#ivrole').value.trim()||g.cv.ruolo||'';
 const out=$('#ivout');out.innerHTML='<div class="dwait">Preparo le domande con Ollama...</div>';
 try{
  const d=await (await fetch('/interview',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({cv:g.cv,ruolo})})).json();
  if(d.error){out.innerHTML=`<div class="empty">${esc(d.error)}<br><br>Serve Ollama acceso.</div>`;return;}
  const badge={tecnica:'acc',comportamentale:'am',hr:'g'};
  const dom=(d.domande||[]);
  if(!dom.length){out.innerHTML='<div class="empty">Nessuna domanda generata, riprova.</div>';return;}
  out.innerHTML=`<div class="panel"><div class="panel-h">${svg('chat')} ${dom.length} domande per ${esc(ruolo||'il ruolo')}</div><div class="panel-b">${dom.map((q,i)=>`
   <div class="frow" style="align-items:flex-start"><div class="fmain"><div class="fn" style="white-space:normal">${i+1}. ${esc(demoji(q.q||''))}</div>
    <button class="btn" style="margin-top:8px" onclick="this.nextElementSibling.style.display='block';this.style.display='none'">Mostra traccia</button>
    <div class="fp" style="display:none;white-space:normal;margin-top:8px;padding:10px 12px;background:var(--panel2);border-radius:var(--rk)"><b style="color:var(--green)">Traccia:</b> ${esc(demoji(q.traccia||''))}</div>
   </div><span class="tag ${badge[(q.tipo||'').toLowerCase()]||''}">${esc(q.tipo||'')}</span></div>`).join('')}</div></div>`;
 }catch(e){out.innerHTML='<div class="empty">Errore di rete.</div>';}
}

// ================= Lettera & Job Match =================
RENDER.jobmatch=function(){
 const g=_needCv();
 if(!g.ok){$('#view').innerHTML=g.html;return;}
 $('#view').innerHTML=`<div class="panel" style="margin-bottom:18px"><div class="panel-b">
   <div class="fp" style="margin-bottom:8px">Incolla il <b>link</b> dell'annuncio: lo scarico e lo confronto col tuo CV (${esc(g.cv.nome||'profilo')}), con la probabilita di essere chiamato.</div>
   <div class="toolbar"><input class="inp" id="jmurl" placeholder="https://... link dell'offerta di lavoro" style="flex:1">
   <button class="btn pri" onclick="jmGo(true)">${svg('send')} Analizza dal link</button></div>
   <div style="margin-top:12px"><button class="btn" onclick="this.nextElementSibling.style.display='block';this.style.display='none'">oppure incolla il testo a mano</button>
    <div style="display:none;margin-top:10px"><textarea class="cginp" id="jmtext" rows="6" placeholder="Incolla qui la descrizione della posizione..."></textarea>
    <div style="text-align:right;margin-top:10px"><button class="btn" onclick="jmGo(false)">${svg('send')} Analizza il testo</button></div></div></div>
   <div class="fp" style="margin-top:10px;opacity:.8">Nota: alcuni siti (LinkedIn, Indeed) caricano l'annuncio via JavaScript o richiedono login: in quel caso usa l'incolla-testo.</div>
   </div></div><div id="jmout"></div>`;
};
async function jmGo(fromUrl){
 const g=_needCv();if(!g.ok)return;
 const out=$('#jmout');
 let body;
 if(fromUrl){
  const url=($('#jmurl').value||'').trim();
  if(!/^https?:\/\/.+/.test(url)){out.innerHTML='<div class="empty">Inserisci un link http/https valido.</div>';return;}
  body={cv:g.cv,url};
 }else{
  const ann=($('#jmtext')?$('#jmtext').value:'').trim();
  if(ann.length<40){out.innerHTML='<div class="empty">Incolla il testo dell\'annuncio (almeno qualche riga).</div>';return;}
  body={cv:g.cv,annuncio:ann};
 }
 out.innerHTML='<div class="dwait">'+(fromUrl?'Scarico l\'annuncio dal link, ':'')+'confronto col profilo e scrivo la lettera...</div>';
 try{
  const d=await (await fetch('/jobmatch',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)})).json();
  if(d.error){out.innerHTML=`<div class="empty">${esc(d.error)}<br><br>Se e' Ollama, accendilo in basso a sinistra.</div>`;return;}
  const prob=d.probabilita||d.punteggio||0,match=d.punteggio||0,L=(a,f)=>(Array.isArray(a)?a:[]).map(f).join('');
  window.__jmletter=d.lettera||'';
  let h=`<div class="panel" style="margin-bottom:18px"><div class="panel-b"><div class="cvhead">
   <div class="cvscore" style="--p:${prob};--sc:${scColor(prob)}"><div class="in"><div class="n num">${prob}%</div><div class="l">colloquio</div></div></div>
   <div style="flex:1;min-width:220px"><div style="font-size:18px;font-weight:600">${esc(d.ruolo||'Compatibilita')}</div>
   <div style="color:var(--mut);font-size:13.5px;margin-top:6px">${esc(demoji(d.verdetto||'Probabilita stimata di essere chiamato per un colloquio.'))}</div>
   <div style="margin-top:10px;display:flex;gap:10px;align-items:center"><span class="tag" style="background:${scColor(match)}22;color:${scColor(match)}">compatibilita ${match}/100</span>${d.fonte?`<a href="${esc(d.fonte)}" target="_blank" rel="noopener" class="fp" style="color:var(--acc);text-decoration:none">${svg('ext')} annuncio</a>`:''}</div>
   </div></div></div></div>`;
  if((d.coperti||[]).length)h+=`<div class="panel" style="margin-bottom:18px"><div class="panel-h">${svg('check')} Requisiti coperti</div><div class="panel-b">${L(d.coperti,x=>`<div class="frow"><div class="fmain"><div class="fn" style="white-space:normal;font-weight:400">${esc(demoji(x))}</div></div><span class="tag g">ok</span></div>`)}</div></div>`;
  if((d.mancanti||[]).length)h+=`<div class="panel" style="margin-bottom:18px"><div class="panel-h">${svg('x')} Da colmare</div><div class="panel-b">${L(d.mancanti,x=>`<div class="frow"><div class="fmain"><div class="fn" style="white-space:normal;font-weight:400">${esc(demoji(x))}</div></div><span class="tag r">gap</span></div>`)}</div></div>`;
  if((d.consigli||[]).length)h+=`<div class="panel" style="margin-bottom:18px"><div class="panel-h">${svg('bulb')} Consigli</div><div class="panel-b">${L(d.consigli,x=>`<div class="frow"><div class="fmain"><div class="fn" style="white-space:normal;font-weight:400">${esc(demoji(x))}</div></div></div>`)}</div></div>`;
  if(d.lettera)h+=`<div class="panel"><div class="panel-h">${svg('send')} Lettera di presentazione<button class="btn" style="margin-left:auto" onclick="dlLetter()">${svg('download')} .txt</button></div><div class="panel-b"><div style="white-space:pre-wrap;line-height:1.6;font-size:14px">${esc(demoji(d.lettera))}</div></div></div>`;
  out.innerHTML=h;
 }catch(e){out.innerHTML='<div class="empty">Errore di rete.</div>';}
}
function dlLetter(){const t=window.__jmletter||'';if(!t)return;
 const b=new Blob([t],{type:'text/plain'});const a=document.createElement('a');a.href=URL.createObjectURL(b);a.download='lettera_presentazione.txt';a.click();}

// ================= Widget desktop =================
RENDER.widget=function(){
 $('#view').innerHTML=`
  <div class="panel" style="margin-bottom:18px"><div class="panel-h">${svg('monitor')} Collegamento sul desktop</div><div class="panel-b">
   <div class="fp" style="white-space:normal;margin-bottom:14px">Metto un'icona <b>miAi</b> sul desktop: un clic avvia il server (se spento) e apre miAi. Non installa nulla, resta tutto in locale.</div>
   <div class="toolbar" style="flex-wrap:wrap">
    <button class="btn pri" id="wgapp" onclick="wgApp()">${svg('monitor')} Apri l'app installata (consigliato)</button>
    <button class="btn" id="wgmk" onclick="wgMake()">${svg('ext')} Apri nel browser</button></div>
   <div class="fp" style="white-space:normal;margin-top:10px;opacity:.8">"App installata" apre la finestra dedicata (serve aver gia installato miAi qui sotto). "Nel browser" apre una scheda normale.</div>
   <div id="wgres" style="margin-top:14px"></div></div></div>

  <div class="panel" style="margin-bottom:18px"><div class="panel-h">${svg('layout')} Installa come app (finestra propria)</div><div class="panel-b">
   <div class="fp" style="white-space:normal;margin-bottom:14px">Installa miAi come app: si apre in una finestra sua (senza barre del browser) con la sua icona, agganciabile alla barra delle applicazioni.</div>
   <button class="btn pri" onclick="wgInstall()">${svg('download')} Installa miAi</button>
   <div class="fp" style="white-space:normal;margin-top:12px;opacity:.85">Se il pulsante non fa nulla: nel menu del browser (tre puntini) &rarr; <b>Installa miAi</b> / "Installa questo sito come app". Da installata puoi trascinarne l'icona sul desktop.</div></div></div>

  <div class="panel"><div class="panel-h">${svg('spark')} Suggerimento</div><div class="panel-b">
   <div class="fp" style="white-space:normal">Per avere miAi sempre pronto all'accensione del PC: premi Win+R, scrivi <b>shell:startup</b>, e trascina li dentro il collegamento creato qui sopra.</div></div></div>`;
};
async function wgShortcut(endpoint,btn){
 const res=$('#wgres');btn.disabled=true;const old=btn.innerHTML;btn.innerHTML='Creo...';
 try{
  const r=await (await fetch(endpoint,{method:'POST',headers:{'Content-Type':'application/json'},body:'{}'})).json();
  if(r.ok){res.innerHTML=`<div class="cgfb ok" style="margin:0"><b>${svg('check')} Collegamento creato</b>Trovi l'icona <b>miAi</b> sul desktop: doppio clic per aprire${r.browser?' (app '+esc(r.browser)+')':''}.<div class="fp" style="margin-top:6px;opacity:.8">${esc(r.path||'')}</div></div>`;}
  else{res.innerHTML=`<div class="cgfb no" style="margin:0"><b>${svg('x')} Non creato</b>${esc(r.err||'errore')}</div>`;}
 }catch(e){res.innerHTML='<div class="cgfb no" style="margin:0">Errore di rete.</div>';}
 btn.disabled=false;btn.innerHTML=old;
}
function wgApp(){wgShortcut('/app-shortcut',$('#wgapp'));}
function wgMake(){wgShortcut('/desktop-shortcut',$('#wgmk'));}
async function wgInstall(){
 if(__pwaPrompt){__pwaPrompt.prompt();try{await __pwaPrompt.userChoice;}catch(e){}__pwaPrompt=null;}
 else{alert('Usa il menu del browser (tre puntini) e scegli "Installa miAi". Se non compare, la pagina potrebbe essere gia installata o aperta come app.');}
}

// ================= Assistente miAi =================
let __chat=[];
RENDER.assistente=function(){
 const chips=['Cosa e successo oggi?','Quali repo mi consigli?','Ci sono minacce che mi riguardano?','Riassumi le mie idee migliori','Come sto messo a spazio disco?'];
 $('#view').innerHTML=`<div class="chatwrap">
   <div class="chatlog" id="chatlog"></div>
   <div class="chatchips">${chips.map(c=>`<span class="tag" onclick="chatSend(this.textContent)">${esc(c)}</span>`).join('')}</div>
   <div class="chatin"><textarea class="inp" id="chatq" placeholder="Chiedi a miAi... (vede i tuoi dati raccolti)" onkeydown="if(event.key==='Enter'&&!event.shiftKey){event.preventDefault();chatSend()}"></textarea>
    <button class="btn pri" onclick="chatSend()">${svg('send')}</button></div></div>`;
 chatDraw();
};
function chatDraw(){const l=$('#chatlog');if(!l)return;
 l.innerHTML=__chat.length?__chat.map(m=>`<div class="msg ${m.r}${m.wait?' wait':''}">${m.html?m.t:esc(demoji(m.t))}</div>`).join('')
  :'<div class="msg a">Ciao! Sono miAi. Ti aiuto con i tuoi dati e posso <b>agire</b>: prova "apri Disco", "aggiungi promemoria comprare il pane", "cambia tema Minecraft", "aggiorna".</div>';
 l.scrollTop=l.scrollHeight;}
function cgAction(q){
 const s=q.toLowerCase().trim();
 // naviga: "apri/vai a/mostra/portami a <sezione>"
 let m=s.match(/^(?:apri|vai a|vai su|mostra(?:mi)?|portami a|apparecchia)\s+(?:la |il |lo |le |i )?(.+)/);
 if(m){const q2=_norm(m[1]);const n=NAV.find(x=>x.id&&(_norm(x.label)===q2||_norm(x.label).includes(q2)||q2.includes(_norm(x.label))));
   if(n){go(n.id);return {nav:true};}}
 // promemoria: "aggiungi promemoria X" / "ricordami di X"
 m=s.match(/^(?:aggiungi|nuovo|crea)\s+(?:un |una |il )?(?:promemoria|impegno|appuntamento|evento)\s+(.+)/)||s.match(/^ricordami(?: di)?\s+(.+)/);
 if(m){const t=q.slice(q.length-m[1].length).trim();const l=agGet();l.push({id:'a'+Date.now(),title:t,date:_agToday(),time:'',done:false});agSave(l);
   return {msg:'Aggiunto all\'agenda di oggi: <b>'+esc(t)+'</b>.'};}
 // task: "aggiungi task X"
 m=s.match(/^(?:aggiungi|nuovo|crea)\s+(?:un |una )?(?:task|attivita|attivita')\s+(.+)/);
 if(m){const t=q.slice(q.length-m[1].length).trim();const pj=projGet();
   if(!pj.length)return {msg:'Prima crea un progetto nella sezione Progetti, poi potro aggiungere task.'};
   const tk=taskGet();tk.push({id:'t'+Date.now(),pj:pj[0].id,title:t,done:false,prio:'media'});taskSave(tk);
   return {msg:'Aggiunto task a <b>'+esc(pj[0].name)+'</b>: '+esc(t)+'.'};}
 // tema: "cambia tema X"
 m=s.match(/^(?:cambia|imposta|metti)\s+(?:il )?tema(?: in| a)?\s+(.+)/);
 if(m){const q2=_norm(m[1]);const th=THEMES.find(x=>_norm(x.label)===q2||_norm(x.label).includes(q2));
   if(th){applyTheme(th.id);return {msg:'Tema cambiato in <b>'+esc(th.label)+'</b>.'};}
   return {msg:'Non trovo un tema con quel nome. Vai in Temi per la lista.'};}
 // ollama/modello on-off
 if(/\b(accendi|avvia|attiva)\b.*\b(ollama|modello|ai)\b/.test(s)){if(!$('#ollama').classList.contains('on'))$('#ollama').click();return {msg:'Sto accendendo il modello locale.'};}
 if(/\b(spegni|ferma|disattiva)\b.*\b(ollama|modello|ai)\b/.test(s)){if($('#ollama').classList.contains('on'))$('#ollama').click();return {msg:'Sto spegnendo il modello locale.'};}
 // aggiorna dati
 if(/^aggiorna(?:\s+i?\s*dati)?\.?$/.test(s)){$('#refresh').click();return {msg:'Aggiornamento dati avviato.'};}
 return null;
}
async function chatSend(txt){
 const q=(txt||($('#chatq')?$('#chatq').value:'')||'').trim();if(!q)return;
 if($('#chatq'))$('#chatq').value='';
 const act=cgAction(q);
 if(act){if(act.nav)return;   // ha cambiato pagina: nulla da mostrare in chat
   __chat.push({r:'u',t:q});__chat.push({r:'a',t:act.msg,html:true});chatDraw();return;}
 __chat.push({r:'u',t:q});__chat.push({r:'a',t:'',wait:true});chatDraw();
 const idx=__chat.length-1;
 try{
  const resp=await fetch('/ask-stream',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({q})});
  if(!resp.ok||!resp.body)throw new Error('nostream');
  const reader=resp.body.getReader(),dec=new TextDecoder();let buf='',acc='';
  for(;;){const {done,value}=await reader.read();if(done)break;
   buf+=dec.decode(value,{stream:true});const parts=buf.split('\n\n');buf=parts.pop();
   for(const p of parts){const dl=p.split('\n').find(x=>x.startsWith('data: '));if(!dl)continue;
    try{const v=JSON.parse(dl.slice(6));if(typeof v==='string'){acc+=v;__chat[idx]={r:'a',t:acc};chatDraw();}else if(v&&v.err){__chat[idx]={r:'a',t:'Errore: '+v.err};}}catch(e){}}}
  if(!acc&&!__chat[idx].t)__chat[idx]={r:'a',t:'(nessuna risposta)'};else if(acc)__chat[idx]={r:'a',t:acc};
 }catch(e){
  // fallback non-streaming
  try{const d=await (await fetch('/ask',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({q})})).json();__chat[idx]={r:'a',t:d.answer||'(nessuna risposta)'};}
  catch(e2){__chat[idx]={r:'a',t:'Errore di rete. Il modello e raggiungibile? (spia in basso a sinistra)'};}
 }
 chatDraw();
}

// ================= Scrittura & traduzione =================
const WMODES=[['correggi','Correggi'],['formale','Rendi formale'],['informale','Rendi informale'],['accorcia','Accorcia'],['allunga','Espandi'],['email','Trasforma in email'],['traduci_en','Traduci in inglese'],['traduci_it','Traduci in italiano']];
RENDER.scrittura=function(){
 $('#view').innerHTML=`<div class="panel"><div class="panel-b">
   <div class="toolbar" style="flex-wrap:wrap;margin-bottom:12px">
     <select class="inp" id="wmode" style="max-width:220px">${WMODES.map(m=>`<option value="${m[0]}">${esc(m[1])}</option>`).join('')}</select>
     <button class="btn pri" onclick="wrGo()">${svg('pen')} Elabora</button></div>
   <textarea class="cginp" id="wtext" rows="7" placeholder="Incolla o scrivi qui il testo (email, messaggio, paragrafo del CV...)"></textarea>
   <div id="wrout" style="margin-top:16px"></div></div></div>`;
};
async function wrGo(){
 const text=($('#wtext').value||'').trim(),mode=$('#wmode').value,out=$('#wrout');
 if(text.length<3){out.innerHTML='<div class="empty">Scrivi qualcosa da elaborare.</div>';return;}
 out.innerHTML='<div class="dwait">miAi sta elaborando...</div>';
 try{
  const d=await (await fetch('/rewrite',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({text,mode})})).json();
  if(d.error){out.innerHTML=`<div class="empty">${esc(d.error)}<br><br>Serve Ollama acceso.</div>`;return;}
  window.__wrout=d.out||'';
  out.innerHTML=`<div class="panel" style="margin:0"><div class="panel-h">${svg('check')} Risultato<button class="btn" style="margin-left:auto" onclick="wrCopy(this)">${svg('doc')} Copia</button></div>
   <div class="panel-b"><div style="white-space:pre-wrap;line-height:1.6;font-size:14px">${esc(demoji(d.out||''))}</div></div></div>`;
 }catch(e){out.innerHTML='<div class="empty">Errore di rete.</div>';}
}
function wrCopy(btn){const t=window.__wrout||'';(navigator.clipboard?navigator.clipboard.writeText(t):Promise.reject()).then(()=>{const o=btn.innerHTML;btn.textContent='copiato';setTimeout(()=>btn.innerHTML=o,1400);}).catch(()=>{prompt('Copia il testo:',t);});}

// ================= Agenda & promemoria =================
function _ymd(d){return d.getFullYear()+'-'+String(d.getMonth()+1).padStart(2,'0')+'-'+String(d.getDate()).padStart(2,'0');}
const _agToday=()=>_ymd(new Date());          // data LOCALE (niente shift UTC)
function _agM(){return window.__agMonth||_agToday().slice(0,7);}
function agGet(){return LS.get('agenda',[]);}
function agSave(l){LS.set('agenda',l);}
RENDER.agenda=function(){
 const l=agGet(),today=_agToday(),sel=window.__agSel||today;
 const pend=l.filter(x=>!x.done);
 const in7=_ymd(new Date(Date.now()+7*864e5));
 const K=[{k:'Da fare',v:pend.length,cls:'a'},{k:'Oggi',v:pend.filter(x=>x.date===today).length,cls:'am'},{k:'Prossimi 7 giorni',v:pend.filter(x=>x.date>today&&x.date<=in7).length},{k:'Scadute',v:pend.filter(x=>x.date<today).length}];
 let h=kpis(K)+`<div class="panel" style="margin-top:18px"><div class="panel-b">
   <div class="toolbar" style="flex-wrap:wrap">
     <input class="inp" id="agt" placeholder="Cosa? (es. Appuntamento dentista)" style="flex:1;min-width:200px" onkeydown="if(event.key==='Enter')agAdd()">
     <input class="inp" id="agd" type="date" value="${sel}" style="max-width:170px">
     <input class="inp" id="agh" type="time" style="max-width:130px">
     <button class="btn pri" onclick="agAdd()">${svg('plus')} Aggiungi</button></div>
   <div class="fp" style="margin-top:8px">Suggerimento: clicca un giorno del calendario per scegliere la data.</div></div></div>`;
 h+=`<div class="panel" style="margin-top:18px"><div class="panel-b">${agCalendar(_agM(),l,today,sel)}</div></div>`;
 const up=pend.slice().sort((a,b)=>(a.date+(a.time||'')).localeCompare(b.date+(b.time||'')));
 if(up.length){
  h+=`<div class="panel" style="margin-top:18px"><div class="panel-h">${svg('calendar')} In arrivo <span class="cnt num">${up.length}</span></div><div class="panel-b">${up.map(it=>{const late=it.date<today;
   return `<div class="agrow ${it.done?'done':''} ${late?'late':''}"><button class="agck" onclick="agToggle('${it.id}')">${svg('check')}</button>
    <div class="agmain"><div class="agt">${esc(demoji(it.title))}</div><div class="agd">${esc(agFmt(it.date))}${it.time?' &middot; '+esc(it.time):''}${late?' &middot; scaduta':''}</div></div>
    <button class="agdel" title="rimuovi" onclick="agDel('${it.id}')">${svg('x')}</button></div>`;}).join('')}</div></div>`;
 }
 $('#view').innerHTML=h;
};
function agCalendar(ym,list,today,sel){
 const Y=+ym.slice(0,4),M=+ym.slice(5,7);
 const first=new Date(Y,M-1,1);
 const off=(first.getDay()+6)%7;                // lunedi = primo giorno
 const start=new Date(Y,M-1,1-off);
 const label=first.toLocaleDateString('it-IT',{month:'long',year:'numeric'});
 const WD=['Lun','Mar','Mer','Gio','Ven','Sab','Dom'];
 const byd={};list.forEach(e=>{(byd[e.date]=byd[e.date]||[]).push(e);});
 let cells='';
 for(let i=0;i<42;i++){
  const d=new Date(start);d.setDate(start.getDate()+i);const ds=_ymd(d);
  const offM=(d.getMonth()!==M-1);const evs=byd[ds]||[];
  const chips=evs.slice(0,3).map(e=>`<div class="calev ${e.done?'done':(ds<today?'late':'')}" title="${escA(demoji(e.title))}" onclick="event.stopPropagation();agToggle('${e.id}')">${esc(demoji(e.title))}</div>`).join('')+(evs.length>3?`<div class="calmore">+${evs.length-3} altri</div>`:'');
  cells+=`<div class="calcell ${offM?'off':''} ${ds===today?'today':''} ${ds===sel?'sel':''}" data-d="${ds}" data-n="${evs.length||''}" onclick="agPick('${ds}')"><span class="calnum">${d.getDate()}</span>${chips}</div>`;
 }
 return `<div class="calbar"><button class="calnav" onclick="agNav(-1)" title="mese precedente">&#8249;</button><b>${esc(label)}</b><button class="btn" onclick="agNav(0)">Oggi</button><button class="calnav" onclick="agNav(1)" title="mese successivo">&#8250;</button></div>
  <div class="calwk">${WD.map(w=>`<span>${w}</span>`).join('')}</div><div class="calgrid">${cells}</div>`;
}
function agNav(delta){
 if(delta===0){window.__agMonth=_agToday().slice(0,7);window.__agSel=_agToday();}
 else{const Y=+_agM().slice(0,4),M=+_agM().slice(5,7);window.__agMonth=_ymd(new Date(Y,M-1+delta,1)).slice(0,7);}
 RENDER.agenda('agenda');}
function agPick(ds){window.__agSel=ds;const inp=$('#agd');if(inp)inp.value=ds;
 document.querySelectorAll('.calcell.sel').forEach(e=>e.classList.remove('sel'));
 const c=document.querySelector('.calcell[data-d="'+ds+'"]');if(c)c.classList.add('sel');
 const t=$('#agt');if(t)t.focus();}
function agFmt(d){try{return new Date(d+'T00:00').toLocaleDateString('it-IT',{weekday:'short',day:'numeric',month:'long'});}catch(e){return d;}}
function agAdd(){const t=($('#agt').value||'').trim(),d=$('#agd').value,h=$('#agh').value;
 if(!t||!d){return;}
 window.__agSel=d;window.__agMonth=d.slice(0,7);
 const l=agGet();l.push({id:'a'+Date.now(),title:t,date:d,time:h||'',done:false});agSave(l);RENDER.agenda('agenda');}
function agToggle(id){const l=agGet();const it=l.find(x=>x.id===id);if(it)it.done=!it.done;agSave(l);RENDER.agenda('agenda');}
function agDel(id){agSave(agGet().filter(x=>x.id!==id));RENDER.agenda('agenda');}

// ================= Progetti & Task =================
function projGet(){return LS.get('projects',[]);}
function projSave(l){LS.set('projects',l);}
function taskGet(){return LS.get('tasks',[]);}
function taskSave(l){LS.set('tasks',l);}
const PJSTATUS=[['attivo','a'],['pausa','am'],['completato','g']];
const PJSUGG=['App web','Sito portfolio','Bot Telegram','Script di automazione','App mobile','Tesi'];
function pjProg(pid){const t=taskGet().filter(x=>x.pj===pid);const d=t.filter(x=>x.done).length;return{d,n:t.length,pct:t.length?Math.round(d/t.length*100):0};}
RENDER.progetti=function(){
 const pj=projGet();
 const attivi=pj.filter(p=>p.status!=='completato').length;
 const tk=taskGet();const K=[{k:'Progetti',v:pj.length,cls:'a'},{k:'Attivi',v:attivi,cls:'am'},{k:'Task aperti',v:tk.filter(x=>!x.done).length},{k:'Task fatti',v:tk.filter(x=>x.done).length,cls:'g'}];
 let h=kpis(K)+`<div class="panel" style="margin-top:18px"><div class="panel-b">
   <div class="toolbar" style="flex-wrap:wrap"><input class="inp" id="pjn" placeholder="Nome progetto" style="flex:1;min-width:180px">
    <input class="inp" id="pjd" placeholder="Descrizione (opzionale)" style="flex:2;min-width:180px">
    <button class="btn pri" onclick="pjAdd()">${svg('plus')} Aggiungi</button></div>`;
 if(!pj.length)h+=`<div class="chatchips" style="margin-top:12px">${PJSUGG.map(s=>`<span class="tag" onclick="pjAdd('${esc(s)}')">${svg('plus')} ${esc(s)}</span>`).join('')}</div>`;
 h+='</div></div>';
 if(pj.length){
  h+='<div class="pjgrid">'+pj.map(p=>{const pr=pjProg(p.id);const st=PJSTATUS.find(s=>s[0]===p.status)||PJSTATUS[0];
   const tks=taskGet().filter(x=>x.pj===p.id);
   return `<div class="pjcard ${p.status==='completato'?'done':''}">
    <div class="pjact"><button title="stato" onclick="pjCycle('${p.id}')">${svg('spark')}</button><button title="elimina" onclick="pjDel('${p.id}')">${svg('x')}</button></div>
    <div class="pjh"><span class="tag ${st[1]}">${esc(st[0])}</span><b>${esc(demoji(p.name))}</b></div>
    ${p.desc?`<div class="pjdesc">${esc(demoji(p.desc))}</div>`:''}
    <div class="pjbar"><i style="width:${pr.pct}%"></i></div>
    <div class="pjmeta"><span>${pr.d}/${pr.n} task</span><span>${pr.pct}%</span></div>
    <div class="pjtasks">${tks.length?tks.map(t=>`<div class="pjtask ${t.done?'done':''}"><button class="agck" onclick="tkToggle('${t.id}')">${svg('check')}</button><span>${esc(demoji(t.title))}</span></div>`).join(''):'<div class="pjp" style="color:var(--faint);font-size:12.5px">Nessun task. Aggiungine uno.</div>'}
     <div class="pjadd"><input class="inp" id="pjt-${p.id}" placeholder="Nuovo task..." onkeydown="if(event.key==='Enter')pjAddTask('${p.id}')" style="flex:1"><button class="btn" onclick="pjAddTask('${p.id}')">${svg('plus')}</button></div></div>
   </div>`;}).join('')+'</div>';
 }else h+='<div class="empty" style="margin-top:18px">Nessun progetto. Aggiungine uno qui sopra o scegli tra i suggeriti.</div>';
 $('#view').innerHTML=h;
};
function pjAdd(name){const n=(name||($('#pjn')?$('#pjn').value:'')||'').trim();if(!n)return;
 const d=(!name&&$('#pjd'))?$('#pjd').value.trim():'';
 const l=projGet();l.push({id:'p'+Date.now(),name:n,desc:d,status:'attivo'});projSave(l);RENDER.progetti('progetti');}
function pjDel(id){if(!confirm('Eliminare il progetto e i suoi task?'))return;
 projSave(projGet().filter(p=>p.id!==id));taskSave(taskGet().filter(t=>t.pj!==id));RENDER.progetti('progetti');}
function pjCycle(id){const l=projGet();const p=l.find(x=>x.id===id);if(!p)return;
 const i=PJSTATUS.findIndex(s=>s[0]===p.status);p.status=PJSTATUS[(i+1)%PJSTATUS.length][0];projSave(l);RENDER.progetti('progetti');}
function pjAddTask(pid){const inp=$('#pjt-'+pid);const t=(inp?inp.value:'').trim();if(!t)return;
 const l=taskGet();l.push({id:'t'+Date.now(),pj:pid,title:t,done:false,prio:'media'});taskSave(l);RENDER.progetti('progetti');}
function tkToggle(id){const l=taskGet();const t=l.find(x=>x.id===id);if(t)t.done=!t.done;taskSave(l);
 (cur==='task'?RENDER.task:RENDER.progetti)(cur);}

RENDER.task=function(){
 const pj=projGet();const flt=window.__tkFilter||'';const fp=window.__tkPrio||'';
 let tk=taskGet().slice();
 if(flt)tk=tk.filter(t=>t.pj===flt);
 if(fp)tk=tk.filter(t=>(t.prio||'media')===fp);
 tk.sort((a,b)=>(a.done-b.done)||({alta:0,media:1,bassa:2}[a.prio]-{alta:0,media:1,bassa:2}[b.prio]));
 const pjName=id=>{const p=pj.find(x=>x.id===id);return p?p.name:'(senza progetto)';};
 const K=[{k:'Task totali',v:taskGet().length,cls:'a'},{k:'Da fare',v:taskGet().filter(x=>!x.done).length,cls:'am'},{k:'Fatti',v:taskGet().filter(x=>x.done).length,cls:'g'}];
 let h=kpis(K)+`<div class="panel" style="margin-top:18px"><div class="panel-b">
   <div class="toolbar" style="flex-wrap:wrap">
    <input class="inp" id="tkt" placeholder="Nuovo task" style="flex:1;min-width:180px">
    <select class="inp" id="tkpj" style="max-width:190px">${pj.length?pj.map(p=>`<option value="${p.id}">${esc(p.name)}</option>`).join(''):'<option value="">(crea prima un progetto)</option>'}</select>
    <select class="inp" id="tkprio" style="max-width:130px"><option value="alta">Alta</option><option value="media" selected>Media</option><option value="bassa">Bassa</option></select>
    <button class="btn pri" onclick="tkAdd()">${svg('plus')} Aggiungi</button></div>
   ${pj.length?`<div class="chatchips" style="margin-top:10px"><span class="tag ${flt?'':'acc'}" onclick="tkSetFilter('')">Tutti</span>${pj.map(p=>`<span class="tag ${flt===p.id?'acc':''}" onclick="tkSetFilter('${p.id}')">${esc(p.name)}</span>`).join('')}</div>`:''}
   <div class="chatchips" style="margin-top:8px"><span class="fp" style="align-self:center;margin-right:2px">Priorita:</span>
    <span class="tag ${fp?'':'acc'}" onclick="tkSetPrio('')">Tutte</span>
    ${[['alta','Alta'],['media','Media'],['bassa','Bassa']].map(p=>`<span class="tag ${fp===p[0]?'acc':''}" onclick="tkSetPrio('${p[0]}')"><span class="prio ${p[0]}" style="display:inline-block;margin-right:5px;vertical-align:middle"></span>${p[1]}</span>`).join('')}</div>
   </div></div>`;
 if(tk.length){
  h+=`<div class="panel" style="margin-top:18px"><div class="panel-b">${tk.map(t=>`<div class="tkrow ${t.done?'done':''}">
    <button class="agck" onclick="tkToggle('${t.id}')">${svg('check')}</button>
    <button class="priobtn" onclick="tkCyclePrio('${t.id}')" title="priorita ${t.prio||'media'} - clicca per cambiare"><span class="prio ${t.prio||'media'}"></span></button>
    <div class="tkmain"><div class="tkt">${esc(demoji(t.title))}</div><div class="tkp">${svg('folder')} ${esc(pjName(t.pj))}</div></div>
    <button class="agdel" title="rimuovi" onclick="tkDel('${t.id}')">${svg('x')}</button></div>`).join('')}</div></div>`;
 }else h+='<div class="empty" style="margin-top:18px">Nessun task. Aggiungine uno e collegalo a un progetto.</div>';
 $('#view').innerHTML=h;
};
function tkSetFilter(id){window.__tkFilter=id;RENDER.task('task');}
function tkSetPrio(p){window.__tkPrio=p;RENDER.task('task');}
function tkCyclePrio(id){const order=['alta','media','bassa'];const l=taskGet();const t=l.find(x=>x.id===id);
 if(!t)return;t.prio=order[(order.indexOf(t.prio||'media')+1)%3];taskSave(l);RENDER.task('task');}
function tkAdd(){const t=($('#tkt').value||'').trim(),pj=$('#tkpj').value,prio=$('#tkprio').value;
 if(!t||!pj){if(!pj)alert('Crea prima un progetto nella sezione Progetti.');return;}
 const l=taskGet();l.push({id:'t'+Date.now(),pj,title:t,done:false,prio});taskSave(l);RENDER.task('task');}
function tkDel(id){taskSave(taskGet().filter(t=>t.id!==id));RENDER.task('task');}

// ================= Temi (pagina) =================
RENDER.temi=function(){
 $('#view').innerHTML=`<div class="thgrid">${THEMES.map(t=>{
  const bg=t.dots[0],ac=t.dots[1],tx=t.dots[2];
  return `<div class="thcard ${theme===t.id?'on':''}" onclick="applyTheme('${t.id}');RENDER.temi('temi')">
   <div class="thprev" style="background:${bg}">
    <div class="bar" style="background:${ac};width:58%"></div>
    <div class="row"><span class="dot" style="background:${ac}"></span><span class="mini" style="background:${tx};opacity:.16"></span></div>
    <div class="bar" style="background:${tx};opacity:.1;width:82%"></div></div>
   <div class="thmeta"><b>${esc(t.label)}</b>${t.tag?`<span class="tag">${esc(t.tag)}</span>`:''}<span class="chk">${svg('check')}</span></div>
  </div>`;}).join('')}</div>`;
};

// ================= Impostazioni (sezioni visibili) =================
RENDER.impostazioni=function(){
 const on=LS.get('sections_on',{})||{};
 const items=NAV.filter(n=>n.id&&!SEC_LOCKED.includes(n.id));
 let h=`<div class="panel"><div class="panel-h">${svg('settings')} Sezioni visibili <span class="fp" style="margin-left:auto;font-weight:400">Scegli cosa mostrare nel menu</span></div><div class="panel-b">`;
 h+=items.map(n=>{const vis=on[n.id]!==false;
   return `<div class="setrow"><span class="sic">${svg(n.icon)}</span><div class="sm"><b>${esc(n.label)}</b><div>${esc(n.desc||'')}</div></div><div class="sw ${vis?'on':''}" onclick="secToggle('${n.id}',this)"></div></div>`;}).join('');
 h+=`</div></div><div class="panel" style="margin-top:16px"><div class="panel-b"><div class="toolbar" style="flex-wrap:wrap">
   <button class="btn" onclick="secAll()">Attiva tutte</button>
   <button class="btn" onclick="showOnboarding()">${svg('settings')} Rivedi la scelta iniziale</button></div>
   <div class="fp" style="margin-top:10px">Oggi, Temi e Impostazioni restano sempre visibili.</div></div></div>`;
 h+=`<div class="panel" style="margin-top:16px"><div class="panel-h">${svg('lock')} Blocco con PIN</div><div class="panel-b">
   <div class="fp" style="white-space:normal;margin-bottom:12px">Proteggi l'apertura di miAi con un PIN (min 4 caratteri). Applicato dal server: senza PIN i dati non si aprono. Se lo dimentichi, elimina il file <b>pin.json</b> nella cartella di miAi.</div>
   <div id="pinstate" class="fp" style="margin-bottom:10px">...</div>
   <div class="toolbar" style="flex-wrap:wrap">
     <input class="inp" id="pin-new" type="password" inputmode="numeric" placeholder="Nuovo PIN" style="max-width:200px" autocomplete="new-password">
     <button class="btn pri" onclick="pinSave()">${svg('check')} Imposta PIN</button>
     <button class="btn" id="pin-off" onclick="pinRemove()" style="display:none">Rimuovi PIN</button>
     <button class="btn" id="pin-lock" onclick="pinLockNow()" style="display:none">${svg('lock')} Blocca ora</button></div>
   <div id="pin-res" style="margin-top:10px"></div>
   <div class="fld" style="margin-top:16px;max-width:320px"><label>Blocco automatico dopo inattivita</label>
     <select class="inp" onchange="LS.set('autolock_min',+this.value);armAutolock()">
       ${[[0,'Mai'],[1,'1 minuto'],[5,'5 minuti'],[15,'15 minuti'],[30,'30 minuti'],[60,'1 ora']].map(o=>`<option value="${o[0]}" ${(+LS.get('autolock_min',0))===o[0]?'selected':''}>${o[1]}</option>`).join('')}</select></div>
   <div class="fp" style="margin-top:6px">Con il PIN attivo, dopo il tempo scelto miAi si riblocca. Anche i dati salvati (store) sono cifrati a riposo con una chiave derivata dal PIN.</div>
   </div></div>
  <div class="panel" style="margin-top:16px"><div class="panel-h">${svg('download')} Dati e backup</div><div class="panel-b">
   <div class="fp" style="white-space:normal;margin-bottom:12px">Esporta tutti i tuoi dati personali (preferiti, agenda, progetti, CV, impostazioni) in un file, o ripristinali su questo o un altro PC. Il file resta sul tuo computer.</div>
   <div class="toolbar" style="flex-wrap:wrap"><button class="btn pri" onclick="dataExport()">${svg('download')} Esporta i miei dati</button>
     <button class="btn" onclick="$('#imp-file').click()">${svg('doc')} Importa da file</button>
     <input type="file" id="imp-file" accept="application/json,.json" hidden onchange="dataImport(this.files[0])"></div>
   <div id="imp-res" style="margin-top:10px"></div></div></div>`;
 h+=`<div class="panel" style="margin-top:16px"><div class="panel-h">${svg('cpu')} Server e avvio</div><div class="panel-b">
   <div class="fp" style="white-space:normal;margin-bottom:12px">Il server locale di miAi gira in background sul tuo PC (nessun dato esce). Qui lo gestisci senza toccare il Desktop.</div>
   <div class="setrow"><span class="sic">${svg('activity')}</span><div class="sm"><b>Avvia miAi all'accensione del PC</b><div>Cosi il server e sempre pronto e la app si apre senza pensieri.</div></div><div class="sw" id="autostart-sw" onclick="autostartToggle(this)"></div></div>
   <div class="toolbar" style="flex-wrap:wrap;margin-top:12px"><button class="btn" onclick="serverRestart()">${svg('refresh')} Riavvia server</button></div>
   <div id="srv-res" style="margin-top:10px"></div></div></div>`;
 $('#view').innerHTML=h;
 fetch('/autostart').then(r=>r.json()).then(a=>{const sw=$('#autostart-sw');if(sw)sw.classList.toggle('on',!!a.on);}).catch(()=>{});
 fetch('/auth-status').then(r=>r.json()).then(a=>{const st=$('#pinstate');if(!st)return;
   st.innerHTML=a.locked?'<b style="color:var(--green)">PIN attivo.</b> miAi chiede il PIN all\'apertura.':'PIN non impostato: miAi si apre senza blocco.';
   const off=$('#pin-off'),lk=$('#pin-lock');if(off)off.style.display=a.locked?'':'none';if(lk)lk.style.display=a.locked?'':'none';}).catch(()=>{});
};
async function pinSave(){const pin=($('#pin-new')||{}).value||'';const res=$('#pin-res');
 if(pin.length<4){res.innerHTML='<div class="cgfb no" style="margin:0">Il PIN deve avere almeno 4 caratteri.</div>';return;}
 try{const r=await (await fetch('/set-pin',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({pin})})).json();
  res.innerHTML=r.ok?'<div class="cgfb ok" style="margin:0"><b>PIN impostato.</b> Verra chiesto alla prossima apertura.</div>':`<div class="cgfb no" style="margin:0">${esc(r.err||'errore')}</div>`;
  if(r.ok)RENDER.impostazioni('impostazioni');}
 catch(e){res.innerHTML='<div class="cgfb no" style="margin:0">Errore di rete.</div>';}}
async function pinRemove(){if(!confirm('Rimuovere il PIN? miAi si aprira senza blocco.'))return;
 try{await fetch('/set-pin',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({pin:''})});RENDER.impostazioni('impostazioni');}catch(e){}}
async function pinLockNow(){try{await fetch('/lock',{method:'POST',headers:{'Content-Type':'application/json'},body:'{}'});location.reload();}catch(e){}}
async function autostartToggle(sw){const on=!sw.classList.contains('on');
 try{const r=await (await fetch('/autostart',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({on})})).json();
  if(r.ok){sw.classList.toggle('on',r.on);$('#srv-res').innerHTML=`<div class="cgfb ok" style="margin:0">${r.on?'Avvio automatico attivato.':'Avvio automatico disattivato.'}</div>`;}
  else $('#srv-res').innerHTML=`<div class="cgfb no" style="margin:0">${esc(r.err||'errore')}</div>`;}
 catch(e){$('#srv-res').innerHTML='<div class="cgfb no" style="margin:0">Errore di rete.</div>';}}
async function serverRestart(){if(!confirm('Riavviare il server? La app si ricarica tra pochi secondi.'))return;
 $('#srv-res').innerHTML='<div class="dwait">Riavvio il server...</div>';
 try{await fetch('/server-restart',{method:'POST',headers:{'Content-Type':'application/json'},body:'{}'});}catch(e){}
 setTimeout(()=>location.reload(),3000);}
function dataExport(){const o={};PERSIST.forEach(k=>{const v=localStorage.getItem(k);if(v!=null)o[k]=v;});
 // includi anche i log nutrizione (nutri_YYYY-MM-DD)
 for(let i=0;i<localStorage.length;i++){const k=localStorage.key(i);if(k.indexOf('nutri_')===0)o[k]=localStorage.getItem(k);}
 const blob=new Blob([JSON.stringify({miai_backup:1,date:new Date().toISOString(),data:o},null,1)],{type:'application/json'});
 const a=document.createElement('a');a.href=URL.createObjectURL(blob);a.download='miai-backup-'+new Date().toISOString().slice(0,10)+'.json';a.click();}
async function dataImport(file){const res=$('#imp-res');if(!file)return;
 if(!confirm('Importare i dati dal file? Sovrascrivera i dati attuali con quelli del backup.'))return;
 try{const txt=await file.text();const j=JSON.parse(txt);const d=j.data||j;
  if(!d||typeof d!=='object'){res.innerHTML='<div class="cgfb no" style="margin:0">File non valido.</div>';return;}
  let n=0;for(const k in d){if(typeof d[k]==='string'){localStorage.setItem(k,d[k]);n++;}}
  pushStore();res.innerHTML=`<div class="cgfb ok" style="margin:0"><b>Importati ${n} elementi.</b> Ricarico...</div>`;
  setTimeout(()=>location.reload(),900);}
 catch(e){res.innerHTML='<div class="cgfb no" style="margin:0">Errore nella lettura del file.</div>';}}
function secToggle(id,elm){const on=LS.get('sections_on',{})||{};const vis=on[id]!==false;on[id]=!vis;LS.set('sections_on',on);elm.classList.toggle('on',!vis);buildNav();}
function secAll(){const on={};NAV.forEach(n=>{if(n.id)on[n.id]=true;});LS.set('sections_on',on);buildNav();RENDER.impostazioni('impostazioni');}

// ================= Modello AI (backend configurabile) =================
RENDER.modello=async function(){
 const v=$('#view');v.innerHTML='<div class="dwait">Leggo la configurazione...</div>';
 let c;try{c=await (await fetch('/llm-config')).json();}catch(e){v.innerHTML='<div class="empty">Impossibile leggere la configurazione.</div>';return;}
 const models=(c.models||[]);
 const modelField=models.length
   ? `<select class="inp" id="lm-model">${models.map(m=>`<option ${m===c.model?'selected':''}>${esc(m)}</option>`).join('')}${models.includes(c.model)?'':`<option selected>${esc(c.model)}</option>`}</select>`
   : `<input class="inp" id="lm-model" value="${escA(c.model)}" placeholder="nome del modello">`;
 v.innerHTML=`
  <div class="panel" style="margin-bottom:16px"><div class="panel-b" style="display:flex;align-items:center;gap:12px">
   <span class="dot" style="width:12px;height:12px;border-radius:50%;background:${c.online?'var(--green)':'var(--red)'};box-shadow:0 0 0 4px ${c.online?'var(--green-soft)':'var(--red-soft)'}"></span>
   <div style="flex:1"><b>${c.online?'Backend raggiungibile':'Backend non raggiungibile'}</b>
    <div class="fp">${esc(c.provider)} &middot; ${esc(c.model)} &middot; ${c.local?'in locale (i dati restano sul PC)':'remoto'}</div></div></div></div>

  <div class="panel"><div class="panel-h">${svg('spark')} Configura il modello</div><div class="panel-b">
   <div class="fld" style="margin-bottom:14px"><label>Tipo di backend</label>
    <select class="inp" id="lm-prov" style="max-width:360px" onchange="lmProv(this.value)">
     <option value="ollama" ${c.provider==='ollama'?'selected':''}>Ollama (locale, consigliato)</option>
     <option value="openai" ${c.provider==='openai'?'selected':''}>Endpoint OpenAI-compatibile (LM Studio, llama.cpp, vLLM, API)</option></select></div>
   <div class="fld" style="margin-bottom:14px"><label>Indirizzo del server (base URL)</label>
    <input class="inp" id="lm-base" value="${escA(c.base)}" style="max-width:420px" placeholder="http://127.0.0.1:11434"></div>
   <div class="fld" style="margin-bottom:14px"><label>Modello</label>${modelField}</div>
   <div class="fld" style="margin-bottom:14px"><label>Lingua delle risposte AI (l'interfaccia resta in italiano)</label>
    <select class="inp" id="lm-lang" style="max-width:280px">${(c.langs||[]).map(l=>`<option value="${l.code}" ${c.lang===l.code?'selected':''}>${esc(l.name)}</option>`).join('')}</select></div>
   <div class="fld" id="lm-keywrap" style="margin-bottom:14px;display:${c.provider==='openai'?'flex':'none'}"><label>API key (se richiesta)</label>
    <input class="inp" id="lm-key" type="password" style="max-width:420px" placeholder="${c.has_key?'(salvata) lascia vuoto per non cambiarla':'sk-...'}"></div>
   <div id="lm-warn" class="cgfb no" style="margin:0 0 14px;display:${c.local?'none':'block'}"><b>${svg('x')} Attenzione privacy</b>Con un backend remoto i tuoi prompt (CV, testi, dati) ESCONO dal PC verso quel server. Per restare 100% locale usa Ollama o un endpoint su 127.0.0.1.</div>
   <div style="display:flex;gap:10px;flex-wrap:wrap"><button class="btn pri" onclick="lmSave()">${svg('check')} Salva</button>
    <button class="btn" onclick="RENDER.modello('modello')">Ricarica</button></div>
   <div id="lm-res" style="margin-top:12px"></div>
   <div class="fp" style="margin-top:14px;white-space:normal">Suggerimento: se il tuo PC regge modelli piu grandi, scaricali con <b>ollama pull</b> (es. qwen2.5:7b) e selezionali qui. Un PC potente puo usare modelli migliori; uno leggero resta su un 3b.</div>
  </div></div>`;
};
function lmProv(p){$('#lm-keywrap').style.display=(p==='openai')?'flex':'none';
 const local=(p==='ollama')||/127\.0\.0\.1|localhost/.test($('#lm-base').value||'');
 $('#lm-warn').style.display=local?'none':'block';
 if(p==='openai'&&/11434/.test($('#lm-base').value||''))$('#lm-base').value='http://127.0.0.1:1234';}
async function lmSave(){
 const body={provider:$('#lm-prov').value,base:$('#lm-base').value.trim(),model:$('#lm-model').value.trim(),lang:$('#lm-lang').value};
 const k=$('#lm-key');if(k&&k.value)body.key=k.value;
 const res=$('#lm-res');res.innerHTML='<div class="dwait">Salvo e verifico...</div>';
 try{const r=await (await fetch('/llm-config',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)})).json();
  res.innerHTML=`<div class="cgfb ${r.online?'ok':'no'}" style="margin:0"><b>${svg(r.online?'check':'x')} Salvato: ${esc(r.model)}</b>${r.online?'Backend raggiungibile.':'Attenzione: il backend non risponde a questo indirizzo. Controlla che sia acceso.'}</div>`;
  ollamaStatus();
  if(body.lang&&body.lang!==__lang){setLang(body.lang);}
 }catch(e){res.innerHTML='<div class="cgfb no" style="margin:0">Errore di rete.</div>';}
}

// ================= Onboarding (prima installazione) =================
async function showOnboarding(){
 const ov=$('#onbov');const on=LS.get('sections_on',{})||{};
 ov.classList.add('on');ov.innerHTML='<div class="onbcard"><div class="dwait">Preparo il primo avvio...</div></div>';
 let body='<div class="onbgrp">Sezioni del menu</div>';
 NAV.forEach(n=>{
  if(n.g){body+=`<div class="onbgrp">${esc(n.g)}</div>`;return;}
  if(SEC_LOCKED.includes(n.id))return;
  const vis=on[n.id]!==false;
  body+=`<div class="onbsec ${vis?'on':''}" data-id="${n.id}" onclick="this.classList.toggle('on')"><span class="cb">${svg('check')}</span><span class="oi">${svg(n.icon)}</span><div><b style="font-size:14px">${esc(n.label)}</b></div></div>`;
 });
 // argomenti del Giornale (dal catalogo del server)
 try{const d=await (await fetch('/topics')).json();const foll=new Set(d.followed||[]);const cats={};
  (d.catalog||[]).forEach(t=>{(cats[t.cat]=cats[t.cat]||[]).push(t);});
  body+='<div class="onbgrp" style="margin-top:20px">Argomenti del Giornale (notizie che vuoi seguire)</div>';
  Object.keys(cats).forEach(c=>{body+=`<div class="onbgrp" style="opacity:.7">${esc(c)}</div>`;
   cats[c].forEach(t=>{body+=`<div class="onbsec ${foll.has(t.id)?'on':''}" data-kind="topic" data-id="${t.id}" onclick="this.classList.toggle('on')"><span class="cb">${svg('check')}</span><div><b style="font-size:14px">${esc(t.label)}</b></div></div>`;});});
 }catch(e){}
 ov.innerHTML=`<div class="onbcard"><h2>Benvenuto in miAi</h2><div class="sub">Personalizza miAi: scegli le sezioni del menu e gli argomenti di notizie che vuoi seguire. Puoi cambiare tutto quando vuoi.</div>
  ${body}<div style="display:flex;gap:10px;justify-content:flex-end;margin-top:18px;position:sticky;bottom:-28px;background:var(--panel);padding:12px 0"><button class="btn" onclick="onbAll()">Seleziona sezioni</button><button class="btn pri" onclick="onbSave()">${svg('check')} Entra in miAi</button></div></div>`;
}
function onbAll(){document.querySelectorAll('#onbov .onbsec:not([data-kind])').forEach(e=>e.classList.add('on'));}
async function onbSave(){const ov=$('#onbov');const on={};const topics=[];
 ov.querySelectorAll('.onbsec').forEach(e=>{
  if(e.dataset.kind==='topic'){if(e.classList.contains('on'))topics.push(e.dataset.id);}
  else on[e.dataset.id]=e.classList.contains('on');});
 LS.set('sections_on',on);LS.set('onboarded',true);ov.classList.remove('on');buildNav();
 __newsData=null;
 try{await fetch('/topics',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({followed:topics})});}catch(e){}
 go('oggi');}

// ================= Command palette (Ctrl+K) =================
const ACTIONS=[
 {t:'Accendi / spegni Ollama',s:'azione',ic:'spark',run:()=>$('#ollama').click()},
 {t:'Aggiorna i dati',s:'azione',ic:'chart',run:()=>$('#refresh').click()},
 {t:'Genera un\'idea (swipe)',s:'azione',ic:'bulb',run:()=>{go('idee');ideeMode='scopri';RENDER.idee('idee');}},
 {t:'Cambia tema',s:'azione',ic:'sun',run:()=>$('#theme').click()}];
let cmdSel=0,cmdList=[];
function cmdItems(q){
 q=q.toLowerCase();const out=[];
 NAV.forEach(n=>{if(n.id&&(!q||n.label.toLowerCase().includes(q)||(n.desc||'').toLowerCase().includes(q)))out.push({t:n.label,s:'sezione',ic:n.icon,run:()=>go(n.id)});});
 ACTIONS.forEach(a=>{if(!q||a.t.toLowerCase().includes(q))out.push(a);});
 if(q){
  P.github.filter(r=>r.full_name.toLowerCase().includes(q)).slice(0,5).forEach(r=>out.push({t:r.full_name,s:'repo',ic:'github',run:()=>window.open(r.url,'_blank')}));
  P.idee.filter(r=>(r.titolo||'').toLowerCase().includes(q)).slice(0,5).forEach(r=>out.push({t:r.titolo,s:'idea',ic:'bulb',run:()=>go('idee')}));
 }
 return out.slice(0,40);
}
function cmdRender(){const box=$('#cmd .cmdres');if(!box)return;
 box.innerHTML=cmdList.length?cmdList.map((it,i)=>`<div class="cmdi ${i===cmdSel?'sel':''}" data-i="${i}">${svg(it.ic||'spark')}<span class="ci-t">${esc(it.t)}</span><span class="ci-s">${esc(it.s||'')}</span></div>`).join(''):'<div class="cmdempty">Nessun risultato.</div>';
 box.querySelectorAll('.cmdi').forEach(e=>{e.onmouseenter=()=>{cmdSel=+e.dataset.i;cmdMark();};e.onclick=()=>cmdRun(+e.dataset.i);});
}
function cmdMark(){document.querySelectorAll('#cmd .cmdi').forEach((e,i)=>e.classList.toggle('sel',i===cmdSel));}
function cmdRun(i){const it=cmdList[i];cmdClose();if(it)it.run();}
function cmdOpen(){$('#cmd').innerHTML=`<div class="cmdbox"><div class="cmdin">${svg('spark')}<input id="cmd-q" placeholder="Cerca sezioni, repo, idee, azioni..."><span class="kbd">Esc</span></div><div class="cmdres"></div></div>`;
 $('#cmd').classList.add('on');cmdSel=0;cmdList=cmdItems('');cmdRender();
 const inp=$('#cmd-q');inp.focus();
 inp.oninput=()=>{cmdList=cmdItems(inp.value.trim());cmdSel=0;cmdRender();};
 inp.onkeydown=e=>{if(e.key==='ArrowDown'){e.preventDefault();cmdSel=Math.min(cmdSel+1,cmdList.length-1);cmdMark();scrollSel();}
   else if(e.key==='ArrowUp'){e.preventDefault();cmdSel=Math.max(cmdSel-1,0);cmdMark();scrollSel();}
   else if(e.key==='Enter'){e.preventDefault();cmdRun(cmdSel);}};
}
function scrollSel(){const el=document.querySelectorAll('#cmd .cmdi')[cmdSel];if(el)el.scrollIntoView({block:'nearest'});}
function cmdClose(){$('#cmd').classList.remove('on');}
$('#cmd').addEventListener('click',e=>{if(e.target.id==='cmd')cmdClose();});
document.addEventListener('keydown',e=>{if((e.ctrlKey||e.metaKey)&&e.key.toLowerCase()==='k'){e.preventDefault();cmdOpen();}
 else if(e.key==='Escape')cmdClose();});

function bootApp(){loadStore().then(()=>{
 theme=LS.get('theme',theme);applyTheme(theme);
 buildNav();   // ricostruisce con le sezioni scelte (ora che lo store e caricato)
 notifOn=LS.get('notif_on',false)&&('Notification' in window)&&Notification.permission==='granted';setNotif(notifOn);
 const _h=location.hash.slice(1);
 go((NAV.some(n=>n.id===_h)||['cyber','blockchain','mercato','notizie'].includes(_h))?_h:'oggi');
 if(!LS.get('onboarded',false))showOnboarding();   // prima installazione: scegli le sezioni
 armAutolock();
});}
let _alkT=null;
function armAutolock(){
 const min=+LS.get('autolock_min',0)||0;
 clearTimeout(_alkT);
 if(!min)return;                                   // 0 = disattivato
 const reset=()=>{clearTimeout(_alkT);_alkT=setTimeout(async()=>{
   try{await fetch('/lock',{method:'POST',headers:{'Content-Type':'application/json'},body:'{}'});}catch(e){}
   location.reload();                              // se c'e un PIN torna il lucchetto
 },min*60000);};
 ['mousemove','keydown','click','touchstart'].forEach(ev=>document.addEventListener(ev,reset,{passive:true}));
 reset();
}
// blocco con PIN: se attivo e non sbloccato, mostra il lucchetto e NON avviare l'app
function showLock(err){const ov=$('#lockov');ov.classList.add('on');
 ov.innerHTML=`<div class="lockcard"><div class="lockic">${svg('lock')}</div><h2>miAi e bloccato</h2>
   <p class="sub">Inserisci il PIN per accedere.</p>
   <input class="inp" id="lk-pin" type="password" inputmode="numeric" placeholder="PIN" autocomplete="off"
     onkeydown="if(event.key==='Enter')lkUnlock()" style="text-align:center;font-size:20px;letter-spacing:4px;max-width:220px">
   ${err?`<div class="cgfb no" style="margin:12px 0 0">${esc(err)}</div>`:''}
   <div style="margin-top:16px"><button class="btn pri" onclick="lkUnlock()">${svg('check')} Sblocca</button></div></div>`;
 setTimeout(()=>{const i=$('#lk-pin');if(i)i.focus();},60);}
async function lkUnlock(){const pin=($('#lk-pin')||{}).value||'';
 try{const r=await (await fetch('/unlock',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({pin})})).json();
  if(r.ok){$('#lockov').classList.remove('on');$('#lockov').innerHTML='';bootApp();}
  else showLock('PIN errato. Riprova.');}
 catch(e){showLock('Errore di rete.');}}
(async()=>{
 let a={locked:false,authed:true};
 try{a=await (await fetch('/auth-status')).json();}catch(e){}
 if(a.locked&&!a.authed)showLock();else bootApp();
})();
</script></body></html>"""


if __name__ == "__main__":
    print(render_ui())
