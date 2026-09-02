"""Fase 3 - profilo hardware/software del PC.

Scansiona una tantum (o su richiesta) l'ambiente e salva machine.json.
La Fase 4 lo usa per il verdetto di compatibilita delle repo.

Uso: python machine.py        -> scansiona, salva, stampa.
"""
import json
import re
import shutil
import subprocess
from pathlib import Path

import psutil

ROOT = Path(__file__).parent
PROFILE = ROOT / "machine.json"


def _run(cmd):
    """Ritorna stdout stripped o '' se il comando manca/fallisce.
    Su Windows molti tool sono wrapper .cmd (npm, docker) -> prova anche quello."""
    exe = shutil.which(cmd[0]) or shutil.which(cmd[0] + ".cmd")
    if not exe:
        return ""
    try:
        out = subprocess.run([exe, *cmd[1:]], capture_output=True, text=True, timeout=15)
        return (out.stdout or "").strip()
    except Exception:
        return ""


def _ver(exe, *args):
    return _run([exe, *(args or ("--version",))]) or "non installato"


def _gpu():
    """(nome, vram_MB, cuda) da nvidia-smi, o valori vuoti se assente/AMD/Intel."""
    q = _run(["nvidia-smi", "--query-gpu=name,memory.total,driver_version",
              "--format=csv,noheader,nounits"])
    if not q:
        return {"name": "nessuna GPU NVIDIA rilevata", "vram_mb": 0, "cuda": "", "driver": ""}
    name, vram, driver = [x.strip() for x in q.splitlines()[0].split(",")]
    cuda = ""
    m = re.search(r"CUDA Version:\s*([\d.]+)", _run(["nvidia-smi"]))
    if m:
        cuda = m.group(1)
    return {"name": name, "vram_mb": int(vram), "cuda": cuda, "driver": driver}


def scan():
    vm = psutil.virtual_memory()
    free = shutil.disk_usage(str(ROOT)).free
    return {
        "os": _run(["cmd", "/c", "ver"]) or "Windows",
        "cpu_cores": psutil.cpu_count(logical=True),
        "cpu_cores_fisici": psutil.cpu_count(logical=False),
        "ram_gb": round(vm.total / 1024**3, 1),
        "disco_libero_gb": round(free / 1024**3, 1),
        "gpu": _gpu(),
        "python": _ver("python"),
        "pip": _ver("pip"),
        "node": _ver("node"),
        "npm": _ver("npm"),
        "docker": _ver("docker"),
        "git": _ver("git"),
    }


def load():
    """Profilo salvato, o None se mai scansionato."""
    if PROFILE.exists():
        return json.loads(PROFILE.read_text(encoding="utf-8"))
    return None


def get(refresh=False):
    """Profilo: dal file, oppure scansiona e salva se manca o refresh=True."""
    if not refresh:
        p = load()
        if p:
            return p
    p = scan()
    PROFILE.write_text(json.dumps(p, indent=2, ensure_ascii=False), encoding="utf-8")
    return p


if __name__ == "__main__":
    p = get(refresh=True)
    g = p["gpu"]
    print("PROFILO MACCHINA")
    print(f"  CPU     {p['cpu_cores']} thread ({p['cpu_cores_fisici']} core), RAM {p['ram_gb']} GB")
    print(f"  GPU     {g['name']} - {g['vram_mb']} MB VRAM, CUDA {g['cuda'] or 'n/d'}")
    print(f"  Disco   {p['disco_libero_gb']} GB liberi")
    print(f"  Python  {p['python']}")
    print(f"  Node    {p['node']} | npm {p['npm']}")
    print(f"  Docker  {p['docker']}")
    print(f"  Git     {p['git']}")
    print(f"\nsalvato -> {PROFILE}")
