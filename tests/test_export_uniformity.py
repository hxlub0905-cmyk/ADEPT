# -*- coding: utf-8 -*-
"""d4t.core.export.uniformity_charts（F85）—— 四種圖的 SVG。

headless、零 Qt：`core` 不准 import Qt（鐵則 1），而這一份就是那條規矩的
下半場 —— 檔案裡的圖跟畫面上的圖是**兩份繪圖程式碼**，防線是它們吃同一支
`chart_series()`。所以這裡守的是：

1. 那一支資料函式（畫面與檔案唯一的共同出處）算得對、退化輸入不炸；
2. 四種圖都產得出**合法 XML**，而且「沒有東西可畫」時仍然回一張圖；
3. 鎖定範圍真的鎖得住（那是這一輪唯一非做不可的外觀設定）；
4. 顏色的**意思**沒有撞（琥珀在 d4t 已經有兩個意思了）。
"""
from __future__ import annotations

import xml.dom.minidom as minidom

import numpy as np
import pytest

from d4t.core.export import uniformity_charts as uc


def _note(region: str, values, cx, cy, rects=None, metric="glv_median"):
    n = len(values)
    rects = rects or [[int(cx[i]) - 5, int(cy[i]) - 5, 10, 10] for i in range(n)]
    return {"region": region, "prefix": region,
            "spread": {"stats": {metric: list(values)},
                       "cx": [float(v) for v in cx],
                       "cy": [float(v) for v in cy],
                       "rects": rects, "boxes": list(range(n))}}


@pytest.fixture
def grid():
    """6 × 4 的格子，左到右有梯度，其中一格是髒點。"""
    vals, cx, cy, rects = [], [], [], []
    for j in range(4):
        for i in range(6):
            x, y = 40 + i * 70, 40 + j * 70
            vals.append(112.0 + i * 2.4)
            cx.append(float(x + 20))
            cy.append(float(y + 20))
            rects.append([x, y, 40, 40])
    vals[9] += 14.0
    return _note("epi", vals, cx, cy, rects)


def _xml(svg: str):
    """畫出來的東西**要是合法 XML** —— 它會被塞進 HTML 報表。"""
    return minidom.parseString(svg)


# --------------------------------------------------------------------------- #
# 1. 資料層 —— 畫面與檔案唯一的共同出處
# --------------------------------------------------------------------------- #
def test_the_series_carries_one_point_per_box(grid):
    s = uc.chart_series([grid])
    assert s["metric"] == "glv_median"
    assert len(s["groups"]) == 1
    g = s["groups"][0]
    assert len(g["values"]) == len(g["cx"]) == len(g["cy"]) == 24


def test_each_region_gets_its_own_colour(grid):
    other = _note("mg", [70.0] * 6, [10, 20, 30, 40, 50, 60], [10] * 6)
    s = uc.chart_series([grid, other])
    assert [g["name"] for g in s["groups"]] == ["epi", "mg"]
    assert s["groups"][0]["colour"] != s["groups"][1]["colour"]


def test_a_note_without_spread_is_simply_not_plotted():
    """走 pooled、或沒開 `report` 時 `spread` 是 None。

    **空的 groups 跟「畫出來是平的」是兩件事** —— 呼叫端要說得出差別，
    所以這裡不是回一組零。
    """
    s = uc.chart_series([{"region": "epi", "spread": None}, {"nope": 1}, "junk"])
    assert s["groups"] == []


def test_positions_that_do_not_line_up_drop_the_whole_group():
    """值與位置共用索引是前提 —— 對不上就整組不畫（畫一半比不畫糟）。"""
    bad = _note("epi", [1.0, 2.0, 3.0], [0.0, 1.0, 2.0], [0.0, 1.0, 2.0])
    bad["spread"]["cx"] = [0.0, 1.0]        # 少一個
    assert uc.chart_series([bad])["groups"] == []


