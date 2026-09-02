"""Gestione sicura del token GitHub.

- Salvato in Windows Credential Manager (cifrato per-utente) via keyring, mai in chiaro.
- Popup mascherato SOLO se token manca o ha >30 giorni (rotazione mensile).
- Validato contro GitHub prima di salvare (rifiuta token errati).

Uso manuale: `python auth.py`  -> forza inserimento/aggiornamento.
"""
import datetime
import keyring
import requests

SERVICE = "jarvis-github"
MAX_AGE_DAYS = 30


def _validate(token):
    """True se il token e valido (200 su /user)."""
    try:
        r = requests.get("https://api.github.com/user",
                         headers={"Authorization": f"Bearer {token}"}, timeout=15)
        return r.status_code == 200
    except Exception:
        return False


def _prompt(reason):
    """Popup tkinter mascherato. Ritorna token o None se annullato."""
    import tkinter as tk
    result = {"token": None}
    win = tk.Tk()
    win.title("Jarvis - Token GitHub")
    win.configure(bg="#0d1117")
    win.resizable(False, False)
    win.eval("tk::PlaceWindow . center")

    def row(txt, pady=0):
        tk.Label(win, text=txt, bg="#0d1117", fg="#e6edf3",
                 font=("Segoe UI", 10)).pack(padx=24, pady=pady, anchor="w")

    row(reason, pady=(20, 4))
    row("Incolla il Personal Access Token (classic, senza scope):", pady=(0, 8))
    ent = tk.Entry(win, show="●", width=52, bg="#161b22", fg="#e6edf3",
                   insertbackground="#e6edf3", relief="flat", font=("Consolas", 10))
    ent.pack(padx=24, ipady=5)
    ent.focus_set()
    msg = tk.Label(win, text="", bg="#0d1117", fg="#d29922", font=("Segoe UI", 9))
    msg.pack(padx=24, pady=(6, 0))

    def submit():
        tok = ent.get().strip()
        if not tok:
            msg.config(text="Campo vuoto.")
            return
        msg.config(text="Verifico...", fg="#8b949e")
        win.update()
        if _validate(tok):
            result["token"] = tok
            win.destroy()
        else:
            msg.config(text="Token non valido o rete assente.", fg="#f85149")

    btns = tk.Frame(win, bg="#0d1117")
    btns.pack(pady=16)
    tk.Button(btns, text="Salva", command=submit, bg="#238636", fg="white",
              relief="flat", padx=18, pady=4, font=("Segoe UI", 10)).pack(side="left", padx=6)
    tk.Button(btns, text="Annulla", command=win.destroy, bg="#21262d", fg="#e6edf3",
              relief="flat", padx=18, pady=4, font=("Segoe UI", 10)).pack(side="left", padx=6)
    ent.bind("<Return>", lambda e: submit())
    win.mainloop()
    return result["token"]


def _age_days():
    saved = keyring.get_password(SERVICE, "saved_at")
    if not saved:
        return None
    try:
        return (datetime.date.today() - datetime.date.fromisoformat(saved)).days
    except ValueError:
        return None


def get_token(force=False):
    """Ritorna un token valido, chiedendolo solo se manca/scaduto.
    Se annullato: usa il token esistente (se c'e), altrimenti None (modo degradato)."""
    tok = keyring.get_password(SERVICE, "token")
    age = _age_days()
    expired = age is None or age >= MAX_AGE_DAYS

    if not force and tok and not expired:
        return tok

    reason = ("Aggiornamento mensile del token." if (tok and expired)
              else "Primo avvio: serve il token GitHub.")
    new = _prompt(reason)
    if new:
        keyring.set_password(SERVICE, "token", new)
        keyring.set_password(SERVICE, "saved_at", datetime.date.today().isoformat())
        return new
    return tok  # annullato: fallback al vecchio (o None)


if __name__ == "__main__":
    t = get_token(force=True)
    print("Token salvato." if t else "Nessun token impostato.")
