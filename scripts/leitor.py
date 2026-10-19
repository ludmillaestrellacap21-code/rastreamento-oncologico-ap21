"""
leitor.py

Projeto: Monitoramento de Rastreamento Oncológico — AP 2.1

Leitura do VitaCare (CSV) e SISREG (Google Sheets)
+ cruzamento por CNS.
"""

import glob
import os
import re
import sqlite3
import unicodedata
from datetime import date
from pathlib import Path

import pandas as pd


# =============================================================================
# CONFIGURAÇÕES
# =============================================================================

ROOT = Path(__file__).resolve().parents[1]

PASTA_VITACARE = str(ROOT / "entrada" / "vitacare")

SISREG_SHEET_ID = "12XKX5LoSvOWylaDUrGYJl6pnFwsb5HzBjQFiGEidUs8"

ABAS_SISREG = {
    "mamografia": "2046953194",
    "colonoscopia": "0",
}

ABAS_ALT = {
    "citopatologico": "1611187501",
    "sangue_oculto": "1553183361",
}

DB_PATH = str(ROOT / "banco" / "rastreamento.db")


MAPA_RISCO = {
    "🔵": "Eletivo",
    "🟢": "Medio",
    "🟡": "Alto",
    "🔴": "Urgente",
}


# O VitaCare atual utiliza códigos:
# A = Ativo
# O = Outros
# T / I não entram na população válida.
SITUACOES_VITACARE_VALIDAS = ["A", "O"]


FAIXAS = {
    "mamografia": {
        "sexo": "F",
        "idade_min": 50,
        "idade_max": 69,
    },
    "citopatologico": {
        "sexo": "F",
        "idade_min": 25,
        "idade_max": 64,
    },
    "colonoscopia": {
        "sexo": None,
        "idade_min": 50,
        "idade_max": 75,
    },
    "sangue_oculto": {
        "sexo": None,
        "idade_min": 50,
        "idade_max": 75,
    },
}


PRAZO_ANOS = 2


# Colunas utilizadas no export do VitaCare.
COLUNAS_VITACARE = [
    "N CNS DA PESSOA CADASTRADA",
    "NOME DA PESSOA CADASTRADA",
    "DATA DE NASCIMENTO",
    "SEXO",
    "NOME UNIDADE DE SAUDE",
    "NOME EQUIPE DE SAUDE",
    "CODIGO MICROAREA",
    "SITUACAO USUARIO",
]


# =============================================================================
# FUNÇÕES AUXILIARES
# =============================================================================

def normalizar_texto(valor):
    """
    Remove acentos, emojis e diferenças de caixa para comparações.
    """
    if pd.isna(valor):
        return ""

    valor = str(valor).strip()

    valor = unicodedata.normalize("NFKD", valor)

    valor = "".join(
        caractere
        for caractere in valor
        if not unicodedata.combining(caractere)
    )

    valor = valor.encode(
        "ascii",
        errors="ignore"
    ).decode("ascii")

    return valor.upper().strip()


def normalizar_coluna(nome):
    """
    Transforma nomes de colunas em formato padronizado.

    Exemplo:
    'Situação' -> 'SITUACAO'
    'Código de solicitação' -> 'CODIGO_DE_SOLICITACAO'
    """
    nome = normalizar_texto(nome)

    nome = re.sub(
        r"[^A-Z0-9]+",
        "_",
        nome
    )

    return nome.strip("_")


def encontrar_arquivo_vitacare(pasta):
    """
    Procura o CSV do VitaCare na pasta de entrada.

    Se houver mais de um FICHA_A, utiliza o arquivo
    com data de modificação mais recente.
    """
    candidatos = glob.glob(
        os.path.join(
            pasta,
            "*FICHA_A*.csv"
        )
    )

    if not candidatos:
        raise FileNotFoundError(
            f"Nenhum CSV do VitaCare encontrado em {pasta}. "
            "Confira se o arquivo está na pasta e se o nome "
            "contém 'FICHA_A'."
        )

    if len(candidatos) > 1:
        print(
            f"   ATENÇÃO: {len(candidatos)} arquivos encontrados. "
            "Será utilizado o mais recente."
        )

    return max(
        candidatos,
        key=os.path.getmtime
    )


