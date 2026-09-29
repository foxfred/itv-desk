import base64
import hashlib
import json
import os
import re
import time

import requests

DEFAULT_BASE = "https://api.deepseek.com/v1"
DEFAULT_MODEL = "deepseek-chat"

_GROUP_SYSTEM = (
    "你是中文电视直播频道的分类助手。请把给定的频道名分配到合适的分组。"
    "优先复用已有分组名；无法归类时归入「其他」。"
    "只输出一个 JSON 对象，键是频道名，值是分组名，不要输出任何解释文字。"
)

_NAMEFIX_SYSTEM = (
    "你是中文电视直播频道名的清洗助手。把给定的频道名清洗成规范台名。规则："
    "①繁体转简体；②去掉清晰度/画质/线路后缀（如 高清、超清、标清、蓝光、4K、1080P、线路1、无插件）；"
    "③去掉广告引流词（如 官网、APP、下载、关注、抢红包）；④去掉频道名里夹带的网址；"
    "⑤统一台名写法（如 央视频道用 CCTV+数字，如 CCTV-5 写成 CCTV5）；"
    "⑥频道序号和加号必须保留：CCTV5+ 不能变成 CCTV5，CCTV5 不能变成 CCTV5+；"
    "⑦无法判断的不要输出。"
    "只输出一个 JSON 对象，键是原名，值是清洗后的台名；只输出有变化的条目，没有可清洗的就输出空对象 {}，不要输出任何解释文字。"
)

_TAG_SYSTEM = (
    "你是中文电视直播频道的打标助手。给每个频道名打上内容标签，标签只能从这个集合里选："
    "购物、测试卡、轮播、成人、宗教、体育、新闻、影视、少儿、音乐、纪录、地方、港澳台、正常。"
    "判断依据是频道名本身（含台名、栏目词、广告词）；无法判断时给「正常」。"
    "只输出一个 JSON 对象，键是频道名，值是标签数组（如 [\"购物\"]），不要输出任何解释文字。"
)

_SEARCH_SYSTEM = (
    "你是中文电视直播频道的搜索助手。用户给一个搜索词和一份频道名清单，"
    "请判断哪些频道名与搜索词相关（含别名、简称、同义词、台网对应关系，例如「中央一台」对应「CCTV1 综合」「央视一套」，"
    "「凤凰」对应「凤凰卫视中文台」）。"
    "只输出一个 JSON 对象，键是 matched（相关频道名数组，按相关度从高到低）、keywords（建议扩展出的关键词数组）。"
    "没有相关频道时 matched 为空数组。不要输出任何解释文字。"
)

_VERIFY_SYSTEM = (
    "你是电视直播源核验助手。你会看到某频道的截图，请判断画面内容是否与该频道名相符。"
    "若画面是台标/演播室/节目画面且与频道定位一致，判 yes；"
    "若是完全无关的内容（如挂羊头卖狗肉、购物广告冒充新闻台、测试卡）判 no；"
    "信息不足判 unsure。只输出 JSON：{\"verdict\":\"yes|no|unsure\",\"reason\":\"不超过30字的理由\"}，不要输出其它文字。"
)

_RANK_SYSTEM = (
    "你是直播源稳定性评估助手。给你一个频道名和它的多个源（含协议、分辨率、延迟、历史成功/失败次数），"
    "请按「最可能稳定可用」排序，并给每个源一句不超过20字的理由。"
    "只输出 JSON：{\"order\":[源地址数组，按推荐顺序],\"reason\":{\"源地址\":\"理由\"}}，不要输出其它文字。"
)

_DIAG_SYSTEM = (
    "你是直播播放故障诊断助手。用户会给你一段软件日志与检测信息，"
    "请判断最可能的故障原因（网络/源失效/编码不支持/代理/进程/配置），并给出可执行的处理建议（中文，2~3 条）。"
    "只输出 JSON：{\"cause\":\"原因分类\",\"detail\":\"不超过80字的说明\",\"suggestions\":[\"建议1\",\"建议2\"]}，不要输出其它文字。"
)

_EPG_SYSTEM = (
    "你是中文电视 EPG（节目单）助手。给一份频道名清单，判断每个频道该用哪类 EPG 源"
    "（取值：央视/卫视/地方/港澳台/无），并给出可用于检索的关键词。"
    "只输出 JSON：{\"频道名\":{\"type\":\"卫视\",\"keyword\":\"湖南卫视\"}}，不要输出其它文字。"
)

_EPG_SUM_SYSTEM = (
    "你是节目单摘要助手。给一份某频道当天节目列表，输出一段不超过120字的中文摘要，"
    "点出重点节目与类型分布。只输出 JSON：{\"summary\":\"...\"}，不要输出其它文字。"
)

_NL_SYSTEM = (
    "你是操作意图解析助手。把用户的中文指令解析成对下述接口的调用计划（只做解析，不执行）。"
    "可用接口：GET /api/channels（查频道）、POST /api/channels/check（检测）、POST /api/channels/merge-duplicates（去重）、"
    "POST /api/channels/reclassify（重新分组）、POST /api/channels/match-logos（匹配台标）、"
    "POST /api/ai/group（AI 分组）、POST /api/ai/namefix（AI 清洗）、POST /api/ai/tags（AI 打标）、"
    "POST /api/export（导出）、POST /api/subscriptions/update（更新订阅）。"
    "只输出 JSON：{\"intent\":\"一句话意图\",\"actions\":[{\"api\":\"...\",\"method\":\"POST\",\"params\":{},\"desc\":\"说明\"}],"
    "\"reply\":\"给用户看的中文确认话术\"}。若无法映射到任何接口，actions 输出空数组并在 reply 里说明。不要输出其它文字。"
)

