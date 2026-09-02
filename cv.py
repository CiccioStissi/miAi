"""Sezione CV - estrae il testo da un PDF e lo fa analizzare a Ollama.

Nessuna rete esterna: pypdf legge il PDF in locale, Ollama fa l'analisi.
Ritorna dati strutturati + punteggio 0-100 + cosa/come cambiare + riscritture.

Uso CLI: python cv.py percorso.pdf
"""
import base64
import io
import ipaddress
import json
import re
import socket
from html.parser import HTMLParser
from urllib.parse import urlparse

import requests
from pypdf import PdfReader

import llm

MAX_CHARS = 12000  # taglia CV molto lunghi: oltre non serve, satura il contesto


def extract_text(pdf_bytes):
    """Testo grezzo dal PDF. Solleva ValueError se non e' leggibile."""
    try:
        reader = PdfReader(io.BytesIO(pdf_bytes))
    except Exception as e:
        raise ValueError(f"PDF non leggibile: {e}")
    parts = [(p.extract_text() or "") for p in reader.pages]
    # NFKC: normalizza le legature dei PDF (ﬃ -> ffi, ﬁ -> fi...) e altri caratteri compat
    import unicodedata
    text = unicodedata.normalize("NFKC", "\n".join(parts))
    text = re.sub(r"\n{3,}", "\n\n", text).strip()
    if len(text) < 30:
        raise ValueError("PDF senza testo estraibile (forse e' una scansione/immagine).")
    return text[:MAX_CHARS]


_PROMPT = (
    "Sei un recruiter senior e career coach. Analizza questo CV in modo critico ma utile. "
    "Estrai i dati e valuta con onesta': un punteggio alto va MERITATO.\n\n"
    "CV:\n{cv}\n\n"
    "Rispondi SOLO in JSON con questa struttura esatta:\n"
    '{{"nome":"","ruolo":"ruolo professionale che emerge dal CV",'
    '"contatti":{{"email":"","telefono":"","link":"linkedin/github/sito se presenti"}},'
    '"sintesi":"2 righe che riassumono il profilo",'
    '"competenze":["skill principali, max 12"],'
    '"esperienze":[{{"ruolo":"","dove":"","periodo":"","punti":["1-3 bullet chiave"]}}],'
    '"istruzione":[{{"titolo":"","dove":"","anno":""}}],'
    '"punteggio":0,'
    '"dettaglio":{{"struttura":0,"contenuto":0,"impatto":0,"leggibilita":0}},'
    '"punti_forti":["cosa gia funziona, max 5"],'
    '"problemi":[{{"cosa":"il problema","come":"azione concreta per risolverlo","gravita":"alta|media|bassa"}}],'
    '"riscritture":[{{"prima":"frase debole presa dal CV","dopo":"versione piu forte e misurabile"}}]}}\n'
    "Regole: punteggio e dettaglio sono interi 0-100 e devono essere COERENTI col giudizio. "
    "Valuta con criteri concreti: verbi d'azione, risultati QUANTIFICATI (numeri/%/impatto), "
    "compatibilita' con i filtri ATS (parole chiave del ruolo, formato pulito), assenza di frasi "
    "generiche o riempitive, coerenza cronologica. Dai 3-6 problemi ordinati per gravita', ognuno "
    "con un'azione concreta e specifica (non consigli vaghi). Dai 2-4 riscritture: 'prima' e' una "
    "frase debole PRESA dal CV, 'dopo' e' piu' forte, specifica e misurabile. Scrivi nella stessa "
    "lingua del CV. Niente testo fuori dal JSON."
)


def _clamp(v):
    try:
        return max(0, min(100, int(float(v))))
    except (TypeError, ValueError):
        return 0


