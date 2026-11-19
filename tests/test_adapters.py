"""跨适配器纯函数测试：分类与群场景识别"""
from nonebot.adapters.onebot.v11 import Message as OBMessage
from nonebot.adapters.onebot.v11.event import GroupMessageEvent as OBGroupEvent, PrivateMessageEvent
from nonebot.adapters.milky.event import GroupMessageEvent as MilkyGroupEvent, FriendMessageEvent

from nonebot_plugin_alconna.uniseg import (
    Emoji,
    File,
    Image,
    Text,
    UniMessage,
    Video,
    Voice,
)

from nonebot_plugin_group_heat import classify_uniseg, get_group_scene


class TestClassify:
    def test_text(self):
        assert classify_uniseg(UniMessage([Text("你好")])) == "text"

    def test_emoji_is_sticker(self):
        assert classify_uniseg(UniMessage([Emoji("178")])) == "sticker"

    def test_image_is_file(self):
        assert classify_uniseg(UniMessage([Image(url="http://x/a.jpg")])) == "file"

    def test_all_media_are_file(self):
        assert classify_uniseg(UniMessage([Video(url="http://x/v.mp4")])) == "file"
        assert classify_uniseg(UniMessage([Voice(url="http://x/a.mp3")])) == "file"
        assert classify_uniseg(UniMessage([File(id="1", name="a", url="http://x/f")])) == "file"

    def test_first_segment_wins(self):
        msg = UniMessage([Text("看看"), Image(url="http://x/a.jpg")])
        assert classify_uniseg(msg) == "text"
        msg = UniMessage([Emoji("1"), Text("嘿嘿")])
        assert classify_uniseg(msg) == "sticker"

    def test_other(self):
        from nonebot_plugin_alconna.uniseg import At

        # 无可计分段（如仅 @）
        assert classify_uniseg(UniMessage([At(flag="user", target="1")])) == "other"
        # 空消息
        assert classify_uniseg(UniMessage()) == "other"


def make_ob_group_event(text: str = "你好", group_id: int = 438, user_id: int = 5678) -> OBGroupEvent:
    return OBGroupEvent(
        time=1122,
        self_id=1,
        post_type="message",
        sub_type="normal",
        user_id=user_id,
        message_type="group",
        message_id=1234,
        message=OBMessage(text),
        raw_message=text,
        font=0,
        sender={"user_id": user_id, "nickname": "t"},
        group_id=group_id,
    )


def make_milky_group_event(text: str = "你好", group_id: int = 438, user_id: int = 5678):
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


class TestGetGroupScene:
    def test_ob11_group(self):
        assert get_group_scene(make_ob_group_event()) == (438, 5678)

    def test_ob11_private(self):
        ev = PrivateMessageEvent(
            time=1122, self_id=1, post_type="message", sub_type="friend",
            user_id=5678, message_type="private", message_id=1,
            message=OBMessage("hi"), raw_message="hi", font=0,
            sender={"user_id": 5678, "nickname": "t"},
        )
        assert get_group_scene(ev) is None

    def test_milky_group(self):
        assert get_group_scene(make_milky_group_event()) == (438, 5678)

    def test_milky_friend(self):
        ev = FriendMessageEvent.model_validate({
            "time": 1122,
            "self_id": 1,
            "data": {
                "message_scene": "friend",
                "peer_id": 5678,
                "message_seq": 1234,
                "sender_id": 5678,
                "time": 1122,
                "segments": [{"type": "text", "data": {"text": "hi"}}],
            },
        })
        assert get_group_scene(ev) is None

    def test_other_event(self):
        from nonebot.adapters import Event

        class FakeEvent(Event):
            def get_type(self): return "message"
            def get_event_name(self): return "test"
            def get_event_description(self): return "test"
            def get_user_id(self): return "1"
            def get_session_id(self): return "1"
            def get_message(self): raise ValueError
            def get_plaintext(self): return ""
            def is_tome(self): return False

        assert get_group_scene(FakeEvent(time=1, self_id=1)) is None
