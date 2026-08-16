"""热度评价与绘图测试"""
import pytest

from nonebot_plugin_group_heat.heat_image import draw_heat_line, get_heat_comment
from nonebot_plugin_group_heat.database import BASE_HEAT


class TestHeatComment:
    @pytest.mark.parametrize("heat,expected_part", [
        (-10, "冰块"),
        (0, "冬天"),
        (5, "冬天"),
        (10, "舒适"),
        (19.9, "舒适"),
        (20, "最佳状态"),
        (29.9, "最佳状态"),
        (30, "空调"),
        (38.9, "空调"),
        (39, "高温补贴"),
        (100, "高温补贴"),
    ])
    def test_thresholds(self, heat, expected_part):
        assert expected_part in get_heat_comment(heat)


class TestDrawHeatLine:
    def test_renders_png(self):
        values = [BASE_HEAT, BASE_HEAT + 0.5, BASE_HEAT + 1.2, BASE_HEAT]
        labels = ["00:00", "00:30", "01:00", "01:30"]
        path = draw_heat_line(values, labels, avg_heat=sum(values) / len(values))
        assert path.exists()
        assert path.suffix == ".png"
        assert path.stat().st_size > 1000
        path.unlink()

    def test_unique_filenames(self):
        values = [BASE_HEAT]
        labels = ["00:00"]
        p1 = draw_heat_line(values, labels, BASE_HEAT)
        p2 = draw_heat_line(values, labels, BASE_HEAT)
        assert p1 != p2  # 回归：固定文件名会被并发请求互相覆盖
        p1.unlink()
        p2.unlink()

    def test_cjk_font_pick(self):
        from nonebot_plugin_group_heat.heat_image import _pick_cjk_font
        # 本机（macOS/Windows/装了 CJK 字体的 Linux）应能找到至少一个中文字体；
        # 找不到时返回 None 也不应报错
        font = _pick_cjk_font()
        assert font is None or isinstance(font, str)
