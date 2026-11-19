"""命令处理测试（nonebug，OneBot v11 与 Milky 双适配器路径）"""
import nonebot_plugin_group_heat as plugin
from nonebot.adapters.onebot.v11 import Bot as OB11Bot, Message
from nonebot.adapters.onebot.v11.event import (
    GroupMessageEvent,
    PrivateMessageEvent,
    Sender,
)
from nonebot.adapters.milky import Bot as MilkyBot
from nonebot.adapters.milky.config import ClientInfo
from nonebot.adapters.milky.event import (
    FriendMessageEvent as MilkyFriendEvent,
    GroupMessageEvent as MilkyGroupEvent,
)

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


def make_milky_group_event(text: str, group_id: int = 438, user_id: int = 5678) -> MilkyGroupEvent:
    return MilkyGroupEvent.model_validate({
        "time": 1122,
        "self_id": 1,
        "data": {
            "message_scene": "group",
            "peer_id": group_id,
            "message_seq": 1234,
            "sender_id": user_id,
            "time": 1122,
            "segments": [{"type": "text", "data": {"text": text}}],
        },
    })


def make_milky_friend_event(text: str, user_id: int = 5678) -> MilkyFriendEvent:
    return MilkyFriendEvent.model_validate({
        "time": 1122,
        "self_id": 1,
        "data": {
            "message_scene": "friend",
            "peer_id": user_id,
            "message_seq": 1234,
            "sender_id": user_id,
            "time": 1122,
            "segments": [{"type": "text", "data": {"text": text}}],
        },
    })


class FakeUni:
    """打桩 UniMessage，避免测试依赖 uniseg 导出器对 fake 适配器的行为"""

    @staticmethod
    def image(path=None):
        class _Sender:
            async def send(self, **kwargs):
                return None
        return _Sender()


class TestHeatCommand:
    async def test_ob11_group(self, app, monkeypatch):
        """回归：成功回复后不应再追加“获取热度失败”"""
        async def fake_heat(group_id, minutes=30):
            return 12.34

        monkeypatch.setattr(plugin, "get_recent_heat", fake_heat)

        async with app.test_matcher() as ctx:
            adapter = ctx.create_adapter()
            bot = ctx.create_bot(adapter=adapter, base=OB11Bot)
            event = make_group_event("/群热度")
            ctx.receive_event(bot, event)
            ctx.should_call_send(
                event,
                "过去30分钟的群热度：12.34°\n温度非常舒适，大家继续努力~",
                result=None,
                bot=bot,
            )
            ctx.should_finished(heat_cmd)

    async def test_milky_group(self, app, monkeypatch):
        """Milky 群消息路径：判群、查询、回复"""
        calls = []

        async def fake_heat(group_id, minutes=30):
            calls.append(group_id)
            return 15.0

        monkeypatch.setattr(plugin, "get_recent_heat", fake_heat)

        async with app.test_matcher() as ctx:
            adapter = ctx.create_adapter()
            bot = ctx.create_bot(adapter=adapter, base=MilkyBot, self_id="1", info=ClientInfo())
            event = make_milky_group_event("/群热度")
            ctx.receive_event(bot, event)
            ctx.should_call_send(
                event,
                "过去30分钟的群热度：15.00°\n温度非常舒适，大家继续努力~",
                result=None,
                bot=bot,
            )
            ctx.should_finished(heat_cmd)

        assert calls == [438]

    async def test_ob11_private(self, app):
        async with app.test_matcher() as ctx:
            adapter = ctx.create_adapter()
            bot = ctx.create_bot(adapter=adapter, base=OB11Bot)
            event = make_private_event("/群热度")
            ctx.receive_event(bot, event)
            ctx.should_call_send(event, "该命令仅支持群聊", result=None, bot=bot)
            ctx.should_finished(heat_cmd)

    async def test_milky_private(self, app):
        async with app.test_matcher() as ctx:
            adapter = ctx.create_adapter()
            bot = ctx.create_bot(adapter=adapter, base=MilkyBot, self_id="1", info=ClientInfo())
            event = make_milky_friend_event("/群热度")
            ctx.receive_event(bot, event)
            ctx.should_call_send(event, "该命令仅支持群聊", result=None, bot=bot)
            ctx.should_finished(heat_cmd)

    async def test_db_error_single_reply(self, app, monkeypatch):
        async def fake_heat(group_id, minutes=30):
            raise RuntimeError("db boom")

        monkeypatch.setattr(plugin, "get_recent_heat", fake_heat)

        async with app.test_matcher() as ctx:
            adapter = ctx.create_adapter()
            bot = ctx.create_bot(adapter=adapter, base=OB11Bot)
            event = make_group_event("/群热度")
            ctx.receive_event(bot, event)
            ctx.should_call_send(event, "获取热度失败，请稍后再试", result=None, bot=bot)
            ctx.should_finished(heat_cmd)


