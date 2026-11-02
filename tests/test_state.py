from datetime import datetime, timedelta

from mail2reminders.state import State


def test_mark_and_reload(tmp_path):
    path = tmp_path / "state.json"
    state = State(path)
    assert not state.is_done("abc")
    state.mark("abc", {"created_at": datetime.now().isoformat(timespec="seconds")})
    state.save()

    again = State(path)
    assert again.is_done("abc")
    assert again.data["last_run"] is not None


def test_prune_removes_old_entries(tmp_path):
    path = tmp_path / "state.json"
    state = State(path)
    state.mark("old", {"created_at": (datetime.now() - timedelta(days=200)).isoformat()})
    state.mark("new", {"created_at": datetime.now().isoformat(timespec="seconds")})
    state.save()

    assert "old" not in state.data["created"]
    assert "new" in state.data["created"]


def test_corrupt_file_falls_back_to_empty(tmp_path):
    path = tmp_path / "state.json"
    path.write_text("{not json", encoding="utf-8")
    state = State(path)
    assert state.data["created"] == {}
