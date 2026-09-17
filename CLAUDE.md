# CLAUDE.md

## Projeto

uptime-events: monitor de uptime em Python Workers na Cloudflare, plano gratuito. Desenvolvido com Spec-Driven Development.

Fontes de verdade, nesta ordem:
1. `docs/vision.md` — o quê e por quê, restrições, regras de negócio
2. `docs/roadmap.md` — fases e critérios de saída
3. Este arquivo — como trabalhar no repositório

Se o código e a spec divergirem, pare e aponte a divergência. Não "corrija" a spec por conta própria.

## Fluxo de trabalho

- Trabalhe **somente na fase atual** do roadmap. Não antecipe funcionalidades de fases futuras nem de pós-MVP.
- Antes de implementar, apresente um plano curto (arquivos afetados, abordagem, testes) e aguarde aprovação.
- Uma tarefa por vez, commits pequenos. Ao concluir uma fase, atualize o status no `roadmap.md`.
- Mudança de escopo, de schema ou nova dependência exige aprovação explícita e atualização do `vision.md` no mesmo commit.
- Na dúvida entre duas interpretações da spec, pergunte.

## Stack

Resumo; a versão completa, com o que está fora da stack e os cuidados com SQLite, está na seção 4 do `vision.md`. Não introduza peça nova da Cloudflare, framework ou biblioteca que não esteja listada lá sem aprovação.

- Python Workers (runtime Pyodide) — nem todo pacote do PyPI funciona; verifique compatibilidade antes de propor dependência
- D1 (SQLite), Queues, Cron Triggers, Cache API
- Wrangler para dev, migrations e deploy
- Sem framework web pesado; roteamento simples e explícito

## Restrições inegociáveis (plano gratuito)

Todo código deve respeitar o orçamento da seção 5 do `vision.md`. Em especial:

- **10 ms de CPU por invocação.** Nada de processamento pesado, imports desnecessários no caminho quente ou serialização de estruturas grandes.
- **50 subrequests por invocação.** Escritas no D1 sempre em batch. Lotes de no máximo 20 monitores.
- **Fila: uma mensagem por lote, nunca por monitor.**
- **KV não é usado para dados que mudam a cada minuto.**
- **Um único cron.** Novos jobs periódicos entram no handler `scheduled` existente.

Se uma solução só funciona no plano pago, ela está errada para este projeto.

## Regras de implementação

- **Idempotência em todo consumer.** Identidade do check é `(monitor_id, due_slot)`; escrita com `INSERT OR IGNORE`; se a linha já existia, não reavaliar estado nem notificar.
- A máquina de estados é uma função pura (estado atual + resultado → novo estado + efeitos), testável sem I/O.
- Acesso ao D1 concentrado em uma camada de repositório; SQL parametrizado, nunca interpolado.
- Schema só muda por migration nova em `migrations/`. Nunca editar migration já aplicada.
- Todas as tabelas de domínio carregam `user_id`, mesmo no MVP single-user.
- Timestamps em UTC, inteiros (epoch em segundos).
- `fetch` para alvos de usuário sempre com timeout e limite de tamanho de resposta; bloquear IPs privados e hosts internos (SSRF).
- Segredos apenas via `wrangler secret`. Nada sensível no repositório.

## Testes

- Lógica de negócio (scheduler, máquina de estados, rollup, anti-flapping) com testes unitários sem dependência do runtime.
- Todo bug corrigido ganha um teste que o reproduz.
- Casos obrigatórios: mensagem reentregue, falha única, flapping, monitor pausado, job de rollup executado duas vezes.

## Convenções

- Código, identificadores e mensagens de commit em inglês; documentação em português.
- Conventional Commits (`feat:`, `fix:`, `docs:`, `test:`, `chore:`).
- Type hints em todas as funções públicas.

## Estrutura (alvo)

```
src/
  entry.py          # handlers fetch / scheduled / queue
  scheduler.py
  checker.py
  notifier.py
  state_machine.py
  rollup.py
  repo/             # acesso ao D1
  http/             # rotas da API e status page
migrations/
tests/
docs/
wrangler.jsonc
```

## Comandos

> A preencher ao final da Fase 0, com os comandos validados no spike (dev local, teste de cron, migrations, testes, deploy). Não presumir comandos de tutoriais de TypeScript.
