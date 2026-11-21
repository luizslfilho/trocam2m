# Plataforma de telemetria — prompts por etapa (base: especificação v2)

## Como usar
1. Salve a especificação v2 no repositório como `docs/especificacao.md`. Ela é a única fonte de verdade; os prompts abaixo só dizem **qual parte** fazer agora.
2. **Uma etapa por sessão** do Claude Code. Entre etapas, use `/clear`: o que precisa persistir fica no `CLAUDE.md`, em `docs/progresso.md` e em `docs/decisoes.md`.
3. Toda etapa segue o mesmo ritmo: plano → seu OK → código com testes → lint e testes passando → atualização do progresso → commit.
4. Só avance quando a lista **Conferir antes de seguir** estiver marcada.
5. Se o Claude Code achar contradição na especificação, ele para e pergunta (Seção 0). Resolva no arquivo, não na conversa.

| Etapa | Entrega | Fase da especificação | Depende de |
|---|---|---|---|
| 0 | Repositório, `CLAUDE.md` e plano | Seção 0 | — |
| 1 | Esqueleto, docker e CI | Fase 1 | 0 |
| 2 | Banco, RLS e agregados | Fase 1 | 1 |
| 3 | Autenticação, papéis e revenda | Seção 4 | 2 |
| 4 | Ingestão e normalização | Fase 2 | 2 |
| 5 | Conectores e motorista | Fase 2 | 4 |
| 6 | Configuração com herança | Fase 3 / Seção 6 | 2 |
| 7 | Motor de KPIs e alertas DTC | Fase 3 | 4, 6 |
| 8 | API do dashboard e seed | Fase 3 | 3, 7 |
| 9 | Viagens, preventiva e abastecimentos | Fase 3.5 | 7 |
| 10 | Programa de Boa Condução | Fase 3.5 | 9 |
| 11 | Relatórios e agendamento | Fase 3.5 | 8, 10 |
| 12 | Front: base e dashboard | Fase 4 / 7.1 | 8 |
| 13 | Front: condução, operação e configurações | Fase 4 / 7.2–7.3 | 11, 12 |
| 14 | Pré-produção (recomendado, fora da especificação) | — | 13 |
| 15 | Assistente MCP e emissões (pós-v1) | Fase 5 | 14 |

Depois da etapa 2, as etapas 3, 4 e 6 podem andar em qualquer ordem.

---

## Etapa 0 — Repositório, contexto permanente e plano

```
Leia docs/especificacao.md inteiro. Esta é a etapa 0 de 15.

Tarefas:
1. Repositório próprio (Seção 0): primeiro commit em main com README, .gitignore e licença; depois crie o branch feature/foundation. Nunca use git worktree.
2. Crie CLAUDE.md na raiz (máx. ~150 linhas), para toda sessão futura:
   - posicionamento do produto em 3 linhas (independente de equipamento, linguagem simples, qualidade do dado explícita, nenhuma promessa de ganho percentual);
   - regras de domínio inegociáveis, resumidas: 1.1 (incluindo ociosidade evitável e PTO), 1.1.1, 1.1.2, 1.2 a 1.9;
   - regras de segurança (Seção 4) e LGPD;
   - cuidado jurídico do Programa de Boa Condução (prêmio, nunca desconto; textos "gratificação conquistada");
   - stack e comandos (make up, make test, make lint, make seed);
   - convenções: ruff/mypy, teste obrigatório por regra de negócio, migrations só via Alembic, nada de segredo no código, não inventar formato de API (TODO(doc)), nenhum dado real de cliente;
   - fluxo: plano antes de codar, uma etapa por vez, atualizar docs/progresso.md e docs/decisoes.md ao final.
3. Crie docs/progresso.md com a tabela das etapas 1 a 15 (status, data, observações) e a seção "Pendências de documentação" (TODO(doc)).
4. Crie docs/decisoes.md (uma linha por decisão: data, decisão, motivo).
5. Me mostre o CLAUDE.md e liste as dúvidas, lacunas e contradições que encontrou na especificação, numeradas.

Não escreva código de aplicação nesta etapa. Commit: "docs: contexto do projeto e plano por etapas".
```

