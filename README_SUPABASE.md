# Rastreamento Oncológico AP 2.1 — versão Supabase

Esta versão **não remove** o SQLite nem o BigQuery. Ela adiciona o Supabase como banco operacional e uma aplicação Streamlit para o painel nominal.

## 1. Segurança antes de tudo
O arquivo `credencial.json` antigo não deve ficar no repositório. Mova-o para uma pasta segura fora do projeto e configure `GOOGLE_APPLICATION_CREDENTIALS` no `.env`.

> Como uma credencial foi incluída em um ZIP compartilhado, é recomendável revogar/rotacionar essa chave no Google Cloud e criar uma nova.

## 2. Criar o projeto Supabase
1. Crie um projeto no Supabase.
2. Abra **SQL Editor** e execute `supabase/schema.sql`.
3. Em **Authentication > Providers**, mantenha Email habilitado.
4. Se desejar login Gmail, habilite Google e configure Client ID/Secret e Redirect URL conforme exibido pelo próprio Supabase.

## 3. Configurar variáveis
Copie `.env.example` para `.env` e preencha:
- `SUPABASE_URL`
- `SUPABASE_PUBLISHABLE_KEY`
- `SUPABASE_SECRET_KEY`
- parâmetros do BigQuery, se continuar usando-o.

Nunca exponha `SUPABASE_SECRET_KEY` no painel/browser. Ela é usada somente pelo script local `supabase_sync.py`.

## 4. Instalar dependências
```bash
pip install -r requirements.txt
```

## 5. Primeira carga
O banco SQLite existente já pode ser migrado:
```bash
python scripts_v2/supabase_sync.py
```

## 6. Executar o painel
```bash
streamlit run dashboard/app.py
```

## 7. Atualização mensal
A ideia é preservar seu fluxo atual. Depois de colocar o novo arquivo VitaCare na pasta de entrada:
```bash
python scripts_v2/atualizar_v2.py
```

A ordem será:
1. VitaCare + SISREG -> SQLite
2. SQLite -> Supabase
3. SQLite -> BigQuery + Excel

## Modelo de dados
- `pacientes`: cadastro único por CNS.
- `programas`: critérios dos quatro rastreios.
- `elegibilidade_rastreamento`: uma linha por paciente + programa.
- `solicitacoes_agendamentos`: histórico completo, sem usar esses eventos para inflar os denominadores.
- `rastreamentos`: estado atual de cada paciente/programa.
- `historico_status`: preparado para snapshots futuros.
- `vw_painel_rastreamento`: visão pronta para o dashboard.

## Próxima melhoria recomendada
Hoje a regra existente considera `Agendamento Confirmado` como evidência do exame. O próximo passo é separar **agendamento**, **realização** e, quando houver fonte disponível, **resultado do exame**. Isso permite indicadores epidemiologicamente mais seguros e evita tratar consulta/agendamento como exame realizado.
