# F87：圖的視窗（`ui/uniformity_window`）＋ 設定編輯器（`ui/chart_settings`）。
"""鎖的都是不變量：

* 視窗畫的 SVG **就是**會寫出去的那一份（同一支 `build_chart_svg`、
  同一支 `_style_for`）；
* 編輯器 round-trip 是 identity（鐵則 9 的 UI 側）；
* 上下界只有一份（`chart_style.bounds`），UI 不自己抄；
* 沒顯示的每張圖覆寫不准被安靜地清掉。
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))

pytest.importorskip("PySide6")

from PySide6.QtCore import QRectF  # noqa: E402
from PySide6.QtWidgets import (  # noqa: E402
    QApplication, QCheckBox, QDoubleSpinBox, QLineEdit, QSpinBox,
)

import d4t.core.steps  # noqa: F401,E402
from d4t.core.export import uniformity_charts as uc  # noqa: E402
from d4t.core.pipeline import chart_style as cs  # noqa: E402
from d4t.core.pipeline import get_step  # noqa: E402
from d4t.ui import studio as studio_mod  # noqa: E402
from d4t.ui import theme as theme_mod  # noqa: E402
from d4t.ui.chart_settings import ChartSettingsDialog, ColourButton  # noqa: E402
from d4t.ui.uniformity_window import UniformityWindow, fit_into  # noqa: E402


@pytest.fixture(scope="module")
def qapp():
    app = QApplication.instance() or QApplication([])
    theme_mod.apply_theme(app, "light")
    yield app


def _series(n=24, metric="glv_mean"):
    vals = [112.0 + i * 2.4 for i in range(n)]
    notes = [{"region": "cells", "prefix": "cells", "spread": {
        "stats": {metric: vals},
        "cx": [float(40 + 70 * (i % 6)) for i in range(n)],
        "cy": [float(40 + 70 * (i // 6)) for i in range(n)],
        "rects": [[40 + 70 * (i % 6), 40 + 70 * (i // 6), 40, 40]
                  for i in range(n)],
        "boxes": list(range(n))}}]
    return uc.chart_series(notes, metric)


# --------------------------------------------------------------------------- #
# 視窗
# --------------------------------------------------------------------------- #
def test_the_window_draws_exactly_what_gets_written(qapp):
    """**畫面上那一張就是檔案裡那一張** —— 一個位元組都不差。

    這是 F85 計畫書風險表的第一行（「兩份繪圖程式碼會漂」）。收成一份之後，
    這一條問的是它**真的還是一份**：視窗那一格產的字串，跟卡片走
    `_style_for` 產的字串比對。
    """
    win = UniformityWindow()
    win.set_context(_series(), look='{"tick_size":15}', metric="glv_mean")
    card = get_step("output_uniformity")
    p = card.validate_params({"folder": "/tmp/x", "look": '{"tick_size":15}',
                              "metric": "glv_mean"})
    for kind, view in win.views.items():
        view.resize(view.MIN_W, view.MIN_H)
        want = uc.build_chart_svg(_series(), kind,
                                  card()._style_for(kind, p, "glv_mean"),
                                  width=view.MIN_W, height=view.MIN_H)
        assert view.svg() == want, kind


def test_the_window_only_shows_the_ticked_charts(qapp):
    win = UniformityWindow()
    win.set_context(_series(), kinds=["box", "map"], metric="glv_mean")
    assert sorted(win.views) == ["box", "map"]
    win.set_context(_series(), kinds=list(uc.CHARTS), metric="glv_mean")
    assert sorted(win.views) == sorted(uc.CHARTS)


def test_the_window_says_when_there_is_nothing_to_plot(qapp):
    """空白視窗本身不是訊息（同儀表的 `empty_reason`）。"""
    win = UniformityWindow()
    win.set_context({"groups": [], "metric": "", "metrics": []})
    assert "Nothing to plot" in win.head.text()


def test_a_chart_is_never_stretched_out_of_shape(qapp):
    """``QSvgRenderer.render(p, rect)`` 會把 viewBox 拉滿 —— 一張被橫向
    拉扁的散佈圖讀起來是另一組資料。"""
    box = QRectF(0, 0, 400, 100)

    class _S:
        def width(self):
            return 300.0

        def height(self):
            return 200.0

    got = fit_into(_S(), box)
    assert abs(got.width() / got.height() - 1.5) < 1e-6
    assert got.height() <= box.height() + 1e-6
    assert abs(got.center().x() - box.center().x()) < 1e-6


def test_a_broken_size_does_not_take_the_window_down(qapp):
    """鐵則 7 的 UI 版 —— 圖畫不出來不准毀掉視窗。"""
    win = UniformityWindow()
    win.set_context(_series(), metric="glv_mean")
    for w, h in ((40, 30), (1, 1), (900, 600)):
        for view in win.views.values():
            view.resize(w, h)
            assert view.svg()


# --------------------------------------------------------------------------- #
# 編輯器
# --------------------------------------------------------------------------- #
def test_the_editor_round_trips(qapp):
    """開起來、什麼都不動、按 OK —— **一個字都不准變**（鐵則 9 的 UI 側）。

    這是最容易壞的那一條：任何一格的預設值在 UI 與 core 之間漂掉，
    這個對話框就會在使用者「只是看了一下」之後偷偷改掉 recipe。
    """
    for look in ('', '{"tick_size":14,"tick_bold":true}',
                 '{"box.title":"EPI","lock":true,"lo":10,"hi":90}',
                 '{"line_color":"#ff8800","percent":true,"profile.xticks":9}'):
        dlg = ChartSettingsDialog(look, list(uc.CHARTS))
        assert dlg.value() == cs.format_style(cs.parse_style(look)), look


def test_the_editor_keeps_overrides_for_charts_it_is_not_showing(qapp):
    """把熱圖取消勾選之後再來調設定 —— 熱圖的標題不准被安靜地清掉。"""
    look = '{"map.title":"Where","box.title":"Spread"}'
    dlg = ChartSettingsDialog(look, ["box"])
    assert "map.title" in dlg.value()
    dlg.per["box"]["title"].setText("Spread 2")
    got = cs.parse_style(dlg.value())
    assert got["map.title"] == "Where" and got["box.title"] == "Spread 2"


def test_reset_says_what_it_does(qapp):
    """鈕上寫的是「全部回預設」—— 收起來的覆寫也一起（不然那是半句實話）。"""
    dlg = ChartSettingsDialog('{"map.title":"Where","tick_size":18}', ["box"])
    dlg.reset()
    assert dlg.value() == ""


def test_every_setting_has_a_home_on_the_page(qapp):
    """**每一格都要編得到。** 少一格的下場是它只能靠手改 JSON ——
    而目標使用者不會寫 code（推廣鐵則）。"""
    dlg = ChartSettingsDialog("", list(uc.CHARTS))
    assert set(dlg.globals) == set(cs.GLOBAL_KEYS)
    for kind in uc.CHARTS:
        assert set(dlg.per[kind]) == set(cs.PER_CHART_KEYS)


def test_the_bounds_come_from_core_not_from_a_copy(qapp):
    """上下界只有一份（`chart_style.bounds`）。

    抄一份的那天，使用者打得進一個滑桿拉不到的值 —— 或反過來，拉得到一個
    存不進去的值，而錯誤訊息會出現在按下 OK 之後。
    """
    dlg = ChartSettingsDialog("", ["box"])
    for key, w in dlg.globals.items():
        got = cs.bounds(key)
        if got is None:
            assert not isinstance(w, (QSpinBox, QDoubleSpinBox)), key
            continue
        lo, hi = got
        assert abs(w.minimum() - lo) < 1e-6, key
        assert abs(w.maximum() - hi) < 1e-6, key


def test_the_editors_match_the_kind_of_value(qapp):
    """bool → 打勾、顏色 → 色塊、文字 → 輸入框、數字 → 數字框。

    型別對不上不會炸，它會**安靜地存錯東西**（一個 QLineEdit 存出來的
    ``"True"`` 不是 ``true``）。
    """
    dlg = ChartSettingsDialog("", ["box"])
    for key, w in dlg.globals.items():
        default = cs.DEFAULTS[key]
        if key.endswith("_color"):
            assert isinstance(w, ColourButton), key
        elif isinstance(default, bool):
            assert isinstance(w, QCheckBox), key
        elif isinstance(default, str):
            assert isinstance(w, QLineEdit), key
        else:
            assert isinstance(w, (QSpinBox, QDoubleSpinBox)), key


def test_a_colour_goes_back_to_auto(qapp):
    """顏色的預設是**自動**（跟著區域色走），而回到自動要**看得見** ——
    藏在右鍵裡的功能對不會寫 code 的人等於不存在。"""
    dlg = ChartSettingsDialog('{"point_color":"#ff0000"}', ["box"])
    btn = dlg.globals["point_color"]
    assert btn.value() == "#ff0000" and btn.clear_btn.isEnabled()
    btn.clear_btn.click()
    assert btn.value() == "" and not btn.clear_btn.isEnabled()
    assert dlg.value() == "", "回到自動就等於預設，那一格不該再留在 recipe 裡"


def test_the_per_chart_tick_count_can_say_follow_the_others(qapp):
    """每張圖的刻度數要能說「跟大家一樣」—— 一個看起來像 1 的數字答不出
    「這是沒設定，還是真的設成 1」。"""
    dlg = ChartSettingsDialog("", ["box"])
    w = dlg.per["box"]["xticks"]
    assert w.value() == w.minimum()
    assert w.specialValueText()
    assert dlg.value() == ""
    w.setValue(9)
    assert cs.parse_style(dlg.value())["box.xticks"] == 9


def test_a_broken_style_string_opens_on_the_defaults(qapp):
    """recipe 那一格壞掉（手改壞了）也要開得起來 —— 開不起來的對話框
    等於把使用者鎖在外面（鐵則 7 的 UI 版）。"""
    dlg = ChartSettingsDialog("{not json", list(uc.CHARTS))
    assert dlg.value() == ""


def test_the_settings_reach_all_four_charts(qapp):
    """**字級不能只對四張裡的兩張有效。**

    盒鬚圖走 `boxplot.build_boxplot_svg`、熱圖以前寫死 10px —— 兩條不同的
    路，而「只有兩張跟著變」是使用者會以為自己按錯的那種 bug。
    """
    s = _series()
    for kind in uc.CHARTS:
        a = uc.build_chart_svg(s, kind, cs.style_for("", kind))
        b = uc.build_chart_svg(
            s, kind, cs.style_for('{"tick_size":22,"tick_bold":true}', kind))
        assert a != b, kind


# --------------------------------------------------------------------------- #
# 接線（Studio）
# --------------------------------------------------------------------------- #
@pytest.fixture
def window(qapp):
    # ⚠ `studio` **一定要在模組層 import**：`conftest` 那支關掉「關閉時確認
    # 存檔」的 autouse fixture 是 ``sys.modules.get("d4t.ui.studio")`` ——
    # 在 fixture 裡才 import 的話它那時候還看不到這個模組，於是 `win.close()`
    # 會停在一個沒有人按得下去的 QMessageBox 上，測試就永遠跑不完
    # （實際發生過，2026-09-07）。
    win = studio_mod.StudioWindow(show_welcome_on_start=False)
    yield win
    win.close()


def _pick_uniformity(window):
    nid = window.model.add_step("output_uniformity")
    window.select_node(nid)
    return nid


def test_the_button_opens_one_window_not_a_pile_of_them(qapp, window):
    """開第二次是把同一個抬到最前面。

    每按一次多開一個的話，改設定只會改到其中一個 —— 而其他幾個還畫著舊的
    樣子，兩張都畫得出來。
    """
    from d4t.ui import inspectors as insp_mod

    _pick_uniformity(window)
    assert isinstance(window._inspector, insp_mod.UniformityPreviewInspector)
    window._inspector.charts_requested.emit()
    first = window._charts_window
    assert first is not None and first.isVisible()
    window._inspector.charts_requested.emit()
    assert window._charts_window is first


def test_changing_the_style_in_the_window_writes_it_back_to_the_card(
        qapp, window):
    """視窗裡改完設定要**進 recipe**，而且 Ctrl+Z 撤得掉。

    一個會改 recipe 而撤不掉的視窗，比沒有那個視窗糟 —— 所以它走「量給我填」
    同一條路（`_on_param_requested` → `set_param`）。
    """
    nid = _pick_uniformity(window)
    before = str(window.model.nodes[nid].params.get("look", ""))
    window._on_chart_style_changed('{"tick_size":18}')
    assert window.model.nodes[nid].params["look"] == '{"tick_size":18}'
    window.undo()
    assert str(window.model.nodes[nid].params.get("look", "")) == before


def test_the_style_only_lands_on_a_uniformity_card(qapp, window):
    """選到別張卡的時候那個訊號**什麼都不做** —— 視窗還開著、使用者按了
    設定，而 `look` 落在一張沒有那一格的卡上會是一條驗證錯誤。"""
    nid = window.model.add_step("output_report")
    window.select_node(nid)
    window._on_chart_style_changed('{"tick_size":18}')
    assert "look" not in window.model.nodes[nid].params


# --------------------------------------------------------------------------- #
# 熱圖疊在影像上（F87 第五刀）
# --------------------------------------------------------------------------- #
def _heat_view(qapp, n=6):
    import numpy as np

    from d4t.ui.widgets import ImageView

    view = ImageView()
    view.resize(400, 380)
    view.set_image(np.linspace(60, 200, 200 * 200,
                               dtype=np.float32).reshape(200, 200))
    cells = [(0.05 + 0.15 * i, 0.2, 0.15, 0.3) for i in range(n)]
    colours = [uc.heat_hex(i / max(1, n - 1)) for i in range(n)]
    view.set_heat(cells, colours, (10.0, 90.0, "glv_mean"))
    return view


def test_the_view_paints_the_heat_and_says_how_much(qapp):
    view = _heat_view(qapp)
    assert view.heat_count() == 6
    assert view.heat_legend() == (10.0, 90.0, "glv_mean")
    view.show()
    qapp.processEvents()
    view.grab()                       # 畫一次不准炸


def test_a_mismatched_heat_is_dropped_whole(qapp):
    """**長度對不上就整組不畫** —— 同 `set_overlay` / `set_marks` 的規矩。

    錯位的顏色會把值畫在別的地方，而畫面上沒有任何東西透露那件事。
    """
    view = _heat_view(qapp)
    view.set_heat([(0.1, 0.1, 0.2, 0.2), (0.4, 0.1, 0.2, 0.2)], ["#ff0000"],
                  (0.0, 1.0, "x"))
    assert view.heat_count() == 0


def test_clearing_the_heat_takes_the_bar_with_it(qapp):
    view = _heat_view(qapp)
    view.clear_heat()
    assert view.heat_count() == 0 and view.heat_legend() is None
    view.grab()


def test_the_heat_goes_under_the_boxes_not_over_them(qapp):
    """順序就是意思：熱色是「量出來多少」，框是「量的是哪一塊」。

    反過來畫的話，一片色塊會蓋掉框 —— 而「這一塊的顏色是從哪一格量來的」
    那句話就沒了（PEAR 的 `_paint_heat_cells` 也是先熱後框）。
    """
    import inspect as _inspect

    from d4t.ui.widgets import ImageView

    src = _inspect.getsource(ImageView.paintEvent)
    assert src.index("_paint_heat(") < src.index("_paint_overlay(")
    assert src.index("_paint_overlay(") < src.index("_paint_marks(")


def test_the_colour_bar_is_readable_on_any_image(qapp):
    """色條底下要墊一塊 —— 影像可以是任何亮度，直接寫字的話深色圖上那兩個
    數字看不見，而那些顏色就不再是資料、只是裝飾。"""
    import inspect as _inspect

    from d4t.ui.widgets import ImageView

    src = _inspect.getsource(ImageView._paint_heat_bar)
    assert "bg_surface" in src and "drawRoundedRect" in src


def test_the_studio_hands_the_view_what_the_card_says(qapp, window):
    """卡片交、UI 畫 —— 同 `measure_marks` 那條界線（`Step.overlay_heat`）。"""
    nid = window.model.add_step("output_uniformity")
    window.select_node(nid)
    # 還沒跑過就什麼都沒有（熱色來自 context，不是 model）
    assert window.heat_tiles("test") == ([], [], None)
    assert window.image_view.heat_count() == 0


# --------------------------------------------------------------------------- #
# 卡片上的那一格（F87 第六刀）
# --------------------------------------------------------------------------- #
def test_the_chart_look_row_has_a_button_not_a_json_box(qapp):
    """使用者 2026-09-07：「Chart look 是什麼? 我沒看到 Chart setting
    沒看到編輯器」。

    `chart_style` 的值是一串 JSON。沒有專屬編輯器的話那一格會掉進表單的預設
    分支 —— 一個**可以打字的文字框，裡面是生 JSON** —— 而目標使用者是不會寫
    code 的製程工程師。更糟的是編輯器**存在**、只是掛在別的地方，所以畫面上
    那一格看起來就是「這個功能沒做」。
    """
    from d4t.core.pipeline import get_step
    from d4t.ui.widgets import ChartStyleField, ParamForm

    form = ParamForm()
    form.set_step(get_step("output_uniformity").describe(),
                  {"folder": "out", "charts": "box,map",
                   "look": '{"tick_size":14,"box.title":"EPI"}'}, [], [])
    row = form._rows["look"]
    assert isinstance(row.editor, ChartStyleField)
    # **原字串照放，不偷偷正規化** —— 這一格只是顯示，改寫 recipe 的值
    # 要有人真的按了 OK（同 `CurveField` 只在 `curve_changed` 時才送出）。
    assert row.editor.text() == '{"tick_size":14,"box.title":"EPI"}'
    assert "2 changes" in row.editor.summary.text()
    assert row.editor.button.text().startswith("Chart settings")


def test_every_chart_style_param_gets_that_editor(qapp):
    """**registry 全掃** —— 下一張用 `chart_style` 的卡不必再發現一次。"""
    from d4t.core.pipeline import list_steps
    from d4t.ui.widgets import ChartStyleField, ParamForm

    seen = 0
    for card in list_steps():
        spec = card.describe()
        names = [q["name"] for q in spec["params"]
                 if q["type"] == "chart_style"]
        if not names:
            continue
        form = ParamForm()
        form.set_step(spec, {}, [], [])
        for name in names:
            assert isinstance(form._rows[name].editor, ChartStyleField), name
            seen += 1
    assert seen, "沒有任何一格是 chart_style —— 這條測試就沒在守東西了"


def test_the_editor_only_offers_the_charts_this_card_writes(qapp):
    """右半的分頁 = 這張卡勾了哪幾張圖。沒勾的那幾張的覆寫**不准被清掉**。"""
    from d4t.core.pipeline import get_step
    from d4t.ui.widgets import ParamForm

    form = ParamForm()
    form.set_step(get_step("output_uniformity").describe(),
                  {"folder": "out", "charts": "box",
                   "look": '{"map.title":"Where"}'}, [], [])
    assert form._chart_kinds() == ["box"]
    dlg = ChartSettingsDialog(form._rows["look"].editor.text(),
                              form._chart_kinds())
    assert sorted(dlg.per) == ["box"]
    assert "map.title" in dlg.value()


def test_an_empty_charts_box_still_opens_on_all_four(qapp):
    """一個空的分頁區讀起來是「壞了」—— 沒勾就全部給。"""
    from d4t.core.pipeline import get_step
    from d4t.ui.widgets import ParamForm

    form = ParamForm()
    form.set_step(get_step("output_uniformity").describe(),
                  {"folder": "out", "charts": ""}, [], [])
    assert form._chart_kinds() == list(uc.CHARTS)
