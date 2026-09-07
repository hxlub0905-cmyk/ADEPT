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
@pytest.mark.parametrize("kind", uc.DEFAULT_CHARTS)
def test_every_chart_renders_valid_xml(grid, kind):
    """⚠ **預設勾的那幾張** —— 只有它們光靠 `series` 就畫得出來。散佈圖吃的
    是長表 ＋ 一份角色配置，見下面那一支。"""
    svg = uc.build_chart_svg(uc.chart_series([grid]), kind,
                             {"title": uc.CHART_LABELS[kind]})
    doc = _xml(svg)
    assert doc.documentElement.tagName == "svg"
    assert uc.CHART_LABELS[kind] in svg


def test_the_scatter_needs_a_frame_and_a_spec(grid):
    """散佈圖走的是另一條路（長表），而**兩份都要**。"""
    from d4t.core.export import chart_frame

    frame = chart_frame.build_frame([grid])
    metric = uc.chart_series([grid])["metric"]
    st = {"title": uc.CHART_LABELS[uc.CHART_SCATTER]}
    spec = '{"mark":"point","x":"x","y":"%s"}' % metric

    svg = uc.build_chart_svg({}, uc.CHART_SCATTER, st, frame=frame, spec=spec)
    _xml(svg)
    assert uc.CHART_LABELS[uc.CHART_SCATTER] in svg
    assert svg.count("<circle") == len(frame)

    # 少了 spec **要說出原因**，不是畫一張空白（同 `_empty` 那條規矩）。
    said = uc.build_chart_svg({}, uc.CHART_SCATTER, st, frame=frame)
    _xml(said)
    assert "pick x and y" in said
    # 少了長表也一樣。
    none = uc.build_chart_svg({}, uc.CHART_SCATTER, st, spec=spec)
    _xml(none)
    assert "no boxes to plot" in none


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


def test_the_heat_map_tiles_every_region_in_one_go(grid):
    """**所有區域一起鋪一次**（PEAR 的 `heat_cells(self._rois, …)`）。

    這一條以前問的是相反的事（「只畫第一群，而且要講出來」）。那個設計是
    我先製造問題再繞開它：一群鋪一次才會互相蓋，中線由全部的框一起決定就
    不會 —— 2026-09-07 使用者定調「都按照 PEAR 一樣」。
    """
    other = _note("mg", [70.0] * 6, [10, 20, 30, 40, 50, 60], [10] * 6)
    s = uc.chart_series([grid, other])
    one = uc.build_chart_svg(uc.chart_series([grid]), uc.CHART_MAP)
    two = uc.build_chart_svg(s, uc.CHART_MAP)
    assert "not shown" not in two, "不再有被藏起來的區域"
    # 兩群的名字都要出現在底下那一行 —— 圖畫的是誰，圖上要說得出來
    assert "epi" in two and "mg" in two
    # 格子真的多了（第二群不是被丟掉）
    assert two.count("<rect") > one.count("<rect")


def test_the_heat_map_says_the_colour_scale_is_shared(grid):
    """一起鋪的代價是**色階跨區域共用** —— 那件事圖上要看得到。

    不然兩個區域各自最紅的地方會被讀成一樣紅，而它們差了一整個量級。
    """
    other = _note("mg", [70.0] * 6, [10, 20, 30, 40, 50, 60], [10] * 6)
    two = uc.build_chart_svg(uc.chart_series([grid, other]), uc.CHART_MAP)
    assert "one colour scale across 2 regions" in two
    # 只有一群時不該冒出那句話（沒有「跨」可言）
    assert "one colour scale" not in uc.build_chart_svg(
        uc.chart_series([grid]), uc.CHART_MAP)