**Conferir antes de seguir**
- [ ] `CLAUDE.md` resume a especificação sem acrescentar regras
- [ ] Dúvidas respondidas e especificação ajustada quando necessário

---

## Etapa 1 — Esqueleto, docker e CI

```
Leia CLAUDE.md e docs/progresso.md. Etapa 1 de 15: esqueleto do repositório (parte da Fase 1).

Escopo:
- Estrutura: backend/ (app/core, app/domain, app/config, app/adapters, app/ingestion, app/kpi, app/scoring, app/reports, app/api, app/db, tests/), frontend/ (Vite + React + TS + Tailwind + shadcn/ui), docker/.
- docker-compose.yml com api, worker, poller, scheduler, timescaledb (PostgreSQL 16 + TimescaleDB), redis e frontend; healthcheck em todos.
- FastAPI com /health e /ready (checa banco e Redis); Pydantic Settings; .env.example completo sem valores reais; logs estruturados sem dados pessoais.
- Makefile: up, down, test, lint, fmt, migrate, seed (placeholder).
- Qualidade: ruff, mypy (strict em app/domain), pytest + pytest-asyncio; ESLint e tsc --noEmit no front; pre-commit.
- CI: lint e testes do backend, build e tsc do front.

Fora do escopo: tabelas, autenticação, regras de negócio.
Antes de codar, mostre a árvore e as versões fixadas das dependências; espere meu OK.
Aceite: make up sobe tudo saudável; make test e make lint passam; /ready responde 200; CI verde.
Ao final: progresso, decisões e commit.
```

**Conferir antes de seguir**
- [ ] Todos os serviços saudáveis no `docker compose ps`
- [ ] `.env.example` sem segredo real
- [ ] CI verde

---

## Etapa 2 — Banco, RLS e agregados

```
Leia CLAUDE.md e docs/progresso.md. Etapa 2 de 15: banco de dados (Fase 1).

Escopo:
- Migrations Alembic com todas as tabelas listadas na Fase 1 da especificação (resellers com branding até audit_log), mais ingest_tokens (hash) e rejected_packets (exigidos pela Seção 4).
- telemetry_raw como hypertable; chave única (tenant_id, asset_id, source, ts_utc); ts_utc e received_at; flags de qualidade; compressão após 7 dias.
- Continuous aggregates horário e diário com time_bucket no fuso do tenant; refresh cobrindo pelo menos 7 dias para trás (1.6).
- fuel_prices com data de vigência; config_versions e scoring_rules versionados (preparando as etapas 6 e 10).
- maintenance_events com status (incluindo suggested, 1.5).
- RLS em todas as tabelas de negócio: tenant_id NOT NULL e indexado; role da aplicação sem BYPASSRLS; políticas por app.tenant_id e, para revenda, pelos tenants do app.reseller_id; helper de SET LOCAL por transação.
- Seed pequeno do dtc_dictionary, marcado "a revisar por especialista".

Testes obrigatórios (TimescaleDB real):
- migrations sobem do zero e descem sem erro;
- tenant A não lê nem escreve dados do tenant B;
- revendedor X não acessa clientes do revendedor Y;
- duplicado em telemetry_raw é ignorado;
- agregado diário respeita America/Sao_Paulo (evento às 23h30 local cai no dia certo).

Antes de codar: diagrama do schema em mermaid, lista de índices e políticas RLS; espere meu OK.
Ao final: progresso, decisões e commit.
```

**Conferir antes de seguir**
- [ ] Isolamento entre tenants e entre revendedores testado e no CI
- [ ] Role da aplicação sem `BYPASSRLS`
- [ ] Agregado diário no fuso local

---

