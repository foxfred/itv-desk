import os
import re
import io
import json
import time
import html
import shutil
import hashlib
import threading
import subprocess
import difflib
from collections import Counter, defaultdict

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
    "順": "顺", "預": "预", "領": "领", "顯": "显", "願": "愿", "戲": "戏", "價": "价",
    "購": "购", "選": "选", "進": "进", "遠": "远", "適": "适", "釋": "释", "鄉": "乡",
    "鄉": "乡", "劃": "划", "剛": "刚", "創": "创", "辦": "办", "勝": "胜", "勞": "劳",
    "勢": "势", "匯": "汇", "區": "区", "醫": "医", "協": "协", "單": "单", "嚴": "严",
    "嚐": "尝", "囉": "啰", "寶": "宝", "宮": "宫", "將": "将", "層": "层", "師": "师",
    "帶": "带", "幾": "几", "廣": "广", "彙": "汇", "徹": "彻", "態": "态", "懷": "怀",
    "戰": "战", "戶": "户", "掛": "挂", "揮": "挥", "損": "损", "搖": "摇", "擔": "担",
    "擴": "扩", "擺": "摆", "攝": "摄", "敗": "败", "敵": "敌", "斷": "断", "無": "无",
    "舊": "旧", "計": "计", "訂": "订", "討": "讨", "訓": "训", "訪": "访", "設": "设",
    "許": "许", "評": "评", "認": "认", "誠": "诚", "調": "调", "談": "谈", "請": "请",
    "謝": "谢", "譯": "译", "護": "护", "變": "变", "讓": "让", "豐": "丰", "貝": "贝",
    "責": "责", "貨": "货", "貴": "贵", "費": "费", "貼": "贴", "賺": "赚", "贈": "赠",
    "趕": "赶", "踐": "践", "車": "车", "輪": "轮", "轉": "转", "載": "载", "較": "较",
    "輕": "轻", "輛": "辆", "輸": "输", "辦": "办", "邊": "边", "鄰": "邻", "醫": "医",
    "鐘": "钟", "鋼": "钢", "錄": "录", "鏡": "镜", "鐵": "铁", "長": "长", "閉": "闭",
    "間": "间", "聞": "闻", "關": "关", "陸": "陆", "險": "险", "隨": "随", "隱": "隐",
    "雞": "鸡", "離": "离", "難": "难", "電": "电", "需": "需", "靜": "静", "頁": "页",
    "頂": "顶", "項": "项", "順": "顺", "預": "预", "頒": "颁", "領": "领", "頻": "频",
    "題": "题", "額": "额", "願": "愿", "類": "类", "風": "风", "飛": "飞", "餐": "餐",
    "館": "馆", "駐": "驻", "驗": "验", "驚": "惊", "髮": "发", "鬥": "斗", "魚": "鱼",
    "鳥": "鸟", "鹽": "盐", "麗": "丽", "黃": "黄", "點": "点", "齊": "齐", "龍": "龙",
    "蘇": "苏", "滬": "沪", "寧": "宁", "遼": "辽", "陝": "陕", "瓊": "琼", "粵": "粤",
    "臺": "台", "灣": "湾", "濱": "滨", "揚": "扬", "錦": "锦", "濟": "济", "撫": "抚",
    "廈": "厦", "閩": "闽", "贛": "赣", "晉": "晋", "魯": "鲁", "冀": "冀", "豫": "豫",
    "鄂": "鄂", "湘": "湘", "桂": "桂", "滇": "滇", "黔": "黔", "隴": "陇", "瓊": "琼",
    "粵": "粤", "滄": "沧", "遜": "逊", "灤": "滦", "瀋": "沈", "澤": "泽", "濰": "潍",
    "濟": "济", "煙": "烟", "臨": "临", "諸": "诸", "嵊": "嵊", "義": "义", "烏": "乌",
    "蕪": "芜", "撫": "抚", "嶺": "岭", "嶽": "岳", "巖": "岩", "嶼": "屿", "嵐": "岚",
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


