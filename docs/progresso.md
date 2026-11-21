# Progresso por etapa

Guia das etapas: `etapas-claude-code-v2.md`. Especificação: `docs/especificacao.md`.
Status possíveis: `pendente`, `em andamento`, `concluída`, `bloqueada`.

Etapa 0 (repositório, `CLAUDE.md` e plano): concluída em 2026-11-21, aguardando respostas às dúvidas da especificação.

| Etapa | Entrega | Status | Data | Observações |
|---|---|---|---|---|
| 1 | Esqueleto, docker e CI | pendente | | |
| 2 | Banco, RLS e agregados | pendente | | |
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
| Revisão do `dtc_dictionary` inicial por especialista | etapa 7 | a fazer após o seed |
| Fonte oficial do fator de CO₂ do diesel | etapa 7 | a definir |
