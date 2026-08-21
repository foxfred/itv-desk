"""辅助工具函数 - find_logo + LOGO_DB（外置为 data/logos.json）+ FileManager"""
import re
import os
import json
from app.config import Config, FileManager


# ==================== Logo 数据库 ====================
# 硬编码维护成本高且易失效，已外置为 backend/app/data/logos.json；
# 文件优先，缺失/损坏时回退到下方内嵌副本，保证向后兼容与可用性。
_LOGO_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data", "logos.json")

_EMBEDDED_LOGO_DB = {
    "中天新闻": "https://gitee.com/suxuang/TVlogo/raw/main/img/CTI2.png",
    "中天娱乐": "https://gitee.com/suxuang/TVlogo/raw/main/img/CTI3.png",
    "凤凰中文": "https://gcore.jsdelivr.net/gh/yuanzl77/TVlogo@master/png/凤凰中文.png",
    "凤凰资讯": "https://gcore.jsdelivr.net/gh/yuanzl77/TVlogo@master/png/凤凰资讯.png",
    "凤凰香港": "https://gcore.jsdelivr.net/gh/yuanzl77/TVlogo@master/png/凤凰香港.png",
    "翡翠台": "https://gcore.jsdelivr.net/gh/yuanzl77/TVlogo@master/png/翡翠台.png",
    "明珠台": "https://gcore.jsdelivr.net/gh/yuanzl77/TVlogo@master/png/明珠台.png",
    "TVBS亚洲": "https://gcore.jsdelivr.net/gh/yuanzl77/TVlogo@master/png/TVBS亚洲.png",
    "TVBS新闻": "https://gcore.jsdelivr.net/gh/yuanzl77/TVlogo@master/png/TVBS新闻.png",
    "三立新闻": "https://gcore.jsdelivr.net/gh/yuanzl77/TVlogo@master/png/三立新闻.png",
    "三立台湾": "https://gcore.jsdelivr.net/gh/yuanzl77/TVlogo@master/png/三立台湾.png",
    "三立都会": "https://gcore.jsdelivr.net/gh/yuanzl77/TVlogo@master/png/三立都会.png",
    "东森综合": "https://gcore.jsdelivr.net/gh/yuanzl77/TVlogo@master/png/东森综合.png",
    "东森超视": "https://gcore.jsdelivr.net/gh/yuanzl77/TVlogo@master/png/东森超视.png",
    "东森电影": "https://gcore.jsdelivr.net/gh/yuanzl77/TVlogo@master/png/东森电影.png",
    "东森新闻": "https://gcore.jsdelivr.net/gh/yuanzl77/TVlogo@master/png/东森新闻.png",
    "纬来体育": "https://gcore.jsdelivr.net/gh/yuanzl77/TVlogo@master/png/纬来体育.png",
    "纬来育乐": "https://gcore.jsdelivr.net/gh/yuanzl77/TVlogo@master/png/纬来育乐.png",
    "无线新闻": "https://gcore.jsdelivr.net/gh/yuanzl77/TVlogo@master/png/无线新闻.png",
    "香港卫视": "https://gcore.jsdelivr.net/gh/yuanzl77/TVlogo@master/png/香港卫视.png",
    "Viutv": "https://gcore.jsdelivr.net/gh/yuanzl77/TVlogo@master/png/Viutv.png",
    "靖天资讯": "https://www.xn--rgv465a.top/tvlogo/靖天资讯.png",
    "CCTV1": "https://gcore.jsdelivr.net/gh/yuanzl77/TVlogo@master/png/CCTV1.png",
    "CCTV2": "https://gcore.jsdelivr.net/gh/yuanzl77/TVlogo@master/png/CCTV2.png",
    "CCTV3": "https://gcore.jsdelivr.net/gh/yuanzl77/TVlogo@master/png/CCTV3.png",
    "CCTV4": "https://gcore.jsdelivr.net/gh/yuanzl77/TVlogo@master/png/CCTV4.png",
    "CCTV5": "https://gcore.jsdelivr.net/gh/yuanzl77/TVlogo@master/png/CCTV5.png",
    "CCTV6": "https://gcore.jsdelivr.net/gh/yuanzl77/TVlogo@master/png/CCTV6.png",
    "CCTV7": "https://gcore.jsdelivr.net/gh/yuanzl77/TVlogo@master/png/CCTV7.png",
    "CCTV8": "https://gcore.jsdelivr.net/gh/yuanzl77/TVlogo@master/png/CCTV8.png",
    "CCTV10": "https://gcore.jsdelivr.net/gh/yuanzl77/TVlogo@master/png/CCTV10.png",
    "CCTV13": "https://gcore.jsdelivr.net/gh/yuanzl77/TVlogo@master/png/CCTV13.png",
    "湖南卫视": "https://gcore.jsdelivr.net/gh/yuanzl77/TVlogo@master/png/湖南卫视.png",
    "浙江卫视": "https://gcore.jsdelivr.net/gh/yuanzl77/TVlogo@master/png/浙江卫视.png",
    "东方卫视": "https://gcore.jsdelivr.net/gh/yuanzl77/TVlogo@master/png/东方卫视.png",
    "江苏卫视": "https://gcore.jsdelivr.net/gh/yuanzl77/TVlogo@master/png/江苏卫视.png",
    "北京卫视": "https://gcore.jsdelivr.net/gh/yuanzl77/TVlogo@master/png/北京卫视.png",
    "广东卫视": "https://gcore.jsdelivr.net/gh/yuanzl77/TVlogo@master/png/广东卫视.png",
    "深圳卫视": "https://gcore.jsdelivr.net/gh/yuanzl77/TVlogo@master/png/深圳卫视.png",
    "安徽卫视": "https://gcore.jsdelivr.net/gh/yuanzl77/TVlogo@master/png/安徽卫视.png",
    "辽宁卫视": "https://gcore.jsdelivr.net/gh/yuanzl77/TVlogo@master/png/辽宁卫视.png",
    "山东卫视": "https://gcore.jsdelivr.net/gh/yuanzl77/TVlogo@master/png/山东卫视.png",
}

_LOGO_DB_CACHE = None


def _load_logo_db():
    content, err = FileManager.read_text(_LOGO_FILE)
    if not err and content:
        try:
            data = json.loads(content)
            if isinstance(data, dict) and data:
                return data
        except Exception:
            pass
    return _EMBEDDED_LOGO_DB


def get_logo_db():
    """返回当前生效的 Logo 数据库（文件优先，回退内嵌）。带缓存，可调用 reload_logo_db 刷新。"""
    global _LOGO_DB_CACHE
    if _LOGO_DB_CACHE is None:
        _LOGO_DB_CACHE = _load_logo_db()
    return _LOGO_DB_CACHE


def reload_logo_db():
    """重新从文件加载 Logo 数据库（例如用户修改 logos.json 后调用）。"""
    global _LOGO_DB_CACHE
    _LOGO_DB_CACHE = _load_logo_db()
    return _LOGO_DB_CACHE


# 兼容旧引用：直接访问 LOGO_DB 拿到当前生效的数据库
LOGO_DB = get_logo_db()


def find_logo(channel_name):
    if not channel_name:
        return None
    db = get_logo_db()
    if channel_name in db:
        return db[channel_name]
    for key, url in db.items():
        if key in channel_name:
            return url
    clean_name = re.sub(r'\[.*?\]|\(.*?\)|\（.*?\）|HD|4K|高清', '', channel_name).strip()
    for key, url in db.items():
        if key in clean_name:
            return url
    return None


# FileManager 已统一收敛至 app.config.FileManager，本文件不再重复定义。