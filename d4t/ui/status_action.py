# 狀態列上那一句話的「下一步」 — authored 2026-09-08 (X5 ＋ X6).
"""**一句話說出發生了什麼，但沒有說接下來能做什麼。**

兩個不同的抱怨，同一個形狀：

* **X5 —— 流程的終點沒有出口。** 整批跑完寫出一個報表資料夾，狀態列說
  ``Wrote 6000 defects to ...\\report``，然後使用者要自己開檔案總管、自己把
  那條路徑貼進去。`QDesktopServices` 這個 repo 只用過一次（welcome 的說明
  連結）—— 出口一直在那裡，只是沒有接上。
* **X6 —— 破壞性操作要給即時反悔。** `_say_fallout` 會說「這條線接上去，那兩
  條被拿掉了」，而那句話在狀態列一閃即逝。**誤操作後的三秒鐘，是使用者最不想
  去找 Ctrl+Z 的三秒鐘** —— 他正在看那句話，而不是在想快捷鍵。

兩件事要的是同一個東西：**那一句話旁邊的一顆鈕**。所以這裡不是兩個機制，是
一個 —— 一顆掛在狀態列上、跟著訊息來去的按鈕。

三條規矩（都是踩得到的）
------------------------
1. **下一句話一定把它收起來。** 一顆停在那裡的「復原」按鈕，在使用者做了三件
   別的事之後按下去，復原的不是他以為的那一件。訊息換了 = 上下文換了 = 那顆鈕
   失效，沒有例外。
2. **它是補充，不是唯一的路。** Ctrl+Z 照樣在、報表資料夾的路徑照樣寫在訊息
   裡 —— 這顆鈕只是把「已經做得到的事」縮短成一次點擊。所以它壞掉的時候，
   沒有任何功能消失。
3. **不做那種按了會再問一次的鈕。** 三秒鐘的反悔要是三秒鐘，不是三秒鐘再加
   一個對話框。

⚠ **不要用 `isVisible()` 問它在不在**（`ui/problems_bar.py` 學到的同一課）：
頂層視窗還沒 `show()` 之前那個答案永遠是 False。這裡用 :meth:`StatusAction.armed`
—— 一個明確的狀態。
"""
from __future__ import annotations

from typing import Any, Callable, Optional

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QToolButton, QWidget

__all__ = ["StatusAction", "open_folder"]


def open_folder(path: Any) -> bool:
    """在系統的檔案瀏覽器裡開一個資料夾。開得成回 True。

    ⚠ **給的是資料夾就開資料夾，給的是檔案就開它所在的資料夾** —— 使用者說
    「帶我去」的時候，要的是那個位置，不是用某個程式把檔案打開（一份 CSV 被
    Excel 鎖住之後，下一次寫回去會失敗）。

    失敗**不拋例外**：這是一顆補充用的鈕（見檔頭第 2 條），開不起來的時候
    路徑仍然寫在訊息裡。呼叫端拿 False 去講一句話就好。
    """
    from pathlib import Path

    from PySide6.QtCore import QUrl
    from PySide6.QtGui import QDesktopServices

    try:
        p = Path(str(path))
        target = p if p.is_dir() else p.parent
        if not target.exists():
            return False
        return bool(QDesktopServices.openUrl(
            QUrl.fromLocalFile(str(target.resolve()))))
    except Exception:  # 補充用的鈕，不准害死呼叫端
        return False


class StatusAction(QToolButton):
    """狀態列那一句話旁邊的一顆鈕 —— 跟著訊息來，也跟著下一句訊息走。

    用法只有兩支：:meth:`arm`（這一句話有下一步）與 :meth:`disarm`
    （下一句話來了）。``studio._status`` 每次都呼叫後者，所以**忘了收**這件事
    在設計上就不會發生 —— 那比「記得在每個分支收掉」可靠。
    """

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.setCursor(Qt.PointingHandCursor)
        self.setToolButtonStyle(Qt.ToolButtonTextOnly)
        self.setObjectName("statusAction")
        self._callback: Optional[Callable[[], Any]] = None
        self._armed = False
        self.clicked.connect(self._fire)
        self.hide()

    # -- 狀態 ---------------------------------------------------------------
    def armed(self) -> bool:
        """現在有沒有掛著一個下一步（**明確狀態**，不問 `isVisible()`）。"""
        return self._armed

    def label(self) -> str:
        return self.text()

    # -- 掛上／收掉 ---------------------------------------------------------
    def arm(self, label: str, callback: Callable[[], Any],
            tip: str = "") -> None:
        """這一句話有下一步：``label`` 那顆鈕按下去就跑 ``callback``。"""
        text = str(label or "").strip()
        if not text or callback is None:
            self.disarm()
            return
        self._callback = callback
        self._armed = True
        self.setText(text)
        self.setToolTip(str(tip or text))
        self.setAccessibleName(str(tip or text))
        self.show()

    def disarm(self) -> None:
        """下一句話來了 —— 收起來（見檔頭第 1 條）。"""
        self._callback = None
        self._armed = False
        self.setText("")
        self.setToolTip("")
        self.hide()

    def _fire(self) -> None:
        """按下去。**先收再跑** —— 跑的過程會再講一句話，而那句話會自己 arm。

        順序反過來的話（先跑再收）就會把新那一句的鈕一起收掉，症狀是「復原
        之後那顆『重做』鈕閃一下就不見了」。
        """
        cb = self._callback
        self.disarm()
        if cb is not None:
            cb()
