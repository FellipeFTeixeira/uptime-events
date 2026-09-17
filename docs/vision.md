# Vision — uptime-events

## 1. O que é

Monitor de uptime rodando 100% na plataforma Cloudflare. O usuário cadastra endpoints HTTP, o sistema os verifica periodicamente, registra histórico, detecta quedas e recuperações, notifica, e expõe uma status page pública.

## 2. Por que existe

- Projeto de aprendizado: exercitar arquitetura de backend (agendamento, filas, idempotência, máquina de estados, agregação de dados) usando os primitivos da Cloudflare.
- Projeto de portfólio: público no GitHub, desenvolvido com Spec-Driven Development e Claude Code.
- Utilidade real: monitorar os próprios projetos do autor.

## 3. Restrições fixas

| Restrição | Decisão |
| --- | --- |
| Linguagem | Python Workers |
| Plano | Workers Free, sem exceção. Se algo não couber, reduz-se o escopo, não se paga |
| Usuários | Single-user no MVP. Multi-usuário é etapa posterior, mas o schema já nasce preparado (`user_id` nas tabelas) |
| Infra | Nada fora da Cloudflare (sem VPS, sem banco externo) |

## 4. Stack

**Linguagem e runtime**
- Python em Python Workers. O runtime é o Pyodide (CPython compilado para WebAssembly): nem todo pacote do PyPI funciona, em especial os que dependem de extensões em C fora da lista suportada. Compatibilidade se verifica antes de adotar qualquer dependência.

**Plataforma (Cloudflare, plano gratuito)**

| Peça | Papel no projeto |
| --- | --- |
| Workers | Execução do código, com três handlers: `fetch` (HTTP), `scheduled` (cron) e `queue` (consumidor) |
| D1 | Banco relacional (SQLite). Monitores, checks, incidentes, canais e rollups |
| Queues | Duas filas: `checks` e `notifications` |
| Cron Triggers | Um único cron de 1 minuto |
| Cache API | Cache da status page |

**Ferramentas**
- Wrangler: dev local, migrations do D1, secrets e deploy
- GitHub Actions: CI (lint + testes)
- Claude Code: desenvolvimento guiado por esta spec

**Fora da stack, por decisão**
- Sem framework web (Django, FastAPI, Flask): roteamento simples e explícito, para poupar CPU e evitar incompatibilidade com o Pyodide
- Sem ORM: SQL parametrizado em uma camada de repositório
- Sem frontend em JavaScript no MVP (ver decisão 2 da seção 10)
- Sem KV, R2, Durable Objects ou Analytics Engine no MVP. Só entram se uma fase do roadmap justificar, com atualização desta seção

**A definir na Fase 0**
- Ferramental Python: gerenciador de pacotes, test runner, linter e o wrapper da Cloudflare para Python Workers. Candidatos: `uv`, `pytest`, `ruff`, `pywrangler`. Só são adotados depois de validados contra o runtime no spike.

**Atenção ao D1 (SQLite, não PostgreSQL)**
- Tipagem frouxa: o tipo declarado na coluna não é imposto. Validar na aplicação e usar `CHECK` onde fizer sentido
- Sem tipo nativo de data: timestamps como inteiro (epoch em segundos, UTC)
- JSON guardado como `TEXT`, com funções `json_*` para consulta
- Chaves estrangeiras e demais recursos devem ser confirmados no D1 antes de a modelagem depender deles

## 5. Orçamento do plano gratuito

Esses limites são restrições de design, não detalhes de deploy. Todos devem ser reconfirmados na Fase 0.

| Recurso | Limite (free) | Consequência no design |
| --- | --- | --- |
| CPU por invocação | 10 ms | **Maior risco do projeto.** `fetch` aguardando rede não conta, mas o overhead do runtime Python conta. Validar com spike antes de qualquer outra coisa |
| Subrequests por invocação | 50 | Um consumidor processa no máximo ~20 monitores por mensagem (1 fetch cada + escritas no D1 em batch) |
| Conexões de saída simultâneas | 6 | Checks dentro de um lote rodam com concorrência máxima de 6 |
| Queues | 10.000 operações/dia; cada mensagem custa ~3 (write, read, delete) | **Nunca uma mensagem por monitor.** O scheduler agrupa monitores em lotes; uma mensagem = um lote |
| Cron Triggers | 5 por conta | Um único cron de 1 minuto para tudo (checks, rollup e limpeza decidem internamente se é hora de rodar) |
| KV | 1.000 escritas/dia | Não dá para reescrever a status page a cada minuto no KV. Usar Cache API ou regravar só quando o estado muda |
| D1 | limites diários de linhas lidas/escritas (confirmar valores) | Define o teto de monitores × frequência e obriga rollup + retenção |
| Requests | 100.000/dia | Folgado; status page cacheada |

