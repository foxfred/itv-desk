import json
import os


class FileManager:
    @staticmethod
    def read_text(filepath, encoding="utf-8", fallback_encodings=None):
        if fallback_encodings is None:
            fallback_encodings = ["utf-8", "gbk", "gb2312", "utf-16"]
        for enc in [encoding] + fallback_encodings:
            try:
                with open(filepath, "r", encoding=enc, errors="ignore") as f:
                    return f.read(), None
            except UnicodeDecodeError:
                continue
            except Exception as e:
                return "", str(e)
        return "", f"无法解码文件: {filepath}"

    @staticmethod
    def write_text(filepath, content, encoding="utf-8"):
        try:
            with open(filepath, "w", encoding=encoding) as f:
                f.write(content)
            return True, None
        except Exception as e:
            return False, str(e)

    @staticmethod
    def read_json(filepath, default=None, expect=None):
        """读取 JSON 文件。

        - 文件不存在 / JSON 损坏 / 读取异常 → 返回 `default`，不抛异常
        - `expect` 传 `dict` 或 `list` 时做类型校验，类型不符同样返回 `default`

        收敛了 ai_service / stats_service / screenshot_service / subscription_service
        各自实现的「open + json.load + isinstance 校验 + except 兜底」。
        """
        try:
            with open(filepath, "r", encoding="utf-8") as f:
                data = json.load(f)
        except Exception:
            return default
        if expect is not None and not isinstance(data, expect):
            return default
        return data

    @staticmethod
    def write_json_atomic(filepath, data, indent=2, encoding="utf-8", sort_keys=False):
        """原子写 JSON：同目录建临时文件 → fsync → os.replace 覆盖。

        返回 `(ok, err)`；调用方自行决定是否记录日志。
        """
        import tempfile
        try:
            d = os.path.dirname(os.path.abspath(filepath))
            fd, tmp = tempfile.mkstemp(dir=d, suffix=".tmp")
            try:
                with os.fdopen(fd, "w", encoding=encoding) as f:
                    json.dump(data, f, ensure_ascii=False, indent=indent,
                              sort_keys=sort_keys)
                    f.flush()
                    os.fsync(f.fileno())
                os.replace(tmp, filepath)
            except Exception:
                try:
                    os.unlink(tmp)
                except Exception:
                    pass
                raise
            return True, None
        except Exception as e:
            return False, str(e)