def analyze(pdf_bytes, ollama_url="http://localhost:11434", model="llama3.2:3b"):
    text = extract_text(pdf_bytes)  # ValueError risale al chiamante -> messaggio all'utente
    prompt = _PROMPT.format(cv=text)
    d = json.loads(llm.generate(prompt, fmt="json", timeout=240))
    d["punteggio"] = _clamp(d.get("punteggio"))
    det = d.get("dettaglio") or {}
    d["dettaglio"] = {k: _clamp(det.get(k)) for k in ("struttura", "contenuto", "impatto", "leggibilita")}
    # se il modello scorda il totale, media delle sotto-voci
    if not d["punteggio"] and any(d["dettaglio"].values()):
        d["punteggio"] = round(sum(d["dettaglio"].values()) / 4)
    d["chars"] = len(text)
    return d


def analyze_b64(b64, **kw):
    """Wrapper per il server: riceve il PDF in base64 dal client."""
    return analyze(base64.b64decode(b64), **kw)


def _ask_json(prompt, ollama_url=None, model=None, timeout=240):
    return json.loads(llm.generate(prompt, fmt="json", timeout=timeout))


# ---- Riassunto di un PDF qualsiasi (paper, dispensa, contratto...) ----
def pdf_summary(pdf_bytes, ollama_url="http://localhost:11434", model="llama3.2:3b"):
    text = extract_text(pdf_bytes)  # riusa il parser del CV
    prompt = ("Riassumi questo documento per qualcuno che non ha tempo di leggerlo. "
              "Sii concreto e fedele al testo, niente invenzioni.\n\nDOCUMENTO:\n" + text +
              '\n\nRispondi SOLO in JSON: {"titolo":"","tipo":"tipo di documento (paper, dispensa, contratto, articolo...)",'
              '"sintesi":"3-5 righe che spiegano di cosa tratta e la conclusione",'
              '"punti_chiave":["i concetti/risultati principali, max 7"],'
              '"termini":[{"t":"termine tecnico","d":"definizione breve"}],'
              '"domande":["domande di verifica per capire se hai capito, max 5"]}')
    d = _ask_json(prompt, ollama_url, model)
    d["chars"] = len(text)
    return d


def pdf_summary_b64(b64, **kw):
    return pdf_summary(base64.b64decode(b64), **kw)


def _cv_ctx(cv):
    """Compatta i dati del CV (gia estratti) in testo per i prompt."""
    if not isinstance(cv, dict):
        return ""
    parts = [f"Nome: {cv.get('nome','')}", f"Ruolo: {cv.get('ruolo','')}",
             "Competenze: " + ", ".join(cv.get("competenze", []) or [])]
    for e in (cv.get("esperienze") or [])[:5]:
        parts.append(f"Esperienza: {e.get('ruolo','')} @ {e.get('dove','')} ({e.get('periodo','')})")
    for i in (cv.get("istruzione") or [])[:3]:
        parts.append(f"Istruzione: {i.get('titolo','')} - {i.get('dove','')}")
    return "\n".join(p for p in parts if p.strip().split(":", 1)[-1].strip())


# ---- Palestra colloquio: domande + tracce di risposta dal CV + ruolo ----
def interview(cv, ruolo, ollama_url="http://localhost:11434", model="llama3.2:3b"):
    ctx = _cv_ctx(cv)
    prompt = ("Sei un recruiter che prepara un candidato a un colloquio per il ruolo di '" + str(ruolo) +
              "'. Basandoti sul suo profilo, genera domande realistiche di colloquio con una traccia di "
              "risposta (spunti, non la risposta finale).\n\nPROFILO:\n" + (ctx or "(non fornito)") +
              '\n\nRispondi SOLO in JSON: {"ruolo":"","domande":[{"q":"la domanda",'
              '"tipo":"tecnica|comportamentale|hr","traccia":"come impostare una buona risposta, con esempio"}]}\n'
              "Dai 6-8 domande, mix dei tre tipi, in italiano.")
    d = _ask_json(prompt, ollama_url, model)
    if not isinstance(d.get("domande"), list):
        d["domande"] = []
    return d


