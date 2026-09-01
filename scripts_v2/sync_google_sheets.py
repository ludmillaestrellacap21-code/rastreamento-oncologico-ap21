import hashlib
import json
import os
import re
import unicodedata
from datetime import datetime

import gspread
from google.oauth2.service_account import Credentials
import requests
import time

from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry


SUPABASE_URL = os.environ["SUPABASE_URL"]
SUPABASE_KEY = os.environ["SUPABASE_SERVICE_ROLE_KEY"]
SUPABASE_REST_URL = (
    SUPABASE_URL.rstrip("/")
    + "/rest/v1"
)

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


BATCH_SIZE = 100


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
    import time

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

        enviado = False

        for tentativa in range(1, 6):

            try:
                supabase.table(
                    "staging_google_sheets"
                ).upsert(
                    lote,
                    on_conflict="fonte,chave_origem",
                ).execute()

                enviado = True

                print(
                    f"Enviados "
                    f"{min(inicio + BATCH_SIZE, total)} "
                    f"de {total}"
                )

                break

            except Exception as erro:

                print(
                    f"Tentativa {tentativa}/5 falhou "
                    f"no lote iniciado em {inicio}: "
                    f"{type(erro).__name__}"
                )

                if tentativa == 5:
                    raise

                espera = tentativa * 3

                print(
                    f"Aguardando {espera}s "
                    f"antes de tentar novamente..."
                )

                time.sleep(espera)

        if not enviado:
            raise RuntimeError(
                f"Não foi possível enviar o lote "
                f"iniciado em {inicio}"
            )

def criar_sessao_supabase():

    retry = Retry(
        total=5,
        connect=5,
        read=5,
        backoff_factor=2,
        status_forcelist=[
            429,
            500,
            502,
            503,
            504,
        ],
        allowed_methods=[
            "GET",
            "POST",
            "PATCH",
            "DELETE",
        ],
    )

    adapter = HTTPAdapter(
        max_retries=retry
    )

    sessao = requests.Session()

    sessao.mount(
        "https://",
        adapter,
    )

    sessao.headers.update({
        "apikey": SUPABASE_KEY,
        "Authorization":
            f"Bearer {SUPABASE_KEY}",
        "Content-Type":
            "application/json",
    })

    return sessao


def inserir_historico(
    sessao,
    dados,
):

    url = (
        f"{SUPABASE_REST_URL}"
        f"/historico_cargas"
    )

    resposta = sessao.post(
        url,
        params={
            "select": "id"
        },
        headers={
            "Prefer":
                "return=representation"
        },
        json=dados,
        timeout=60,
    )

    resposta.raise_for_status()

    resultado = resposta.json()

    if resultado:
        return resultado[0]["id"]

    return None


def atualizar_historico(
    sessao,
    carga_id,
    dados,
):

    if not carga_id:
        return

    url = (
        f"{SUPABASE_REST_URL}"
        f"/historico_cargas"
    )

    resposta = sessao.patch(
        url,
        params={
            "id": f"eq.{carga_id}"
        },
        headers={
            "Prefer":
                "return=minimal"
        },
        json=dados,
        timeout=60,
    )

    resposta.raise_for_status()


def enviar_lote_supabase(
    sessao,
    lote,
):

    url = (
        f"{SUPABASE_REST_URL}"
        f"/staging_google_sheets"
    )

    resposta = sessao.post(
        url,
        params={
            "on_conflict":
                "fonte,chave_origem"
        },
        headers={
            "Prefer":
                "resolution=merge-duplicates,"
                "return=minimal"
        },
        json=lote,
        timeout=120,
    )

    resposta.raise_for_status()
        
def main():
    print(
        "INICIANDO SINCRONIZAÇÃO GOOGLE SHEETS"
    )

    sessao = criar_sessao_supabase()

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

    carga_id = inserir_historico(
    sessao,
    {
        "fonte": "Google Sheets",
        "competencia":
            datetime.now().strftime(
                "%Y-%m"
            ),
        "status": "processando",
    },
)

print(
    f"Carga iniciada. ID: "
    f"{carga_id}"
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

        def upsert_lotes(
    sessao,
    todos,
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

        for tentativa in range(1, 6):

            try:

                enviar_lote_supabase(
                    sessao,
                    lote,
                )

                print(
                    f"Enviados "
                    f"{min(inicio + BATCH_SIZE, total)} "
                    f"de {total}"
                )

                break

            except Exception as erro:

                print(
                    f"Tentativa "
                    f"{tentativa}/5 "
                    f"falhou: "
                    f"{type(erro).__name__}"
                )

                if tentativa == 5:
                    raise

                espera = tentativa * 3

                print(
                    f"Aguardando "
                    f"{espera}s..."
                )

                time.sleep(
                    espera
                )

    atualizar_historico(
    sessao,
    carga_id,
    {
        "fim_em":
            datetime.utcnow().isoformat(),

        "registros_lidos":
            total_lidos,

        "registros_processados":
            total_processados,

        "registros_erro":
            total_erros,

        "status":
            "erro",

        "mensagem":
            str(erro)[:1000],
    },
)

        raise


if __name__ == "__main__":
    main()