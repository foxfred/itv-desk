"""频道名校正服务（方案书-频道名自动校正 · 阶段 B/C）

要解决的问题：源站自己乱标频道名——写着 CCTV5+ 实际播的是 CCTV1/13 或别的台。
频道名本身是被告，不能同时当判据，所以必须引入"与名字无关的真值来源"。

四层流水线：
  ① 抓帧      高分辨率（默认 960）+ 跳过首帧（默认 3 秒）——实测 320px 会把台标认成
              「民新昆台」「中天新脚」这类乱码，960px 才能读出「中天新闻」「江苏综艺」
  ② 有效性预筛  垃圾页/推广页（扫码下载 APP）、黑屏纯色帧 → 判「源异常」，不参与改名。
              实测多路「纬来体育 #3/#5/#6」抓到的是同一张扫码下载页，根本不是频道
  ③ 文本提取   本地 RapidOCR 离线识别（一次全画面，按文本框坐标分区：
              左上角台标区(top) / 中部 / 字幕区；右上角(topright) 只记录不判定
              —— 实测那里放的全是栏目品牌与平台水印，真台标都在左上角）
  ④ 名称裁决   别名库反查 + 数字对齐否决 + 模糊匹配（正向）
              字幕条节目名 → EPG 反向索引投票（反向）→ 置信度合成
              可选：视觉模型兜底（OpenAI 兼容接口，默认智谱 glm-4v-flash）

三种改名策略（设置项 namefix_strategy，用户可自选）：
  advise    只出建议表，永远人工确认（默认，最稳）
  auto_high 扫描后自动应用置信度 ≥ namefix_min_confidence 的项（可在建议表撤销）
  auto_all  扫描后自动应用所有已定名的项（激进，仍可整批撤销）

安全设计：
- 改名一律走 channel_service.update_channel，应用前自动备份 channels_cache.json；
- 每批改动写 namefix_undo.json，支持整批撤销；
- 数字序列不一致（CCTV5 vs CCTV5+）一律拒绝改名——宁可漏改，不可改错；
- 归一化只剥纯画质词，**不剥 4K/8K**（4K 是频道身份）；
- 非左上角台标区的命中置信度封顶 0.88，永不被自动应用；
- 候选不唯一时只标注不建议。
"""
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

# ==================== 文本归一化 ====================
_SP = re.compile(r"[\s\-_\.·#、，,。:：;；!！?？\"'“”‘’()（）\[\]【】《》<>/\\|]+")
# 画质/线路后缀：**只剥纯画质描述，绝不碰频道身份**。
# ⚠️ 血泪教训（2026-09-14 用户实测报错）：原正则里带 `4k|8k`，于是 `_n("CCTV4K")`
#    被归一成裸「cctv」——等于把「CCTV4K」注册成了裸「CCTV」的别名。画面里右上角
#    咪咕转播央视信号压着的平台水印「CCTV.」一读出来就精确命中 CCTV4K，
#    结果**辽宁卫视、宁夏卫视等一批带咪咕标的卫视频道全被判成 CCTV4K**。
#    4K/8K 是频道身份（CCTV4K 是独立频道，与 CCTV 不是一回事），不是画质后缀。
#    另：`超高清` 必须整体成一个备选，否则只剥掉尾巴的「高清」会留下半截「超」，
#    产生 `cctv4k超` / `央视超` 这种脏键。
_HD = re.compile(r"(超高清|超清|高清|标清|fhd|uhd|hd|蓝光|原画|流畅|无插件|线路\d*|\d{3,4}p)+$", re.I)
_NUM = re.compile(r"\d+")
# 「加号频道」标记：CCTV5+ / CCTV5PLUS / CCTV5加 是同一个台，
# 但与 CCTV5 是两个不同的台——这是本功能最关键的防误改点（用户报的错就是它）
_PLUS = re.compile(r"(plus|加|\+)$", re.I)

# 繁体→简体映射（自研整理，只收频道名高频字）
# 必要性：实测 OCR 对港澳台频道输出繁体（「中天新聞」「江蘇綜藝」「鳳凰衛視」），
# 而声道名/别名库都写简体，不做转换会整片匹配不上。
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
    # 省份/地名用字（卫视名高频，漏一个就整台匹配不上）
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
    """匹配用归一化键：繁转简 → 去符号 → 归并加号写法 → 去 HD/4K 后缀 → 小写"""
    if not s:
        return ""
    t = str(s).translate(_T2S_TABLE)
    t = _SP.sub("", t.lower())
    t = _PLUS.sub("+", t)
    t = _HD.sub("", t)
    return t.strip()


