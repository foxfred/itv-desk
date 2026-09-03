"""SQLAlchemy ORM 模型 Channel"""
from sqlalchemy import Column, Integer, String, Boolean
from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    pass


class Channel(Base):
    __tablename__ = "channels"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String, default="")
    url = Column(String, default="")
    group = Column(String, default="杂项频道")
    tag = Column(String, default="")
    logo = Column(String, default="")
    status = Column(String, default="未检查")
    code = Column(String, default="-")
    ms = Column(String, default="-")
    res = Column(String, default="-")
    quality = Column(String, default="-")
    geo = Column(String, default="中国")
    stack = Column(String, default="IPv4")
    checked = Column(Boolean, default=False)