## Etapa 3 — Autenticação, papéis e revenda

```
Leia CLAUDE.md e docs/progresso.md. Etapa 3 de 15: autenticação e contexto (Seção 4 e 1.1.1).

Escopo:
- Login com senha (argon2); JWT de acesso curto + refresh rotativo em cookie httpOnly, Secure, SameSite=Strict; logout invalida o refresh; nada de token no corpo da resposta.
- Papéis: reseller_admin, admin, fleet_manager, viewer, driver, com as permissões da Seção 4 (valores de gratificação só para admin; driver só vê o próprio extrato).
- Contexto: tenant e reseller vêm só do token e são aplicados via SET LOCAL em toda transação.
- GET /api/v1/branding resolvendo a marca do revendedor pelo host.
- Revendedor lista seus clientes e troca o cliente ativo.
- Rate limit no login; audit log de login, troca de cliente e ações administrativas.
- Criptografia de platform_credentials (envelope encryption; chave por variável de ambiente em dev, interface pronta para KMS).

Testes: matriz de permissões por papel; driver não acessa dado de outro motorista; revendedor não troca para cliente de outro revendedor; refresh reutilizado é bloqueado; checagem de origem nas rotas que alteram dados.
Plano antes de codar; espere meu OK. Ao final: progresso, decisões e commit.
```

**Conferir antes de seguir**
- [ ] Matriz de permissões por papel passando
- [ ] Nenhum token no `localStorage` ou em JSON

---

## Etapa 4 — Ingestão e normalização

```
Leia CLAUDE.md e docs/progresso.md. Etapa 4 de 15: ingestão e normalização (Fase 2, sem conectores reais).

Escopo (1.4, 1.6, 1.7 e Seção 3):
- CanonicalTelemetryPacket (Pydantic v2, extra="forbid") com posição, velocidade GPS e roda, ignição, RPM, carga do motor (SPN 92), torque (SPN 513), combustível (nível, contador, taxa), odômetro, horímetro, marcha, PTO, tensão da bateria/alimentação, cinto, eventos de frenagem/aceleração/curva, RFID, VIN, DTCs ativos e flags de qualidade.
- param_mapping por (source, hardware_model) com escala, offset e unidade.
- Saneamento CAN: sentinelas brutos e escalados viram null; faixa física por parâmetro (incluindo tensão 0–36 V); salto impossível; RPM 0 em movimento como falha de leitura.
- Pipeline: adaptador → normalizador → Redis Stream → worker de escrita em lote com ON CONFLICT DO NOTHING → asset_live_state.
- Deduplicação: atalho Redis com TTL + garantia no banco.
- Pacote inválido vai para rejected_packets com o motivo, sem derrubar o lote.
- Registro das janelas afetadas por dado atrasado, para reprocessamento de KPIs, viagens e ocorrências.

Testes: sentinelas (1, 2 e 4 bytes e escalados), faixa física, salto, duplicado, fora de ordem, lote misto, worker reiniciado no meio do lote sem perda nem duplicação.
Plano antes de codar; espere meu OK. Ao final: progresso, decisões e commit.
```

**Conferir antes de seguir**
- [ ] Nenhum sentinela vira zero
- [ ] Reiniciar o worker não perde nem duplica pacotes

---

## Etapa 5 — Conectores e motorista