_GARBLED_SYSTEM = (
    "你是中文编码修复助手。给一段疑似乱码的文本，判断它原本是什么编码被错误解码导致的"
    "（如 GBK 被当 UTF-8、UTF-8 被当 GBK、Latin-1 误读），并给出正确的还原文本。"
    "只输出 JSON：{\"encoding\":\"gbk|utf-8|latin-1|unknown\",\"fixed\":\"还原后的文本\",\"confidence\":0~1}，不要输出其它文字。"
)

_SUB_AUDIT_SYSTEM = (
    "你是订阅源体检助手。给你一个 m3u 订阅源的地址、频道名样本与分组样本，"
    "请判断结构是否混乱（分组过碎/命名杂乱/含广告台/含空台/重复严重），并给出具体处理建议。"
    "只输出 JSON：{\"score\":0~100,\"issues\":[\"问题1\"],\"suggestions\":[\"建议1\"]}，不要输出其它文字。"
)

_WALL_SYSTEM = (
    "你是频道墙排布助手。给你一批频道（含收藏标记、播放次数、延迟、分辨率、分组），"
    "请给出最适合上墙的顺序（最常看/最稳的靠前）。只输出 JSON：{\"order\":[\"频道名数组\"],\"reason\":\"不超过50字\"}，不要输出其它文字。"
)

_EXPORT_SYSTEM = (
    "你是 IPTV 播放列表整理助手。给一份分组与频道名清单，为每个分组写一句不超过30字的中文说明（描述该组内容特点）。"
    "只输出 JSON：{\"分组名\":\"说明\"}，不要输出其它文字。"
)


def _norm_base(base):
    b = str(base or "").strip().rstrip("/")
    # 容错：用户经常把 base_url 填成完整 chat 路径（".../v1/chat/completions"），
    # 服务会自动再拼 /chat/completions，导致 ".../chat/completions/chat/completions" 404。
    # 自动剥掉末尾的 chat/completions（不区分大小写、有/无尾斜杠）。
    low = b.lower()
    for suf in ("/chat/completions", "/completions"):
        if low.endswith(suf):
            b = b[: -len(suf)].rstrip("/")
            break
    return b or DEFAULT_BASE


def _pick(data, key, default):
    v = data.get(key)
    return default if v is None or v == "" else v


