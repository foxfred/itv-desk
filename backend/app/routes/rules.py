"""规则管理路由"""
from fastapi import APIRouter, Depends
from pydantic import BaseModel
from typing import Optional

router = APIRouter(prefix="/api/rules", tags=["rules"])


class RuleReq(BaseModel):
    frm: str
    to: str
    mode: str = "包含"
    index: Optional[int] = None


def get_rule_service():
    from app.main import rule_service
    return rule_service


def get_channel_service():
    from app.main import channel_service
    return channel_service


@router.get("")
def get_rules(rule_service=Depends(get_rule_service)):
    return rule_service.get_rules()


@router.post("")
def save_rule(body: RuleReq, rule_service=Depends(get_rule_service)):
    return {"ok": True, "rules": rule_service.save_rule(body.frm, body.to, body.mode, body.index)}


@router.delete("/{index}")
def delete_rule(index: int, rule_service=Depends(get_rule_service)):
    return {"ok": True, "rules": rule_service.delete_rule(index)}


@router.post("/apply")
def apply_rules(rule_service=Depends(get_rule_service),
                channel_service=Depends(get_channel_service)):
    return rule_service.apply_rules(channel_service)


@router.post("/preview")
def preview_rules(rule_service=Depends(get_rule_service),
                  channel_service=Depends(get_channel_service)):
    return rule_service.preview_rules(channel_service)