```
Leia CLAUDE.md e docs/progresso.md. Etapa 5 de 15: conectores e identificação do motorista (Fase 2).

Escopo (Seção 3 e 1.1.2):
- Interface PlatformConnector.
- WialonConnector (pull): token/login, core/search_items, messages/load_interval em janelas de 1 h, messages/unload sempre, relogin no erro de sessão, backoff exponencial, checkpoint por unidade, limite de concorrência por conta.
- Serviço poller agendado por credencial.
- POST /api/v1/ingest/stream/{source} (push via gateway): X-Ingest-Token por fonte e tenant guardado como hash, hmac.compare_digest, limite de corpo, rate limit.
- RedGPSConnector: estrutura completa com TODO(doc) e fixture fictícia; não invente endpoints nem campos.
- VIN do pacote preenche o cadastro do ativo quando vazio.
- Motorista: RFID via param_mapping; sincronização das atribuições de motorista da Wialon; driver_assignments com prioridade RFID > plataforma > fixo.
- Mapeamento de unidades para assets e para o cliente certo quando a credencial é do revendedor.

Testes com respostas gravadas da Wialon (sessão expirada, lote vazio, unidade nova, fora de ordem), token de ingestão inválido, troca de motorista por RFID no meio do dia, conflito RFID × fixo.
No final, liste todos os TODO(doc). Plano antes de codar; espere meu OK. Ao final: progresso, decisões e commit.
```

**Conferir antes de seguir**
- [ ] Poller grava dados reais da conta demo da Wialon
- [ ] Lista de `TODO(doc)` revisada (o que pedir à RedGPS)

---

## Etapa 6 — Configuração com herança

```
Leia CLAUDE.md e docs/progresso.md. Etapa 6 de 15: configuração (Seção 6).

Escopo:
- Resolver de configuração com herança: padrão do sistema → cliente → grupo de ativos → modelo → ativo; a resposta informa de qual nível veio cada valor.
- Todos os parâmetros da Seção 6 com os padrões indicados, tipados e validados (ex.: idle_max < extra_eco_max < eco_max; faixas leve < médio < grave).
- Versionamento em config_versions (quem, quando, valor anterior e novo) e audit log; consulta "qual valor valia na data X".
- Preço do diesel com vigência: consulta por data, histórico preservado.
- Endpoints: ler configuração resolvida por nível, sobrescrever, remover sobrescrita (volta a herdar), histórico.
- Cache da configuração resolvida com invalidação na alteração.

Testes: herança em todos os níveis; sobrescrita e remoção; valor vigente em data passada; validações cruzadas; troca de preço do diesel no meio do mês.
Plano antes de codar; espere meu OK. Ao final: progresso, decisões e commit.
```

**Conferir antes de seguir**
- [ ] "Valor vigente na data X" funcionando para config e para preço do diesel

---

## Etapa 7 — Motor de KPIs e alertas DTC

```
Leia CLAUDE.md e docs/progresso.md. Etapa 7 de 15: motor de KPIs (Fase 3).

Escopo (1.1, 1.2, 1.3, 1.5, 1.7 e Seção 5, exceto divergência de abastecimento, que fica na etapa 9):
- Estados por intervalo ponderados pela duração real: desligado, ociosidade, trabalhando/movimento (regra por categoria), manutenção, sem dado.
- Ociosidade evitável: exclui PTO ativa e cercas de ociosidade permitida; a bruta fica disponível para o drawer.
- Faixas de RPM, sobre-giro, excesso de velocidade (limite por categoria e por cerca, tolerância e duração mínima), eventos bruscos, possível banguela.
- Disponibilidade (paradas suggested não contam; aberta conta até agora), utilização (inclusive dias usados e por grupo), custo da ociosidade com preço vigente na data, CO₂ (ociosidade e total), consumo contra a média padrão do modelo, autonomia, faixa econômica, eventos severos por 100 km / 10 h, saúde elétrica.
- Qualidade em todo KPI (reliable/partial/unreliable + motivo); unreliable fora de médias e rankings.
- Alertas DTC: abrir, fechar após N minutos sem o código, tempo em aberto; critical gera sugestão em maintenance_events.
- Reprocessamento das janelas afetadas por dado atrasado.
- Toda regra lê os limites pelo resolver da etapa 6.

Testes com valores esperados calculados à mão para cada KPI, incluindo: virada de dia no fuso local, parada atravessando a meia-noite, PTO ativa não contando como ociosidade, cerca permitida, preço do diesel mudando no meio do período, máquina sem sinal de carga (partial), litros estimados, dado atrasado alterando o agregado.
Plano antes de codar; espere meu OK. Ao final: progresso, decisões e commit.
```

