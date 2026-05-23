import re
from datetime import datetime
from nonebot import on_command, on_message, get_driver, require
from nonebot.adapters.onebot.v11 import Bot, Event, MessageSegment
from nonebot.adapters.onebot.v11.event import GroupMessageEvent
from nonebot.plugin import PluginMetadata
from nonebot.log import logger

from .config import Config
from nonebot import get_plugin_config
from .database import init_db, add_message, get_recent_heat, get_yesterday_heat
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
        elif seg.type in ["file", "image", "record", "video"]:
            return "file"
    return "other"


driver = get_driver()

@driver.on_startup
async def startup():
    await init_db()
    logger.info("群热度插件数据库初始化完成")


msg_recorder = on_message(priority=1, block=False)

@msg_recorder.handle()
async def record_message(bot: Bot, event: Event):
    if not isinstance(event, GroupMessageEvent):
        return
    
    group_id = event.group_id
    user_id = event.user_id
    msg_type = await get_message_type(event)
    timestamp = datetime.now().timestamp()
    
    await add_message(group_id, user_id, msg_type, timestamp)


heat_cmd = on_command("/群热度", aliases={"群热度"}, priority=10, block=True)

@heat_cmd.handle()
async def handle_heat(event: Event):
    if not isinstance(event, GroupMessageEvent):
        await heat_cmd.finish("该命令仅支持群聊")
    
    group_id = event.group_id
    try:
        heat = await get_recent_heat(group_id, minutes=30)
        comment = get_heat_comment(heat)
        await heat_cmd.finish(f"过去30分钟的群热度：{heat:.2f}°\n{comment}")
    except Exception as e:
        logger.error(f"获取群热度失败: {e}")
        await heat_cmd.finish("获取热度失败，请稍后再试")


yesterday_cmd = on_command("/昨日热度图", aliases={"昨日热度图"}, priority=10, block=True)

@yesterday_cmd.handle()
async def handle_yesterday(event: Event):
    if not isinstance(event, GroupMessageEvent):
        await yesterday_cmd.finish("该命令仅支持群聊")
    
    group_id = event.group_id
    try:
        heat_values, time_labels, avg_heat = await get_yesterday_heat(group_id)
        
        if not heat_values:
            await yesterday_cmd.finish("暂无昨日数据，请明天再来~")
        
        img_path = draw_heat_line(heat_values, time_labels, avg_heat)
        comment = get_heat_comment(avg_heat)
        
        msg = f"昨日群平均热度：{avg_heat:.2f}°\n{comment}"
        await yesterday_cmd.send(MessageSegment.image(img_path))
        await yesterday_cmd.finish(msg)
    except Exception as e:
        logger.error(f"生成昨日热度图失败: {e}")
        await yesterday_cmd.finish("生成热度图失败，请稍后再试")