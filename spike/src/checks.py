"""Pure helpers for the spike. No runtime imports so pytest runs them on plain CPython."""

from __future__ import annotations

from typing import TypedDict

SLOT_SECONDS = 60


class Monitor(TypedDict):
    id: int
    url: str


class CheckResult(TypedDict):
    monitor_id: int
    due_slot: int
    ok: bool
    status_code: int | None
    latency_ms: int | None
    error: str | None
    checked_at: int


def due_slot(now_s: int, slot_seconds: int = SLOT_SECONDS) -> int:
    """Floor a timestamp (epoch seconds) to the start of its scheduling slot."""
    return now_s - (now_s % slot_seconds)


def build_message(now_s: int, monitors: list[Monitor]) -> dict:
    """Body published on the `checks` queue: one message per batch, never per monitor."""
    return {"due_slot": due_slot(now_s), "monitors": monitors}


def make_result(
    monitor_id: int,
    slot: int,
    checked_at: int,
    *,
    status_code: int | None = None,
    latency_ms: int | None = None,
    error: str | None = None,
    expected_status: int = 200,
) -> CheckResult:
    ok = error is None and status_code == expected_status
    return CheckResult(
        monitor_id=monitor_id,
        due_slot=slot,
        ok=ok,
        status_code=status_code,
        latency_ms=latency_ms,
        error=error,
        checked_at=checked_at,
    )


def result_row(r: CheckResult) -> tuple:
    """Bind order for INSERT_SQL."""
    return (
        r["monitor_id"],
        r["due_slot"],
        1 if r["ok"] else 0,
        r["status_code"],
        r["latency_ms"],
        r["error"],
        r["checked_at"],
    )


INSERT_SQL = (
    "INSERT OR IGNORE INTO checks "
    "(monitor_id, due_slot, ok, status_code, latency_ms, error, checked_at) "
    "VALUES (?1, ?2, ?3, ?4, ?5, ?6, ?7)"
)
