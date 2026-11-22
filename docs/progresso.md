# Progresso por etapa

Guia das etapas: `etapas-claude-code-v2.md`. Especificação: `docs/especificacao.md`.
Status possíveis: `pendente`, `em andamento`, `concluída`, `bloqueada`.

Etapa 0 (repositório, `CLAUDE.md` e plano): concluída em 2026-11-21. Dúvidas a–j respondidas pelo dono e registradas em `docs/decisoes.md`.

| Etapa | Entrega | Status | Data | Observações |
|---|---|---|---|---|
| 1 | Esqueleto, docker e CI | concluída | 2026-11-22 | `make up` (7 serviços saudáveis), `make test` (10 testes) e `make lint` passando; CI verde no primeiro push (execução 44965879581) |
| 2 | Banco, RLS e agregados | em andamento | 2026-11-22 | 5 migrations, 79 testes (isolamento tenant × tenant e revendedor × revendedor, inclusive nas funções de telemetria), lint limpo localmente; falta o CI verde |
| 3 | Autenticação, papéis e revenda | pendente | | |
| 4 | Ingestão e normalização | pendente | | |
| 5 | Conectores e motorista | pendente | | RedGPS depende da documentação |
| 6 | Configuração com herança | pendente | | |
| 7 | Motor de KPIs e alertas DTC | pendente | | |
| 8 | API do dashboard e seed | pendente | | |
| 9 | Viagens, preventiva e abastecimentos | pendente | | |
| 10 | Programa de Boa Condução | pendente | | |
| 11 | Relatórios e agendamento | pendente | | |
| 12 | Front: base e dashboard | pendente | | |
| 13 | Front: condução, operação e configurações | pendente | | |
| 14 | Pré-produção (fora da especificação) | pendente | | |
| 15 | Assistente MCP e emissões (pós-v1) | pendente | | |

## Pendências de documentação (TODO(doc))

| Item | Bloqueia | Situação |
|---|---|---|
| Documentação oficial da RedGPS (autenticação, endpoints, formato e campos das mensagens) | etapa 5 | aguardando envio |
| Nomes de parâmetro da Wialon por modelo de rastreador (CAN, RFID, PTO, cinto, eventos bruscos, tensão) | etapas 4 e 5 | a levantar |
| Revisão do `dtc_dictionary` inicial (5 códigos J1939 genéricos, marcados `a_revisar_por_especialista`) | etapa 7 | a fazer |
| Semântica da largura da cerca de linha na Wialon (total ou de cada lado) | etapa 5 | `TODO(doc)` em `app/domain/geofence.py`; assumido total |
| Fonte oficial do fator de CO₂ do diesel (padrão 2,68 kg/L, IPCC 2006 genérico) | etapa 7 | padrão definido; revisar com a ferramenta do GHG Protocol (biodiesel) |
| Prazo padrão de retenção da telemetria bruta (LGPD) | etapa 14 | aguardando o dono |
| Nome completo do titular no `LICENSE` | — | aguardando o dono |
