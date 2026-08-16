from datetime import datetime
from nonebot import on_command, on_message, get_driver, get_plugin_config, require
from nonebot.adapters.onebot.v11 import Event, MessageSegment
from nonebot.adapters.onebot.v11.event import GroupMessageEvent
from nonebot.plugin import PluginMetadata
from nonebot.log import logger

require("nonebot_plugin_localstore")
require("nonebot_plugin_apscheduler")
from nonebot_plugin_apscheduler import scheduler

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
    supported_adapters={"~onebot.v11"},
)
config = get_plugin_config(Config)


async def get_message_type(event: Event) -> str:
    msg = event.get_message()
    for seg in msg:
        if seg.type == "text":
            return "text"
        elif seg.type == "face":
            return "sticker"
        elif seg.type in ("file", "image", "record", "video"):
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
async def record_message(event: Event):
    if not isinstance(event, GroupMessageEvent):
        return

    msg_type = await get_message_type(event)
    timestamp = datetime.now().timestamp()
    await add_message(event.group_id, event.user_id, msg_type, timestamp)


heat_cmd = on_command("群热度", priority=10, block=True)


@heat_cmd.handle()
async def handle_heat(event: Event):
    if not isinstance(event, GroupMessageEvent):
        await heat_cmd.finish("该命令仅支持群聊")

    try:
        heat = await get_recent_heat(event.group_id, minutes=30)
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
    if not isinstance(event, GroupMessageEvent):
        await yesterday_cmd.finish("该命令仅支持群聊")

    try:
        heat_values, time_labels, avg_heat = await get_yesterday_heat(event.group_id)
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
        await yesterday_cmd.send(MessageSegment.image(img_path))
        await yesterday_cmd.finish(msg)
    finally:
        # 图片发送完毕后删除临时文件
        try:
            img_path.unlink(missing_ok=True)
        except Exception as e:
            logger.warning(f"清理热度图临时文件失败: {e}")
