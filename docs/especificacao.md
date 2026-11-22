# PAPEL
Atue como arquiteto de software sênior em telemetria veicular (CAN J1939), gestão de frota pesada (caminhões rodoviários e fora de estrada, máquinas da linha amarela) e SaaS multi-tenant de missão crítica.

Objetivo: construir a base modular, segura e escalável de uma plataforma de gestão de ativos por telemetria, recebendo dados da **Wialon** e da **RedGPS**, preparada para outras fontes no futuro (ex.: flespi).

Posicionamento do produto: independente de equipamento (lê as plataformas onde as rastreadoras já estão), linguagem simples para o gestor e **qualidade do dado explícita em todo número** (1.7). Nenhuma promessa de ganho percentual no produto ou no material: o argumento é dado confiável.

---

# 0. COMO TRABALHAR (OBRIGATÓRIO)
- Git: repositório próprio. Primeiro commit em `main` (README, .gitignore, licença); depois crie o branch `feature/foundation`. **Nunca use git worktree.** Um commit por fase, com mensagem clara.
- **Não gere tudo de uma vez.** Execute por fases (Seção 8). No início de cada fase, mostre o plano (arquivos, schema, decisões) e espere meu OK. Ao fim de cada fase, rode testes e lint e me mostre o resultado.
- **Não invente formatos de API.** Onde não houver documentação oficial (campos do RedGPS, nomes de parâmetros da Wialon por modelo de rastreador), crie a estrutura com `# TODO(doc)`, fixtures de exemplo em `tests/fixtures/` claramente marcadas como fictícias e um mapeamento configurável. Liste no fim de cada fase o que ficou pendente de documentação.
- **Nenhum dado real de cliente** em seed, fixture, teste ou exemplo: nomes, placas, IMEIs e coordenadas são fictícios.
- Prefira código simples e testado a código "completo" sem teste. Nada de segredo no código.
- Se encontrar contradição neste prompt, pare e pergunte antes de escolher.

---

# 1. DOMÍNIO E REGRAS DE NEGÓCIO

## 1.1 Categorias de ativo (`asset_category`)
| Categoria | Base de medida | Consumo | Ociosidade |
|---|---|---|---|
| `truck` | odômetro (km) | km/L e L/h | ignição ligada, RPM > 0 e velocidade < 3 km/h |
| `yellow_line` | horímetro (h) | L/h | ignição ligada, RPM > 0 e carga do motor abaixo do limiar de trabalho (padrão 20%, configurável por modelo) |

Para `yellow_line`, "trabalhando" = carga do motor (SPN 92) ou torque real (SPN 513) acima do limiar, ou tomada de força ativa quando disponível. Sem sinal de carga, use RPM acima da marcha lenta e marque o KPI como qualidade `partial` (rótulo "Parcial" na interface).

Para `truck`, "trabalhando" = ignição ligada e velocidade ≥ 3 km/h, ou tomada de força (PTO) ativa (Munck, cesto, betoneira, bomba), mesmo parado. Motor ligado parado sem PTO é ociosidade, não trabalho. A utilização de caminhão conta movimento + PTO.

**Ociosidade evitável:** para as duas categorias, tempo com tomada de força (PTO) ativa — Munck, cesto, betoneira, bomba hidráulica — **não** é ociosidade; conta como trabalho. Também podem ser excluídas por configuração as paradas dentro de cercas marcadas como "ociosidade permitida" (ex.: oficina). O KPI exibido ao gestor é a ociosidade evitável; a bruta fica no drawer.

A v1 atende as duas categorias ao mesmo tempo (frota mista). Toda tela, KPI e seed precisa funcionar com `truck` e `yellow_line` juntos e separados.

## 1.1.1 Hierarquia de clientes e revenda (white-label desde a v1)
- Três níveis: **revendedor** (rastreadora, ex.: dono da base instalada) → **cliente** (tenant, a empresa dona da frota) → **grupos de ativos** (frota, obra, frente de serviço).
- Cada revendedor tem marca própria: nome, logo, cores e domínio/subdomínio, carregados pelo front a partir do host acessado.
- O revendedor enxerga e administra apenas os seus clientes; um cliente nunca vê outro cliente, nem do mesmo revendedor.
- RLS precisa cobrir os dois níveis: usuário de cliente filtra por `tenant_id`; usuário de revendedor filtra pelos `tenant_id` vinculados ao seu `reseller_id`.
- Credenciais de plataforma (Wialon/RedGPS) podem pertencer ao revendedor e ser compartilhadas entre os clientes dele, com mapeamento explícito de quais unidades pertencem a qual cliente.