def _digits(s):
    """数字序列：CCTV5 与 CCTV5+ 的 5 相同，但与 CCTV13 不同。"""
    return tuple(_NUM.findall(str(s or "")))


def _sig(s):
    """结构签名 = (数字序列, 加号个数)。

    只比数字不够：CCTV5 与 CCTV5+ 数字相同却是两个台。
    实测自检中 'CCTV5' 曾被模糊匹配到 'CCTV5+'（相似度 0.91）——正是用户报的那类误配，
    所以模糊匹配必须要求签名完全一致。
    """
    t = _n(s)
    return tuple(_NUM.findall(t)), t.count("+")


_IDX_TAIL = re.compile(r"[\s_\-]*#\s*\d+\s*$")


def _split_idx(name):
    """拆出「一源一行」展开时自动加的行号后缀（如「内蒙古卫视 #3」）。

    为什么必须拆：
    - 行号会污染名称索引 —— 池里的名字是「中天新闻 #5」，而画面 OCR 读出的是
      「cti中天新闻」，不拆就永远匹配不上（实测 7 路中天新闻全部判为未命中）；
    - 行号会被误当成频道号 —— 「内蒙古卫视 #3」的 3 与「内蒙古卫视」数字不一致，
      于是被判成"疑似错标"，全是假警报。
    改名时行号要原样保留，否则多个源会重名。
    返回 (基名, 后缀)。
    """
    s = str(name or "")
    m = _IDX_TAIL.search(s)
    if m:
        return s[:m.start()].strip(), m.group(0).strip()
    return s.strip(), ""


# ==================== 异常/垃圾页特征 ====================
# 实测样本：盗版 APP 公告页、扫码下载引导页、商品广告
_JUNK_KW = ("打赏", "二维码", "扫码", "扫描右", "扫描下", "下载", "安装", "关注我们",
            "公众号", "加群", "客服", "订购电话", "抢购热线", "请查看网站", "版权归",
            "感谢您", "点击链接", "浏览器打开", "固件升级", "无法播放", "打不开",
            "扫码下载", "最新版", "app下载", "android", "安卓系统", "机顶盒",
            # 英文推广页（实测：多路「纬来体育」抓到同一张英文扫码下载页）
            "qr code", "qrcode", "download", "latest app", "scan the", "install our",
            "play.google", "apk", "our app")
_URL_RE = re.compile(
    r"(https?://|www\.|[a-z0-9][a-z0-9\-]{1,}\.(?:com|cn|net|tv|xyz|top|cc|me|org|io|app|vip|site|online|club|fun)(?:[/\s:]|$))",
    re.I)
# 商品/广告噪声：顶部条与中部常被这些占据，不参与频道名判定
_AD_NOISE = ("洗涤", "清潔", "清洁", "濕巾", "湿巾", "益生菌", "胶原", "膠原", "蛋白", "胜肽",
             "買", "买", "优惠", "限时", "搶購", "抢购", "赞助", "贊助", "热线", "專線", "专线",
             "工厂", "工廠", "正品", "新品", "上市", "代言", "折", "券", "订购", "訂購",
             "專輯", "专辑", "推薦", "推荐", "课程", "課程", "报名", "報名", "夏令",
             # 平台水印/角标（实测：咪咕转播的央视超高清信号会把「CCTV. 超高清 集成播控」
             # 压在画面右上角，属于播出平台的标识，跟"这一路是哪个频道"无关）。
             # 注：「米咕／米古」是 OCR 对「咪咕」的常见误读，一并拦掉。
             "咪咕", "米咕", "米古", "央视频", "集成播控", "BesTV", "百视通", "奇异果",
             "银河电视", "云视听")


def _looks_junk(text):
    """单行是否属于垃圾/推广内容"""
    t = str(text or "")
    low = t.lower()
    if any(k in low for k in _JUNK_KW):
        return True
    if _URL_RE.search(t):
        return True
    return False


# 台标特征字：短文本里带这些字的，宁可留着当"台标线索"，也不当广告丢掉
_STATION_KW = ("电视", "卫视", "頻道", "频道", "电台", "電視")


