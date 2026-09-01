"""Sincroniza o SQLite com o Supabase aplicando as regras v2 do rastreamento.

Regras usadas:
- Mamografia: mulheres de 50 a 74 anos; prazo de 2 anos.
- Citopatologico: mulheres de 25 a 64 anos; prazo de 3 anos.
- Sangue oculto: 50 a 75 anos; prazo de 2 anos.
- Colonoscopia: acompanhamento/seguimento; somente quem possui registro de
  colonoscopia no SISREG. Nao e gerada como populacao-alvo universal.

Importante: agendamento confirmado NÃO é tratado como exame realizado.
A rotina manual atualiza população, elegibilidade, eventos e fluxo operacional.
A situação temporal do painel é calculada apenas a partir de data comprovada de realização.

Uso:
    py scripts_v2/supabase_sync.py --test
    py scripts_v2/supabase_sync.py --reset-tracking
    py scripts_v2/supabase_sync.py
"""
from __future__ import annotations

import argparse
import hashlib
import os
import sqlite3
import time
from datetime import date, datetime

import pandas as pd
from supabase import create_client

from config import DB_PATH, SUPABASE_URL, SUPABASE_SECRET_KEY

BATCH_SIZE = 250
MAX_RETRIES = 6

REGRAS = {
    "mamografia": {
        "nome": "Mamografia",
        "sexo": "F",
        "idade_min": 50,
        "idade_max": 74,
        "prazo_anos": 2,
        "populacional": True,
    },
    "citopatologico": {
        "nome": "Citopatológico",
        "sexo": "F",
        "idade_min": 25,
        "idade_max": 64,
        "prazo_anos": 3,
        "populacional": True,
    },
    "sangue_oculto": {
        "nome": "Sangue oculto nas fezes",
        "sexo": None,
        "idade_min": 50,
        "idade_max": 75,
        "prazo_anos": 2,
        "populacional": True,
    },
    "colonoscopia": {
        "nome": "Colonoscopia (seguimento)",
        "sexo": None,
        "idade_min": 0,
        "idade_max": 120,
        "prazo_anos": 0,  # 0 = sem periodicidade populacional fixa neste projeto
        "populacional": False,
    },
}


def norm_date(v):
    if v is None or pd.isna(v):
        return None
    if isinstance(v, (pd.Timestamp, datetime, date)):
        return pd.Timestamp(v).date().isoformat()
    s = str(v).strip()
    if not s or s in {"-", "nan", "NaT", "None", "Não informada"}:
        return None
    if len(s) >= 10 and s[4:5] == "-" and s[7:8] == "-":
        d = pd.to_datetime(s, errors="coerce")
    else:
        d = pd.to_datetime(s, dayfirst=True, errors="coerce")
    return None if pd.isna(d) else d.date().isoformat()


def val(v):
    if v is None or pd.isna(v):
        return None
    s = str(v).strip()
    return None if s in {"", "-", "nan", "NaT", "None"} else s


def chunks(records, size=BATCH_SIZE):
    for i in range(0, len(records), size):
        yield records[i : i + size]


def client():
    if not SUPABASE_URL or not SUPABASE_SECRET_KEY:
        raise RuntimeError("Configure SUPABASE_URL e SUPABASE_SECRET_KEY no .env")
    return create_client(SUPABASE_URL, SUPABASE_SECRET_KEY)


def read_sqlite():
    if not DB_PATH.exists():
        raise FileNotFoundError(f"Banco SQLite não encontrado: {DB_PATH}")
    con = sqlite3.connect(DB_PATH)
    try:
        pacientes = pd.read_sql("select * from pacientes", con)
        ag = pd.read_sql("select * from agendamentos", con)
    finally:
        con.close()
    return pacientes, ag


def upsert_com_retry(sb, tabela, dados, conflito, tentativas=MAX_RETRIES):
    if not dados:
        return None
    for tentativa in range(1, tentativas + 1):
        try:
            return sb.table(tabela).upsert(dados, on_conflict=conflito).execute()
        except Exception as exc:
            if tentativa >= tentativas:
                print(f"\nERRO definitivo em {tabela} após {tentativas} tentativas.")
                raise
            espera = min(5 * tentativa, 30)
            print(
                f"\nFalha temporária em {tabela} "
                f"(tentativa {tentativa}/{tentativas}). Nova tentativa em {espera}s..."
            )
            print(f"Motivo: {type(exc).__name__}: {exc}")
            time.sleep(espera)


