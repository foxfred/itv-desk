"""SQLAlchemy 异步引擎和会话管理"""
import os
import sys
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker

# 数据目录：开发时取项目根目录，PyInstaller 打包后取 exe 所在目录
# 注意：如果手动移动 EXE，必须把 _internal/ 目录一起复制，否则程序无法启动。
# 如果仅移动 EXE 而不带 _internal/，所有 Python 依赖和模块都找不到。
if getattr(sys, 'frozen', False):
    DATA_DIR = os.path.dirname(os.path.abspath(sys.executable))
else:
    DATA_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
DATABASE_URL = f"sqlite+aiosqlite:///{os.path.join(DATA_DIR, 'channels.db')}"

engine = create_async_engine(DATABASE_URL, echo=False, connect_args={"check_same_thread": False})
AsyncSessionLocal = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


async def get_db():
    """FastAPI 依赖注入：获取异步数据库会话"""
    async with AsyncSessionLocal() as session:
        yield session


async def init_db():
    """初始化数据库表（幂等）"""
    from app.models import Base
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)