def calcular_idade(data_nascimento):
    hoje = date.today()

    try:
        dn = pd.to_datetime(
            data_nascimento,
            dayfirst=True
        ).date()

        return (
            hoje.year
            - dn.year
            - (
                (hoje.month, hoje.day)
                < (dn.month, dn.day)
            )
        )

    except Exception:
        return None


def montar_url_sheet(sheet_id, gid):
    return (
        f"https://docs.google.com/spreadsheets/d/{sheet_id}"
        f"/export?format=csv&gid={gid}"
    )


def padronizar_cns(cns):
    if pd.isna(cns):
        return None

    cns = str(cns).strip().replace(" ", "")

    if not cns:
        return None

    return cns


def padronizar_nome(nome):
    if pd.isna(nome):
        return None

    return str(nome).strip().upper()


def calcular_status(situacao, data_agendamento):
    """
    Calcula o status do rastreamento sem depender
    de emoji ou acentuação da situação original.
    """
    hoje = date.today()

    situacao_norm = normalizar_texto(
        situacao
    )

    if "AGENDAMENTO CONFIRMADO" in situacao_norm:

        if (
            pd.notna(data_agendamento)
            and str(data_agendamento).strip()
            not in [
                "",
                "-",
                "Não informada",
                "Nao informada",
            ]
        ):
            try:
                dt = pd.to_datetime(
                    data_agendamento,
                    dayfirst=True
                ).date()

                anos_passados = (
                    hoje - dt
                ).days / 365.25

                if anos_passados <= PRAZO_ANOS:
                    return "Em dia"

                return "Em atraso"

            except Exception:
                return "Em atraso"

        return "Em atraso"

    if "AGENDAMENTO FALTA" in situacao_norm:
        return "Falta - Reconvocar"

    if (
        "AGENDADA" in situacao_norm
        or "AGENDADO" in situacao_norm
    ):
        return "Agendado"

    return "Nunca realizado"


# =============================================================================
# LEITURA DO VITACARE
# =============================================================================

def ler_vitacare(pasta):

    print("\nLendo VitaCare...")

    caminho = encontrar_arquivo_vitacare(
        pasta
    )

    print(
        f"   Arquivo: "
        f"{os.path.basename(caminho)}"
    )

    df = pd.read_csv(
        caminho,
        dtype=str,
        encoding="latin1",
        sep=";",
        usecols=COLUNAS_VITACARE,
        low_memory=False,
    )

    df = df.rename(
        columns={
            "N CNS DA PESSOA CADASTRADA":
                "cns",

            "NOME DA PESSOA CADASTRADA":
                "nome",

            "DATA DE NASCIMENTO":
                "data_nascimento",

            "SEXO":
                "sexo",

            "NOME UNIDADE DE SAUDE":
                "unidade",

            "NOME EQUIPE DE SAUDE":
                "equipe",

            "CODIGO MICROAREA":
                "microarea",

            "SITUACAO USUARIO":
                "situacao_usuario",
        }
    )

    df["cns"] = df[
        "cns"
    ].apply(
        padronizar_cns
    )

    df["nome"] = df[
        "nome"
    ].apply(
        padronizar_nome
    )

    df["sexo"] = (
        df["sexo"]
        .fillna("")
        .str.strip()
        .str.upper()
    )

    df["idade"] = df[
        "data_nascimento"
    ].apply(
        calcular_idade
    )

    df["situacao_usuario"] = (
        df["situacao_usuario"]
        .fillna("")
        .str.strip()
        .str.upper()
    )

    df["equipe"] = (
        df["equipe"]
        .fillna("Sem equipe")
    )

    df.loc[
        df["equipe"]
        .astype(str)
        .str.strip()
        .eq(""),
        "equipe"
    ] = "Sem equipe"

    df = df.dropna(
        subset=["cns"]
    )

    df = df[
        df["cns"]
        .astype(str)
        .str.strip()
        .ne("")
    ].copy()

    total_antes = len(df)

    df = df[
        df[
            "situacao_usuario"
        ].isin(
            SITUACOES_VITACARE_VALIDAS
        )
    ].copy()

    print(
        f"   Filtro situação: "
        f"{total_antes} -> {len(df)} "
        "(removidos óbitos, mudanças, etc.)"
    )

    feminino = (
        df["sexo"] == "F"
    )

    idade_25_64 = (
        (df["idade"] >= 25)
        & (df["idade"] <= 64)
    )

    idade_50_69 = (
        (df["idade"] >= 50)
        & (df["idade"] <= 69)
    )

    idade_50_75 = (
        (df["idade"] >= 50)
        & (df["idade"] <= 75)
    )

    populacao_alvo = (
        (feminino & idade_25_64)
        |
        (feminino & idade_50_69)
        |
        idade_50_75
    )

    df = df[
        populacao_alvo
    ].copy()

    print(
        f"   OK: {len(df)} pacientes "
        "na população-alvo."
    )

    return df


