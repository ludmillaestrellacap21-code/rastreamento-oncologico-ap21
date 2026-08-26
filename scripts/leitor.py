"""
leitor.py
Projeto: Monitoramento de Rastreamento Oncológico — AP 21
Leitura do VitaCare (csv) e SISREG (Google Sheets) + cruzamento por CNS
"""

import glob
import pandas as pd
from datetime import date
import sqlite3
import os
from pathlib import Path

# =============================================================================
# CONFIGURAÇÕES
# =============================================================================

ROOT = Path(__file__).resolve().parents[1]
PASTA_VITACARE = str(ROOT / "entrada" / "vitacare")

SISREG_SHEET_ID = "12XKX5LoSvOWylaDUrGYJl6pnFwsb5HzBjQFiGEidUs8"

ABAS_SISREG = {
    "mamografia":   "2046953194",
    "colonoscopia": "0",
}

ABAS_ALT = {
    "citopatologico": "1611187501",
    "sangue_oculto":  "1553183361",
}

DB_PATH = str(ROOT / "banco" / "rastreamento.db")

MAPA_RISCO = {
    "🔵": "Eletivo",
    "🟢": "Medio",
    "🟡": "Alto",
    "🔴": "Urgente",
}

SITUACOES_VALIDAS = [
    "✅ Agendamento Confirmado",
    "❌ Agendamento Falta",
    "📅 Agendada",
]

SITUACOES_VITACARE_VALIDAS = ["ATIVO", "OUTROS"]

FAIXAS = {
    "mamografia":     {"sexo": "F", "idade_min": 50, "idade_max": 69},
    "citopatologico": {"sexo": "F", "idade_min": 25, "idade_max": 64},
    "colonoscopia":   {"sexo": None, "idade_min": 50, "idade_max": 75},
    "sangue_oculto":  {"sexo": None, "idade_min": 50, "idade_max": 75},
}

PRAZO_ANOS = 2

# Colunas que realmente usamos do export do VitaCare.
# Reduz uso de memória em relação a carregar o CSV inteiro (arquivo pode passar de 400MB).
COLUNAS_VITACARE = [
    "N_CNS_DA_PESSOA_CADASTRADA",
    "NOME_DA_PESSOA_CADASTRADA",
    "DATA_DE_NASCIMENTO",
    "SEXO",
    "NOME_UNIDADE_DE_SAUDE",
    "NOME_EQUIPE_DE_SAUDE",
    "CODIGO_MICROAREA",
    "SITUACAO_USUARIO",
]

# =============================================================================
# FUNÇÕES AUXILIARES
# =============================================================================

def encontrar_arquivo_vitacare(pasta):
    """
    Procura o CSV do VitaCare na pasta de entrada.
    O VitaCare inclui a data no nome do arquivo (ex.: '21-2026+SUB_PAV_FICHA_A_V2+21.csv'),
    então não dá pra confiar em um nome fixo. Pega o mais recente pela data de modificação
    caso haja mais de um.
    """
    candidatos = glob.glob(os.path.join(pasta, "*FICHA_A*.csv"))
    if not candidatos:
        raise FileNotFoundError(
            f"Nenhum CSV do VitaCare encontrado em {pasta}. "
            f"Confira se o export foi salvo nessa pasta e se o nome contém 'FICHA_A'."
        )
    if len(candidatos) > 1:
        print(f"   ⚠️  {len(candidatos)} arquivos encontrados, usando o mais recente.")
    return max(candidatos, key=os.path.getmtime)


def calcular_idade(data_nascimento):
    hoje = date.today()
    try:
        dn = pd.to_datetime(data_nascimento, dayfirst=True).date()
        return hoje.year - dn.year - ((hoje.month, hoje.day) < (dn.month, dn.day))
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
    return str(cns).strip().replace(" ", "")


def padronizar_nome(nome):
    if pd.isna(nome):
        return None
    return str(nome).strip().upper()


def calcular_status(situacao, data_agendamento):
    hoje = date.today()

    if situacao in ["✅ Agendamento Confirmado", "Agendamento confirmado"]:
        if pd.notna(data_agendamento) and str(data_agendamento).strip() not in ["", "Não informada"]:
            try:
                dt = pd.to_datetime(data_agendamento, dayfirst=True).date()
                anos_passados = (hoje - dt).days / 365.25
                if anos_passados <= PRAZO_ANOS:
                    return "Em dia"
                else:
                    return "Em atraso"
            except Exception:
                return "Em atraso"
        return "Em atraso"
    elif situacao == "❌ Agendamento Falta":
        return "Falta - Reconvocar"
    elif situacao == "📅 Agendada":
        return "Agendado"
    else:
        return "Nunca realizado"


# =============================================================================
# LEITURA DO VITACARE
# =============================================================================

