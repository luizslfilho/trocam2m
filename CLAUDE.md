# CLAUDE.md — contexto permanente do projeto

Fonte de verdade: `docs/especificacao.md`. Este arquivo **resume** a especificação; em caso de dúvida, vale ela.
Se achar contradição ou lacuna na especificação: **pare e pergunte**. A correção é feita no arquivo, não na conversa.

## Produto
- Independente de equipamento: lê as plataformas onde as rastreadoras já estão (Wialon, RedGPS; outras depois, ex.: flespi).
- Linguagem simples para o gestor; termos técnicos (SPN, FMI, CAN) só no drawer de detalhes.
- Qualidade do dado explícita em todo número. **Nenhuma promessa de ganho percentual**: o argumento é dado confiável.

## Regras de domínio inegociáveis (resumo)
**1.1 Categorias** — frota mista na v1: tudo funciona com `truck` e `yellow_line` juntos e separados.
- `truck`: base odômetro; consumo km/L e L/h; ociosidade = ignição ligada, RPM > 0 e velocidade < 3 km/h.
- `yellow_line`: base horímetro; consumo L/h; ociosidade = ignição ligada, RPM > 0 e carga abaixo do limiar (padrão 20 %, por modelo). "Trabalhando" = carga (SPN 92) ou torque (SPN 513) acima do limiar, ou PTO ativa. Sem sinal de carga: RPM acima da marcha lenta e KPI `partial`.
- **Ociosidade evitável**: PTO ativa (Munck, cesto, betoneira, bomba) **não** é ociosidade, é trabalho. Cercas de "ociosidade permitida" podem ser excluídas. O gestor vê a evitável; a bruta fica no drawer.

**1.1.1 Revenda** — revendedor → cliente (tenant) → grupos de ativos. Marca do revendedor pelo host. Revendedor só vê os seus clientes; cliente nunca vê outro cliente. RLS nos dois níveis (`tenant_id`; tenants do `reseller_id`). Credencial de plataforma do revendedor pode ser compartilhada, com mapeamento explícito unidade → cliente.

**1.1.2 Motorista** — vem da plataforma de origem: RFID/iButton (via `param_mapping`) ou vínculo fixo (plataforma ou nosso cadastro). `driver_assignments` com período e `source` (`rfid`, `platform_assignment`, `fixed`); prioridade RFID > plataforma > fixo. KPIs pelo período de vínculo, **nunca** o vínculo atual aplicado ao passado. Sem motorista = "sem motorista", fora do ranking.

**1.2 RPM** — faixas por modelo: 1 marcha lenta parado, 2 marcha lenta em movimento, 3 extra econômica, 4 econômica, 5 RPM máximo (> `eco_max`). Tempo **ponderado pela duração da amostra**, nunca pela contagem de mensagens.

**1.3 Banguela** — com sinal de marcha: > 15 km/h em neutro. Sem sinal: `possivel_banguela` = RPM ≤ `idle_max` por > 20 s acima de 30 km/h. Limiares configuráveis.

**1.4 Saneamento CAN** — erro/"não disponível" **nunca vira zero**, vira `null` (sentinelas brutos de 1, 2 e 4 bytes e sentinelas já escalados, ex.: RPM 8031,875). Faixa física por parâmetro (RPM 0–4000, velocidade 0–160, nível 0–100 %, tensão 0–36 V) e salto impossível. RPM 0 com ignição ligada em movimento = falha de leitura. Flags: `sentinel_removed`, `out_of_range`, `spike`, `gap_before`.

**1.5 DTC** — `dtc_dictionary` pequeno, marcado "a revisar por especialista" (não inventar códigos). Alerta abre na 1ª ocorrência e fecha após N min sem o código; guarda duração. `critical` gera parada `suggested`, que só vale após confirmação do gestor.

**1.6 Fora de ordem e idempotência** — chave única `(tenant_id, asset_id, source, ts_utc)`; Redis com TTL é atalho, garantia é `ON CONFLICT DO NOTHING`. Cálculo sempre por `ts_utc` do equipamento; guardar `received_at`. Dado atrasado reprocessa as janelas (aggregates com refresh ≥ 7 dias para trás; KPIs, viagens e ocorrências). Agregados diários no **fuso do tenant** (padrão `America/Sao_Paulo`).

**1.7 Qualidade** — todo KPI da API traz `quality: reliable | partial | unreliable` e o motivo. `unreliable` aparece, mas fica fora de rankings e médias.

**1.8 Viagens** — ignição (ou movimento) do início ao fim, com tolerância de parada (padrão 3 min). Motorista pelo período de vínculo. Recalcular com dado atrasado.

**1.9 Preventiva** — plano por modelo ou ativo; gatilho horímetro, odômetro e/ou data (vence o que chegar primeiro). Estados `ok`, `due_soon`, `overdue`. Próximo vencimento pela leitura real da execução.

**KPIs (Seção 5)** — seguir as definições da tabela da especificação ao pé da letra. Destaques: utilização usa a jornada operacional do tenant (padrão 12 h/dia), nunca 24 h; disponibilidade só com manutenção lançada (`suggested` não conta; aberta conta até agora); custo da ociosidade usa o preço do diesel **vigente na data**; litros estimados marcados como `estimado`; fator de CO₂ (padrão 2,68 kg/L) e sua fonte são configuração, nunca constante no código; divergência de abastecimento é **"anomalia a investigar"**, nunca "fraude", ligada a ativo e transação, nunca a pessoa.

