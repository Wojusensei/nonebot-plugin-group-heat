from datetime import datetime
from typing import Optional, Tuple

from nonebot import on_command, on_message, get_driver, get_plugin_config, require
from nonebot.adapters import Event
from nonebot.plugin import PluginMetadata
from nonebot.log import logger

require("nonebot_plugin_localstore")
require("nonebot_plugin_apscheduler")
require("nonebot_plugin_alconna")

from nonebot_plugin_apscheduler import scheduler

from nonebot_plugin_alconna.uniseg import (
    Audio,
    Emoji,
    File,
    Image,
    Text,
    UniMessage,
    UniMsg,
    Video,
    Voice,
)

# 适配器按需导入：用户只装其中一个适配器时插件仍可正常加载
try:
    from nonebot.adapters.onebot.v11 import GroupMessageEvent as OBGroupMessageEvent
except ImportError:
    OBGroupMessageEvent = None

try:
    from nonebot.adapters.milky.event import GroupMessageEvent as MilkyGroupMessageEvent
except ImportError:
    MilkyGroupMessageEvent = None

from .config import Config
from .database import (
    init_db,
    add_message,
    get_recent_heat,
    get_yesterday_heat,
    cleanup_old_messages,
)
from .heat_image import draw_heat_line, get_heat_comment

__plugin_meta__ = PluginMetadata(
    name="群热度统计",
    description="统计群内热度，支持实时查询和昨日热度图",
    usage=(
        "/群热度 - 获取过去30分钟的群热度\n"
        "/昨日热度图 - 获取昨日每30分钟的热度折线图和平均热度"
    ),
    type="application",
    homepage="https://github.com/Wojusensei/nonebot-plugin-group-heat",
    config=Config,
    supported_adapters={"~onebot.v11", "~milky"},
)
config = get_plugin_config(Config)


def get_group_scene(event: Event) -> Optional[Tuple[int, int]]:
    """识别群消息事件，返回 (group_id, user_id)；非群消息返回 None"""
    if OBGroupMessageEvent is not None and isinstance(event, OBGroupMessageEvent):
        return event.group_id, event.user_id
    if MilkyGroupMessageEvent is not None and isinstance(event, MilkyGroupMessageEvent):
        return event.data.peer_id, event.data.sender_id
    return None


def classify_uniseg(msg: UniMessage) -> str:
    """按通用消息段类型分类：text / sticker / file / other

    与 0.2 语义一致：取第一个可计分的消息段。
    """
    for seg in msg:
        if isinstance(seg, Text):
            return "text"
        if isinstance(seg, Emoji):
            return "sticker"
        if isinstance(seg, (Image, Video, Voice, Audio, File)):
            return "file"
    return "other"


driver = get_driver()


@driver.on_startup
async def startup():
    await init_db()
    removed = await cleanup_old_messages()
    if removed:
        logger.info(f"群热度插件清理了 {removed} 条过期消息记录")
    # 每日清理过期消息记录，防止数据库无限增长
    scheduler.add_job(
        cleanup_old_messages,
        "cron",
        hour=4, minute=30,
        id="group_heat_cleanup",
        replace_existing=True,
    )
    logger.info("群热度插件数据库初始化完成")


msg_recorder = on_message(priority=1, block=False)


@msg_recorder.handle()
async def record_message(event: Event, msg: UniMsg):
    scene = get_group_scene(event)
    if scene is None:
        return

    msg_type = classify_uniseg(msg)
    if msg_type == "other":
        return

    group_id, user_id = scene
    timestamp = datetime.now().timestamp()
    await add_message(group_id, user_id, msg_type, timestamp)


heat_cmd = on_command("群热度", priority=10, block=True)


@heat_cmd.handle()
async def handle_heat(event: Event):
    scene = get_group_scene(event)
    if scene is None:
        await heat_cmd.finish("该命令仅支持群聊")

    group_id = scene[0]
    try:
        heat = await get_recent_heat(group_id, minutes=30)
    except Exception as e:
        logger.error(f"获取群热度失败: {e}")
        await heat_cmd.finish("获取热度失败，请稍后再试")

    # 注意：finish() 会抛出 FinishedException，不要放在捕获 Exception 的 try 里，
    # 否则成功回复后还会再收到一条“获取热度失败”
    comment = get_heat_comment(heat)
    await heat_cmd.finish(f"过去30分钟的群热度：{heat:.2f}°\n{comment}")


yesterday_cmd = on_command("昨日热度图", priority=10, block=True)


@yesterday_cmd.handle()
async def handle_yesterday(event: Event):
    scene = get_group_scene(event)
    if scene is None:
        await yesterday_cmd.finish("该命令仅支持群聊")

    group_id = scene[0]
    try:
        heat_values, time_labels, avg_heat = await get_yesterday_heat(group_id)
    except Exception as e:
        logger.error(f"生成昨日热度图失败: {e}")
        await yesterday_cmd.finish("生成热度图失败，请稍后再试")

    if not heat_values:
        await yesterday_cmd.finish("暂无昨日数据，请明天再来~")

    try:
        img_path = draw_heat_line(heat_values, time_labels, avg_heat)
    except Exception as e:
        logger.error(f"绘制热度图失败: {e}")
        await yesterday_cmd.finish("生成热度图失败，请稍后再试")

    comment = get_heat_comment(avg_heat)
    msg = f"昨日群平均热度：{avg_heat:.2f}°\n{comment}"
    try:
        await UniMessage.image(path=img_path).send()
        await yesterday_cmd.finish(msg)
    finally:
        # 图片发送完毕后删除临时文件
        try:
            img_path.unlink(missing_ok=True)
        except Exception as e:
            logger.warning(f"清理热度图临时文件失败: {e}")
