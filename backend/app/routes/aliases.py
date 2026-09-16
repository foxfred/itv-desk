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
    svc = get_alias_service()
    return {
        **svc.count(),
        "map": svc.all(),
    }


@router.post("")
def alias_set(body: GroupReq):
    return get_alias_service().set_group(body.canon, body.aliases)


@router.delete("")
def alias_remove(canon: str):
    return get_alias_service().remove_group(canon)


@router.post("/import")
def alias_import(body: ImportReq):
    return get_alias_service().import_text(body.text, replace=body.replace)


@router.post("/reset")
def alias_reset():
    return get_alias_service().reset_seed()


@router.get("/seed")
def alias_seed():
    return {k: list(v) for k, v in sorted(SEED.items())}
