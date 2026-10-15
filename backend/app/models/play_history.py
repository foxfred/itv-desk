from datetime import datetime

from sqlalchemy import Boolean, Column, DateTime, Integer, String

from app.models.channel import Base


class PlaybackHistory(Base):
    __tablename__ = "playback_history"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String, default="")
    url = Column(String, default="")
    group = Column(String, default="")
    played_at = Column(DateTime, default=datetime.utcnow)
    play_count = Column(Integer, default=1)
    is_favorite = Column(Boolean, default=False)
