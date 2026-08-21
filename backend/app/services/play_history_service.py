"""播放历史服务 - 基于 SQLite(SQLAlchemy) 的播放记录持久化"""
import asyncio
from datetime import datetime
from sqlalchemy import select, desc
from app.database import AsyncSessionLocal, init_db
from app.models.play_history import PlaybackHistory

MAX_HISTORY = 200
MAX_FAVORITES = 500


def _ensure_sync(coro):
    """在 FastAPI 同步路由/后台线程中运行异步协程"""
    try:
        return asyncio.run(coro)
    except RuntimeError:
        loop = asyncio.new_event_loop()
        try:
            return loop.run_until_complete(coro)
        finally:
            loop.close()


async def _upsert_async(name, url, group="", favorite=False):
    async with AsyncSessionLocal() as session:
        result = await session.execute(
            select(PlaybackHistory).where(PlaybackHistory.url == url)
        )
        record = result.scalar_one_or_none()
        if record:
            record.play_count = (record.play_count or 1) + 1
            record.played_at = datetime.utcnow()
            if favorite:
                record.is_favorite = True
            await session.commit()
            return record.id
        record = PlaybackHistory(name=name, url=url, group=group, is_favorite=favorite)
        session.add(record)
        await session.commit()
        # 容量控制：超出后删除最旧的
        count = await session.scalar(
            select(PlaybackHistory.id).order_by(desc(PlaybackHistory.played_at))
        )
        if count is None:
            return record.id
        rows = (await session.execute(
            select(PlaybackHistory).order_by(desc(PlaybackHistory.played_at))
        )).scalars().all()
        if len(rows) > MAX_HISTORY:
            for old in rows[MAX_HISTORY:]:
                await session.delete(old)
            await session.commit()
        return record.id


async def _list_async(limit=50):
    async with AsyncSessionLocal() as session:
        rows = (await session.execute(
            select(PlaybackHistory).order_by(desc(PlaybackHistory.played_at)).limit(limit)
        )).scalars().all()
        return [{
            "id": r.id,
            "name": r.name,
            "url": r.url,
            "group": r.group,
            "played_at": r.played_at.isoformat() if r.played_at else None,
            "play_count": r.play_count,
            "is_favorite": bool(r.is_favorite),
        } for r in rows]


async def _remove_async(record_id):
    async with AsyncSessionLocal() as session:
        record = await session.get(PlaybackHistory, record_id)
        if record:
            await session.delete(record)
            await session.commit()
            return True
        return False


async def _toggle_favorite_async(record_id):
    async with AsyncSessionLocal() as session:
        record = await session.get(PlaybackHistory, record_id)
        if record:
            record.is_favorite = not record.is_favorite
            await session.commit()
            return bool(record.is_favorite)
        return None


async def _clear_async():
    async with AsyncSessionLocal() as session:
        rows = (await session.execute(select(PlaybackHistory))).scalars().all()
        for r in rows:
            await session.delete(r)
        await session.commit()
        return len(rows)


def record_play(name, url, group="", favorite=False):
    """记录一次播放（供同步调用）"""
    return _ensure_sync(_upsert_async(name, url, group, favorite))


def list_history(limit=50):
    return _ensure_sync(_list_async(limit))


def remove(record_id):
    return _ensure_sync(_remove_async(record_id))


def toggle_favorite(record_id):
    return _ensure_sync(_toggle_favorite_async(record_id))


def clear():
    return _ensure_sync(_clear_async())


def init():
    """初始化数据库表"""
    return _ensure_sync(init_db())
