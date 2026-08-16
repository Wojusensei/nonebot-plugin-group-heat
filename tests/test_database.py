"""数据库统计逻辑测试（真实 sqlite）"""
import sqlite3
from datetime import datetime, timedelta

import pytest

from nonebot_plugin_group_heat import database as db


@pytest.fixture
async def db_ready(app):
    await db.init_db()
    # 每个测试前清空表，避免同会话内数据互相污染
    conn = sqlite3.connect(str(db.get_db_path()))
    conn.execute("DELETE FROM messages")
    conn.commit()
    conn.close()
    return db


async def test_recent_heat_weights(db_ready):
    db = db_ready
    now = datetime.now().timestamp()
    # 20 条文本 + 1 表情 + 1 文件
    for _ in range(20):
        await db.add_message(100, 1, "text", now - 60)
    await db.add_message(100, 1, "sticker", now - 60)
    await db.add_message(100, 2, "file", now - 60)
    heat = await db.get_recent_heat(100, minutes=30)
    assert heat == pytest.approx(-10.0 + 20 * 0.05 + 0.2 + 0.3)


async def test_recent_heat_excludes_old(db_ready):
    db = db_ready
    old = datetime.now().timestamp() - 3600  # 1 小时前
    await db.add_message(100, 1, "text", old)
    heat = await db.get_recent_heat(100, minutes=30)
    assert heat == pytest.approx(-10.0)


async def test_recent_heat_isolated_between_groups(db_ready):
    db = db_ready
    now = datetime.now().timestamp()
    await db.add_message(100, 1, "text", now)
    await db.add_message(200, 1, "text", now)
    heat_100 = await db.get_recent_heat(100, minutes=30)
    assert heat_100 == pytest.approx(-10.0 + 0.05)


async def test_yesterday_heat_empty(db_ready):
    """回归：昨日没有任何消息时返回空列表（而不是 48 个 -10）"""
    db = db_ready
    values, labels, avg = await db.get_yesterday_heat(999)
    assert values == []
    assert labels == []
    assert avg == -10.0


async def test_yesterday_heat_buckets(db_ready):
    db = db_ready
    now = datetime.now()
    yesterday_start = now.replace(hour=0, minute=0, second=0, microsecond=0) - timedelta(days=1)
    # 昨日 10:15 两条文本
    t = (yesterday_start + timedelta(hours=10, minutes=15)).timestamp()
    await db.add_message(100, 1, "text", t)
    await db.add_message(100, 1, "text", t)
    # 昨日 20:45 一个文件
    t2 = (yesterday_start + timedelta(hours=20, minutes=45)).timestamp()
    await db.add_message(100, 2, "file", t2)
    # 今天的消息不应计入
    await db.add_message(100, 1, "text", now.timestamp())

    values, labels, avg = await db.get_yesterday_heat(100)
    assert len(values) == 48
    assert len(labels) == 48
    # 10:00-10:30 区间（bucket 20）：-10 + 2*0.05
    assert values[20] == pytest.approx(-10.0 + 0.1)
    # 20:30-21:00 区间（bucket 41）：-10 + 0.3
    assert values[41] == pytest.approx(-10.0 + 0.3)
    # 其余区间都是基础值
    assert values[0] == pytest.approx(-10.0)
    assert labels[20] == "10:00"
    assert labels[41] == "20:30"
    # 平均 = (-10*47 + (-10+0.1) + (-10+0.3)) / 48
    assert avg == pytest.approx((-10.0 * 48 + 0.1 + 0.3) / 48)


async def test_cleanup_old_messages(db_ready, monkeypatch):
    db = db_ready
    now = datetime.now()
    await db.add_message(100, 1, "text", (now - timedelta(days=30)).timestamp())
    await db.add_message(100, 1, "text", (now - timedelta(days=2)).timestamp())
    removed = await db.cleanup_old_messages(retention_days=7)
    assert removed == 1
    heat = await db.get_recent_heat(100, minutes=30)
    # 剩下的 2 天前消息也不在 30 分钟窗口内
    assert heat == pytest.approx(-10.0)