## 1.1.2 Identificação do motorista
- O motorista vem **da própria plataforma de origem** (Wialon ou RedGPS), por dois caminhos:
  - **RFID/iButton:** código lido pelo rastreador e enviado como parâmetro; o adaptador extrai o código e resolve o motorista pelo cadastro.
  - **Vínculo fixo:** atribuição motorista ↔ unidade feita na plataforma (na Wialon, motoristas do recurso e suas atribuições) ou cadastrada no nosso sistema.
- Tabela `driver_assignments` com período (`started_at`, `ended_at`), ativo, motorista e `source` (`rfid`, `platform_assignment`, `fixed`). Prioridade quando houver conflito: RFID > atribuição da plataforma > vínculo fixo.
- KPIs e score por motorista são calculados pelos períodos de vínculo, nunca pelo vínculo atual aplicado ao passado.
- Período sem motorista identificado aparece como "sem motorista" e fica fora do ranking.
- Nomes de parâmetro do RFID por modelo de rastreador seguem o `param_mapping` (marcar `TODO(doc)` onde não houver documentação).

## 1.2 Faixas de RPM (limites configuráveis por modelo de veículo)
1. Marcha lenta parado: RPM ≤ `idle_max` e velocidade < 3 km/h
2. Marcha lenta em movimento: RPM ≤ `idle_max` e velocidade ≥ 3 km/h
3. Extra econômica: `idle_max` < RPM ≤ `extra_eco_max`
4. Econômica: `extra_eco_max` < RPM ≤ `eco_max`
5. RPM máximo: RPM > `eco_max`

Tempo por faixa **ponderado pela duração de cada amostra**, nunca pela contagem de mensagens.

## 1.3 Banguela (coasting)
- Com sinal de marcha/embreagem no CAN: velocidade > 15 km/h com marcha em neutro.
- Sem esse sinal: evento `possivel_banguela` quando RPM ≤ `idle_max` por > 20 s com velocidade > 30 km/h. Limiares configuráveis.

## 1.4 Saneamento CAN J1939
- Valores de "erro" e "não disponível" nunca viram zero: viram `null`.
  - Dado bruto: 1 byte `0xFE`/`0xFF`; 2 bytes `0xFE00–0xFEFF`/`0xFF00–0xFFFF`; 4 bytes faixas equivalentes.
  - Dado já decodificado pela plataforma (caso comum na Wialon): o sentinela aparece escalado (ex.: RPM 8031,875 = 0xFFFF × 0,125). Por isso, além dos sentinelas, aplique **faixa física válida por parâmetro** (ex.: RPM 0–4000, velocidade 0–160 km/h, nível 0–100%, tensão 0–36 V) e detecção de salto impossível entre amostras.
- RPM = 0 com ignição ligada e veículo em movimento = falha de leitura, não motor desligado.
- Cada pacote normalizado carrega flags de qualidade (`sentinel_removed`, `out_of_range`, `spike`, `gap_before`).

## 1.5 Códigos de falha (DM1 – SPN/FMI)
- Tabela `dtc_dictionary` (SPN, FMI, descrição em português simples, severidade `critical`/`warning`/`info`, ação sugerida). Comece com um seed pequeno e marque como "a revisar por especialista"; não invente dezenas de códigos.
- Alerta abre na primeira ocorrência ativa e fecha quando o código some por N minutos (configurável). Guardar duração em aberto.
- Alerta `critical` gera uma **sugestão de parada** em `maintenance_events` (status `suggested`); só vira parada real quando o gestor confirma.