def test_the_heat_map_scale_spans_every_region(grid):
    """色條的兩端是**全部**的值，不是第一群的（PEAR 的 vmin/vmax 也是全取）。"""
    other = _note("mg", [70.0] * 6, [10, 20, 30, 40, 50, 60], [10] * 6)
    two = uc.build_chart_svg(uc.chart_series([grid, other]), uc.CHART_MAP)
    lo = min(list(grid["spread"]["stats"].values())[0] + [70.0])
    assert uc._fmt(lo) in two, "色條的下界要含到第二群那 70"


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
def test_the_region_palette_is_the_same_hues_the_canvas_uses():
    """**同一組色相、同一個順序，另一個底上的另一階**（F88 第一刀 b）。

    ⚠ 這一條以前是逐字相等。改掉是因為一組顏色服務不了兩個底：畫布那一組是
    為了**深色的 SEM 影像**取的（那一份自己的說明就寫著「都偏亮」），而這幾張
    圖畫在**白紙**上 —— 那一組在白底上八個全部對比度不到 3:1，一排 profile
    在投影機上就是這樣發虛的。往下取步救得了紙，會毀掉影像上的框。

    所以守的東西也跟著換：**身分是色相與順序**（第 3 個在哪裡都是那個藍），
    不是亮度。亮度跟著底走，各自對著自己的底驗過 —— 跟深色模式同一條規矩。
    """
    import colorsys

    from d4t.ui import theme

    def _rgb(hex_colour):
        h = hex_colour.lstrip("#")
        return [int(h[i:i + 2], 16) / 255.0 for i in (0, 2, 4)]

    def hue(hex_colour):
        """⚠ **HSV 的色相是個便宜的替身**，不是感知上的那個。

        真正量過的是 OKLCH（位移 ≤ 0.5°，記在 `REGION_COLOURS` 的說明裡，
        而重取步要重跑那支配色檢查器）。這裡用 stdlib 的 `colorsys` 是因為
        測試不該自己抄一份 OKLab 轉換 —— 它守的是「有沒有人把某一格換成
        另一個顏色」，那件事 HSV 答得出來。所以下面的容差是 12° 而不是 1°：
        往下取步時 HSV 的色相本來就會漂（實測最大 7.2°，那個綠）。
        """
        return colorsys.rgb_to_hsv(*_rgb(hex_colour))[0] * 360.0

    def light(hex_colour):
        # 相對亮度（sRGB 加權）—— 這裡只要問「誰比較深」，不必動到 OKLab。
        r, g, b = _rgb(hex_colour)
        return 0.2126 * r + 0.7152 * g + 0.0722 * b

    assert len(uc.REGION_COLOURS) == len(theme.REGION_COLORS)
    for i, (paper, image) in enumerate(
            zip(uc.REGION_COLOURS, theme.REGION_COLORS)):
        drift = abs(hue(paper) - hue(image))
        assert min(drift, 360.0 - drift) <= 12.0, i      # 同一個色相
        assert light(paper) < light(image), i            # 紙上那一階比較深


def test_every_region_colour_is_readable_on_white_paper():
    """**這一條就是「投影機上看得清楚」寫成一個數字**（F88 第一刀 b）。

    圖畫在白底上，而一條對比度 1.8:1 的細線在投影機上是看不到的 —— 舊那一組
    八個**全部**在 3:1 以下（用配色檢查器量的，2026-09-07）。3:1 是非文字
    圖形元件的通用門檻。

    ⚠ 這一條**只管畫在紙上的那一組**。`theme.REGION_COLORS` 畫在深色的 SEM
    影像上，那裡要的是反過來的東西（夠亮），所以它不在這條測試的範圍裡。
    """
    from d4t.ui.theme import contrast_ratio

    bad = [(c, round(contrast_ratio(c, "#ffffff"), 2))
           for c in uc.REGION_COLOURS if contrast_ratio(c, "#ffffff") < 3.0]
    assert not bad, bad


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
    assert uc.heat_hex(0.0) == uc.HEAT_RAMP[0]
    assert uc.heat_hex(1.0) == uc.HEAT_RAMP[-1]
    assert uc.heat_hex(-5.0) == uc.HEAT_RAMP[0]
    assert uc.heat_hex(9.0) == uc.HEAT_RAMP[-1]
    assert uc.heat_hex(float("nan")) == uc._MUTED


# --------------------------------------------------------------------------- #
# 5. 一頁 —— 版型跟盒鬚圖那一頁共用
# --------------------------------------------------------------------------- #
def test_the_page_holds_every_chart_that_was_asked_for(grid):
    from d4t.core.export import chart_frame

    metric = uc.chart_series([grid])["metric"]
    page = uc.build_charts_page(
        uc.chart_series([grid]), uc.CHARTS, "Uniformity",
        frame=chart_frame.build_frame([grid]),
        spec='{"mark":"point","x":"x","y":"%s"}' % metric)
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


