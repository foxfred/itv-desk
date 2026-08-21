"""SQLAlchemy ORM 模型 PlaybackHistory - 播放历史（SQLite 持久化）"""
from sqlalchemy import Column, Integer, String, DateTime, Boolean
from app.models.channel import Base
from datetime import datetime


class PlaybackHistory(Base):
    __tablename__ = "playback_history"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String, default="")
    url = Column(String, default="")
    group = Column(String, default="")
    played_at = Column(DateTime, default=datetime.utcnow)
    play_count = Column(Integer, default=1)
    is_favorite = Column(Boolean, default=False)