**Conferir antes de seguir**
- [ ] Cada KPI com teste de valor calculado à mão
- [ ] Ociosidade evitável e bruta conferidas num caso com PTO

---

## Etapa 8 — API do dashboard e seed

```
Leia CLAUDE.md e docs/progresso.md. Etapa 8 de 15: API e seed (Fase 3).

Escopo:
- GET /api/v1/dashboard/summary (filtros categoria, grupo, período): cards, distribuição diária do tempo, combustível diário com R$, faixa econômica, eventos severos, preventivas vencendo; tudo com qualidade.
- GET /api/v1/dashboard/assets: status derivado, fonte, medidores, consumo atual, autonomia, posição para o mapa.
- GET /api/v1/assets/{id}/telemetry (série com no máximo 500 pontos) e GET /api/v1/assets/{id}/detail (CAN atual, SPN/FMI, tensão, ociosidade bruta e evitável, últimas 24 h).
- CRUD de ativos, grupos, cercas e maintenance_events (incluindo confirmar sugestão), conforme papéis.
- OpenAPI documentado; paginação e filtros.
- seed.py exatamente como descrito na Fase 3, só com dados fictícios.

Testes de contrato dos endpoints e de desempenho básico (summary de 30 dias para 500 ativos em menos de 1 s com seed ampliado).
Plano antes de codar; espere meu OK. Ao final: progresso, decisões e commit.
```

**Conferir antes de seguir**
- [ ] `make seed` + API mostram números coerentes entre cards, gráficos e tabela
- [ ] Desempenho dentro do limite

---

## Etapa 9 — Viagens, preventiva e abastecimentos

```
Leia CLAUDE.md e docs/progresso.md. Etapa 9 de 15: operação (parte da Fase 3.5).

Escopo:
- Viagens (1.8): detecção com tolerância de parada, campos completos, origem e destino por cerca ou coordenada, motorista pelo período de vínculo, recálculo com dado atrasado.
- Manutenção preventiva (1.9): planos por modelo ou ativo, gatilho por horímetro, odômetro e/ou data (o que vencer primeiro), estados ok/due_soon/overdue, recálculo do próximo vencimento pela leitura real na execução.
- Abastecimentos: fuel_transactions por lançamento manual e importação CSV (com validação linha a linha e relatório de erros); divergência contra o aumento de nível na janela do abastecimento, com tolerância da configuração; resultado é "anomalia a investigar", vinculada a ativo e transação, nunca a pessoa.
- Endpoints de lista e detalhe para viagens, planos, vencimentos, transações e divergências.

Testes: semáforo não quebra viagem; viagem atravessando a meia-noite; preventiva vencendo por horímetro e por data; CSV com linhas inválidas; abastecimento dentro e fora da tolerância; dado atrasado recalculando a viagem.
Plano antes de codar; espere meu OK. Ao final: progresso, decisões e commit.
```

**Conferir antes de seguir**
- [ ] Nenhum texto ou campo chama divergência de "fraude"

---

## Etapa 10 — Programa de Boa Condução

