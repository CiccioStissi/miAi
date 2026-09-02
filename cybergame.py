"""CyberQuest - percorso di apprendimento cybersecurity a livelli (SOLO difensivo).

Contenuto: una banca di sfide curate (verificate a mano) + un generatore Ollama
che estende il percorso all'infinito (oltre la banca) mantenendo il taglio
DIFENSIVO ed educativo. Ogni sfida ha una risposta canonica -> si verifica lato
client, e una spiegazione del "perche" -> si impara, non si indovina soltanto.

Tipi di sfida (entrambi verificabili senza rete):
  - "scelta": domanda a risposta multipla, campo `a` = indice opzione giusta
  - "input" : risposta testuale breve (decode/identifica), confronto normalizzato

Uso CLI: python cybergame.py           (stampa la banca)
         python cybergame.py --demo    (self-check)
         python cybergame.py --gen phishing 2   (genera un livello via Ollama)
"""
import json
import re

import requests
import llm

# Capitoli del percorso: id, titolo, icona (nome usato dal front-end), colore.
CHAPTERS = [
    {"id": "basi", "nome": "Le basi (parti da qui)", "icon": "shield", "col": "#43d391"},
    {"id": "phishing", "nome": "Phishing & Ingegneria sociale", "icon": "mail", "col": "#ff6a3d"},
    {"id": "cripto", "nome": "Password & Crittografia", "icon": "lock", "col": "#8a6cff"},
    {"id": "rete", "nome": "Reti & Traffico", "icon": "wifi", "col": "#39e0cb"},
    {"id": "web", "nome": "Sicurezza Web (difesa)", "icon": "globe", "col": "#5b8cff"},
    {"id": "log", "nome": "Log & Incident Response", "icon": "activity", "col": "#f5a524"},
    {"id": "malware", "nome": "Concetti Malware", "icon": "bug", "col": "#e01b2c"},
    {"id": "osint", "nome": "OSINT difensiva & Privacy", "icon": "eye", "col": "#1fd982"},
    {"id": "codice", "nome": "Secure Coding", "icon": "code", "col": "#46dcd2"},
]

