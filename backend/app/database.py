import os
import sys
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker

if getattr(sys, 'frozen', False):
    DATA_DIR = os.path.dirname(os.path.abspath(sys.executable))
else:
    DATA_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
DATABASE_URL = f"sqlite+aiosqlite:///{os.path.join(DATA_DIR, 'channels.db')}"

engine = create_async_engine(DATABASE_URL, echo=False, connect_args={"check_same_thread": False})
AsyncSessionLocal = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


async def get_db():
    async with AsyncSessionLocal() as session:
        yield session


async def init_db():
    from app.models import Base
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)