## 1.6 Área de sombra, dados fora de ordem e idempotência
- Rastreadores descarregam histórico fora de ordem ao recuperar sinal.
- Chave de unicidade: `(tenant_id, asset_id, source, ts_utc)`. Redis com TTL é só um atalho; a garantia final é `ON CONFLICT DO NOTHING` no banco.
- Todo cálculo usa `ts_utc` do equipamento, nunca a hora de chegada. Guardar também `received_at`.
- Dado atrasado deve reprocessar as janelas afetadas: política de refresh dos continuous aggregates cobrindo pelo menos 7 dias para trás e recálculo de KPIs, viagens e ocorrências do período atingido.
- Agregados diários no **fuso do tenant** (padrão `America/Sao_Paulo`), não em UTC. Montados a partir do agregado horário em UTC; vale para fusos de hora cheia (todo o Brasil). Fuso com meia hora exige revisão.

## 1.7 Qualidade do dado (diferencial do produto)
Todo KPI devolvido pela API vem com `quality: "reliable" | "partial" | "unreliable"` e o motivo (ex.: "6 ativos sem RPM via CAN no período", "lacuna de comunicação de 3 h"). KPI `unreliable` é exibido, mas fica fora de rankings e médias da frota.

## 1.8 Viagens
- Viagem = do início ao fim da ignição (ou movimento, quando não houver ignição), com tolerância de parada configurável (padrão 3 min) para não quebrar a viagem em semáforo.
- Guardar: ativo, motorista (pelo período de vínculo), início, fim, distância, duração, tempo parado, velocidade máxima, litros (quando houver), origem e destino (cerca ou coordenada).
- Viagens são recalculadas quando chega dado atrasado no intervalo (1.6).

## 1.9 Manutenção preventiva
- Plano por modelo ou por ativo: item (ex.: troca de óleo), gatilho por **horímetro**, **odômetro** e/ou **data** (o que vencer primeiro), intervalo e antecedência do aviso.
- Estados: `ok`, `due_soon`, `overdue`. Ao lançar a execução, o próximo vencimento é recalculado a partir da leitura real do dia.

---

# 2. STACK
- **Back-end:** Python 3.12, FastAPI, Pydantic v2, SQLAlchemy 2.0 async, asyncpg, Alembic para migrations. Ingestão isolada em módulo próprio, para poder ser extraída depois (ex.: para Go) sem mexer no resto.
- **Fila e estado vivo:** Redis Streams (ingestão → worker de escrita em lote) e Redis Hash para `asset_live_state`.
- **Banco:** PostgreSQL 16 + TimescaleDB: hypertable `telemetry_raw` com compressão após 7 dias, continuous aggregate horário (UTC) e diário montado a partir dele no fuso do tenant, Row-Level Security nas tabelas relacionais. Como o TimescaleDB não aceita RLS em hypertable com compressão nem com continuous aggregate, a telemetria fica num schema interno sem acesso direto da aplicação (ver Seção 4).
- **Cercas:** sem PostGIS; geometria em GeoJSON com bbox e teste ponto-em-cerca em Python atrás de uma interface (`GeofenceMatcher`). Tipos: polígono, círculo e linha com largura.
- **Front-end:** TypeScript, React (Vite), Tailwind, shadcn/ui, Recharts, TanStack Query; mapa com MapLibre GL. Provedor de tiles definido por variável de ambiente; em produção, nunca os tiles públicos do OpenStreetMap (em dev, qualquer provedor gratuito).
- **Relatórios:** geração de PDF e Excel no back-end, agendador de tarefas (ex.: APScheduler ou worker dedicado) e envio por e-mail via SMTP configurável.
- **Qualidade:** ruff, mypy (strict no domínio), pytest + pytest-asyncio, testes de integração com TimescaleDB real via docker; ESLint e `tsc --noEmit` no front.
- **Local:** `docker-compose.yml` com api, worker, poller, scheduler, timescaledb, redis e frontend. `make up`, `make test`, `make seed`, `make lint`.

---

# 3. INGESTÃO POR FONTE
O retranslator da Wialon fala protocolos TCP próprios (Wialon IPS, Retranslator), não JSON por HTTP. Por isso:

- **Wialon, modo pull (implementar agora):** poller por tenant usando a Remote API (`token/login`, `core/search_items`, `messages/load_interval` em janelas de 1 h, sempre `messages/unload`), relogin automático no erro de sessão, backoff exponencial e checkpoint do último `ts` lido por unidade.
- **Wialon, modo push (deixar a interface pronta):** retranslator → gateway (ex.: flespi) → `POST /api/v1/ingest/stream/{source}` em JSON.
- **RedGPS:** adaptador conforme a documentação oficial que eu fornecer; até lá, stub com `TODO(doc)` e fixture fictícia.
- Todos os adaptadores convertem para o schema canônico `CanonicalTelemetryPacket` através de `param_mapping` configurável por `(source, hardware_model)`. Nenhum KPI pode depender de detalhe da fonte.
- O pacote canônico inclui, além de posição, velocidade, ignição e CAN: **tensão da bateria/alimentação**, **PTO**, **cinto** (quando houver), **acelerômetro/eventos de frenagem, aceleração e curva bruscas** (quando o rastreador gerar), **RFID** e **VIN** (para preencher o cadastro do ativo).

---

# 4. SEGURANÇA
- **Multi-tenant:** toda tabela de negócio com `tenant_id` NOT NULL e indexado; RLS ativa em todas as tabelas relacionais. Exceção: `telemetry_raw` e os aggregates ficam sem RLS num schema interno sem GRANT para a aplicação, lidos só por funções que exigem o contexto de tenant (erro se ausente) e gravados por uma role de ingestão só com INSERT; role da aplicação sem `BYPASSRLS`; tenant aplicado via `SET LOCAL app.tenant_id` em cada transação, vindo do token, nunca do corpo da requisição.
- **Teste obrigatório:** um tenant não lê nem escreve dado de outro, nem chamando a API com IDs alheios; um revendedor não acessa clientes de outro revendedor. Esse teste roda no CI e bloqueia merge.
- **Ingestão:** token por fonte e por tenant (`X-Ingest-Token`), guardado como hash, comparado com `hmac.compare_digest`; limite de tamanho de corpo; rate limit por token; Pydantic estrito (`extra="forbid"`); payload inválido vai para uma fila de rejeitados com o motivo, sem derrubar o lote.
- **Credenciais das plataformas** (tokens Wialon/RedGPS por tenant): criptografadas (envelope encryption; chave por variável de ambiente em dev, KMS em produção). Sempre tokens somente leitura.
- **Usuários:** JWT de curta duração + refresh, entregue em cookie `httpOnly`, `Secure`, `SameSite=Strict` (nada de token no `localStorage`). RBAC: `reseller_admin` (administra seus clientes e a marca), `admin` (administra o próprio cliente, vê valores de gratificação), `fleet_manager` (opera, lança manutenção, trata contestações), `viewer` (só leitura), `driver` (vê apenas o próprio extrato e contesta ocorrências). O usuário `driver` se liga ao cadastro de motorista por `users.driver_id` (nullable); `driver` sem `driver_id` não acessa nada.
- **Mesmo host por revendedor:** front e API servidos no mesmo host de cada revendedor, atrás de proxy reverso (front em `/`, API em `/api`), para o cookie `SameSite=Strict` funcionar em domínio próprio.
- **Geral:** Pydantic Settings + `.env.example`; CORS restrito; logs sem dados pessoais; audit log de acessos administrativos e de toda mudança de configuração de pontuação.
- **LGPD:** dado de condução identifica o motorista. Política de retenção configurável por tenant (padrão: telemetria bruta por [A DEFINIR PELO DONO]; ocorrências e ciclos fechados por 5 anos); o motorista tem acesso aos próprios dados; finalidade do programa de condução registrada por tenant.

---

