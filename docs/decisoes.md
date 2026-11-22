# Decisões

Uma linha por decisão. Decisões que mudam regra de negócio também exigem ajuste em `docs/especificacao.md`.

| Data | Decisão | Motivo |
|---|---|---|
| 2026-11-21 | Python 3.12 nos containers; 3.13 local aceito | Versão da especificação nos containers; desenvolvimento local já usa 3.13 |
| 2026-11-21 | Repositório definitivo: `luizslfilho/telemetria` (privado), separado de qualquer repositório ou equipamento de trabalho | Projeto pessoal isolado; os documentos da etapa 0 foram redigidos numa sessão anterior e transferidos para cá |
| 2026-11-21 | Especificação movida da raiz para `docs/especificacao.md` | Caminho usado no guia de etapas e no `CLAUDE.md` |
| 2026-11-21 | Licença proprietária ("todos os direitos reservados"), titular a preencher | Produto comercial em repositório privado; confirmado em 2026-11-22 (ver abaixo) |
| 2026-11-21 | Conector RedGPS só com estrutura, `TODO(doc)` e fixture fictícia até a documentação chegar | Seção 0: não inventar formato de API |
| 2026-11-21 | Utilização: "horas disponíveis" = jornada operacional do tenant (padrão 12 h/dia), reduzida proporcionalmente pelas horas em manutenção; nunca 24 h. "Jornada operacional" entra na Seção 6 | Resposta oficial do dono (dúvida a) |
| 2026-11-21 | `users.driver_id` (nullable) liga o usuário `driver` ao cadastro; `driver` sem `driver_id` não acessa nada | Resposta oficial do dono (dúvida b) |
| 2026-11-21 | `ingest_tokens` (hash) e `rejected_packets` entram na lista de tabelas da Fase 1 | Exigidas pela Seção 4 e ausentes da lista (dúvida c) |
| 2026-11-21 | Limite de velocidade na v1 só por categoria e por cerca; sem limite por via (sem map-matching). Texto da ocorrência cita a cerca ou "limite geral" | Resposta oficial do dono (dúvida d) |
| 2026-11-21 | Direção contínua (Lei 13.103) só para `truck` e só com motorista identificado; fora disso a ocorrência não é gerada | Resposta oficial do dono (dúvida e) |
| 2026-11-21 | Front e API no mesmo host de cada revendedor, com proxy reverso (front em `/`, API em `/api`) | Cookie `SameSite=Strict` em domínio próprio (dúvida f) |
| 2026-11-21 | Retenção padrão: telemetria bruta por prazo a definir pelo dono; ocorrências e ciclos fechados por 5 anos; configurável por tenant | Resposta oficial do dono (dúvida g); prazo da bruta veio em branco |
| 2026-11-21 | Provedor de tiles do mapa por variável de ambiente; sem tiles públicos do OpenStreetMap em produção | Resposta oficial do dono (dúvida h) |
| 2026-11-21 | Fator de CO₂ padrão 2,68 kg/L, com "fonte do fator" obrigatória ao salvar | Resposta oficial do dono (dúvida i) |
| 2026-11-21 | RedGPS segue como `TODO(doc)` até a documentação chegar; não bloqueia etapas antes da 5 | Resposta oficial do dono (dúvida j) |
| 2026-11-21 | Histórico copiado de `luizslfilho/trocam2m` para `luizslfilho/telemetria`; o desenvolvimento segue só no `telemetria` | Repositório definitivo confirmado pelo dono |
| 2026-11-21 | TypeScript 5.9.3, não 7.0 | typescript-eslint 8.73 só aceita TypeScript < 6.1 |
| 2026-11-21 | SQLAlchemy fixado em 2.0.58 (última da linha 2.0), não 2.1 | A especificação pede SQLAlchemy 2.0 |
| 2026-11-21 | Imagem `timescale/timescaledb:2.32.1-pg16` (não a `-oss`) | Compressão da hypertable (etapa 2) não existe na edição OSS |
| 2026-11-21 | Duas roles no banco: `telemetria_owner` (dona do schema, só migrations) e `telemetria_app` (NOSUPERUSER, NOBYPASSRLS), criada no init do container | Seção 4: a aplicação nunca contorna RLS. Na imagem oficial a owner é superusuária; rever na etapa 14 |
| 2026-11-21 | Senhas locais geradas por `make env` (aleatórias) e URLs de banco/Redis montadas no docker-compose | `.env.example` fica sem nenhum valor real |
| 2026-11-21 | nginx do container do front faz o proxy reverso (`/` → front, `/api` → API); `/health` e `/ready` respondem na raiz e em `/api` | Decisão f (mesmo host); healthcheck do container não passa pelo proxy |
| 2026-11-21 | worker, poller e scheduler expõem saúde por arquivo de heartbeat (`python -m app.core.healthcheck`) | Serviços sem HTTP; healthcheck simples e sem porta extra |
| 2026-11-21 | Logs JSON (structlog) com remoção de campos por nome (placa, nome, RFID, coordenadas, tokens etc.), em qualquer nível | LGPD: logs sem dados pessoais; na dúvida, o campo sai |
| 2026-11-21 | `make test` e `make lint` rodam dentro dos containers; o CI roda direto no runner com TimescaleDB e Redis como serviços | Localmente só o Docker é necessário; CI mais rápido e sem docker-in-docker |
| 2026-11-21 | Documentação OpenAPI em `/api/docs` só fora de produção | Não expor a superfície da API em produção |
| 2026-11-22 | `truck` "trabalhando" = ignição ligada e velocidade ≥ 3 km/h, ou PTO ativa mesmo parado; parado com motor ligado sem PTO é ociosidade. Utilização de caminhão = movimento + PTO | Resposta oficial do dono (releitura 1); Seção 1.1 ajustada |
| 2026-11-22 | Disponibilidade física usa 24 h/dia (calendário); utilização usa a jornada operacional | Disponibilidade mede se o ativo estava apto; utilização, quanto da jornada o apto trabalhou (releitura 2) |
| 2026-11-22 | Fonte padrão do fator 2,68 kg CO₂/L: "Referência genérica para diesel fóssil (fator padrão IPCC 2006). Revisar com a ferramenta do Programa Brasileiro GHG Protocol, que considera a mistura obrigatória de biodiesel."; valor e fonte marcados "a revisar pelo cliente" | Resposta oficial do dono (releitura 3) |
| 2026-11-22 | LICENSE proprietária, todos os direitos reservados, sem licença open source; titular pessoa física até a empresa ser formalizada (depois, CNPJ) | Resposta oficial do dono (releitura 4); nome do titular ainda em branco no arquivo |
| 2026-11-22 | Qualidade sempre `partial` em código, banco e API; rótulo "Parcial" na interface | Padronização (releitura 5) |
| 2026-11-22 | Opção A: `telemetry_raw` e continuous aggregates sem RLS, no schema `telemetry_internal`, sem nenhum GRANT para `telemetria_app`; leitura só por funções `app.telemetry_*` que filtram pelo contexto e dão erro se ele não estiver definido; RLS continua em todas as tabelas relacionais | TimescaleDB 2.32 recusa RLS em hypertable com compressão ("columnstore cannot be used on table with row security") e com continuous aggregate; mantém compressão e aggregates nativos |
| 2026-11-22 | Leitura de telemetria por funções `plpgsql`, não por views | A checagem de contexto roda sempre antes da leitura; numa view o planejador pode pular a checagem e devolver vazio em silêncio |
| 2026-11-22 | Role `telemetria_ingest` para o worker, só com INSERT na telemetria (sem SELECT, UPDATE, DELETE nem acesso ao cadastro); privilégios extras do worker entram no plano da etapa 4 | Decisão 1 do dono; menor privilégio |
| 2026-11-22 | `ON CONFLICT DO NOTHING` sem alvo na telemetria | Com alvo, o PostgreSQL exige SELECT nas colunas, que a role de ingestão não tem; a única unicidade é a chave (tenant_id, asset_id, source, ts_utc) |
| 2026-11-22 | FK composta `(tenant_id, asset_id)` → `assets` na telemetria e FKs compostas `(tenant_id, x_id)` em todo o cadastro | Sem RLS na hypertable, a FK impede gravar ativo de um tenant com o tenant de outro; no cadastro, impede referência cruzada entre tenants |
| 2026-11-22 | `users` e `platform_credentials` com `reseller_id NOT NULL` e `tenant_id` nullable (CHECK: só `reseller_admin` sem tenant; todos os outros papéis, inclusive `driver`, com tenant); `platform_unit_map` com `tenant_id NOT NULL` liga cada unidade a um cliente do mesmo revendedor; `audit_log` com `tenant_id` nullable | Decisão 2 do dono; revendedor e credencial compartilhada não cabem em `tenant_id NOT NULL` |
| 2026-11-22 | `dtc_dictionary` e `param_mapping` como catálogos globais sem tenant: SELECT para a aplicação, escrita só por migration | Decisão 2 do dono |
| 2026-11-22 | Contexto: `app.visible_tenant_ids()` resolve só tenant / revendedor + tenant (só se for dele) / só revendedor; `app.require_visible_tenant_ids()` dá erro sem contexto ou com tenant fora do revendedor | Um mecanismo só para RLS e para as funções de telemetria |
| 2026-11-22 | RLS sem `FORCE ROW LEVEL SECURITY` | As funções `SECURITY DEFINER` leem `tenants` como dona; com FORCE haveria recursão na política. A aplicação nunca é dona das tabelas |
| 2026-11-22 | Diário = função que soma o aggregate horário (UTC) agrupando pela data no fuso de cada tenant. Premissa: fuso de hora cheia (todo o Brasil); fuso com meia hora exige revisão | Decisão 3 do dono; `time_bucket` em continuous aggregate só aceita fuso constante |
| 2026-11-22 | Cercas em GeoJSON (`jsonb`) com bbox; `ShapelyGeofenceMatcher` atrás de `GeofenceMatcher`, com pré-filtro por bbox e cache por tenant; polígono, círculo (centro + raio) e linha com largura; borda conta como dentro (tolerância de 1 cm) | Decisão 4 do dono; imagem do TimescaleDB sem PostGIS |
| 2026-11-22 | Linha com largura: `width_m` é a largura total (dentro se a até `width_m/2` do eixo), a confirmar na documentação da Wialon | Sem documentação ainda; registrado como `TODO(doc)` |
| 2026-11-22 | Tabelas extras: `platform_unit_map` (unidade → cliente, 1.1.1) e `maintenance_executions` (execução da preventiva, 1.9) | Exigidas pela especificação e ausentes da lista da Fase 1 |
| 2026-11-22 | Testes de banco criam bancos próprios (`telemetria_test`, `telemetria_migrations_test`) e aplicam as migrations do zero | Não dependem nem sujam o banco de desenvolvimento |