def _is_ad_noise(text):
    t = str(text or "")
    if not any(k in t for k in _AD_NOISE):
        return False
    # 带台标特征字的短文本不按广告丢弃：实测「浙江卫视」被 OCR 读成「折电视」，
    # 因命中广告词「折」被整条丢掉 → 左上角"看起来没台标" → 右上角的栏目水印
    # （中国蓝新闻）顺势赢下判定。少丢一条噪声，胜过丢一个台标。
    if len(t) <= 8 and any(k in t for k in _STATION_KW):
        return False
    return True


def _zone(y, x, w, h):
    """按文字在画面里的位置给权重。返回 (区域名, 权重)。

    实测结论（2026-09-14，150 路真实帧反查）：
    - **真台标都在左上角**：CCTV13→CCTV13、CCTV9→CCTV9（#68/#127/#128）、CCTV15 音乐、
      CCTV3 综艺、CCTV9 纪录……命中位置无一例外是 top（x≈0.12, y≈0.10）。
    - **右上角出现的全是栏目/平台角标**，不是台标：
      · 浙江卫视 / 浙江钱江都市 的右上角压着「中国蓝新闻」（浙江广电栏目品牌水印）
        → 曾把 5 路浙江频道判成"中国蓝新闻"；
      · CCTV 体育赛事源的右上角压着「CCTV5+」「CCTV16」→ 曾被判成别的 CCTV 频道。
    - 右上角唯一"命中正确"的情形是台湾频道（台视/中视/民视），但它们的结果全部是
      "同名或仅加修饰"（民视→民视无线台），没有任何一条是真正需要的修正。
    → 所以右上角**一律不参与判定**（权重 0，只记录在案、写进说明），台标以左上角为准。
    宁可漏改，不可改错。
    """
    ry = y / float(h or 1)
    rx = x / float(w or 1)
    if ry < 0.28:
        return ("top", 1.0) if rx < 0.45 else ("topright", 0.0)
    if ry > 0.72:
        return ("bot", 0.85)
    return ("mid", 0.9)


# ==================== OCR 引擎（模块级单例） ====================
_engine = None
_engine_lock = threading.Lock()
_engine_err = ""


def get_engine():
    """惰性初始化 RapidOCR。首次调用约 1-3 秒，之后复用。

    离线、免费、纯 CPU；模型随包分发（rapidocr-onnxruntime）。
    """
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
    """识别一帧，返回 [{t, s, y, x, W, H}]；失败返回 None"""
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


# ==================== 已知频道名索引 ====================
class NameIndex:
    """归一化名 → 规范名；含数字对齐否决。

    数据来源（全部自研/自建，不引用竞品数据文件）：
    - channel_alias.json 的规范名 + 别名
    - 当前频道池里出现过的名字（作为补充规范名）
    """

    def __init__(self, pool_names, alias_map):
        self.exact = {}
        self.canon_digits = {}
        for canon, al in (alias_map or {}).items():
            self._put(canon, canon)
            for a in al or []:
                self._put(a, canon)
        # 池内名字优先作为规范名（它们更贴近用户实际叫法）
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
        """返回 (规范名, 分值, 类型)；无匹配返回 (None, 0, '')

        kind: exact（完全一致）/ contain（包含）/ fuzzy（模糊）
        """
        k = _n(text)
        if len(k) < 2:
            return None, 0.0, ""
        hit = self.exact.get(k)
        if hit:
            return hit, 0.96, "exact"
        sig = _sig(k)
        # 包含匹配：OCR 常在台标文字前后多带台标缩写/水印，
        # 实测「cti中天新闻」包含已知名「中天新闻」；「CCTV4中文国际」同理。
        # 只认「候选名被完整包含」这一个方向（OCR 只读出半个名字时不做判断）。
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
            # 置信度上限压到 0.88：包含式命中不足以自动改，仍需人工确认。
            # 覆盖率越低越不可信（整句字幕里夹带台名 → 低分；短台标带缩写前缀 → 高分）
            return best_c, round(min(0.88, 0.55 + 0.33 * best_cov), 3), "contain"
        # 模糊：先过结构签名闸门（数字序列 + 加号个数都要一致），再算相似度
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


# ==================== EPG 反向索引 ====================
class EpgReverse:
    """节目名 → 频道 的反查（字幕条救星）

    实测背景：138 张"有文字但读不出台标"的样本里，字幕条给出了
    「正午江苏」「2026湖州电视」「遂昌电视台」这类节目/栏目名——
    它们能通过 EPG 当前节目反查到频道。

    实现：把每个 EPG 节目的当前标题切成 4~8 字的 shingle 建倒排，
    查询时对 OCR 文本滑窗取 shingle 投票，越长（越具体）权重越高。
    """

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
        """对一段文本投票，返回 (规范名, 权重)"""
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
            return None, 0          # 票数打平 → 不表态（宁缺勿错）
        return top[0][0], top[0][1]