# =============================================================================
# LEITURA DO SISREG
# Mamografia e Colonoscopia
# =============================================================================

def ler_aba_sisreg(
    nome_programa,
    gid
):

    url = montar_url_sheet(
        SISREG_SHEET_ID,
        gid
    )

    print(
        f"\nLendo SISREG - "
        f"{nome_programa}..."
    )

    try:
        df = pd.read_csv(
            url,
            dtype=str
        )

    except Exception as e:
        print(
            f"   Erro ao ler "
            f"{nome_programa}: {e}"
        )

        return pd.DataFrame()

    # ---------------------------------------------------------
    # Normalizar nomes das colunas
    # ---------------------------------------------------------

    df.columns = [
        normalizar_coluna(
            coluna
        )
        for coluna in df.columns
    ]

    mapa_colunas = {
        "CODIGO_DE_SOLICITACAO":
            "codigo_solicitacao",

        "DATA_DE_SOLICITACAO":
            "data_solicitacao",

        "UNIDADE":
            "unidade_solicitante",

        "SOLICITANTE":
            "solicitante",

        "CNS":
            "cns",

        "NOME_DO_PACIENTE":
            "nome",

        "PROCEDIMENTO":
            "procedimento",

        "RISCO":
            "risco",

        "SITUACAO":
            "situacao",

        "AGENDAMENTO":
            "data_agendamento",
    }

    df = df.rename(
        columns=mapa_colunas
    )

    # ---------------------------------------------------------
    # Conferência das colunas essenciais
    # ---------------------------------------------------------

    obrigatorias = [
        "cns",
        "nome",
        "situacao",
    ]

    faltando = [
        coluna
        for coluna in obrigatorias
        if coluna not in df.columns
    ]

    if faltando:

        print(
            f"   Colunas ausentes em "
            f"{nome_programa}: "
            + ", ".join(faltando)
        )

        print(
            "   Colunas recebidas:",
            list(df.columns)
        )

        return pd.DataFrame()

    # ---------------------------------------------------------
    # Criar colunas opcionais se não existirem
    # ---------------------------------------------------------

    opcionais = {
        "codigo_solicitacao":
            None,

        "data_solicitacao":
            None,

        "unidade_solicitante":
            None,

        "solicitante":
            None,

        "procedimento":
            None,

        "risco":
            None,

        "data_agendamento":
            None,
    }

    for coluna, valor in opcionais.items():

        if coluna not in df.columns:
            df[coluna] = valor

    # ---------------------------------------------------------
    # Padronização
    # ---------------------------------------------------------

    df["cns"] = df[
        "cns"
    ].apply(
        padronizar_cns
    )

    df["nome"] = df[
        "nome"
    ].apply(
        padronizar_nome
    )

    risco_original = (
        df["risco"]
        .fillna("")
        .astype(str)
        .str.strip()
    )

    df["risco"] = (
        risco_original
        .map(MAPA_RISCO)
    )

    # Se não for somente emoji,
    # preserva o texto original.
    df["risco"] = (
        df["risco"]
        .fillna(
            risco_original
        )
        .replace(
            "",
            "Nao informado"
        )
    )

    df["situacao"] = (
        df["situacao"]
        .fillna("")
        .astype(str)
        .str.strip()
    )

    df["programa"] = (
        nome_programa
    )

    # ---------------------------------------------------------
    # Situações válidas
    # Não depende de emoji ou acento
    # ---------------------------------------------------------

    situacao_norm = (
        df["situacao"]
        .apply(
            normalizar_texto
        )
    )

    validas = (
        situacao_norm
        .str.contains(
            "AGENDAMENTO CONFIRMADO",
            na=False
        )
        |
        situacao_norm
        .str.contains(
            "AGENDAMENTO FALTA",
            na=False
        )
        |
        situacao_norm
        .str.contains(
            "AGENDADA",
            na=False
        )
        |
        situacao_norm
        .str.contains(
            "AGENDADO",
            na=False
        )
    )

    df = df[
        validas
    ].copy()

    df = df.dropna(
        subset=["cns"]
    )

    df = df[
        df["cns"]
        .astype(str)
        .str.strip()
        .ne("")
    ].copy()

    print(
        f"   OK: {len(df)} registros "
        f"carregados ({nome_programa})."
    )

    return df