# ---- Scarico e ripulisco il testo di un annuncio da un URL ----
class _HTMLText(HTMLParser):
    _SKIP = {"script", "style", "noscript", "svg", "head"}

    def __init__(self):
        super().__init__()
        self.out, self.skip = [], 0

    def handle_starttag(self, tag, attrs):
        if tag in self._SKIP:
            self.skip += 1

    def handle_endtag(self, tag):
        if tag in self._SKIP and self.skip:
            self.skip -= 1

    def handle_data(self, data):
        if not self.skip:
            t = data.strip()
            if t:
                self.out.append(t)


def _safe_url(url):
    """Guardia anti-SSRF: solo http/https verso host pubblici (no localhost/rete interna)."""
    u = urlparse(url)
    if u.scheme not in ("http", "https") or not u.hostname:
        raise ValueError("URL non valido: usa un indirizzo http/https completo.")
    try:
        ip = ipaddress.ip_address(socket.gethostbyname(u.hostname))
    except Exception:
        raise ValueError("Host non raggiungibile o non risolvibile.")
    if ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_reserved or ip.is_multicast:
        raise ValueError("URL non consentito (punta a un indirizzo interno).")


def fetch_job_text(url):
    _safe_url(url)
    try:
        r = requests.get(url, timeout=20, headers={
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                          "(KHTML, like Gecko) Chrome/120.0 Safari/537.36",
            "Accept-Language": "it,en;q=0.8"})
        r.raise_for_status()
    except requests.RequestException as e:
        raise ValueError(f"Impossibile scaricare la pagina: {str(e)[:80]}")
    p = _HTMLText()
    p.feed(r.text)
    text = re.sub(r"\s{2,}", " ", "\n".join(p.out)).strip()
    if len(text) < 120:
        raise ValueError("La pagina ha poco testo utile (forse richiede login o carica l'annuncio via JavaScript). Incolla il testo a mano.")
    return text[:6000]


# ---- Lettera di presentazione + compatibilita + probabilita di colloquio ----
def jobmatch(cv, annuncio, ollama_url="http://localhost:11434", model="llama3.2:3b"):
    ctx = _cv_ctx(cv)
    ann = str(annuncio)[:4500]
    prompt = ("Confronta il profilo del candidato con questo annuncio di lavoro. Valuta con onesta' la "
              "compatibilita' e la probabilita' realistica di essere chiamato per un colloquio (considera "
              "quanto il profilo copre i requisiti e quanto sarebbe competitivo). Poi scrivi una lettera di "
              "presentazione su misura, concreta e senza fuffa.\n\n"
              "PROFILO:\n" + (ctx or "(non fornito)") + "\n\nANNUNCIO:\n" + ann +
              '\n\nRispondi SOLO in JSON: {"punteggio":0,"probabilita":0,'
              '"verdetto":"una frase sulla probabilita di essere chiamato","ruolo":"ruolo dell\'annuncio",'
              '"coperti":["requisiti dell\'annuncio che il candidato soddisfa"],'
              '"mancanti":["requisiti che mancano o sono deboli"],'
              '"consigli":["come alzare le probabilita o come presentarsi meglio, max 4"],'
              '"lettera":"lettera di presentazione di 150-220 parole, tono professionale"}\n'
              "punteggio (compatibilita col ruolo) e probabilita (chance di colloquio) sono interi 0-100. In italiano.")
    d = _ask_json(prompt, ollama_url, model)
    d["punteggio"] = _clamp(d.get("punteggio"))
    d["probabilita"] = _clamp(d.get("probabilita")) or d["punteggio"]
    return d


def jobmatch_url(cv, url, ollama_url="http://localhost:11434", model="llama3.2:3b"):
    """Scarica l'annuncio dall'URL e lo confronta col CV."""
    text = fetch_job_text(url)  # ValueError -> messaggio all'utente
    d = jobmatch(cv, text, ollama_url=ollama_url, model=model)
    d["fonte"] = url
    return d


