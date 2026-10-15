"""数据目录解析 —— 全局唯一口径。

历史上本仓库存在三套互相矛盾的实现：

1. `app/main.py`          认 `ITV_DATA_DIR` 环境变量（正确）
2. `app/database.py`      只看 `sys.frozen`，开发态靠 dirname 反推
3. `services/channel_store.py` 四级 dirname 硬编码到仓库根，**完全不认环境变量**

后果：打包运行（Electron 传入 `ITV_DATA_DIR`）时，`ChannelStore` 仍把
`channels.db` 写到「exe 上一级」或「仓库根」，与 `main.py` 认定的
数据目录不一致 —— 表现为「设了数据目录，频道库却落在别处」，
CI 里也会往仓库根撒库文件。

本模块是唯一实现，其余各处必须调用 `resolve_data_dir()` / `resolve_res_dir()`，
禁止再自行拼路径。

优先级：
    DATA_DIR: `ITV_DATA_DIR` > frozen（`sys.executable` 同级） > 开发态仓库根
    RES_DIR : `ITV_DATA_DIR` > `sys._MEIPASS` > `sys.executable` 同级 > 仓库 backend 根
"""

import os
import sys


def _backend_root():
    """`backend/` 目录的绝对路径（本文件位于 backend/app/paths.py）。"""
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def is_frozen():
    """是否运行在 PyInstaller / 冻结环境（frozen 属性为字符串路径）。"""
    return bool(getattr(sys, "frozen", False))


def resolve_data_dir():
    """可写数据目录：频道库、缓存、日志、抓图等一律落在这里。"""
    env = os.environ.get("ITV_DATA_DIR")
    if env:
        return os.path.abspath(env)
    if is_frozen():
        return os.path.dirname(os.path.abspath(sys.executable))
    # 开发态：仓库根（backend 的上一级）
    return os.path.dirname(_backend_root())


def resolve_res_dir():
    """静态资源目录：前端 dist、内置模板等只读资源。"""
    env = os.environ.get("ITV_DATA_DIR")
    if env:
        # 显式指定数据目录时，资源默认随数据目录（保持 main.py 原有语义）
        if is_frozen():
            return os.path.abspath(getattr(sys, "_MEIPASS", os.path.abspath(env)))
        return os.path.abspath(env)
    if is_frozen():
        return os.path.abspath(getattr(sys, "_MEIPASS", os.path.dirname(sys.executable)))
    return _backend_root()


# 进程内只解析一次，避免中途 os.chdir / 环境变量变更导致前后不一致。
DATA_DIR = resolve_data_dir()
RES_DIR = resolve_res_dir()


def db_path(filename="channels.db"):
    """SQLite 数据库文件路径。"""
    return os.path.join(DATA_DIR, filename)


def get_data_dir():
    """FastAPI 依赖用的无参可调用对象，返回数据目录。

    必须在 FastAPI `Depends(...)` 里用**函数**而非直接传 `DATA_DIR` 常量，
    否则 FastAPI 会把字符串当成请求参数（query/body）解析。
    原先 routes/{app,backup,export,repair}.py 各自定义了一份完全相同的副本，
    此处收敛为唯一定义。
    """
    return DATA_DIR