# --------------------------------------------------------------------------- #
# 格子版（PEAR 的 `equal cells`，F87 第八刀）
# --------------------------------------------------------------------------- #
def test_the_heat_map_is_a_plain_grid_by_default(grid):
    """使用者 2026-09-07：「他就是示意圖，但目前顯示上會怪怪的 那個 heatmap
    框大小」→「heatmap 裡面的 equal cell（像 pear 那樣）」。

    照實鋪的每一格畫到與鄰居的中線為止 —— 間距不平均、或少了一格，相鄰兩格
    的**面積就明顯不一樣**，而**面積不是這張圖在量的東西**。PEAR 的
    `equal cells` 預設就是開的（`_paint_map_grid` 的 docstring 寫著理由：
    「那才是一張 die map 該有的樣子」）。
    """
    from d4t.core.pipeline import chart_style

    assert chart_style.DEFAULTS["equal_cells"] is True, "預設就該是格子版"
    s = uc.chart_series([grid])
    xc, yc, slots, (lo, hi) = uc.heat_lattice(s)
    assert len(slots) == len(s["groups"][0]["values"])
    assert xc and yc
    # 每一格都落在一個槽位上，而槽位的範圍就是欄數／列數
    for i, j, colour, _v in slots:
        assert 0 <= i < len(xc) and 0 <= j < len(yc)
        assert colour.startswith("#")
    assert hi >= lo


def test_the_grid_fills_the_plot_box_and_the_true_one_does_not(grid):
    """格子版**刻意不保長寬比**（它是示意圖）；照實鋪的那一版保。

    一開始只有照實鋪那一版，而它等比例置中 —— 於是一片寬扁的框陣列在圖上
    只佔中間一條，兩邊全是空白。使用者說「不用跟影像一樣大或比例一樣沒關係」。
    """
    s = uc.chart_series([grid])
    wide = uc.build_chart_svg(s, uc.CHART_MAP, {"equal_cells": True}, 640, 300)
    tall = uc.build_chart_svg(s, uc.CHART_MAP, {"equal_cells": True}, 300, 640)
    # 格子版：圖區就是 padding 之後剩下的那一塊，兩種尺寸下都鋪滿
    assert wide != tall
    for svg, w, h in ((wide, 640, 300), (tall, 300, 640)):
        assert "viewBox='0 0 %d %d'" % (w, h) in svg


def test_turning_equal_cells_off_goes_back_to_true_to_scale(grid):
    """要看真實的空間關係時退得回去 —— 兩種鋪法畫出來不一樣。"""
    s = uc.chart_series([grid])
    a = uc.build_chart_svg(s, uc.CHART_MAP, {"equal_cells": True})
    b = uc.build_chart_svg(s, uc.CHART_MAP, {"equal_cells": False})
    assert a != b


def test_the_grid_ticks_label_the_position_each_slot_stands_for(grid):
    """槽位不是線性軸（欄距被拉成一樣寬了），刻度標的是那一欄自己的座標。"""
    s = uc.chart_series([grid])
    svg = uc.build_chart_svg(s, uc.CHART_MAP,
                             {"equal_cells": True, "xticks": 5}, 640, 420)
    cx = s["groups"][0]["cx"]
    first = uc._fmt(min(cx))
    assert ">%s<" % first in svg, "第一欄的位置要出現在軸上"


def test_the_value_can_be_printed_in_each_cell_both_ways(grid):
    """`map_values` 兩種鋪法**一字不差** —— 一種印一種不印的話，那一格會
    變成「有時候有反應」。"""
    s = uc.chart_series([grid])
    for equal in (True, False):
        base = {"equal_cells": equal}
        off = uc.build_chart_svg(s, uc.CHART_MAP, base, 720, 460)
        on = uc.build_chart_svg(s, uc.CHART_MAP,
                                dict(base, map_values=True), 720, 460)
        assert on != off, equal


def test_a_cell_too_small_for_the_number_prints_nothing(grid):
    """**印一半的數字比不印糟。** 放不下就不印（PEAR 同款的守則）。"""
    s = uc.chart_series([grid])
    tiny = uc.build_chart_svg(s, uc.CHART_MAP,
                              {"equal_cells": True, "map_values": True},
                              uc.MIN_WIDTH, uc.MIN_HEIGHT)
    big = uc.build_chart_svg(s, uc.CHART_MAP,
                             {"equal_cells": True, "map_values": True},
                             900, 560)
    assert tiny.count("<text") < big.count("<text")


def test_the_heat_painted_on_the_image_is_always_true_to_scale():
    """⚠ **疊在影像上的那一層不受 `equal_cells` 影響。**

    它畫在影像上，位置要對得起那張圖 —— 拉成格子的話顏色會落在錯的地方，
    而畫面上看起來完全正常。那正是這個 repo 最貴的那種 bug。
    """
    import inspect as _inspect

    import d4t.core.steps  # noqa: F401
    from d4t.core.pipeline import get_step

    src = _inspect.getsource(get_step("output_uniformity").overlay_heat)
    assert "heat_tiles(" in src
    assert "heat_lattice(" not in src
