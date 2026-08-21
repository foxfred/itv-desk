"""IPTV Core 后端入口（重构版）
通过 app.main 启动分层架构的后端服务。

运行： python main.py      (在 backend 目录下)
"""
import os
import sys

# 确保能找到 app 模块
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.main import run_server

if __name__ == "__main__":
    run_server(host="0.0.0.0", port=8000)