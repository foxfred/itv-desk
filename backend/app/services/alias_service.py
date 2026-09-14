"""频道别名库（P1-9）

解决的问题：同一个频道在中文源里有无数种写法，导致节目单匹配不上
（源里叫「央视五套」，EPG 里叫「CCTV5」）。

别名库把各种写法归一到「规范名」，格式 {规范名: [别名, ...]}，
落盘 DATA_DIR/channel_alias.json。

使用范围：**仅用于 EPG 匹配**（只读匹配，匹配不上最多就是匹配不上，零副作用）。
频道去重路径刻意不带别名——别名一旦判错，去重会真的删掉频道，属不可逆操作，
不值得冒这个险。

种子数据为自研整理（央视全部频道 + 省级卫视 + 省级地面/少儿/教育 + 中国港澳台主要频道），
未引用任何竞品的数据文件——license 红线见 方案书-功能加强规划.md 第三节。
"""
import os
import re
import json
import threading

# 规范名 → 别名列表。规范名本身用官方叫法（CCTV1 而不是"央视一套"）。
# 只收无歧义的：像"广东电视台"这种一个台有好几个频道的写法一律不收，避免误合并。
SEED = {
    "CCTV1": ["央视一套", "央视综合", "中央一台", "中央1台", "央视1套", "CCTV1综合"],
    "CCTV2": ["央视二套", "央视财经", "中央二台", "中央2台", "央视2套"],
    "CCTV3": ["央视三套", "央视综艺", "中央三台", "中央3台", "央视3套"],
    "CCTV4": ["央视四套", "央视中文国际", "中央四台", "中央4台", "CCTV4中文国际", "央视4套"],
    "CCTV5": ["央视五套", "央视体育", "中央五台", "中央5台", "CCTV5体育", "央视5套"],
    "CCTV5+": ["央视体育赛事", "CCTV5加", "CCTV5PLUS", "央5加", "央视五套加", "CCTV5+体育赛事"],
    "CCTV6": ["央视六套", "央视电影", "中央六台", "中央6台", "央视6套", "电影频道"],
    "CCTV7": ["央视七套", "央视国防军事", "中央七台", "中央7台", "央视7套"],
    "CCTV8": ["央视八套", "央视电视剧", "中央八台", "中央8台", "央视8套"],
    "CCTV9": ["央视九套", "央视纪录", "中央九台", "中央9台", "CCTV9纪录", "央视9套"],
    "CCTV10": ["央视十套", "央视科教", "中央十台", "中央10台", "央视10套"],
    "CCTV11": ["央视十一套", "央视戏曲", "中央十一台", "中央11台", "央视11套"],
    "CCTV12": ["央视十二套", "央视社会与法", "中央十二台", "中央12台", "央视12套"],
    "CCTV13": ["央视十三套", "央视新闻", "中央十三台", "中央13台", "CCTV新闻", "央视13套"],
    "CCTV14": ["央视十四套", "央视少儿", "中央十四台", "中央14台", "央视14套"],
    "CCTV15": ["央视十五套", "央视音乐", "中央十五台", "中央15台", "央视15套"],
    "CCTV16": ["央视十六套", "央视奥林匹克", "中央十六台", "中央16台", "CCTV16奥林匹克"],
    "CCTV17": ["央视十七套", "央视农业农村", "中央十七台", "中央17台", "央视17套"],
    "CGTN": ["中国国际电视台", "央视英语频道", "CCTV英语新闻"],
    # ⚠️ 「央视超高清」这个别名已删除（2026-09-14）：归一化会把画质词「超高清」剥掉，
    #    它退化成裸「央视」——而「央视」是央视所有频道的通称，会让任何画面里的
    #    「央视」水印精确命中 CCTV4K。改用不会退化的「央视4K超高清」。
    "CCTV4K": ["央视4K", "CCTV4K超高清", "央视4K超高清"],
    "北京卫视": ["BTV北京", "北京电视台", "北京卫视高清"],
    "天津卫视": ["天津电视台"],
    "河北卫视": ["河北电视台"],
    "山西卫视": ["山西电视台"],
    "内蒙古卫视": ["内蒙古电视台", "内蒙卫视"],
    "辽宁卫视": ["辽宁电视台"],
    "吉林卫视": ["吉林电视台"],
    "黑龙江卫视": ["黑龙江电视台", "龙江卫视"],
    "东方卫视": ["上海卫视", "上海东方卫视", "番茄台"],
    "江苏卫视": ["荔枝台", "江苏电视台"],
    "浙江卫视": ["蓝莓台", "浙江电视台"],
    "安徽卫视": ["海豚台", "安徽电视台"],
    "东南卫视": ["福建东南卫视", "福建卫视"],
    "江西卫视": ["江西电视台"],
    "山东卫视": ["山东电视台"],
    "河南卫视": ["河南电视台"],
    "湖北卫视": ["湖北电视台"],
    "湖南卫视": ["芒果台", "湖南电视台"],
    "广东卫视": ["广东电视台"],
    "广西卫视": ["广西电视台"],
    "海南卫视": ["旅游卫视", "海南电视台"],
    "重庆卫视": ["重庆电视台"],
    "四川卫视": ["四川电视台"],
    "贵州卫视": ["贵州电视台"],
    "云南卫视": ["云南电视台"],
    "西藏卫视": ["西藏电视台"],
    "陕西卫视": ["陕西电视台"],
    "甘肃卫视": ["甘肃电视台"],
    "青海卫视": ["青海电视台"],
    "宁夏卫视": ["宁夏电视台"],
    "新疆卫视": ["新疆电视台"],
    "深圳卫视": ["深圳电视台"],
    "厦门卫视": ["厦门电视台"],
    "兵团卫视": ["新疆兵团卫视"],
    "延边卫视": ["延边电视台"],
    "三沙卫视": ["三沙电视台"],
    "南方卫视": ["广东南方卫视"],
    "金鹰卡通": ["湖南金鹰卡通", "金鹰卡通卫视"],
    "卡酷少儿": ["北京卡酷", "卡酷卡通", "BTV卡酷少儿"],
    "嘉佳卡通": ["广东嘉佳卡通"],
    "优漫卡通": ["江苏优漫卡通", "优漫卡通卫视"],
    "哈哈炫动": ["上海哈哈炫动", "炫动卡通"],
    "山东教育卫视": ["山东教育台"],
    "中国教育一台": ["CETV1", "中国教育电视台一套"],
    "中国教育二台": ["CETV2", "中国教育电视台二套"],
    "中国教育三台": ["CETV3", "中国教育电视台三套"],
    "中国教育四台": ["CETV4", "中国教育电视台四套"],
    "翡翠台": ["TVB翡翠台", "无线翡翠台", "香港翡翠台"],
    "明珠台": ["TVB明珠台", "无线明珠台", "香港明珠台", "Pearl"],
    "无线新闻台": ["TVB无线新闻台", "互动新闻台", "无线互动新闻台"],
    "无线财经资讯台": ["TVB财经资讯台", "无线财经台"],
    "无线星河": ["TVB星河频道", "星河频道"],
    "香港开电视": ["奇妙电视", "HOYTV", "香港开电视77台"],
    "ViuTV": ["ViuTV99", "香港ViuTV"],
    "港台电视31": ["RTHK31", "香港电台31"],
    "港台电视32": ["RTHK32", "香港电台32"],
    "凤凰卫视中文台": ["凤凰中文台", "凤凰卫视"],
    "凤凰卫视资讯台": ["凤凰资讯台"],
    "凤凰卫视香港台": ["凤凰香港台"],
    "澳视澳门": ["澳门电视台", "澳门卫视", "TDM澳门"],
    "澳视高清": ["澳门高清", "TDM高清"],
    "澳门莲花卫视": ["莲花卫视"],
    "中天新闻": ["中天新聞", "中天新闻台"],
    "中天综合": ["中天综合台"],
    "中天娱乐": ["中天娱乐台"],
    "东森新闻": ["東森新聞", "东森新闻台"],
    "东森财经新闻": ["東森財經新聞", "东森财经台"],
    "三立新闻": ["三立新聞", "三立新闻台"],
    "三立台湾台": ["三立台灣台"],
    "民视新闻台": ["民視新聞台", "民视新闻"],
    "民视无线台": ["民視無線台", "民视"],
    "台视": ["TTV", "台湾电视", "台視"],
    "中视": ["CTV", "中国电视", "中視"],
    "华视": ["CTS", "中华电视", "華視"],
    "公视": ["PTS", "公共电视", "公視"],
    "TVBS新闻": ["TVBS新聞", "TVBS新闻台"],
    "年代新闻": ["年代新聞"],
    "非凡新闻": ["非凡新聞"],
    "八大第一台": ["八大第一"],
    "纬来体育": ["緯來體育", "纬来体育台"],
    "纬来育乐": ["緯來育樂", "纬来育乐台"],
    "纬来日本": ["緯來日本", "纬来日本台"],
    "纬来戏剧": ["緯來戲劇", "纬来戏剧台"],
    "纬来电影": ["緯來電影", "纬来电影台"],
    "龙祥电影": ["龍祥電影", "龙祥电影台"],
    "好消息卫视": ["好消息電視台"],
    "大爱一台": ["大愛一台", "大爱电视台"],
    "人间卫视": ["人間衛視"],
    "寰宇新闻": ["寰宇新聞", "寰宇新闻台"],
    "亚洲新闻台": ["CNA", "ChannelNewsAsia"],
}