```
Leia CLAUDE.md e docs/progresso.md. Etapa 10 de 15: Programa de Boa Condução (5.1, parte da Fase 3.5).

Escopo:
- Motor de ocorrências com as regras e pesos padrão da tabela 5.1, todos configuráveis e desligáveis pelo resolver; cada ocorrência com todos os campos e status listados na especificação.
- Ociosidade em blocos (1 ocorrência por bloco), faixas de excesso de velocidade, direção contínua (Lei 13.103), condução sem identificação quando o tenant exige RFID.
- Pontuação por ciclo: pontos iniciais, desconto pelo peso, piso 0, bônus com teto, faixas de premiação; ocorrências por 100 km / 10 h ao lado do saldo.
- Só desconta com dado reliable e motorista identificado; demais com peso 0 (void_quality ou fora do ranking).
- Contestação: abrir, aceitar (pontos voltam) ou recusar com justificativa; tudo no audit log.
- Fechamento de ciclo congelando o resultado; dado atrasado após o fechamento vira ajuste no ciclo seguinte.
- Pesos versionados: ocorrência mantém o peso vigente quando aconteceu.
- Política do programa e data de ciência obrigatórias antes de ativar a premiação; valores em R$ só para admin.
- Endpoints: ranking do ciclo, extrato por motorista, fila de contestações, visão do motorista.

Testes exigidos na Fase 3.5 para o programa: ocorrência unreliable com peso 0, sem motorista fora do ranking, contestação aceita devolvendo pontos, mudança de peso no meio do ciclo, dado atrasado depois do fechamento, comparação por 100 km / 10 h, bloqueio da premiação sem política registrada.
Plano antes de codar; espere meu OK. Ao final: progresso, decisões e commit.
```

**Conferir antes de seguir**
- [ ] Nenhum texto fala em "multa" ou "desconto"
- [ ] Ciclo fechado não muda com dado atrasado

---

## Etapa 11 — Relatórios e agendamento

```
Leia CLAUDE.md e docs/progresso.md. Etapa 11 de 15: relatórios (parte da Fase 3.5).

Escopo:
- Catálogo de relatórios padrão: frota, ociosidade, consumo, condução, manutenção e emissões; filtros por período, categoria, grupo, ativo e motorista.
- Geração em PDF e Excel no back-end, com marca do revendedor e selo de qualidade do dado nos números.
- Filtros salvos e report_schedules (diário, semanal, mensal; PDF ou Excel; destinatários), executados pelo serviço scheduler.
- Envio por SMTP configurável, com registro de envio e falha; reenvio manual.
- Respeito a papel e tenant em todo relatório (valores de gratificação só para admin).

Testes: cada relatório gera arquivo válido com o seed; relatório agendado gerado e enviado para um SMTP de teste; usuário sem permissão não gera relatório com valores de gratificação; relatório não mistura tenants.
Plano antes de codar; espere meu OK. Ao final: progresso, decisões e commit.
```

**Conferir antes de seguir**
- [ ] E-mail de teste recebido com PDF e Excel abrindo corretamente

---

## Etapa 12 — Front: base e dashboard

```
Leia CLAUDE.md e docs/progresso.md. Etapa 12 de 15: front-end base e dashboard (Fase 4, Seção 7.1).

Escopo:
- Base: roteamento, login com cookies, tema do revendedor via /api/v1/branding, layout com navegação, seletor de cliente para reseller_admin, TanStack Query, tratamento global de erro e sessão expirada.
- Dashboard 7.1 com abas (Visão geral, Combustível e emissões, Condução, Utilização, Manutenção); cabeçalho com categoria, grupo, período, busca e alertas críticos; 4 cards com selo de qualidade; gráficos diários (Recharts); alertas mecânicos; preventivas vencendo; faixa econômica e eventos severos.
- Zona ao vivo: mapa MapLibre (tiles configuráveis, cor por status) e tabela com autonomia; drawer com CAN, SPN/FMI, tensão, ociosidade bruta e últimas 24 h (Esc fecha, foco preso no drawer).
- Sem jargão fora do drawer. Estados de carregamento, vazio e erro em todos os blocos. Contraste AA, teclado, 390 px.

Testes: Vitest + Testing Library nos cards, status derivado e drawer; E2E Playwright do login até o drawer de um ativo.
Plano antes de codar; espere meu OK. Ao final: progresso, decisões e commit.
```

**Conferir antes de seguir**
- [ ] Alternar Todos / Caminhões / Linha amarela muda tudo, inclusive o mapa
- [ ] Usável no celular

---

