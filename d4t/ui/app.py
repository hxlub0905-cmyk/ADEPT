# d4t Studio 進入點 — authored 2026-07-28 (M3).
"""``python -m d4t.ui.app`` —— 開一個 d4t Studio 視窗。

薄薄一層：建 QApplication → 套主題 → 開主視窗 → 進 event loop。
所有邏輯都在 :mod:`d4t.ui.studio`，這裡刻意什麼都不做，
方便未來換成別的殼（嵌進廠內既有 app）時只改這一個檔。
"""
from __future__ import annotations

import sys
from typing import List, Optional, Sequence

from PySide6.QtWidgets import QApplication

from . import crashlog, fit_screen, scope, theme
from .branding import app_icon
from .studio import StudioWindow
from .welcome import saved_theme

__all__ = ["main"]


def main(argv: Optional[Sequence[str]] = None) -> int:
    """開視窗並跑到使用者關掉為止；回傳 process exit code。"""
    args: List[str] = list(sys.argv if argv is None else argv)
    if not args:
        args = ["d4t-studio"]

    # ⚠ **第一件事**，在建 QApplication 之前：一個在啟動階段炸掉的 d4t 是
    # 最沒有線索的那一種（畫面上什麼都還沒有出現過），而它正是最需要一份
    # traceback 的那一種（U3）。
    crashlog.install()

    # 產品範圍（U10）：一個字串決定一組開關。**在建任何視窗之前** ——
    # `HIDDEN_STEPS` 是卡片庫建構時就讀掉的，晚一步設等於沒設。
    scope.use_profile(scope.profile_from_env())

    app = QApplication.instance()
    if app is None:
        app = QApplication(args)
    # 設在 app 上而不是每個視窗上 —— 所有 top-level 視窗（Studio、Results、
    # 各種對話框）都會跟著繼承，之後開新視窗不必記得補一行。
    app.setWindowIcon(app_icon())
    theme.apply_theme(app, saved_theme(theme.DEFAULT_THEME))

    win = StudioWindow()
    # **要多大取小的那一個**（U1）：1440×900 是開發機的尺寸，而目標機器是
    # 機台旁那台 1366×768 的 PC。放不下的下場不是「小一點」，是底部那排鈕
    # 在螢幕外面。
    fit_screen.fit(win, 1440, 900)
    win.show()
    fit_screen.keep_on_screen(win)
    return int(app.exec())


if __name__ == "__main__":
    raise SystemExit(main())
