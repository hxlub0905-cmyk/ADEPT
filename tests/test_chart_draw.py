# F88 第二刀：角色配置 → 一張圖（`core/export/chart_draw.py`）。
"""鎖的都是不變量：畫不出來要說出原因、算不出來的那一格不畫、類別色**不
循環**、大小跟著**面積**走、兩群以上一定有圖例。

計畫書：`docs/plans/F88-graph-builder.md` §4。
"""
from __future__ import annotations

import sys
from pathlib import Path
from xml.dom import minidom

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))

from d4t.core.export import uniformity_charts as uc          # noqa: E402
from d4t.core.export.chart_draw import draw                  # noqa: E402
from d4t.core.export.chart_frame import build_frame          # noqa: E402


def _note(name, base, x0=40, cols=3, rows=2):
    n = cols * rows
    return {"region": name, "prefix": name, "spread": {
        "stats": {"glv_mean": [base + i for i in range(n)],
                  "glv_std": [1.0 + 0.4 * i for i in range(n)]},
        "cx": [float(x0 + 90 * (i % cols)) for i in range(n)],
        "cy": [float(40 + 90 * (i // cols)) for i in range(n)],
        "rects": [[x0 + 90 * (i % cols), 40 + 90 * (i // cols), 60, 60]
                  for i in range(n)],
        "boxes": list(range(n))}}


def _frame(*notes):
    return build_frame(list(notes) or [_note("epi", 110.0)])


def _xml(svg):
    return minidom.parseString(svg)


XY = {"mark": "point", "x": "glv_mean", "y": "glv_std"}


# --------------------------------------------------------------------------- #
# 1. 畫不出來的時候**說出原因**
# --------------------------------------------------------------------------- #
def test_no_spec_says_what_is_missing():
    """一張空白讀起來是「這裡本來就沒有東西」（`boxplot` 的同一條規矩）。"""
    svg = draw(_frame(), "")
    _xml(svg)
    assert "pick x and y" in svg


def test_a_column_nobody_measured_says_so_by_name():
    """欄名的驗證住在**有資料的這一側** —— 存 recipe 的時候還不知道。"""
    svg = draw(_frame(), {"mark": "point", "x": "glv_mean", "y": "nope"})
    assert "no column called 'nope'" in svg


def test_an_empty_frame_says_no_boxes():
    svg = draw(build_frame([]), XY)
    assert "no boxes to plot" in svg


# --------------------------------------------------------------------------- #
# 2. 一格框一個記號
# --------------------------------------------------------------------------- #
def test_one_mark_per_box():
    f = _frame(_note("epi", 110.0), _note("mg", 128.0, x0=400))
    svg = draw(f, XY)
    _xml(svg)
    assert svg.count("<circle") == len(f) == 12


def test_a_box_with_nothing_measured_is_not_drawn_at_zero():
    """**算不出來的那一格不畫**（不是 0、也不是 NaN）—— 一個畫在 0 的點會
    在圖上長成一群真的落在那裡的資料。"""
    f = _frame()
    f.rows[0]["glv_std"] = None
    svg = draw(f, XY)
    assert svg.count("<circle") == len(f) - 1


# --------------------------------------------------------------------------- #
# 3. 顏色
# --------------------------------------------------------------------------- #
def test_two_regions_get_two_colours_and_a_legend():
    """**顏色不能是唯一的身分線索** —— 兩群以上一定有圖例。"""
    f = _frame(_note("epi", 110.0), _note("mg", 128.0, x0=400))
    svg = draw(f, dict(XY, color="region"))
    _xml(svg)
    assert uc.REGION_COLOURS[0] in svg and uc.REGION_COLOURS[1] in svg
    assert "epi" in svg and "mg" in svg


def test_the_ninth_group_is_folded_into_other_not_given_a_repeat_colour():
    """循環的話兩群會同色，而圖例上看起來是兩列、圖上分不出來。"""
    notes = [_note("r%d" % i, 100.0 + i, x0=40 + 300 * i, cols=1, rows=1)
             for i in range(len(uc.REGION_COLOURS) + 3)]
    svg = draw(_frame(*notes), dict(XY, color="region"))
    _xml(svg)
    assert "other (3)" in svg
    for colour in uc.REGION_COLOURS:
        assert svg.count("stroke='%s'" % colour) <= 1


def test_a_number_on_colour_is_a_single_hue_ramp_by_default():
    """使用者 2026-09-07：「兩種都可 預設單色」。"""
    f = _frame()
    plain = draw(f, dict(XY, color="glv_mean"))
    rainbow = draw(f, dict(XY, color="glv_mean"), {"ramp": "rainbow"})
    assert uc.seq_hex(1.0) in plain
    assert uc.heat_hex(1.0) in rainbow
    assert plain != rainbow


# --------------------------------------------------------------------------- #
# 4. 大小
# --------------------------------------------------------------------------- #
def test_size_follows_the_area_not_the_radius():
    """半徑線性放大時，兩倍的值看起來是四倍 —— 那張圖說了一件錯的事。"""
    import math
    import re

    f = _frame()
    svg = draw(f, dict(XY, size="glv_mean"), {"point_size": 4.0})
    radii = sorted(float(r) for r in re.findall(r"r='([0-9.]+)'", svg))
    assert radii[0] == round(4.0 * math.sqrt(0.25), 2)
    assert radii[-1] == round(4.0 * math.sqrt(4.0), 2)


def test_a_category_never_drives_the_size():
    """「region B 比 region A 大」沒有意義。"""
    f = _frame(_note("epi", 110.0), _note("mg", 128.0, x0=400))
    svg = draw(f, dict(XY, size="region"), {"point_size": 3.0})
    assert svg.count("r='3.00'") == len(f)


# --------------------------------------------------------------------------- #
# 5. 軸
# --------------------------------------------------------------------------- #
def test_a_category_column_on_an_axis_becomes_slots_in_first_seen_order():
    """區域的順序是使用者在畫布上接線的順序，不是字母序 —— 而那個順序在別的
    圖上（盒鬚圖、圖例）也是一樣的。"""
    f = _frame(_note("zulu", 110.0), _note("alpha", 128.0, x0=400))
    svg = draw(f, {"mark": "point", "x": "region", "y": "glv_mean"})
    _xml(svg)
    assert svg.index(">zulu<") < svg.index(">alpha<")


def test_the_axis_names_default_to_the_columns_they_show():
    svg = draw(_frame(), XY)
    assert "glv_mean" in svg and "glv_std" in svg


def test_a_locked_value_scale_is_obeyed_on_the_side_axis():
    """兩批要並排比的時候，鎖住的照鎖的（同 `_span`）。"""
    loose = draw(_frame(), XY)
    locked = draw(_frame(), XY, {"vlock": (0.0, 100.0)})
    assert locked != loose
    assert ">100<" in locked
