import json
import re

import requests

DEFAULT_BASE = "https://api.deepseek.com/v1"
DEFAULT_MODEL = "deepseek-chat"

_GROUP_SYSTEM = (
    "你是中文电视直播频道的分类助手。请把给定的频道名分配到合适的分组。"
    "优先复用已有分组名；无法归类时归入「其他」。"
    "只输出一个 JSON 对象，键是频道名，值是分组名，不要输出任何解释文字。"
)


def _norm_base(base):
    b = str(base or "").strip().rstrip("/")
    return b or DEFAULT_BASE


def _pick(data, key, default):
    v = data.get(key)
    return default if v is None or v == "" else v


class AIService:
    """OpenAI-compatible client for grouping and other assisted features."""

    def __init__(self, log_callback=None, settings_provider=None):
        self.log = log_callback or (lambda m: None)
        self.settings_provider = settings_provider or (lambda: {})

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
            "use_proxy": bool(s.get("ai_use_proxy")),
            "proxy": str(s.get("proxy") or "").strip(),
            "extra": str(s.get("ai_prompt_extra") or "").strip(),
        }

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
        if c.get("use_proxy") and c.get("proxy"):
            p = c["proxy"]
            url = p if "://" in p else "http://" + p
            return {"http": url, "https": url}
        return {}

    def _session(self, c):
        """trust_env=False unless the user explicitly opted into a proxy."""
        s = requests.Session()
        s.trust_env = False
        s.proxies = self._proxies(c)
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

    def chat(self, messages, base_url=None, api_key=None, model=None,
             temperature=None, max_tokens=None, json_mode=False):
        c = self.resolve(base_url, api_key, model)
        if not c["key"]:
            return {"ok": False, "error": "未配置 API Key（设置 → AI 智能）"}
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
            return {"ok": False, "error": "HTTP %d：%s" % (r.status_code, (r.text or "")[:300]), "url": url}
        try:
            data = r.json()
        except Exception:
            return {"ok": False, "error": "接口返回的不是 JSON", "url": url}
        try:
            content = data["choices"][0]["message"]["content"]
        except Exception:
            return {"ok": False, "error": "返回结构异常：%s" % json.dumps(data, ensure_ascii=False)[:220]}
        usage = data.get("usage") or {}
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