# 5. KPIs (DEFINIÇÕES QUE A API DEVE SEGUIR)
| KPI | Definição |
|---|---|
| Disponibilidade física | (horas do período − horas em manutenção) ÷ horas do período, com **24 h por dia** (horas de calendário). Mede se o ativo estava apto; a utilização mede quanto da jornada o ativo apto trabalhou. Manutenção vem de **lançamento manual** na tabela `maintenance_events` (ativo, tipo preventiva/corretiva, motivo, início, fim, quem lançou). Parada aberta conta até agora. Sugestões (`suggested`) não contam. Sem nenhum lançamento no período, o KPI sai como `partial`. |
| Utilização | horas trabalhando ÷ horas disponíveis. "Horas disponíveis" = jornada operacional do tenant (Seção 6, padrão 12 h/dia) reduzida proporcionalmente pelas horas em manutenção; nunca 24 h como base. "Trabalhando" segue 1.1 por categoria. Também por dias usados no período e por grupo. |
| Ociosidade evitável | horas de ociosidade (1.1, já sem PTO e sem cercas permitidas) e % sobre horas de motor ligado; paradas acima do tempo máximo configurado separadas dentro/fora de cercas. |
| Custo da ociosidade | litros na ociosidade evitável × preço do diesel vigente na data. Litros: delta do contador de combustível do CAN; sem CAN, horas × `idle_lph` do modelo, marcado como `estimado`. |
| CO₂ | litros × fator de emissão configurável por tenant (padrão do sistema 2,68 kg CO₂/L; valor e fonte como configuração, não fixo no código). Calculado para a ociosidade e para o consumo total (relatório de emissões diretas, escopo 1). |
| Consumo | `truck`: km/L e L/h; `yellow_line`: L/h. Comparado à média padrão do modelo (meta). |
| Autonomia | nível atual do tanque (L) × km/L real dos últimos 7 dias (ou média padrão do modelo, marcado como `estimado`); `yellow_line`: litros ÷ L/h. |
| Faixa econômica | % do tempo com motor ligado nas faixas 3 e 4 de 1.2. |
| Eventos severos | excesso de velocidade, sobre-giro (faixa 5 acima de N s), frenagem/aceleração/curva bruscas, possível banguela, por 100 km ou por 10 h. |
| Divergência de abastecimento | litros lançados (cartão, ERP ou manual em `fuel_transactions`) × aumento de nível medido pela sonda/CAN na janela do abastecimento. Diferença acima da tolerância vira **anomalia a investigar**, nunca "fraude"; vinculada a ativo e transação, não a pessoa. |
| Saúde elétrica | tensão da bateria fora da faixa (configurável por 12 V/24 V) e quedas de alimentação do rastreador (possível violação). |

## 5.1 Programa de Boa Condução
Nomenclatura na interface: **Programa de Boa Condução**; o motorista tem **pontos de conduta**; cada mau hábito registrado é uma **ocorrência**; o desconto de cada tipo é o seu **peso**.

**Mecânica**
- A cada **ciclo** (padrão mensal, configurável), cada motorista começa com **pontos iniciais** (padrão 100).
- Cada ocorrência válida desconta o seu peso. O saldo não fica abaixo de 0.
- **Bônus de bons hábitos** opcionais (ex.: +2 por semana sem ocorrência; +3 se a faixa econômica do ciclo passar de X%), com teto nos pontos iniciais.
- **Faixas de premiação** configuráveis (ex.: 90–100 Ouro = 100% da gratificação; 75–89 Prata = 50%; abaixo de 75 = sem gratificação).
- Exibir sempre, ao lado do saldo, **ocorrências por 100 km** (`truck`) ou **por 10 h** (`yellow_line`), para não punir quem roda mais.
- **Só desconta** ocorrência com dado `reliable` e com motorista identificado (1.1.2). Ocorrência de dado `partial`/`unreliable` aparece, marcada, mas com peso 0.
- **Contestação:** motorista ou gestor marca a ocorrência como `contested`; `fleet_manager`/`admin` aceita (pontos voltam) ou recusa, com justificativa. Tudo no audit log.
- O ciclo fecha em data configurável; após o fechamento, o resultado fica congelado (`scoring_cycles.closed_at`). Dado atrasado que chegue depois do fechamento gera ajuste visível no ciclo seguinte, não altera o fechado.
- Mudança de pesos ou limites vale a partir da data da mudança; ocorrências passadas mantêm o peso vigente quando ocorreram (versionar a configuração).

