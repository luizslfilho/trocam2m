# Decisões

Uma linha por decisão. Decisões que mudam regra de negócio também exigem ajuste em `docs/especificacao.md`.

| Data | Decisão | Motivo |
|---|---|---|
| 2026-11-21 | Python 3.12 nos containers; 3.13 local aceito | Versão da especificação nos containers; desenvolvimento local já usa 3.13 |
| 2026-11-21 | Repositório definitivo: `luizslfilho/telemetria` (privado), separado de qualquer repositório ou equipamento de trabalho | Projeto pessoal isolado; os documentos da etapa 0 foram redigidos numa sessão anterior e transferidos para cá |
| 2026-11-21 | Especificação movida da raiz para `docs/especificacao.md` | Caminho usado no guia de etapas e no `CLAUDE.md` |
| 2026-11-21 | Licença proprietária ("todos os direitos reservados"), titular a preencher | Produto comercial em repositório privado; confirmar com o dono |
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
