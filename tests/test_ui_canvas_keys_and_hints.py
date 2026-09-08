# U18／U19／U20：鍵盤走得到、第一次接線找得到、兩種線分得開 — authored 2026-09-08.
"""三件都是「畫布上使用者做不到或看不出來的事」。

* **U18** `Delete` 只住在畫布與 cell_canvas 各自的 `keyPressEvent` 裡，主快捷
  鍵表上沒有 —— 於是「這個工具有哪些鍵」有兩個答案，而使用者讀得到的是不完整
  的那一個。`Esc` 與 Tab 則根本不存在。
* **U19** welcome 的導覽講三段式與四種 source，而新手真正卡住的是**怎麼把兩張
  卡接起來**：埠在哪、要用拖的、菱形埠與圓形埠不一樣。
* **U20** 影像流＝實線圓埠、區域＝虛線菱形埠 —— 設計是對的，但虛線 vs 實線在
  50% 縮放（主畫布常態）下幾乎看不出差別，而同一張 ROI 卡拉出去的兩條線還是
  同一個色相的濃淡兩版。
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


def _canvas(nodes, edges=()):
    from d4t.ui.canvas import PipelineCanvas
    c = PipelineCanvas()
    c.set_nodes(nodes, edges)
    return c


_LOAD = {"node_id": "a", "step": "load_patch", "label": "Load",
         "group": "input", "writes": ["test"]}
_DEN = {"node_id": "b", "step": "denoise", "label": "Denoise",
        "group": "enhance", "writes": ["test"]}
_ROI = {"node_id": "r", "step": "roi_reference", "label": "ROI",
        "group": "region", "writes": ["test"], "regions_out": ["epi", "mg"]}


# --------------------------------------------------------------------------- #
# U18：鍵盤
# --------------------------------------------------------------------------- #
def test_tab_walks_the_cards_in_run_order(qapp):
    c = _canvas([_LOAD, _DEN])
    try:
        assert c.step_selection(+1)
        assert c.selected_node() == "a", "沒選任何東西時 Tab 要選第一張"
        c.step_selection(+1)
        assert c.selected_node() == "b"
    finally:
        c.deleteLater()


def test_tab_wraps_around(qapp):
    """走到底就卡住只會讓人多按幾次 —— 一張畫布上的卡不多。"""
    c = _canvas([_LOAD, _DEN])
    try:
        c.step_selection(+1)
        c.step_selection(+1)
        c.step_selection(+1)
        assert c.selected_node() == "a"
        c.step_selection(-1)
        assert c.selected_node() == "b", "Shift+Tab 要往回走"
    finally:
        c.deleteLater()


def test_tab_on_an_empty_canvas_does_nothing(qapp):
    c = _canvas([])
    try:
        assert c.step_selection(+1) is False
    finally:
        c.deleteLater()


def test_delete_has_exactly_one_implementation(qapp):
    """畫布的 Delete 鍵與主視窗快捷鍵表上那一格走同一支（U18）。

    抄第二份到主視窗上正是這個 repo 最怕的形狀 —— 兩份會漂，而漂開的症狀是
    「用鍵盤刪得掉、用選單刪不掉」這種找不到原因的差別。
    """
    c = _canvas([_LOAD, _DEN])
    seen = []
    try:
        c.remove_requested.connect(seen.append)
        c.step_selection(+1)
        assert c.delete_selected() == 1
        assert seen == ["a"]
    finally:
        c.deleteLater()


def test_escape_lets_go_of_the_selection(qapp):
    from PySide6.QtCore import Qt
    from PySide6.QtGui import QKeyEvent
    from PySide6.QtCore import QEvent
    c = _canvas([_LOAD, _DEN])
    try:
        c.step_selection(+1)
        assert c.selected_node()
        c.keyPressEvent(QKeyEvent(QEvent.KeyPress, Qt.Key_Escape,
                                  Qt.NoModifier))
        assert c.selected_node() is None
    finally:
        c.deleteLater()


def test_escape_is_not_swallowed_when_nothing_is_selected(qapp):
    """Esc 在 Qt 裡還有一個更常見的意思（關掉這個對話框）。

    一個永遠吞掉 Esc 的畫布，會讓包著它的對話框關不掉 —— 而那個症狀離這裡
    很遠，沒有人會回頭懷疑畫布。
    """
    from PySide6.QtCore import QEvent, Qt
    from PySide6.QtGui import QKeyEvent
    c = _canvas([_LOAD])
    try:
        e = QKeyEvent(QEvent.KeyPress, Qt.Key_Escape, Qt.NoModifier)
        e.ignore()
        c.keyPressEvent(e)
        assert not e.isAccepted(), "沒東西可放的時候不該吞掉 Esc"
    finally:
        c.deleteLater()


def test_the_shortcut_table_lists_them(qapp):
    """「這個工具有哪些鍵」只有一個答案（U18）。"""
    from d4t.ui.studio import StudioWindow
    keys = dict(StudioWindow.SHORTCUTS)
    assert keys.get("Del") == "delete_selected"
    assert keys.get("Esc") == "clear_selection"


def test_the_canvas_only_keys_are_scoped_to_the_canvas(qapp):
    """**這張表最貴的一種錯**：Delete 綁在視窗上的話，使用者在參數區的輸入框
    裡按 Delete 會刪掉一張卡。"""
    from PySide6.QtCore import Qt
    from d4t.ui.studio import StudioWindow
    win = StudioWindow()
    try:
        scoped = [sc for sc in win._shortcuts
                  if sc.key().toString() in ("Del", "Esc")]
        assert scoped, "找不到那兩個快捷鍵"
        for sc in scoped:
            assert sc.context() == Qt.WidgetWithChildrenShortcut, \
                "%s 綁成 window-level 了" % sc.key().toString()
            assert sc.parent() is win.pipeline
    finally:
        win.close()


# --------------------------------------------------------------------------- #
# U19：第一次接線
# --------------------------------------------------------------------------- #
def test_one_card_and_no_wires_says_how_to_start(qapp):
    c = _canvas([_LOAD])
    try:
        assert "Drag" in c.first_wire_hint()
    finally:
        c.deleteLater()


def test_the_hint_goes_away_once_there_is_a_wire(qapp):
    """學會之後還一直在的提示會被忽略，而被忽略的提示會連帶讓旁邊真的重要的
    東西一起被忽略（推廣鐵則）。"""
    c = _canvas([_LOAD, _DEN], [("a", "b", "test", "streams")])
    try:
        assert c.first_wire_hint() == ""
    finally:
        c.deleteLater()


def test_picking_a_card_with_a_diamond_port_explains_it(qapp):
    c = _canvas([_LOAD, _ROI])
    try:
        c.set_selected("r")
        assert "diamond" in c.first_wire_hint()
    finally:
        c.deleteLater()


def test_a_plain_card_selected_says_nothing_extra(qapp):
    """兩張卡、沒有線、選到的那張沒有菱形埠 —— 那時候沒有話要講。"""
    c = _canvas([_LOAD, _DEN])
    try:
        c.set_selected("b")
        assert c.first_wire_hint() == ""
    finally:
        c.deleteLater()


# --------------------------------------------------------------------------- #
# U20：兩種線分得開
# --------------------------------------------------------------------------- #
def test_a_region_line_does_not_share_a_hue_with_the_stage(qapp):
    """同一張 ROI 卡拉出去的兩條線要是**不同色相**，不是同色相的濃淡兩版。"""
    from d4t.ui.canvas import region_color
    assert region_color("epi", 0).name() != region_color("", -1).name()


def test_two_regions_get_two_colours(qapp):
    """接到同一張量測卡的 epi 與 mg 兩條虛線要分得出誰是誰。"""
    from d4t.ui.canvas import region_color
    assert region_color("epi", 0).name() != region_color("mg", 1).name()


def test_the_index_is_stable_across_rebuilds(qapp):
    """同一份 recipe 每次開起來顏色都一樣 —— 不然「這條是哪個區域」學不起來。"""
    from d4t.ui.canvas import PipelineCanvas
    nodes = [_LOAD, _ROI, {"node_id": "g", "step": "glv_stats",
                           "label": "GLV", "group": "measure"}]
    edges = [("r", "g", "epi", "roi"), ("r", "g", "mg", "roi")]
    first = None
    for _ in range(3):
        c = PipelineCanvas()
        try:
            c.set_nodes(nodes, edges)
            got = (c.region_index("epi"), c.region_index("mg"))
            first = first if first is not None else got
            assert got == first, got
        finally:
            c.deleteLater()
    assert first == (0, 1), first


def test_an_unknown_region_name_is_not_given_a_colour(qapp):
    """猜一個顏色出來的話，畫面會**指錯**區域 —— 而那件事看不出來。"""
    c = _canvas([_LOAD])
    try:
        assert c.region_index("no_such_region") == -1
        from d4t.ui.canvas import region_color
        assert region_color("no_such_region", -1).name() == \
            region_color("", -1).name(), "認不得的名字要退回階段色"
    finally:
        c.deleteLater()
