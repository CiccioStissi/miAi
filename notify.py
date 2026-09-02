"""Notifica desktop non bloccante.

Usa Wscript.Shell.Popup (auto-chiudente, nessuna dipendenza esterna). Il popup
si chiude da solo dopo `secs` secondi, quindi non blocca il task schedulato.

Uso CLI: python notify.py "titolo" "messaggio"
"""
import subprocess
import sys


def _q(s):
    return "'" + str(s).replace("'", "''") + "'"


def toast(title, msg, secs=9):
    ps = f"(New-Object -ComObject Wscript.Shell).Popup({_q(msg)},{secs},{_q(title)},64)"
    try:
        subprocess.Popen(["powershell", "-NoProfile", "-Command", ps],
                         creationflags=0x08000000)  # CREATE_NO_WINDOW
    except Exception as e:
        print(f"  ! notify err: {e}")


if __name__ == "__main__":
    toast(sys.argv[1] if len(sys.argv) > 1 else "J.A.R.V.I.S.",
          sys.argv[2] if len(sys.argv) > 2 else "test notifica")