# Banca curata. Ogni voce: cap, tipo, q, (opts+a) | (a testo), perche, diff(1-3).
SEED = [
    # --- basi (livello davvero base: usare i propri dispositivi in sicurezza) ---
    {"cap": "basi", "tipo": "scelta", "diff": 1,
     "q": "Qual e' il modo piu sicuro per bloccare lo smartphone?",
     "opts": ["Nessun blocco, e' comodo", "Un PIN di 4 cifre come 1234", "PIN lungo o impronta/volto", "La data di nascita"],
     "a": 2, "perche": "Un blocco lungo (o biometrico) protegge tutto cio che hai sul telefono se lo perdi o te lo rubano. Evita PIN ovvi (1234, data di nascita)."},
    {"cap": "basi", "tipo": "scelta", "diff": 1,
     "q": "Perche NON conviene usare la stessa password su piu siti?",
     "opts": ["E' piu lento", "Se un sito viene bucato, entrano ovunque", "Occupa memoria", "Non e' un problema"],
     "a": 1, "perche": "Se un sito subisce un furto dati, quella password viene provata su email, banca, social. Una password diversa per ogni sito limita il danno a un solo account."},
    {"cap": "basi", "tipo": "scelta", "diff": 1,
     "q": "Cosa ti aiuta ad avere una password diversa e forte per ogni sito senza ricordarle a memoria?",
     "opts": ["Scriverle su un foglio", "Un password manager", "Usarle tutte uguali", "Il nome del cane"],
     "a": 1, "perche": "Un password manager (es. Bitwarden, KeePass) genera e ricorda password uniche e robuste: tu ricordi solo la password principale."},
    {"cap": "basi", "tipo": "scelta", "diff": 1,
     "q": "Cos'e' l'autenticazione a due fattori (2FA)?",
     "opts": ["Una password piu lunga", "Un secondo codice oltre alla password", "Un antivirus", "Un tipo di wifi"],
     "a": 1, "perche": "La 2FA aggiunge un secondo passo (codice sull'app/SMS): anche se qualcuno ruba la password, senza il secondo fattore non entra. Attivala su email e banca."},
    {"cap": "basi", "tipo": "scelta", "diff": 1,
     "q": "Arriva la notifica 'aggiornamento disponibile' su telefono/PC. Cosa fai?",
     "opts": ["La ignoro sempre", "Aggiorno: chiude falle di sicurezza", "Disattivo gli aggiornamenti", "Aspetto un anno"],
     "a": 1, "perche": "Gli aggiornamenti tappano le vulnerabilita che gli attaccanti sfruttano. Tenere sistema e app aggiornati e' una delle difese piu efficaci e semplici."},
    {"cap": "basi", "tipo": "scelta", "diff": 1,
     "q": "Sei sul wifi gratis di un bar. Cosa e' piu prudente evitare?",
     "opts": ["Leggere le notizie", "Accedere alla banca senza precauzioni", "Ascoltare musica", "Guardare le mappe"],
     "a": 1, "perche": "Su reti pubbliche il traffico puo essere intercettato. Per operazioni sensibili usa la rete dati del telefono o una VPN affidabile, e assicurati del lucchetto HTTPS."},
    {"cap": "basi", "tipo": "scelta", "diff": 1,
     "q": "Come proteggi le tue foto e i tuoi file da guasti o ransomware?",
     "opts": ["Non serve", "Backup regolari (es. su disco esterno/cloud)", "Cancellarli spesso", "Rinominarli"],
     "a": 1, "perche": "Un backup e' la rete di sicurezza: se il dispositivo si rompe o vieni colpito da un ransomware, ripristini tutto. Regola 3-2-1: 3 copie, 2 supporti, 1 fuori sede."},
    {"cap": "basi", "tipo": "scelta", "diff": 1,
     "q": "Un'app gratis chiede l'accesso a contatti, microfono e posizione senza motivo. Cosa fai?",
     "opts": ["Concedo tutto", "Nego i permessi non necessari", "Disinstallo l'antivirus", "Condivido l'app"],
     "a": 1, "perche": "Concedi solo i permessi che servono davvero alla funzione dell'app. Permessi eccessivi = piu dati tuoi raccolti. Controllali nelle impostazioni privacy."},
    {"cap": "basi", "tipo": "input", "diff": 1,
     "q": "Quante cifre/caratteri dovrebbe avere ALMENO una buona password oggi? (scrivi il numero)",
     "a": "12", "perche": "Almeno 12 caratteri (meglio una passphrase di piu parole). Piu e' lunga, piu e' difficile da forzare. La lunghezza conta piu della complessita."},
    # --- phishing ---
    {"cap": "phishing", "tipo": "scelta", "diff": 1,
     "q": "Un'email 'della banca' arriva da assistenza@banca-sicura-login.com e chiede di verificare le credenziali entro 24h. Il segnale piu forte di phishing?",
     "opts": ["Il tono cortese", "Il dominio non ufficiale + urgenza artificiale", "La presenza del logo", "L'orario di invio"],
     "a": 1, "perche": "Dominio look-alike e senso d'urgenza sono le due leve classiche del phishing. Le banche non chiedono credenziali via email."},
    {"cap": "phishing", "tipo": "scelta", "diff": 1,
     "q": "Quale URL e piu probabilmente malevolo?",
     "opts": ["https://accounts.google.com", "https://google.com.secure-verify.ru/login", "https://mail.google.com", "https://google.com"],
     "a": 1, "perche": "Il dominio reale e l'ultima parte prima della prima '/': qui e 'secure-verify.ru', non google. 'google.com.' e solo un sottodominio-esca."},
    {"cap": "phishing", "tipo": "scelta", "diff": 2,
     "q": "Ricevi un SMS: 'Pacco in giacenza, paga 1,99 EUR: bit.ly/xz9'. Azione difensiva corretta?",
     "opts": ["Aprire il link da desktop", "Non cliccare e verificare sul sito ufficiale del corriere", "Rispondere STOP", "Inoltrare a un amico"],
     "a": 1, "perche": "Smishing tipico: micro-pagamento per rubare la carta. Mai seguire il link; verificare il tracking sul sito ufficiale digitato a mano."},
    {"cap": "phishing", "tipo": "input", "diff": 2,
     "q": "Come si chiama l'attacco di phishing MIRATO a una singola persona di alto profilo (es. un CEO)? (una parola inglese)",
     "a": "whaling", "perche": "Whaling = spear phishing rivolto ai 'pesci grossi' (dirigenti). Spear phishing e mirato ma non necessariamente a un dirigente."},
    # --- cripto ---
    {"cap": "cripto", "tipo": "input", "diff": 1,
     "q": "Decodifica questa stringa Base64: Q3liZXJRdWVzdA==",
     "a": "cyberquest", "perche": "Base64 e una codifica (reversibile), NON cifratura. Riconoscerla e leggerla e' pane quotidiano nell'analisi difensiva."},
    {"cap": "cripto", "tipo": "scelta", "diff": 1,
     "q": "Quale conservazione delle password lato server e' corretta?",
     "opts": ["In chiaro", "Cifrate con AES reversibile", "Hash con bcrypt/argon2 + salt", "Codificate in Base64"],
     "a": 2, "perche": "Le password non si 'cifrano' (reversibile) ne' si codificano: si fa hashing lento con salt (bcrypt, scrypt, argon2) per resistere al furto del DB."},
    {"cap": "cripto", "tipo": "scelta", "diff": 2,
     "q": "Un hash lungo 32 caratteri esadecimali e' quasi certamente:",
     "opts": ["SHA-256", "MD5", "bcrypt", "SHA-1"],
     "a": 1, "perche": "MD5 = 128 bit = 32 hex. SHA-1 = 40 hex, SHA-256 = 64 hex. MD5 e' rotto: non usarlo per sicurezza."},
    {"cap": "cripto", "tipo": "scelta", "diff": 2,
     "q": "A cosa serve il 'salt' in un hash di password?",
     "opts": ["Rende l'hash piu corto", "Evita rainbow table e hash identici per password uguali", "Cifra la password", "Accelera il login"],
     "a": 1, "perche": "Il salt (unico per utente) impedisce le rainbow table e fa si che due utenti con la stessa password abbiano hash diversi."},
    # --- rete ---
    {"cap": "rete", "tipo": "scelta", "diff": 1,
     "q": "Quale porta e' associata di default a HTTPS?",
     "opts": ["21", "22", "443", "3389"],
     "a": 2, "perche": "443 = HTTPS. 21 FTP, 22 SSH, 3389 RDP. Conoscere le porte comuni aiuta a leggere log e firewall."},
    {"cap": "rete", "tipo": "scelta", "diff": 2,
     "q": "In un firewall difensivo, la policy di default piu sicura per il traffico in ingresso e':",
     "opts": ["Allow all, poi bloccare i cattivi", "Deny all, poi consentire solo il necessario", "Nessuna regola", "Consentire tutte le porte alte"],
     "a": 1, "perche": "Default-deny (whitelist): si nega tutto e si aprono solo i servizi indispensabili. Riduce la superficie d'attacco."},
    {"cap": "rete", "tipo": "input", "diff": 2,
     "q": "Come si chiama l'attacco che intercetta il traffico ponendosi tra due parti? (sigla di 4 lettere, es. XXXX)",
     "a": "mitm", "perche": "Man-in-the-Middle. Difesa: TLS con certificati validi, HSTS, e verifica dell'identita del server."},
    # --- web ---
    {"cap": "web", "tipo": "scelta", "diff": 1,
     "q": "Difesa PRINCIPALE contro l'SQL injection?",
     "opts": ["Nascondere gli errori", "Query parametrizzate / prepared statement", "Disattivare i cookie", "Usare HTTPS"],
     "a": 1, "perche": "Le prepared statement separano codice e dati: l'input utente non puo' piu' cambiare la struttura della query. La validazione e' complementare."},
    {"cap": "web", "tipo": "scelta", "diff": 2,
     "q": "L'header di risposta che mitiga il clickjacking e':",
     "opts": ["X-Frame-Options / CSP frame-ancestors", "Cache-Control", "Accept-Language", "ETag"],
     "a": 0, "perche": "X-Frame-Options: DENY (o CSP frame-ancestors 'none') impedisce che la pagina sia caricata in un iframe ostile."},
    {"cap": "web", "tipo": "scelta", "diff": 2,
     "q": "Un cookie di sessione dovrebbe avere gli attributi:",
     "opts": ["Solo Path", "HttpOnly, Secure, SameSite", "Nessuno", "Solo Domain"],
     "a": 1, "perche": "HttpOnly (no accesso via JS -> mitiga XSS furto sessione), Secure (solo HTTPS), SameSite (mitiga CSRF)."},
    {"cap": "web", "tipo": "input", "diff": 3,
     "q": "Sigla della vulnerabilita in cui codice JS malevolo viene eseguito nel browser della vittima. (3 lettere)",
     "a": "xss", "perche": "Cross-Site Scripting. Difesa: output encoding contestuale, CSP, e sanificazione dell'input."},
    # --- log ---
    {"cap": "log", "tipo": "scelta", "diff": 1,
     "q": "In un log di autenticazione vedi 200 tentativi falliti in 1 minuto da un solo IP. E' segno di:",
     "opts": ["Backup notturno", "Brute force / credential stuffing", "Aggiornamento software", "Errore utente singolo"],
     "a": 1, "perche": "Molti fallimenti rapidi da un IP = attacco a forza bruta. Difesa: rate limiting, lockout, MFA, blocco IP."},
    {"cap": "log", "tipo": "scelta", "diff": 2,
     "q": "Qual e' il PRIMO passo della incident response (NIST) dopo la preparazione?",
     "opts": ["Eradicazione", "Identificazione/Detection", "Recovery", "Lezioni apprese"],
     "a": 1, "perche": "Ciclo NIST: Preparazione -> Detection & Analysis -> Contenimento -> Eradicazione -> Recovery -> Lessons Learned."},
    {"cap": "log", "tipo": "input", "diff": 2,
     "q": "Come si chiama il sistema centralizzato che raccoglie e correla i log di sicurezza? (sigla, 4 lettere)",
     "a": "siem", "perche": "SIEM (Security Information and Event Management): aggrega, correla e allerta sugli eventi di sicurezza."},
    # --- malware ---
    {"cap": "malware", "tipo": "scelta", "diff": 1,
     "q": "Il malware che cifra i file e chiede un riscatto e':",
     "opts": ["Adware", "Ransomware", "Rootkit", "Keylogger"],
     "a": 1, "perche": "Ransomware. Difesa migliore: backup offline testati (regola 3-2-1), patch, e MFA per bloccare l'accesso iniziale."},
    {"cap": "malware", "tipo": "scelta", "diff": 2,
     "q": "La difesa piu efficace contro il ransomware per recuperare i dati e':",
     "opts": ["Antivirus a pagamento", "Backup offline testati (3-2-1)", "Firewall", "Password complesse"],
     "a": 1, "perche": "Solo un backup offline e verificato garantisce il recupero senza pagare. Gli altri riducono il rischio ma non ripristinano i dati."},
    {"cap": "malware", "tipo": "input", "diff": 3,
     "q": "Come si chiama l'analisi di un malware ESEGUENDOLO in un ambiente isolato? (una parola: analisi ...)",
     "a": "dinamica", "perche": "Analisi dinamica = esecuzione in sandbox isolata per osservare il comportamento. L'analisi statica invece non lo esegue."},
    # --- osint ---
    {"cap": "osint", "tipo": "scelta", "diff": 1,
     "q": "Per ridurre la tua impronta OSINT sui social, la mossa piu efficace e':",
     "opts": ["Postare piu spesso", "Limitare dati personali pubblici e geotag", "Usare lo stesso nick ovunque", "Accettare tutte le richieste"],
     "a": 1, "perche": "Meno dati pubblici (compleanno, luoghi, geotag) = meno materiale per social engineering e furto d'identita."},
    {"cap": "osint", "tipo": "scelta", "diff": 2,
     "q": "Riusare la stessa password su piu siti e' pericoloso soprattutto per:",
     "opts": ["Lentezza", "Credential stuffing dopo un data breach", "Consumo batteria", "Cookie di terze parti"],
     "a": 1, "perche": "Se un sito viene bucato, gli attaccanti provano quelle credenziali ovunque (credential stuffing). Difesa: password manager + MFA."},
    # --- codice ---
    {"cap": "codice", "tipo": "scelta", "diff": 2,
     "q": "In questo codice: query = \"SELECT * FROM u WHERE name='\" + input + \"'\" -- il problema e':",
     "opts": ["E' lento", "Concatenazione di input non fidato -> SQL injection", "Manca un indice", "Usa SELECT *"],
     "a": 1, "perche": "Concatenare input dell'utente nella query permette l'iniezione SQL. Usa sempre parametri/prepared statement."},
    {"cap": "codice", "tipo": "scelta", "diff": 2,
     "q": "Dove NON vanno mai messe le chiavi API / segreti?",
     "opts": ["In un secret manager", "In variabili d'ambiente", "Hardcoded nel codice committato su Git", "In un vault cifrato"],
     "a": 2, "perche": "Segreti nel repo finiscono nella cronologia Git per sempre e vengono scansionati dai bot. Usa env var, secret manager o vault."},
    {"cap": "codice", "tipo": "scelta", "diff": 3,
     "q": "La difesa contro attacchi che sfruttano dipendenze compromesse e':",
     "opts": ["Ignorare gli update", "Pinning versioni + audit (SCA) + lockfile", "Usare piu librerie possibili", "Disattivare i test"],
     "a": 1, "perche": "Supply-chain: bloccare le versioni, usare lockfile e scanner SCA (es. audit) per individuare dipendenze vulnerabili."},

    # ===== SFIDE INTERATTIVE =====
    # --- spot: clicca le righe con la falla (codice) ---
    {"cap": "codice", "tipo": "spot", "diff": 2,
     "q": "Clicca la riga che apre a una SQL injection.",
     "code": ["app.get('/user', (req, res) => {",
              "  const id = req.query.id;",
              "  const q = \"SELECT * FROM users WHERE id = \" + id;",
              "  db.query(q, (err, rows) => res.json(rows));",
              "});"],
     "bad": [2],
     "perche": "La riga 3 concatena l'input dell'utente nella query: un id come '1 OR 1=1' cambia la logica. Usa query parametrizzate: db.query('... WHERE id = ?', [id])."},
    {"cap": "web", "tipo": "spot", "diff": 2,
     "q": "Guarda questo pezzo di pagina/login. Clicca le righe con un problema di sicurezza (possono essere piu di una).",
     "code": ["<form action=\"http://esempio.com/login\" method=\"POST\">",
              "  <input type=\"text\" name=\"user\">",
              "  <input type=\"password\" name=\"pass\">",
              "  <button>Entra</button>",
              "</form>",
              "<script>document.cookie = 'sess=' + token;</script>"],
     "bad": [0, 5],
     "perche": "Riga 1: il form invia le credenziali in HTTP (non HTTPS) -> viaggiano in chiaro. Riga 6: il cookie di sessione e scritto via JS senza HttpOnly/Secure -> esposto a XSS. Il cookie andrebbe impostato dal server con HttpOnly; Secure; SameSite."},
    {"cap": "log", "tipo": "spot", "diff": 2,
     "q": "Clicca la riga di log che indica un accesso sospetto.",
     "code": ["10:01 login OK user=mario ip=10.0.0.5",
              "10:02 login OK user=lucia ip=10.0.0.6",
              "10:03 login FAIL user=admin ip=185.23.4.9 (x1)",
              "10:03 login FAIL user=admin ip=185.23.4.9 (x214)",
              "10:04 login OK user=mario ip=10.0.0.5"],
     "bad": [3],
     "perche": "214 tentativi falliti in un secondo sull'utente admin da un IP esterno = brute force/credential stuffing. Difesa: rate limiting, lockout progressivo, MFA e blocco dell'IP."},
    # --- fix: scrivi/correggi il codice (verifica regex must/forbid) ---
    {"cap": "codice", "tipo": "fix", "diff": 2,
     "q": "Riscrivi questa query per evitare la SQL injection (usa un placeholder parametrizzato, niente concatenazione).",
     "start": "const q = \"SELECT * FROM users WHERE id = \" + id;\ndb.query(q);",
     "must": ["db\\.query\\s*\\(", "\\?|\\$1|:id"],
     "forbid": ["\\+\\s*id", "\\+\\s*\"", "\"\\s*\\+"],
     "sol": "db.query('SELECT * FROM users WHERE id = ?', [id]);",
     "perche": "La versione sicura passa l'input come parametro separato: il driver lo tratta come dato, mai come SQL. Cosi 'id' non puo alterare la struttura della query."},
    {"cap": "web", "tipo": "fix", "diff": 2,
     "q": "Questo codice inserisce testo dell'utente nella pagina ed e vulnerabile a XSS. Correggilo (niente innerHTML con input non fidato).",
     "start": "el.innerHTML = userInput;",
     "must": ["textContent|innerText|createTextNode"],
     "forbid": ["innerHTML"],
     "sol": "el.textContent = userInput;",
     "perche": "innerHTML interpreta i tag: un input come <img onerror=...> esegue codice. textContent inserisce il testo come testo, neutralizzando lo script (output encoding)."},
    # --- order: riordina i passi ---
    {"cap": "log", "tipo": "order", "diff": 2,
     "q": "Ordina le fasi della incident response (modello NIST), dalla prima all'ultima.",
     "items": ["Preparazione", "Detection & Analysis", "Contenimento", "Eradicazione", "Recovery", "Lessons Learned"],
     "perche": "NIST: ci si prepara, si rileva/analizza, si contiene per limitare i danni, si eradica la causa, si ripristina, e infine si imparano le lezioni per migliorare."},
    {"cap": "cripto", "tipo": "order", "diff": 2,
     "q": "Ordina i passi per gestire in modo sicuro le password degli utenti lato server.",
     "items": ["Ricevi la password in HTTPS", "Genera un salt casuale per utente", "Applica un hash lento (bcrypt/argon2) con il salt", "Salva hash e salt nel database", "Al login, riesegui l'hash e confronta"],
     "perche": "Mai salvare la password: si genera un salt unico, si applica un hash lento e si salva solo l'hash+salt. Al login si ricalcola e si confronta, senza mai memorizzare il valore in chiaro."},
]

