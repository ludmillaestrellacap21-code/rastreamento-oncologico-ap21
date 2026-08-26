from pathlib import Path
import sqlite3
import pandas as pd

DB_PATH = str(Path(__file__).resolve().parents[1] / "banco" / "rastreamento.db")

conn = sqlite3.connect(DB_PATH)

df = pd.read_sql("""
    SELECT situacao, data_agendamento, status_rastreamento
    FROM populacao_alvo
    WHERE programa_monitorado = 'mamografia'
    AND data_agendamento IS NULL
    AND situacao != 'Sem registro'
    LIMIT 10
""", conn)

conn.close()
print(df)
