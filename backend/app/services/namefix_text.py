# -*- coding: utf-8 -*-
"""频道名文本工具层（自 namefix_service.py 抽出）。

纯函数 / 无状态层：正则与关键词常量、繁简转换、名称归一化、垃圾与广告判定、
OCR 坐标分区，以及 OCR 引擎的惰性单例接入。

不依赖 NamefixService，可独立测试（见 namefix_service.self_check / resolve_check）。
"""

import os
import re
import subprocess
import threading

_FFMPEG = os.environ.get("IPTV_FFMPEG", "ffmpeg")
_UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
_CREATE_NO_WINDOW = getattr(subprocess, "CREATE_NO_WINDOW", 0)
GRAB_TIMEOUT = 12

_SP = re.compile(r"[\s\-_\.·#、，,。:：;；!！?？\"'“”‘’()（）\[\]【】《》<>/\\|]+")
_HD = re.compile(r"(超高清|超清|高清|标清|fhd|uhd|hd|蓝光|原画|流畅|无插件|线路\d*|\d{3,4}p)+$", re.I)
_NUM = re.compile(r"\d+")
_PLUS = re.compile(r"(plus|加|\+)$", re.I)

_T2S = {
    "聞": "闻", "視": "视", "電": "电", "頻": "频", "道": "道", "體": "体", "育": "育",
    "財": "财", "經": "经", "綜": "综", "藝": "艺", "劇": "剧", "戲": "戏", "兒": "儿",
    "衛": "卫", "鳳": "凤", "凰": "凰", "華": "华", "東": "东", "龍": "龙", "馬": "马",
    "國": "国", "際": "际", "樂": "乐", "業": "业", "產": "产", "會": "会", "務": "务",
    "動": "动", "園": "园", "團": "团", "場": "场", "島": "岛", "廣": "广", "應": "应",
    "慶": "庆", "戶": "户", "報": "报", "據": "据", "擊": "击", "攝": "摄", "數": "数",
    "於": "于", "時": "时", "書": "书", "機": "机", "權": "权", "歐": "欧", "歲": "岁",
    "發": "发", "監": "监", "覽": "览", "訊": "讯", "記": "记", "話": "话", "語": "语",
    "說": "说", "資": "资", "車": "车", "農": "农", "運": "运", "過": "过", "郵": "邮",
    "銀": "银", "錢": "钱", "鎮": "镇", "長": "长", "門": "门", "開": "开", "關": "关",
    "陽": "阳", "隊": "队", "雲": "云", "須": "须", "頭": "头", "題": "题", "類": "类",
    "風": "风", "飛": "飞", "飯": "饭", "點": "点", "齊": "齐", "麼": "么", "黃": "黄",
    "與": "与", "萬": "万", "雙": "双", "難": "难", "靈": "灵", "頁": "页", "項": "项",
    "順": "顺", "預": "预", "領": "领", "顯": "显", "願": "愿", "價": "价", "購": "购",
    "選": "选", "進": "进", "遠": "远", "適": "适", "釋": "释", "鄉": "乡", "劃": "划",
    "剛": "刚", "創": "创", "辦": "办", "勝": "胜", "勞": "劳", "勢": "势", "匯": "汇",
    "區": "区", "醫": "医", "協": "协", "單": "单", "嚴": "严", "嚐": "尝", "囉": "啰",
    "寶": "宝", "宮": "宫", "將": "将", "層": "层", "師": "师", "帶": "带", "幾": "几",
    "彙": "汇", "徹": "彻", "態": "态", "懷": "怀", "戰": "战", "掛": "挂", "揮": "挥",
    "損": "损", "搖": "摇", "擔": "担", "擴": "扩", "擺": "摆", "敗": "败", "敵": "敌",
    "斷": "断", "無": "无", "舊": "旧", "計": "计", "訂": "订", "討": "讨", "訓": "训",
    "訪": "访", "設": "设", "許": "许", "評": "评", "認": "认", "誠": "诚", "調": "调",
    "談": "谈", "請": "请", "謝": "谢", "譯": "译", "護": "护", "變": "变", "讓": "让",
    "豐": "丰", "貝": "贝", "責": "责", "貨": "货", "貴": "贵", "費": "费", "貼": "贴",
    "賺": "赚", "贈": "赠", "趕": "赶", "踐": "践", "輪": "轮", "轉": "转", "載": "载",
    "較": "较", "輕": "轻", "輛": "辆", "輸": "输", "邊": "边", "鄰": "邻", "鐘": "钟",
    "鋼": "钢", "錄": "录", "鏡": "镜", "鐵": "铁", "閉": "闭", "間": "间", "陸": "陆",
    "險": "险", "隨": "随", "隱": "隐", "雞": "鸡", "離": "离", "需": "需", "靜": "静",
    "頂": "顶", "頒": "颁", "額": "额", "餐": "餐", "館": "馆", "駐": "驻", "驗": "验",
    "驚": "惊", "髮": "发", "鬥": "斗", "魚": "鱼", "鳥": "鸟", "鹽": "盐", "麗": "丽",
    "蘇": "苏", "滬": "沪", "寧": "宁", "遼": "辽", "陝": "陕", "瓊": "琼", "粵": "粤",
    "臺": "台", "灣": "湾", "濱": "滨", "揚": "扬", "錦": "锦", "濟": "济", "撫": "抚",
    "廈": "厦", "閩": "闽", "贛": "赣", "晉": "晋", "魯": "鲁", "冀": "冀", "豫": "豫",
    "鄂": "鄂", "湘": "湘", "桂": "桂", "滇": "滇", "黔": "黔", "隴": "陇", "滄": "沧",
    "遜": "逊", "灤": "滦", "瀋": "沈", "澤": "泽", "濰": "潍", "煙": "烟", "臨": "临",
    "諸": "诸", "嵊": "嵊", "義": "义", "烏": "乌", "蕪": "芜", "嶺": "岭", "嶽": "岳",
    "巖": "岩", "嶼": "屿", "嵐": "岚",
}
_T2S_TABLE = str.maketrans(_T2S)