_RANKS = [(0, "Script Kiddie"), (150, "Junior Analyst"), (400, "SOC Analyst"),
          (800, "Threat Hunter"), (1400, "Security Engineer"), (2200, "CISO")]


def rank_for(xp):
    r = _RANKS[0][1]
    for soglia, nome in _RANKS:
        if xp >= soglia:
            r = nome
    return r


def get():
    """Banca + capitoli + ranghi per il front-end.
    Ordina le sfide per capitolo (stabile) cosi il percorso raggruppa i mondi
    senza ripetere le intestazioni, a prescindere dall'ordine in SEED."""
    order = {c["id"]: i for i, c in enumerate(CHAPTERS)}
    levels = sorted(SEED, key=lambda l: order.get(l["cap"], 99))
    return {"chapters": CHAPTERS, "levels": levels,
            "ranks": [{"xp": s, "nome": n} for s, n in _RANKS]}


_GEN_PROMPT = (
    "Sei un istruttore di cybersecurity DIFENSIVA. Crea UNA domanda-sfida educativa "
    "sul tema '{tema}', difficolta {diff}/3. Taglio SOLO difensivo/consapevolezza: "
    "riconoscere minacce, scegliere la mitigazione giusta, buone pratiche. "
    "NIENTE istruzioni per attaccare, exploit passo-passo o codice offensivo.\n"
    "Evita queste domande gia' usate: {avoid}\n\n"
    "Formato: JSON con q (domanda), opts (4 risposte COMPLETE e plausibili, testo vero non lettere), "
    "a (indice 0-3 della risposta GIUSTA), perche (spiegazione che DEVE riferirsi all'opzione con indice a).\n"
    "ESEMPIO di output valido:\n"
    '{{"q":"Qual e la difesa piu efficace contro il riuso delle password?",'
    '"opts":["Cambiarle ogni giorno","Password manager con password uniche + MFA",'
    '"Usare parole del dizionario","Scriverle su un foglio"],"a":1,'
    '"perche":"Un password manager genera password uniche per ogni sito e l\'MFA aggiunge un secondo fattore: cosi un breach non compromette gli altri account."}}\n'
    "Ora genera la TUA domanda su '{tema}'. Rispondi SOLO col JSON, opzioni reali (mai a/b/c/d)."
)

