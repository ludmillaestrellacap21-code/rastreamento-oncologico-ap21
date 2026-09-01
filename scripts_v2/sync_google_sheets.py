import hashlib
import json
import os
import re
import unicodedata
from datetime import datetime

import gspread
from google.oauth2.service_account import Credentials
from supabase import create_client


SUPABASE_URL = os.environ["SUPABASE_URL"]
SUPABASE_KEY = os.environ["SUPABASE_SERVICE_ROLE_KEY"]

GOOGLE_SHEET_ID = os.environ["GOOGLE_SHEET_ID"]
GOOGLE_SERVICE_ACCOUNT_JSON = os.environ[
    "GOOGLE_SERVICE_ACCOUNT_JSON"
]


ABAS = {
    "Mamografia Bilateral": "mamografia",
    "Colonoscopia": "colonoscopia",
    "Citopatológico (PAP)": "citopatologico",
    "Sangue Oculto nas Fezes (SO)": "sangue_oculto",
}


BATCH_SIZE = 250


def limpar(valor):
    if valor is None:
        return ""

    return str(valor).strip()


def normalizar_cns(valor):
    valor = limpar(valor)

    return re.sub(r"\D", "", valor)


def parse_data(valor):
    valor = limpar(valor)

    if not valor:
        return None

    formatos = [
        "%d/%m/%Y",
        "%Y-%m-%d",
        "%d/%m/%y",
    ]

    for formato in formatos:
        try:
            return datetime.strptime(
                valor,
                formato
            ).date().isoformat()

        except ValueError:
            pass

    return None


def sem_acentos(valor):
    valor = limpar(valor)

    return "".join(
        c
        for c in unicodedata.normalize("NFD", valor)
        if unicodedata.category(c) != "Mn"
    ).lower()


def chave_hash(*valores):
    texto = "|".join(
        limpar(v)
        for v in valores
    )

    return hashlib.sha256(
        texto.encode("utf-8")
    ).hexdigest()


def status_agendamento(situacao):
    situacao_norm = sem_acentos(situacao)

    if "agendamento confirmado" in situacao_norm:
        return "Confirmado"

    if "agendamento falta" in situacao_norm:
        return "Falta - Reconvocar"

    if "agendada" in situacao_norm:
        return "Agendado"

    if "pendente regulacao" in situacao_norm:
        return "Pendente regulação"

    if "cancelad" in situacao_norm:
        return "Cancelado"

    if "devolvida" in situacao_norm:
        return "Devolvido"

    if "reenviada" in situacao_norm:
        return "Reenviado"

    if "negada" in situacao_norm:
        return "Negado"

    if "obito" in situacao_norm:
        return "Óbito"

    return "Não classificado"


def status_laboratorio(
    entrada,
    recebido,
    entrega,
):
    if limpar(entrega):
        return "Resultado entregue"

    if limpar(recebido):
        return "Em processamento"

    if limpar(entrada):
        return "Coletado - aguardando laboratório"

    return "Sem movimentação"


def eh_alterado(programa, valor):
    valor = sem_acentos(valor)

    if not valor:
        return False

    if programa == "citopatologico":
        return "pap" in valor or "citopatologico" in valor

    if programa == "sangue_oculto":
        return (
            "sangue oculto" in valor
            or valor.startswith("so ")
        )

    return False


def eh_alerta(valor):
    valor = limpar(valor)

    return "🔴" in valor


def registros_da_aba(worksheet):
    valores = worksheet.get_all_values()

    if not valores:
        return []

    cabecalhos = [
        limpar(c)
        for c in valores[0]
    ]

    registros = []

    for linha in valores[1:]:
        registro = {}

        for i, coluna in enumerate(cabecalhos):
            registro[coluna] = (
                linha[i]
                if i < len(linha)
                else ""
            )

        registros.append(registro)

    return registros


def processar_agendamento(
    registro,
    programa,
    nome_aba,
):
    codigo = limpar(
        registro.get("Código de solicitação")
    )

    cns = normalizar_cns(
        registro.get("CNS")
    )

    data_solicitacao = parse_data(
        registro.get("Data de solicitação")
    )

    data_agendamento = parse_data(
        registro.get("Agendamento")
    )

    if codigo:
        chave = codigo

    else:
        chave = chave_hash(
            programa,
            cns,
            data_solicitacao,
            registro.get("Procedimento"),
        )

    situacao = limpar(
        registro.get("Situação")
    )

    return {
        "fonte": nome_aba,
        "programa_codigo": programa,
        "chave_origem": chave,

        "cns": cns or None,
        "nome": limpar(
            registro.get("Nome do paciente")
        ) or None,

        "unidade": limpar(
            registro.get("Unidade")
        ) or None,

        "data_solicitacao": data_solicitacao,
        "data_agendamento": data_agendamento,

        "situacao_origem": situacao or None,

        "status_operacional":
            status_agendamento(situacao),

        "risco": limpar(
            registro.get("Risco")
        ) or None,

        "procedimento": limpar(
            registro.get("Procedimento")
        ) or None,

        "solicitante": limpar(
            registro.get("Solicitante")
        ) or None,

        "data_coleta": None,
        "data_recebimento_laboratorio": None,
        "data_entrega_resultado": None,

        "exame": None,

        "alterado": False,
        "alerta": False,

        "atualizado_em":
            datetime.utcnow().isoformat(),
    }