## Programa de Boa Condução — cuidado jurídico
- É **prêmio por desempenho**, nunca desconto salarial (CLT art. 462). Textos: "gratificação conquistada", "pontos de conduta", "ocorrência", "peso". **Proibido** "multa", "desconto" e "penalidade" em tela, relatório e e-mail.
- Premiação só é ativada depois de registrar a política do programa e a data de ciência dos motoristas.
- Valores em R$ da gratificação só para `admin`.
- Só desconta ocorrência `reliable` com motorista identificado; as demais aparecem com peso 0 (`void_quality`).
- Ciclo fechado é congelado; dado atrasado depois do fechamento vira ajuste no ciclo seguinte. Pesos versionados: ocorrência passada mantém o peso vigente quando aconteceu. Velocidade só por categoria e cerca (sem limite por via). Direção contínua só `truck` com motorista identificado. Contestação e decisão vão para o audit log.

## Segurança (Seção 4) e LGPD
- Toda tabela de negócio com `tenant_id NOT NULL` indexado e RLS ativa. Role da aplicação **sem `BYPASSRLS`**. `SET LOCAL app.tenant_id` (e `app.reseller_id`) por transação, vindo **só do token**.
- Teste de isolamento (tenant × tenant, revendedor × revendedor, inclusive com IDs alheios na API) roda no CI e bloqueia merge.
- Ingestão: `X-Ingest-Token` por fonte e tenant, guardado como hash, `hmac.compare_digest`, limite de corpo, rate limit, Pydantic `extra="forbid"`, inválido vai para rejeitados sem derrubar o lote.
- Credenciais de plataforma com envelope encryption (env em dev, KMS em produção); tokens das plataformas sempre somente leitura.
- JWT curto + refresh em cookie `httpOnly`, `Secure`, `SameSite=Strict`; nada de token no `localStorage`. Papéis: `reseller_admin`, `admin`, `fleet_manager`, `viewer`, `driver` (só o próprio extrato; contesta; ligado por `users.driver_id`, sem ele não acessa nada).
- Front e API no mesmo host de cada revendedor, via proxy reverso (front em `/`, API em `/api`).
- CORS restrito; audit log de acessos administrativos e de toda mudança de pontuação/configuração.
- **LGPD:** dado de condução identifica o motorista. **Logs sem dados pessoais.** Retenção configurável por tenant (ocorrências e ciclos fechados: 5 anos); motorista acessa os próprios dados; finalidade do programa registrada por tenant.

## Stack e comandos
- Back-end: Python 3.12, FastAPI, Pydantic v2 + Settings, SQLAlchemy 2.0 async, asyncpg, Alembic. Ingestão em módulo isolado (extraível).
- Redis Streams (ingestão → worker em lote) e Redis Hash (`asset_live_state`).
- PostgreSQL 16 + TimescaleDB: hypertable `telemetry_raw` (compressão após 7 dias), aggregates horário e diário, RLS.
- Front: TypeScript, React (Vite), Tailwind, shadcn/ui, Recharts, TanStack Query, MapLibre GL (tiles por variável de ambiente; nunca os públicos do OSM em produção).
- Relatórios PDF/Excel no back-end, agendador e SMTP configurável.
- Serviços no docker-compose: api, worker, poller, scheduler, timescaledb, redis, frontend.

| Comando | Faz |
|---|---|
| `make up` | sobe o ambiente local |
| `make test` | roda os testes (integração com TimescaleDB real) |
| `make lint` | ruff, mypy, ESLint, `tsc --noEmit` |
| `make seed` | carrega dados fictícios |

## Convenções
- ruff e mypy (strict em `app/domain`) limpos antes de todo commit.
- **Toda regra de negócio tem teste**; KPIs com valor esperado calculado à mão.
- Migrations **só via Alembic**; nunca alterar o schema à mão.
- **Nenhum segredo no código**; `.env.example` sem valores reais.
- **Não inventar formato de API**: sem documentação oficial (RedGPS, parâmetros Wialon por modelo de rastreador), usar `# TODO(doc)`, fixture fictícia em `tests/fixtures/` e mapeamento configurável; registrar em `docs/progresso.md`.
- **Nenhum dado real de cliente** (nomes, placas, IMEIs, coordenadas) em seed, fixture, teste ou exemplo.
- Código simples e testado vale mais que código "completo" sem teste. Nunca usar `git worktree`.

## Fluxo de trabalho
1. Ler este arquivo e `docs/progresso.md` no início da sessão.
2. **Uma etapa por vez** (guia: `etapas-claude-code-v2.md`). Mostrar o plano (arquivos, schema, decisões) e **esperar OK** antes de codar.
3. Ao terminar: testes e lint passando, resultado mostrado.
4. Atualizar `docs/progresso.md` (status, pendências `TODO(doc)`) e `docs/decisoes.md` (uma linha por decisão).
5. Commit com mensagem clara. Push só quando o dono pedir.
