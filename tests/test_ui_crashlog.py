# U3：未預期的錯誤要留下線索 — authored 2026-09-08.
"""**打包成 exe 之後沒有 console —— 出事＝程式不見，而你什麼都拿不到。**

驗收條件：「故意在一個 slot 內 raise，視窗不消失、log 檔存在且含 traceback」。
所以這一支盯的正是那三句：

1. 例外**寫得進磁碟**，而且寫進去的是 traceback（不是一句「發生錯誤」）；
2. 例外**沒有殺掉 event loop**（視窗還在）；
3. 寫不出去的時候**這一道網自己不炸** —— 它是最後一道，它掛了的話真正的
   那個錯誤就永遠不見了。

還有一條反向的：``d4t/ui/app.py`` 真的有掛上去。一個永遠不會被安裝的
excepthook 是這一整份最容易發生的失敗方式，而它不會讓任何測試變紅。
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))

pytest.importorskip("PySide6")

from PySide6.QtWidgets import QApplication, QPushButton    # noqa: E402

from d4t.ui import crashlog                                # noqa: E402
from d4t.ui import theme as theme_mod                      # noqa: E402


@pytest.fixture(scope="module")
def qapp():
    app = QApplication.instance() or QApplication([])
    theme_mod.apply_theme(app)
    yield app


@pytest.fixture
def log_dir(tmp_path):
    """log 寫到 tmp —— **不准碰開發者真正的那個資料夾**。

    那裡正是他下次真的出事時會去翻的地方，而一份測試留下的假當機紀錄在那裡
    看起來跟真的一模一樣。
    """
    before_dir, before_show = crashlog.LOG_DIR, crashlog.SHOW_DIALOG
    crashlog.LOG_DIR = str(tmp_path / "log")
    crashlog.SHOW_DIALOG = False        # modal 對話框會讓 headless 測試卡死
    crashlog._CURRENT.clear()
    yield Path(crashlog.LOG_DIR)
    crashlog.LOG_DIR, crashlog.SHOW_DIALOG = before_dir, before_show
    crashlog._CURRENT.clear()
    crashlog.uninstall()


def _boom():
    raise ValueError("a very specific thing went wrong")


def test_an_exception_in_a_slot_leaves_a_traceback_on_disk(qapp, log_dir):
    """驗收條件本身：**在 slot 裡 raise**，視窗還在，log 有 traceback。"""
    crashlog.install()
    button = QPushButton("boom")
    button.clicked.connect(_boom)
    button.click()                       # ← 這一下在 Qt 的 slot 裡拋例外
    qapp.processEvents()
    # **能走到這一行就是「視窗沒有消失」**：例外沒有傳出 `click()`，
    # 所以真的執行時 event loop 也不會被它殺掉。而 widget 還活著、
    # 還按得動 —— 再按一次會再記一次。
    button.click()
    qapp.processEvents()

    logs = crashlog.recent_logs()
    assert logs, "什麼都沒有寫出來"
    text = Path(logs[0]).read_text(encoding="utf-8")
    assert "ValueError" in text and "a very specific thing went wrong" in text
    # traceback 要**指得出是哪一行**，不然它跟一句錯誤訊息沒有差別。
    assert "Traceback" in text and "_boom" in text
    assert text.count("Traceback") == 2, "第二次按下去沒有被記到"
    button.deleteLater()


def test_one_session_writes_one_file(qapp, log_dir):
    """連續三個錯誤通常是同一件事的三個症狀 —— 分成三個檔會只傳回其中一個。"""
    crashlog.install()
    for i in range(3):
        try:
            raise RuntimeError("problem %d" % i)
        except RuntimeError:
            crashlog.record(*sys.exc_info())
    logs = crashlog.recent_logs()
    assert len(logs) == 1, logs
    text = Path(logs[0]).read_text(encoding="utf-8")
    assert text.count("Traceback") == 3


def test_it_does_not_blow_up_when_it_cannot_write(qapp, log_dir, tmp_path):
    """**最後一道網不准自己炸。** 寫不出去就回 ``""``，程式照樣活著。"""
    blocker = tmp_path / "blocked"
    blocker.write_text("I am a file, not a folder", encoding="utf-8")
    crashlog.LOG_DIR = str(blocker / "log")   # 父層是檔案 → makedirs 一定失敗
    crashlog._CURRENT.clear()
    try:
        raise KeyError("still needs to be survivable")
    except KeyError:
        assert crashlog.record(*sys.exc_info()) == ""


def test_ctrl_c_is_not_reported_as_a_bug(qapp, log_dir):
    """使用者自己按的中斷不是要回報的東西 —— 它照原本那條路走。"""
    crashlog.install()
    seen = []
    crashlog._PREVIOUS[0] = lambda *a: seen.append(a[0])
    try:
        raise KeyboardInterrupt()
    except KeyboardInterrupt:
        crashlog._hook(*sys.exc_info())
    assert seen and seen[0] is KeyboardInterrupt
    assert not crashlog.recent_logs(), "Ctrl+C 不該留下當機紀錄"


def test_old_logs_are_pruned(qapp, log_dir):
    """只增不減的資料夾在一台跑了兩年的機器上會變成沒有人敢動的東西。"""
    os.makedirs(str(log_dir), exist_ok=True)
    for i in range(crashlog.MAX_FILES + 5):
        (log_dir / ("d4t-2020010%d-%d.log" % (i % 9, i))).write_text(
            "old", encoding="utf-8")
    try:
        raise ValueError("new one")
    except ValueError:
        crashlog.record(*sys.exc_info())
    assert len(crashlog.recent_logs(limit=10 ** 6)) <= crashlog.MAX_FILES


def test_the_hook_is_actually_installed_by_the_app_entry_point():
    """**一個永遠不會被安裝的 excepthook 不會讓任何測試變紅** —— 除了這一條。

    刻意讀原始碼而不是跑 `app.main()`：那一支會進 event loop。
    """
    src = (REPO / "d4t" / "ui" / "app.py").read_text(encoding="utf-8")
    assert "crashlog.install()" in src, (
        "app.main() 沒有掛上 excepthook —— 那整個 crashlog.py 就只是一份"
        "沒有人呼叫的程式碼。")