# =============================================================================
# LEITURA DO FORMATO ALTERNATIVO
# Citopatológico e Sangue Oculto
# =============================================================================

def ler_aba_alt(
    nome_programa,
    gid
):

    url = montar_url_sheet(
        SISREG_SHEET_ID,
        gid
    )

    print(
        f"\nLendo planilha - "
        f"{nome_programa}..."
    )

    try:
        df = pd.read_csv(
            url,
            dtype=str
        )

    except Exception as e:

        print(
            f"   Erro ao ler "
            f"{nome_programa}: {e}"
        )

        return pd.DataFrame()

    # ---------------------------------------------------------
    # Normalização das colunas
    # ---------------------------------------------------------

    df.columns = [
        normalizar_coluna(
            coluna
        )
        for coluna in df.columns
    ]

    mapa_colunas = {
        "CNS":
            "cns",

        "NOME":
            "nome",

        "UNIDADE":
            "unidade_solicitante",

        "EXAME":
            "procedimento",

        "ENTREGA":
            "data_agendamento",

        "SOLICITACAO":
            "data_solicitacao",

        "ALTERADOS":
            "risco",

        "DEVOLUTIVA":
            "devolutiva",
    }

    df = df.rename(
        columns=mapa_colunas
    )

    # ---------------------------------------------------------
    # Conferência mínima
    # ---------------------------------------------------------

    obrigatorias = [
        "cns",
        "nome",
    ]

    faltando = [
        coluna
        for coluna in obrigatorias
        if coluna not in df.columns
    ]

    if faltando:

        print(
            f"   Colunas ausentes em "
            f"{nome_programa}: "
            + ", ".join(faltando)
        )

        print(
            "   Colunas recebidas:",
            list(df.columns)
        )

        return pd.DataFrame()

    opcionais = {
        "unidade_solicitante":
            None,

        "procedimento":
            None,

        "data_agendamento":
            None,

        "data_solicitacao":
            None,

        "risco":
            None,

        "devolutiva":
            None,
    }

    for coluna, valor in opcionais.items():

        if coluna not in df.columns:
            df[coluna] = valor

    # ---------------------------------------------------------
    # Padronização
    # ---------------------------------------------------------

    df["cns"] = df[
        "cns"
    ].apply(
        padronizar_cns
    )

    df["nome"] = df[
        "nome"
    ].apply(
        padronizar_nome
    )

    df["programa"] = (
        nome_programa
    )

    df["situacao"] = (
        df["data_agendamento"]
        .apply(
            lambda x:
            "Agendamento Confirmado"
            if (
                pd.notna(x)
                and str(x).strip()
                not in ["", "-", "nan"]
            )
            else "Sem entrega"
        )
    )

    df["risco"] = (
        df["risco"]
        .fillna("Nao informado")
    )

    df["codigo_solicitacao"] = (
        None
    )

    df["solicitante"] = (
        None
    )

    df = df.dropna(
        subset=["cns"]
    )

    df = df[
        df["cns"]
        .astype(str)
        .str.strip()
        .ne("")
    ].copy()

    print(
        f"   OK: {len(df)} registros "
        f"carregados ({nome_programa})."
    )

    return df


