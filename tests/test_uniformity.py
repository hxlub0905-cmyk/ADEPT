# -*- coding: utf-8 -*-
"""d4t.core.algo.uniformity（F85，vendored from PEAR）。

headless —— 零 Qt、零影像 IO，所以它在沒有圖形環境的機器上也跑得完
（PEAR `CLAUDE.md` §1 的同一條規矩，d4t 是鐵則 1）。

這一份守三件事，而**第三件是這一輪唯一會安靜出錯的地方**：

1. 平的就是 0、斜的算得準、退化輸入不 raise；
2. `jitter_tolerance` 只在**真的有抖動**時合併 —— 稀疏的分布不准動；
3. **斜率的單位是「每 100 px」**。拿掉那個 100，數字不會變成錯的，
   它會變成 0.00x —— 而那在特徵表上讀起來是「很平」。
"""
from __future__ import annotations

import numpy as np
import pytest

from d4t.core.algo import uniformity as u


# --------------------------------------------------------------------------- #
# 散多開
# --------------------------------------------------------------------------- #
def test_a_flat_group_is_zero_on_every_number():
    """完全一樣的框 → range / cv 全部 0。**這是使用者要讀的那一句話。**"""
    s = u.uniformity_stats([120.0, 120.0, 120.0, 120.0])
    assert s["n"] == 4
    assert s["range"] == 0.0
    assert s["range_pct"] == 0.0
    assert s["cv_pct"] == 0.0


def test_the_percentages_are_of_the_mean():
    """90/100/110 → 全距 20 = 平均的 20%；CV 是 std/mean。"""
    s = u.uniformity_stats([90.0, 100.0, 110.0])
    assert s["mean"] == pytest.approx(100.0)
    assert s["range"] == pytest.approx(20.0)
    assert s["range_pct"] == pytest.approx(20.0)
    assert s["cv_pct"] == pytest.approx(np.std([90, 100, 110]))


def test_a_mean_at_zero_does_not_give_infinity():
    """`diff` 那條流的平均就在 0 附近 —— 百分比沒有意義時回 0，不是 inf。

    inf 會一路流進 CSV 與分數表達式，而它在那兩個地方都不會出錯，只會
    讓每一顆的分數變成 inf。
    """
    s = u.uniformity_stats([-5.0, 0.0, 5.0])
    assert np.isfinite(s["range_pct"]) and s["range_pct"] == 0.0
    assert np.isfinite(s["cv_pct"]) and s["cv_pct"] == 0.0


@pytest.mark.parametrize("values", [[], [7.0], [np.nan, np.inf]])
def test_degenerate_input_returns_zeros_instead_of_raising(values):
    """空的、一格、全是 NaN —— 使用者剛放下第一個區域時天天發生。"""
    s = u.uniformity_stats(values)
    assert s["range"] == 0.0 and s["cv_pct"] == 0.0
    assert all(np.isfinite(v) for v in s.values())


def test_nan_boxes_are_dropped_not_propagated():
    """混進一個 NaN 不該把整組統計變成 NaN（F19：算不出來的那一格不寫）。"""
    s = u.uniformity_stats([10.0, np.nan, 20.0])
    assert s["n"] == 2
    assert s["range"] == pytest.approx(10.0)


# --------------------------------------------------------------------------- #
# 有沒有斜掉
# --------------------------------------------------------------------------- #
def test_a_flat_field_has_no_slope():
    assert u.slope_per_100px([0.0, 50.0, 100.0], [80.0, 80.0, 80.0]) == 0.0


def test_the_slope_is_per_100_px_not_per_px():
    """**這一條就是那個 100 的防線。**

    每 100 px 升 10 灰階的斜坡：正確答案是 10.0。改成每 px 的話這裡是 0.1
    —— 而 0.1 在真實影像上是 0.001 那種數字，特徵表印出來是 0.000，
    讀起來是「很平」，**而且沒有任何錯誤訊息**。
    """
    x = [0.0, 100.0, 200.0, 300.0]
    y = [10.0, 20.0, 30.0, 40.0]
    assert u.slope_per_100px(x, y) == pytest.approx(10.0)
    assert u.SLOPE_UNIT_PX == 100.0


def test_the_slope_keeps_its_sign():
    """往下的斜坡是負的 —— 「哪一邊比較亮」是使用者要的資訊之一。"""
    assert u.slope_per_100px([0.0, 100.0], [50.0, 40.0]) == pytest.approx(-10.0)


def test_a_single_box_has_no_slope_at_all():
    """回 ``None``，**不是 0** —— 「問不出來」跟「很平」在報表上必須分得開。"""
    assert u.slope_per_100px([5.0], [9.0]) is None


def test_boxes_stacked_on_one_column_have_no_slope_along_that_axis():
    """一整欄的框共用一個 X：沿 X 問不出傾斜（分母是 0）。"""
    assert u.slope_per_100px([40.0, 40.0, 40.0], [1.0, 2.0, 3.0]) is None


def test_linear_trend_rejects_mismatched_lengths():
    """值與位置共用索引是所有位置計算的前提 —— 對不上就回 None，不亂配。"""
    assert u.linear_trend([1.0, 2.0], [1.0, 2.0, 3.0]) is None


# --------------------------------------------------------------------------- #
# 框的中心
# --------------------------------------------------------------------------- #
def test_centres_keep_the_order_they_came_in():
    cx, cy = u.rect_centers([(0, 0, 10, 20), (100, 50, 10, 20)])
    assert list(cx) == [5.0, 105.0]
    assert list(cy) == [10.0, 60.0]