# opzioni-segnaposto tipiche quando il modello copia il template invece di ragionare
_PLACEHOLDER = ({"a", "b", "c", "d"}, {"opzione 1", "opzione 2", "opzione 3", "opzione 4"})


def _valid_level(d):
    if not isinstance(d, dict) or not d.get("q"):
        return False
    t = d.get("tipo")
    if t == "input":
        return bool(str(d.get("a", "")).strip())
    if t == "spot":
        code, bad = d.get("code"), d.get("bad")
        return (isinstance(code, list) and len(code) >= 2 and isinstance(bad, list)
                and len(bad) >= 1 and all(isinstance(b, int) and 0 <= b < len(code) for b in bad))
    if t == "fix":
        return bool(d.get("start") is not None and isinstance(d.get("must"), list)
                    and d.get("must") and isinstance(d.get("forbid"), list) and d.get("sol"))
    if t == "order":
        items = d.get("items")
        return isinstance(items, list) and len(items) >= 3
    opts = d.get("opts")
    if not (isinstance(opts, list) and 2 <= len(opts) <= 6 and isinstance(d.get("a"), int) and 0 <= d["a"] < len(opts)):
        return False
    norm = {str(o).strip().lower() for o in opts}
    if norm in _PLACEHOLDER or any(len(str(o).strip()) < 2 for o in opts):
        return False  # opzioni-segnaposto o vuote: scarta
    return len(norm) == len(opts)  # niente opzioni duplicate