class AIService:
    """OpenAI-compatible client for grouping and other assisted features."""

    def __init__(self, log_callback=None, settings_provider=None, data_dir=None):
        self.log = log_callback or (lambda m: None)
        self.settings_provider = settings_provider or (lambda: {})
        self.data_dir = data_dir or "."

    def cfg(self):
        s = self.settings_provider() or {}
        return {
            "enabled": bool(s.get("ai_enabled")),
            "base": _norm_base(s.get("ai_base_url")),
            "key": str(s.get("ai_api_key") or "").strip(),
            "model": str(_pick(s, "ai_model", DEFAULT_MODEL)).strip() or DEFAULT_MODEL,
            "timeout": int(_pick(s, "ai_timeout", 60)),
            "temperature": float(_pick(s, "ai_temperature", 0.2)),
            "max_tokens": int(_pick(s, "ai_max_tokens", 2048)),
            # 代理统一跟随「抓取面板」的 use_proxy 开关（2026-09-28 统一入口，原 ai_use_proxy 已废弃）
            "use_proxy": bool(s.get("use_proxy")),
            "proxy": str(s.get("proxy") or "").strip(),
            "extra": str(s.get("ai_prompt_extra") or "").strip(),
            "daily_limit": int(_pick(s, "ai_daily_token_limit", 0) or 0),
            "cache_enabled": bool(_pick(s, "ai_cache_enabled", True)),
        }

    def vision_cfg(self):
        """视觉槽位：优先 ai_vision_*，回退旧 namefix_vision_*（兼容既有配置）。"""
        s = self.settings_provider() or {}
        base = str(s.get("ai_vision_base_url") or "").strip()
        key = str(s.get("ai_vision_api_key") or "").strip()
        model = str(s.get("ai_vision_model") or "").strip()
        timeout = int(_pick(s, "ai_vision_timeout", 45) or 45)
        enabled = bool(s.get("ai_vision_enabled"))
        if not (base and key and model):
            lb = str(s.get("namefix_vision_base") or "").strip()
            lk = str(s.get("namefix_vision_key") or "").strip()
            lm = str(s.get("namefix_vision_model") or "").strip()
            if not (base or key or model):
                base, key, model = lb, lk, lm
            if not enabled:
                enabled = bool(s.get("namefix_vision_enabled"))
            if timeout in (0, 45):
                timeout = int(s.get("namefix_vision_timeout") or timeout or 45)
        c = self.cfg()
        return {"enabled": enabled, "base": _norm_base(base or c["base"]), "key": key or c["key"],
                "model": model, "timeout": timeout, "proxy": c["proxy"],
                "use_proxy": c["use_proxy"]}

    # ---------- token 用量 ----------
    @property
    def _usage_file(self):
        return os.path.join(self.data_dir, "ai_usage.json")

    def _load_usage(self):
        try:
            with open(self._usage_file, "r", encoding="utf-8") as f:
                d = json.load(f)
            return d if isinstance(d, dict) else {}
        except Exception:
            return {}

    def usage_today(self):
        d = self._load_usage()
        day = time.strftime("%Y-%m-%d")
        rec = d.get(day) or {}
        limit = self.cfg().get("daily_limit") or 0
        total = int(rec.get("total_tokens") or 0)
        return {"date": day, "requests": int(rec.get("requests") or 0),
                "prompt_tokens": int(rec.get("prompt_tokens") or 0),
                "completion_tokens": int(rec.get("completion_tokens") or 0),
                "total_tokens": total, "limit": limit,
                "remaining": max(0, limit - total) if limit else None,
                "exceeded": bool(limit and total >= limit)}

    def _add_usage(self, usage):
        if not isinstance(usage, dict):
            return
        d = self._load_usage()
        day = time.strftime("%Y-%m-%d")
        rec = d.get(day) or {}
        rec["requests"] = int(rec.get("requests") or 0) + 1
        for k in ("prompt_tokens", "completion_tokens", "total_tokens"):
            rec[k] = int(rec.get(k) or 0) + int(usage.get(k) or 0)
        d = {day: rec}
        try:
            tmp = self._usage_file + ".tmp"
            with open(tmp, "w", encoding="utf-8") as f:
                json.dump(d, f, ensure_ascii=False, indent=2)
            os.replace(tmp, self._usage_file)
        except Exception:
            pass

    # ---------- 结果缓存 ----------
    @property
    def _cache_file(self):
        return os.path.join(self.data_dir, "ai_cache.json")

    def _cache_load(self):
        try:
            with open(self._cache_file, "r", encoding="utf-8") as f:
                d = json.load(f)
            return d if isinstance(d, dict) else {}
        except Exception:
            return {}

    def _cache_save(self, d):
        try:
            tmp = self._cache_file + ".tmp"
            with open(tmp, "w", encoding="utf-8") as f:
                json.dump(d, f, ensure_ascii=False)
            os.replace(tmp, self._cache_file)
        except Exception:
            pass

    def _cache_get(self, key):
        if not self.cfg().get("cache_enabled"):
            return None
        return self._cache_load().get(key)

    def _cache_put(self, key, value):
        if not self.cfg().get("cache_enabled"):
            return
        d = self._cache_load()
        d[key] = value
        if len(d) > 5000:
            d = dict(list(d.items())[-4000:])
        self._cache_save(d)

    def cache_stats(self):
        d = self._cache_load()
        return {"entries": len(d), "enabled": bool(self.cfg().get("cache_enabled")),
                "file": os.path.basename(self._cache_file)}

    def cache_clear(self):
        self._cache_save({})
        return {"ok": True, "entries": 0}

    def resolve(self, base_url=None, api_key=None, model=None):
        c = self.cfg()
        if base_url:
            c["base"] = _norm_base(base_url)
        if api_key:
            c["key"] = str(api_key).strip()
        if model:
            c["model"] = str(model).strip()
        return c

    @staticmethod
    def _headers(key):
        h = {"Content-Type": "application/json"}
        if key:
            h["Authorization"] = "Bearer " + key
        return h

    @staticmethod
    def _proxies(c):
        # 统一走 network.resolve_proxy（2026-09-28 统一入口）：开关打开用填的地址，关闭返回 {} 走系统代理
        from app.utils.network import resolve_proxy
        p = resolve_proxy(c)
        if p:
            url = p if "://" in p else "http://" + p
            return {"http": url, "https": url}
        return {}

    def _session(self, c):
        """代理规则（2026-09-28 统一）：
        开关打开 → 走「抓取面板」里填的代理地址；
        开关关闭 → 走系统代理（HTTP_PROXY / HTTPS_PROXY 环境变量）。
        """
        s = requests.Session()
        proxies = self._proxies(c)
        s.proxies = proxies
        s.trust_env = not proxies  # 未指定代理时跟随系统环境变量
        s.headers.update(self._headers(c.get("key")))
        return s

    def list_models(self, base_url=None, api_key=None):
        c = self.resolve(base_url, api_key)
        url = c["base"].rstrip("/") + "/models"
        try:
            with self._session(c) as s:
                r = s.get(url, timeout=min(max(c["timeout"], 10), 40))
        except Exception as e:
            return {"ok": False, "error": "请求失败：%s" % str(e)[:180], "url": url}
        if r.status_code != 200:
            return {"ok": False, "error": "HTTP %d：%s" % (r.status_code, (r.text or "")[:220]), "url": url}
        try:
            data = r.json()
        except Exception:
            return {"ok": False, "error": "接口返回的不是 JSON", "url": url}
        raw = data.get("data") or data.get("models") or []
        models = []
        for m in raw:
            if isinstance(m, str):
                models.append(m)
            elif isinstance(m, dict):
                mid = m.get("id") or m.get("name") or m.get("model")
                if mid:
                    models.append(str(mid))
        models = sorted(set(models))
        if not models:
            return {"ok": False, "error": "接口未返回任何模型", "url": url}
        return {"ok": True, "models": models, "count": len(models), "url": url}

    @staticmethod
    def _looks_like_model_not_found(text):
        """各种上游对"模型不存在"的不同说法（中英文），统一识别。"""
        s = (text or "").lower()
        if any(k in s for k in ("model_not_found", "model not found",
                                "no available channel for model",
                                "the model does not exist",
                                "unknown model", "invalid model",
                                "model not support", "model not supported",
                                "model unavailable")):
            return True
        # 中文兜底（各家网关/聚合站会换说法）
        if any(k in (text or "") for k in ("没有任何已启用厂商声明模型",
                                          "模型不存在", "未知模型", "不支持的模型",
                                          "model不存在")):
            return True
        return False

    def _model_not_found_hint(self, c, err_text):
        """chat/completions 报 model_not_found 时，自动拉一次 /v1/models 列出可用模型。
        返回追加到错误消息末尾的中文提示；失败/无列表则返回空。
        """
        if not self._looks_like_model_not_found(err_text):
            return ""
        try:
            r = self.list_models(base_url=c.get("base"), api_key=c.get("key"))
        except Exception:
            return ""
        if not r.get("ok") or not r.get("models"):
            return ""
        avail = r["models"]
        show = avail[:25]
        more = "" if len(avail) <= 25 else "…（还有 %d 个未列出，请点「获取模型列表」看全部）" % (len(avail) - 25)
        return "　该端点可用模型（共 %d 个，已按字母排序，取前 25）：%s%s。请在「设置 → AI 智能」把模型名改成其中之一，或点「获取模型列表」直接选。" % (
            len(avail), "、".join(show), more)

    def chat(self, messages, base_url=None, api_key=None, model=None,
             temperature=None, max_tokens=None, json_mode=False):
        c = self.resolve(base_url, api_key, model)
        if not c["key"]:
            return {"ok": False, "error": "未配置 API Key（设置 → AI 智能）"}
        u = self.usage_today()
        if u.get("exceeded"):
            return {"ok": False, "error": "已达今日 AI token 上限（%d），可在「设置 → AI 智能」调整或清零"
                    % int(u.get("limit") or 0)}
        payload = {
            "model": c["model"],
            "messages": messages,
            "temperature": c["temperature"] if temperature is None else temperature,
            "max_tokens": c["max_tokens"] if max_tokens is None else max_tokens,
            "stream": False,
        }
        if json_mode:
            payload["response_format"] = {"type": "json_object"}
        url = c["base"].rstrip("/") + "/chat/completions"
        r = self._post(url, c, payload)
        if isinstance(r, dict):
            return r
        if json_mode and r.status_code in (400, 404, 415, 422, 500):
            payload.pop("response_format", None)
            r = self._post(url, c, payload)
            if isinstance(r, dict):
                return r
        if r.status_code != 200:
            err_text = r.text or ""
            err = "HTTP %d：%s" % (r.status_code, err_text[:300])
            err += self._model_not_found_hint(c, err_text)
            return {"ok": False, "error": err, "url": url}
        try:
            data = r.json()
        except Exception:
            return {"ok": False, "error": "接口返回的不是 JSON", "url": url}
        try:
            content = data["choices"][0]["message"]["content"]
        except Exception:
            return {"ok": False, "error": "返回结构异常：%s" % json.dumps(data, ensure_ascii=False)[:220]}
        usage = data.get("usage") or {}
        self._add_usage(usage)
        return {"ok": True, "content": content, "usage": usage, "model": payload["model"]}

    def chat_vision(self, prompt, image_paths, base_url=None, api_key=None, model=None,
                    max_tokens=None, json_mode=False):
        """多模态调用：图片以 base64 data URL 内联，走 ai_vision_* 槽位。"""
        v = self.vision_cfg()
        if base_url:
            v["base"] = _norm_base(base_url)
        if api_key:
            v["key"] = str(api_key).strip()
        if model:
            v["model"] = str(model).strip()
        if not v["key"] or not v["model"]:
            return {"ok": False, "error": "未配置视觉模型（设置 → AI 智能 → 视觉模型）"}
        u = self.usage_today()
        if u.get("exceeded"):
            return {"ok": False, "error": "已达今日 AI token 上限，可在「设置 → AI 智能」调整"}
        parts = [{"type": "text", "text": prompt}]
        for p in (image_paths or []):
            try:
                with open(p, "rb") as f:
                    b64 = base64.b64encode(f.read()).decode("ascii")
            except Exception as e:
                return {"ok": False, "error": "读取截图失败：%s" % str(e)[:120]}
            ext = os.path.splitext(p)[1].lower().lstrip(".") or "jpeg"
            if ext == "jpg":
                ext = "jpeg"
            parts.append({"type": "image_url",
                          "image_url": {"url": "data:image/%s;base64,%s" % (ext, b64)}})
        payload = {
            "model": v["model"],
            "messages": [{"role": "user", "content": parts}],
            "max_tokens": int(max_tokens or 512),
            "stream": False,
        }
        if json_mode:
            payload["response_format"] = {"type": "json_object"}
        url = v["base"].rstrip("/") + "/chat/completions"
        try:
            r = requests.post(url, headers=self._headers(v["key"]), json=payload,
                              timeout=max(int(v.get("timeout") or 45), 10),
                              proxies=self._proxies(v))
        except Exception as e:
            return {"ok": False, "error": "请求失败：%s" % str(e)[:220]}
        if r.status_code != 200:
            err_text = r.text or ""
            err = "HTTP %d：%s" % (r.status_code, err_text[:300])
            err += self._model_not_found_hint(v, err_text)
            return {"ok": False, "error": err}
        try:
            data = r.json()
            content = data["choices"][0]["message"]["content"]
        except Exception:
            return {"ok": False, "error": "返回结构异常"}
        usage = data.get("usage") or {}
        self._add_usage(usage)
        return {"ok": True, "content": content, "usage": usage, "model": payload["model"]}

    def _post(self, url, c, payload):
        """POST /chat/completions; returns Response or an error dict."""
        try:
            return requests.post(url, headers=self._headers(c["key"]), json=payload,
                                 timeout=max(c["timeout"], 10), proxies=self._proxies(c))
        except Exception as e:
            return {"ok": False, "error": "请求失败：%s" % str(e)[:220], "url": url}

    def test(self, base_url=None, api_key=None, model=None):
        r = self.chat([{"role": "user", "content": "只回复两个字：可用"}],
                      base_url=base_url, api_key=api_key, model=model, max_tokens=16)
        if not r.get("ok"):
            return r
        return {"ok": True, "reply": str(r.get("content") or "").strip()[:80],
                "model": r.get("model"), "usage": r.get("usage")}

    @staticmethod
    def _extract_json(text):
        t = str(text or "").strip()
        if t.startswith("```"):
            t = re.sub(r"^```[a-zA-Z]*\s*", "", t)
            t = re.sub(r"\s*```$", "", t)
        try:
            return json.loads(t)
        except Exception:
            pass
        m = re.search(r"\{[\s\S]*\}", t)
        if m:
            try:
                return json.loads(m.group(0))
            except Exception:
                pass
        return None

    def suggest_groups(self, names, existing_groups, base_url=None, api_key=None,
                       model=None, extra=""):
        names = [str(n).strip() for n in (names or []) if str(n).strip()][:400]
        if not names:
            return {"ok": False, "error": "没有可分析的频道"}
        user = "已有分组：%s\n\n待分类频道（共 %d 个）：\n%s" % (
            "、".join([str(g) for g in (existing_groups or [])][:60]) or "（无）",
            len(names), "\n".join(names))
        if extra:
            user += "\n\n额外要求：" + extra
        r = self.chat([{"role": "system", "content": _GROUP_SYSTEM},
                       {"role": "user", "content": user}],
                      base_url=base_url, api_key=api_key, model=model, json_mode=True)
        if not r.get("ok"):
            return r
        data = self._extract_json(r.get("content"))
        if not isinstance(data, dict):
            return {"ok": False, "error": "模型未返回可解析的 JSON 分组结果",
                    "preview": str(r.get("content"))[:300]}
        mapping = {}
        for k, v in data.items():
            k2 = str(k).strip()
            v2 = str(v).strip()
            if k2 and v2:
                mapping[k2] = v2
        if not mapping:
            return {"ok": False, "error": "模型返回的分组结果为空"}
        counts = {}
        for v in mapping.values():
            counts[v] = counts.get(v, 0) + 1
        return {"ok": True, "mapping": mapping, "count": len(mapping),
                "groups": counts, "model": r.get("model"), "usage": r.get("usage")}

    def suggest_namefix(self, names, base_url=None, api_key=None, model=None, extra=""):
        names = [str(n).strip() for n in (names or []) if str(n).strip()][:400]
        if not names:
            return {"ok": False, "error": "没有可分析的频道"}
        user = "待清洗频道名（共 %d 个）：\n%s" % (len(names), "\n".join(names))
        if extra:
            user += "\n\n额外要求：" + extra
        r = self.chat([{"role": "system", "content": _NAMEFIX_SYSTEM},
                       {"role": "user", "content": user}],
                      base_url=base_url, api_key=api_key, model=model, json_mode=True)
        if not r.get("ok"):
            return r
        data = self._extract_json(r.get("content"))
        if not isinstance(data, dict):
            return {"ok": False, "error": "模型未返回可解析的 JSON 清洗结果",
                    "preview": str(r.get("content"))[:300]}
        mapping = {}
        for k, v in data.items():
            k2 = str(k).strip()
            v2 = str(v).strip()
            if k2 and v2 and k2 != v2:
                if k2.replace("+", "").replace("加", "") == v2.replace("+", "").replace("加", ""):
                    continue
                mapping[k2] = v2
        if not mapping:
            return {"ok": True, "mapping": {}, "count": 0,
                    "msg": "模型认为这些频道名都不需要清洗",
                    "model": r.get("model"), "usage": r.get("usage")}
        return {"ok": True, "mapping": mapping, "count": len(mapping),
                "model": r.get("model"), "usage": r.get("usage")}

    # ---------- 通用 JSON 任务通道（统一缓存 + 用量） ----------
    def _json_task(self, kind, system, user, cache_payload=None, max_tokens=None,
                   vision_images=None, extra="", expect="dict"):
        ck = None
        if cache_payload is not None and self.cfg().get("cache_enabled"):
            raw = json.dumps(cache_payload, ensure_ascii=False, sort_keys=True)
            ck = "%s:%s" % (kind, hashlib.md5(raw.encode("utf-8")).hexdigest())
            hit = self._cache_get(ck)
            if hit is not None:
                return {"ok": True, "data": hit, "cached": True}
        text = user + (("\n\n额外要求：" + extra) if extra else "")
        if vision_images:
            r = self.chat_vision(text, vision_images, max_tokens=max_tokens, json_mode=True)
        else:
            r = self.chat([{"role": "system", "content": system},
                           {"role": "user", "content": text}],
                          json_mode=True, max_tokens=max_tokens)
        if not r.get("ok"):
            return r
        data = self._extract_json(r.get("content"))
        if data is None:
            return {"ok": False, "error": "模型未返回可解析的 JSON",
                    "preview": str(r.get("content"))[:300]}
        if expect == "list" and not isinstance(data, list):
            inner = data.get("items") if isinstance(data, dict) else None
            if not isinstance(inner, list):
                return {"ok": False, "error": "模型返回结构不是列表", "preview": str(data)[:200]}
            data = inner
        if ck:
            self._cache_put(ck, data)
        return {"ok": True, "data": data, "cached": False,
                "model": r.get("model"), "usage": r.get("usage")}

    @staticmethod
    def _clean_names_in(names, limit=300):
        return [str(n).strip() for n in (names or []) if str(n).strip()][:limit]

    @staticmethod
    def _tags_of(v):
        if isinstance(v, list):
            return [str(x).strip() for x in v if str(x).strip()]
        return [t for t in re.split(r"[,，、\s]+", str(v or "")) if t]

    # ---------- #3 频道打标与自动分级 ----------
    def suggest_tags(self, names, existing_tags=None, extra=""):
        names = self._clean_names_in(names)
        if not names:
            return {"ok": False, "error": "没有可分析的频道"}
        user = "已有标签：%s\n\n待打标频道（共 %d 个）：\n%s" % (
            "、".join([str(t) for t in (existing_tags or [])][:40]) or "（无）",
            len(names), "\n".join(names))
        r = self._json_task("tags", _TAG_SYSTEM, user, cache_payload=names, extra=extra)
        if not r.get("ok"):
            return r
        data = r["data"]
        mapping = {}
        if isinstance(data, dict):
            for k, v in data.items():
                k2 = str(k).strip()
                tags = self._tags_of(v)
                if k2 and tags:
                    mapping[k2] = tags
        return {"ok": True, "mapping": mapping, "count": len(mapping), "cached": r.get("cached")}

    # ---------- #4 模糊搜索同义词扩展 ----------
    def expand_search(self, query, names, groups=None, extra=""):
        query = str(query or "").strip()
        if not query:
            return {"ok": False, "error": "搜索词为空"}
        names = self._clean_names_in(names, 500)
        if not names:
            return {"ok": False, "error": "频道库为空"}
        user = "搜索词：%s\n\n已有分组：%s\n\n频道名清单（共 %d 个）：\n%s" % (
            query, "、".join([str(g) for g in (groups or [])][:40]) or "（无）",
            len(names), "\n".join(names))
        r = self._json_task("search", _SEARCH_SYSTEM, user,
                            cache_payload=[query, names], extra=extra)
        if not r.get("ok"):
            return r
        data = r["data"] if isinstance(r["data"], dict) else {}
        matched = [str(x).strip() for x in (data.get("matched") or []) if str(x).strip()]
        kws = [str(x).strip() for x in (data.get("keywords") or []) if str(x).strip()]
        valid = set(names)
        matched = [m for m in matched if m in valid]
        return {"ok": True, "matched": matched, "count": len(matched),
                "keywords": kws, "cached": r.get("cached")}

    # ---------- #1 增强版：接 namefix 候选做裁决 ----------
    def clean_names(self, items, extra=""):
        """items: [{"name":原名, "ocr":OCR文本, "epg":EPG命中, "candidates":[候选标准名]}]"""
        items = [it for it in (items or []) if isinstance(it, dict) and str(it.get("name") or "").strip()][:60]
        if not items:
            return {"ok": False, "error": "没有可裁决的频道"}
        lines = []
        for it in items:
            parts = [str(it.get("name") or "").strip()]
            if it.get("ocr"):
                parts.append("OCR:%s" % str(it["ocr"])[:40])
            if it.get("epg"):
                parts.append("EPG:%s" % str(it["epg"])[:40])
            cand = [str(c).strip() for c in (it.get("candidates") or []) if str(c).strip()][:5]
            if cand:
                parts.append("候选:%s" % "/".join(cand))
            lines.append(" | ".join(parts))
        user = "待裁决频道（共 %d 条，格式：原名 | OCR | EPG | 候选）：\n%s" % (len(items), "\n".join(lines))
        r = self._json_task("clean", _NAMEFIX_SYSTEM, user, cache_payload=lines, extra=extra)
        if not r.get("ok"):
            return r
        data = r["data"] if isinstance(r["data"], dict) else {}
        mapping, detail = {}, {}
        for k, v in data.items():
            k2 = str(k).strip()
            if isinstance(v, dict):
                v2 = str(v.get("name") or v.get("fixed") or "").strip()
                conf = v.get("confidence")
                reason = str(v.get("reason") or "").strip()[:60]
            else:
                v2, conf, reason = str(v).strip(), None, ""
            if not k2 or not v2 or k2 == v2:
                continue
            if k2.replace("+", "").replace("加", "") == v2.replace("+", "").replace("加", ""):
                continue
            mapping[k2] = v2
            detail[k2] = {"confidence": conf, "reason": reason}
        return {"ok": True, "mapping": mapping, "detail": detail, "count": len(mapping),
                "cached": r.get("cached")}

    # ---------- #2 源真实性核验（视觉） ----------
    def verify_source(self, name, image_path, group="", extra=""):
        name = str(name or "").strip()
        if not name:
            return {"ok": False, "error": "缺少频道名"}
        if not image_path or not os.path.exists(image_path):
            return {"ok": False, "error": "该频道还没有截图，请先抓帧"}
        prompt = "频道名：%s%s\n请判断这张截图是否与该频道相符。" % (
            name, ("（分组：%s）" % group) if group else "")
        r = self._json_task("verify", _VERIFY_SYSTEM, prompt, vision_images=[image_path],
                            cache_payload=[name, os.path.basename(image_path)], extra=extra)
        if not r.get("ok"):
            return r
        data = r["data"] if isinstance(r["data"], dict) else {}
        verdict = str(data.get("verdict") or "unsure").strip().lower()
        if verdict not in ("yes", "no", "unsure"):
            verdict = "unsure"
        return {"ok": True, "verdict": verdict, "reason": str(data.get("reason") or "")[:60],
                "cached": r.get("cached")}

    # ---------- #6 多源择优排序 ----------
    def rank_sources(self, name, sources, extra=""):
        sources = [s for s in (sources or []) if isinstance(s, dict) and str(s.get("url") or "").strip()][:20]
        if not sources:
            return {"ok": False, "error": "没有可评估的源"}
        lines = []
        for s in sources:
            lines.append("%s | 协议:%s | 分辨率:%s | 延迟:%s | 成功:%s 失败:%s" % (
                str(s.get("url"))[:120], s.get("stack") or "-", s.get("res") or "-",
                s.get("ms") if s.get("ms") is not None else "-",
                s.get("ok_count", 0), s.get("fail_count", 0)))
        user = "频道名：%s\n\n候选源（共 %d 个）：\n%s" % (str(name or "").strip(), len(sources), "\n".join(lines))
        r = self._json_task("rank", _RANK_SYSTEM, user,
                            cache_payload=[name, lines], extra=extra)
        if not r.get("ok"):
            return r
        data = r["data"] if isinstance(r["data"], dict) else {}
        order = [str(x).strip() for x in (data.get("order") or []) if str(x).strip()]
        urls = [str(s.get("url")) for s in sources]
        order = [u for u in order if u in urls] + [u for u in urls if u not in order]
        return {"ok": True, "order": order,
                "reason": data.get("reason") if isinstance(data.get("reason"), dict) else {},
                "cached": r.get("cached")}

    # ---------- #9 播放故障诊断 ----------
    def diagnose_playback(self, log_tail, context=None, extra=""):
        log_tail = str(log_tail or "").strip()
        if not log_tail:
            return {"ok": False, "error": "没有可分析的日志"}
        user = "日志尾部：\n%s\n\n检测/环境信息：%s" % (
            log_tail[-6000:], json.dumps(context or {}, ensure_ascii=False)[:800])
        r = self._json_task("diag", _DIAG_SYSTEM, user, cache_payload=log_tail[-2000:], extra=extra)
        if not r.get("ok"):
            return r
        data = r["data"] if isinstance(r["data"], dict) else {}
        return {"ok": True, "cause": str(data.get("cause") or "")[:40],
                "detail": str(data.get("detail") or "")[:200],
                "suggestions": [str(x)[:120] for x in (data.get("suggestions") or [])][:5],
                "cached": r.get("cached")}

    # ---------- #10 EPG 智能补齐与摘要 ----------
    def suggest_epg_sources(self, names, extra=""):
        names = self._clean_names_in(names)
        if not names:
            return {"ok": False, "error": "没有可分析的频道"}
        user = "频道名清单（共 %d 个）：\n%s" % (len(names), "\n".join(names))
        r = self._json_task("epgsrc", _EPG_SYSTEM, user, cache_payload=names, extra=extra)
        if not r.get("ok"):
            return r
        data = r["data"] if isinstance(r["data"], dict) else {}
        out = {}
        for k, v in data.items():
            k2 = str(k).strip()
            if not k2:
                continue
            if isinstance(v, dict):
                out[k2] = {"type": str(v.get("type") or "")[:16],
                           "keyword": str(v.get("keyword") or "")[:40]}
            else:
                out[k2] = {"type": str(v)[:16], "keyword": k2}
        return {"ok": True, "mapping": out, "count": len(out), "cached": r.get("cached")}

    def summarize_epg(self, channel_name, programs, extra=""):
        progs = [str(p).strip() for p in (programs or []) if str(p).strip()][:80]
        if not progs:
            return {"ok": False, "error": "没有节目数据"}
        user = "频道：%s\n节目列表：\n%s" % (str(channel_name or "").strip(), "\n".join(progs))
        r = self._json_task("epgsum", _EPG_SUM_SYSTEM, user, cache_payload=[channel_name, progs], extra=extra)
        if not r.get("ok"):
            return r
        data = r["data"] if isinstance(r["data"], dict) else {}
        return {"ok": True, "summary": str(data.get("summary") or "")[:400], "cached": r.get("cached")}

    # ---------- #8 自然语言操作（只解析，不执行） ----------
    def nl_plan(self, text, context=None, extra=""):
        text = str(text or "").strip()
        if not text:
            return {"ok": False, "error": "指令为空"}
        user = "用户指令：%s\n\n当前上下文：%s" % (text, json.dumps(context or {}, ensure_ascii=False)[:600])
        r = self._json_task("nl", _NL_SYSTEM, user, extra=extra)
        if not r.get("ok"):
            return r
        data = r["data"] if isinstance(r["data"], dict) else {}
        actions = []
        for a in (data.get("actions") or []):
            if isinstance(a, dict) and str(a.get("api") or "").strip():
                actions.append({"api": str(a["api"]).strip(),
                                "method": str(a.get("method") or "POST").upper(),
                                "params": a.get("params") if isinstance(a.get("params"), dict) else {},
                                "desc": str(a.get("desc") or "")[:80]})
        return {"ok": True, "intent": str(data.get("intent") or "")[:80],
                "actions": actions, "reply": str(data.get("reply") or "")[:200],
                "cached": r.get("cached")}

    # ---------- #5 乱码智能还原 ----------
    def judge_garbled(self, text, extra=""):
        text = str(text or "").strip()
        if not text:
            return {"ok": False, "error": "文本为空"}
        r = self._json_task("garbled", _GARBLED_SYSTEM, "待判断文本：\n%s" % text[:2000],
                            cache_payload=text[:500], extra=extra)
        if not r.get("ok"):
            return r
        data = r["data"] if isinstance(r["data"], dict) else {}
        return {"ok": True, "encoding": str(data.get("encoding") or "unknown")[:16],
                "fixed": str(data.get("fixed") or "")[:2000],
                "confidence": data.get("confidence"), "cached": r.get("cached")}

    # ---------- #7 订阅源体检 ----------
    def audit_subscription(self, url, names, groups=None, extra=""):
        names = self._clean_names_in(names, 200)
        if not names:
            return {"ok": False, "error": "没有可分析的频道样本"}
        user = "订阅源地址：%s\n\n分组样本：%s\n\n频道名样本（共 %d 个）：\n%s" % (
            str(url or "")[:200], "、".join([str(g) for g in (groups or [])][:40]) or "（无）",
            len(names), "\n".join(names))
        r = self._json_task("subaudit", _SUB_AUDIT_SYSTEM, user,
                            cache_payload=[url, names], extra=extra)
        if not r.get("ok"):
            return r
        data = r["data"] if isinstance(r["data"], dict) else {}
        try:
            score = int(data.get("score"))
        except Exception:
            score = None
        return {"ok": True, "score": score,
                "issues": [str(x)[:120] for x in (data.get("issues") or [])][:8],
                "suggestions": [str(x)[:120] for x in (data.get("suggestions") or [])][:8],
                "cached": r.get("cached")}

    # ---------- #11 频道墙智能排布 ----------
    def suggest_wall_order(self, channels, extra=""):
        chs = [c for c in (channels or []) if isinstance(c, dict) and str(c.get("name") or "").strip()][:200]
        if not chs:
            return {"ok": False, "error": "没有可排布的频道"}
        lines = []
        for c in chs:
            lines.append("%s | 收藏:%s | 播放次数:%s | 延迟:%s | 分辨率:%s | 分组:%s" % (
                str(c.get("name"))[:60], "是" if c.get("fav") else "否",
                c.get("plays", 0), c.get("ms") if c.get("ms") is not None else "-",
                c.get("res") or "-", c.get("group") or "-"))
        user = "频道清单（共 %d 个）：\n%s" % (len(lines), "\n".join(lines))
        r = self._json_task("wall", _WALL_SYSTEM, user, cache_payload=lines, extra=extra)
        if not r.get("ok"):
            return r
        data = r["data"] if isinstance(r["data"], dict) else {}
        valid = {str(c.get("name")) for c in chs}
        order = [str(x).strip() for x in (data.get("order") or []) if str(x).strip() in valid]
        return {"ok": True, "order": order, "reason": str(data.get("reason") or "")[:120],
                "cached": r.get("cached")}

    # ---------- #12 导出描述生成 ----------
    def export_descriptions(self, groups, names_by_group=None, extra=""):
        groups = [str(g).strip() for g in (groups or []) if str(g).strip()][:60]
        if not groups:
            return {"ok": False, "error": "没有分组"}
        lines = []
        for g in groups:
            sample = [str(n)[:30] for n in ((names_by_group or {}).get(g) or [])][:12]
            lines.append("%s：%s" % (g, "、".join(sample) or "（无样本）"))
        user = "分组与样本频道：\n%s" % "\n".join(lines)
        r = self._json_task("exportdesc", _EXPORT_SYSTEM, user, cache_payload=lines, extra=extra)
        if not r.get("ok"):
            return r
        data = r["data"] if isinstance(r["data"], dict) else {}
        out = {str(k).strip(): str(v)[:80] for k, v in data.items() if str(k).strip()}
        return {"ok": True, "mapping": out, "count": len(out), "cached": r.get("cached")}