class TestYesterdayCommand:
    async def test_no_data(self, app, monkeypatch):
        """回归：昨日无数据应提示，而不是画 -10 平线图"""
        async def fake_yesterday(group_id):
            return [], [], -10.0

        monkeypatch.setattr(plugin, "get_yesterday_heat", fake_yesterday)

        async with app.test_matcher() as ctx:
            adapter = ctx.create_adapter()
            bot = ctx.create_bot(adapter=adapter, base=OB11Bot)
            event = make_group_event("/昨日热度图")
            ctx.receive_event(bot, event)
            ctx.should_call_send(event, "暂无昨日数据，请明天再来~", result=None, bot=bot)
            ctx.should_finished(yesterday_cmd)

    async def test_success_no_extra_error(self, app, monkeypatch):
        """回归：成功回复后不应再追加报错（FinishedException 被 except 吞）"""
        from pathlib import Path

        async def fake_yesterday(group_id):
            return [-10.0, -9.5], ["00:00", "00:30"], -9.75

        def fake_draw(values, labels, avg):
            p = Path("/tmp/fake_heat_test.png")
            p.write_bytes(b"png")
            return p

        monkeypatch.setattr(plugin, "get_yesterday_heat", fake_yesterday)
        monkeypatch.setattr(plugin, "draw_heat_line", fake_draw)
        monkeypatch.setattr(plugin, "UniMessage", FakeUni)

        async with app.test_matcher() as ctx:
            adapter = ctx.create_adapter()
            bot = ctx.create_bot(adapter=adapter, base=OB11Bot)
            event = make_group_event("/昨日热度图")
            ctx.receive_event(bot, event)
            ctx.should_call_send(
                event,
                "昨日群平均热度：-9.75°\n群成冰块啦，群主快开暖气",
                result=None,
                bot=bot,
            )
            ctx.should_finished(yesterday_cmd)

    async def test_milky_no_data(self, app, monkeypatch):
        async def fake_yesterday(group_id):
            return [], [], -10.0

        monkeypatch.setattr(plugin, "get_yesterday_heat", fake_yesterday)

        async with app.test_matcher() as ctx:
            adapter = ctx.create_adapter()
            bot = ctx.create_bot(adapter=adapter, base=MilkyBot, self_id="1", info=ClientInfo())
            event = make_milky_group_event("/昨日热度图")
            ctx.receive_event(bot, event)
            ctx.should_call_send(event, "暂无昨日数据，请明天再来~", result=None, bot=bot)
            ctx.should_finished(yesterday_cmd)


class TestRecorder:
    async def test_records_ob11_group(self, app, monkeypatch):
        calls = []

        async def fake_add(group_id, user_id, msg_type, timestamp):
            calls.append((group_id, user_id, msg_type))

        monkeypatch.setattr(plugin, "add_message", fake_add)

        async with app.test_matcher() as ctx:
            adapter = ctx.create_adapter()
            bot = ctx.create_bot(adapter=adapter, base=OB11Bot)
            ctx.receive_event(bot, make_private_event("私聊消息"))
            ctx.receive_event(bot, make_group_event("大家好啊"))

        assert len(calls) == 1
        assert calls[0][2] == "text"

    async def test_records_milky_group(self, app, monkeypatch):
        """Milky 群文本消息应被记录为 text"""
        calls = []

        async def fake_add(group_id, user_id, msg_type, timestamp):
            calls.append((group_id, user_id, msg_type))

        monkeypatch.setattr(plugin, "add_message", fake_add)

        async with app.test_matcher() as ctx:
            adapter = ctx.create_adapter()
            bot = ctx.create_bot(adapter=adapter, base=MilkyBot, self_id="1", info=ClientInfo())
            ctx.receive_event(bot, make_milky_friend_event("私聊消息"))
            ctx.receive_event(bot, make_milky_group_event("大家好啊"))

        assert calls == [(438, 5678, "text")]

    async def test_records_file_type(self, app, monkeypatch):
        """媒体消息记录链路：fake 适配器下 uniseg 不转换 image 段，
        段类型分类已在 test_adapters 纯单测覆盖，此处打桩分类函数验证链路"""
        calls = []

        async def fake_add(group_id, user_id, msg_type, timestamp):
            calls.append((group_id, user_id, msg_type))

        monkeypatch.setattr(plugin, "add_message", fake_add)
        monkeypatch.setattr(plugin, "classify_uniseg", lambda msg: "file")

        async with app.test_matcher() as ctx:
            adapter = ctx.create_adapter()
            bot = ctx.create_bot(adapter=adapter, base=OB11Bot)
            event = make_group_event("[CQ:image,file=abc.jpg]")
            ctx.receive_event(bot, event)

        assert calls and calls[0][2] == "file"