# ==================== 主服务 ====================
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
        self.items = {}          # cid(str) -> 建议项
        self._load()

    # ---------------- 配置 / 依赖 ----------------
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

    # ---------------- 持久化 ----------------
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

    # ---------------- 抓帧 ----------------
    def _frame_path(self, url):
        return os.path.join(self.shot_dir, "nf_" + hashlib.md5(
            (url or "").encode("utf-8", "ignore")).hexdigest()[:16] + ".jpg")

    def _grab(self, url, out, width, offset):
        """抓一帧。返回 (ok, 说明)。

        组合重试：UA+偏移 → UA+首帧 → 无UA+偏移 → 无UA+首帧。
        实测部分协议（rtmp）不接受 -user_agent，直接报 "Option not found"；
        另一些源首帧是公告页，需要 -ss 跳过。两者都要能兜住。
        """
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
        # 这些是确定性失败（源已死/地址无效），换组合重试也是白花时间，直接放弃
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
        """取一帧：优先复用已有截图（仅当分辨率够），否则重抓"""
        # 1) 本服务自己的高清帧
        p = self._frame_path(url)
        if os.path.isfile(p) and os.path.getsize(p) > 1024:
            return p, True, "缓存帧"
        # 2) 复用截图服务产物（分辨率达标才用）
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

    # ---------------- 视觉兜底 ----------------
    def vision_ask(self, frame_path, override=None):
        """调用 OpenAI 兼容视觉接口认台标。返回 (名称, 说明)"""
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
        """连通性自测：找一张已有帧或现抓一张，返回模型回答"""
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

    # ---------------- 单频道裁决 ----------------
    def analyze_one(self, ch, index, epgrev, width, offset, reuse, use_vision):
        """对单个频道跑完整流水线，返回建议项 dict"""
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
            # 纯画面无文字 → 视觉兜底
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

        # 分区（带位置权重：左上角才是台标权威区，右上角多为平台水印）
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

        # 垃圾页判定：够多推广特征，且几乎没有有效频道文字
        useful = sum(len(v) for v in regions.values())
        if len(junk_lines) >= 3 and useful <= 2:
            rec["state"] = "junk"
            rec["note"] = "疑似推广/下载引导页，非正常频道画面（%d 条推广特征）" % len(junk_lines)
            return rec
        if len(junk_lines) >= 2 and _URL_RE.search(" ".join(junk_lines)):
            rec["state"] = "junk"
            rec["note"] = "含下载链接的推广页"
            return rec

        # 右上角角标只记录、不参与判定（实测那里放的全是栏目品牌与平台水印）
        tr_texts = [t for t, _w in regions["topright"]]
        blk_note = ""
        if tr_texts:
            blk_note = "右上角角标「%s」按栏目/平台水印处理，未采纳（台标以左上角为准）" % \
                "、".join(tr_texts[:2])

        # 名称裁决：只认左上角台标区 / 中部 / 字幕条
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
                conf += 0.01        # 左上角台标区才是权威位置
            else:
                # 中部/字幕区/右上角提到某个台名，不等于「本台就是它」（可能是栏目名、
                # 赞助、串场字幕，或右上角的平台水印），因此封顶到**自动改名门槛之下**
                # （默认门槛 0.9 → 封顶 0.88），只能作为建议等人工确认，永不被自动应用。
                conf = min(conf, 0.88)
        else:
            # 正向读不出频道名 → 字幕条节目名反查 EPG
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

        # EPG 交叉验证（第二票）
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
        # 行号后缀原样保留：改名后仍要能区分同一频道的多个源
        rec["new"] = best + (" " + cur_suffix if cur_suffix else "")
        rec["confidence"] = conf
        rec["kind"] = kind
        rec["region"] = region
        rec["note"] = epg_note
        if blk_note:
            rec["note"] = (rec["note"] + "；" if rec["note"] else "") + blk_note
        rec["detail"] = detail.get(best, [])[:4]

        # 与现名比对（用基名，行号后缀不参与比较、也不参与数字闸门）
        if _n(cur_base) == _n(best):
            rec["state"] = "consistent"
            rec["note"] = (rec["note"] + "；" if rec["note"] else "") + "与现名一致，无需改名"
            return rec
        if _digits(cur_base) and _sig(cur_base) != _sig(best):
            # 基名的频道号不同：可能是真错标，也可能是不同频道的源 → 只提示不自动
            rec["note"] = (rec["note"] + "；" if rec["note"] else "") + \
                "现名与识别名数字不一致（%s→%s），建议人工确认" % (cur_base, best)
            rec["confidence"] = round(min(conf, 0.75), 3)
        rec["state"] = "pending"
        return rec

    # ---------------- 批量扫描 ----------------
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

    # ---------------- 查询 / 应用 / 撤销 ----------------
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
        """改名前的自动备份（沿用项目 _bak_<日期>_<说明>/ 惯例）"""
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
        """应用建议：把 new 写入频道名。ids 为空时应用所有 pending。"""
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
        """撤销：不传 batch_id 则撤销最近一批"""
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


