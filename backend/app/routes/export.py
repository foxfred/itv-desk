"""导出路由"""
import os
import shutil
import subprocess
import traceback
from fastapi import APIRouter, HTTPException, Depends
from fastapi.responses import FileResponse, JSONResponse
from pydantic import BaseModel
from typing import List

router = APIRouter(prefix="/api", tags=["export"])


class ExportReq(BaseModel):
    fmt: str = "m3u"
    ids: List[int] = []


def get_export_service():
    from app.main import export_service
    return export_service


def get_channel_service():
    from app.main import channel_service
    return channel_service


def get_log():
    from app.main import log
    return log


@router.post("/export")
def export(body: ExportReq, export_service=Depends(get_export_service),
           channel_service=Depends(get_channel_service),
           log=Depends(get_log)):
    try:
        channels = channel_service.get_all()
        fpath, err_or_fname = export_service.export_channels(channels, body.fmt, body.ids)
        if not fpath:
            log(f"导出失败: {err_or_fname}")
            raise HTTPException(400 if "没有可导出" in (err_or_fname or "") else 500, err_or_fname or "导出失败")
        fname = os.path.basename(fpath)
        return FileResponse(fpath, filename=fname)
    except HTTPException:
        raise
    except Exception as e:
        log(f"导出异常: {traceback.format_exc()}")
        raise HTTPException(500, f"导出异常: {e}")


class ExportDirectReq(BaseModel):
    ids: List[int] = []
    filename: str = ""


def get_data_dir():
    from app.main import DATA_DIR
    return DATA_DIR


@router.post("/export-direct")
def export_direct(body: ExportDirectReq,
                  export_service=Depends(get_export_service),
                  channel_service=Depends(get_channel_service),
                  data_dir: str = Depends(get_data_dir),
                  log=Depends(get_log)):
    """导出到服务器根目录，不弹下载对话框"""
    try:
        channels = channel_service.get_all()
        fname = body.filename or "检查整理结果_已去重.m3u"
        fpath = os.path.join(data_dir, fname)
        if body.ids:
            idset = set(body.ids)
            channels = [ch for ch in channels if ch["id"] in idset]
        if not channels:
            return {"error": "没有可导出的频道"}
        from app.utils.m3u_parser import export_playlist
        success, err = export_playlist(channels, fpath, "m3u")
        if not success:
            return {"error": err or "导出失败"}
        log(f"已导出 {len(channels)} 个频道到 {fname}")
        return {"ok": True, "path": fpath, "count": len(channels)}
    except Exception as e:
        log(f"导出异常: {traceback.format_exc()}")
        return {"error": str(e)}


@router.get("/players")
def find_players():
    """查找 VLC 和 PotPlayer 可执行文件路径"""
    return {
        "vlc": shutil.which("vlc.exe") or _find_common("vlc", [
            r"C:\Program Files\VideoLAN\VLC\vlc.exe",
            r"C:\Program Files (x86)\VideoLAN\VLC\vlc.exe",
        ]),
        "pot": shutil.which("potplayermini.exe") or shutil.which("potplayer.exe") or _find_common("pot", [
            r"C:\Program Files\DAUM\PotPlayer\PotPlayerMini64.exe",
            r"C:\Program Files\DAUM\PotPlayer\PotPlayer.exe",
            r"C:\Program Files (x86)\DAUM\PotPlayer\PotPlayerMini64.exe",
        ]),
    }


def _find_common(name, paths):
    for p in paths:
        if os.path.isfile(p):
            return p
    return None


class PlayExternalReq(BaseModel):
    player: str
    url: str


@router.post("/play-external")
def play_external(body: PlayExternalReq):
    """调用外部播放器打开指定 URL"""
    players = find_players()
    exe = players.get(body.player)
    if not exe:
        raise HTTPException(400, f"未找到外部播放器: {body.player}，请先安装 VLC 或 PotPlayer")
    try:
        subprocess.Popen([exe, body.url], shell=False)
        return {"ok": True, "player": body.player}
    except Exception as e:
        raise HTTPException(500, f"启动播放器失败: {e}")