def gen(chapter="phishing", diff=1, avoid=None, ollama_url="http://localhost:11434", model="llama3.2:3b"):
    """Genera un nuovo livello via Ollama. Verifica la struttura prima di restituirlo."""
    tema = next((c["nome"] for c in CHAPTERS if c["id"] == chapter), chapter)
    prompt = _GEN_PROMPT.format(tema=tema, diff=int(diff),
                                avoid=", ".join((avoid or [])[:6]) or "(nessuna)")
    for _ in range(3):  # il modello piccolo sbaglia formato: fino a 3 tentativi
        try:
            d = json.loads(llm.generate(prompt, fmt="json", options={"temperature": 0.8}, timeout=120))
        except Exception:
            continue
        d["tipo"] = "scelta"  # sempre scelta multipla (auto-verificabile)
        if isinstance(d.get("a"), str) and d["a"].isdigit():
            d["a"] = int(d["a"])
        if _valid_level(d):
            d.update(cap=chapter, diff=int(diff), gen=True)
            return d
    return {"error": "generazione non riuscita, riprova"}


def _demo():
    seen = set()
    for lv in SEED:
        assert lv["cap"] in {c["id"] for c in CHAPTERS}, f"capitolo ignoto: {lv['cap']}"
        assert lv.get("perche"), f"manca perche: {lv['q'][:30]}"
        assert _valid_level(lv), f"livello non valido: {lv['q'][:30]}"
        assert lv["q"] not in seen, f"domanda duplicata: {lv['q'][:30]}"
        seen.add(lv["q"])
    assert rank_for(0) == "Script Kiddie" and rank_for(5000) == "CISO"
    assert not _valid_level({"tipo": "scelta", "q": "x", "opts": ["a"], "a": 5})
    # ogni sfida "fix" DEVE essere risolvibile: la soluzione passa must (tutti) e forbid (nessuno)
    import re as _re
    for lv in SEED:
        if lv.get("tipo") == "fix":
            sol = lv["sol"]
            assert all(_re.search(p, sol, _re.I) for p in lv["must"]), f"sol non passa must: {lv['q'][:30]}"
            assert not any(_re.search(p, sol, _re.I) for p in lv["forbid"]), f"sol viola forbid: {lv['q'][:30]}"
    tipi = {}
    for lv in SEED:
        tipi[lv.get("tipo", "?")] = tipi.get(lv.get("tipo", "?"), 0) + 1
    print(f"ok: {len(SEED)} sfide su {len(CHAPTERS)} capitoli - tipi: {tipi}")


if __name__ == "__main__":
    import sys
    if "--demo" in sys.argv:
        _demo()
    elif "--gen" in sys.argv:
        i = sys.argv.index("--gen")
        cap = sys.argv[i + 1] if len(sys.argv) > i + 1 else "phishing"
        dif = int(sys.argv[i + 2]) if len(sys.argv) > i + 2 else 1
        print(json.dumps(gen(cap, dif), ensure_ascii=False, indent=2))
    else:
        for lv in SEED:
            print(f"[{lv['cap']:9} d{lv['diff']}] {lv['q'][:70]}")