_STRIP = re.compile(r"[\s\-_\.·]+")


def _key(name):
    """归一化键：去符号 + 转小写（与 epg_service._normalize_name 保持一致）"""
    if not name:
        return ""
    return _STRIP.sub("", str(name).lower())


class AliasService:
    """别名库读写 + 规范化查询"""

    def __init__(self, data_dir=None, log_callback=None):
        self.data_dir = data_dir or os.getcwd()
        self.path = os.path.join(self.data_dir, "channel_alias.json")
        self.log = log_callback or (lambda m: None)
        self._lock = threading.RLock()
        self.map = {}          # {规范名: [别名...]}
        self._index = {}       # {归一化别名/规范名: 规范名}
        self._load()
        self._rebuild()

    # -------------------- 持久化 --------------------
    def _load(self):
        if not os.path.exists(self.path):
            self.map = {k: list(v) for k, v in SEED.items()}
            self._save()
            return
        try:
            with open(self.path, "r", encoding="utf-8") as f:
                data = json.load(f)
            if isinstance(data, dict) and data:
                self.map = {str(k): [str(x) for x in (v or [])] for k, v in data.items()}
                return
        except Exception as e:
            self.log(f"别名库读取失败，回退种子数据：{e}")
        self.map = {k: list(v) for k, v in SEED.items()}

    def _save(self):
        try:
            tmp = self.path + ".tmp"
            with open(tmp, "w", encoding="utf-8") as f:
                json.dump(self.map, f, ensure_ascii=False, indent=1, sort_keys=True)
            os.replace(tmp, self.path)
        except Exception as e:
            self.log(f"别名库保存失败：{e}")

    def _rebuild(self):
        idx = {}
        for canon, aliases in self.map.items():
            idx[_key(canon)] = canon
            for a in aliases:
                k = _key(a)
                if k:
                    idx[k] = canon
        self._index = idx

    # -------------------- 查询 --------------------
    def canonical(self, name):
        """把任意写法归一为规范名；不在库里则原样返回"""
        if not name:
            return name
        return self._index.get(_key(name), name)

    def count(self):
        return {"groups": len(self.map),
                "aliases": sum(len(v) for v in self.map.values())}

    def all(self):
        return {k: list(v) for k, v in sorted(self.map.items())}

    # -------------------- 维护 --------------------
    def set_group(self, canon, aliases):
        """新增/覆盖一个规范名及其别名"""
        canon = (canon or "").strip()
        if not canon:
            return {"ok": False, "error": "规范名不能为空"}
        with self._lock:
            self.map[canon] = [str(a).strip() for a in (aliases or []) if str(a).strip()]
            self._rebuild()
            self._save()
        return {"ok": True, **self.count()}

    def remove_group(self, canon):
        with self._lock:
            if canon in self.map:
                self.map.pop(canon)
                self._rebuild()
                self._save()
                return {"ok": True, **self.count()}
        return {"ok": False, "error": "没有这个规范名"}

    def import_text(self, text, replace=False):
        """导入文本格式，每行一条：`规范名=别名1,别名2`（也支持 `=` 写成 `:`）。

        只做增量合并（replace=True 才整体替换），导入后立刻持久化。
        """
        parsed, errors = {}, []
        for i, raw in enumerate(str(text or "").splitlines(), 1):
            line = raw.strip()
            if not line or line.startswith("#"):
                continue
            sep = "=" if "=" in line else (":" if ":" in line else None)
            if not sep:
                errors.append(f"第{i}行缺少分隔符（应为 规范名=别名1,别名2）")
                continue
            canon, _, rest = line.partition(sep)
            canon = canon.strip()
            if not canon:
                errors.append(f"第{i}行规范名为空")
                continue
            aliases = [x.strip() for x in re.split(r"[,，、|]", rest) if x.strip()]
            parsed.setdefault(canon, [])
            for a in aliases:
                if a not in parsed[canon]:
                    parsed[canon].append(a)
        if not parsed and not replace:
            return {"ok": False, "error": "没有解析到有效条目", "errors": errors}
        with self._lock:
            if replace:
                self.map = parsed
            else:
                for canon, aliases in parsed.items():
                    cur = self.map.setdefault(canon, [])
                    for a in aliases:
                        if a not in cur:
                            cur.append(a)
            self._rebuild()
            self._save()
        return {"ok": True, "imported": len(parsed), "errors": errors, **self.count()}

    def reset_seed(self):
        with self._lock:
            self.map = {k: list(v) for k, v in SEED.items()}
            self._rebuild()
            self._save()
        return {"ok": True, **self.count()}


# ==================== 模块级单例（供 epg_service / channel_service 直接调用） ====================
_service = None
_service_lock = threading.Lock()


def _default_data_dir():
    if os.environ.get("ITV_DATA_DIR"):
        return os.path.abspath(os.environ["ITV_DATA_DIR"])
    try:
        from app.database import DATA_DIR
        return DATA_DIR
    except Exception:
        return os.getcwd()


def get_service():
    global _service
    if _service is None:
        with _service_lock:
            if _service is None:
                _service = AliasService(data_dir=_default_data_dir())
    return _service


def canonical(name):
    """便捷入口：把频道名归一成规范名（未收录则原样返回）"""
    try:
        return get_service().canonical(name)
    except Exception:
        return name