class NameIndex:

    def __init__(self, pool_names, alias_map):
        self.exact = {}
        self.canon_digits = {}
        for canon, al in (alias_map or {}).items():
            self._put(canon, canon)
            for a in al or []:
                self._put(a, canon)
        for nm in pool_names or []:
            if nm:
                self._put(nm, nm)

    def _put(self, key, canon):
        k = _n(key)
        if not k:
            return
        self.exact.setdefault(k, canon)
        self.canon_digits.setdefault(canon, _digits(canon))

    def lookup(self, text, fuzzy=0.86):
        k = _n(text)
        if len(k) < 2:
            return None, 0.0, ""
        hit = self.exact.get(k)
        if hit:
            return hit, 0.96, "exact"
        sig = _sig(k)
        best_c, best_cov = None, 0.0
        for cand_key, canon in self.exact.items():
            if len(cand_key) < 4 or cand_key == k:
                continue
            if _sig(cand_key) != sig:
                continue
            if cand_key in k:
                cov = len(cand_key) / float(len(k))
                if cov > best_cov:
                    best_cov, best_c = cov, canon
        if best_c and best_cov >= 0.33:
            return best_c, round(min(0.88, 0.55 + 0.33 * best_cov), 3), "contain"
        best, bestr = None, 0.0
        for cand_key, canon in self.exact.items():
            if abs(len(cand_key) - len(k)) > 2:
                continue
            if _sig(cand_key) != sig:
                continue
            if len(cand_key) < 3 or len(k) < 3:
                continue
            r = difflib.SequenceMatcher(None, k, cand_key).ratio()
            if r > bestr:
                bestr, best = r, canon
        if best and bestr >= fuzzy:
            return best, round(0.55 + 0.35 * bestr, 3), "fuzzy"
        return None, 0.0, ""


class EpgReverse:

    def __init__(self, epg_service):
        self.index = defaultdict(Counter)
        self.ready = False
        self.build_error = ""
        try:
            if not getattr(epg_service, "epg_loaded", False) or not getattr(epg_service, "epg_data", None):
                self.build_error = "EPG 未加载"
                return
            from datetime import datetime
            now = datetime.now()
            n = 0
            for chan, info in epg_service.epg_data.items():
                canon = _n(chan)
                for prog in info.get("programs", []):
                    s, e = prog.get("start", ""), prog.get("stop", "")
                    if not s or not e:
                        continue
                    try:
                        st = datetime.strptime(s[:14], "%Y%m%d%H%M%S")
                        sp = datetime.strptime(e[:14], "%Y%m%d%H%M%S")
                    except Exception:
                        continue
                    if not (st <= now <= sp):
                        continue
                    title = _n(prog.get("title", ""))
                    if len(title) < 4:
                        continue
                    for L in (4, 5, 6, 7, 8):
                        for i in range(0, len(title) - L + 1):
                            self.index[title[i:i + L]][canon] += L
                    n += 1
            self.ready = n > 0
            if not self.ready:
                self.build_error = "EPG 当前时段无节目数据"
        except Exception as e:
            self.build_error = f"EPG 索引构建失败：{e}"

    def vote(self, text):
        if not self.ready:
            return None, 0
        t = _n(text)
        if len(t) < 4:
            return None, 0
        acc = Counter()
        for L in (4, 5, 6, 7, 8):
            if len(t) < L:
                break
            for i in range(0, len(t) - L + 1):
                sh = t[i:i + L]
                c = self.index.get(sh)
                if c:
                    for chan, w in c.items():
                        acc[chan] += w
        if not acc:
            return None, 0
        top = acc.most_common(2)
        if len(top) > 1 and top[0][1] == top[1][1]:
            return None, 0
        return top[0][0], top[0][1]