# ================= CV Builder in LaTeX =================
# Il modello produce SOLO il CONTENUTO migliorato in JSON; il LaTeX lo genera Python
# (template fisso, escaping corretto): cosi il .tex compila sempre, niente LaTeX rotto
# inventato da un modello piccolo. Poi MiKTeX/pdflatex compila in PDF (se presente).

_TEX_MAP = {"\\": r"\textbackslash{}", "&": r"\&", "%": r"\%", "$": r"\$", "#": r"\#",
            "_": r"\_", "{": r"\{", "}": r"\}", "~": r"\textasciitilde{}", "^": r"\textasciicircum{}"}


def _tex(s):
    return "".join(_TEX_MAP.get(c, c) for c in str(s or ""))


_CV_BUILD_PROMPT = (
    "Sei un career coach esperto. Dato il CV grezzo qui sotto, RISCRIVILO in meglio: bullet piu' "
    "forti, concreti e possibilmente misurabili, sintesi efficace, ordine sensato. NON inventare "
    "esperienze, titoli, date o competenze non presenti nel testo. Mantieni la STESSA lingua del CV.\n\n"
    "CV:\n{cv}\n\n{sugg}"
    "Rispondi SOLO in JSON con questa struttura:\n"
    '{{"nome":"","ruolo":"","contatti":{{"email":"","telefono":"","luogo":"","link":["url o handle"]}},'
    '"sintesi":"2-3 righe","competenze":["skill"],'
    '"esperienze":[{{"ruolo":"","dove":"","periodo":"","punti":["bullet migliorati"]}}],'
    '"istruzione":[{{"titolo":"","dove":"","anno":""}}],'
    '"lingue":["es. Italiano (madrelingua)"],'
    '"extra":[{{"titolo":"nome sezione (es. Progetti, Certificazioni)","voci":["voce"]}}]}}'
)


def analysis_to_text(a):
    """Serializza l'analisi CV (dati strutturati) in testo, per ricostruire il CV."""
    L = []
    for k in ("nome", "ruolo", "sintesi"):
        if a.get(k):
            L.append(f"{k.capitalize()}: {a[k]}")
    c = a.get("contatti") or {}
    ct = [x for x in (c.get("email"), c.get("telefono"), c.get("link")) if x]
    if ct:
        L.append("Contatti: " + ", ".join(map(str, ct)))
    if a.get("competenze"):
        L.append("Competenze: " + ", ".join(map(str, a["competenze"])))
    for e in a.get("esperienze") or []:
        L.append(f"Esperienza: {e.get('ruolo','')} - {e.get('dove','')} ({e.get('periodo','')})")
        L += ["  - " + str(p) for p in (e.get("punti") or [])]
    for i in a.get("istruzione") or []:
        L.append(f"Istruzione: {i.get('titolo','')} - {i.get('dove','')} ({i.get('anno','')})")
    return "\n".join(L)


def suggestions_from(a):
    """Consigli dall'analisi (problemi + riscritture) da applicare nel nuovo CV."""
    out = []
    for pb in a.get("problemi") or []:
        if pb.get("cosa"):
            out.append(f"- {pb.get('cosa','')}: {pb.get('come','')}")
    for rw in a.get("riscritture") or []:
        if rw.get("prima"):
            out.append(f"- Riscrivi \"{rw.get('prima','')}\" in modo piu' forte come \"{rw.get('dopo','')}\"")
    return "\n".join(out)


def cv_build_json(text, suggestions=""):
    sugg = ("Applica questi consigli dell'analisi al nuovo CV:\n" + suggestions + "\n\n") if suggestions else ""
    prompt = _CV_BUILD_PROMPT.format(cv=text[:MAX_CHARS], sugg=sugg)
    return json.loads(llm.generate(prompt, fmt="json", timeout=300))


