# 狀態列說過的話要留得住 — authored 2026-09-08 (U2 後半).
"""**狀態列是暫態的，而它常常是唯一講出「那件事沒成功」的地方。**

`studio._status` 的說明自己寫著：狀態列是唯一會講出「這件事沒成功」的地方
（lint 擋下試跑、卡片加不進去、模板存不起來）。而 ``showMessage`` 的下一句話
就會把上一句蓋掉 —— 使用者眼角瞄到一行紅字、伸手去看，畫面上已經換成
「Added denoise」了。

Problems 列（`ui/problems_bar.py`）補的是**現在還有什麼擋著**，這一份補的是
**剛才發生過什麼**。兩個是不同的問題：前者從 recipe 推導得出來（lint 隨時可以
重跑），後者不行 —— 一句「Could not save: PermissionError」再也回不來。

一顆鈕，不是一塊面板
--------------------
它掛在狀態列右邊（``addPermanentWidget``），平常只有一個字。把歷史攤在畫面上
的話，那塊空間每一天有 99% 的時間裝的是使用者已經讀過的東西 —— 而狀態列本來
就是「看一眼就走」的地方。
"""
from __future__ import annotations

import time
from typing import Any, Dict, List, Optional

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog, QListWidget, QPushButton, QToolButton, QVBoxLayout, QWidget,
)

__all__ = ["MAX_LINES", "StatusHistory", "StatusHistoryDialog"]

#: 記幾句。**只增不減的清單在一台開了一整天的機器上是一個記憶體洞**，
#: 而使用者要回頭找的永遠是最近那幾句 —— 更早的他已經處理完了。
MAX_LINES = 200


class StatusHistoryDialog(QDialog):
    """歷史清單（新的在最上面 —— 使用者要找的是「剛才那一句」）。"""

    def __init__(self, lines: List[Dict[str, Any]],
                 parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("What d4t has been saying")
        self.setModal(False)          # 一邊看一邊回去修，不要擋著主視窗
        from . import fit_screen

        lay = QVBoxLayout(self)
        lay.setContentsMargins(12, 12, 12, 12)
        lay.setSpacing(8)
        self.list = QListWidget(self)
        for row in reversed(lines):
            self.list.addItem("%s  %s%s" % (row["at"],
                                            "⚠ " if row["level"] == "error"
                                            else "", row["text"]))
        lay.addWidget(self.list, 1)
        close = QPushButton("Close", self)
        close.clicked.connect(self.close)
        lay.addWidget(close, 0, Qt.AlignRight)
        fit_screen.fit(self, 720, 420)


class StatusHistory(QToolButton):
    """狀態列右邊那一顆 —— 點開是「剛才說過的話」。

    宿主每次 `_status` 都呼叫 :meth:`add`；這個 widget 自己不碰狀態列，
    所以它跟「訊息長什麼樣」完全解耦。
    """

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self._lines: List[Dict[str, Any]] = []
        self._dialog: Optional[StatusHistoryDialog] = None
        self.setCursor(Qt.PointingHandCursor)
        self.setAutoRaise(True)
        self.clicked.connect(self.open_history)
        self._sync()

    # ---- 對外 -------------------------------------------------------------
    def add(self, text: str, level: str = "info") -> None:
        line = str(text or "").strip()
        if not line:
            return
        # 同一句連著講兩次只留一句 —— 重新整理一次面板會把同一則訊息再說一遍，
        # 而一份「同一句話 40 次」的歷史等於沒有歷史。
        if self._lines and self._lines[-1]["text"] == line:
            return
        self._lines.append({"at": time.strftime("%H:%M:%S"), "text": line,
                            "level": str(level or "info")})
        del self._lines[:-MAX_LINES]
        self._sync()

    def lines(self) -> List[Dict[str, Any]]:
        return [dict(r) for r in self._lines]

    def open_history(self) -> Optional[StatusHistoryDialog]:
        if not self._lines:
            return None
        self._dialog = StatusHistoryDialog(self._lines, self.window())
        self._dialog.show()
        return self._dialog

    def _sync(self) -> None:
        n = len(self._lines)
        self.setText("History" if not n else "History (%d)" % n)
        self.setEnabled(bool(n))
        self.setToolTip(
            "Everything the status bar has said this session - it scrolls "
            "past fast, and the line that mattered is usually the one that "
            "just got replaced." if n else "Nothing has been said yet.")
