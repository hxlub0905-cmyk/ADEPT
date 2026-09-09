# 未預期的錯誤要留下線索 — authored 2026-09-08 (U3).
"""**打包成離線 exe 之後沒有 console —— 出事＝程式直接不見，而你什麼都拿不到。**

現況（2026-09-08 量的）：整個 ``d4t/`` 沒有任何一處用 ``logging``，也沒有
``sys.excepthook``。（2026-09-09 起 ``logging`` 有了 —— ``d4t/core/log.py``，
接**被接住然後吃掉**的例外；這一份接的是**沒被接住**的。兩份寫進同一個
資料夾。）開發時這件事看不出來，因為錯誤會印在終端機上；而
`docs/NO-GIT-SETUP.md` 那台機器是**解壓縮就跑**，那裡沒有終端機。

於是使用者能講的話只有「它突然關掉了」，而那句話裡沒有任何可以查的東西。

這一份買到什麼
--------------
1. **視窗不會消失**：Qt 的 slot 裡拋出來的例外走 ``sys.excepthook``，接住它
   就不會殺掉 event loop（PySide6 的預設是印出來然後繼續）。
2. **磁碟上有一份 traceback**：Windows 放 ``%LOCALAPPDATA%/d4t/log``，
   其他平台放 ``~/.d4t/log``。
3. **使用者知道它在哪**：跳一個對話框，上面有「開啟資料夾」——
   「請把 log 傳回來」這句話沒有那顆鈕的話，等於在要求使用者去找一個他從來
   沒聽過的資料夾。

它刻意**不**做的兩件事
----------------------
* **不吞掉例外的意義。** 對話框上寫的是「這是一個沒有被預期到的錯誤」，
  不是「操作失敗」—— 後者會讓使用者以為是自己按錯了。
* **不 log 使用者的資料。** 寫進去的是 traceback 與版本資訊，不是 recipe、
  不是路徑以外的檔案內容 —— 廠內識別碼不該離開那台機器（鐵則 8 的精神）。
"""
from __future__ import annotations

import os
import sys
import time
import traceback
from typing import Any, List

__all__ = [
    "SHOW_DIALOG", "MAX_FILES", "LOG_DIR", "log_dir", "log_path", "install",
    "uninstall", "record", "recent_logs",
]

#: log 要寫去哪（``""`` = 照 :func:`log_dir` 算的那個真的位置）。
#:
#: 測試用的鉤子（同 `fit_screen.FORCE_RECT`）：沒有它的話，跑一次測試就會在
#: 開發者真正的 ``~/.d4t/log`` 底下留一份假的當機紀錄 —— 而那正是他下次真的
#: 出事時會去翻的資料夾。
LOG_DIR = ""

#: 出事時要不要跳對話框。**測試把它關掉** —— 一個 modal 對話框在 headless
#: 測試裡不會讓測試失敗，它會讓測試永遠停在那裡（`tests/conftest.py` 的
#: `PROMPT_ON_CLOSE` 是同一個教訓）。
SHOW_DIALOG = True

#: 留幾份 log。舊的自己刪掉 —— 一個只增不減的資料夾在一台跑了兩年的機台旁
#: PC 上會變成沒有人敢動的東西。
MAX_FILES = 20

#: 這個 session 的 log **檔名**（不含資料夾 —— 資料夾每次重算，`LOG_DIR`
#: 才換得動）。
_CURRENT: List[str] = []
#: 被換掉的那個 excepthook（`uninstall` 要還回去）。
_PREVIOUS: List[Any] = []


def log_dir() -> str:
    """log 放哪裡。

    Windows 用 ``%LOCALAPPDATA%``（漫遊設定檔不該扛 log），其他平台用
    ``~/.d4t/log`` —— 跟 `autosave` 同一個家，理由也一樣：**使用者找得到，
    而且不需要管理員權限**。
    """
    if LOG_DIR:
        return str(LOG_DIR)
    base = os.environ.get("LOCALAPPDATA") if os.name == "nt" else ""
    if base:
        return os.path.join(base, "d4t", "log")
    return os.path.join(os.path.expanduser("~"), ".d4t", "log")


def log_path() -> str:
    """這個 session 的 log 檔（第一次呼叫時決定名字）。

    **一個 session 一個檔**，不是一個錯誤一個檔：連續三個錯誤通常是同一件事
    的三個症狀，而分成三個檔會讓使用者只傳回其中一個。
    """
    if not _CURRENT:
        _CURRENT.append("d4t-%s-%d.log"
                        % (time.strftime("%Y%m%d-%H%M%S"), os.getpid()))
    return os.path.join(log_dir(), _CURRENT[0])