_TEX_PREAMBLE = r"""\documentclass[11pt,a4paper]{article}
\usepackage[T1]{fontenc}
\usepackage[utf8]{inputenc}
\usepackage[margin=1.7cm]{geometry}
\usepackage{enumitem}
\usepackage{titlesec}
\usepackage[dvipsnames]{xcolor}
\usepackage[hidelinks]{hyperref}
\definecolor{accent}{HTML}{2B5CE0}
\setlist[itemize]{leftmargin=1.2em,itemsep=1pt,topsep=2pt}
\titleformat{\section}{\large\bfseries\color{accent}}{}{0em}{}[\vspace{-0.6em}\color{accent}\rule{\linewidth}{0.8pt}]
\titlespacing{\section}{0pt}{10pt}{5pt}
\setlength{\parindent}{0pt}
\pagestyle{empty}
"""


def _tex_section(title, body):
    return "\\section{" + _tex(title) + "}\n" + body + "\n" if body.strip() else ""


def render_latex(cv):
    """Genera un documento LaTeX completo (pdflatex) dal CV strutturato."""
    name = _tex(cv.get("nome") or "Nome Cognome")
    role = _tex(cv.get("ruolo") or "")
    c = cv.get("contatti") or {}
    links = c.get("link") or []
    if isinstance(links, str):
        links = [links]
    bits = [x for x in (c.get("email"), c.get("telefono"), c.get("luogo"), *links) if x]
    contact = r" \ \textbullet\ ".join(_tex(b) for b in bits)

    parts = [_TEX_PREAMBLE, r"\begin{document}",
             r"\begin{center}{\Huge\bfseries " + name + r"}\\[2pt]"]
    if role:
        parts.append(r"{\large\color{accent}" + role + r"}\\[3pt]")
    if contact:
        parts.append(r"{\small " + contact + r"}")
    parts.append(r"\end{center}\vspace{4pt}")

    if cv.get("sintesi"):
        parts.append(_tex_section("Profilo", _tex(cv["sintesi"])))
    if cv.get("competenze"):
        skills = ", ".join(_tex(s) for s in cv["competenze"])
        parts.append(_tex_section("Competenze", skills))

    exp = ""
    for e in cv.get("esperienze") or []:
        head = r"\textbf{" + _tex(e.get("ruolo", "")) + "}"
        if e.get("dove"):
            head += r" \textit{" + _tex(e["dove"]) + "}"
        if e.get("periodo"):
            head += r"\hfill {\small " + _tex(e["periodo"]) + "}"
        exp += head + r"\\" + "\n"
        pts = [p for p in (e.get("punti") or []) if str(p).strip()]
        if pts:
            exp += r"\begin{itemize}" + "\n" + "\n".join(r"\item " + _tex(p) for p in pts) + "\n" + r"\end{itemize}" + "\n"
        exp += r"\vspace{3pt}" + "\n"
    parts.append(_tex_section("Esperienza", exp))

    edu = ""
    for i in cv.get("istruzione") or []:
        edu += r"\textbf{" + _tex(i.get("titolo", "")) + "}"
        if i.get("dove"):
            edu += " -- " + _tex(i["dove"])
        if i.get("anno"):
            edu += r"\hfill {\small " + _tex(i["anno"]) + "}"
        edu += r"\\" + "\n"
    parts.append(_tex_section("Istruzione", edu))

    if cv.get("lingue"):
        parts.append(_tex_section("Lingue", ", ".join(_tex(x) for x in cv["lingue"])))
    for sec in cv.get("extra") or []:
        voci = [v for v in (sec.get("voci") or []) if str(v).strip()]
        if voci:
            body = r"\begin{itemize}" + "\n" + "\n".join(r"\item " + _tex(v) for v in voci) + "\n" + r"\end{itemize}"
            parts.append(_tex_section(sec.get("titolo", "Altro"), body))

    parts.append(r"\end{document}")
    return "\n".join(p for p in parts if p)


def build_latex(text, suggestions=""):
    cv = cv_build_json(text, suggestions)
    return render_latex(cv), cv


