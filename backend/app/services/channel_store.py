import os
import sqlite3
import threading

DEFAULT_DB = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))),
    "channels.db",
)


class ChannelStore:
    def __init__(self, db_path=None):
        self.db_path = db_path or DEFAULT_DB
        self._lock = threading.RLock()
        self._conn = sqlite3.connect(self.db_path, check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._init_schema()

    def _init_schema(self):
        with self._lock:
            self._conn.execute(
                """CREATE TABLE IF NOT EXISTS channels (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT,
                    url TEXT,
                    norm_url TEXT UNIQUE,
                    status TEXT,
                    code TEXT,
                    ms TEXT,
                    res TEXT,
                    quality TEXT,
                    geo TEXT,
                    stack TEXT,
                    group_name TEXT,
                    tag TEXT,
                    is_fake_live INTEGER DEFAULT 0,
                    logo TEXT,
                    checked INTEGER DEFAULT 0,
                    order_idx INTEGER,
                    origin TEXT
                )"""
            )
            for col_sql in ("ALTER TABLE channels ADD COLUMN origin TEXT",
                            "ALTER TABLE channels ADD COLUMN is_fake_live INTEGER DEFAULT 0"):
                try:
                    self._conn.execute(col_sql)
                except Exception:
                    pass
            self._conn.commit()

    def clear(self):
        with self._lock:
            self._conn.execute("DELETE FROM channels")
            self._conn.commit()

    def shift_orders(self, delta):
        with self._lock:
            self._conn.execute("UPDATE channels SET order_idx = order_idx + ?", (delta,))
            self._conn.commit()

    @staticmethod
    def _row_from_channel(ch, order_idx, norm_url):
        return (
            ch.get("name", ""),
            ch.get("url", ""),
            norm_url,
            ch.get("status", "未检查"),
            ch.get("code", "-"),
            ch.get("ms", "-"),
            ch.get("res", "-"),
            ch.get("quality", "-"),
            ch.get("geo", ""),
            ch.get("stack", ""),
            ch.get("group", ""),
            ch.get("tag", ""),
            1 if ch.get("is_fake_live", False) else 0,
            ch.get("logo", ""),
            1 if ch.get("checked") else 0,
            order_idx,
            ch.get("origin", "manual"),
        )

    def upsert_many(self, rows):
        if not rows:
            return
        with self._lock:
            self._conn.executemany(
                """INSERT INTO channels
                   (name,url,norm_url,status,code,ms,res,quality,geo,stack,group_name,tag,is_fake_live,logo,checked,order_idx,origin)
                   VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
                   ON CONFLICT(norm_url) DO UPDATE SET
                     name=excluded.name, url=excluded.url, status=excluded.status,
                     code=excluded.code, ms=excluded.ms, res=excluded.res, quality=excluded.quality,
                     geo=excluded.geo, stack=excluded.stack, group_name=excluded.group_name,
                     tag=excluded.tag, is_fake_live=excluded.is_fake_live, logo=excluded.logo,
                     checked=excluded.checked, order_idx=excluded.order_idx, origin=excluded.origin""",
                rows,
            )
            self._conn.commit()

    def update_by_norm(self, norm_url, **fields):
        cols = {
            "name": fields.get("name"), "url": fields.get("url"),
            "status": fields.get("status"), "code": fields.get("code"),
            "ms": fields.get("ms"), "res": fields.get("res"),
            "quality": fields.get("quality"), "geo": fields.get("geo"),
            "stack": fields.get("stack"), "group_name": fields.get("group"),
            "tag": fields.get("tag"),
            "is_fake_live": (1 if fields.get("is_fake_live") else 0) if "is_fake_live" in fields else None,
            "logo": fields.get("logo"),
            "origin": fields.get("origin"),
            "checked": (1 if fields.get("checked") else 0) if "checked" in fields else None,
        }
        sets, vals = [], []
        for k, v in cols.items():
            if v is not None:
                sets.append(f"{k}=?")
                vals.append(v)
        if not sets:
            return
        vals.append(norm_url)
        with self._lock:
            self._conn.execute(f"UPDATE channels SET {','.join(sets)} WHERE norm_url=?", vals)
            self._conn.commit()

    def delete_by_norms(self, norm_urls):
        if not norm_urls:
            return
        with self._lock:
            self._conn.executemany(
                "DELETE FROM channels WHERE norm_url=?", [(n,) for n in norm_urls]
            )
            self._conn.commit()

    def count(self):
        with self._lock:
            return self._conn.execute("SELECT COUNT(*) FROM channels").fetchone()[0]

    def group_counts(self):
        with self._lock:
            rows = self._conn.execute(
                "SELECT group_name, COUNT(*) FROM channels GROUP BY group_name ORDER BY COUNT(*) DESC"
            ).fetchall()
            return [{"group": (r[0] or "未分组"), "count": r[1]} for r in rows]

    def get_page(self, offset, limit):
        with self._lock:
            rows = self._conn.execute(
                "SELECT * FROM channels ORDER BY order_idx, id LIMIT ? OFFSET ?",
                (limit, offset),
            ).fetchall()
            return [self._row_to_dict(r, idx) for idx, r in enumerate(rows, offset + 1)]

    def search(self, text, offset=0, limit=200):
        like = f"%{text}%"
        with self._lock:
            rows = self._conn.execute(
                """SELECT * FROM channels
                   WHERE name LIKE ? OR group_name LIKE ? OR tag LIKE ?
                   ORDER BY order_idx, id LIMIT ? OFFSET ?""",
                (like, like, like, limit, offset),
            ).fetchall()
            return [self._row_to_dict(r, idx) for idx, r in enumerate(rows, offset + 1)]

    @staticmethod
    def _row_to_dict(r, idx):
        return {
            "id": idx,
            "name": r["name"], "url": r["url"], "status": r["status"], "code": r["code"],
            "ms": r["ms"], "res": r["res"], "quality": r["quality"], "geo": r["geo"],
            "stack": r["stack"], "group": r["group_name"], "tag": r["tag"], "logo": r["logo"],
            "checked": bool(r["checked"]),
            "origin": r["origin"] or "manual",
        }

    def close(self):
        try:
            self._conn.close()
        except Exception:
            pass
