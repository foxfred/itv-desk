"""频道别名库路由（P1-9）

别名库把同一频道的各种写法（CCTV5 / 央视五套 / 中央5台）归一到规范名，用于
EPG 匹配与（可选）去重判重。详见 services/alias_service.py。
"""
from fastapi import APIRouter, Depends
from pydantic import BaseModel

from app.services.alias_service import get_service as get_alias_service, SEED

router = APIRouter(prefix="/api/aliases", tags=["aliases"])


def get_settings():
    from app.main import settings
    return settings


class GroupReq(BaseModel):
    canon: str
    aliases: list[str] = []


class ImportReq(BaseModel):
    text: str = ""
    replace: bool = False


@router.get("")
def alias_list(settings=Depends(get_settings)):
    """别名库全量 + 统计"""
    svc = get_alias_service()
    return {
        **svc.count(),
        "map": svc.all(),
    }


@router.post("")
def alias_set(body: GroupReq):
    """新增/覆盖一个规范名及其别名"""
    return get_alias_service().set_group(body.canon, body.aliases)


@router.delete("")
def alias_remove(canon: str):
    return get_alias_service().remove_group(canon)


@router.post("/import")
def alias_import(body: ImportReq):
    """文本导入，每行一条：`规范名=别名1,别名2`

    例：CCTV5=央视体育,央视五套,中央5台
    """
    return get_alias_service().import_text(body.text, replace=body.replace)


@router.post("/reset")
def alias_reset():
    """恢复内置种子别名（会覆盖当前自定义内容）"""
    return get_alias_service().reset_seed()


@router.get("/seed")
def alias_seed():
    """内置种子别名（供前端"查看内置"用，也可复制出来改）"""
    return {k: list(v) for k, v in sorted(SEED.items())}
