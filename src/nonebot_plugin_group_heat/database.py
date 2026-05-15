import sqlite3
import asyncio
from pathlib import Path
from datetime import datetime, timedelta
from typing import List, Tuple


def get_data_dir():
    from nonebot_plugin_localstore import get_data_dir as _get_data_dir
    return _get_data_dir("nonebot_plugin_group_heat")


def get_db_path():
    data_dir = get_data_dir()
    data_dir.mkdir(parents=True, exist_ok=True)
    return data_dir / "heat.db"


async def init_db():
    def _init():
        conn = sqlite3.connect(str(get_db_path()))
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
    await asyncio.get_event_loop().run_in_executor(None, _init)


async def add_message(group_id: int, user_id: int, msg_type: str, timestamp: float):
    def _add():
        conn = sqlite3.connect(str(get_db_path()))
        c = conn.cursor()
        c.execute(
            "INSERT INTO messages (group_id, user_id, msg_type, timestamp) VALUES (?, ?, ?, ?)",
            (group_id, user_id, msg_type, timestamp)
        )
        conn.commit()
        conn.close()
    await asyncio.get_event_loop().run_in_executor(None, _add)


async def get_recent_heat(group_id: int, minutes: int = 30) -> float:
    now = datetime.now().timestamp()
    start = now - minutes * 60

    def _calc():
        conn = sqlite3.connect(str(get_db_path()))
        c = conn.cursor()
        c.execute('SELECT msg_type FROM messages WHERE group_id = ? AND timestamp >= ?', (group_id, start))
        rows = c.fetchall()
        conn.close()
        heat = -10.0
        for row in rows:
            msg_type = row[0]
            if msg_type == 'text':
                heat += 0.05
            elif msg_type == 'sticker':
                heat += 0.2
            elif msg_type == 'file':
                heat += 0.3
        return heat
    return await asyncio.get_event_loop().run_in_executor(None, _calc)


async def get_yesterday_heat(group_id: int) -> Tuple[List[float], List[str], float]:
    now = datetime.now()
    yesterday_start = now.replace(hour=0, minute=0, second=0, microsecond=0) - timedelta(days=1)
    yesterday_end = yesterday_start + timedelta(days=1)

    intervals = []
    current = yesterday_start
    while current < yesterday_end:
        intervals.append(current)
        current += timedelta(minutes=30)

    heat_values = []
    time_labels = []

    for interval_start in intervals:
        interval_end = interval_start + timedelta(minutes=30)
        start_ts = interval_start.timestamp()
        end_ts = interval_end.timestamp()

        def _calc_interval():
            conn = sqlite3.connect(str(get_db_path()))
            c = conn.cursor()
            c.execute('SELECT msg_type FROM messages WHERE group_id = ? AND timestamp >= ? AND timestamp < ?',
                      (group_id, start_ts, end_ts))
            rows = c.fetchall()
            conn.close()
            heat = -10.0
            for row in rows:
                t = row[0]
                if t == 'text':
                    heat += 0.05
                elif t == 'sticker':
                    heat += 0.2
                elif t == 'file':
                    heat += 0.3
            return heat

        heat = await asyncio.get_event_loop().run_in_executor(None, _calc_interval)
        heat_values.append(heat)
        time_labels.append(interval_start.strftime("%H:%M"))

    avg_heat = sum(heat_values) / len(heat_values) if heat_values else -10.0
    return heat_values, time_labels, avg_heat