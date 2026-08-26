"""Orquestrador v2: mantém o pipeline legado e adiciona a sincronização Supabase."""
import subprocess, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PY = sys.executable
steps = [
    (ROOT/'scripts'/'leitor.py', 'Processar VitaCare + SISREG no SQLite'),
    (ROOT/'scripts_v2'/'supabase_sync.py', 'Sincronizar Supabase'),
    (ROOT/'scripts'/'relatorio.py', 'Atualizar BigQuery e Excel'),
]
for script, label in steps:
    print(f'\n=== {label} ===')
    r=subprocess.run([PY,str(script)], cwd=str(script.parent))
    if r.returncode:
        raise SystemExit(r.returncode)
print('\n✅ Pipeline completo finalizado.')
