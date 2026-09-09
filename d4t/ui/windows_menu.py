# 「現在開著哪些視窗」的下拉 — authored 2026-09-08 (F99 P2-6).
"""Studio 有好幾個頂層視窗（Results、Region check、Uniformity…；規矩在
`docs/ARCHITECTURE.md` U15），而一台 1366×768 的機台 PC 上它們很快就疊在一起、
或被主視窗蓋住 —— 使用者要自己去工作列翻。這一支給工具列上**既有的**那顆鈕
（Help）掛一張下拉：列出開著的視窗，點了就拉到前面。

為什麼掛在 Help 上而不是加一顆鈕：那條工具列在 1366 上只剩 76 px
（`test_the_toolbar_still_fits_the_machine_beside_the_tool`），一顆「Windows」
就把它撐爆了。`MenuButtonPopup` 讓鈕本身照舊（點了開導覽），只多一個小箭頭。

選單**每次打開才建**（`aboutToShow`）：視窗是會開會關的，建一次就過期。
"""
from __future__ import annotations

from typing import Any, Callable, List, Optional, Sequence, Tuple

__all__ = ["attach", "rows"]

#: 提供者回的每一列：``(給人看的名字, 視窗或 None)``。None ＝ 這個視窗還沒開過。
Row = Tuple[str, Optional[Any]]


def rows(provider: Callable[[], Sequence[Row]]) -> List[Tuple[str, Optional[Any], bool]]:
    """把提供者回的列整理成 ``(名字, 視窗, 現在開著嗎)``。純函式，測試用。"""
    out: List[Tuple[str, Optional[Any], bool]] = []
    for title, win in (provider() or ()):
        alive = False
        if win is not None:
            try:
                alive = bool(win.isVisible())
            except RuntimeError:            # C++ 那一邊已經沒了
                win = None
        out.append((str(title), win, alive))
    return out


def attach(button, provider: Callable[[], Sequence[Row]]) -> None:
    """給一顆 QToolButton 掛上「Windows」下拉。"""
    from PySide6.QtWidgets import QMenu, QToolButton

    menu = QMenu(button)

    def rebuild() -> None:
        menu.clear()
        head = menu.addAction("Windows")
        head.setEnabled(False)
        for title, win, alive in rows(provider):
            act = menu.addAction(title if alive else "%s (not open)" % title)
            act.setEnabled(alive)
            if alive:
                act.triggered.connect(
                    lambda _c=False, w=win: (w.show(), w.raise_(),
                                             w.activateWindow()))

    menu.aboutToShow.connect(rebuild)
    button.setMenu(menu)
    button.setPopupMode(QToolButton.MenuButtonPopup)
    button.setToolTip(button.toolTip() + "\n\nThe arrow lists the windows "
                      "that are open right now and brings one to the front.")
