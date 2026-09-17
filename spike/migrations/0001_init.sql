-- Spike table: mirrors the planned `checks` shape (vision.md section 7) minus user_id.
CREATE TABLE IF NOT EXISTS checks (
    id          INTEGER PRIMARY KEY,
    monitor_id  INTEGER NOT NULL,
    due_slot    INTEGER NOT NULL,
    ok          INTEGER NOT NULL CHECK (ok IN (0, 1)),
    status_code INTEGER,
    latency_ms  INTEGER,
    error       TEXT,
    checked_at  INTEGER NOT NULL,
    UNIQUE (monitor_id, due_slot)
);