**Ocorrências e pesos padrão (todos configuráveis, podendo ser desligados)**
| Ocorrência | Regra padrão | Peso |
|---|---|---|
| Ociosidade acima do tempo máximo | parado com motor ligado > 5 min (sem PTO, fora de cerca permitida); 1 ocorrência a cada bloco de 10 min | 1 por bloco |
| Excesso de velocidade leve | acima do limite + tolerância (5 km/h) até +10 km/h, por ≥ 10 s | 2 |
| Excesso de velocidade médio | +10 a +20 km/h por ≥ 10 s | 4 |
| Excesso de velocidade grave | acima de +20 km/h por ≥ 10 s | 8 |
| Sobre-giro (RPM máximo) | faixa 5 por > 5 s | 3 |
| Possível banguela | regra 1.3 | 5 |
| Frenagem brusca | evento do rastreador/acelerômetro | 4 |
| Aceleração brusca | idem | 2 |
| Curva brusca | idem | 3 |
| Sem cinto em movimento | quando o sinal existir; > 30 s acima de 10 km/h | 5 |
| Condução sem identificação | ativo em movimento sem RFID lido quando o tenant exige RFID | 3 |
| Direção contínua acima do limite | sem pausa mínima após o tempo máximo (Lei 13.103); só `truck` e só com motorista identificado, senão não é gerada | 5 |

Cada ocorrência guarda: tipo, motorista, ativo, início, fim, local, valor medido × limite (ex.: "92 km/h com limite de 60 na cerca Pátio" ou "92 km/h com limite geral de 80"), peso aplicado, versão da configuração, qualidade do dado e status (`valid`, `contested`, `accepted_contest`, `rejected_contest`, `void_quality`).

**Cuidado jurídico (refletir no texto da interface e na documentação)**
- O programa é **prêmio por desempenho**, nunca desconto salarial (CLT art. 462). A interface fala em "gratificação conquistada", não em "multa" ou "desconto".
- O tenant registra a política do programa (texto livre e data de ciência dos motoristas) antes de ativar a premiação.
- Valores em R$ da gratificação só aparecem para `admin`.

---

# 6. CONFIGURAÇÃO (ABA "CONFIGURAÇÕES")
Hierarquia de herança: **padrão do sistema → cliente (tenant) → grupo de ativos → modelo de veículo → ativo**. A tela mostra de onde vem cada valor ("herdado do cliente") e permite sobrescrever no nível atual. Toda alteração é versionada (`config_versions`: quem, quando, valor anterior e novo) e entra no audit log.

**Ociosidade**
- Tempo máximo parado com motor ligado antes de virar ocorrência (padrão 5 min)
- Bloco de tempo para ocorrências repetidas (padrão 10 min)
- Excluir tempo com PTO ativa (sim/não)
- Cercas com ociosidade permitida (pátio, oficina, frente de serviço)

**Velocidade**
- Limite geral por categoria (padrão 80 km/h `truck`, 40 km/h `yellow_line`)
- Limite por cerca (ex.: pátio 20, mina 40, perímetro urbano 60)
- Não há limite por via na v1 (sem map-matching): vale o da cerca ou o limite geral da categoria
- Tolerância (padrão +5 km/h) e duração mínima para contar (padrão 10 s)
- Faixas leve/médio/grave (padrão +10 e +20 km/h)

**Motor (por modelo)**
- `idle_max` (marcha lenta), `extra_eco_max`, `eco_max`, RPM máximo absoluto (para faixa física válida)
- Tempo mínimo em RPM máximo para ocorrência (padrão 5 s)
- Limiar de carga para "trabalhando" em `yellow_line` (padrão 20%)
- Limiares de banguela (1.3)

**Combustível, custo e emissões**
- Preço do diesel (R$/L) com **data de vigência**; histórico preservado para o passado não mudar
- Média padrão km/L por modelo (meta e base da autonomia) e L/h para `yellow_line`
- Consumo em marcha lenta `idle_lph` por modelo (para quando não houver CAN)
- Capacidade do tanque por modelo/ativo (litros)
- Tolerância de divergência de abastecimento (padrão 5% ou X L, o maior)
- Fator de CO₂ (kg/L, padrão 2,68) e a fonte do fator, obrigatória ao salvar. Fonte padrão: "Referência genérica para diesel fóssil (fator padrão IPCC 2006). Revisar com a ferramenta do Programa Brasileiro GHG Protocol, que considera a mistura obrigatória de biodiesel." Valor e fonte padrão aparecem marcados como "a revisar pelo cliente"

**Jornada**
- Jornada operacional (horas disponíveis por dia para a utilização; padrão 12 h/dia)
- Tempo máximo de direção contínua (padrão 5 h 30) e pausa mínima (padrão 30 min)