# ==================== 工具 ====================
def _img_size(path):
    try:
        from PIL import Image
        with Image.open(path) as im:
            return im.size
    except Exception:
        return 0, 0


def _resolve(text, index):
    """把任意写法解析为规范名（先用索引，再退别名库）"""
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


# ==================== 回归自检（纯文本层，不联网不抓帧） ====================
def self_check():
    """关键规则回归自检。返回 {"total", "passed", "failed": [{case, want, got}]}。

    为什么要有它：2026-09-14 用户实测报「辽宁卫视被判成 CCTV4K」，
    根因是归一化把 `4k` 当画质后缀剥掉，让裸「CCTV」精确命中 CCTV4K。
    这类回归靠肉眼看不出来，必须有断言守着。
    """
    cases = []

    def add(name, fn, want):
        try:
            got = fn()
        except Exception as e:
            got = "EXC:%s" % str(e)[:60]
        cases.append((name, want, got))

    # —— 归一化：4K/8K 是频道身份，不是画质后缀 ——
    add("_n(CCTV4K)", lambda: _n("CCTV4K"), "cctv4k")
    add("_n(CCTV4K超高清)", lambda: _n("CCTV4K超高清"), "cctv4k")
    add("_n(央视4K)", lambda: _n("央视4K"), "央视4k")
    # —— 画质后缀仍要剥掉（否则「湖南卫视高清」匹配不上「湖南卫视」）——
    add("_n(湖南卫视高清)", lambda: _n("湖南卫视高清"), "湖南卫视")
    add("_n(浙江卫视1080p)", lambda: _n("浙江卫视1080p"), "浙江卫视")
    # —— 结构签名闸门：CCTV5 与 CCTV5+ 必须不同 ——
    add("_sig(CCTV5)!=_sig(CCTV5+)", lambda: _sig("CCTV5") != _sig("CCTV5+"), True)
    # —— 行号后缀剥离 ——
    add("_split_idx(内蒙古卫视 #3)", lambda: _split_idx("内蒙古卫视 #3"),
        ("内蒙古卫视", "#3"))
    # —— 位置权重：右上角只记录不判定，台标以左上角为准 ——
    add("_zone 左上角", lambda: _zone(30, 100, 960, 540), ("top", 1.0))
    add("_zone 右上角不判定", lambda: _zone(30, 800, 960, 540), ("topright", 0.0))
    add("_zone 底部", lambda: _zone(500, 400, 960, 540), ("bot", 0.85))
    # —— 平台水印词 ——
    add("_is_ad_noise(咪咕视频)", lambda: _is_ad_noise("咪咕视频"), True)
    add("_is_ad_noise(集成播控)", lambda: _is_ad_noise("集成播控"), True)
    add("_is_ad_noise(辽宁卫视)", lambda: _is_ad_noise("辽宁卫视"), False)
    # 短中文不要被广告词吞掉（「折电视」曾因含「折」被丢，左上角就"看起来没台标"）
    add("_is_ad_noise(折电视)=短中文豁免", lambda: _is_ad_noise("折电视"), False)
    add("_is_ad_noise(限时抢购)=真广告", lambda: _is_ad_noise("限时抢购"), True)

    return {"total": len(cases),
            "passed": sum(1 for _n_, w, g in cases if w == g),
            "failed": [{"case": n, "want": w, "got": g} for n, w, g in cases if w != g]}


def resolve_check(alias_map, pool_names=None):
    """依赖别名库的自检（需传入实际别名表）。同上，供 /self-check 调用。"""
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


# ==================== 模块级单例 ====================
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
