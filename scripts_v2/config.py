from pathlib import Path
import os
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]
load_dotenv(ROOT / '.env')

DB_PATH = ROOT / 'banco' / 'rastreamento.db'
VITACARE_DIR = ROOT / 'entrada' / 'vitacare'
EXCEL_DIR = ROOT / 'saida' / 'excel'

SUPABASE_URL = os.getenv('SUPABASE_URL', '')
SUPABASE_PUBLISHABLE_KEY = os.getenv('SUPABASE_PUBLISHABLE_KEY', '')
SUPABASE_SECRET_KEY = os.getenv('SUPABASE_SECRET_KEY', '')

BIGQUERY_PROJECT = os.getenv('BIGQUERY_PROJECT', 'rastreamento-oncologico-ap21')
BIGQUERY_DATASET = os.getenv('BIGQUERY_DATASET', 'rastreamento_oncologico')
BIGQUERY_TABLE = os.getenv('BIGQUERY_TABLE', 'populacao_alvo')
