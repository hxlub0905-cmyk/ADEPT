# F88 第二刀：角色配置 → 一張圖（`core/export/chart_draw.py`）。
"""鎖的都是不變量：畫不出來要說出原因、算不出來的那一格不畫、類別色**不
循環**、大小跟著**面積**走、兩群以上一定有圖例。

計畫書：`docs/history/plans/F88-graph-builder.md` §4。
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


# --------------------------------------------------------------------------- #
# 6. 三種記號（F88 第三刀）
# --------------------------------------------------------------------------- #
def test_every_mark_in_the_vocabulary_has_someone_who_draws_it():
    """`chart_spec.MARKS` 說有哪幾個字，`chart_draw._MARKS` 說每個字怎麼畫。

    少一支的症狀是「那張圖畫不出來，而畫面上不說為什麼」—— 所以兩邊要對齊。
    """
    from d4t.core.export import chart_draw
    from d4t.core.pipeline import chart_spec

    assert set(chart_draw._MARKS) == set(chart_spec.MARKS)


def test_a_line_is_drawn_in_order_of_the_bottom_axis():
    """長表的列序是「哪個區域的第幾格框」。照那個順序連起來的話，線會在圖上
    來回折 —— 而那是一團看起來有意義的雜訊。"""
    import re

    f = _frame()
    # 故意把列序打亂：畫出來的線**不該**跟著亂。
    f.rows.reverse()
    svg = draw(f, {"mark": "line", "x": "glv_mean", "y": "glv_std"})
    _xml(svg)
    pts = re.search(r"<polyline points='([^']+)'", svg).group(1)
    xs = [float(p.split(",")[0]) for p in pts.split(" ")]
    assert xs == sorted(xs)


def test_one_line_per_colour_group():
    """「一列一條線」就是 `Colour = row`（計畫書 §9-2）。"""
    f = _frame(_note("epi", 110.0), _note("mg", 128.0, x0=400))
    svg = draw(f, {"mark": "line", "x": "glv_mean", "y": "glv_std",
                   "color": "region"})
    _xml(svg)
    assert svg.count("<polyline") == 2


def test_a_group_whose_first_value_is_zero_still_gets_its_own_colour():
    """⚠ **`0` 是一個值，不是「沒有值」。**

    `row` / `col` 的第一格就是 0，而第一版寫的是 ``row.get(column) or ""``
    —— 於是第 0 列拿不到自己的顏色（畫出來是灰的），而圖例上它**有**顏色。
    render 出來才看到的。
    """
    f = _frame(_note("epi", 110.0, cols=2, rows=2))
    svg = draw(f, dict(XY, color="row"))
    _xml(svg)
    # 第 0 列與第 1 列各拿一個區域色，沒有人是那個「認不得」的灰
    assert uc.REGION_COLOURS[0] in svg and uc.REGION_COLOURS[1] in svg
    from d4t.core.export.chart_draw import _MUTED
    assert "stroke='%s'" % _MUTED not in svg


def test_bars_in_one_slot_sit_side_by_side_never_on_top_of_each_other():
    """疊起來的長條只有最底下那一段是從同一條基線量的，而這張圖問的是
    「誰比較高」。第一版只照顏色分群並排，於是同一群裡落在同一個槽的三格框
    **疊在一起畫**，看起來剛好像一張堆疊長條圖 —— render 出來才看到的。
    """
    import re

    f = _frame(_note("epi", 110.0, cols=2, rows=3))     # 一個 col 三格框
    svg = draw(f, {"mark": "bar", "x": "col", "y": "glv_mean"})
    _xml(svg)
    # ⚠ 只挑長條：圖區的外框也是一個 `<rect>`（第一版忘了，於是「所有長條
    # 一樣寬」那一條被外框的 564 px 弄紅）。長條是唯一帶 `fill-opacity` 的。
    bars = re.findall(r"<rect x='([0-9.]+)' y='[0-9.]+' width='([0-9.]+)' "
                      r"height='[0-9.]+' fill='[^']+' fill-opacity=", svg)
    assert len(bars) == len(f)
    # 沒有兩根重疊（左緣排序之後，前一根的右緣不超過下一根的左緣）
    spans = sorted((float(x), float(x) + float(w)) for x, w in bars)
    for (_l0, r0), (l1, _r1) in zip(spans, spans[1:]):
        assert r0 <= l1 + 0.01, spans


def test_bars_are_all_the_same_width():
    """寬度會被讀成一種意思，而這張圖上它什麼都不是。"""
    import re

    f = _frame(_note("epi", 110.0, cols=3, rows=2))
    svg = draw(f, {"mark": "bar", "x": "col", "y": "glv_mean"})
    widths = {w for w in re.findall(
        r"<rect x='[0-9.]+' y='[0-9.]+' width='([0-9.]+)' height='[0-9.]+' "
        r"fill='[^']+' fill-opacity=", svg)}
    assert len(widths) == 1, widths


def test_a_numeric_axis_used_as_slots_is_still_in_number_order():
    """長條圖把一條數值軸當槽用時，「第一次出現的順序」是長表的列序 ——
    於是 125 那根會落在 115 左邊，而那張圖看起來完全正常。"""
    from d4t.core.export.chart_draw import _Band

    band = _Band(["125", "115", "120"])
    assert band.slots == ["115", "120", "125"]
    assert band.numeric


def test_too_many_slots_thin_the_labels_but_never_the_marks():
    """18 個標籤擠在 580 px 上會疊成一條看不懂的黑線（render 出來才看到）。"""
    from d4t.core.export.chart_draw import _Band

    band = _Band([str(i) for i in range(40)])
    assert len(band.slots) == 40                 # 記號一個都不少
    assert len(band.ticks(5)) < 40               # 標籤跳著標


def test_size_is_not_offered_to_a_line_or_a_bar():
    """一條線沒有大小，而一根長條的寬度是版面決定的、不是資料。"""
    from d4t.core.pipeline import chart_spec

    assert chart_spec.uses({"mark": "point"}, "size")
    assert not chart_spec.uses({"mark": "line"}, "size")
    assert not chart_spec.uses({"mark": "bar"}, "size")


# --------------------------------------------------------------------------- #
# 7. 盒子與格子（F88 第四刀）
# --------------------------------------------------------------------------- #
def test_a_box_per_slot_with_the_median_inside_it():
    import re

    f = _frame(_note("epi", 110.0), _note("mg", 128.0, x0=400))
    svg = draw(f, {"mark": "box", "x": "region", "y": "glv_mean"})
    _xml(svg)
    # 一個區域一個盒子 ＋ 一條中位數線
    bodies = re.findall(r"<rect x='[0-9.]+' y='[0-9.]+' width='[0-9.]+' "
                        r"height='[0-9.]+' fill='[^']+' fill-opacity=", svg)
    assert len(bodies) == 2
    # ⚠ **不能數 `<line`** —— `_ylabels` 順手畫的橫格線也是 `<line`
    # （第一版數到 5）。中位數那一條的記號是它穿著區域色。
    medians = [ln for ln in re.findall(r"<line [^>]*>", svg)
               if any("stroke='%s'" % c in ln for c in uc.REGION_COLOURS)]
    assert len(medians) == 2


def test_the_box_statistics_are_the_ones_boxplot_already_defined():
    """⚠ **不在這裡再算一次。** `box_stats` 已經定死了「鬚的端點是落在
    1.5×IQR 之內的**真實資料點**，不是算出來的柵欄」—— 差別在圖上看得見。
    各算一份的那天，同一份報表裡兩張盒鬚圖的鬚會不一樣長。
    """
    from d4t.core.export.boxplot import box_stats

    f = _frame()
    vals = [r["glv_mean"] for r in f.rows]
    st = box_stats(vals)
    svg = draw(f, {"mark": "box", "x": "region", "y": "glv_mean"},
               {"vlock": (st["lo"], st["hi"])})
    # 鬚鎖在資料的端點上 ⇒ 兩端剛好貼著圖區
    _xml(svg)
    assert "<path" in svg


def test_whiskers_can_be_turned_off():
    f = _frame()
    on = draw(f, {"mark": "box", "x": "region", "y": "glv_mean"})
    off = draw(f, {"mark": "box", "x": "region", "y": "glv_mean"},
               {"whiskers": False})
    assert "<path" in on and "<path" not in off


def test_cells_need_a_colour_because_a_grid_of_nothing_says_nothing():
    """一片沒有顏色的格子跟「還沒挑完」在畫面上長得一模一樣。"""
    from d4t.core.pipeline import chart_spec

    assert chart_spec.missing_roles(
        '{"mark":"cell","x":"col","y":"row"}') == ["color"]
    svg = draw(_frame(), {"mark": "cell", "x": "col", "y": "row"})
    assert "pick color" in svg


def test_one_cell_per_box_on_a_grid_of_slots():
    import re

    f = _frame(_note("epi", 110.0, cols=3, rows=2))
    svg = draw(f, {"mark": "cell", "x": "col", "y": "row",
                   "color": "glv_mean"})
    _xml(svg)
    # ⚠ 圖例的色塊也是 `<rect … fill='#…'/>`（第一版數到 7）。格子的座標是
    # 兩位小數，圖例的是整數 —— 那是這兩者在字串上唯一穩定的差別。
    cells = re.findall(r"<rect x='[0-9]+\.[0-9]{2}' y='[0-9]+\.[0-9]{2}' "
                       r"width='[0-9]+\.[0-9]{2}' height='[0-9]+\.[0-9]{2}' "
                       r"fill='#[0-9a-f]{6}'/>", svg)
    assert len(cells) == len(f) == 6


def test_a_slot_with_no_box_is_left_blank_not_painted_at_zero():
    """留白說的是「這裡沒有量到」；畫成色階最低的那一格說的是「這裡很低」。"""
    import re

    f = _frame(_note("epi", 110.0, cols=3, rows=2))
    f.rows.pop()                                  # 少一格
    svg = draw(f, {"mark": "cell", "x": "col", "y": "row",
                   "color": "glv_mean"})
    cells = re.findall(r"<rect x='[0-9]+\.[0-9]{2}' y='[0-9]+\.[0-9]{2}' "
                       r"width='[0-9]+\.[0-9]{2}' height='[0-9]+\.[0-9]{2}' "
                       r"fill='#[0-9a-f]{6}'/>", svg)
    assert len(cells) == 5


def test_the_cell_labels_follow_the_heat_map_s_own_rule():
    """門檻、字重、以及「淺底印深字、深底印白字」**跟熱圖同一份**
    （`_svg_map` ＋ `_is_dark`）—— 第一版在這裡自己寫了一條 `t > 0.55`，
    那就是同一句話長出兩種意思的起點。"""
    f = _frame(_note("epi", 110.0, cols=3, rows=2))
    spec = {"mark": "cell", "x": "col", "y": "row", "color": "glv_mean"}
    plain = draw(f, spec)
    shown = draw(f, spec, {"map_values": True})
    assert "<text" in shown and shown != plain
    assert "font-weight='700'" in shown
    # 深的那一端印白字（熱圖用的是同一個 `#ffffff` / `#1f2430`）
    assert "fill='#ffffff'" in shown and "fill='#1f2430'" in shown


# --------------------------------------------------------------------------- #
# 8. 「這一格改得到這張圖嗎」那張表不准漂（F88 第五刀）
# --------------------------------------------------------------------------- #
#: 每一種記號拿來試的那一份 spec（欄名對得上 `_frame()`）。
_SPEC_FOR = {
    "point": {"mark": "point", "x": "glv_mean", "y": "glv_std",
              "size": "glv_mean"},
    "line": {"mark": "line", "x": "glv_mean", "y": "glv_std"},
    "bar": {"mark": "bar", "x": "col", "y": "glv_mean"},
    "box": {"mark": "box", "x": "region", "y": "glv_mean"},
    "cell": {"mark": "cell", "x": "col", "y": "row", "color": "glv_mean"},
}

#: 那一格「改動」長什麼樣（預設 -> 另一個值）。
_MOVE = {
    # log 軸：`_SPEC_FOR` 的 Y 全部是正的，所以每一種記號都動得到
    # （格子的 Y 是槽 —— 那一個本來就不該動，而表上也沒有列它）。
    "yscale": {"yscale": "log"},
    "slot_order": {"slot_order": "desc"},
    # ⚠ **兩個值**：落在範圍外的線刻意不畫（`draw_refs`），而 `_SPEC_FOR`
    # 裡有的記號 Y 是 `glv_mean`（110–115）、有的是 `glv_std`（1–3）。
    # 一個值只蓋得到一半，而那一半會被讀成「這個記號沒讀這一格」。
    "ref_lines": {"ref_lines": "112, 2"},
    "whiskers": {"whiskers": False},
    "map_values": {"map_values": True},
    "points": {"points": False},
    "point_fill": {"point_fill": True},
    "fill_strength": {"fill_strength": 2.5},
    "fill_color": {"fill_color": "#123456"},
}


def test_the_mark_table_matches_what_the_drawing_code_actually_reads():
    """**兩個方向都測。**

    `uniformity_charts.CUSTOM_BY_MARK` 說「這一格哪幾種記號真的讀它」，而
    設定編輯器照它決定要不要顯示那一列。少測一邊的話那張表就只是一段註解：

    * 列了卻沒人讀 ⇒ 使用者改一格**什麼都不會發生**；
    * 讀了卻沒列 ⇒ 那一格在編輯器裡是**收起來**的，而它在檔案裡有作用。

    第二種是比較貴的那一個 —— 它是「畫面上改不到一個真的會變的東西」。
    """
    f = _frame(_note("epi", 110.0, cols=3, rows=2),
               _note("mg", 128.0, x0=400, cols=3, rows=2))
    for key, marks in uc.CUSTOM_BY_MARK.items():
        for mark, spec in _SPEC_FOR.items():
            base = draw(f, spec)
            moved = draw(f, spec, dict(_MOVE[key]))
            reads = moved != base
            assert reads == (mark in marks), (
                "%s / %s：表上說 %s，實際上 %s"
                % (key, mark, "讀" if mark in marks else "不讀",
                   "讀了" if reads else "沒讀"))


def test_every_mark_is_covered_by_that_test():
    """加一種記號而忘了在上面那張表裡試它，症狀是「那條測試照樣綠」。"""
    from d4t.core.pipeline import chart_spec

    assert set(_SPEC_FOR) == set(chart_spec.MARKS)
    assert set(_MOVE) == set(uc.CUSTOM_BY_MARK)


# --------------------------------------------------------------------------- #
# 9. log 軸與排序（F89-5）
# --------------------------------------------------------------------------- #
def _spread(values):
    """一批一列一顆的結果（值差好幾個數量級）。"""
    from d4t.core.export.chart_frame import build_lot_frame

    return build_lot_frame([
        {"defect_id": "d%d" % i, "ok": True, "score": float(i), "bin": None,
         "features": {"v": v}} for i, v in enumerate(values)])


def test_a_log_axis_puts_the_decades_on_the_ticks():
    """缺陷尺寸、粒徑、計數跨兩三個數量級是常態，而線性軸上它們全部擠在最
    下面一條 —— 那張圖畫得出來，只是什麼都看不到。"""
    f = _spread([1.0, 12.0, 130.0, 1400.0])
    spec = {"mark": "point", "x": "score", "y": "v"}
    plain = draw(f, spec)
    logged = draw(f, spec, {"yscale": "log"})
    _xml(logged)
    assert logged != plain
    assert "(log)" in logged, "軸名要說出它是 log"
    for decade in (">1<", ">10<", ">100<", ">1000<"):
        assert decade in logged, decade


def test_zero_and_negatives_are_left_out_and_the_axis_says_how_many():
    """畫在軸底的話讀起來是「它很小」，而真相是「它畫不出來」。一張安靜少了
    三顆點的圖，跟一張本來就只有那幾顆的圖長得一模一樣。"""
    f = _spread([1.0, 10.0, 0.0, -5.0])
    svg = draw(f, {"mark": "point", "x": "score", "y": "v"}, {"yscale": "log"})
    _xml(svg)
    assert svg.count("<circle") == 2
    assert "2 not shown" in svg


def test_bars_can_be_sorted_by_value_and_the_labels_follow():
    """⚠ 重排要在**畫刻度之前**。第一版在 `_bars` 裡才排，而 `_ticks` 已經
    在 `_Plot` 的建構子裡跑過 —— 長條照新順序擺、標籤照舊順序印，兩邊對不
    起來。那比不排序糟得多：它畫得出來，而且是錯的。
    """
    import re

    f = _spread([30.0, 5.0, 900.0, 1.0])
    spec = {"mark": "bar", "x": "defect_id", "y": "v"}
    order = lambda st: re.findall(r">(d\d)</text>", draw(f, spec, st))  # noqa: E731

    assert order({}) == ["d0", "d1", "d2", "d3"]
    assert order({"slot_order": "asc"}) == ["d3", "d1", "d0", "d2"]
    assert order({"slot_order": "desc"}) == ["d2", "d0", "d1", "d3"]


def test_sorting_never_touches_a_scatter_or_a_wafer_map():
    """散佈圖排過之後 X 軸不再是那一欄的值（說謊）；格子排過之後 wafer map
    的兩條軸被打亂，而那張圖的整個意思就是「哪一格在哪裡」。"""
    f = _spread([30.0, 5.0, 900.0, 1.0])
    for spec in ({"mark": "point", "x": "defect_id", "y": "v"},
                 {"mark": "line", "x": "defect_id", "y": "v"},
                 {"mark": "cell", "x": "defect_id", "y": "bin", "color": "v"}):
        assert draw(f, spec, {"slot_order": "desc"}) == draw(f, spec), \
            spec["mark"]


def test_a_slot_with_no_value_sorts_last_not_lowest():
    """它不是「最小的那一個」，它是「沒有量到」。"""
    import re

    f = _spread([30.0, 5.0, 900.0])
    f.rows.append({"defect_id": "zz", "ok": True, "score": 9.0, "bin": None,
                   "v": None})
    # ⚠ 只挑**槽的標籤** —— 刻度數字與軸名也是 `<text>`（第一版數到 `v`）。
    svg = draw(f, {"mark": "bar", "x": "defect_id", "y": "v"},
               {"slot_order": "asc"})
    slots = [t for t in re.findall(r">(\w+)</text>", svg)
             if t in ("d0", "d1", "d2", "zz")]
    assert slots == ["d1", "d0", "d2", "zz"], slots


# --------------------------------------------------------------------------- #
# 10. 分面（F89-5）—— F88 §8 那句「明確不做」翻案了
# --------------------------------------------------------------------------- #
def test_one_panel_per_value_of_the_column():
    f = _frame(_note("epi", 110.0), _note("mg", 128.0, x0=400))
    svg = draw(f, {"mark": "box", "x": "row", "y": "glv_mean",
                   "facet": "region"}, {}, 700, 500)
    _xml(svg)
    assert svg.count("<g transform='translate(") == 2
    assert ">epi</text>" in svg and ">mg</text>" in svg


def test_the_panels_are_composed_with_g_not_a_nested_svg():
    """⚠ 巢狀 `<svg>` 是合法的 SVG 1.1，瀏覽器也開得起來 —— 但 Qt 的
    renderer 走 **Svg Tiny 1.2**，那一版沒有巢狀 `<svg>`，它會整塊**跳過**：
    寫出去的檔案是對的、Studio 裡的預覽一片空白。

    那正好打破這整個功能的不變量（「畫面上的圖跟寫出去的逐位元組相同」），
    而且是最壞的那個方向 —— 檔案對、畫面錯。render 出來才看到的。
    """
    f = _frame(_note("epi", 110.0), _note("mg", 128.0, x0=400))
    svg = draw(f, {"mark": "point", "x": "x", "y": "glv_mean",
                   "facet": "region"}, {}, 700, 500)
    assert svg.count("<svg") == 1, "巢狀 <svg>：Qt 會整塊跳過"


def test_every_panel_shares_one_pair_of_axes():
    """分開畫的幾張圖各自縮放，於是**一樣高的柱子其實不一樣高** —— 而共用
    座標軸正是分面比「幾張分開的圖」強的地方。"""
    import re

    # 兩群的值差很遠：各自縮放的話兩格的刻度會完全不同。
    f = _frame(_note("epi", 110.0), _note("mg", 190.0, x0=400))
    svg = draw(f, {"mark": "box", "x": "row", "y": "glv_mean",
                   "facet": "region"}, {}, 700, 500)
    panels = re.findall(r"<g transform='translate\([^']*\)'>(.*?)</g>", svg)
    assert len(panels) == 2
    ticks = [sorted(set(re.findall(r">(\d+)</text>", part))) for part in panels]
    assert ticks[0] == ticks[1], ticks


def test_the_colours_do_not_change_from_panel_to_panel():
    """同一個區域在第一格是綠的、在第三格變成琥珀色的話，那一頁沒有人讀得動。"""
    f = _frame(_note("epi", 110.0, cols=2, rows=2))
    svg = draw(f, {"mark": "point", "x": "x", "y": "glv_mean",
                   "color": "row", "facet": "col"}, {}, 700, 500)
    _xml(svg)
    # 兩列各拿一個區域色，而且**每一格都是同一個**
    assert uc.REGION_COLOURS[0] in svg and uc.REGION_COLOURS[1] in svg


def test_the_legend_is_printed_once_not_once_per_panel():
    """同一組顏色在一頁上被講四遍，而那幾行字佔的正是小圖最缺的高度。"""
    import re

    f = _frame(_note("epi", 110.0), _note("mg", 128.0, x0=400))
    svg = draw(f, {"mark": "point", "x": "x", "y": "glv_mean",
                   "color": "row", "facet": "region"}, {}, 700, 500)
    swatches = re.findall(r"<rect x='[0-9.]+' y='[0-9.]+' width='8' "
                          r"height='8'", svg)
    # `_note` 預設是 3 欄 × 2 列 ⇒ `row` 有兩個值 ⇒ 一份圖例兩個色塊。
    # 每一格各印一份的話會是四個。
    assert len(swatches) == 2, swatches


def test_too_many_panels_is_refused_with_the_reason():
    """16 格之後每一格只剩 150 px，而那時候該做的是先篩一輪。"""
    from d4t.core.export.chart_draw import MAX_FACETS

    notes = [_note("r%d" % i, 100.0 + i, x0=40 + 200 * i, cols=1, rows=1)
             for i in range(MAX_FACETS + 2)]
    svg = draw(_frame(*notes), {"mark": "point", "x": "x", "y": "glv_mean",
                                "facet": "region"}, {}, 700, 500)
    _xml(svg)
    assert "filter first" in svg
