"""
atualizar.py
Projeto: Monitoramento de Rastreamento Oncológico — AP 21
Execute este script mensalmente para atualizar todos os dados.
Ele roda o leitor.py e o relatorio.py em sequência automaticamente.
"""

import subprocess
import sys
import os
from pathlib import Path
from datetime import datetime

# =============================================================================
# CONFIGURAÇÕES
# =============================================================================

PASTA_SCRIPTS = str(Path(__file__).resolve().parent)
PYTHON        = sys.executable  # usa o mesmo Python que está rodando este script

SCRIPTS = [
    ("leitor.py",    "Leitura e cruzamento dos dados"),
    ("relatorio.py", "Envio para o BigQuery"),
]

# =============================================================================
# EXECUÇÃO
# =============================================================================

if __name__ == "__main__":
    inicio = datetime.now()

    print("=" * 55)
    print("  Atualização — Rastreamento Oncológico AP 21")
    print(f"  {inicio.strftime('%d/%m/%Y às %H:%M')}")
    print("=" * 55)

    for script, descricao in SCRIPTS:
        caminho = os.path.join(PASTA_SCRIPTS, script)
        print(f"\n🚀 Executando: {script}")
        print(f"   {descricao}...")
        print("-" * 55)

        resultado = subprocess.run(
            [PYTHON, caminho],
            capture_output=False,  # mostra o output em tempo real
        )

        if resultado.returncode != 0:
            print(f"\n❌ Erro ao executar {script}. Atualização interrompida.")
            sys.exit(1)

    fim      = datetime.now()
    duracao  = (fim - inicio).seconds

    print("\n" + "=" * 55)
    print("  ✅ Atualização concluída com sucesso!")
    print(f"  Duração total: {duracao} segundos")
    print(f"  {fim.strftime('%d/%m/%Y às %H:%M')}")
    print("=" * 55)