class NamefixService:
    def __init__(self, data_dir=None, log_callback=None):
        self.data_dir = data_dir or os.getcwd()
        self.log = log_callback or (lambda m: None)
        self.sug_file = os.path.join(self.data_dir, "namefix_suggestions.json")
        self.undo_file = os.path.join(self.data_dir, "namefix_undo.json")
        self.shot_dir = os.path.join(self.data_dir, "screenshots")
        try:
            os.makedirs(self.shot_dir, exist_ok=True)
        except Exception:
            pass
        self._lock = threading.RLock()
        self._state = {"running": False, "done": 0, "total": 0, "ok": 0,
                       "junk": 0, "resolved": 0, "error": None, "started": 0,
                       "finished": 0, "applied": 0}
        self.items = {}
        self._load()

    def _settings(self):
        try:
            from app.config import Config
            return Config.load_settings() or {}
        except Exception:
            return {}

    def _cfg(self, key, default=None):
        v = self._settings().get(key, None)
        return default if v is None else v

    def _channel_service(self):
        from app.main import channel_service
        return channel_service

    def _epg_service(self):
        try:
            from app.main import epg_service
            return epg_service
        except Exception:
            return None

    def _load(self):
        try:
            d = json.load(io.open(self.sug_file, encoding="utf-8"))
            items = d.get("items", []) if isinstance(d, dict) else []
            self.items = {str(it.get("cid")): it for it in items if it.get("cid") is not None}
        except Exception:
            self.items = {}

    def _save(self):
        try:
            tmp = self.sug_file + ".tmp"
            with io.open(tmp, "w", encoding="utf-8") as f:
                json.dump({"updated": time.time(),
                           "items": list(self.items.values())}, f,
                          ensure_ascii=False, indent=1)
            os.replace(tmp, self.sug_file)
        except Exception as e:
            self.log("建议表保存失败：%s" % e)

    def _load_undo(self):
        try:
            d = json.load(io.open(self.undo_file, encoding="utf-8"))
            return d.get("batches", []) if isinstance(d, dict) else []
        except Exception:
            return []

    def _save_undo(self, batches):
        try:
            tmp = self.undo_file + ".tmp"
            with io.open(tmp, "w", encoding="utf-8") as f:
                json.dump({"batches": batches[-20:]}, f, ensure_ascii=False, indent=1)
            os.replace(tmp, self.undo_file)
        except Exception as e:
            self.log("撤销记录保存失败：%s" % e)

    def _frame_path(self, url):
        return os.path.join(self.shot_dir, "nf_" + hashlib.md5(
            (url or "").encode("utf-8", "ignore")).hexdigest()[:16] + ".jpg")

    def _grab(self, url, out, width, offset):
        url = (url or "").strip()
        if not url:
            return False, "无地址"
        if url.lower().startswith(("udp://", "rtp://", "srt://")):
            return False, "协议不支持截图"
        head = [_FFMPEG, "-y", "-hide_banner", "-loglevel", "error",
                "-rw_timeout", str(GRAB_TIMEOUT * 1_000_000)]
        tail = ["-frames:v", "1", "-vf", "scale=%d:-2" % width, "-q:v", "3", out]
        ss = ["-ss", str(offset)] if offset and float(offset) > 0 else []
        ua = ["-user_agent", _UA]
        combos, seen = [], set()
        for use_ua in (True, False):
            for pre in (ss, []):
                c = (ua if use_ua else []) + pre
                k = tuple(c)
                if k not in seen:
                    seen.add(k)
                    combos.append(c)
        last = ""
        ua_broken = False
        FATAL = ("Connection refused", "Could not resolve", "Server returned 4",
                 "Invalid data found", "No route to host", "Protocol not found",
                 "No such file or directory")
        for pre in combos:
            if ua_broken and "-user_agent" in pre:
                continue
            try:
                os.remove(out)
            except Exception:
                pass
            try:
                p = subprocess.run(head + pre + ["-i", url] + tail, capture_output=True,
                                   timeout=GRAB_TIMEOUT, creationflags=_CREATE_NO_WINDOW)
                if p.returncode == 0 and os.path.isfile(out) and os.path.getsize(out) > 1024:
                    return True, ""
                last = (p.stderr or b"").decode("utf-8", "ignore").strip()[-120:] or "抓帧失败"
                if "Option not found" in last:
                    ua_broken = True
                elif any(k in last for k in FATAL):
                    break
            except subprocess.TimeoutExpired:
                last = "抓帧超时"
            except FileNotFoundError:
                return False, "未找到 ffmpeg（设置环境变量 IPTV_FFMPEG 或加入 PATH）"
            except Exception as e:
                last = str(e)[:120]
        return False, last

    def _frame_for(self, url, width, offset, reuse):
        p = self._frame_path(url)
        if os.path.isfile(p) and os.path.getsize(p) > 1024:
            return p, True, "缓存帧"
        if reuse:
            try:
                from app.main import screenshot_service
                idx = screenshot_service.list_index()
                rel = idx.get(url)
                if rel:
                    cand = os.path.join(self.shot_dir, os.path.basename(rel))
                    if os.path.isfile(cand):
                        w, _h = _img_size(cand)
                        if w >= width:
                            return cand, True, "复用截图"
            except Exception:
                pass
        ok, err = self._grab(url, p, width, offset)
        return (p, True, "") if ok else (None, False, err)

    def vision_ask(self, frame_path, override=None):
        s = dict(override) if override else self._settings()
        if not s.get("namefix_vision_enabled"):
            return None, "视觉兜底未启用"
        base = (s.get("namefix_vision_base") or "").strip()
        model = (s.get("namefix_vision_model") or "").strip()
        key = (s.get("namefix_vision_key") or "").strip()
        if not base or not model or not key:
            return None, "视觉接口未配置完整（地址/模型/Key）"
        try:
            import base64
            import urllib.request
            b64 = base64.b64encode(io.open(frame_path, "rb").read()).decode()
            prompt = ("这是电视直播画面截图。请判断这是哪个电视频道。"
                      "只回答频道名称（如 CCTV-5+、湖南卫视、浙江少儿）；"
                      "如果无法判断就只回答两个字：未知。不要解释，不要加标点。")
            body = {"model": model, "max_tokens": 32, "temperature": 0.01,
                    "messages": [{"role": "user", "content": [
                        {"type": "text", "text": prompt},
                        {"type": "image_url",
                         "image_url": {"url": "data:image/jpeg;base64," + b64}}]}]}
            req = urllib.request.Request(
                base, data=json.dumps(body).encode("utf-8"),
                headers={"Content-Type": "application/json",
                         "Authorization": "Bearer " + key})
            timeout = int(s.get("namefix_vision_timeout") or 45)
            with urllib.request.urlopen(req, timeout=timeout) as r:
                d = json.loads(r.read().decode("utf-8"))
            txt = ((d.get("choices") or [{}])[0].get("message", {}) or {}).get("content", "")
            txt = str(txt or "").strip().strip("。.，,；;\"'“”")
            if not txt or txt in ("未知", "无法判断", "unknown", "Unknown"):
                return None, "视觉模型未能识别"
            return txt, ""
        except Exception as e:
            return None, "视觉接口调用失败：%s" % str(e)[:120]

    def vision_test(self):
        s = self._settings()
        if not (s.get("namefix_vision_key") or "").strip():
            return {"ok": False, "error": "未填写视觉接口 Key"}
        frame = None
        for fn in sorted(os.listdir(self.shot_dir)) if os.path.isdir(self.shot_dir) else []:
            if fn.lower().endswith((".jpg", ".png")):
                frame = os.path.join(self.shot_dir, fn)
                break
        if not frame:
            return {"ok": False, "error": "没有可用于测试的画面帧，请先抓帧"}
        name, err = self.vision_ask(frame, override=dict(s, namefix_vision_enabled=True))
        return {"ok": bool(name), "answer": name or "", "error": err,
                "frame": os.path.basename(frame)}

    def analyze_one(self, ch, index, epgrev, width, offset, reuse, use_vision):
        cid = ch.get("id")
        url = (ch.get("url") or "").strip()
        cur = (ch.get("name") or "").strip()
        cur_base, cur_suffix = _split_idx(cur)
        rec = {"cid": cid, "url": url, "old": cur, "group": ch.get("group") or "",
               "new": "", "confidence": 0.0, "kind": "", "region": "", "state": "pending",
               "evidence": "", "votes": {}, "checked_at": time.time(), "note": "",
               "cur_base": cur_base, "idx_suffix": cur_suffix}
        if not url:
            rec["state"] = "invalid"
            rec["note"] = "无地址"
            return rec

        frame, ok, info = self._frame_for(url, width, offset, reuse)
        if not ok:
            rec["state"] = "unreachable"
            rec["note"] = "抓帧失败：%s" % info
            return rec
        rec["frame"] = "/screenshots/" + os.path.basename(frame)

        lines = _ocr_lines(frame)
        if lines is None:
            rec["state"] = "ocr_error"
            rec["note"] = _engine_err or "OCR 失败"
            return rec

        w, h = _img_size(frame)
        rec["size"] = [w, h]
        if not lines:
            rec["state"] = "no_text"
            if use_vision:
                name, err = self.vision_ask(frame)
                if name:
                    canon, conf = _resolve(name, index)
                    if canon:
                        rec.update(new=canon + (" " + cur_suffix if cur_suffix else ""),
                                   confidence=round(min(0.86, conf), 3),
                                   kind="vision", region="vision",
                                   note="OCR 无文字，由视觉模型识别")
                        return rec
                rec["note"] = "画面无文字，视觉模型未识别（%s）" % (err or "无结果")
            else:
                rec["note"] = "画面无文字（需视觉兜底或人工）"
            return rec

        regions = {"top": [], "mid": [], "bot": [], "topright": []}
        junk_lines, ad_lines = [], []
        for L in lines:
            t = L["t"]
            if _looks_junk(t):
                junk_lines.append(t)
                continue
            if _is_ad_noise(t):
                ad_lines.append(t)
                continue
            zone, w0 = _zone(L["y"], L["x"], w, h)
            regions[zone].append((t, w0))

        rec["texts"] = {k: [t for t, _w in v][:6] for k, v in regions.items()}
        rec["junk_texts"] = junk_lines[:4]

        useful = sum(len(v) for v in regions.values())
        if len(junk_lines) >= 3 and useful <= 2:
            rec["state"] = "junk"
            rec["note"] = "疑似推广/下载引导页，非正常频道画面（%d 条推广特征）" % len(junk_lines)
            return rec
        if len(junk_lines) >= 2 and _URL_RE.search(" ".join(junk_lines)):
            rec["state"] = "junk"
            rec["note"] = "含下载链接的推广页"
            return rec

        tr_texts = [t for t, _w in regions["topright"]]
        blk_note = ""
        if tr_texts:
            blk_note = "右上角角标「%s」按栏目/平台水印处理，未采纳（台标以左上角为准）" % \
                "、".join(tr_texts[:2])

        votes = Counter()
        detail = {}
        for zone in ("top", "mid", "bot"):
            for t, weight in regions[zone]:
                canon, score, kind = index.lookup(t, float(self._cfg("namefix_fuzzy_threshold", 0.86)))
                if not canon:
                    continue
                votes[canon] += score * weight
                detail.setdefault(canon, []).append({"t": t, "kind": kind, "score": score,
                                                     "region": zone})
        rec["votes"] = {k: round(v, 3) for k, v in votes.most_common(5)}

        epg_note = ""
        best, conf, kind, region = None, 0.0, "", ""
        if votes:
            ranked = votes.most_common(2)
            if len(ranked) > 1 and abs(ranked[0][1] - ranked[1][1]) < 0.02 and ranked[0][0] != ranked[1][0]:
                rec["state"] = "ambiguous"
                rec["note"] = "台标候选中票数接近（%s / %s），不自动改名" % (ranked[0][0], ranked[1][0])
                return rec
            best = ranked[0][0]
            d0 = detail[best][0]
            region, kind = d0["region"], d0["kind"]
            base = {"exact": 0.95, "alias": 0.93, "fuzzy": d0["score"]}.get(kind, d0["score"])
            conf = base + (0.02 if len(detail[best]) >= 2 else 0.0)
            if region == "top":
                conf += 0.01
            else:
                conf = min(conf, 0.88)
        else:
            if epgrev and epgrev.ready:
                for zone in ("bot", "mid", "top"):
                    for t, _w in regions[zone]:
                        cand, weight = epgrev.vote(t)
                        if cand:
                            best, conf, kind, region = cand, 0.72, "epg", zone
                            epg_note = "字幕条节目名反查 EPG 得到"
                            break
                    if best:
                        break

        if not best:
            rec["state"] = "unresolved"
            rec["note"] = "画面文字里没有可判定的频道信息"
            if blk_note:
                rec["note"] += "；" + blk_note
            return rec

        if best and epgrev and epgrev.ready and kind != "epg":
            for t, _w in (regions["bot"] + regions["mid"])[:6]:
                cand, weight = epgrev.vote(t)
                if cand:
                    if cand == _n(best):
                        conf += 0.03
                        epg_note = "EPG 节目单同向，置信度上调"
                    else:
                        conf = min(conf, 0.5)
                        epg_note = "EPG 节目单指向 %s，与台标结论冲突，需人工确认" % cand
                    break

        conf = round(min(0.99, conf), 3)
        rec["new"] = best + (" " + cur_suffix if cur_suffix else "")
        rec["confidence"] = conf
        rec["kind"] = kind
        rec["region"] = region
        rec["note"] = epg_note
        if blk_note:
            rec["note"] = (rec["note"] + "；" if rec["note"] else "") + blk_note
        rec["detail"] = detail.get(best, [])[:4]

        if _n(cur_base) == _n(best):
            rec["state"] = "consistent"
            rec["note"] = (rec["note"] + "；" if rec["note"] else "") + "与现名一致，无需改名"
            return rec
        if _digits(cur_base) and _sig(cur_base) != _sig(best):
            rec["note"] = (rec["note"] + "；" if rec["note"] else "") + \
                "现名与识别名数字不一致（%s→%s），建议人工确认" % (cur_base, best)
            rec["confidence"] = round(min(conf, 0.75), 3)
        rec["state"] = "pending"
        return rec

    def scan(self, ids=None, limit=None, use_vision=None):
        cs = self._channel_service()
        pool = list(getattr(cs, "pool", []) or [])
        if ids:
            want = {int(i) for i in ids if str(i).strip()}
            pool = [c for c in pool if c.get("id") in want]
        if limit:
            pool = pool[:int(limit)]
        if not pool:
            return {"started": False, "error": "没有可扫描的频道"}

        s = self._settings()
        width = int(s.get("namefix_capture_width") or 960)
        offset = float(s.get("namefix_capture_offset") or 3)
        reuse = bool(s.get("namefix_reuse_screenshot", True))
        strategy = (s.get("namefix_strategy") or "advise").strip()
        vision = bool(s.get("namefix_vision_enabled")) if use_vision is None else bool(use_vision)
        workers = max(1, min(12, int(s.get("namefix_workers") or 4)))

        with self._lock:
            if self._state.get("running"):
                return {"started": False, "error": "已有扫描任务在运行"}
            self._state = {"running": True, "done": 0, "total": len(pool), "ok": 0,
                           "junk": 0, "resolved": 0, "error": None,
                           "started": time.time(), "finished": 0, "applied": 0,
                           "strategy": strategy}

        def work():
            try:
                from concurrent.futures import ThreadPoolExecutor
                eng_ok = ocr_available()
                if not eng_ok:
                    with self._lock:
                        self._state["error"] = _engine_err or "OCR 引擎不可用（请安装 rapidocr-onnxruntime）"
                        self._state["running"] = False
                    return
                base_names = []
                for c in getattr(cs, "pool", []) or []:
                    b, _sfx = _split_idx(c.get("name"))
                    if b:
                        base_names.append(b)
                index = NameIndex(base_names, self._load_alias())
                epgrev = EpgReverse(self._epg_service())
                self.log("名称校正扫描启动：%d 个频道，%d 线程，抓帧 %dpx/%ss，策略 %s%s"
                         % (len(pool), workers, width, offset, strategy,
                            "，EPG 反查就绪" if epgrev.ready else "，EPG 反查不可用(%s)" % epgrev.build_error))

                def run(ch):
                    try:
                        return self.analyze_one(ch, index, epgrev, width, offset, reuse, vision)
                    except Exception as e:
                        return {"cid": ch.get("id"), "url": ch.get("url"), "old": ch.get("name"),
                                "state": "error", "note": "分析异常：%s" % str(e)[:120],
                                "confidence": 0.0, "checked_at": time.time()}

                with ThreadPoolExecutor(max_workers=workers) as ex:
                    for rec in ex.map(run, pool):
                        save_now = False
                        with self._lock:
                            self.items[str(rec.get("cid"))] = rec
                            st = self._state
                            st["done"] += 1
                            if rec.get("state") == "junk":
                                st["junk"] += 1
                            elif rec.get("state") == "pending":
                                st["resolved"] += 1
                            if rec.get("new"):
                                st["ok"] += 1
                            if st["done"] % 25 == 0:
                                save_now = True
                        if save_now:
                            self._save()
                self._save()

                applied = 0
                if strategy in ("auto_high", "auto_all"):
                    minc = float(s.get("namefix_min_confidence") or 0.9)
                    targets = [it for it in self.items.values()
                               if it.get("state") == "pending" and it.get("new")
                               and (strategy == "auto_all" or float(it.get("confidence") or 0) >= minc)]
                    r = self.apply([it["cid"] for it in targets])
                    applied = r.get("changed", 0)
                with self._lock:
                    self._state["applied"] = applied
                    self._state["running"] = False
                    self._state["finished"] = time.time()
                self.log("名称校正扫描完成：可判定 %d / 共 %d，源异常 %d，自动改名 %d"
                         % (self._state["resolved"], len(pool), self._state["junk"], applied))
            except Exception as e:
                with self._lock:
                    self._state["error"] = str(e)[:200]
                    self._state["running"] = False

        threading.Thread(target=work, daemon=True).start()
        return {"started": True, "total": len(pool), "strategy": strategy,
                "vision": vision, "workers": workers}

    def _load_alias(self):
        try:
            from app.services.alias_service import get_service
            return get_service().all()
        except Exception:
            try:
                return json.load(io.open(os.path.join(self.data_dir, "channel_alias.json"),
                                         encoding="utf-8"))
            except Exception:
                return {}

    def get_status(self):
        with self._lock:
            return dict(self._state)

    def suggestions(self, state=None):
        with self._lock:
            items = list(self.items.values())
        if state:
            items = [it for it in items if it.get("state") == state]
        order = {"pending": 0, "ambiguous": 1, "unresolved": 2, "unreachable": 3,
                 "junk": 4, "no_text": 5, "consistent": 6, "invalid": 7, "error": 8}
        items.sort(key=lambda x: (order.get(x.get("state"), 9), -float(x.get("confidence") or 0)))
        summary = Counter(it.get("state") for it in items)
        return {"total": len(items), "summary": dict(summary), "items": items}

    def dismiss(self, ids):
        n = 0
        with self._lock:
            for cid in ids or []:
                it = self.items.get(str(cid))
                if it:
                    it["state"] = "dismissed"
                    n += 1
            self._save()
        return {"ok": True, "dismissed": n}

    def _backup(self):
        d = os.path.join(self.data_dir, "_bak_%s_改名前" % time.strftime("%Y%m%d"))
        try:
            os.makedirs(d, exist_ok=True)
            for fn in ("channels_cache.json", "channels.db"):
                src = os.path.join(self.data_dir, fn)
                dst = os.path.join(d, fn)
                if os.path.isfile(src) and not os.path.isfile(dst):
                    shutil.copy2(src, dst)
            return d
        except Exception as e:
            self.log("备份失败（继续改名）：%s" % e)
            return ""

    def apply(self, ids=None, force=False):
        cs = self._channel_service()
        with self._lock:
            targets = []
            for it in self.items.values():
                if ids and str(it.get("cid")) not in {str(i) for i in ids}:
                    continue
                if not ids and it.get("state") != "pending":
                    continue
                if not it.get("new"):
                    continue
                if it.get("state") == "dismissed" and not ids:
                    continue
                targets.append(it)
        if not targets:
            return {"ok": True, "changed": 0, "msg": "没有可应用的建议"}
        self._backup()
        changes, failed = [], []
        for it in targets:
            cid, new = it.get("cid"), it.get("new")
            old = it.get("old") or ""
            try:
                r = cs.update_channel(cid, name=new)
                if r is False:
                    failed.append({"cid": cid, "error": "频道不存在（可能已被删除）"})
                    continue
                it["state"] = "applied"
                it["old"] = new
                it["applied_at"] = time.time()
                changes.append({"cid": cid, "old": old, "new": new, "url": it.get("url")})
            except Exception as e:
                failed.append({"cid": cid, "error": str(e)[:120]})
        if changes:
            batches = self._load_undo()
            batches.append({"id": "nf%d" % int(time.time()),
                            "ts": time.time(),
                            "count": len(changes),
                            "changes": changes})
            self._save_undo(batches)
        with self._lock:
            self._save()
        if changes:
            try:
                cs._store_rebuild()
            except Exception:
                pass
        self.log("名称校正应用：改名 %d 个，失败 %d 个" % (len(changes), len(failed)))
        return {"ok": True, "changed": len(changes), "failed": failed}

    def undo(self, batch_id=None):
        cs = self._channel_service()
        batches = self._load_undo()
        if not batches:
            return {"ok": False, "error": "没有可撤销的记录"}
        b = None
        if batch_id:
            for x in batches:
                if x.get("id") == batch_id:
                    b = x
        else:
            b = batches[-1]
        if not b:
            return {"ok": False, "error": "找不到该批次"}
        n = 0
        for ch in b.get("changes", []):
            try:
                cs.update_channel(ch["cid"], name=ch["old"])
                it = self.items.get(str(ch["cid"]))
                if it:
                    it["state"] = "dismissed"
                    it["old"] = ch["old"]
                n += 1
            except Exception:
                pass
        batches = [x for x in batches if x.get("id") != b.get("id")]
        self._save_undo(batches)
        with self._lock:
            self._save()
        try:
            cs._store_rebuild()
        except Exception:
            pass
        self.log("名称校正撤销：还原 %d 个" % n)
        return {"ok": True, "restored": n}

    def undo_list(self):
        return {"batches": [{"id": b.get("id"), "ts": b.get("ts"),
                             "count": b.get("count", len(b.get("changes", [])))}
                            for b in reversed(self._load_undo())]}

    def clear(self):
        with self._lock:
            self.items = {}
            self._save()
        return {"ok": True}