def test_asking_for_a_metric_nobody_measured_gives_nothing(grid):
    assert uc.chart_series([grid], metric="glv_bogus")["groups"] == []
    # 但它仍然說得出有哪些可選 —— UI 的下拉讀這個
    assert uc.chart_series([grid], metric="glv_bogus")["metrics"] == ["glv_median"]


# --------------------------------------------------------------------------- #
# 2. 四種圖都畫得出來
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize("kind", uc.CHARTS)
def test_every_chart_renders_valid_xml(grid, kind):
    svg = uc.build_chart_svg(uc.chart_series([grid]), kind,
                             {"title": uc.CHART_LABELS[kind]})
    doc = _xml(svg)
    assert doc.documentElement.tagName == "svg"
    assert uc.CHART_LABELS[kind] in svg


@pytest.mark.parametrize("kind", uc.CHARTS)
def test_nothing_to_plot_still_returns_a_picture(kind):
    """**空字串不行。** 呼叫端把它塞進 HTML，而一個消失的區塊讀起來是
    「這裡本來就沒有東西」（`boxplot` 的同一條規矩）。"""
    svg = uc.build_chart_svg({"groups": [], "metric": ""}, kind)
    _xml(svg)
    assert "no boxes to plot" in svg


def test_the_four_names_are_the_words_the_user_picked():
    """使用者 2026-09-07 定調 position profile（不是 Across the field）。"""
    assert uc.CHART_LABELS[uc.CHART_PROFILE] == "Position profile"
    assert set(uc.CHARTS) == set(uc.CHART_LABELS)


def test_the_profile_prints_the_slope_in_the_unit_it_is_measured_in(grid):
    """圖上那句話要**帶著 100** —— 那是這一輪唯一會安靜出錯的地方。"""
    svg = uc.build_chart_svg(uc.chart_series([grid]), uc.CHART_PROFILE)
    assert "/ 100 px" in svg


def test_the_heat_map_says_when_it_is_only_showing_one_region(grid):
    """兩群疊在同一張 (x, y) 上，後畫的會蓋掉先畫的 —— **那件事要講出來**。"""
    other = _note("mg", [70.0] * 6, [10, 20, 30, 40, 50, 60], [10] * 6)
    s = uc.chart_series([grid, other])
    svg = uc.build_chart_svg(s, uc.CHART_MAP)
    assert "not shown" in svg
    # 只有一群時不該冒出那句話
    assert "not shown" not in uc.build_chart_svg(uc.chart_series([grid]),
                                                 uc.CHART_MAP)


def test_the_histogram_legend_carries_each_group_n(grid):
    """兩群的框數差十倍時，同樣高的柱子講的是完全不同的事。"""
    other = _note("mg", [70.0] * 6, [10, 20, 30, 40, 50, 60], [10] * 6)
    svg = uc.build_chart_svg(uc.chart_series([grid, other]), uc.CHART_HIST)
    assert "n=24" in svg and "n=6" in svg


# --------------------------------------------------------------------------- #
# 3. 鎖定範圍 —— 唯一非做不可的外觀設定
# --------------------------------------------------------------------------- #
def test_locking_the_value_axis_really_locks_it(grid):
    """auto 縮放在看一批時是對的，兩批擺在一起就會騙人。

    這一條的做法是「同一份資料，鎖與不鎖畫出來不一樣」—— 比對刻度文字，
    因為那才是使用者讀的東西。
    """
    s = uc.chart_series([grid])
    auto = uc.build_chart_svg(s, uc.CHART_HIST)
    lock = uc.build_chart_svg(s, uc.CHART_HIST, {"vlock": (0.0, 255.0)})
    assert auto != lock
    assert ">250<" in lock or ">200<" in lock       # 鎖到 0–255 才有的刻度
    assert ">250<" not in auto