**Programa de Boa Condução**
- Liga/desliga o programa; ciclo (mensal/quinzenal) e dia de fechamento
- Pontos iniciais; peso de cada ocorrência (e liga/desliga por tipo)
- Bônus de bons hábitos e teto
- Faixas de premiação, nome das faixas e % da gratificação; valor base da gratificação (R$, opcional)
- Exigir RFID (sim/não)
- Texto da política e data de ciência

**Manutenção**
- Planos preventivos por modelo (1.9) e antecedência do aviso
- Tempo para fechar alerta DTC após sumir (1.5)

**Comunicação e qualidade**
- Tempo sem dado para status "sem sinal" (padrão 30 min) e para "lacuna" no KPI (padrão 2 h)
- Faixa de tensão normal por sistema (12 V / 24 V)

**Fuso e unidades**
- Fuso do tenant (padrão `America/Sao_Paulo`), moeda e formato de data

---

# 7. TELAS

## 7.1 Dashboard do gestor
Sem jargão na superfície. Termos técnicos (SPN, FMI, parâmetros CAN) só no drawer de detalhes. Organizado em **abas por tema**: Visão geral, Combustível e emissões, Condução, Utilização, Manutenção.

1. **Cabeçalho:** categoria (Todos / Caminhões / Linha amarela), grupo, período (Hoje / 7 dias / 30 dias / ciclo), busca e contador clicável de alertas críticos.
2. **Zona 1 – quatro cards:** disponibilidade física, utilização, consumo e desperdício (km/L ou L/h conforme o filtro, custo em R$ e CO₂ da ociosidade evitável) e alertas críticos ativos. Cada card mostra o selo de qualidade do dado.
3. **Zona 2 – gráficos:** distribuição do tempo da frota por dia (barra empilhada: trabalhando, marcha lenta, deslocamento, desligado, manutenção, sem dado) e combustível total × desperdiçado na ociosidade por dia, com R$.
4. **Zona 3 – saúde e operação:** alertas mecânicos em linguagem simples (ativo, problema, severidade, tempo em aberto), manutenções preventivas vencendo e índice de faixa econômica da frota com resumo de eventos severos.
5. **Zona 4 – ao vivo:** mapa com os ativos (cor por status) e tabela com status (trabalhando, marcha lenta, alerta crítico, sem sinal há X min), fonte, horímetro/odômetro, consumo atual, autonomia e drawer com parâmetros CAN, SPN/FMI, tensão e últimas 24 h.

## 7.2 Programa de Boa Condução
1. **Ranking do ciclo:** posição, motorista, pontos de conduta, faixa, km ou horas no ciclo, ocorrências por 100 km / 10 h, tendência contra o ciclo anterior. Motoristas com dado insuficiente aparecem à parte, sem posição.
2. **Extrato do motorista:** lista de ocorrências em linguagem simples ("Ficou 18 min parado com motor ligado na Av. X"), com mapa, valor medido × limite, peso, status e botão de contestar.
3. **Fila de contestações** para o gestor.
4. **Visão do motorista** (papel `driver`): só o próprio saldo, extrato e faixa atual.

## 7.3 Outras telas
- **Viagens:** lista e trajeto no mapa por ativo/motorista/período.
- **Manutenção:** abrir/fechar parada, sugestões vindas de DTC, planos preventivos e vencimentos.
- **Abastecimentos:** lançamento/importação (CSV) de transações e lista de divergências.
- **Relatórios:** catálogo de relatórios padrão (frota, ociosidade, consumo, condução, manutenção, emissões), filtros salvos e **agendamento** (diário/semanal/mensal, PDF ou Excel, destinatários).
- **Configurações:** Seção 6.
- **Revendedor:** lista dos seus clientes com o resumo de cada um e a marca.

Requisitos gerais: responsivo (funciona no celular), contraste AA, estados de carregamento, vazio e erro em todos os blocos.

---

# 8. FASES E CRITÉRIOS DE ACEITE
Cada fase termina com testes passando, lint limpo, commit e um resumo do que ficou pendente.

