"""Compara o motor com o juiz para cada validacao/vN.json que tenha validacao/vN_resp.json ao lado.

  python3 validacao/conferir.py
"""
import subprocess
import sys
from pathlib import Path

AQUI = Path(__file__).resolve().parent
RAIZ = AQUI.parent

for sub in sorted(AQUI.glob("v*.json")):
    if sub.stem.endswith("_resp"):
        continue
    resp = sub.with_name(f"{sub.stem}_resp.json")
    if not resp.exists():
        print(f"{sub.stem}: sem resposta do juiz ({resp.name})")
        continue
    cmd = [sys.executable, str(RAIZ / "comparar.py"), str(sub), str(resp)]
    saida = subprocess.run(cmd, capture_output=True, text=True, cwd=RAIZ).stdout.strip().splitlines()
    print(f"{sub.stem}: {saida[-1] if saida else 'sem saída'}")
    if not saida or not saida[-1].startswith("OK"):
        print(f"   detalhes: python3 comparar.py validacao/{sub.name} validacao/{resp.name}")