Conta de referência: cron de 1 min = 1.440 ticks/dia. Com 1 lote por tick, são ~4.320 operações de fila/dia. Logo o MVP comporta no máximo 2 lotes por tick (~40 monitores a 1 min). Intervalo padrão de 5 min, mínimo de 1 min.

## 6. Arquitetura

```
Cron (1 min)
   └─> Scheduler Worker
         ├─ lê do D1 os monitores vencidos (next_check_at <= agora)
         ├─ agrupa em lotes de até 20
         └─ publica 1 mensagem por lote na fila `checks`

Fila `checks`
   └─> Checker (consumer)
         ├─ executa os fetch (concorrência 6, timeout por monitor)
         ├─ grava resultados no D1 (idempotente)
         ├─ avalia a máquina de estados de cada monitor
         └─ se houve transição, publica na fila `notifications`

Fila `notifications`
   └─> Notifier (consumer) ─> webhook (Discord / genérico), com retry

HTTP
   ├─ /api/*      API de gestão (auth por token)
   └─ /status/*   status page pública (cacheada)
```

Scheduler, Checker, Notifier e HTTP podem ser handlers de um único Worker (`scheduled`, `queue`, `fetch`). Separar em Workers distintos só se houver motivo concreto.

## 7. Modelo de dados (D1)

- **monitors**: id, user_id, name, url, method, expected_status, timeout_ms, interval_s, state (`up` | `down` | `unknown`), consecutive_failures, next_check_at, paused, created_at
- **checks**: id, monitor_id, due_slot, ok, status_code, latency_ms, error, checked_at — `UNIQUE(monitor_id, due_slot)`
- **incidents**: id, monitor_id, started_at, resolved_at, cause
- **notification_channels**: id, user_id, kind, config (JSON), enabled
- **check_rollups**: monitor_id, bucket_start, granularity (`hour` | `day`), total, failures, avg_latency_ms, p95_latency_ms

## 8. Regras de negócio centrais

**Idempotência.** A fila entrega "pelo menos uma vez". A identidade de um check é `(monitor_id, due_slot)`, onde `due_slot` é o horário em que o check *estava previsto*, não o horário em que rodou. Escrita com `INSERT OR IGNORE`; se a linha já existia, o consumidor não reavalia estado nem notifica.

**Máquina de estados.**
- `up → down`: após N falhas consecutivas (padrão N=3). Abre incidente e notifica.
- `down → up`: após 1 sucesso. Fecha incidente e notifica.
- `unknown`: estado inicial; a primeira transição para `up` não notifica.

**Anti-flapping.** Cooldown mínimo entre notificações do mesmo monitor (padrão 10 min). Transições continuam sendo registradas, só o alerta é suprimido.

**Retenção.** Checks brutos por 7 dias. Rollup horário por 90 dias. Rollup diário indefinido. Uptime de 24h usa dados brutos; 7d/30d/90d usam rollups.

## 9. Escopo do MVP

Dentro:
- CRUD de monitores HTTP via API
- Checagem agendada com histórico
- Incidentes com detecção de queda e recuperação
- Notificação por webhook (formato Discord + genérico)
- Status page pública com estado atual, uptime 24h/7d/30d e incidentes recentes
- Rollup e limpeza de dados

Fora (pós-MVP):
- Multi-usuário, cadastro, login
- Checks de keyword, SSL, TCP, DNS
- Janelas de manutenção
- Checagem multi-região
- Email como canal de alerta
- Painel web de administração (no MVP a gestão é via API)

## 10. Decisões em aberto

1. **Auth da API**: token em secret do Worker (simples) vs Cloudflare Access (nativo, sem código). Recomendação: token no MVP.
2. **Status page**: HTML renderizado no Worker vs página estática consumindo a API JSON. Recomendação: HTML no Worker, cacheado, zero JS.
3. **Canal de notificação inicial**: Discord vs Telegram.

## 11. Critérios de sucesso

- Roda 30 dias seguidos no plano gratuito sem estourar nenhum limite.
- Nenhum alerta duplicado e nenhum falso positivo causado por falha única.
- Queda real detectada em até `interval × N` + 1 min.
- Repositório com spec, roadmap e histórico de commits que contam como o projeto foi construído.
