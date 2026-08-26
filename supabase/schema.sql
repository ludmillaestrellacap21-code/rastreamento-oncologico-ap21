-- Rastreamento Oncológico AP 2.1
-- Executar no SQL Editor do Supabase.

create extension if not exists pgcrypto;

create table if not exists public.pacientes (
  id uuid primary key default gen_random_uuid(),
  cns text not null unique,
  nome text,
  data_nascimento date,
  sexo text,
  unidade text,
  equipe text,
  microarea text,
  situacao_usuario text,
  atualizado_em timestamptz not null default now()
);

create table if not exists public.programas (
  codigo text primary key,
  nome text not null,
  sexo_alvo text,
  idade_min integer not null,
  idade_max integer not null,
  prazo_anos integer not null default 2,
  ativo boolean not null default true
);

insert into public.programas (codigo,nome,sexo_alvo,idade_min,idade_max,prazo_anos) values
('mamografia','Mamografia','F',50,69,2),
('citopatologico','Citopatológico','F',25,64,2),
('colonoscopia','Colonoscopia',null,50,75,2),
('sangue_oculto','Sangue oculto nas fezes',null,50,75,2)
on conflict (codigo) do update set
  nome=excluded.nome, sexo_alvo=excluded.sexo_alvo,
  idade_min=excluded.idade_min, idade_max=excluded.idade_max,
  prazo_anos=excluded.prazo_anos;

create table if not exists public.elegibilidade_rastreamento (
  id uuid primary key default gen_random_uuid(),
  paciente_id uuid not null references public.pacientes(id) on delete cascade,
  programa_codigo text not null references public.programas(codigo),
  idade integer,
  elegivel boolean not null default true,
  competencia date,
  atualizado_em timestamptz not null default now(),
  unique (paciente_id, programa_codigo)
);

create table if not exists public.solicitacoes_agendamentos (
  id uuid primary key default gen_random_uuid(),
  paciente_id uuid not null references public.pacientes(id) on delete cascade,
  programa_codigo text not null references public.programas(codigo),
  codigo_solicitacao text,
  data_solicitacao date,
  data_agendamento date,
  situacao text,
  risco text,
  unidade_solicitante text,
  solicitante text,
  procedimento text,
  devolutiva text,
  origem text not null default 'SISREG',
  chave_origem text,
  criado_em timestamptz not null default now(),
  unique (programa_codigo, chave_origem)
);

create table if not exists public.rastreamentos (
  id uuid primary key default gen_random_uuid(),
  paciente_id uuid not null references public.pacientes(id) on delete cascade,
  programa_codigo text not null references public.programas(codigo),
  status_rastreamento text not null,
  risco text,
  ultima_data_agendamento date,
  ultima_data_solicitacao date,
  ultima_situacao text,
  ultimo_procedimento text,
  atualizado_em timestamptz not null default now(),
  unique (paciente_id, programa_codigo)
);

create table if not exists public.historico_status (
  id bigserial primary key,
  paciente_id uuid not null references public.pacientes(id) on delete cascade,
  programa_codigo text not null references public.programas(codigo),
  status_rastreamento text not null,
  risco text,
  referencia_data date,
  registrado_em timestamptz not null default now()
);

create index if not exists idx_pacientes_unidade on public.pacientes(unidade);
create index if not exists idx_pacientes_equipe on public.pacientes(equipe);
create index if not exists idx_rastreamentos_status on public.rastreamentos(status_rastreamento);
create index if not exists idx_agendamentos_paciente_programa on public.solicitacoes_agendamentos(paciente_id, programa_codigo);

-- View pronta para o painel: uma linha por paciente + programa.
create or replace view public.vw_painel_rastreamento
with (security_invoker = true) as
select
  p.id as paciente_id,
  p.cns,
  p.nome,
  p.data_nascimento,
  e.idade,
  p.sexo,
  p.unidade,
  p.equipe,
  p.microarea,
  p.situacao_usuario,
  e.programa_codigo,
  pr.nome as programa,
  r.status_rastreamento,
  r.risco,
  r.ultima_data_agendamento as data_agendamento,
  r.ultima_data_solicitacao as data_solicitacao,
  r.ultima_situacao as situacao,
  r.ultimo_procedimento as procedimento,
  r.atualizado_em
from public.elegibilidade_rastreamento e
join public.pacientes p on p.id=e.paciente_id
join public.programas pr on pr.codigo=e.programa_codigo
left join public.rastreamentos r
  on r.paciente_id=e.paciente_id and r.programa_codigo=e.programa_codigo
where e.elegivel=true;

-- RLS: leitura para usuários autenticados. Escrita somente via service role no pipeline.
alter table public.pacientes enable row level security;
alter table public.programas enable row level security;
alter table public.elegibilidade_rastreamento enable row level security;
alter table public.solicitacoes_agendamentos enable row level security;
alter table public.rastreamentos enable row level security;
alter table public.historico_status enable row level security;

drop policy if exists "authenticated read pacientes" on public.pacientes;
create policy "authenticated read pacientes" on public.pacientes for select to authenticated using (true);
drop policy if exists "authenticated read programas" on public.programas;
create policy "authenticated read programas" on public.programas for select to authenticated using (true);
drop policy if exists "authenticated read elegibilidade" on public.elegibilidade_rastreamento;
create policy "authenticated read elegibilidade" on public.elegibilidade_rastreamento for select to authenticated using (true);
drop policy if exists "authenticated read agendamentos" on public.solicitacoes_agendamentos;
create policy "authenticated read agendamentos" on public.solicitacoes_agendamentos for select to authenticated using (true);
drop policy if exists "authenticated read rastreamentos" on public.rastreamentos;
create policy "authenticated read rastreamentos" on public.rastreamentos for select to authenticated using (true);
drop policy if exists "authenticated read historico" on public.historico_status;
create policy "authenticated read historico" on public.historico_status for select to authenticated using (true);
