import sqlite3
import asyncio
from pathlib import Path
from datetime import datetime, timedelta
from typing import List, Optional, Tuple
from nonebot import require, get_plugin_config

require("nonebot_plugin_localstore")
import nonebot_plugin_localstore as store

from .config import Config

DATA_DIR = store.get_plugin_data_dir()
DATA_DIR.mkdir(parents=True, exist_ok=True)
DB_PATH = DATA_DIR / "heat.db"

config = get_plugin_config(Config)

# 消息类型 → 热度权重
HEAT_WEIGHTS = {
    "text": 0.05,
    "sticker": 0.2,
    "file": 0.3,
}
# 每个统计周期的初始热度
BASE_HEAT = -10.0


def get_db_path() -> Path:
    return DB_PATH


def _connect() -> sqlite3.Connection:
    conn = sqlite3.connect(str(get_db_path()), timeout=10)
    conn.execute("PRAGMA journal_mode=WAL")
    return conn


async def init_db():
    def _init():
        conn = _connect()
        c = conn.cursor()
        c.execute('''
            CREATE TABLE IF NOT EXISTS messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                group_id INTEGER NOT NULL,
                user_id INTEGER NOT NULL,
                msg_type TEXT NOT NULL,
                timestamp REAL NOT NULL
            )
        ''')
        c.execute('CREATE INDEX IF NOT EXISTS idx_group_time ON messages (group_id, timestamp)')
        conn.commit()
        conn.close()
    await asyncio.to_thread(_init)


async def add_message(group_id: int, user_id: int, msg_type: str, timestamp: float):
    def _add():
        conn = _connect()
        c = conn.cursor()
        c.execute(
            "INSERT INTO messages (group_id, user_id, msg_type, timestamp) VALUES (?, ?, ?, ?)",
            (group_id, user_id, msg_type, timestamp)
        )
        conn.commit()
        conn.close()
    await asyncio.to_thread(_add)


async def get_recent_heat(group_id: int, minutes: int = 30) -> float:
    now = datetime.now().timestamp()
    start = now - minutes * 60

    def _calc():
        conn = _connect()
        c = conn.cursor()
        c.execute(
            'SELECT msg_type, COUNT(*) FROM messages '
            'WHERE group_id = ? AND timestamp >= ? GROUP BY msg_type',
            (group_id, start)
        )
        rows = c.fetchall()
        conn.close()
        heat = BASE_HEAT
        for msg_type, count in rows:
            heat += HEAT_WEIGHTS.get(msg_type, 0.0) * count
        return heat
    return await asyncio.to_thread(_calc)


def _yesterday_range(now: datetime) -> Tuple[datetime, datetime]:
    yesterday_start = now.replace(hour=0, minute=0, second=0, microsecond=0) - timedelta(days=1)
    return yesterday_start, yesterday_start + timedelta(days=1)


async def get_yesterday_heat(group_id: int) -> Tuple[List[float], List[str], float]:
    """昨日每 30 分钟热度序列。

    昨日全天没有任何消息时返回空列表（热度图无意义），
    有消息但某些区间安静时，该区间热度为初始值 BASE_HEAT。
    """
    now = datetime.now()
    yesterday_start, yesterday_end = _yesterday_range(now)
    start_ts = yesterday_start.timestamp()
    end_ts = yesterday_end.timestamp()

    def _calc():
        conn = _connect()
        c = conn.cursor()
        # 单次查询按 30 分钟分桶统计
        c.execute(
            'SELECT CAST((timestamp - ?) / 1800 AS INTEGER) AS bucket, msg_type, COUNT(*) '
            'FROM messages WHERE group_id = ? AND timestamp >= ? AND timestamp < ? '
            'GROUP BY bucket, msg_type',
            (start_ts, group_id, start_ts, end_ts)
        )
        rows = c.fetchall()
        conn.close()
        return rows

    rows = await asyncio.to_thread(_calc)
    if not rows:
        return [], [], BASE_HEAT

    buckets: dict[int, float] = {}
    for bucket, msg_type, count in rows:
        buckets[bucket] = buckets.get(bucket, 0.0) + HEAT_WEIGHTS.get(msg_type, 0.0) * count

    total_buckets = int((end_ts - start_ts) / 1800)
    heat_values = [BASE_HEAT + buckets.get(i, 0.0) for i in range(total_buckets)]
    time_labels = [
        (yesterday_start + timedelta(minutes=30 * i)).strftime("%H:%M")
        for i in range(total_buckets)
    ]
    avg_heat = sum(heat_values) / len(heat_values)
    return heat_values, time_labels, avg_heat


async def cleanup_old_messages(retention_days: Optional[int] = None) -> int:
    """删除超过保留期的消息记录，返回删除行数"""
    days = retention_days if retention_days is not None else config.group_heat_retention_days
    threshold = datetime.now().timestamp() - days * 86400

    def _cleanup():
        conn = _connect()
        c = conn.cursor()
        c.execute('DELETE FROM messages WHERE timestamp < ?', (threshold,))
        removed = c.rowcount
        conn.commit()
        conn.close()
        return removed
    return await asyncio.to_thread(_cleanup)