def test_a_locked_heat_range_says_it_is_locked(grid):
    """色階鎖住的時候要**在圖上說**：同一個顏色在兩張圖上是同一個灰階，
    只有鎖住才成立，而讀圖的人沒有別的線索知道。"""
    s = uc.chart_series([grid])
    assert "locked" in uc.build_chart_svg(s, uc.CHART_MAP,
                                          {"hlock": (0.0, 255.0)})
    assert "locked" not in uc.build_chart_svg(s, uc.CHART_MAP)


def test_a_lock_that_makes_no_sense_falls_back_to_auto(grid):
    """上下界寫反、寫成字、寫成 nan —— 都退回 auto，不炸也不畫出空白。"""
    s = uc.chart_series([grid])
    good = uc.build_chart_svg(s, uc.CHART_HIST)
    for bad in ((10.0, 1.0), ("a", "b"), (float("nan"), 1.0), ()):
        assert uc.build_chart_svg(s, uc.CHART_HIST, {"vlock": bad}) == good


# --------------------------------------------------------------------------- #
# 4. 顏色的意思不准撞
# --------------------------------------------------------------------------- #
def test_the_region_palette_is_the_same_one_the_canvas_uses():
    """`core` 不准 import Qt，所以這份是副本 —— **副本會漂，這條測試守它**。"""
    from d4t.ui import theme
    assert uc.REGION_COLOURS == theme.REGION_COLORS


def test_the_trend_line_is_not_any_region_colour():
    """趨勢線跟區域色同色的話，第二群的 profile 實線與它的趨勢虛線會撞。

    實測發生過（2026-09-07 第一版用琥珀，而琥珀是區域色第 2 個）。
    """
    assert uc._TREND not in uc.REGION_COLOURS


def test_the_trend_line_is_not_the_odd_one_out_colour():
    """琥珀在 d4t 已經有一個意思了：**最異常的那一格**。

    同一個顏色在同一份報表裡講兩件事，使用者得先決定現在是哪一種。
    """
    from d4t.core.export.overlay import ROI_WINNER_COLOR
    amber = "#%02x%02x%02x" % ROI_WINNER_COLOR
    assert uc._TREND != amber


def test_the_heat_ramp_never_reuses_a_region_colour():
    """熱圖上顏色的意思是「值多少」，不是「這是哪一群」。"""
    assert not (set(uc.HEAT_RAMP) & set(uc.REGION_COLOURS))


def test_the_ramp_runs_cold_to_hot_and_clamps():
    assert uc._heat_hex(0.0) == uc.HEAT_RAMP[0]
    assert uc._heat_hex(1.0) == uc.HEAT_RAMP[-1]
    assert uc._heat_hex(-5.0) == uc.HEAT_RAMP[0]
    assert uc._heat_hex(9.0) == uc.HEAT_RAMP[-1]
    assert uc._heat_hex(float("nan")) == uc._MUTED


# --------------------------------------------------------------------------- #
# 5. 一頁 —— 版型跟盒鬚圖那一頁共用
# --------------------------------------------------------------------------- #
def test_the_page_holds_every_chart_that_was_asked_for(grid):
    page = uc.build_charts_page(uc.chart_series([grid]), uc.CHARTS, "Uniformity")
    assert page.count("<svg") == len(uc.CHARTS)
    for label in uc.CHART_LABELS.values():
        assert label in page


def test_the_page_ignores_a_chart_kind_nobody_defined(grid):
    page = uc.build_charts_page(uc.chart_series([grid]),
                                ["histogram", "bogus"], "Uniformity")
    assert page.count("<svg") == 1


def test_the_boxplot_page_still_draws_its_own_charts():
    """F85 讓那一支多吃一個 `svg` 鍵 —— **既有呼叫端一個字不動**。"""
    from d4t.core.export.boxplot import build_boxplot_page
    page = build_boxplot_page(
        [{"title": "score", "series": [{"name": "a", "values": [1.0, 2.0, 3.0]}]}],
        "Batch")
    assert "<svg" in page and "score" in page