def enviar_em_lotes(sb, tabela, rows, conflito, rotulo=None):
    total = len(rows)
    rotulo = rotulo or tabela
    if total == 0:
        print(f"{rotulo}: nenhum registro para enviar.")
        return
    print(f"\n{rotulo}: {total:,} registros preparados.")
    for numero_lote, lote in enumerate(chunks(rows), start=1):
        upsert_com_retry(sb, tabela, lote, conflito)
        processados = min(numero_lote * BATCH_SIZE, total)
        if numero_lote % 10 == 0 or processados == total:
            percentual = (processados / total) * 100
            print(f"{rotulo}: {processados:,}/{total:,} ({percentual:.1f}%)")


def buscar_ids_pacientes(sb):
    ids = {}
    offset = 0
    print("\nLendo IDs de pacientes do Supabase...")
    while True:
        res = (
            sb.table("pacientes")
            .select("id,cns")
            .range(offset, offset + 999)
            .execute()
            .data
        )
        if not res:
            break
        ids.update({str(x["cns"]).strip(): x["id"] for x in res})
        if len(res) < 1000:
            break
        offset += 1000
        if offset % 50000 == 0:
            print(f"IDs carregados: {len(ids):,}")
    print(f"IDs de pacientes disponíveis: {len(ids):,}")
    return ids


def idade_atual(row):
    v = row.get("idade")
    if pd.notna(v):
        try:
            return int(float(v))
        except (TypeError, ValueError):
            pass
    dn = pd.to_datetime(row.get("data_nascimento"), dayfirst=True, errors="coerce")
    if pd.isna(dn):
        return None
    hoje = date.today()
    d = dn.date()
    return hoje.year - d.year - ((hoje.month, hoje.day) < (d.month, d.day))


def calcular_fluxo(situacao):
    situacao = val(situacao) or "Sem movimentação"
    mapa = {
        "✅ Agendamento Confirmado": "Confirmado",
        "Agendamento confirmado": "Confirmado",
        "❌ Agendamento Falta": "Falta - Reconvocar",
        "📅 Agendada": "Agendado",
        "⏳ Pendente Regulação": "Pendente regulação",
        "❌ Agendamento Cancelado": "Cancelado",
        "❌ Cancelada": "Cancelado",
        "↩️ Devolvida": "Devolvido",
        "🔄 Reenviada": "Reenviado",
        "🚫 Negada": "Negado",
        "◾ Óbito": "Óbito",
    }
    return mapa.get(situacao, situacao)


def ultimo_evento_por_programa(ag, programa):
    if ag.empty or "programa" not in ag.columns:
        return pd.DataFrame()
    x = ag[ag["programa"].astype(str).str.strip() == programa].copy()
    if x.empty:
        return x
    x["cns"] = x["cns"].astype(str).str.strip()
    x["_dt_ag"] = pd.to_datetime(x.get("data_agendamento"), dayfirst=True, errors="coerce")
    x["_dt_sol"] = pd.to_datetime(x.get("data_solicitacao"), dayfirst=True, errors="coerce")
    x["_ord"] = x["_dt_ag"].fillna(x["_dt_sol"])
    x = x.sort_values("_ord", ascending=False).drop_duplicates("cns", keep="first")
    return x


def construir_populacao_corrigida(pacientes, ag):
    """Cria uma linha por CNS + programa com as regras v2."""
    pac = pacientes.copy()
    pac = pac.dropna(subset=["cns"])
    pac["cns"] = pac["cns"].astype(str).str.strip()
    pac = pac[pac["cns"] != ""].drop_duplicates("cns", keep="last")
    pac["idade"] = pac.apply(idade_atual, axis=1)
    pac["sexo"] = pac["sexo"].astype(str).str.strip().str.upper()

    frames = []
    col_eventos = None

    for programa, regra in REGRAS.items():
        ult = ultimo_evento_por_programa(ag, programa)

        if regra["populacional"]:
            filtro = pac["idade"].between(regra["idade_min"], regra["idade_max"], inclusive="both")
            if regra["sexo"]:
                filtro &= pac["sexo"].eq(regra["sexo"])
            pop = pac[filtro].copy()
        else:
            # Colonoscopia: acompanhamento por indicação/registro, não toda a faixa etária.
            if ult.empty:
                continue
            cns_indicados = set(ult["cns"].dropna().astype(str).str.strip())
            pop = pac[pac["cns"].isin(cns_indicados)].copy()
            col_eventos = ult

        pop["programa_monitorado"] = programa

        if not ult.empty:
            cols = [
                "cns", "situacao", "risco", "data_agendamento",
                "data_solicitacao", "unidade_solicitante", "procedimento"
            ]
            cols = [c for c in cols if c in ult.columns]
            pop = pop.merge(ult[cols], on="cns", how="left")
        else:
            for c in ["situacao", "risco", "data_agendamento", "data_solicitacao", "unidade_solicitante", "procedimento"]:
                pop[c] = None

        pop["status_rastreamento"] = (
            "Seguimento" if programa == "colonoscopia"
            else "Sem registro de realização"
        )
        pop["status_fluxo"] = pop["situacao"].apply(calcular_fluxo)
        frames.append(pop)
        print(f"Regra {programa}: {len(pop):,} combinações CNS + programa.")

    if not frames:
        return pd.DataFrame()
    base = pd.concat(frames, ignore_index=True)
    return base.drop_duplicates(["cns", "programa_monitorado"], keep="last")