def _img_size(path):
    try:
        from PIL import Image
        with Image.open(path) as im:
            return im.size
    except Exception:
        return 0, 0


def _resolve(text, index):
    if not text:
        return None, 0.0
    canon, score, _kind = index.lookup(text)
    if canon:
        return canon, score
    try:
        from app.services.alias_service import canonical
        c = canonical(text)
        if c and c != text:
            return c, 0.9
    except Exception:
        pass
    return None, 0.0


def self_check():
    cases = []

    def add(name, fn, want):
        try:
            got = fn()
        except Exception as e:
            got = "EXC:%s" % str(e)[:60]
        cases.append((name, want, got))

    add("_n(CCTV4K)", lambda: _n("CCTV4K"), "cctv4k")
    add("_n(CCTV4K超高清)", lambda: _n("CCTV4K超高清"), "cctv4k")
    add("_n(央视4K)", lambda: _n("央视4K"), "央视4k")
    add("_n(湖南卫视高清)", lambda: _n("湖南卫视高清"), "湖南卫视")
    add("_n(浙江卫视1080p)", lambda: _n("浙江卫视1080p"), "浙江卫视")
    add("_sig(CCTV5)!=_sig(CCTV5+)", lambda: _sig("CCTV5") != _sig("CCTV5+"), True)
    add("_split_idx(内蒙古卫视 #3)", lambda: _split_idx("内蒙古卫视 #3"),
        ("内蒙古卫视", "#3"))
    add("_zone 左上角", lambda: _zone(30, 100, 960, 540), ("top", 1.0))
    add("_zone 右上角不判定", lambda: _zone(30, 800, 960, 540), ("topright", 0.0))
    add("_zone 底部", lambda: _zone(500, 400, 960, 540), ("bot", 0.85))
    add("_is_ad_noise(咪咕视频)", lambda: _is_ad_noise("咪咕视频"), True)
    add("_is_ad_noise(集成播控)", lambda: _is_ad_noise("集成播控"), True)
    add("_is_ad_noise(辽宁卫视)", lambda: _is_ad_noise("辽宁卫视"), False)
    add("_is_ad_noise(折电视)=短中文豁免", lambda: _is_ad_noise("折电视"), False)
    add("_is_ad_noise(限时抢购)=真广告", lambda: _is_ad_noise("限时抢购"), True)

    return {"total": len(cases),
            "passed": sum(1 for _n_, w, g in cases if w == g),
            "failed": [{"case": n, "want": w, "got": g} for n, w, g in cases if w != g]}


