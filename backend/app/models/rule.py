from typing import Optional


class Rule:
    def __init__(self, frm: str = "", to: str = "", mode: str = "包含", index: Optional[int] = None):
        self.frm = frm
        self.to = to
        self.mode = mode
        self.index = index

    def to_dict(self):
        return {"from": self.frm, "to": self.to, "mode": self.mode}

    @staticmethod
    def from_dict(d: dict):
        return Rule(frm=d.get("from", ""), to=d.get("to", ""), mode=d.get("mode", "包含"))