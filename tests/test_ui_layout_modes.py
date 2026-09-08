# U5 ＋ U8：一個視窗兩種模式，而參數與儀表挨著 — authored 2026-09-08.
"""**畫布是這個工具的賣點，卻是螢幕上第三大的東西。**

U5：以前「看全貌」是把畫布開在**第二個視窗**（F8-UI D 案）。那條路 work，
但代價是兩份 `PipelineCanvas` 實體與兩份狀態 —— 每個訊號接兩次、每次重畫記得
兩邊都畫（`_canvases()` 的存在就是那個稅）。現在是同一份畫布的兩種版面。

U8：儀表（Card / Features）以前住在**右欄下半**，參數住在中欄下半，中間隔著
整張影像。調參數的迴圈是「改一個數字 → 看那個數字怎麼變」，而那兩件事每一次
都要橫跨半個螢幕。
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))


@pytest.fixture(scope="module")
def qapp():
    from PySide6.QtWidgets import QApplication
    app = QApplication.instance() or QApplication([])
    yield app


@pytest.fixture
def window(qapp):
    from d4t.ui.studio import StudioWindow
    win = StudioWindow()
    win.show()
    win.resize(1400, 900)
    qapp.processEvents()
    try:
        yield win
    finally:
        win.close()


# --------------------------------------------------------------------------- #
# U5：兩種模式
# --------------------------------------------------------------------------- #
def test_there_is_only_ever_one_canvas(window):
    """**驗收條件**：`_canvases()` 恆為長度 1。

    那個列表存在的理由（兩份畫布要各畫一次）已經沒有了 —— 留著是因為呼叫端
    寫的是「對每一份畫布做這件事」，而那句話仍然是對的。
    """
    for mode in ("build", "tune", "build"):
        window.set_layout_mode(mode)
        assert len(window._canvases()) == 1
    assert window._canvases()[0] is window.pipeline


def test_switching_does_not_rebuild_the_canvas(window, qapp):
    """**驗收條件**：node id 與選取狀態保持。

    重建的話使用者拖過的位置會被自動排版洗掉 —— 那正是 2026-08-14 使用者
    退掉過一次的行為。
    """
    nid = window.model.node_order[0] if window.model.node_order else None
    if nid is None:
        nid = window.model.add_step("load_patch")
        window._refresh_all()
        qapp.processEvents()
    window.select_node(nid)
    ids = window.pipeline.node_ids()
    window.set_layout_mode("build")
    qapp.processEvents()
    assert window.pipeline.node_ids() == ids
    assert window.pipeline.selected() == nid


def test_build_gives_the_canvas_the_whole_column(window, qapp):
    window.set_layout_mode("build")
    qapp.processEvents()
    assert window.canvas_column.sizes()[1] == 0


def test_the_button_says_where_it_will_take_you(window):
    """鈕上寫的是**按下去會去哪裡**，不是現在在哪裡。

    寫現在在哪裡的話，使用者要先讀懂「這是狀態不是動作」才知道按了會怎樣。

    ⚠ **那顆鈕住在畫布的縮放列上，不在工具列。** 第一版放在工具列，而
    `test_ui_small_screen` 當場抓到：工具列在 1366×768 上要 1,285 px 而只有
    1,229 px —— 尾巴幾顆會被收進 » 溢位選單，**在開發機上看不到**。
    它現在跟 fit／1:1／tidy 排在一起，那本來就是「怎麼看」那一組；
    而且控制項長在它控制的東西上（同 F7-22 那顆「斷開」的 ×）。
    只有圖示的鈕話講在 tooltip 上。
    """
    btn = window.pipeline.zoom_buttons()[-1]
    window.set_layout_mode("tune")
    assert "Build" in btn.toolTip(), btn.toolTip()
    window.set_layout_mode("build")
    assert "Tune" in btn.toolTip(), btn.toolTip()
    assert btn.accessibleName() == btn.toolTip(), \
        "沒有文字的鈕對讀螢幕軟體是空的 —— tooltip 要當 accessible name"


def test_that_button_toggles_rather_than_going_one_way(window, qapp):
    """按了之後要有路回來。

    單向切到 Build 的話，使用者按了那顆鈕就卡在那裡了 —— 而 Ctrl+B 是給記得
    的人用的，不是唯一的路。
    """
    window.set_layout_mode("tune")
    btn = window.pipeline.zoom_buttons()[-1]
    btn.click()
    qapp.processEvents()
    assert window.layout_mode() == "build"
    btn.click()
    qapp.processEvents()
    assert window.layout_mode() == "tune"


def test_the_toolbar_did_not_grow_for_this(window):
    """**這一條是那個 regression 的便利貼。**

    U5／X3 一開始各在工具列上加了一顆鈕（Build/Tune、抽樣的「…」），加起來
    132 px —— 而那台機器只剩 76 px 的餘裕。兩顆都搬走了：一顆進畫布的縮放列，
    一顆併進那個會變的字本身。
    """
    from PySide6.QtWidgets import QToolButton
    assert not hasattr(window, "btn_layout"), \
        "版面切換又回到工具列上了 —— 那台機器沒有位子（test_ui_small_screen）"
    assert isinstance(window.lbl_trial_n, QToolButton), \
        "抽樣那個字本身就該是可以點的東西，不要旁邊再放一顆鈕"


def test_toggling_goes_back_and_forth(window):
    window.set_layout_mode("tune")
    assert window.toggle_layout_mode() == "build"
    assert window.toggle_layout_mode() == "tune"


def test_an_unknown_mode_changes_nothing(window):
    """打錯的模式不該讓版面變成一個沒有人設計過的樣子。"""
    window.set_layout_mode("tune")
    assert window.set_layout_mode("zoomed") == "tune"
    assert window.layout_mode() == "tune"


def test_ctrl_b_is_in_the_shortcut_table(window):
    from d4t.ui.studio import StudioWindow
    assert dict(StudioWindow.SHORTCUTS).get("Ctrl+B") == "layout_mode"


def test_the_two_modes_remember_different_ratios(window):
    """使用者在 Build 裡把畫布拉高、在 Tune 裡把設定拉高 —— 那是兩個偏好。

    共用一格的話切一次模式就把另一個覆蓋掉，而他每次切回來都要再調一次。
    """
    keys = window._SPLIT_KEYS
    assert set(keys) == {"build", "tune"}
    assert keys["build"] != keys["tune"]


def test_the_popout_is_gone(window):
    """彈出視窗退場（U5）—— 留著一條沒有人維護的第二條路比刪掉更糟。"""
    for name in ("open_canvas_window", "canvas_popout_open", "_popout_view",
                 "_canvas_popout"):
        assert not hasattr(window, name), "%s 還在" % name


def test_picking_a_card_does_not_fight_the_user_in_build_mode(window, qapp):
    """他明講了「現在我要看流程」—— 選一張卡不該把設定區推回來。"""
    window.set_layout_mode("build")
    if window.model.node_order:
        window.select_node(window.model.node_order[0])
    qapp.processEvents()
    assert window.layout_mode() == "build"
    assert window.canvas_column.sizes()[1] == 0
    assert window.params_open() is False


# --------------------------------------------------------------------------- #
# U8：參數與儀表同欄同框
# --------------------------------------------------------------------------- #
def test_the_gauges_sit_next_to_the_parameters(window):
    """**驗收條件**：改一個參數之後，數值變化與該參數在同一個視野內。"""
    row = window.params_row
    assert window.canvas_column.widget(1) is row
    assert row.widget(0) is window.stack
    assert row.widget(1) is window.gauge_pane


def test_they_are_actually_side_by_side_on_screen(window, qapp):
    """結構對還不夠 —— 量一次真的座標。

    這一條問的是「同一個視野」那句話本身：兩塊的**垂直**範圍要重疊（併排），
    而不是一個在另一個下面幾百 px 的地方。

    ⚠ 要先選一張卡：沒選的時候整個下半是收起來的（高度 0），而兩塊高度都是
    0 的時候「有沒有併排」問不出答案。
    """
    if not window.model.node_order:
        window.model.add_step("load_patch")
        window._refresh_all()
    window.select_node(window.model.node_order[0])
    qapp.processEvents()
    a = window.stack.geometry()
    b = window.gauge_pane.geometry()
    assert a.width() > 0 and b.width() > 0, (a, b)
    top, bottom = max(a.top(), b.top()), min(a.bottom(), b.bottom())
    assert bottom > top, "參數與儀表沒有併排：%s vs %s" % (a, b)


def test_the_image_stayed_in_its_own_column(window):
    """影像**不搬**：它是另一種迴圈（改參數 → 看圖），而且它要的是高度。"""
    kids = [window.root_splitter.widget(i)
            for i in range(window.root_splitter.count())]
    assert window.preview_pane in kids
    assert window.gauge_pane not in kids
    assert not window.preview_pane.isAncestorOf(window.gauge_pane), \
        "儀表還留在影像那一欄裡"


def test_the_card_name_is_only_written_once(window, qapp):
    """卡名與階段色只出現一次（U8）。

    兩邊各畫一次的話，同一張卡的名字在同一個框裡出現兩遍，而使用者要花一秒
    鐘確認那是不是兩張卡。儀表那一邊只留 Card / Features 兩顆切換鈕。
    """
    from PySide6.QtWidgets import QAbstractButton
    labels = [b.text() for b in window.gauge_pane.findChildren(QAbstractButton)]
    assert sorted(labels) == ["Card", "Features"], labels