def _n(s):
    if not s:
        return ""
    t = str(s).translate(_T2S_TABLE)
    t = _SP.sub("", t.lower())
    t = _PLUS.sub("+", t)
    t = _HD.sub("", t)
    return t.strip()


def _digits(s):
    return tuple(_NUM.findall(str(s or "")))


def _sig(s):
    t = _n(s)
    return tuple(_NUM.findall(t)), t.count("+")


_IDX_TAIL = re.compile(r"[\s_\-]*#\s*\d+\s*$")


def _split_idx(name):
    s = str(name or "")
    m = _IDX_TAIL.search(s)
    if m:
        return s[:m.start()].strip(), m.group(0).strip()
    return s.strip(), ""


_JUNK_KW = ("打赏", "二维码", "扫码", "扫描右", "扫描下", "下载", "安装", "关注我们",
            "公众号", "加群", "客服", "订购电话", "抢购热线", "请查看网站", "版权归",
            "感谢您", "点击链接", "浏览器打开", "固件升级", "无法播放", "打不开",
            "扫码下载", "最新版", "app下载", "android", "安卓系统", "机顶盒",
            "qr code", "qrcode", "download", "latest app", "scan the", "install our",
            "play.google", "apk", "our app")
_URL_RE = re.compile(
    r"(https?://|www\.|[a-z0-9][a-z0-9\-]{1,}\.(?:com|cn|net|tv|xyz|top|cc|me|org|io|app|vip|site|online|club|fun)(?:[/\s:]|$))",
    re.I)
_AD_NOISE = ("洗涤", "清潔", "清洁", "濕巾", "湿巾", "益生菌", "胶原", "膠原", "蛋白", "胜肽",
             "買", "买", "优惠", "限时", "搶購", "抢购", "赞助", "贊助", "热线", "專線", "专线",
             "工厂", "工廠", "正品", "新品", "上市", "代言", "折", "券", "订购", "訂購",
             "專輯", "专辑", "推薦", "推荐", "课程", "課程", "报名", "報名", "夏令",
             "咪咕", "米咕", "米古", "央视频", "集成播控", "BesTV", "百视通", "奇异果",
             "银河电视", "云视听")


def _looks_junk(text):
    t = str(text or "")
    low = t.lower()
    if any(k in low for k in _JUNK_KW):
        return True
    if _URL_RE.search(t):
        return True
    return False


_STATION_KW = ("电视", "卫视", "頻道", "频道", "电台", "電視")


def _is_ad_noise(text):
    t = str(text or "")
    if not any(k in t for k in _AD_NOISE):
        return False
    if len(t) <= 8 and any(k in t for k in _STATION_KW):
        return False
    return True


def _zone(y, x, w, h):
    ry = y / float(h or 1)
    rx = x / float(w or 1)
    if ry < 0.28:
        return ("top", 1.0) if rx < 0.45 else ("topright", 0.0)
    if ry > 0.72:
        return ("bot", 0.85)
    return ("mid", 0.9)


_engine = None
_engine_lock = threading.Lock()
_engine_err = ""


def get_engine():
    global _engine, _engine_err
    if _engine is not None:
        return _engine
    with _engine_lock:
        if _engine is not None:
            return _engine
        try:
            from rapidocr_onnxruntime import RapidOCR
            _engine = RapidOCR()
            _engine_err = ""
        except Exception as e:
            try:
                from rapidocr import RapidOCR as _R2
                _engine = _R2()
                _engine_err = ""
            except Exception as e2:
                _engine_err = f"OCR 引擎不可用：{e} / {e2}"
                _engine = False
    return _engine


def ocr_available():
    return bool(get_engine())


def _ocr_lines(path):
    eng = get_engine()
    if not eng:
        return None
    try:
        out = eng(path)
    except Exception:
        return None
    res = out[0] if isinstance(out, tuple) else getattr(out, "boxes", None)
    if not res:
        return []
    try:
        from PIL import Image
        with Image.open(path) as im:
            W, H = im.size
    except Exception:
        W, H = 0, 0
    lines = []
    for item in res:
        try:
            box, text, score = item[0], str(item[1]), float(item[2])
            ys = [p[1] for p in box]
            xs = [p[0] for p in box]
        except Exception:
            continue
        if not text.strip():
            continue
        lines.append({"t": text.strip(), "s": round(score, 3),
                      "y": int(sum(ys) / len(ys)), "x": int(sum(xs) / len(xs)),
                      "W": W, "H": H})
    return lines
