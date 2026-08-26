"""
setup.py
Projeto: Monitoramento de Rastreamento Oncológico — AP 21
Execute este script UMA VEZ para criar toda a estrutura de pastas do projeto.
"""

import os
from pathlib import Path

# =============================================================================
# PASTA RAIZ DO PROJETO — ajuste se quiser outro local
# =============================================================================
RAIZ = str(Path(__file__).resolve().parents[1])

# =============================================================================
# ESTRUTURA DE PASTAS
# =============================================================================
PASTAS = [
    # Dados de entrada
    r"entrada\vitacare",       # relatórios exportados do VitaCare (.xlsx)
    r"entrada\sisreg",         # downloads manuais do SISREG (backup local, opcional)

    # Banco de dados
    r"banco",                  # arquivo rastreamento.db (SQLite)

    # Saídas geradas pelos scripts
    r"saida\excel",            # relatórios Excel gerados pelo relatorio.py
    r"saida\logs",             # logs de execução dos scripts

    # Scripts Python do projeto
    r"scripts",                # leitor.py, relatorio.py, etc.
]

# =============================================================================
# CRIAÇÃO DAS PASTAS
# =============================================================================
print("=" * 50)
print("  Setup — Rastreamento Oncológico AP 21")
print("=" * 50)
print(f"\n📁 Pasta raiz: {RAIZ}\n")

for pasta in PASTAS:
    caminho_completo = os.path.join(RAIZ, pasta)
    os.makedirs(caminho_completo, exist_ok=True)
    print(f"   ✅ {caminho_completo}")

# =============================================================================
# ARQUIVO README NA RAIZ
# =============================================================================
readme_path = os.path.join(RAIZ, "LEIAME.txt")
with open(readme_path, "w", encoding="utf-8") as f:
    f.write("""MONITORAMENTO DE RASTREAMENTO ONCOLÓGICO — AP 21
================================================

ESTRUTURA DE PASTAS:

  entrada/
    vitacare/     → Coloque aqui o relatório geral exportado do VitaCare (.xlsx)
    sisreg/       → Backups locais da planilha do SISREG (opcional)

  banco/          → Banco SQLite gerado automaticamente (rastreamento.db)

  saida/
    excel/        → Relatórios Excel gerados pelo relatorio.py
    logs/         → Registros de execução dos scripts

  scripts/        → Todos os scripts Python do projeto

ORDEM DE EXECUÇÃO:
  1. setup.py      → apenas na primeira vez
  2. leitor.py     → leitura e cruzamento dos dados
  3. relatorio.py  → geração do Excel de saída

FONTES DE DADOS:
  - VitaCare: exportar relatório geral e salvar em entrada/vitacare/
  - SISREG: planilha lida automaticamente do Google Sheets (online)
""")

print(f"\n📄 LEIAME.txt criado em {RAIZ}")
print("\n✅ Estrutura criada com sucesso!")
print("\nPróximo passo: mova os scripts .py para a pasta 'scripts'")
print(f"e coloque o relatório do VitaCare em '{RAIZ}\\entrada\\vitacare\\'")
