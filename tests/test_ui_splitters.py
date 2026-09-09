"""區域之間的細線（`ui/splitters.py`，2026-09-09）。

F100 v2 用 QSS 做這件事，結果是一根 5–9px 的實心灰條，而沒有任何測試量過
「看得見的那條有幾個像素」—— 對比度測試只問 token 的顏色差夠不夠。這裡真的
開一支 splitter、抓圖、沿著把手數像素：兩個方向、兩個主題。
"""
from __future__ import annotations

import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
UI = ROOT / "d4t" / "ui"


@pytest.fixture(scope="module")
def qapp():
    from PySide6.QtWidgets import QApplication

    return QApplication.instance() or QApplication([])


def _run_across(splitter, orient):
    """把手正中央那一列（或那一行）的顏色，含把手外各 2px。"""
    from PySide6.QtCore import Qt
    from PySide6.QtGui import QColor

    img = splitter.grab().toImage()
    g = splitter.handle(1).geometry()
    if orient == Qt.Horizontal:
        xs = range(g.left() - 2, g.right() + 3)
        return g.width(), [QColor(img.pixel(x, splitter.height() // 2)).name() for x in xs]
    ys = range(g.top() - 2, g.bottom() + 3)
    return g.height(), [QColor(img.pixel(splitter.width() // 2, y)).name() for y in ys]


@pytest.mark.parametrize("theme_name", ["light", "dark"])
@pytest.mark.parametrize("orient_name", ["Horizontal", "Vertical"])
def test_the_handle_is_5px_to_grab_and_1px_to_see(qapp, theme_name, orient_name):
    from PySide6.QtCore import Qt
    from PySide6.QtWidgets import QWidget

    from d4t.ui import theme
    from d4t.ui.splitters import HANDLE_PX, HairlineSplitter

    theme.apply_theme(qapp, theme_name)
    orient = getattr(Qt, orient_name)
    sp = HairlineSplitter(orient)
    sp.addWidget(QWidget())
    sp.addWidget(QWidget())
    sp.resize(200, 200)
    sp.show()
    qapp.processEvents()
    sp.setSizes([100, 100])
    qapp.processEvents()
    try:
        size, run = _run_across(sp, orient)
        divider = theme.TOKENS["divider"].lower()
        page = theme.TOKENS["bg_page"].lower()
        assert size == HANDLE_PX, (orient_name, size)
        assert run.count(divider) == 1, (orient_name, theme_name, run)
        assert run.index(divider) == 2 + HANDLE_PX // 2, "線要在把手正中間：%s" % run
        assert all(c == page for c in run if c != divider), \
            "把手其餘部分要是頁面底色，不是塗滿分隔色：%s" % run
    finally:
        sp.close()
        theme.apply_theme(qapp, "light")


def test_every_splitter_in_the_ui_is_the_hairline_one():
    """`QSplitter(` 不准再直接出現在 `d4t/ui` —— 那條線是同一條規矩，
    少一支就少一條線。"""
    offenders = []
    for py in sorted(UI.glob("*.py")):
        if py.name == "splitters.py":
            continue
        for lineno, line in enumerate(py.read_text(encoding="utf-8").splitlines(), 1):
            if re.search(r"\bQSplitter\(", line):
                offenders.append("%s:%d" % (py.name, lineno))
    assert not offenders, offenders


def test_the_stylesheet_no_longer_sizes_or_colours_the_handle():
    """尺寸與顏色都搬進 `splitters.py` 了；QSS 那一邊只准把背景放掉。
    兩邊各管一半的那一天，就是「直向 5px、橫向 9px」回來的那一天。"""
    from d4t.ui import theme

    qss = theme.build_stylesheet()
    block = "\n".join(l for l in qss.splitlines() if "QSplitter::handle" in l)
    assert block, "QSS 裡要留 QSplitter::handle（test_ui_widgets 也在問）"
    for forbidden in ("width:", "height:", "margin:", "border-left", "border-top",
                      theme.TOKENS["divider"]):
        assert forbidden not in block, (forbidden, block)
