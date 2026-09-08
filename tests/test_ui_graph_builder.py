# F88 第二刀：`chart_spec` 那一格的編輯器（`ui/graph_builder`）。
"""鎖的都是不變量：

* 選單是**從資料長出來的**（`Frame.columns`），不是一張寫死的清單；
* **不拿第一欄當預設** —— 一張沒有人設定過的圖不准看起來像設定好了；
* 預覽走的是**寫出去的同一支** `build_chart_svg`；
* 卡片上那一格是「摘要 ＋ 一顆按鈕」，不是一個要手寫 JSON 的文字框。
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))

pytest.importorskip("PySide6")

from PySide6.QtWidgets import QApplication, QLineEdit  # noqa: E402

import d4t.core.steps  # noqa: F401,E402
from d4t.core.export import uniformity_charts as uc  # noqa: E402
from d4t.core.export.chart_frame import build_frame  # noqa: E402
from d4t.core.pipeline import chart_spec as cspec  # noqa: E402
from d4t.core.pipeline import get_step  # noqa: E402
from d4t.ui import theme as theme_mod  # noqa: E402
from d4t.ui.graph_builder import (  # noqa: E402
    NONE_WORD, PICK_WORD, GraphBuilderDialog, SpecEditor,
)
from d4t.ui.widgets import ChartSpecField, ParamForm  # noqa: E402


@pytest.fixture(scope="module")
def qapp():
    app = QApplication.instance() or QApplication([])
    theme_mod.apply_theme(app, "light")
    yield app


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


@pytest.fixture
def frame():
    return build_frame([_note("epi", 110.0), _note("mg", 128.0, x0=400)])


# --------------------------------------------------------------------------- #
# 1. 選單從資料長出來
# --------------------------------------------------------------------------- #
def test_the_menus_are_built_from_the_data(qapp, frame):
    """寫死一份的那天，使用者的欄位在選單上找不到。"""
    ed = SpecEditor("", frame.columns, numeric=frame.numeric_columns())
    # ⚠ 值是欄名（`itemData`），畫面上是白話（`itemText`）—— 兩個都要問。
    got = [ed.boxes["x"].itemData(i) for i in range(ed.boxes["x"].count())]
    assert "glv_mean" in got and "glv_std" in got and "region" in got
    shown = [ed.boxes["x"].itemText(i) for i in range(ed.boxes["x"].count())]
    assert "Box centre X (px)" in shown, "欄名還是原始的鍵"


def test_size_only_offers_numbers(qapp, frame):
    """「region B 比 region A 大」沒有意義。"""
    ed = SpecEditor("", frame.columns, numeric=frame.numeric_columns())
    got = [ed.boxes["size"].itemData(i)
           for i in range(ed.boxes["size"].count())]
    assert "region" not in got and "row" not in got
    assert "glv_mean" in got


def test_a_role_this_mark_cannot_use_is_not_shown(qapp, frame):
    """一格答了也沒用的設定比沒有那一格更糟（同 `GLOBAL_APPLIES`）。"""
    ed = SpecEditor("", frame.columns)
    for role in ed.boxes:
        assert cspec.uses("", role), role


# --------------------------------------------------------------------------- #
# 2. 不拿第一欄當預設
# --------------------------------------------------------------------------- #
def test_nothing_is_picked_until_the_user_picks_it(qapp, frame):
    """第一版就是拿第一欄當預設的：打開對話框，X 與 Y 都落在 `region` 上，
    於是一張沒有人設定過的圖**看起來像設定好了** —— 而它畫出來是一團疊在
    同一個點上的圓。"""
    ed = SpecEditor("", frame.columns, numeric=frame.numeric_columns())
    assert ed.spec() == ""
    assert ed.boxes["x"].currentText() == PICK_WORD
    assert ed.boxes["color"].currentText() == NONE_WORD
    assert not ed.boxes["x"].currentData()


def test_what_the_recipe_says_is_what_the_menus_show(qapp, frame):
    text = '{"color":"region","mark":"point","x":"glv_mean","y":"glv_std"}'
    ed = SpecEditor(text, frame.columns, numeric=frame.numeric_columns())
    assert ed.boxes["x"].currentData() == "glv_mean"
    assert ed.boxes["color"].currentData() == "region"
    assert ed.spec() == text, "round-trip 不是 identity（鐵則 9 的 UI 側）"


def test_a_broken_value_does_not_take_the_dialog_down(qapp, frame):
    ed = SpecEditor("{not json", frame.columns)
    assert ed.spec() == ""


# --------------------------------------------------------------------------- #
# 3. 預覽
# --------------------------------------------------------------------------- #
def test_the_preview_is_the_svg_that_would_be_written(qapp, frame):
    """畫面上的圖跟寫出去的圖不一樣、而兩張都畫得出來，是這個 repo 最貴的
    那種 bug。"""
    text = '{"mark":"point","x":"glv_mean","y":"glv_std"}'
    dlg = GraphBuilderDialog(text, frame)
    mine = dlg.view.svg()
    theirs = uc.build_chart_svg(
        {}, uc.CHART_CUSTOM,
        uc.resolve_style("", uc.CHART_CUSTOM, uc.AXIS_X, ""),
        width=max(dlg.view.MIN_W, dlg.view.width()),
        height=max(dlg.view.MIN_H, dlg.view.height()),
        frame=frame, spec=text)
    assert mine == theirs
    assert mine.count("<circle") == len(frame)


def test_picking_a_column_moves_the_preview(qapp, frame):
    # ⚠ 打開時落在一個**預設**上（第五刀），所以起點不是那句「pick x and
    # y」了 —— 起點是一張畫得出來的圖，而改一格要看得出差別。
    dlg = GraphBuilderDialog("", frame)
    before = dlg.view.svg()
    assert dlg.editor.set_role("y", "w")
    after = dlg.view.svg()
    assert after != before


def test_no_data_yet_still_opens_and_says_why(qapp):
    """按鈕照開 —— 一顆按不下去的按鈕沒有告訴使用者任何事。"""
    dlg = GraphBuilderDialog("", None)
    assert dlg.editor.boxes["x"].count() == 1      # 只有那句「還沒挑」
    assert "no boxes to plot" in dlg.view.svg()


def test_it_never_opens_on_a_blank_page(qapp, frame):
    """**打開時一定是一個預設**（計畫書 §5）。graph builder 最容易讓不寫
    code 的人卡住的就是「面前一張白紙」（推廣鐵則）。

    ⚠ 這跟第二刀刻意不做的「拿第一欄當預設」是兩回事：那個是隨便挑一欄，
    畫出來是一團疊在同一點的圓、而且看起來像設定好了；這個是一張**有名字、
    有意思**的圖，而名字就寫在那顆膠囊上。
    """
    dlg = GraphBuilderDialog("", frame)
    assert dlg.editor.spec(), "打開是空白的"
    assert "pick x and y" not in dlg.view.svg()
    assert dlg.view.svg().count("<circle") == len(frame)


def test_a_spec_that_is_already_set_is_not_overwritten_by_a_preset(qapp, frame):
    """使用者存過的那一份**不准被起點蓋掉**。"""
    text = '{"mark":"bar","x":"region","y":"glv_mean"}'
    dlg = GraphBuilderDialog(text, frame)
    assert dlg.editor.spec() == text


def test_every_preset_lands_on_a_chart_that_actually_draws(qapp, frame):
    """一顆按了畫不出東西的鈕，比沒有那顆鈕更糟。"""
    from d4t.core.export import chart_draw

    dlg = GraphBuilderDialog("", frame)
    for name, _why, _t in chart_draw.PRESETS:
        assert dlg.presets.buttons[name].isEnabled(), name
        dlg.presets.buttons[name].click()
        qapp.processEvents()
        svg = dlg.view.svg()
        assert "pick " not in svg and "no column called" not in svg, name
        assert dlg.editor.spec(), name


def test_with_no_numbers_measured_the_presets_are_not_offered(qapp):
    """佔位符換不掉（那一顆沒有量出任何統計量）—— 一份指著不存在的欄的 spec
    會畫出一句「no column called '@metric'」，那比空的更難懂。"""
    from d4t.core.export import chart_draw
    from d4t.core.export.chart_frame import build_frame

    dlg = GraphBuilderDialog("", build_frame([]))
    for name, _why, _t in chart_draw.PRESETS:
        assert not dlg.presets.buttons[name].isEnabled(), name
    assert dlg.editor.spec() == ""


def test_setting_a_whole_spec_at_once_signals_once(qapp, frame):
    """中途那幾次畫的是**半套**設定 —— 畫面會抖一下，而每一次都要重畫一張圖。"""
    ed = SpecEditor("", frame.columns, numeric=frame.numeric_columns())
    seen = []
    ed.changed.connect(lambda: seen.append(1))
    ed.set_spec('{"color":"region","mark":"box","x":"region","y":"glv_mean"}')
    assert len(seen) == 1
    assert ed.spec() == \
        '{"color":"region","mark":"box","x":"region","y":"glv_mean"}'


# --------------------------------------------------------------------------- #
# 4. 卡片上那一格
# --------------------------------------------------------------------------- #
def test_the_card_row_is_a_summary_not_a_json_box(qapp, frame):
    """目標使用者是不會寫 code 的製程工程師（推廣鐵則）—— 那一格掉進表單的
    預設分支的話，它是一個要手寫 JSON 的文字框。"""
    form = ParamForm()
    form.set_step(get_step("output_uniformity").describe(),
                  {"charts": uc.CHART_CUSTOM, "folder": "/tmp/x",
                   "spec": '{"mark":"point","x":"glv_mean","y":"glv_std"}'})
    row = form._rows["spec"]
    assert isinstance(row.editor, ChartSpecField)
    assert not isinstance(row.editor, QLineEdit)
    assert "glv_std" in row.editor.summary.text()
    assert "{" not in row.editor.summary.text()

    form.set_chart_frame(frame)
    assert row.editor._frame is frame


def test_the_row_is_hidden_when_that_chart_is_not_ticked(qapp):
    """沒勾那張圖就別問這件事（同 `Profile along`，F87）。"""
    from d4t.core.pipeline.step import param_visible

    spec = [p for p in get_step("output_uniformity").params
            if p.name == "spec"][0]
    assert not param_visible(spec.show_when, {"charts": "box,histogram"})
    assert param_visible(spec.show_when,
                         {"charts": "box,%s" % uc.CHART_CUSTOM})


# --------------------------------------------------------------------------- #
# 5. 記號那一排（F88 第三刀）
# --------------------------------------------------------------------------- #
def test_the_mark_is_a_row_of_chips_not_a_dropdown(qapp, frame):
    """**一格選項＝一排膠囊（圖 + 字）**（F68 的規矩）。三種記號講的正是
    「這張圖長什麼形狀」，那本來就畫得出來。"""
    from d4t.ui.glyphs import CHIP_ICONS
    from d4t.ui.graph_builder import MARK_ICONS
    from d4t.ui.widgets import ChoiceChips

    ed = SpecEditor("", frame.columns)
    assert isinstance(ed.marks, ChoiceChips)
    for mark in cspec.MARKS:
        assert ed.marks.chip(mark) is not None, mark
        assert MARK_ICONS[mark] in CHIP_ICONS, mark


def test_picking_a_mark_redraws_and_hides_what_it_cannot_use(qapp, frame):
    """一格答了也沒用的設定比沒有那一格更糟 —— 一條線沒有大小。"""
    dlg = GraphBuilderDialog(
        '{"color":"region","mark":"point","size":"glv_mean",'
        '"x":"glv_mean","y":"glv_std"}', frame)
    assert dlg.editor.boxes["size"].isVisibleTo(dlg.editor)
    before = dlg.view.svg()

    dlg.editor.marks.chip(cspec.MARK_LINE).click()
    qapp.processEvents()
    assert not dlg.editor.boxes["size"].isVisibleTo(dlg.editor)
    assert dlg.view.svg() != before
    assert "<polyline" in dlg.view.svg()
    assert '"size"' not in dlg.editor.spec()


def test_a_hidden_role_is_not_wiped(qapp, frame):
    """收起來**不等於清掉** —— 把記號換成折線再換回來，原本挑的「大小」還在
    （同 `ChartSettingsDialog` 那條「沒顯示的覆寫要留著」）。"""
    text = ('{"color":"region","mark":"point","size":"glv_mean",'
            '"x":"glv_mean","y":"glv_std"}')
    ed = SpecEditor(text, frame.columns, numeric=frame.numeric_columns())
    ed.marks.chip(cspec.MARK_BAR).click()
    ed.marks.chip(cspec.MARK_POINT).click()
    assert ed.spec() == text


def test_bars_draw_from_the_same_dialog(qapp, frame):
    dlg = GraphBuilderDialog(
        '{"mark":"bar","x":"region","y":"glv_mean"}', frame)
    assert "fill-opacity" in dlg.view.svg()


# --------------------------------------------------------------------------- #
# 6. 預覽讀得動（F89-1）
# --------------------------------------------------------------------------- #
def test_the_preview_is_never_taller_than_it_is_wide(qapp, frame):
    """SVG 是**照那一格的尺寸產的** —— 那一格被拉成直條，圖就被畫成直條。
    圖表要的是寬 > 高（`ChartView.ASPECT` 的說明）。"""
    for w, h in ((720, 780), (600, 1200), (1000, 900)):
        dlg = GraphBuilderDialog("", frame)
        dlg.resize(w, h)
        dlg.show()
        qapp.processEvents()
        view = dlg.view
        assert view.width() >= view.height(), (w, h, view.width(),
                                               view.height())


def test_both_dialogs_agree_on_the_shape_of_a_preview(qapp):
    """兩個對話框畫的是同一種東西 —— 比例不一樣的話，同一張圖在兩邊長得
    不一樣，而使用者會以為其中一邊壞了。"""
    from d4t.ui.chart_settings import ChartSettingsDialog

    assert (GraphBuilderDialog.PREVIEW_ASPECT
            == ChartSettingsDialog.PREVIEW_ASPECT)


# --------------------------------------------------------------------------- #
# 7. 讀得懂（F89-2，使用者 2026-09-08：「工程師會不會看不懂?」）
# --------------------------------------------------------------------------- #
def test_the_menus_say_what_a_column_is_but_store_the_column_name(qapp, frame):
    """`x` 是**框中心的座標**，但它擺在「Across the bottom」旁邊，讀起來就是
    「X 軸」—— 挑它想畫「數值」的人會拿到位置，而那張圖畫得出來、有數字、
    而且答錯了問題。

    ⚠ **只加顯示的字，鍵一個都不動** —— 存回 recipe 的還是 `x`。
    """
    ed = SpecEditor('{"mark":"point","x":"x","y":"glv_mean"}', frame.columns,
                    numeric=frame.numeric_columns())
    assert ed.boxes["x"].currentText() == "Box centre X (px)"
    assert ed.boxes["x"].currentData() == "x"
    assert '"x":"x"' in ed.spec(), "白話跑進 recipe 了"


def test_what_the_user_measured_comes_first(qapp, frame):
    """混在同一張清單裡的話，`glv_median`（他要的）跟 `w`（框有多寬，幾乎
    沒有人要畫）長得一樣重要。"""
    ed = SpecEditor("", frame.columns, numeric=frame.numeric_columns())
    got = [ed.boxes["y"].itemData(i) for i in range(1, ed.boxes["y"].count())]
    assert got[0] in ("glv_mean", "glv_std"), got
    assert got.index("glv_mean") < got.index("w"), got


def test_the_box_plot_mark_is_not_called_boxes(qapp):
    """這個工具裡「box」已經有一個意思了 —— **一格量測框**（長表上那一欄就叫
    `box`）。同一排選單裡出現 `box`（第幾個框）跟 `Boxes`（一種圖）的話，
    會混淆的是**人**，而那正是 CLAUDE.md 花一整段講的 `bundle`。
    """
    from d4t.core.export import chart_frame

    assert cspec.MARK_LABELS[cspec.MARK_BOX] == "Box plot"

    # 真正的不變量：**沒有一個記號的名字等於一個欄的名字**（原始鍵或白話都
    # 算）。`Box plot` 裡有「box」是可以的 —— 它畫的就是那種圖；不可以的是
    # 兩個東西**叫同一個名字**。
    marks = {v.strip().lower() for v in cspec.MARK_LABELS.values()}
    columns = ({c.strip().lower() for c in chart_frame.COLUMNS_FIXED}
               | {v.strip().lower()
                  for v in chart_frame.COLUMN_LABELS.values()})
    assert not (marks & columns), sorted(marks & columns)
