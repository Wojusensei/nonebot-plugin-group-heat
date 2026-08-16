"""命令处理测试（nonebug）"""
import nonebot_plugin_group_heat as plugin
from nonebot.adapters.onebot.v11 import Message, GroupMessageEvent, PrivateMessageEvent

from nonebot_plugin_group_heat import heat_cmd, yesterday_cmd


def make_group_event(text: str, group_id: int = 10000, user_id: int = 20000) -> GroupMessageEvent:
    return GroupMessageEvent(
        time=1122,
        self_id=1,
        post_type="message",
        sub_type="normal",
        user_id=user_id,
        message_type="group",
        message_id=1234,
        message=Message(text),
        raw_message=text,
        font=0,
        sender={"user_id": user_id, "nickname": "test"},
        group_id=group_id,
    )


def make_private_event(text: str, user_id: int = 20000) -> PrivateMessageEvent:
    return PrivateMessageEvent(
        time=1122,
        self_id=1,
        post_type="message",
        sub_type="friend",
        user_id=user_id,
        message_type="private",
        message_id=1234,
        message=Message(text),
        raw_message=text,
        font=0,
        sender={"user_id": user_id, "nickname": "test"},
    )


async def test_heat_in_group(app, monkeypatch):
    """回归：成功回复后不应再追加“获取热度失败”"""
    async def fake_heat(group_id, minutes=30):
        return 12.34

    monkeypatch.setattr(plugin, "get_recent_heat", fake_heat)

    async with app.test_matcher() as ctx:
        adapter = ctx.create_adapter()
        bot = ctx.create_bot(adapter=adapter)
        event = make_group_event("/群热度")
        ctx.receive_event(bot, event)
        ctx.should_call_send(
            event,
            "过去30分钟的群热度：12.34°\n温度非常舒适，大家继续努力~",
            result=None,
            bot=bot,
        )
        ctx.should_finished(heat_cmd)


async def test_heat_db_error(app, monkeypatch):
    async def fake_heat(group_id, minutes=30):
        raise RuntimeError("db boom")

    monkeypatch.setattr(plugin, "get_recent_heat", fake_heat)

    async with app.test_matcher() as ctx:
        adapter = ctx.create_adapter()
        bot = ctx.create_bot(adapter=adapter)
        event = make_group_event("/群热度")
        ctx.receive_event(bot, event)
        ctx.should_call_send(event, "获取热度失败，请稍后再试", result=None, bot=bot)
        ctx.should_finished(heat_cmd)


async def test_heat_in_private(app):
    async with app.test_matcher() as ctx:
        adapter = ctx.create_adapter()
        bot = ctx.create_bot(adapter=adapter)
        event = make_private_event("/群热度")
        ctx.receive_event(bot, event)
        ctx.should_call_send(event, "该命令仅支持群聊", result=None, bot=bot)
        ctx.should_finished(heat_cmd)


async def test_yesterday_no_data(app, monkeypatch):
    """回归：昨日无数据应提示，而不是画 -10 平线图"""
    async def fake_yesterday(group_id):
        return [], [], -10.0

    monkeypatch.setattr(plugin, "get_yesterday_heat", fake_yesterday)

    async with app.test_matcher() as ctx:
        adapter = ctx.create_adapter()
        bot = ctx.create_bot(adapter=adapter)
        event = make_group_event("/昨日热度图")
        ctx.receive_event(bot, event)
        ctx.should_call_send(event, "暂无昨日数据，请明天再来~", result=None, bot=bot)
        ctx.should_finished(yesterday_cmd)


async def test_yesterday_success(app, monkeypatch):
    from pathlib import Path

    async def fake_yesterday(group_id):
        return [-10.0, -9.5], ["00:00", "00:30"], -9.75

    def fake_draw(values, labels, avg):
        p = Path("/tmp/fake_heat_test.png")
        p.write_bytes(b"png")
        return p

    monkeypatch.setattr(plugin, "get_yesterday_heat", fake_yesterday)
    monkeypatch.setattr(plugin, "draw_heat_line", fake_draw)

    class FakeSegment:
        @staticmethod
        def image(path):
            return "IMAGE_SENT"

    monkeypatch.setattr(plugin, "MessageSegment", FakeSegment)

    async with app.test_matcher() as ctx:
        adapter = ctx.create_adapter()
        bot = ctx.create_bot(adapter=adapter)
        event = make_group_event("/昨日热度图")
        ctx.receive_event(bot, event)
        ctx.should_call_send(event, "IMAGE_SENT", result=None, bot=bot)
        ctx.should_call_send(
            event,
            "昨日群平均热度：-9.75°\n群成冰块啦，群主快开暖气",
            result=None,
            bot=bot,
        )
        ctx.should_finished(yesterday_cmd)


async def test_recorder_only_records_group(app, monkeypatch):
    """私聊消息不应被记录"""
    calls = []

    async def fake_add(group_id, user_id, msg_type, timestamp):
        calls.append((group_id, user_id, msg_type))

    monkeypatch.setattr(plugin, "add_message", fake_add)

    async with app.test_matcher() as ctx:
        adapter = ctx.create_adapter()
        bot = ctx.create_bot(adapter=adapter)
        ctx.receive_event(bot, make_private_event("大家好啊"))
        # 私聊消息不应触发记录
        ctx.receive_event(bot, make_group_event("大家好啊"))
        # 记录器不回复任何消息，receive 后无断言即验证不发送

    # 只有群消息被记录为 text
    assert len(calls) == 1 and calls[0][2] == "text"


async def test_recorder_classifies_image(app, monkeypatch):
    calls = []

    async def fake_add(group_id, user_id, msg_type, timestamp):
        calls.append((group_id, user_id, msg_type))

    monkeypatch.setattr(plugin, "add_message", fake_add)

    async with app.test_matcher() as ctx:
        adapter = ctx.create_adapter()
        bot = ctx.create_bot(adapter=adapter)
        event = make_group_event("[CQ:image,file=abc.jpg]")
        ctx.receive_event(bot, event)

    assert calls and calls[0][2] == "file"
