"""Spike Worker: fetch / scheduled / queue handlers on the Free plan.

Disposable. Exists only to measure CPU time, validate tooling and prove idempotent writes.
"""

from __future__ import annotations

import asyncio
import json
import time

import js
from pyodide.ffi import to_js
from workers import Response, WorkerEntrypoint, fetch

from checks import INSERT_SQL, Monitor, build_message, due_slot, make_result, result_row

TARGETS: list[Monitor] = [
    {"id": 1, "url": "https://example.com/"},
    {"id": 2, "url": "https://www.cloudflare.com/"},
    {"id": 3, "url": "https://github.com/"},
    {"id": 4, "url": "https://httpbin.org/status/200"},
    {"id": 5, "url": "https://httpstat.us/500"},
]
TIMEOUT_MS = 5000
CONCURRENCY = 6


def _now_s() -> int:
    return int(time.time())


async def _check_one(sem: asyncio.Semaphore, m: Monitor, slot: int):
    async with sem:
        t0 = time.perf_counter()
        try:
            resp = await fetch(
                m["url"],
                method="GET",
                redirect="follow",
                signal=js.AbortSignal.timeout(TIMEOUT_MS),
                headers={"User-Agent": "uptime-spike/0.0"},
            )
            latency = int((time.perf_counter() - t0) * 1000)
            return make_result(m["id"], slot, _now_s(), status_code=resp.status, latency_ms=latency)
        except Exception as e:  # noqa: BLE001 - spike: any failure is a failed check
            latency = int((time.perf_counter() - t0) * 1000)
            return make_result(m["id"], slot, _now_s(), latency_ms=latency, error=str(e)[:200])


async def _run_batch(env, slot: int, monitors: list[Monitor]) -> dict:
    sem = asyncio.Semaphore(CONCURRENCY)
    results = await asyncio.gather(*(_check_one(sem, m, slot) for m in monitors))

    cpu_t0 = time.perf_counter()
    # `_binding` unwraps the SDK proxy: D1.batch() needs raw JS D1PreparedStatement objects.
    stmts = [env.DB.prepare(INSERT_SQL).bind(*result_row(r))._binding for r in results]
    build_ms = (time.perf_counter() - cpu_t0) * 1000
    io_t0 = time.perf_counter()
    outcome = await env.DB.batch(to_js(stmts))
    inserted = sum(int(o.meta.changes) for o in outcome)
    batch_ms = (time.perf_counter() - io_t0) * 1000

    summary = {
        "due_slot": slot,
        "monitors": len(monitors),
        "inserted": inserted,
        "ignored": len(monitors) - inserted,
        "build_stmts_ms": round(build_ms, 3),
        "d1_batch_ms": round(batch_ms, 3),
        "results": [
            {
                "id": r["monitor_id"],
                "ok": r["ok"],
                "status": r["status_code"],
                "ms": r["latency_ms"],
            }
            for r in results
        ],
    }
    print("batch", json.dumps(summary))
    return summary


def _rows(res) -> list:
    rows = res.results
    return rows.to_py() if hasattr(rows, "to_py") else rows


class Default(WorkerEntrypoint):
    async def scheduled(self, controller, env, ctx):
        now_s = int(controller.scheduledTime / 1000)
        body = build_message(now_s, TARGETS)
        await self.env.CHECKS.send(body)
        print("scheduled", json.dumps({"due_slot": body["due_slot"], "monitors": len(TARGETS)}))

    async def queue(self, batch, env, ctx):
        for msg in batch.messages:
            body = msg.body
            if hasattr(body, "to_py"):
                body = body.to_py()
            await _run_batch(self.env, int(body["due_slot"]), list(body["monitors"]))
            msg.ack()

    async def fetch(self, request):
        url = js.URL.new(request.url)
        path = url.pathname

        if path == "/ping":
            # Baseline: no bindings, no I/O. Measures pure Python runtime overhead per invocation.
            return Response("ok")

        if path == "/replay":
            # Re-publish a message for a given slot: proves INSERT OR IGNORE on redelivery.
            slot = url.searchParams.get("slot")
            slot_i = int(slot) if slot else due_slot(_now_s())
            await self.env.CHECKS.send({"due_slot": slot_i, "monitors": TARGETS})
            return Response.json({"replayed_slot": slot_i})

        if path == "/run":
            # Run a batch inline (no queue) for local debugging.
            slot = url.searchParams.get("slot")
            slot_i = int(slot) if slot else due_slot(_now_s())
            return Response.json(await _run_batch(self.env, slot_i, TARGETS))

        totals = await self.env.DB.prepare(
            "SELECT COUNT(*) AS rows_total, COUNT(DISTINCT due_slot) AS slots, "
            "COUNT(DISTINCT monitor_id) AS monitors FROM checks"
        ).first()
        recent = await self.env.DB.prepare(
            "SELECT monitor_id, due_slot, ok, status_code, latency_ms, error, checked_at "
            "FROM checks ORDER BY due_slot DESC, monitor_id LIMIT 15"
        ).all()
        dupes = await self.env.DB.prepare(
            "SELECT monitor_id, due_slot, COUNT(*) AS n FROM checks "
            "GROUP BY monitor_id, due_slot HAVING n > 1"
        ).all()
        return Response.json(
            {
                "totals": totals.to_py() if hasattr(totals, "to_py") else totals,
                "duplicates": _rows(dupes),
                "recent": _rows(recent),
            }
        )
