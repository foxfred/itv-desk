from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel

router = APIRouter(prefix="/api/subscriptions", tags=["subscriptions"])


class SubAddReq(BaseModel):
    url: str
    name: str = ""
    suffix_list: str = "m3u,m3u8,txt"
    proxy: str = ""
    mirror: str = "不使用加速"
    enabled: bool = True


class SubToggleReq(BaseModel):
    url: str
    enabled: bool = True


class SubUpdateOneReq(BaseModel):
    url: str


def get_subscription_service():
    from app.main import subscription_service
    return subscription_service


@router.get("")
def list_subs(sub_service=Depends(get_subscription_service)):
    return sub_service.list()


@router.post("")
def add_sub(body: SubAddReq, sub_service=Depends(get_subscription_service)):
    return sub_service.add(body.url, body.name, body.suffix_list, body.proxy, body.mirror, body.enabled)


@router.delete("")
def remove_sub(url: str = Query(...), sub_service=Depends(get_subscription_service)):
    return sub_service.remove(url)


@router.post("/toggle")
def toggle_sub(body: SubToggleReq, sub_service=Depends(get_subscription_service)):
    return sub_service.set_enabled(body.url, body.enabled)


@router.post("/update")
def update_all(sub_service=Depends(get_subscription_service)):
    return sub_service.update_all()


@router.post("/update-one")
def update_one(body: SubUpdateOneReq, sub_service=Depends(get_subscription_service)):
    return sub_service.update_one(body.url)
