import json
import os

import gspread
from google.oauth2.service_account import Credentials


SHEET_ID = os.environ["GOOGLE_SHEET_ID"]
SERVICE_ACCOUNT_JSON = os.environ["GOOGLE_SERVICE_ACCOUNT_JSON"]

ABAS = [
    "Mamografia Bilateral",
    "Citopatológico (PAP)",
    "Colonoscopia",
    "Sangue Oculto nas Fezes (SO)",
]


def main():
    credenciais_dict = json.loads(SERVICE_ACCOUNT_JSON)

    scopes = [
        "https://www.googleapis.com/auth/spreadsheets.readonly",
        "https://www.googleapis.com/auth/drive.readonly",
    ]

    credentials = Credentials.from_service_account_info(
        credenciais_dict,
        scopes=scopes,
    )

    client = gspread.authorize(credentials)
    planilha = client.open_by_key(SHEET_ID)

    print(f"Planilha encontrada: {planilha.title}")
    print("=" * 70)

    for nome_aba in ABAS:
        try:
            aba = planilha.worksheet(nome_aba)

            valores = aba.get_all_values()

            total_linhas = len(valores)
            total_colunas = max(
                (len(linha) for linha in valores),
                default=0,
            )

            print(f"Aba: {nome_aba}")
            print(f"Linhas: {total_linhas}")
            print(f"Colunas: {total_colunas}")

            if total_linhas > 0:
                print("Cabeçalhos:")
                print(valores[0])

            print("-" * 70)

        except Exception as e:
            print(f"ERRO ao acessar a aba '{nome_aba}': {e}")
            print("-" * 70)


if __name__ == "__main__":
    main()