# ---- Editor contenuti: estrai fedelmente struttura+contenuti, modifica SOLO il testo ----
_CV_EXTRACT_PROMPT = (
    "Estrai questo CV MANTENENDO le sue sezioni e il loro ORDINE originale. NON migliorare, "
    "NON inventare, NON riordinare, NON riassumere: riporta i contenuti in modo FEDELE, parola per "
    "parola dove puoi. Mantieni la lingua.\n"
    "REGOLE IMPORTANTI:\n"
    "- Ogni contenuto va in UNA SOLA sezione: NON duplicare righe o voci tra sezioni diverse.\n"
    "- La sezione Profilo/Sommario contiene SOLO il paragrafo introduttivo, NON esperienze/studi/skill.\n"
    "- Metti ogni riga sotto la sezione a cui appartiene nell'originale.\n"
    "- Se una voce ha ruolo/azienda/periodo o titolo di studio, mettili nei campi 'titolo'/'periodo'.\n\n"
    "CV:\n{cv}\n\n"
    "Rispondi SOLO in JSON:\n"
    '{{"nome":"","ruolo":"","contatti":{{"email":"","telefono":"","luogo":"","link":["url/handle"]}},'
    '"sezioni":[{{"titolo":"nome sezione come nell\'originale",'
    '"blocchi":[{{"titolo":"(es. Ruolo - Azienda, o Titolo di studio; vuoto se non serve)",'
    '"periodo":"(vuoto se assente)","righe":["riga o bullet, testo fedele"]}}]}}]}}'
)


def cv_extract_structured(text):
    """Estrae il CV in un modello generico a sezioni/blocchi, fedele all'originale."""
    return json.loads(llm.generate(_CV_EXTRACT_PROMPT.format(cv=text[:MAX_CHARS]), fmt="json", timeout=300))


def improve_text(text, ruolo=""):
    """Migliora un pezzo di testo del CV senza inventare fatti (per il tasto 'Migliora')."""
    if not (text or "").strip():
        return text
    prompt = ("Migliora questo testo di un CV: piu' incisivo, verbi d'azione, concreto e quando "
              "possibile quantificato. NON inventare fatti, numeri o esperienze non presenti. "
              "Mantieni la STESSA lingua e lo stesso significato. "
              + (f"Ruolo target: {ruolo}. " if ruolo else "")
              + "Rispondi SOLO con il testo migliorato, senza virgolette ne' spiegazioni.\n\nTESTO:\n" + text)
    return llm.generate(prompt).strip()


def _tex_header(cv):
    name = _tex(cv.get("nome") or "Nome Cognome")
    role = _tex(cv.get("ruolo") or "")
    c = cv.get("contatti") or {}
    links = c.get("link") or []
    if isinstance(links, str):
        links = [links]
    bits = [x for x in (c.get("email"), c.get("telefono"), c.get("luogo"), *links) if x]
    contact = r" \ \textbullet\ ".join(_tex(b) for b in bits)
    out = [r"\begin{center}{\Huge\bfseries " + name + r"}\\[2pt]"]
    if role:
        out.append(r"{\large\color{accent}" + role + r"}\\[3pt]")
    if contact:
        out.append(r"{\small " + contact + r"}")
    out.append(r"\end{center}\vspace{4pt}")
    return "\n".join(out)


