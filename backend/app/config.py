import json
import os
import sys

# ==================== 文件管理器 ====================
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
    def write_lines(filepath, lines, encoding="utf-8"):
        try:
            with open(filepath, "w", encoding=encoding) as f:
                for line in lines:
                    f.write(line + "\n")
            return True, None
        except Exception as e:
            return False, str(e)

    @staticmethod
    def write_json_atomic(filepath, data, indent=2, encoding="utf-8"):
        """原子写 JSON：先写同目录 .tmp 临时文件，再 os.replace 改名覆盖目标。

        避免并发写入或进程崩溃时把 channels_cache.json 写半截（截断损坏）
        导致下次启动整池频道丢失。os.replace 在同卷上是原子操作。
        """
        import tempfile
        try:
            d = os.path.dirname(os.path.abspath(filepath))
            fd, tmp = tempfile.mkstemp(dir=d, suffix=".tmp")
            try:
                with os.fdopen(fd, "w", encoding=encoding) as f:
                    json.dump(data, f, ensure_ascii=False, indent=indent)
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

    @staticmethod
    def ensure_dir(dirpath):
        if not os.path.exists(dirpath):
            os.makedirs(dirpath)
        return os.path.exists(dirpath)


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
        # 常规
        "auto_load_epg": True,
        "default_epg": "https://epg.163189.xyz/pp.xml",
        "save_window_geometry": True,
        "load_cache_on_startup": True,
        "save_cache_on_exit": True,
        "auto_correct_after_epg": False,
        "url_history_limit": 20,
        "mirror_history_limit": 20,
        "epg_history_limit": 20,
        "cache_directory": "scraping_cache",
        "default_export_filename": "检查整理结果_已去重",
        "unknown_group_name": "未分组",
        "default_group_name": "自动分组",
        "json_indent": 2,
        "default_volume": 75,
        "default_playback_speed": 1.0,
        "default_speed": "1.0x",
        "auto_check_after_import": False,
        "auto_export_after_check": False,
        "startup_delay_ms": 500,
        "cache_file_name": "channels_cache.json",
        "column_widths_file": "column_widths.json",
        "smart_paste_default_group": "粘贴导入",
        "cache_default_group": "杂项频道",
        "cache_default_geo": "中国",
        "cache_default_stack": "IPv4",
        # 分组重构（#60）：导入/校正时按统一算法自动分组
        "auto_group": True,            # 导入时按算法自动重分组（关则保留原 group-title）
        "foreign_group_name": "外国频道",  # 外国频道统一归入的组名
        "custom_group_rules": [],      # 自定义分组规则：[{"keyword": "关键词", "group": "目标组"}]，最高优先级
        "group_override_by_url": [],   # 按 URL 精确覆盖分组：[{"url": "子串或正则", "group": "目标组"}]
        # 网络
        "default_proxy": "127.0.0.1:10808",
        "user_agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        "download_timeout": 15,
        "download_retries": 2,
        "scraper_timeout": 15,
        "scraper_retries": 2,
        "scraper_threads": 8,
        "scraper_min_interval": 0.0,
        "download_chunk_size": 8192,
        "suffix_list": "m3u,m3u8,txt",
        "default_suffix_list": "m3u,m3u8,txt",
        "max_connections": 100,
        "mirror_history": ["不使用加速", "ghp.ci", "ghproxy.com", "ghproxy.net", "kkgithub.com", "raw.fastgit.org"],
        "mirror": "不使用加速",
        "proxy": "",
        # 应用自更新（内置 GitHub raw 更新清单地址，开箱即用，用户可在设置页修改）
        "update_url": "https://raw.githubusercontent.com/foxfred/itv-desk/master/release/update.json",
        # 检查
        "check_timeout": 1.5,
        "check_threads": 40,
        "check_retries": 1,
        "reset_filter_after_check": True,
        "auto_delete_invalid_after_check": False,
        "show_quality_column": True,
        "progress_update_freq": 50,
        "batch_update_size": 30,
        "latency_grade_a_threshold": 300,
        "latency_grade_b_threshold": 800,
        "checker_batch_size": 10,
        # 播放器假直播白名单：URL 命中其中子串或正则时不再提示假直播
        "fake_live_whitelist": [],
        # 网段扫描（复用 http_probe_channel，设置项可配置）
        "scan_timeout": 5,
        "scan_max_workers": 40,
        # 定时任务（秒，0=关闭）
        "subscription_auto_update_interval": 0,
        "epg_auto_refresh_interval": 0,
        # 全局设置（主题、窗口、全局配色）
        "theme_mode": "浅色",
        "theme": "浅色",
        "theme_preset": "默认蓝",
        "font_size": 13,
        "window_default_width": 1400,
        "window_default_height": 820,
        "window_geometry": "",
        "color_log_bg": "#111111",
        "color_log_fg": "#33FF33",
        "color_video_bg": "#000000",
        # 左侧面板（抓取配置区布局）
        "left_panel_ratio": 0.28,
        "left_panel_min_width": 380,
        "left_panel_max_width": 620,
        "left_config_ratio": 0.60,
        "left_config_min_height": 280,
        "config_row_spacing": 8,
        "config_button_padding_left": 6,
        "config_button_padding_right": 6,
        "config_label_color": "#000000",
        "config_label_min_width": 68,
        "config_label_alignment": "左对齐",
        "config_input_border_width": 1,
        "config_input_border_color": "#CCCCCC",
        "config_input_border_radius": 4,
        "config_input_padding": 4,
        "config_input_height": 24,
        "config_button_border_width": 1,
        "config_button_border_color": "#2B7DE9",
        "config_button_border_radius": 4,
        "config_button_height": 26,
        "config_group_border_width": 1,
        "config_group_border_color": "rgba(0,0,0,0.15)",
        "config_group_title_color": "#000000",
        # 左侧面板 - 抓取配置区颜色与背景
        "config_input_bg_color": "#FFFFFF",
        "config_input_text_color": "#000000",
        "config_input_placeholder_color": "#AAAAAA",
        "config_button_bg_color": "#F0F0F0",
        "config_button_text_color": "#000000",
        "config_group_bg_color": "transparent",
        "config_group_border_radius": 0,
        "config_vertical_layout": False,
        "config_group_spacing": 12,
        "config_label_padding": 4,
        # 左侧面板 - 抓取配置区扩展布局
        "config_outer_margin_left": 5,
        "config_outer_margin_top": 5,
        "config_outer_margin_right": 5,
        "config_outer_margin_bottom": 5,
        "config_group_margin_left": 10,
        "config_group_margin_top": 16,
        "config_group_margin_right": 10,
        "config_group_margin_bottom": 10,
        "config_group_title_left": 10,
        "config_grid_horizontal_spacing": 8,
        "config_grid_vertical_spacing": 8,
        "config_label_font_size": 12,
        "config_label_bold": False,
        "config_input_font_size": 12,
        "config_input_dropdown_width": 24,
        "config_button_font_size": 12,
        "config_button_bold": False,
        "config_button_margin_top": 0,
        "config_button_margin_bottom": 0,
        "config_url_combo_min_width": 180,
        "config_url_combo_max_width": 360,
        "config_mirror_combo_min_width": 120,
        "config_mirror_combo_max_width": 220,
        "config_epg_combo_min_width": 80,
        "config_epg_combo_max_width": 320,
        "config_input_max_width": 320,
        "config_clear_url_button_width": 24,
        "config_single_url_button_min_width": 60,
        "config_url_pool_button_min_width": 60,
        "config_load_epg_button_width": 60,
        "config_run_button_min_height": 34,
        # 右侧面板（统计卡片、表格、工具栏、筛选栏）
        "stats_card_height": 72,
        "stats_card_min_height": 40,
        "stats_card_max_height": 200,
        "stats_card_bg": "#2B7DE9",
        "stats_card_border_color": "#2B7DE9",
        "stats_card_border_radius": 8,
        "stats_card_value_font_size": 22,
        "stats_card_label_font_size": 12,
        "stats_card_value_color_total": "#FFFFFF",
        "stats_card_value_color_online": "#4ADE80",
        "stats_card_value_color_offline": "#FB7185",
        "stats_card_label_color": "#FFFFFF",
        "stats_card_position": "顶部",
        "stats_card_visible": True,
        "stats_card_border_width": 0,
        "stats_card_padding": 12,
        "stats_card_margin": 4,
        "stats_card_align": "均分",
        "stats_card_width": 0,
        "stats_row_padding_top": 8,
        "stats_row_padding_bottom": 4,
        # 右侧面板 - 统计卡片独立样式（三个卡可分别调整）
        "stats_card_total_border_width": 0,
        "stats_card_online_border_width": 0,
        "stats_card_offline_border_width": 0,
        "stats_card_total_border_radius": 8,
        "stats_card_online_border_radius": 8,
        "stats_card_offline_border_radius": 8,
        "stats_card_total_bg": "#2B7DE9",
        "stats_card_online_bg": "#2B7DE9",
        "stats_card_offline_bg": "#2B7DE9",
        "stats_card_line_spacing": 2,
        "toolbar_bg_color": "transparent",
        "filter_bg_color": "transparent",
        "search_box_bg_color": "#FFFFFF",
        "search_box_text_color": "#000000",
        "toolbar_height": 28,
        "toolbar_button_border_width": 1,
        "toolbar_button_border_color": "rgba(0,0,0,0.1)",
        "toolbar_button_border_radius": 4,
        "toolbar_button_padding": 6,
        "toolbar_button_height": 22,
        "toolbar_button_min_width": 60,
        "toolbar_button_spacing": 6,
        "toolbar_button_font_size": 12,
        "toolbar_button_inner_spacing": -1,
        "filter_input_border_width": 1,
        "filter_input_border_color": "#CCCCCC",
        "filter_input_border_radius": 4,
        "filter_input_padding": 4,
        "filter_input_height": 22,
        "search_box_width": 140,
        "filter_height": 26,
        "right_panel_top_spacing": 0,
        "stats_toolbar_spacing": 6,
        "toolbar_filter_spacing": 4,
        "filter_table_spacing": 6,
        # 右侧面板 - 统计卡片/工具栏/筛选栏/表格扩展
        "stats_card_spacing": 0,
        "stats_card_value_font_bold": True,
        "stats_card_label_font_bold": False,
        "stats_card_total_min_width": 80,
        "stats_card_online_min_width": 80,
        "stats_card_offline_min_width": 80,
        "toolbar_button_check_all_min_width": 60,
        "toolbar_button_check_sel_min_width": 60,
        "toolbar_button_stop_check_min_width": 60,
        "toolbar_button_clear_invalid_min_width": 60,
        "toolbar_button_clear_list_min_width": 60,
        "toolbar_button_open_player_min_width": 60,
        "toolbar_button_export_selected_min_width": 60,
        "toolbar_button_export_all_min_width": 60,
        "toolbar_label_color": "#333333",
        "toolbar_label_font_size": 11,
        "search_box_position": "左侧",
        "filter_radio_spacing": 8,
        "filter_label_color": "#333333",
        "filter_label_font_size": 11,
        "progress_bar_height": 18,
        "progress_frame_height": 28,
        "table_header_font_size": 12,
        "table_header_height": 28,
        "table_cell_padding": 4,
        "row_height": 28,
        "color_table_bg": "#F7F9FA",
        "color_table_text": "#000000",
        "color_online": "#C8F0C8",
        "color_online_fg": "#000000",
        "color_offline": "#FFC8C8",
        "color_offline_fg": "#000000",
        "color_unknown": "#FFFFFF",
        "color_unknown_fg": "#000000",
        "color_quality_a": "#E8F5E9",
        "color_quality_b": "#FFF8E1",
        "color_quality_c": "#FFEBEB",
        "color_group_hmt": "#E53E3E",
        "color_group_cctv": "#2B6CB0",
        "color_group_province": "#3182CE",
        "color_group_movie": "#805AD5",
        "color_group_sport": "#38A169",
        "color_group_kids": "#D69E2E",
        "color_group_round": "#4A5568",
        "color_group_city": "#2D3748",
        "color_group_misc": "#718096",
        "show_ch_geo": True,
        "show_ch_stack": True,
        "show_ch_group": True,
        "show_ch_tag": True,
        "show_ch_quality": True,
        "sort_column": 0,
        "sort_order": "升序",
        "default_column_widths": [40, 160, 65, 80, 50, 90, 50, 60, 90, 80, 260],
        "column_labels": ["#", "频道", "在线状态", "状态", "ms", "分辨率", "质量", "网络栈", "分组", "标记", "地址"],
        "column_visibility": [True, True, True, True, True, True, True, True, True, True, True],
        "video_min_width": 120,
        "log_min_width": 80,
        "lock_splitters": True,
        "filter_status": "全部",
        "filter_stack": "全部协议",
        # 播放器
        "player_update_interval_ms": 500,
        "player_hide_controls_delay_ms": 3000,
        "player_seek_step_ms": 5000,
        "player_keyboard_volume_step": 5,
        "player_keyboard_enabled": True,
        "prefer_external_player": False,
        "external_player": "vlc",
        "external_player_path": "",  # 手动指定外部播放器可执行文件路径（留空则自动检测）
        "player_stream_proxy": False,  # 内置 HLS 播放经本地后端中继（绕过 WebView 跨源/MSE 限制）
        # 双窗口播放器（Phase 5 设置面板）
        "player_window_topmost": False,  # 播放窗口总在最前（📌置顶默认状态）
        "double_click_auto_play": True,  # 双击频道自动播放（列表即唯一选源入口）
        # 以下三项由「系统设置→播放器」面板保存（SettingsView），此前漏列 DEFAULTS，
        # 导致「恢复默认」会丢失；补齐以保持配置键一致、重置可保留。
        "default_volume": 75,  # 默认音量(%)
        "default_playback_speed": 1.0,  # 默认倍速
        "color_video_bg": "#000000",  # 视频背景色
        # 日志与调试
        "debug_log": False,
        "debug_log_traceback": True,
        "log_timestamp": True,
        "log_max_lines": 5000,
        "log_auto_clear": 10000,
        # 高级/内部参数（全部可调）
        "scrape_page_timeout_multiplier": 2,
        "scrape_page_timeout_max": 30,
        "epg_timeout_multiplier": 3,
        "epg_timeout_max": 15,
        "epg_download_max_retries": 2,
        "repair_check_timeout": 5,
        "repair_max_retries": 1,
        "repair_max_workers": 10,
        "repair_hd_size_threshold": 500000,
        "repair_sd_size_threshold": 100000,
        "search_debounce_ms": 200,
        "pending_update_interval_ms": 50,
        "table_update_timer_ms": 200,
        "volume_step": 5,
        "status_bar_message_timeout_ms": 3000,
    }

    @staticmethod
    def load_json(fname, default):
        content, err = FileManager.read_text(fname)
        if err:
            return default
        try:
            return json.loads(content)
        except:
            return default

    @staticmethod
    def save_json(fname, data, max_len=20):
        try:
            if isinstance(data, list):
                data = data[:max_len]
            content = json.dumps(data, ensure_ascii=False, indent=2)
            success, err = FileManager.write_text(fname, content)
            return success
        except:
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
        """从 settings.json 读取单个配置项，失败返回 default"""
        settings = Config.load_settings()
        return settings.get(key, default)

    @staticmethod
    def get_data_dir():
        """获取运行期数据目录（EXE 所在目录，或开发态仓库根目录）。
        所有运行时文件（settings.json、channels.db、channels_cache.json 等）
        都落在此目录下。"""
        try:
            from app.main import DATA_DIR
            return DATA_DIR
        except ImportError:
            return os.getcwd()