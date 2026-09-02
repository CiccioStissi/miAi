"""Consumi AI multi-agente: aggrega i token dei vari agenti/CLI installati.

Ognuno usa l'AI che preferisce (Claude Code, Codex CLI, Gemini CLI...): questo
modulo rileva i LOG LOCALI di ciascuno e ne somma i token. Chi ne ha piu di uno
li vede tutti insieme + il totale combinato.

Onesta': i tool SOLO cloud (ChatGPT web, DeepSeek web...) non lasciano log
leggibili sul PC (l'uso sta sui loro server), quindi non sono auto-tracciabili;
li elenchiamo come "non rilevati". Le CLI agentiche invece scrivono transcript
locali e si leggono.

Nessun dato esce dal PC: si leggono solo file gia presenti in locale.
"""
import json
from datetime import datetime, timezone
from pathlib import Path

HOME = Path.home()

# Agenti cloud puri: nessun log locale, li mostriamo come non tracciabili in auto.
KNOWN_CLOUD = [("chatgpt", "ChatGPT (web)"), ("deepseek", "DeepSeek"),
               ("gemini_web", "Gemini (web)"), ("copilot", "GitHub Copilot")]


def _new():
    return {"tot": {"input": 0, "output": 0, "cache_w": 0, "cache_r": 0},
            "per_day": {}, "models": {}, "msgs": 0, "sess": {}, "files": 0}


def _touch_sess(agg, sid, ts, cwd=None, fu=None):
    s = agg["sess"].setdefault(sid, {"id": sid, "tok": 0, "msgs": 0, "first": None,
                                     "last": None, "cwd": "", "fu": ""})
    if ts:
        s["first"] = ts if s["first"] is None or ts < s["first"] else s["first"]
        s["last"] = ts if s["last"] is None or ts > s["last"] else s["last"]
    if cwd and not s["cwd"]:
        s["cwd"] = cwd
    if fu and not s["fu"]:
        s["fu"] = fu
    return s


def _add(agg, sid, it, ot, cw, cr, ts, model):
    t = agg["tot"]
    t["input"] += it; t["output"] += ot; t["cache_w"] += cw; t["cache_r"] += cr
    agg["msgs"] += 1
    tt = it + ot + cw + cr
    bil = it + ot + cw          # token "che pesano": esclude la cache riletta (riuso)
    s = _touch_sess(agg, sid, ts)
    s["tok"] += tt; s["msgs"] += 1
    day = (ts or "")[:10]
    if day:
        pd = agg["per_day"].setdefault(day, [0, 0]); pd[0] += tt; pd[1] += bil
    if model:
        agg["models"][model] = agg["models"].get(model, 0) + tt


def _finish(agg, id_, label, note=""):
    t = agg["tot"]
    days = sorted(agg["per_day"].items())
    sess_list = sorted(agg["sess"].values(), key=lambda x: x["last"] or "", reverse=True)
    for s in sess_list:
        s["cwd"] = (s["cwd"] or "").replace("\\", "/").rstrip("/").split("/")[-1]
        s["first"] = (s["first"] or "")[:10]
        s["last"] = (s["last"] or "")[:10]
    return {
        "id": id_, "label": label, "present": agg["msgs"] > 0, "note": note,
        "tot": t, "total": sum(t.values()),
        "billable": t["input"] + t["output"] + t["cache_w"],
        "messages": agg["msgs"], "sessions": len([s for s in agg["sess"] if agg["sess"][s]["tok"]]) or agg["files"],
        "days": len(days),
        "per_day": [{"day": d, "tok": v[0], "bil": v[1]} for d, v in days],
        "models": sorted([{"model": k, "tok": v} for k, v in agg["models"].items()], key=lambda x: -x["tok"])[:6],
        "sessions_list": sess_list[:40],
        "first": days[0][0] if days else None, "last": days[-1][0] if days else None,
    }


def _iter(root, pattern="*.jsonl"):
    if not root.exists():
        return
    for f in root.rglob(pattern):
        try:
            yield f, f.read_text(encoding="utf-8", errors="ignore").splitlines()
        except Exception:
            continue


# ---------- Claude Code (formato noto) ----------
def _claude_fu(o):
    m = o.get("message") or {}
    if m.get("role") != "user":
        return None
    c = m.get("content")
    txt = c if isinstance(c, str) else (" ".join(b.get("text", "") for b in c if isinstance(b, dict) and b.get("type") == "text") if isinstance(c, list) else "")
    txt = " ".join((txt or "").split())
    if not txt or txt.startswith("<") or txt.startswith("Caveat") or txt.startswith("[System"):
        return None
    return txt[:100]