# =============================================================================
# LEITURA GERAL DO SISREG
# =============================================================================

def ler_sisreg():

    frames = []

    # Mamografia e colonoscopia
    for programa, gid in (
        ABAS_SISREG.items()
    ):

        df = ler_aba_sisreg(
            programa,
            gid
        )

        if not df.empty:
            frames.append(df)

    # Citopatológico e sangue oculto
    for programa, gid in (
        ABAS_ALT.items()
    ):

        df = ler_aba_alt(
            programa,
            gid
        )

        if not df.empty:
            frames.append(df)

    if not frames:

        print(
            "\nATENÇÃO: Nenhum dado "
            "carregado do SISREG."
        )

        # Retorna estrutura vazia
        # com as colunas esperadas.
        return pd.DataFrame(
            columns=[
                "codigo_solicitacao",
                "data_solicitacao",
                "unidade_solicitante",
                "solicitante",
                "cns",
                "nome",
                "procedimento",
                "risco",
                "situacao",
                "data_agendamento",
                "programa",
            ]
        )

    df_total = pd.concat(
        frames,
        ignore_index=True
    )

    print(
        f"\nTotal SISREG/planilhas: "
        f"{len(df_total)} registros."
    )

    return df_total


# =============================================================================
# FILTRO POR POPULAÇÃO-ALVO
# + CRUZAMENTO POR PROGRAMA
# =============================================================================

def filtrar_populacao_alvo(
    df_vitacare,
    df_sisreg
):

    """
    Para cada programa:

    1. Filtra a população-alvo do VitaCare.
    2. Filtra o SISREG apenas para o mesmo programa.
    3. Cruza os registros pelo CNS.

    Isso evita que registros de um programa
    apareçam em outro.
    """

    print(
        "\nFiltrando população-alvo "
        "e cruzando por programa..."
    )

    frames = []

    for programa, criterio in (
        FAIXAS.items()
    ):

        # -----------------------------------------------------
        # População-alvo VitaCare
        # -----------------------------------------------------

        filtro = (
            (
                df_vitacare["idade"]
                >= criterio["idade_min"]
            )
            &
            (
                df_vitacare["idade"]
                <= criterio["idade_max"]
            )
        )

        if criterio["sexo"]:

            filtro &= (
                df_vitacare["sexo"]
                == criterio["sexo"]
            )

        df_pop = (
            df_vitacare[
                filtro
            ].copy()
        )

        df_pop[
            "programa_monitorado"
        ] = programa

        # -----------------------------------------------------
        # SISREG do mesmo programa
        # -----------------------------------------------------

        if (
            not df_sisreg.empty
            and "programa"
            in df_sisreg.columns
        ):

            df_sis_prog = (
                df_sisreg[
                    df_sisreg[
                        "programa"
                    ]
                    == programa
                ]
                .copy()
            )

        else:
            df_sis_prog = (
                pd.DataFrame()
            )

        # -----------------------------------------------------
        # Cruzamento
        # -----------------------------------------------------

        if not df_sis_prog.empty:

            df_sis_prog[
                "data_agendamento"
            ] = pd.to_datetime(
                df_sis_prog[
                    "data_agendamento"
                ],
                dayfirst=True,
                errors="coerce",
            )

            df_sis_prog = (
                df_sis_prog
                .sort_values(
                    "data_agendamento",
                    ascending=False,
                )
                .drop_duplicates(
                    subset=["cns"]
                )
            )

            colunas_merge = [
                "cns",
                "situacao",
                "risco",
                "data_agendamento",
                "data_solicitacao",
                "unidade_solicitante",
                "procedimento",
            ]

            # Garante todas as colunas.
            for coluna in (
                colunas_merge
            ):

                if (
                    coluna
                    not in
                    df_sis_prog.columns
                ):
                    df_sis_prog[
                        coluna
                    ] = None

            df_prog = (
                df_pop.merge(
                    df_sis_prog[
                        colunas_merge
                    ],
                    on="cns",
                    how="left",
                )
            )

        else:

            df_prog = (
                df_pop.copy()
            )

            df_prog[
                "situacao"
            ] = None

            df_prog[
                "risco"
            ] = None

            df_prog[
                "data_agendamento"
            ] = None

            df_prog[
                "data_solicitacao"
            ] = None

            df_prog[
                "unidade_solicitante"
            ] = None

            df_prog[
                "procedimento"
            ] = None

        # -----------------------------------------------------
        # Sem registro
        # -----------------------------------------------------

        df_prog[
            "situacao"
        ] = (
            df_prog[
                "situacao"
            ]
            .fillna(
                "Sem registro"
            )
        )

        df_prog[
            "risco"
        ] = (
            df_prog[
                "risco"
            ]
            .fillna(
                "Nao informado"
            )
        )

        df_prog[
            "data_agendamento"
        ] = (
            df_prog[
                "data_agendamento"
            ]
            .fillna(
                "Não informada"
            )
        )

        # -----------------------------------------------------
        # Status do rastreamento
        # -----------------------------------------------------

        df_prog[
            "status_rastreamento"
        ] = df_prog.apply(
            lambda row:
            calcular_status(
                row["situacao"],
                row[
                    "data_agendamento"
                ],
            ),
            axis=1,
        )

        frames.append(
            df_prog
        )

        print(
            f"   {programa}: "
            f"{len(df_prog)} pacientes "
            "na população-alvo."
        )

    if not frames:
        return pd.DataFrame()

    return pd.concat(
        frames,
        ignore_index=True
    )


