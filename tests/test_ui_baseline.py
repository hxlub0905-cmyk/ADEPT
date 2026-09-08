# X1：調參迴圈的記憶 — authored 2026-09-08.
"""**「剛才那個改動讓它變好還是變壞」** —— 這一支鎖住那句話答得出來。

四件事：

1. 兩塊 snapshot 相減是**純函式**（不用開視窗就測得起來，所以它不會因為
   UI 改版而失去守護）；
2. 沒有答案卷的時候仍然講得出東西（顆數與「判進非 0 bin 的有幾顆」），
   **而不是一片空白**；
3. 顆數不一樣的兩批放在一起比，那件事要**寫在畫面上** —— 差值有數字而且
   完全沒有意義，是這個 repo 最怕的那個形狀（「跑得完、有數字、而且是錯的」）；
4. 釘住的那一塊**關窗重開還在**（驗收條件的後半句）。
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))

pytest.importorskip("PySide6")

from PySide6.QtCore import QSettings                 # noqa: E402
from PySide6.QtWidgets import QApplication           # noqa: E402

from d4t.ui import baseline                          # noqa: E402
from d4t.ui import theme as theme_mod                # noqa: E402
from d4t.ui.results import ResultsWindow             # noqa: E402


@pytest.fixture(scope="module")
def qapp():
    app = QApplication.instance() or QApplication([])
    theme_mod.apply_theme(app)
    yield app


def _results(n_real_wrong: int = 0, n: int = 10):
    """一批假結果：前一半是真缺陷（bin 1），後一半不是（bin 0）。

    ``n_real_wrong`` 顆真缺陷被判成 bin 0（＝ 漏抓），用來造出兩次不同的
    正確率。
    """
    rows, truth = [], {}
    half = n // 2
    for i in range(n):
        real = i < half
        wrong = real and i < n_real_wrong
        rows.append({"defect_id": str(i), "ok": True,
                     "score": 1.0 if real else 0.0,
                     "bin": 0 if (not real or wrong) else 1})
        truth[str(i)] = {"is_real": bool(real)}
    return rows, truth


# --------------------------------------------------------------------------- #
# 純函式（不用 QApplication）
# --------------------------------------------------------------------------- #
def test_a_better_run_reads_as_a_plus_and_a_worse_one_as_a_minus():
    rows_a, truth = _results(n_real_wrong=2)      # 漏 2 顆 → 8/10
    rows_b, _ = _results(n_real_wrong=0)          # 一顆都沒漏 → 10/10
    a = baseline.snapshot(rows_a, truth)
    b = baseline.snapshot(rows_b, truth)

    line = baseline.diff_line(b, a)
    assert "accuracy 100% (+20)" in line, line
    assert "missed 0 (-2)" in line, line
    # 反過來也要對得上 —— 一個只會往上的差值等於沒有差值。
    assert "accuracy 80% (-20)" in baseline.diff_line(a, b)


def test_no_change_still_writes_a_zero_rather_than_a_blank():
    """**空白分不出「沒變」與「沒有這個數字」**，而那兩件事意思相反。"""
    rows, truth = _results(n_real_wrong=1)
    snap = baseline.snapshot(rows, truth)
    line = baseline.diff_line(snap, snap)
    assert "(+0)" in line, line


def test_without_a_ground_truth_it_still_says_something_useful():
    rows_a, _ = _results(n_real_wrong=3)
    rows_b, _ = _results(n_real_wrong=0)
    a = baseline.snapshot(rows_a)                 # 沒有答案卷
    b = baseline.snapshot(rows_b)
    assert a["accuracy"] is None
    line = baseline.diff_line(b, a)
    assert "10 defects" in line
    assert "flagged 5 (+3)" in line, line


def test_two_batches_of_different_size_say_so():
    """First 50 與 First 200 的正確率放在一起比 —— 差值必須帶著那句警語。"""
    rows_a, truth = _results(n_real_wrong=1, n=10)
    rows_b, truth_b = _results(n_real_wrong=1, n=20)
    truth.update(truth_b)
    line = baseline.diff_line(baseline.snapshot(rows_b, truth),
                              baseline.snapshot(rows_a, truth))
    assert "not the same batch" in line, line


# --------------------------------------------------------------------------- #
# 存得住（驗收條件的後半句）
# --------------------------------------------------------------------------- #
def test_a_pinned_baseline_survives_closing_the_window(qapp, tmp_path):
    """關窗重開 baseline 還在 —— **這正是它跟一個變數的差別**。"""
    ini = str(tmp_path / "d4t.ini")
    rows, truth = _results(n_real_wrong=2)
    snap = baseline.snapshot(rows, truth)

    win = ResultsWindow()
    win.baseline_store = baseline.BaselineStore(
        QSettings(ini, QSettings.IniFormat))
    win.set_run_snapshot(snap)
    assert win.pin_baseline() is True
    win.close()

    again = ResultsWindow()
    again.baseline_store = baseline.BaselineStore(
        QSettings(ini, QSettings.IniFormat))
    again.baseline_bar.set_baseline(again.baseline_store.load())
    assert again.baseline_bar.baseline() is not None
    assert "accuracy 80%" in again.baseline_text(), again.baseline_text()
    again.close()


def test_the_bar_shows_the_difference_once_a_baseline_is_pinned(qapp, tmp_path):
    rows_a, truth = _results(n_real_wrong=2)
    rows_b, _ = _results(n_real_wrong=0)
    win = ResultsWindow()
    win.baseline_store = baseline.BaselineStore(
        QSettings(str(tmp_path / "x.ini"), QSettings.IniFormat))

    assert "nothing pinned" in win.baseline_text()
    win.set_run_snapshot(baseline.snapshot(rows_a, truth))
    win.pin_baseline()
    win.set_run_snapshot(baseline.snapshot(rows_b, truth))
    text = win.baseline_text()
    # 驗收條件：**A、B 與差值同時看得到**。只給差值的話，使用者知道
    # 「好了 20 個百分點」卻不知道「從幾變成幾」。
    assert "accuracy 100% (+20)" in text, text        # B ＋ 差值
    assert "baseline: accuracy 80%" in text, text     # A

    win.clear_baseline()
    assert "pin it" in win.baseline_text()
    win.close()


def test_pinning_needs_a_run(qapp, tmp_path):
    """還沒跑過就沒有東西可以釘 —— **那顆鈕要是灰的，不是按了沒反應的**。"""
    win = ResultsWindow()
    win.baseline_store = baseline.BaselineStore(
        QSettings(str(tmp_path / "y.ini"), QSettings.IniFormat))
    assert win.baseline_bar.btn_pin.isEnabled() is False
    assert win.pin_baseline() is False
    win.close()
