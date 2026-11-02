from mail2reminders.config import DEFAULTS, load_config, merge


def test_merge_is_deep():
    merged = merge(DEFAULTS, {"mail": {"lookback_days": 7}})
    assert merged["mail"]["lookback_days"] == 7
    assert merged["mail"]["account"] == DEFAULTS["mail"]["account"]


def test_load_existing_config_does_not_rewrite(tmp_path):
    path = tmp_path / "config.json"
    original = '{"reminders": {"list": "Inbox"}}'
    path.write_text(original, encoding="utf-8")

    config = load_config(path, create=False)

    assert config["reminders"]["list"] == "Inbox"
    assert config["parsing"]["date_order"] == "DMY"
    assert path.read_text(encoding="utf-8") == original


def test_creates_default_config(tmp_path):
    path = tmp_path / "nested" / "config.json"
    config = load_config(path)
    assert path.exists()
    assert config["mail"]["account"] == DEFAULTS["mail"]["account"]
