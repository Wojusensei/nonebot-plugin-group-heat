import uuid
from pathlib import Path
from typing import List

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib import font_manager
from nonebot import require

require("nonebot_plugin_localstore")
import nonebot_plugin_localstore as store

from .database import BASE_HEAT

CACHE_DIR = store.get_plugin_cache_dir()
CACHE_DIR.mkdir(parents=True, exist_ok=True)

# 常见中文字体（覆盖 Windows / macOS / Linux 发行版）
_CJK_FONT_CANDIDATES = [
    "Microsoft YaHei", "SimHei",            # Windows
    "PingFang SC", "Hiragino Sans GB",      # macOS
    "Noto Sans CJK SC", "WenQuanYi Micro Hei", "WenQuanYi Zen Hei",  # Linux
    "Source Han Sans SC", "Source Han Sans CN",
]


def _pick_cjk_font() -> str | None:
    installed = {f.name for f in font_manager.fontManager.ttflist}
    for name in _CJK_FONT_CANDIDATES:
        if name in installed:
            return name
    return None


def _apply_cjk_font():
    font = _pick_cjk_font()
    if font:
        plt.rcParams['font.sans-serif'] = [font]
    else:
        # 没有可用中文字体时仍照常渲染（中文会显示为方框），但保证负号正常
        plt.rcParams['font.sans-serif'] = _CJK_FONT_CANDIDATES
    plt.rcParams['axes.unicode_minus'] = False


def draw_heat_line(heat_values: List[float], time_labels: List[str], avg_heat: float) -> Path:
    _apply_cjk_font()

    fig, ax = plt.subplots(figsize=(14, 6))
    x = list(range(len(heat_values)))

    ax.plot(x, heat_values, marker='o', linestyle='-', color='#FF6B6B', linewidth=2, markersize=6)
    ax.fill_between(x, heat_values, BASE_HEAT, alpha=0.2, color='orange')
    ax.axhline(y=avg_heat, color='blue', linestyle='--', linewidth=1.5, label=f'平均热度: {avg_heat:.2f}')

    ax.set_xlabel('时间 (每30分钟)', fontsize=12)
    ax.set_ylabel('热度值', fontsize=12)
    ax.set_title('昨日群热度变化趋势图', fontsize=14, fontweight='bold')

    tick_step = max(1, len(time_labels) // 12)
    ax.set_xticks(x[::tick_step])
    ax.set_xticklabels(time_labels[::tick_step], rotation=45, ha='right', fontsize=8)

    ax.grid(True, alpha=0.3)
    ax.legend(loc='upper right')
    plt.tight_layout()

    # 随机文件名，避免多个群同时请求时互相覆盖
    img_path = CACHE_DIR / f"yesterday_heat_{uuid.uuid4().hex[:10]}.png"
    plt.savefig(img_path, dpi=100, bbox_inches='tight')
    plt.close(fig)

    return img_path


def get_heat_comment(heat: float) -> str:
    if heat < 0:
        return "群成冰块啦，群主快开暖气"
    elif heat < 10:
        return "是冬天到了吗，好冷www"
    elif heat < 20:
        return "温度非常舒适，大家继续努力~"
    elif heat < 30:
        return "群热度达到最佳状态！"
    elif heat < 39:
        return "好热，群主快开空调！"
    else:
        return "请发送高温补贴喵。。"