def parse_claude():
    agg = _new()
    base = HOME / ".claude" / "projects"
    for f, lines in _iter(base):
        agg["files"] += 1
        for line in lines:
            try:
                o = json.loads(line)
            except Exception:
                continue
            m = o.get("message") or {}
            sid = o.get("sessionId") or o.get("session_id") or f.stem
            ts = o.get("timestamp") or ""
            _touch_sess(agg, sid, ts, o.get("cwd"), _claude_fu(o))
            u = m.get("usage")
            if isinstance(u, dict):
                _add(agg, sid, u.get("input_tokens", 0) or 0, u.get("output_tokens", 0) or 0,
                     u.get("cache_creation_input_tokens", 0) or 0, u.get("cache_read_input_tokens", 0) or 0,
                     ts, m.get("model"))
    return _finish(agg, "claude", "Claude Code")


# ---------- Generico (Codex, Gemini, altre CLI): cerca i token nel JSON ----------
def _find_usage(o):
    if isinstance(o, dict):
        k = o.keys()
        if ("input_tokens" in k or "prompt_tokens" in k) and ("output_tokens" in k or "completion_tokens" in k):
            it = o.get("input_tokens", o.get("prompt_tokens", 0)) or 0
            ot = o.get("output_tokens", o.get("completion_tokens", 0)) or 0
            cw = o.get("cache_creation_input_tokens", 0) or 0
            cr = o.get("cache_read_input_tokens", o.get("cached_input_tokens", o.get("cached_tokens", 0))) or 0
            return (it, ot, cw, cr)
        for v in o.values():
            r = _find_usage(v)
            if r:
                return r
    elif isinstance(o, list):
        for v in o:
            r = _find_usage(v)
            if r:
                return r
    return None


def _find_ts(o):
    if not isinstance(o, dict):
        return ""
    for key in ("timestamp", "ts", "time", "created_at", "created", "date"):
        v = o.get(key)
        if isinstance(v, str) and len(v) >= 10:
            return v[:19]
        if isinstance(v, (int, float)):
            try:
                return datetime.fromtimestamp(v if v < 1e11 else v / 1000, timezone.utc).isoformat()[:19]
            except Exception:
                pass
    return ""


def parse_generic(id_, label, root, pattern="*.jsonl"):
    agg = _new()
    for f, lines in _iter(root, pattern):
        agg["files"] += 1
        for line in lines:
            try:
                o = json.loads(line)
            except Exception:
                continue
            u = _find_usage(o)
            if u and (u[0] or u[1]):
                _add(agg, f.stem, u[0], u[1], u[2], u[3], _find_ts(o),
                     o.get("model") if isinstance(o, dict) else None)
    return _finish(agg, id_, label)


def parse_codex():
    return parse_generic("codex", "Codex CLI", HOME / ".codex")


def parse_gemini():
    return parse_generic("gemini", "Gemini CLI", HOME / ".gemini")


def all_usage():
    srcs = [parse_claude(), parse_codex(), parse_gemini()]
    comb = _new()
    for s in srcs:
        if not s["present"]:
            continue
        for k in comb["tot"]:
            comb["tot"][k] += s["tot"][k]
        comb["msgs"] += s["messages"]
        for d in s["per_day"]:
            pd = comb["per_day"].setdefault(d["day"], [0, 0]); pd[0] += d["tok"]; pd[1] += d["bil"]
        for m in s["models"]:
            comb["models"][m["model"]] = comb["models"].get(m["model"], 0) + m["tok"]
    combined = _finish(comb, "combined", "Tutti gli agenti")
    combined["sessions"] = sum(s["sessions"] for s in srcs if s["present"])
    return {
        "sources": [{k: v for k, v in s.items() if k != "sessions_list"} for s in srcs],
        "sessions_by": {s["id"]: s["sessions_list"] for s in srcs if s["present"]},
        "combined": combined,
        "detected": [s["id"] for s in srcs if s["present"]],
        "not_detected": [{"id": i, "label": l} for i, l in KNOWN_CLOUD],
    }


def _demo():
    d = all_usage()
    assert "combined" in d and isinstance(d["sources"], list)
    c = next((s for s in d["sources"] if s["id"] == "claude"), None)
    assert c is not None
    print(f"ok: rilevati {d['detected']} | Claude msg={c['messages']} billable={c['billable']}")


if __name__ == "__main__":
    import sys
    if "--demo" in sys.argv:
        _demo()
    else:
        d = all_usage()
        for s in d["sources"]:
            flag = "OK " if s["present"] else "-- "
            print(f"{flag}{s['label']:14} msg={s['messages']:>6}  billable={s['billable']:>12,}  giorni={s['days']}")
        print(f"   COMBINATO      msg={d['combined']['messages']:>6}  billable={d['combined']['billable']:>12,}")