def render_latex_generic(m):
    """Rende in LaTeX il modello generico a sezioni/blocchi (struttura preservata)."""
    parts = [_TEX_PREAMBLE, r"\begin{document}", _tex_header(m)]
    for sez in m.get("sezioni") or []:
        body = ""
        for b in sez.get("blocchi") or []:
            righe = [r for r in (b.get("righe") or []) if str(r).strip()]
            head = ""
            if b.get("titolo"):
                head = r"\textbf{" + _tex(b["titolo"]) + "}"
            if b.get("periodo"):
                head += r"\hfill {\small " + _tex(b["periodo"]) + "}"
            if head:
                body += head + r"\\" + "\n"
            if len(righe) > 1:
                body += (r"\begin{itemize}" + "\n"
                         + "\n".join(r"\item " + _tex(r) for r in righe)
                         + "\n" + r"\end{itemize}" + "\n")
            elif righe:
                body += _tex(righe[0]) + r"\\" + "\n"
            body += r"\vspace{2pt}" + "\n"
        parts.append(_tex_section(sez.get("titolo", ""), body))
    parts.append(r"\end{document}")
    return "\n".join(p for p in parts if p)


def latex_available():
    import shutil
    return bool(shutil.which("pdflatex"))


def compile_pdf(tex):
    """Compila il .tex in PDF con pdflatex (MiKTeX). Ritorna (pdf_bytes, None) o (None, log)."""
    import os
    import shutil
    import subprocess
    import tempfile
    if not latex_available():
        return None, "pdflatex non trovato (installa MiKTeX o TeX Live)"
    d = tempfile.mkdtemp(prefix="cvtex_")
    try:
        with open(os.path.join(d, "cv.tex"), "w", encoding="utf-8") as f:
            f.write(tex)
        r = None
        for _ in range(2):   # due passate: layout stabile
            r = subprocess.run(["pdflatex", "-interaction=nonstopmode", "-halt-on-error", "cv.tex"],
                               cwd=d, capture_output=True, text=True, timeout=120)
        pdf = os.path.join(d, "cv.pdf")
        if os.path.exists(pdf):
            with open(pdf, "rb") as f:
                return f.read(), None
        log = (r.stdout if r else "")[-1500:]
        return None, "compilazione fallita:\n" + log
    except subprocess.TimeoutExpired:
        return None, "compilazione troppo lenta (timeout)"
    finally:
        shutil.rmtree(d, ignore_errors=True)


def _demo():
    # firma minima PDF: verifica che extract_text rifiuti input non-PDF
    try:
        extract_text(b"non un pdf")
    except ValueError:
        pass
    else:
        raise AssertionError("doveva rifiutare input non-PDF")
    assert _clamp("85") == 85 and _clamp(200) == 100 and _clamp(None) == 0 and _clamp(-5) == 0
    # SSRF guard: localhost e rete interna devono essere rifiutati, schema non http pure
    for bad in ("http://127.0.0.1/x", "http://localhost/x", "http://169.254.169.254/", "file:///etc/passwd"):
        try:
            _safe_url(bad)
        except ValueError:
            pass
        else:
            raise AssertionError(f"doveva rifiutare {bad}")
    # estrazione testo: script/style vanno scartati
    p = _HTMLText()
    p.feed("<html><head><style>x{}</style></head><body>Ciao<script>evil()</script> Mondo</body></html>")
    txt = " ".join(p.out)
    assert "Ciao" in txt and "Mondo" in txt and "evil" not in txt, txt
    # LaTeX builder: escaping dei caratteri speciali + documento ben formato
    assert _tex("R&D 100% #1 a_b") == r"R\&D 100\% \#1 a\_b"
    tex = render_latex({"nome": "Mario R&D", "ruolo": "Dev",
                        "esperienze": [{"ruolo": "Eng", "dove": "ACME", "punti": ["x_1 & y"]}]})
    assert tex.startswith(r"\documentclass") and r"\end{document}" in tex
    assert r"Mario R\&D" in tex and r"x\_1 \& y" in tex
    print("ok: cv guardie coerenti (SSRF + HTML strip + LaTeX escape)")


if __name__ == "__main__":
    import sys
    if "--demo" in sys.argv:
        _demo()
    elif len(sys.argv) > 1:
        data = open(sys.argv[1], "rb").read()
        print(json.dumps(analyze(data), ensure_ascii=False, indent=2))
    else:
        print("uso: python cv.py file.pdf  |  python cv.py --demo")