def resolve_check(alias_map, pool_names=None):
    idx = NameIndex(pool_names or [], alias_map or {})
    cases = [
        ("裸 CCTV. 不表态", idx.lookup("CCTV.")[0], None),
        ("裸 CCTV 不表态", idx.lookup("CCTV")[0], None),
        ("裸 央视 不表态", idx.lookup("央视")[0], None),
        ("CCTV4K 仍可判", idx.lookup("CCTV4K")[0], "CCTV4K"),
        ("CCTV15 仍可判", idx.lookup("CCTV15")[0], "CCTV15"),
        ("CCTV5 仍可判", idx.lookup("CCTV5")[0], "CCTV5"),
        ("湖南卫视高清→湖南卫视", idx.lookup("湖南卫视高清")[0], "湖南卫视"),
        ("民视→民视无线台", idx.lookup("民视")[0], "民视无线台"),
    ]
    return {"total": len(cases),
            "passed": sum(1 for _n_, w, g in cases if w == g),
            "failed": [{"case": n, "want": w, "got": g} for n, w, g in cases if w != g]}


_service = None
_service_lock = threading.Lock()


def get_service():
    global _service
    if _service is None:
        with _service_lock:
            if _service is None:
                try:
                    from app.database import DATA_DIR
                    dd = DATA_DIR
                except Exception:
                    dd = os.getcwd()
                _service = NamefixService(data_dir=dd)
    return _service
