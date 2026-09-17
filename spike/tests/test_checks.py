from checks import INSERT_SQL, build_message, due_slot, make_result, result_row


def test_due_slot_floors_to_minute():
    assert due_slot(1_700_000_059) == 1_700_000_040
    assert due_slot(1_700_000_040) == 1_700_000_040


def test_build_message_is_one_message_per_batch():
    monitors = [{"id": 1, "url": "https://a"}, {"id": 2, "url": "https://b"}]
    msg = build_message(1_700_000_059, monitors)
    assert msg["due_slot"] == 1_700_000_040
    assert len(msg["monitors"]) == 2


def test_make_result_ok_requires_expected_status_and_no_error():
    assert make_result(1, 60, 61, status_code=200, latency_ms=10)["ok"] is True
    assert make_result(1, 60, 61, status_code=500, latency_ms=10)["ok"] is False
    assert make_result(1, 60, 61, error="timeout")["ok"] is False


def test_result_row_matches_insert_placeholders():
    r = make_result(7, 120, 125, status_code=200, latency_ms=42)
    row = result_row(r)
    assert len(row) == INSERT_SQL.count("?")
    assert row[:3] == (7, 120, 1)