def atualizar_programas(sb):
    rows = []
    for codigo, r in REGRAS.items():
        rows.append({
            "codigo": codigo,
            "nome": r["nome"],
            "sexo_alvo": r["sexo"],
            "idade_min": r["idade_min"],
            "idade_max": r["idade_max"],
            "prazo_anos": r["prazo_anos"],
            "ativo": True,
        })
    upsert_com_retry(sb, "programas", rows, "codigo")
    print("Regras da tabela programas atualizadas.")


def limpar_rastreamento(sb):
    """Evita DELETE massivo via REST, que pode estourar o statement timeout."""
    raise RuntimeError(
        "O --reset-tracking não apaga mais tabelas via API REST. "
        "Para reconstrução completa, use o SQL Editor do Supabase e execute:\n"
        "TRUNCATE TABLE historico_status, solicitacoes_agendamentos, "
        "rastreamentos, elegibilidade_rastreamento RESTART IDENTITY CASCADE;\n"
        "Depois rode novamente sem --reset-tracking."
    )


def testar_conexao():
    sb = client()
    resposta = sb.table("programas").select("codigo,nome").limit(1).execute()
    print("Conexão com o Supabase: OK")
    print(f"Tabela programas acessível: {resposta.data[:1]}")


def iniciar_historico_manual(sb):
    try:
        usuario = os.getenv("USERNAME") or os.getenv("USER") or "Rotina local"
        resp = sb.table("historico_cargas").insert({
            "fonte": "Base mensal / SQLite",
            "competencia": date.today().strftime("%Y-%m"),
            "status": "processando",
            "tipo_carga": "manual",
            "usuario": usuario,
        }).execute()
        return resp.data[0]["id"] if resp.data else None
    except Exception as exc:
        print(f"Aviso: não foi possível iniciar histórico da carga manual: {exc}")
        return None


def finalizar_historico_manual(sb, carga_id, lidos, processados, erros=0):
    if not carga_id:
        return
    try:
        sb.table("historico_cargas").update({
            "fim_em": datetime.now().astimezone().isoformat(),
            "registros_lidos": int(lidos),
            "registros_processados": int(processados),
            "registros_erro": int(erros),
            "status": "sucesso",
            "mensagem": "Sincronização manual da base mensal concluída.",
        }).eq("id", carga_id).execute()
    except Exception as exc:
        print(f"Aviso: não foi possível finalizar histórico da carga manual: {exc}")


