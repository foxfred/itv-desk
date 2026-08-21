"""导出服务"""
import os
from app.utils.m3u_parser import export_playlist
from app.config import Config


class ExportService:
    """频道导出服务"""

    def __init__(self, settings=None, data_dir=None):
        self._settings = settings or {}
        self._data_dir = data_dir or os.getcwd()

    def export_channels(self, channels, fmt="m3u", ids=None):
        """导出频道列表到文件"""
        if ids:
            idset = set(ids)
            channels = [ch for ch in channels if ch["id"] in idset]
        if not channels:
            return None, "没有可导出的频道"
        fname = f"{self._settings.get('default_export_filename', '检查整理结果_已去重')}.{fmt}"
        fpath = os.path.join(self._data_dir, fname)
        success, err = export_playlist(channels, fpath, fmt)
        if not success:
            return None, err
        return fpath, fname