# =============================================================================
# SALVAR NO SQLITE
# =============================================================================

def salvar_sqlite(
    df_vitacare,
    df_sisreg,
    df_populacao
):

    print(
        f"\nSalvando no banco: "
        f"{DB_PATH}"
    )

    os.makedirs(
        os.path.dirname(
            DB_PATH
        ),
        exist_ok=True,
    )

    # ---------------------------------------------------------
    # Datas da população-alvo
    # ---------------------------------------------------------

    for coluna in [
        "data_agendamento",
        "data_solicitacao",
    ]:

        if coluna in (
            df_populacao.columns
        ):

            df_populacao[
                coluna
            ] = (
                df_populacao[
                    coluna
                ]
                .astype(str)
                .replace(
                    {
                        "NaT": "-",
                        "None": "-",
                        "nan": "-",
                        "Não informada": "-",
                        "Nao informada": "-",
                    }
                )
            )

        if coluna in (
            df_sisreg.columns
        ):

            df_sisreg[
                coluna
            ] = (
                df_sisreg[
                    coluna
                ]
                .astype(str)
                .replace(
                    {
                        "NaT": "-",
                        "None": "-",
                        "nan": "-",
                    }
                )
            )

    conn = sqlite3.connect(
        DB_PATH
    )

    try:

        df_vitacare.to_sql(
            "pacientes",
            conn,
            if_exists="replace",
            index=False,
        )

        df_sisreg.to_sql(
            "agendamentos",
            conn,
            if_exists="replace",
            index=False,
        )

        df_populacao.to_sql(
            "populacao_alvo",
            conn,
            if_exists="replace",
            index=False,
        )

        conn.commit()

    finally:
        conn.close()

    print(
        "   OK: Banco atualizado "
        "com sucesso."
    )


# =============================================================================
# EXECUÇÃO PRINCIPAL
# =============================================================================

if __name__ == "__main__":

    print(
        "=" * 60
    )

    print(
        "Monitoramento de Rastreamento "
        "Oncológico — AP 2.1"
    )

    print(
        "=" * 60
    )

    df_vitacare = (
        ler_vitacare(
            PASTA_VITACARE
        )
    )

    df_sisreg = (
        ler_sisreg()
    )

    df_populacao = (
        filtrar_populacao_alvo(
            df_vitacare,
            df_sisreg,
        )
    )

    salvar_sqlite(
        df_vitacare,
        df_sisreg,
        df_populacao,
    )

    print(
        "\nProcessamento concluído!"
    )

    print(
        f"Banco disponível em: "
        f"{DB_PATH}"
    )