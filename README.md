# miAi

**Centro di comando personale — locale, offline e privacy-first.**
Un'unica dashboard che raccoglie notizie, trend GitHub, idee di business, progetti, task,
analisi del CV, un gioco per imparare la cybersecurity e molto altro. Gira interamente sul
tuo PC: **nessun dato personale esce dal computer e finisce in rete.**

> Progetto personale, single-user, pensato per uso locale su `127.0.0.1`.
> Backend AI a scelta (Ollama locale o qualsiasi endpoint OpenAI-compatibile).

---

## Filosofia

- **Offline-first**: server in ascolto solo su `127.0.0.1`, nessun servizio cloud richiesto.
- **Privacy by design**: i dati (preferiti, agenda, progetti, CV) restano sul disco; con PIN
  attivo lo storage è **cifrato a riposo** (Fernet, chiave derivata dal PIN via scrypt).
- **Zero build**: l'interfaccia è un singolo file HTML generato da Python, servito da
  `http.server` della standard library. Niente Node, niente bundler.
- **Generico e personalizzabile**: in fase di primo avvio scegli quali sezioni mostrare,
  quali argomenti seguire, quali interessi e quale modello AI usare.

---

## Funzionalità principali

| Area | Cosa fa |
|------|---------|
| **Oggi** | Il meglio di tutte le sezioni filtrato alla data odierna; tessere scegli-tu. |
| **Assistente** | Chat con l'AI locale che vede i tuoi dati e **agisce** (apri sezioni, aggiungi promemoria/task, cambia tema…), con risposte in streaming. |
| **Giornale** | Notizie dei soli argomenti che scegli (cronaca, sport, tech, immobiliare…), più Cyber e Blockchain. Fonti RSS pubbliche. |
| **GitHub** | Repository nuove e di tendenza filtrate per i tuoi interessi, con punteggio di rilevanza. |
| **Idee** | Idee di business generate incrociando trend reali e i tuoi interessi. |
| **Progetti / Task** | I tuoi progetti attivi con avanzamento e task collegati, con priorità. |
| **Analisi CV** | Carichi il CV in PDF: estrazione dati, suggerimenti e punteggio 0–100. |
| **CyberQuest** | Percorso a livelli per imparare la cybersecurity difensiva giocando (quiz + mini-giochi interattivi). |
| **Riassunto PDF** | Sintesi, punti chiave e domande da un PDF (paper, dispensa, contratto). |
| **Palestra colloquio** | Domande di colloquio realistiche dal tuo CV e dal ruolo target. |
| **Lettera & Match** | Compatibilità CV ↔ annuncio + lettera di presentazione su misura. |
| **Agenda / Scrittura** | Scadenze con avvisi desktop; riscrittura/traduzione testi con l'AI. |
| **Disco / PC** | Spazio liberabile, file freddi e duplicati; consigli sul tuo hardware reale. |
| **Consumi AI** | Token usati dai tuoi agenti AI (Claude Code, Codex, Gemini…), combinati e per agente. |
| **Personalizza** | 30+ temi, scelta del modello AI, PIN, auto-lock, backup/ripristino, avvio automatico. |

---

## Privacy & sicurezza

- Server vincolato a `127.0.0.1`; validazione di **Host** e **Origin** (anti CSRF / DNS-rebinding).
- **Content-Security-Policy** con `connect-src 'self'` (blocca l'esfiltrazione via XSS),
  `Referrer-Policy: no-referrer`, `X-Content-Type-Options: nosniff`.
- **PIN opzionale** applicato lato server (401 sui dati finché non sblocchi) + **auto-lock**.
- **Cifratura dello storage a riposo** con Fernet (chiave da scrypt sul PIN).
- I moduli che escono in rete leggono **solo fonti pubbliche** (GitHub, Google News RSS,
  CoinGecko, CISA) e non inviano mai dati personali.

---

## Lingue

Cambio lingua dell'intera interfaccia tramite **argos-translate** (traduzione neurale
**offline**): dopo il download una-tantum del pacchetto lingua, la traduzione è locale,
istantanea (cache su disco) e copre ogni testo. I contenuti generati dall'AI seguono la
lingua scelta.

---

## Stack tecnico

- **Python** (standard library `http.server`, `sqlite3`), zero framework web.
- **SQLite** per i dati raccolti dall'agente.
- **Interfaccia**: un singolo `app.html` generato da template Python (CSS/JS inline).
- **AI**: [Ollama](https://ollama.com) locale di default, oppure qualsiasi endpoint
  OpenAI-compatibile (LM Studio, llama.cpp, vLLM, API cloud).
- **Traduzione**: [argos-translate](https://github.com/argosopentech/argos-translate) (offline).
- **Sicurezza**: `cryptography` (Fernet), `keyring` per il token GitHub (Credential Manager).

---

## Avvio rapido

```bash
pip install -r requirements.txt

python agent.py     # prima raccolta dati + genera app.html
python server.py    # avvia il server locale
```

Apri **http://127.0.0.1:8770/app**.

> Per le funzioni AI serve [Ollama](https://ollama.com) in esecuzione (`ollama serve`) con un
> modello scaricato (es. `ollama pull qwen2.5:3b-instruct`), oppure configura un altro backend
> dalla sezione **Modello AI**.

Su Windows puoi attivare l'**avvio automatico** al login dalle Impostazioni dell'app.

---

## Architettura in breve

```
agent.py      raccolta dati (GitHub, notizie, disco, hardware) -> SQLite
ui.py         genera app.html (single-file) dal payload
server.py     http.server su 127.0.0.1: API + servizio dell'app + auth/PIN + cifratura
llm.py        backend AI configurabile (Ollama / OpenAI-compatibile), coda + streaming
mt.py         traduzione UI offline (argos-translate) con cache su disco
```

---

## Licenza

[PolyForm Noncommercial 1.0.0](LICENSE) — **uso personale e non commerciale**.
Puoi usarlo, studiarlo e modificarlo per te; **non** è consentito venderlo o usarlo a fini
commerciali.