## Etapa 13 — Front: condução, operação e configurações

```
Leia CLAUDE.md e docs/progresso.md. Etapa 13 de 15: demais telas (Fase 4, Seções 7.2 e 7.3).

Escopo:
- Programa de Boa Condução: ranking do ciclo (dado insuficiente à parte), extrato em linguagem simples com mapa, valor medido × limite, peso e status, botão de contestar, fila de contestações, visão do motorista (papel driver). Textos: "gratificação conquistada", nunca "multa" ou "desconto".
- Viagens (lista e trajeto no mapa), Manutenção (paradas, sugestões de DTC para confirmar, planos e vencimentos), Abastecimentos (lançamento, importação CSV com erros por linha, divergências como "anomalia a investigar"), Relatórios (catálogo, filtros salvos, agendamentos).
- Configurações (Seção 6) mostrando de onde vem cada valor ("herdado do cliente"), sobrescrever e voltar a herdar, histórico de alterações.
- Painel do revendedor: clientes com resumo e edição da marca.

Aceite da Fase 4: build e tsc sem erro; tudo funcional com o seed; abrir e fechar uma parada muda a disponibilidade; alterar um peso muda o extrato só a partir da data da mudança; 390 px.
Testes: E2E Playwright para "abrir parada → disponibilidade cai" e "mudar peso → extrato antigo não muda"; teste do papel driver vendo só o próprio extrato.
Plano antes de codar; espere meu OK. Ao final: progresso, decisões e commit.
```

**Conferir antes de seguir**
- [ ] Os dois E2E da Fase 4 passando
- [ ] Login como motorista mostra só o próprio extrato

---

## Etapa 14 — Pré-produção (recomendado, fora da especificação)

```
Leia CLAUDE.md e docs/progresso.md. Etapa 14 de 15: pré-produção.

Escopo:
- Auditoria de segurança completa (multi-tenant, autenticação, ingestão, segredos, dependências, cabeçalhos HTTP, CORS, CSP); relatório com achados e correção dos críticos.
- Observabilidade: lag da fila, pacotes rejeitados, última mensagem por ativo, tempo de cálculo de KPIs e de ciclos, falhas de envio de relatório; alertas.
- Backups criptografados com teste de restauração documentado.
- Retenção de dados por tenant (LGPD) executada pelo scheduler.
- Deploy: imagens enxutas, migrations no pipeline, variáveis por ambiente, docs/deploy.md.

Plano antes de codar; espere meu OK. Ao final: progresso, decisões, commit e PR de feature/foundation para main com o resumo das etapas.
```

**Conferir antes de seguir**
- [ ] Nenhum achado crítico de segurança em aberto
- [ ] Restauração de backup testada de verdade

---

## Etapa 15 — Assistente MCP e emissões (pós-v1)

```
Leia CLAUDE.md e docs/progresso.md. Etapa 15 de 15: Fase 5 da especificação (pós-v1).

Escopo:
- Servidor MCP somente leitura sobre a API de KPIs, autenticado como o usuário, respeitando tenant e papel.
- Relatório de emissões diretas (escopo 1) por período e grupo.
- Modo privacidade (ocultar posição fora do expediente configurado) e rotas planejadas × realizadas.

Aceite: o MCP não devolve dado de outro tenant (mesmo teste de isolamento da etapa 2); relatório de emissões bate com os litros do período.
Plano antes de codar; espere meu OK. Ao final: progresso, decisões e commit.
```

---

## Se algo der errado no meio de uma etapa
```
Pare. Leia CLAUDE.md e docs/progresso.md. Explique em até 10 linhas o que quebrou, a causa provável e duas opções de correção com prós e contras. Não altere código até eu escolher.
```

## Para retomar uma etapa interrompida
```
Leia CLAUDE.md, docs/progresso.md e o git log do branch atual. Diga em que ponto a etapa N parou, o que falta e o próximo passo. Espere meu OK antes de continuar.
```