def recent_logs(limit: int = MAX_FILES) -> List[str]:
    """log 資料夾裡的檔案（新的在前）。讀不到就回空的。"""
    try:
        names = [os.path.join(log_dir(), n) for n in os.listdir(log_dir())
                 if n.startswith("d4t-") and n.endswith(".log")]
    except OSError:
        return []
    names.sort(key=lambda p: os.path.getmtime(p) if os.path.exists(p) else 0,
               reverse=True)
    return names[:int(limit)]


def _prune() -> None:
    for stale in recent_logs(limit=10 ** 6)[MAX_FILES:]:
        try:
            os.remove(stale)
        except OSError:  # 刪不掉就算了
            pass


def record(exc_type: Any, exc: Any, tb: Any) -> str:
    """把一個例外寫進 log；回傳寫到哪（寫不出去回 ``""``）。

    **寫不出去不可以再拋一次。** 這一支是最後一道網 —— 它自己炸掉的話，
    使用者看到的會是一個關於 log 的錯誤，而真正的那個錯誤永遠不見了。
    """
    text = "".join(traceback.format_exception(exc_type, exc, tb))
    stamp = time.strftime("%Y-%m-%d %H:%M:%S")
    block = ("\n" + "=" * 72 + "\n"
             "%s  ·  python %s  ·  %s\n%s\n"
             % (stamp, sys.version.split()[0], sys.platform, text))
    path = log_path()
    try:
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "a", encoding="utf-8") as f:
            f.write(block)
        _prune()
        return path
    except OSError:
        return ""


def _tell_the_user(exc: Any, path: str) -> None:
    """跳那個對話框（沒有 QApplication 就什麼都不做）。"""
    try:
        from PySide6.QtCore import QUrl
        from PySide6.QtGui import QDesktopServices
        from PySide6.QtWidgets import QApplication, QMessageBox
    except Exception:  # 沒有 Qt 就只有 log
        return
    if QApplication.instance() is None:
        return

    box = QMessageBox()
    box.setIcon(QMessageBox.Warning)
    box.setWindowTitle("d4t hit an unexpected error")
    # **第一句要說「這不是你按錯了」。** 使用者對一個看不懂的錯誤的預設反應
    # 是「我剛才做錯了什麼」，而那個反應會讓他不回報。
    box.setText("Something went wrong inside d4t. This is a bug in the "
                "program, not something you did.")
    box.setInformativeText(
        "d4t is still running - what you were doing may not have finished.\n\n"
        "%s\n\nThe details were written to:\n%s\n\n"
        "Please send that file back so it can be fixed."
        % (("%s: %s" % (type(exc).__name__, exc))[:300],
           path or "(the log could not be written)"))
    open_btn = None
    if path:
        open_btn = box.addButton("Open the folder", QMessageBox.ActionRole)
    box.addButton(QMessageBox.Close)
    box.exec()
    if open_btn is not None and box.clickedButton() is open_btn:
        QDesktopServices.openUrl(QUrl.fromLocalFile(os.path.dirname(path)))


def _hook(exc_type: Any, exc: Any, tb: Any) -> None:
    # Ctrl+C **照原本的路走** —— 使用者自己按的中斷不是一個要回報的 bug。
    if issubclass(exc_type, KeyboardInterrupt):
        (_PREVIOUS[0] if _PREVIOUS else sys.__excepthook__)(exc_type, exc, tb)
        return
    path = record(exc_type, exc, tb)
    # 開發時仍然要看得到 —— 這一份是**補**一條路，不是取代終端機那一條。
    try:
        sys.__excepthook__(exc_type, exc, tb)
    except Exception:  # 沒有 stderr 的環境
        pass
    if SHOW_DIALOG:
        try:
            _tell_the_user(exc, path)
        except Exception:  # 最後一道網不准自己炸
            pass


def install() -> str:
    """掛上 excepthook；回傳這個 session 的 log 路徑。重複呼叫是安全的。"""
    if not _PREVIOUS:
        _PREVIOUS.append(sys.excepthook)
    sys.excepthook = _hook
    return log_path()


def uninstall() -> None:
    """還原（測試用；正常執行時整個 process 都掛著）。"""
    if _PREVIOUS:
        sys.excepthook = _PREVIOUS.pop()
    else:
        sys.excepthook = sys.__excepthook__