**Fase 1 – Fundação e banco**
Estrutura de pastas (`backend/`, `frontend/`, `docker/`), docker-compose, Alembic, schema completo (resellers com branding, tenants, users, asset_groups, assets, drivers, driver_assignments, asset_models com limiares, param_mapping, telemetry_raw hypertable, asset_live_state, geofences, trips, dtc_dictionary, dtc_alerts, maintenance_events, maintenance_plans, fuel_prices, fuel_transactions, platform_credentials, config_settings, config_versions, scoring_rules, scoring_cycles, driver_occurrences, occurrence_contests, report_schedules, audit_log, ingest_tokens (hash), rejected_packets; `users.driver_id` nullable), RLS e continuous aggregates.
Aceite: `make up` sobe tudo; migrations aplicam do zero; teste de isolamento entre tenants e entre revendedores passa.

**Fase 2 – Ingestão e normalização**
`CanonicalTelemetryPacket`, saneamento CAN (1.4), deduplicação (1.6), poller Wialon, endpoint de stream, stub RedGPS, worker de escrita em lote, `asset_live_state` e identificação do motorista (1.1.2: RFID no pacote e sincronização das atribuições da Wialon).
Aceite: testes com sentinelas, salto impossível, pacote duplicado, histórico fora de ordem, lote com item inválido (os válidos entram, o inválido vai para rejeitados), troca de motorista por RFID no meio do dia e conflito entre RFID e vínculo fixo.

**Fase 3 – Motor de KPIs e API**
KPIs da Seção 5 com qualidade do dado, alertas DTC, resolução de configuração com herança (Seção 6), endpoints `GET /api/v1/dashboard/summary`, `GET /api/v1/dashboard/assets`, `GET /api/v1/assets/{id}/telemetry` (série reduzida a no máximo 500 pontos) e `seed.py` com dois revendedores, três clientes, frota mista de caminhões e máquinas, motoristas com RFID e vínculo fixo, paradas de manutenção lançadas, ociosidade com e sem PTO, lacunas de sinal, alertas DTC e dado atrasado.
Aceite: testes de cada KPI com valores esperados calculados à mão, inclusive virada de dia no fuso do tenant, mudança de preço do diesel no meio do período e dado atrasado reprocessando o agregado.

**Fase 3.5 – Operação e Programa de Boa Condução**
Viagens (1.8), manutenção preventiva (1.9), divergência de abastecimento, motor de ocorrências e pontuação (5.1), contestações, fechamento de ciclo, relatórios padrão em PDF/Excel e agendamento por e-mail.
Aceite: testes com ocorrência em dado `unreliable` (peso 0), ocorrência sem motorista (fora do ranking), contestação aceita devolvendo pontos, mudança de peso no meio do ciclo (passado mantém o peso antigo), dado atrasado depois do fechamento (ajuste no ciclo seguinte), comparação por 100 km/10 h, plano preventivo vencendo por horímetro e por data, e um relatório agendado gerado e enviado para um SMTP de teste.

**Fase 4 – Front-end**
Telas da Seção 7 consumindo a API real: dashboard com abas e mapa, alternância de categoria, gráficos e drawer; Programa de Boa Condução (ranking, extrato, contestações, visão do motorista); manutenção; abastecimentos; relatórios; configurações com herança visível; tema do revendedor aplicado pelo domínio; painel do revendedor.
Aceite: `npm run build` e `tsc` sem erro; tudo funcional com o seed (dois revendedores, três clientes, frota mista); abrir e fechar uma parada muda a disponibilidade; alterar um peso na configuração muda o extrato só a partir da data da mudança; layout utilizável em 390 px de largura.

**Fase 5 – Assistente e emissões (depois da v1)**
- Servidor MCP somente leitura sobre a API de KPIs, respeitando tenant e papel do usuário (ex.: "qual máquina ficou mais ociosa na obra X este mês?").
- Relatório de emissões diretas (escopo 1) por período e grupo.
- Modo privacidade (ocultar posição fora do expediente configurado), rotas planejadas × realizadas.
Aceite: o MCP não devolve dado de outro tenant (mesmo teste de isolamento da Fase 1); relatório de emissões bate com os litros do período.

Comece pela Fase 1: mostre o plano, a árvore de diretórios e o schema, e espere meu OK.