def ler_vitacare(pasta):
    print("📂 Lendo VitaCare...")

    caminho = encontrar_arquivo_vitacare(pasta)
    print(f"   Arquivo: {os.path.basename(caminho)}")

    df = pd.read_csv(
        caminho,
        dtype=str,
        encoding="latin1",
        sep=";",
        usecols=COLUNAS_VITACARE,
    )

    df = df.rename(columns={
        "N_CNS_DA_PESSOA_CADASTRADA": "cns",
        "NOME_DA_PESSOA_CADASTRADA":  "nome",
        "DATA_DE_NASCIMENTO":         "data_nascimento",
        "SEXO":                       "sexo",
        "NOME_UNIDADE_DE_SAUDE":      "unidade",
        "NOME_EQUIPE_DE_SAUDE":       "equipe",
        "CODIGO_MICROAREA":           "microarea",
        "SITUACAO_USUARIO":           "situacao_usuario",
    })

    df["cns"]              = df["cns"].apply(padronizar_cns)
    df["nome"]             = df["nome"].apply(padronizar_nome)
    df["sexo"]             = df["sexo"].str.strip().str.upper()
    df["idade"]            = df["data_nascimento"].apply(calcular_idade)
    df["situacao_usuario"] = df["situacao_usuario"].str.strip().str.upper()

    df["equipe"] = df["equipe"].fillna("Sem equipe")
    df.loc[df["equipe"].str.strip() == "", "equipe"] = "Sem equipe"

    df = df.dropna(subset=["cns"])

    total_antes = len(df)
    df = df[df["situacao_usuario"].isin(SITUACOES_VITACARE_VALIDAS)].copy()
    print(f"   Filtro situação: {total_antes} → {len(df)} (removidos óbitos, mudanças, etc.)")

    feminino    = df["sexo"] == "F"
    idade_25_64 = (df["idade"] >= 25) & (df["idade"] <= 64)
    idade_50_69 = (df["idade"] >= 50) & (df["idade"] <= 69)
    idade_50_75 = (df["idade"] >= 50) & (df["idade"] <= 75)

    populacao_alvo = (
        (feminino & idade_25_64) |
        (feminino & idade_50_69) |
        idade_50_75
    )

    df = df[populacao_alvo].copy()
    print(f"   ✅ {len(df)} pacientes na população-alvo.")
    return df


# =============================================================================
# LEITURA DO SISREG — FORMATO SISREG (Mamografia e Colonoscopia)
# =============================================================================

def ler_aba_sisreg(nome_programa, gid):
    url = montar_url_sheet(SISREG_SHEET_ID, gid)
    print(f"🌐 Lendo SISREG — {nome_programa}...")

    try:
        df = pd.read_csv(url, dtype=str)
    except Exception as e:
        print(f"   ⚠️  Erro ao ler {nome_programa}: {e}")
        return pd.DataFrame()

    df = df.rename(columns={
        "Código de solicitação": "codigo_solicitacao",
        "Data de solicitação":   "data_solicitacao",
        "Unidade":               "unidade_solicitante",
        "Solicitante":           "solicitante",
        "CNS":                   "cns",
        "Nome do paciente":      "nome",
        "Procedimento":          "procedimento",
        "Risco":                 "risco",
        "Situação":              "situacao",
        "Agendamento":           "data_agendamento",
    })

    df["cns"]      = df["cns"].apply(padronizar_cns)
    df["nome"]     = df["nome"].apply(padronizar_nome)
    df["risco"]    = df["risco"].str.strip().map(MAPA_RISCO).fillna("Nao informado")
    df["situacao"] = df["situacao"].str.strip()
    df["programa"] = nome_programa

    df = df[df["situacao"].isin(SITUACOES_VALIDAS)]
    df = df.dropna(subset=["cns"])

    print(f"   ✅ {len(df)} registros carregados ({nome_programa}).")
    return df


# =============================================================================
# LEITURA DO FORMATO ALTERNATIVO (Citopatológico e Sangue Oculto)
# =============================================================================

def ler_aba_alt(nome_programa, gid):
    url = montar_url_sheet(SISREG_SHEET_ID, gid)
    print(f"🌐 Lendo SISREG — {nome_programa}...")

    try:
        df = pd.read_csv(url, dtype=str)
    except Exception as e:
        print(f"   ⚠️  Erro ao ler {nome_programa}: {e}")
        return pd.DataFrame()

    df.columns = df.columns.str.strip()

    df = df.rename(columns={
        "CNS":         "cns",
        "Nome":        "nome",
        "Unidade":     "unidade_solicitante",
        "Exame":       "procedimento",
        "Entrega":     "data_agendamento",
        "Solicitação": "data_solicitacao",
        "Alterados":   "risco",
        "Devolutiva":  "devolutiva",
    })

    df["cns"]      = df["cns"].apply(padronizar_cns)
    df["nome"]     = df["nome"].apply(padronizar_nome)
    df["programa"] = nome_programa

    df["situacao"] = df["data_agendamento"].apply(
        lambda x: "✅ Agendamento Confirmado" if pd.notna(x) and str(x).strip() != "" else "Sem entrega"
    )

    df["risco"]              = "Nao informado"
    df["codigo_solicitacao"] = None
    df["solicitante"]        = None

    df = df.dropna(subset=["cns"])

    print(f"   ✅ {len(df)} registros carregados ({nome_programa}).")
    return df


# =============================================================================
# LEITURA GERAL DO SISREG
# =============================================================================