# --------------------------------------------------------------------------- #
# 抖動容差 —— 第二個會安靜出錯的地方
# --------------------------------------------------------------------------- #
def test_jitter_is_merged_when_the_gaps_really_do_step():
    """三欄，每欄的框差 1–2 px，欄距 100 px。容差要落在那一階中間。"""
    tol = u.jitter_tolerance([0.0, 1.0, 2.0, 100.0, 101.0, 102.0,
                              200.0, 201.0, 202.0])
    assert 2.0 < tol < 98.0


def test_a_genuinely_sparse_layout_is_never_merged():
    """等距散開的五個位置**不是抖動** —— 合併它等於把資料改掉。

    這一條與上面那一條是一對：只留其中一條的話，把 4.0 那道門檻拿掉
    （或設成 1.0）測試照樣全綠，而每一個稀疏的版面都會被壓成一欄。
    """
    assert u.jitter_tolerance([0.0, 10.0, 20.0, 30.0, 40.0]) == 0.0


def test_merely_uneven_spacing_is_not_jitter_either():
    """間距 10 / 12 / 15 / 20 —— 不平均，但**沒有階梯**，所以不准合併。

    ⚠ 這一條是突變測試逼出來的。原本我以為
    `test_a_genuinely_sparse_layout_is_never_merged` 守著那道 4 倍門檻，
    實測**把 4.0 改成 1.0，整份測試照樣全綠** —— 因為等距的那一組是被
    ``i < 1`` 那道門擋掉的，根本走不到倍率那一行。

    這一組的最大倍率是 1.33（``i = 2``，過得了第一道門），所以它是**唯一**
    真的踩在 4.0 上的輸入。門檻一鬆，五個位置會被壓成兩欄。
    """
    assert u.jitter_tolerance([0.0, 10.0, 22.0, 37.0, 57.0]) == 0.0


def test_one_small_gap_among_large_ones_is_a_missing_box_not_a_wobble():
    """一堆大間距裡混一個小的 = 少放了一個框（``i >= 1`` 那道門擋的）。"""
    assert u.jitter_tolerance([0.0, 1.0, 100.0, 200.0, 300.0]) == 0.0


@pytest.mark.parametrize("pos", [[], [1.0], [1.0, 2.0]])
def test_too_few_positions_to_tell(pos):
    assert u.jitter_tolerance(pos) == 0.0


def test_clustering_uses_the_mean_of_each_knot():
    got = u.cluster_positions([0.0, 2.0, 100.0, 102.0], tol=5.0)
    assert list(got) == [1.0, 101.0]


def test_zero_tolerance_keeps_every_distinct_centre():
    got = u.cluster_positions([0.0, 2.0, 100.0], tol=0.0)
    assert list(got) == [0.0, 2.0, 100.0]


# --------------------------------------------------------------------------- #
# 鋪磚（heat map 的格子）
# --------------------------------------------------------------------------- #
def test_cell_edges_tile_the_axis_with_no_gap_and_no_overlap():
    """相鄰的格子共用一條邊 —— 那正是「一片梯度看起來是一片」的前提。"""
    centres, edges = u.cell_edges([10.0, 30.0, 50.0])
    assert list(centres) == [10.0, 30.0, 50.0]
    assert edges.size == centres.size + 1
    assert list(edges) == [0.0, 20.0, 40.0, 60.0]


def test_a_lone_centre_gets_a_placeholder_cell():
    """沒有鄰居可量 → 1 px 的格子，呼叫端拿框自己的尺寸去換。"""
    centres, edges = u.cell_edges([42.0])
    assert list(centres) == [42.0]
    assert list(edges) == [41.5, 42.5]


def test_cell_boxes_come_back_aligned_with_the_rects():
    boxes = u.cell_boxes([(0, 0, 10, 10), (100, 0, 10, 10), (200, 0, 10, 10)])
    assert len(boxes) == 3
    # 中間那格的左右邊界落在跟鄰居的中線上
    assert boxes[1][0] == pytest.approx(55.0)
    assert boxes[1][2] == pytest.approx(155.0)


def test_cell_boxes_are_clipped_to_the_image():
    boxes = u.cell_boxes([(0, 0, 10, 10), (100, 0, 10, 10)], bounds=(110, 20))
    assert boxes[0][0] >= 0.0 and boxes[0][1] >= 0.0
    assert boxes[-1][2] <= 110.0 and boxes[-1][3] <= 20.0


def test_no_rects_no_boxes():
    assert u.cell_boxes([]) == []


# --------------------------------------------------------------------------- #
# profile 線
# --------------------------------------------------------------------------- #
def test_a_column_of_boxes_collapses_into_one_point():
    """兩欄各兩格 → 兩個點，值是各欄的平均。**那條線才讀得出平不平。**"""
    pos, mean = u.profile_by_position([0.0, 0.0, 100.0, 100.0],
                                      [1.0, 3.0, 5.0, 7.0])
    assert list(pos) == [0.0, 100.0]
    assert list(mean) == [2.0, 6.0]


def test_hand_placed_columns_still_collapse_into_one_point_each():
    """中心差 1 px 的同一欄不該裂成兩欄（裂了就是一欄一個轉折）。"""
    pos, mean = u.profile_by_position(
        [0.0, 1.0, 100.0, 101.0, 200.0, 201.0],
        [1.0, 3.0, 5.0, 7.0, 9.0, 11.0])
    assert pos.size == 3
    assert list(mean) == [2.0, 6.0, 10.0]


def test_profile_drops_boxes_whose_value_is_missing():
    pos, mean = u.profile_by_position([0.0, 100.0], [np.nan, 5.0])
    assert list(pos) == [100.0]
    assert list(mean) == [5.0]


def test_profile_with_nothing_to_plot():
    pos, mean = u.profile_by_position([], [])
    assert pos.size == 0 and mean.size == 0
