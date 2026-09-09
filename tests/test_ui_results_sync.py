# d4t — Results 視窗：縮圖與表格同一個排序、同一個篩選（2026-09-09）。
"""使用者：「希望它跟 Tiles 一樣支援排序跟篩選」。兩種看法看的是同一批，
所以條件只有一份：宿主走 `ResultsWindow.set_filter` 一次餵兩邊；任何一邊
按掉 chip 另一邊也清；縮圖的排序下拉換了表格照那欄排，表頭點了下拉跟著。

Qt 一律 lazy import。
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


@pytest.fixture(scope="module")
def qapp():
    from PySide6.QtWidgets import QApplication

    from d4t.ui import theme as theme_mod
    app = QApplication.instance() or QApplication([])
    theme_mod.apply_theme(app, "light")
    yield app


def _results():
    return [
        {"defect_id": "1", "ok": True, "bin": 2, "score": 0.42,
         "features": {"glv": 90.0}},
        {"defect_id": "2", "ok": True, "bin": 0, "score": 0.10,
         "features": {"glv": 10.0}},
        {"defect_id": "3", "ok": True, "bin": 0, "score": 0.77,
         "features": {"glv": 50.0}},
    ]


def _window(qapp):
    from d4t.ui.results import ResultsWindow
    win = ResultsWindow()
    rows = _results()
    win.gallery.set_sort_keys(["score", "glv"])
    win.gallery.set_items([dict(r, thumb=None) for r in rows])
    win.set_table(rows, {"1": "bright"})
    return win


def _table_ids(win):
    t = win.table
    return [t.cell_text(i, "defect_id") for i in range(t.row_count())]


def test_one_filter_reaches_both_views_and_either_chip_clears_both(qapp):
    from PySide6.QtCore import Qt

    win = _window(qapp)
    try:
        win.set_filter({"mode": "bin", "bin": 0})
        assert sorted(win.gallery.displayed_ids()) == ["2", "3"]
        assert sorted(_table_ids(win)) == ["2", "3"]
        # 表格那顆 chip → 兩邊都清
        win.table._filter_chip.click()
        assert win.gallery.displayed_count() == 3 and win.table.row_count() == 3
        # 縮圖那顆 chip → 兩邊都清
        win.set_filter({"mode": "bin", "bin": 2})
        assert win.table.row_count() == 1
        chips = [c for c in win.gallery._chips]
        assert chips, "縮圖那邊要有 chip"
        chips[0].click()
        assert win.gallery.filter_text() == "" and win.table.row_count() == 3
        _ = Qt
    finally:
        win.close()


def test_the_gallery_sort_drives_the_table_and_back(qapp):
    from PySide6.QtCore import Qt

    win = _window(qapp)
    try:
        # 縮圖下拉挑 glv 降冪 → 表格照 glv 降冪
        win.gallery.sort_combo.setCurrentIndex(
            win.gallery.sort_keys().index("glv") + 1)
        assert _table_ids(win) == ["1", "3", "2"], _table_ids(win)
        # 表頭點 score 升冪 → 縮圖的排序跟著
        cols = win.table.columns()
        win.table.table.sortByColumn(cols.index("score"), Qt.AscendingOrder)
        assert win.gallery.sort_key() == "score"
        assert win.gallery.sort_descending() is False
        assert win.gallery.displayed_ids() == ["2", "1", "3"]
    finally:
        win.close()
