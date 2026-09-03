"""规则服务 - 管理频道名替换规则"""
import re
import threading
from app.config import Config


class RuleService:
    """管理 channel_rules.json 的规则"""

    def __init__(self, log_callback=None):
        self.log_callback = log_callback or (lambda msg: None)
        self._rules = Config.load_json(Config.RULES_FILE, [])

    def get_rules(self):
        return self._rules

    def save_rule(self, frm, to, mode, index=None):
        rule = {"from": frm, "to": to, "mode": mode}
        if index is not None and 0 <= index < len(self._rules):
            self._rules[index] = rule
        else:
            if rule not in self._rules:
                self._rules.append(rule)
        Config.save_json(Config.RULES_FILE, self._rules)
        return self._rules

    def delete_rule(self, index):
        if 0 <= index < len(self._rules):
            del self._rules[index]
            Config.save_json(Config.RULES_FILE, self._rules)
        return self._rules

    def _apply_rules_to_name(self, name):
        result = name
        for rule in self._rules:
            frm, to, mode = rule.get("from", ""), rule.get("to", ""), rule.get("mode", "包含")
            if not frm:
                continue
            if mode == "包含":
                if frm in result:
                    result = result.replace(frm, to)
            elif mode == "正则":
                try:
                    result = re.sub(frm, to, result)
                except Exception:
                    continue
        return result

    def apply_rules(self, channel_service):
        """应用规则到频道名"""
        if not self._rules:
            return {"error": "没有规则可应用"}
        count = 0
        with channel_service.lock:
            for ch in channel_service.pool:
                old = ch.get("name", "")
                new = self._apply_rules_to_name(old)
                if new != old:
                    ch["name"] = new
                    count += 1
        self.log_callback(f"  [规则] 应用规则完成，{count} 个频道名被修改")
        return {"count": count}

    def preview_rules(self, channel_service):
        """预览规则效果"""
        results = []
        with channel_service.lock:
            names = [ch.get("name", "") for ch in channel_service.pool]
        for name in names[:20]:
            new = self._apply_rules_to_name(name)
            if new != name:
                results.append({"old": name, "new": new})
        return {"results": results}