def processar_laboratorio(
    registro,
    programa,
    nome_aba,
):
    cns = normalizar_cns(
        registro.get("CNS")
    )

    solicitacao = limpar(
        registro.get("Solicitação")
    )

    entrada = limpar(
        registro.get("Entrada")
    )

    recebido = limpar(
        registro.get("Recebido")
    )

    entrega = limpar(
        registro.get("Entrega")
    )

    exame = limpar(
        registro.get("Exame")
    )

    alterados = limpar(
        registro.get("Alterados")
    )

    if solicitacao:
        chave = solicitacao

    else:
        chave = chave_hash(
            programa,
            cns,
            entrada,
            exame,
        )

    return {
        "fonte": nome_aba,
        "programa_codigo": programa,
        "chave_origem": chave,

        "cns": cns or None,

        "nome": limpar(
            registro.get("Nome")
        ) or None,

        "unidade": limpar(
            registro.get("Unidade")
        ) or None,

        "data_solicitacao": None,
        "data_agendamento": None,

        "situacao_origem": None,

        "status_operacional":
            status_laboratorio(
                entrada,
                recebido,
                entrega,
            ),

        "risco": None,
        "procedimento": None,
        "solicitante": None,

        # Entrada = coleta/entrega pela unidade
        "data_coleta":
            parse_data(entrada),

        # Recebido = laboratório recebeu
        "data_recebimento_laboratorio":
            parse_data(recebido),

        # Entrega = unidade recebeu resultado
        "data_entrega_resultado":
            parse_data(entrega),

        "exame": exame or None,

        "alterado":
            eh_alterado(
                programa,
                alterados,
            ),

        "alerta":
            eh_alerta(
                registro.get("Alerta")
            ),

        "atualizado_em":
            datetime.utcnow().isoformat(),
    }


def upsert_lotes(
    supabase,
    dados,
):
    total = len(dados)

    for inicio in range(
        0,
        total,
        BATCH_SIZE,
    ):
        lote = dados[
            inicio:
            inicio + BATCH_SIZE
        ]

        supabase.table(
            "staging_google_sheets"
        ).upsert(
            lote,
            on_conflict="fonte,chave_origem",
        ).execute()

        print(
            f"Enviados "
            f"{min(inicio + BATCH_SIZE, total)} "
            f"de {total}"
        )


def main():
    print(
        "INICIANDO SINCRONIZAÇÃO GOOGLE SHEETS"
    )

    supabase = create_client(
        SUPABASE_URL,
        SUPABASE_KEY,
    )

    credenciais = json.loads(
        GOOGLE_SERVICE_ACCOUNT_JSON
    )

    scopes = [
        "https://www.googleapis.com/auth/spreadsheets.readonly",
        "https://www.googleapis.com/auth/drive.readonly",
    ]

    credentials = (
        Credentials.from_service_account_info(
            credenciais,
            scopes=scopes,
        )
    )

    google = gspread.authorize(
        credentials
    )

    planilha = google.open_by_key(
        GOOGLE_SHEET_ID
    )

    print(
        f"Planilha: {planilha.title}"
    )

    inicio_carga = (
        supabase
        .table("historico_cargas")
        .insert({
            "fonte": "Google Sheets",
            "competencia":
                datetime.now().strftime("%Y-%m"),
            "status": "processando",
        })
        .execute()
    )

    carga_id = (
        inicio_carga.data[0]["id"]
        if inicio_carga.data
        else None
    )

    total_lidos = 0
    total_processados = 0
    total_erros = 0

    try:
        todos = []

        for nome_aba, programa in ABAS.items():

            print()
            print(
                f"Lendo: {nome_aba}"
            )

            aba = planilha.worksheet(
                nome_aba
            )

            registros = registros_da_aba(
                aba
            )

            total_lidos += len(registros)

            print(
                f"Registros lidos: "
                f"{len(registros)}"
            )

            for registro in registros:

                try:

                    if programa in (
                        "mamografia",
                        "colonoscopia",
                    ):

                        item = (
                            processar_agendamento(
                                registro,
                                programa,
                                nome_aba,
                            )
                        )

                    else:

                        item = (
                            processar_laboratorio(
                                registro,
                                programa,
                                nome_aba,
                            )
                        )

                    # CNS é fundamental para
                    # integração posterior.
                    if not item["cns"]:
                        total_erros += 1
                        continue

                    todos.append(item)
                    total_processados += 1

                except Exception as erro:
                    total_erros += 1

                    print(
                        f"Erro em registro: {erro}"
                    )

        print()
        print(
            f"Total para gravar: "
            f"{len(todos)}"
        )

        upsert_lotes(
            supabase,
            todos,
        )

        if carga_id:
            (
                supabase
                .table("historico_cargas")
                .update({
                    "fim_em":
                        datetime.utcnow().isoformat(),

                    "registros_lidos":
                        total_lidos,

                    "registros_processados":
                        total_processados,

                    "registros_erro":
                        total_erros,

                    "status": "sucesso",

                    "mensagem":
                        "Sincronização Google Sheets concluída.",
                })
                .eq(
                    "id",
                    carga_id,
                )
                .execute()
            )

        print()
        print(
            "SINCRONIZAÇÃO CONCLUÍDA"
        )

        print(
            f"Lidos: {total_lidos}"
        )

        print(
            f"Processados: "
            f"{total_processados}"
        )

        print(
            f"Ignorados/erros: "
            f"{total_erros}"
        )

    except Exception as erro:

        if carga_id:
            (
                supabase
                .table("historico_cargas")
                .update({
                    "fim_em":
                        datetime.utcnow().isoformat(),

                    "registros_lidos":
                        total_lidos,

                    "registros_processados":
                        total_processados,

                    "registros_erro":
                        total_erros,

                    "status": "erro",

                    "mensagem":
                        str(erro)[:1000],
                })
                .eq(
                    "id",
                    carga_id,
                )
                .execute()
            )

        raise


if __name__ == "__main__":
    main()