class Config:
    HISTORY_FILE = "url_history.json"
    REMOTE_HISTORY_FILE = "remote_url_history.json"
    MIRROR_HISTORY_FILE = "mirror_history.json"
    EPG_HISTORY_FILE = "epg_history.json"
    TAG_DB_FILE = "channel_tags.json"
    FAKE_LIVE_DB_FILE = "fake_live_tags.json"
    RULES_FILE = "channel_rules.json"
    OUTPUT_M3U = "检查整理结果_已去重.m3u"

    DEFAULTS = {
        "default_epg": "https://epg.163189.xyz/pp.xml",
        "url_history_limit": 20,
        "mirror_history_limit": 20,
        "epg_history_limit": 20,
        "default_export_filename": "检查整理结果_已去重",
        "unknown_group_name": "未分组",
        "default_group_name": "自动分组",
        "json_indent": 2,
        "cache_file_name": "channels_cache.json",
        "smart_paste_default_group": "粘贴导入",
        "cache_default_group": "杂项频道",
        "cache_default_geo": "中国",
        "cache_default_stack": "IPv4",
        "auto_group": True,
        "foreign_group_name": "外国频道",
        "custom_group_rules": [],
        "group_override_by_url": [],
        "use_proxy": False,
        "user_agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        "download_timeout": 15,
        "download_retries": 2,
        "scraper_timeout": 15,
        "scraper_retries": 2,
        "scraper_threads": 8,
        "scraper_min_interval": 0.0,
        "download_chunk_size": 8192,
        "suffix_list": "m3u,m3u8,txt",
        "mirror_history": ["不使用加速", "ghp.ci", "ghproxy.com", "ghproxy.net", "kkgithub.com", "raw.fastgit.org"],
        "mirror": "不使用加速",
        "proxy": "",
        "update_url": "https://raw.githubusercontent.com/foxfred/itv-desk/master/release/update.json",
        "check_timeout": 1.5,
        "check_threads": 40,
        "check_retries": 1,
        "fake_live_whitelist": [],
        "url_blacklist": [],
        "url_whitelist": [],
        "gateway_enabled": False,
        "gateway_token": "",
        "namefix_strategy": "advise",
        "namefix_capture_width": 960,
        "namefix_capture_offset": 3,
        "namefix_reuse_screenshot": True,
        "namefix_min_confidence": 0.9,
        "namefix_fuzzy_threshold": 0.86,
        "namefix_vision_enabled": False,
        "namefix_vision_base": "https://open.bigmodel.cn/api/paas/v4/chat/completions",
        "namefix_vision_model": "glm-4v-flash",
        "namefix_vision_key": "",
        "namefix_vision_timeout": 45,
        "namefix_workers": 4,
        "scan_timeout": 5,
        "scan_max_workers": 40,
        "subscription_auto_update_interval": 0,
        "epg_auto_refresh_interval": 0,
        "theme_mode": "浅色",
        "theme": "#409EFF",
        "theme_preset": "默认蓝",
        "stats_card_position": "顶部",
        "stats_card_visible": True,
        "column_visibility": [True, True, True, True, True, True, True, True, True, True, True],
        "player_update_interval_ms": 500,
        "player_hide_controls_delay_ms": 3000,
        "player_seek_step_ms": 5000,
        "player_keyboard_volume_step": 5,
        "player_keyboard_enabled": True,
        "prefer_external_player": False,
        "external_player": "vlc",
        "external_player_path": "",
        "player_stream_proxy": False,
        "player_window_topmost": False,
        "double_click_auto_play": True,
        "default_volume": 75,
        "default_playback_speed": 1.0,
        "color_video_bg": "#000000",
        "repair_check_timeout": 5,
        "repair_max_retries": 1,
        "repair_max_workers": 10,
        "record_container": "mp4",
        "record_max_minutes": 0,
        "timeshift_minutes": 0,
        "timeshift_segment_seconds": 4,
        "catchup_enabled": True,
        "parental_enabled": False,
        "parental_pin": "",
        "parental_locked_groups": [],
        "ai_enabled": False,
        "ai_base_url": "https://api.deepseek.com/v1",
        "ai_api_key": "",
        "ai_model": "deepseek-chat",
        "ai_timeout": 60,
        "ai_temperature": 0.2,
        "ai_max_tokens": 2048,
        "ai_prompt_extra": "",
        "ai_vision_enabled": False,
        "ai_vision_base_url": "",
        "ai_vision_api_key": "",
        "ai_vision_model": "",
        "ai_vision_timeout": 45,
        "ai_daily_token_limit": 0,
        "ai_cache_enabled": True,
        "hdhr_enabled": False,
        "hdhr_device_id": "",
        "hdhr_tuner_count": 3,
        "hdhr_only_online": True,
        "hdhr_groups": [],
        "hdhr_limit": 300,
        "hdhr_transcode": False,
        "hdhr_ssdp": False,
        "hdhr_exclude_adult": True,
        "hdhr_base_url": "",
        "hdhr_port": 0,
    }

    @staticmethod
    def load_json(fname, default):
        content, err = FileManager.read_text(fname)
        if err:
            return default
        try:
            return json.loads(content)
        except Exception:
            return default

    @staticmethod
    def save_json(fname, data, max_len=20):
        try:
            if isinstance(data, list):
                data = data[:max_len]
            content = json.dumps(data, ensure_ascii=False, indent=2)
            success, _err = FileManager.write_text(fname, content)
            return success
        except Exception:
            return False

    SETTINGS_FILE = "settings.json"

    @staticmethod
    def load_settings():
        settings = Config.load_json(Config.SETTINGS_FILE, {})
        merged = dict(Config.DEFAULTS)
        merged.update(settings)
        return merged

    @staticmethod
    def save_settings(data):
        return Config.save_json(Config.SETTINGS_FILE, data)

    @staticmethod
    def get_setting(key, default=None):
        settings = Config.load_settings()
        return settings.get(key, default)

    @staticmethod
    def get_data_dir():
        from app.paths import DATA_DIR
        return DATA_DIR
