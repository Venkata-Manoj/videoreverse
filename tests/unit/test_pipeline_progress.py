from __future__ import annotations

from src.pipeline import _emit_progress


def test_emit_progress_invokes_callback() -> None:
    events: list[tuple[str, dict]] = []

    def cb(event: str, data: dict) -> None:
        events.append((event, data))

    _emit_progress(cb, "step", step="ingest", status="running", message="working")
    assert len(events) == 1
    assert events[0][0] == "step"
    assert events[0][1]["step"] == "ingest"
    assert events[0][1]["status"] == "running"


def test_emit_progress_no_callback() -> None:
    _emit_progress(None, "step", step="ingest", status="done")
