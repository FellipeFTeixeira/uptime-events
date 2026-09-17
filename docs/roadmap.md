# Roadmap — uptime-events

Cada fase tem um critério de saída verificável. Não se inicia uma fase sem fechar a anterior. Marcar o status aqui ao concluir.

## Fase 0 — Spike de viabilidade  `[ ]`

Objetivo: provar que Python Workers + plano gratuito sustentam o projeto. É descartável; o código do spike não vai para o produto.

- Worker Python mínimo com handlers `fetch`, `scheduled` e `queue`
- Cron de 1 min publica uma mensagem; consumer faz 5 `fetch` externos e grava no D1
- Deploy no plano gratuito e observação por algumas horas
- Medir CPU time por invocação (dashboard / `wrangler tail`)
- Validar e fechar o ferramental Python listado como "a definir" na seção 4 do vision.md
- Reconfirmar na documentação oficial todos os limites da seção 5 do vision.md, em especial D1

**Saída:** documento `docs/spike.md` com números medidos e veredito; seção 4 do vision.md e seção "Comandos" do CLAUDE.md atualizadas com o ferramental validado. Se o CPU time estourar 10 ms de forma consistente, parar e rediscutir (reduzir trabalho por invocação, trocar linguagem ou rever a restrição de plano).

## Fase 1 — Fundação  `[ ]`

- Estrutura do repositório, configuração do wrangler, ambientes `dev` e `production`
- Schema D1 completo via migrations versionadas
- Setup de testes e lint
- CI no GitHub Actions (lint + testes)
- README inicial

**Saída:** `dev` local sobe, migrations aplicam do zero, CI verde.

## Fase 2 — Núcleo de checagem  `[ ]`

- Scheduler: seleciona monitores vencidos, agrupa em lotes, publica, avança `next_check_at`
- Checker: executa checks com concorrência limitada e timeout, grava com `INSERT OR IGNORE`
- Monitores inseridos via seed/SQL (ainda sem API)

**Saída:** com 3 monitores semeados, a tabela `checks` recebe exatamente uma linha por monitor por slot, inclusive quando a mesma mensagem é reentregue (teste automatizado de duplicidade).

## Fase 3 — Incidentes e notificações  `[ ]`

- Máquina de estados (`unknown`/`up`/`down`) com N falhas consecutivas
- Abertura e fechamento de incidentes
- Fila `notifications` + Notifier com retry
- Cooldown anti-flapping

**Saída:** testes cobrindo todas as transições e casos de borda (falha única, flapping, reentrega de mensagem, monitor pausado). Um endpoint de teste derrubado de propósito gera exatamente um alerta de queda e um de recuperação.

## Fase 4 — API de gestão  `[ ]`

- CRUD de monitores e canais de notificação
- Auth por token
- Validação de entrada (URL, intervalo mínimo, limites de quantidade compatíveis com o orçamento do plano)
- Pausar/retomar monitor

**Saída:** todo o ciclo de vida de um monitor operável por `curl`, documentado no README.

## Fase 5 — Status page  `[ ]`

- Página pública com estado atual, uptime 24h/7d/30d, latência e incidentes recentes
- Cache com invalidação em mudança de estado

**Saída:** página carrega sem consultar o D1 na maioria das visitas (verificado por log).

## Fase 6 — Retenção e rollup  `[ ]`

- Job horário: consolida checks brutos em rollup horário
- Job diário: consolida em rollup diário e apaga dados vencidos
- Uptime de 7d+ passa a ler dos rollups

**Saída:** jobs idempotentes (rodar duas vezes produz o mesmo resultado); números de uptime batem entre dados brutos e rollup no período em que ambos existem.

## Fase 7 — Endurecimento e publicação  `[ ]`

- Rodar 30 dias e comparar consumo real com o orçamento do vision.md
- Documentação de arquitetura e de deploy
- Revisão de segurança (SSRF: bloquear alvos internos/privados; limites de tamanho de resposta)

**Saída:** critérios de sucesso do vision.md atendidos.

## Pós-MVP (sem ordem definida)

- Multi-usuário: contas, login, isolamento por `user_id`, limites por usuário
- Painel web de administração
- Checks de keyword, expiração de SSL, TCP
- Janelas de manutenção
- Multi-região via Durable Objects com location hints
- Email como canal de alerta