def ler_sisreg():
    frames = []

    for programa, gid in ABAS_SISREG.items():
        df = ler_aba_sisreg(programa, gid)
        if not df.empty:
            frames.append(df)

    for programa, gid in ABAS_ALT.items():
        df = ler_aba_alt(programa, gid)
        if not df.empty:
            frames.append(df)

    if not frames:
        print("❌ Nenhum dado carregado do SISREG.")
        return pd.DataFrame()

    df_total = pd.concat(frames, ignore_index=True)
    print(f"\n📊 Total SISREG: {len(df_total)} registros em todos os programas.")
    return df_total


# =============================================================================
# FILTRO POR POPULAÇÃO-ALVO + CRUZAMENTO POR PROGRAMA
# =============================================================================

def filtrar_populacao_alvo(df_vitacare, df_sisreg):
    """
    Para cada programa, filtra a população-alvo do VitaCare
    e cruza APENAS com os registros do SISREG do mesmo programa.
    Isso evita que agendamentos de um programa apareçam em outro.
    """
    print("\n🎯 Filtrando população-alvo e cruzando por programa...")
    frames = []

    for programa, criterio in FAIXAS.items():
        # Filtrar população-alvo do VitaCare para esse programa
        filtro = (
            (df_vitacare["idade"] >= criterio["idade_min"]) &
            (df_vitacare["idade"] <= criterio["idade_max"])
        )
        if criterio["sexo"]:
            filtro &= (df_vitacare["sexo"] == criterio["sexo"])

        df_pop = df_vitacare[filtro].copy()
        df_pop["programa_monitorado"] = programa

        # Filtrar SISREG apenas para esse programa
        if not df_sisreg.empty:
            df_sis_prog = df_sisreg[df_sisreg["programa"] == programa].copy()

            df_sis_prog["data_agendamento"] = pd.to_datetime(
                df_sis_prog["data_agendamento"], dayfirst=True, errors="coerce"
            )

            df_sis_prog = (
                df_sis_prog
                .sort_values("data_agendamento", ascending=False)
                .drop_duplicates(subset=["cns"])
            )

            # Cruzar VitaCare com SISREG desse programa
            df_prog = df_pop.merge(
                df_sis_prog[[
                    "cns", "situacao", "risco",
                    "data_agendamento", "data_solicitacao",
                    "unidade_solicitante", "procedimento"
                ]],
                on="cns",
                how="left"
            )
        else:
            df_prog = df_pop.copy()
            df_prog["situacao"]            = None
            df_prog["risco"]               = None
            df_prog["data_agendamento"]    = None
            df_prog["data_solicitacao"]    = None
            df_prog["unidade_solicitante"] = None
            df_prog["procedimento"]        = None

        # Preencher sem registro
        df_prog["situacao"] = df_prog["situacao"].fillna("Sem registro")
        df_prog["risco"]    = df_prog["risco"].fillna("Nao informado")
        df_prog["data_agendamento"] = df_prog["data_agendamento"].fillna("Não informada")

        # Calcular status de rastreamento
        df_prog["status_rastreamento"] = df_prog.apply(
            lambda row: calcular_status(row["situacao"], row["data_agendamento"]),
            axis=1
        )

        frames.append(df_prog)
        print(f"   {programa}: {len(df_prog)} pacientes na população-alvo.")

    return pd.concat(frames, ignore_index=True)


# =============================================================================
# SALVAR NO SQLITE
# =============================================================================

def salvar_sqlite(df_vitacare, df_sisreg, df_populacao):
    print(f"\n💾 Salvando no banco: {DB_PATH}")
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)

    # Converter datas para string e substituir vazios por "-"
    for col in ["data_agendamento", "data_solicitacao"]:
        if col in df_populacao.columns:
            df_populacao[col] = df_populacao[col].astype(str).replace(
                {"NaT": "-", "None": "-", "nan": "-", "Não informada": "-"}
            )
        if col in df_sisreg.columns:
            df_sisreg[col] = df_sisreg[col].astype(str).replace(
                {"NaT": "-", "None": "-", "nan": "-"}
            )

    conn = sqlite3.connect(DB_PATH)
    df_vitacare.to_sql("pacientes",       conn, if_exists="replace", index=False)
    df_sisreg.to_sql("agendamentos",      conn, if_exists="replace", index=False)
    df_populacao.to_sql("populacao_alvo", conn, if_exists="replace", index=False)
    conn.close()

    print("   ✅ Banco atualizado com sucesso.")


# =============================================================================
# EXECUÇÃO PRINCIPAL
# =============================================================================

if __name__ == "__main__":
    print("=" * 55)
    print("  Monitoramento de Rastreamento Oncológico — AP 21")
    print("=" * 55)

    df_vitacare  = ler_vitacare(PASTA_VITACARE)
    df_sisreg    = ler_sisreg()
    df_populacao = filtrar_populacao_alvo(df_vitacare, df_sisreg)
    salvar_sqlite(df_vitacare, df_sisreg, df_populacao)

    print("\n✅ Processamento concluído!")
    print(f"   Banco disponível em: {DB_PATH}")