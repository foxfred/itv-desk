import os
import sys
import json
import tempfile

import pytest


@pytest.fixture(autouse=True)
def _redirect_data_dir(tmp_path, monkeypatch):
    monkeypatch.setenv("ITV_DATA_DIR", str(tmp_path))
    yield


def test_import_app_main():
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
    import app.main  # noqa: F401
    assert app.main.app is not None


def test_stats_endpoint():
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
    from fastapi.testclient import TestClient
    from app.main import app

    client = TestClient(app)
    r = client.get("/api/stats")
    assert r.status_code == 200
    body = r.json()
    assert "total" in body
    assert "online" in body
    assert "offline" in body


def test_logs_endpoint_roundtrip():
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
    from fastapi.testclient import TestClient
    from app.main import app

    client = TestClient(app)
    r = client.get("/api/logs")
    assert r.status_code == 200
    assert "logs" in r.json()

    r2 = client.post("/api/logs/clear")
    assert r2.status_code == 200
    assert r2.json().get("ok") is True


def test_players_endpoint_schema():
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
    from fastapi.testclient import TestClient
    from app.main import app

    client = TestClient(app)
    r = client.get("/api/players")
    assert r.status_code == 200
    body = r.json()
    for k in ("vlc", "pot", "mpv"):
        assert k in body


def test_extract_channels_m3u():
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
    from app.utils.m3u_parser import extract_channels

    sample = (
        "#EXTM3U\n"
        '#EXTINF:-1 group-title="央视频道" tvg-logo="http://x/logo1.png", CCTV-1\n'
        "http://example.com/cctv1.m3u8\n"
        "#EXTINF:-1, 测试频道\n"
        "https://example.com/test.ts\n"
    )
    result = extract_channels(sample)
    assert isinstance(result, list)
    assert len(result) >= 2
    assert result[0]["name"] == "CCTV-1"
    assert result[0]["url"] == "http://example.com/cctv1.m3u8"
    assert result[0]["group"] == "央视频道"


def test_extract_channels_plain_txt():
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
    from app.utils.m3u_parser import extract_channels

    sample = "频道A,http://a.example.com/x.m3u8\n频道B,https://b.example.com/y.ts\n"
    result = extract_channels(sample)
    assert len(result) == 2
    assert result[0]["name"] == "频道A"
    assert result[0]["url"] == "http://a.example.com/x.m3u8"


def test_extract_channels_empty_input():
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
    from app.utils.m3u_parser import extract_channels

    assert extract_channels("") == []
    assert extract_channels("#EXTM3U\n") == []


def test_config_json_roundtrip(tmp_path, monkeypatch):
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
    from app.config import Config, FileManager

    monkeypatch.chdir(tmp_path)
    f = "test_roundtrip.json"
    FileManager.write_json_atomic(f, {"a": 1, "b": [2, 3]})
    loaded = Config.load_json(f, default={})
    assert loaded == {"a": 1, "b": [2, 3]}


def test_frontend_dist_exists(tmp_path):
    dist = os.path.join(os.path.dirname(__file__), "..", "..", "frontend-new", "dist")
    if not os.path.isdir(dist):
        pytest.skip("本地未构建前端，CI 会先跑 lint")
    assert os.path.isfile(os.path.join(dist, "index.html"))


def test_cache_save_roundtrip(tmp_path):
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
    from fastapi.testclient import TestClient
    from app.main import app, channel_service

    client = TestClient(app)
    channel_service.pool.append({
        "url": "http://example.com/fake.m3u8",
        "name": "fake-channel",
    })
    r = client.post("/api/cache/save")
    assert r.status_code == 200
    assert r.json().get("ok") is True
    channel_service.pool.clear()
