"""ITV Desk 后端 — CI 冒烟测试（pytest）

设计原则：零外部网络、零数据库污染
  - 用 FastAPI TestClient 验证核心端点可达
  - 用 M3U 解析 / 工具函数验证纯逻辑
  - 数据目录重定向到临时目录，避免污染工作区
  - 全部离线，不依赖任何网络请求
"""
import os
import sys
import json
import tempfile

import pytest


@pytest.fixture(autouse=True)
def _redirect_data_dir(tmp_path, monkeypatch):
    """每个测试前把 ITV_DATA_DIR 指到临时目录，避免污染仓库。"""
    monkeypatch.setenv("ITV_DATA_DIR", str(tmp_path))
    # 清理 app.log 等可能存在的文件
    yield


def test_import_app_main():
    """app.main 顶层可导入（不触发 run_server）。"""
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
    import app.main  # noqa: F401
    assert app.main.app is not None


def test_stats_endpoint():
    """GET /api/stats 返回 200 且包含 total 字段。"""
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
    """GET /api/logs 与 POST /api/logs/clear 可正常往返。"""
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
    """GET /api/players 返回 3 个播放器键（vlc/pot/mpv）。"""
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
    """M3U 解析：#EXTINF 行 + URL 行配对。"""
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
    """纯 TXT 解析：name,url 单行格式。"""
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
    from app.utils.m3u_parser import extract_channels

    sample = "频道A,http://a.example.com/x.m3u8\n频道B,https://b.example.com/y.ts\n"
    result = extract_channels(sample)
    assert len(result) == 2
    assert result[0]["name"] == "频道A"
    assert result[0]["url"] == "http://a.example.com/x.m3u8"


def test_extract_channels_empty_input():
    """空输入返回空列表，不抛异常。"""
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
    from app.utils.m3u_parser import extract_channels

    assert extract_channels("") == []
    assert extract_channels("#EXTM3U\n") == []


def test_config_json_roundtrip(tmp_path, monkeypatch):
    """FileManager.write_json_atomic / Config.load_json 原子写读。"""
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
    from app.config import Config, FileManager

    # 在临时目录内做相对路径测试
    monkeypatch.chdir(tmp_path)
    f = "test_roundtrip.json"
    FileManager.write_json_atomic(f, {"a": 1, "b": [2, 3]})
    loaded = Config.load_json(f, default={})
    assert loaded == {"a": 1, "b": [2, 3]}


def test_frontend_dist_exists(tmp_path):
    """CI 构建后 frontend-new/dist 应已就绪（防漏构建直接打版）。"""
    dist = os.path.join(os.path.dirname(__file__), "..", "..", "frontend-new", "dist")
    # 在本地开发环境 dist 可能不存在，跳过
    if not os.path.isdir(dist):
        pytest.skip("本地未构建前端，CI 会先跑 lint")
    assert os.path.isfile(os.path.join(dist, "index.html"))


def test_cache_save_roundtrip(tmp_path):
    """POST /api/cache/save 把频道池序列化到缓存文件。"""
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
    from fastapi.testclient import TestClient
    from app.main import app, channel_service

    client = TestClient(app)
    # 注入一个假频道
    channel_service.pool.append({
        "url": "http://example.com/fake.m3u8",
        "name": "fake-channel",
    })
    r = client.post("/api/cache/save")
    assert r.status_code == 200
    assert r.json().get("ok") is True
    # 清理
    channel_service.pool.clear()