def sync(reset_tracking=False):
    sb = client()
    carga_id = iniciar_historico_manual(sb)
    print(f"Banco SQLite: {DB_PATH}")
    print("Lendo pacientes e agendamentos locais...")
    pacientes, ag = read_sqlite()
    print(f"SQLite: {len(pacientes):,} pacientes brutos; {len(ag):,} eventos/agendamentos.")

    atualizar_programas(sb)

    if reset_tracking:
        limpar_rastreamento(sb)

    # 1) pacientes únicos
    pacientes_u = pacientes.dropna(subset=["cns"]).copy()
    pacientes_u["cns"] = pacientes_u["cns"].astype(str).str.strip()
    pacientes_u = pacientes_u[pacientes_u["cns"] != ""].drop_duplicates("cns", keep="last")

    p_rows = []
    for _, r in pacientes_u.iterrows():
        p_rows.append({
            "cns": r["cns"],
            "nome": val(r.get("nome")),
            "data_nascimento": norm_date(r.get("data_nascimento")),
            "sexo": val(r.get("sexo")),
            "unidade": val(r.get("unidade")),
            "equipe": val(r.get("equipe")),
            "microarea": val(r.get("microarea")),
            "situacao_usuario": val(r.get("situacao_usuario")),
        })
    enviar_em_lotes(sb, "pacientes", p_rows, "cns", "Pacientes")
    ids = buscar_ids_pacientes(sb)

    # 2) população/regra atual reconstruída do zero localmente
    base = construir_populacao_corrigida(pacientes_u, ag)
    e_rows, r_rows = [], []
    sem_id = 0

    for _, r in base.iterrows():
        cns = str(r["cns"]).strip()
        pid = ids.get(cns)
        if not pid:
            sem_id += 1
            continue
        prog = val(r.get("programa_monitorado"))
        if not prog:
            continue
        idade = idade_atual(r)
        e_rows.append({
            "paciente_id": pid,
            "programa_codigo": prog,
            "idade": idade,
            "elegivel": True,
        })
        r_rows.append({
            "paciente_id": pid,
            "programa_codigo": prog,
            "status_rastreamento": val(r.get("status_rastreamento")) or "Sem registro de realização",
            "status_fluxo": val(r.get("status_fluxo")),
            "risco": val(r.get("risco")),
            "ultima_data_agendamento": norm_date(r.get("data_agendamento")),
            "ultima_data_solicitacao": norm_date(r.get("data_solicitacao")),
            "ultima_situacao": val(r.get("situacao")),
            "ultimo_procedimento": val(r.get("procedimento")),
        })

    if sem_id:
        print(f"Aviso: {sem_id:,} combinações sem paciente correspondente.")

    enviar_em_lotes(sb, "elegibilidade_rastreamento", e_rows, "paciente_id,programa_codigo", "Elegibilidades")
    enviar_em_lotes(sb, "rastreamentos", r_rows, "paciente_id,programa_codigo", "Rastreamentos")

    # 3) histórico de eventos
    a_rows = []
    ag_sem_paciente = 0
    for _, r in ag.iterrows():
        cns = val(r.get("cns"))
        prog = val(r.get("programa"))
        pid = ids.get(cns) if cns else None
        if not pid or prog not in REGRAS:
            ag_sem_paciente += 1
            continue

        raw_key = "|".join([
            prog,
            val(r.get("codigo_solicitacao")) or "",
            cns,
            val(r.get("data_solicitacao")) or "",
            val(r.get("data_agendamento")) or "",
            val(r.get("procedimento")) or "",
            val(r.get("situacao")) or "",
        ])
        chave = hashlib.sha256(raw_key.encode("utf-8")).hexdigest()
        a_rows.append({
            "paciente_id": pid,
            "programa_codigo": prog,
            "codigo_solicitacao": val(r.get("codigo_solicitacao")),
            "data_solicitacao": norm_date(r.get("data_solicitacao")),
            "data_agendamento": norm_date(r.get("data_agendamento")),
            "situacao": val(r.get("situacao")),
            "risco": val(r.get("risco")),
            "unidade_solicitante": val(r.get("unidade_solicitante")),
            "solicitante": val(r.get("solicitante")),
            "procedimento": val(r.get("procedimento")),
            "devolutiva": val(r.get("devolutiva")),
            "origem": "SISREG",
            "chave_origem": chave,
        })

    if ag_sem_paciente:
        print(f"Aviso: {ag_sem_paciente:,} eventos sem paciente/programa válido foram ignorados.")

    # Deduplica pela mesma chave usada no ON CONFLICT.
    # Isso evita o erro PostgreSQL 21000 quando duas linhas do mesmo lote
    # possuem o mesmo (programa_codigo, chave_origem).
    total_eventos_antes = len(a_rows)
    eventos_unicos = {}

    for row in a_rows:
        programa = row.get("programa_codigo")
        chave = row.get("chave_origem")
        if not programa or not chave:
            continue
        eventos_unicos[(programa, chave)] = row

    a_rows = list(eventos_unicos.values())
    duplicados_removidos = total_eventos_antes - len(a_rows)

    print(f"Eventos duplicados removidos: {duplicados_removidos:,}")

    enviar_em_lotes(
        sb,
        "solicitacoes_agendamentos",
        a_rows,
        "programa_codigo,chave_origem",
        "Solicitações/agendamentos",
    )

    finalizar_historico_manual(
        sb,
        carga_id,
        lidos=len(pacientes) + len(ag),
        processados=len(p_rows) + len(e_rows) + len(r_rows) + len(a_rows),
        erros=sem_id + ag_sem_paciente,
    )

    print("\nSINCRONIZAÇÃO V2 CONCLUÍDA COM SUCESSO.")
    print(f"Pacientes únicos: {len(p_rows):,}")
    print(f"Elegibilidades CNS+programa: {len(e_rows):,}")
    print(f"Rastreamentos CNS+programa: {len(r_rows):,}")
    print(f"Eventos: {len(a_rows):,}")


def main():
    parser = argparse.ArgumentParser(description="Sincroniza rastreamento oncológico com regras v2.")
    parser.add_argument("--test", action="store_true", help="Testa somente a conexão.")
    parser.add_argument(
        "--reset-tracking",
        action="store_true",
        help="Limpa tabelas derivadas antes de reconstruir com as regras v2.",
    )
    args = parser.parse_args()

    if args.test:
        testar_conexao()
    else:
        sync(reset_tracking=args.reset_tracking)


if __name__ == "__main__":
    main()
