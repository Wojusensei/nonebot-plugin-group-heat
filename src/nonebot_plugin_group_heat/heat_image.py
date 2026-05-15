import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np
from pathlib import Path
from typing import List


def get_cache_dir():
    from nonebot_plugin_localstore import get_cache_dir as _get_cache_dir
    cache_dir = _get_cache_dir("nonebot_plugin_group_heat")
    cache_dir.mkdir(parents=True, exist_ok=True)
    return cache_dir


def draw_heat_line(heat_values: List[float], time_labels: List[str], avg_heat: float) -> Path:
    plt.rcParams['font.sans-serif'] = ['Microsoft YaHei', 'SimHei']
    plt.rcParams['axes.unicode_minus'] = False

    fig, ax = plt.subplots(figsize=(14, 6))
    x = np.arange(len(heat_values))

    ax.plot(x, heat_values, marker='o', linestyle='-', color='#FF6B6B', linewidth=2, markersize=6)
    ax.fill_between(x, heat_values, -10, alpha=0.2, color='orange')
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

    img_path = get_cache_dir() / "yesterday_heat.png"
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