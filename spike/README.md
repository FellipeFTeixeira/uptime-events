# Spike — Fase 0

Código descartável. Prova que Python Workers no plano Free sustentam o projeto. Resultado e veredito ficam em `docs/spike.md`; esta pasta é removida na Fase 1.

Comandos (rodar dentro de `spike/`):

```sh
uv sync                                   # instala workers-py, pytest, ruff
uv run pytest                             # testes puros (sem runtime)
uv run ruff check . && uv run ruff format --check .
npx wrangler d1 migrations apply uptime-spike --local
uv run pywrangler dev                     # dev local (cron, fila e D1 simulados)
curl "http://localhost:8787/cdn-cgi/local/scheduled"   # dispara o cron
curl "http://localhost:8787/"             # totais + últimas linhas + duplicatas
curl "http://localhost:8787/replay?slot=<due_slot>"    # reentrega mesma mensagem
```
