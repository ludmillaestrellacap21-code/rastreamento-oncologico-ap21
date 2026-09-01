import json
import os
from collections import Counter

import gspread
from google.oauth2.service_account import Credentials


SHEET_ID = os.environ["GOOGLE_SHEET_ID"]
SERVICE_ACCOUNT_JSON = os.environ["GOOGLE_SERVICE_ACCOUNT_JSON"]

ABAS = {
    "Mamografia Bilateral": [
        "Situação",
        "Risco",
        "Agendamento",
    ],
    "Colonoscopia": [
        "Situação",
        "Risco",
        "Agendamento",
    ],
    "Citopatológico (PAP)": [
        "Alerta",
        "Devolutiva",
        "Exame",
        "Alterados",
        "Entrada",
        "Entrega",
        "Recebido",
    ],
    "Sangue Oculto nas Fezes (SO)": [
        "Alerta",
        "Devolutiva",
        "Exame",
        "Alterados",
        "Entrada",
        "Entrega",
        "Recebido",
    ],
}


def limpar_texto(valor):
    if valor is None:
        return ""

    return str(valor).strip()


def contar_valores(registros, coluna):
    contador = Counter()

    for registro in registros:
        valor = limpar_texto(registro.get(coluna))

        if valor == "":
            valor = "(vazio)"

        contador[valor] += 1

    return contador


def main():

    credenciais_dict = json.loads(
        SERVICE_ACCOUNT_JSON
    )

    scopes = [
        "https://www.googleapis.com/auth/spreadsheets.readonly",
        "https://www.googleapis.com/auth/drive.readonly",
    ]

    credentials = Credentials.from_service_account_info(
        credenciais_dict,
        scopes=scopes,
    )

    client = gspread.authorize(credentials)

    planilha = client.open_by_key(
        SHEET_ID
    )

    print(
        f"Planilha encontrada: {planilha.title}"
    )

    print("=" * 80)

    for nome_aba, colunas_analisar in ABAS.items():

        print()
        print("#" * 80)
        print(f"ABA: {nome_aba}")
        print("#" * 80)

        aba = planilha.worksheet(
            nome_aba
        )

        valores = aba.get_all_values()

        if not valores:

            print("Aba vazia.")
            continue

        # Normaliza os nomes das colunas.
        # Isso resolve, por exemplo, "CNS " com espaço.
        cabecalhos = [
            limpar_texto(x)
            for x in valores[0]
        ]

        registros = []

        for linha in valores[1:]:

            registro = {}

            for indice, coluna in enumerate(
                cabecalhos
            ):

                valor = (
                    linha[indice]
                    if indice < len(linha)
                    else ""
                )

                registro[coluna] = valor

            registros.append(
                registro
            )

        print(
            f"Registros de dados: {len(registros)}"
        )

        print(
            f"Colunas encontradas: {cabecalhos}"
        )

        for coluna in colunas_analisar:

            print()
            print("-" * 80)
            print(
                f"COLUNA: {coluna}"
            )
            print("-" * 80)

            if coluna not in cabecalhos:

                print(
                    "Coluna não encontrada."
                )

                continue

            contador = contar_valores(
                registros,
                coluna
            )

            for valor, quantidade in (
                contador.most_common()
            ):

                print(
                    f"{quantidade:>7} | {valor}"
                )

        print()
        print("=" * 80)


if __name__ == "__main__":
    main()