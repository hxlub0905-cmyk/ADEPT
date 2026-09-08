# U16：UI 反應時間變成可測的門檻 — authored 2026-09-08.
"""**數值正確性有三層守護，UI 沒有任何可量化的門檻。**

「單批 10,000 顆仍然流暢」從 M2 就寫在 README 上，而它從來只是一個**設計目標**
—— 沒有一條測試問過。F90 那把「時間」的尺量的是引擎（`tools/bench.py`），
畫面那一面是空的。

門檻怎麼定（先量再設，跟 F90 同一套）
------------------------------------
2026-09-08 在容器裡量到的（6,000 顆）：

============================  ========
Results 開窗                  0.024 s
Gallery 鋪 6,000 顆            0.026 s
判定段重算（拖門檻那一下）      0.009 s
============================  ========

門檻設在**約 20 倍**。這個倍率是刻意的，而它換到的是一件很具體的事：
**它抓的是「有人把它寫成 O(n²)」，不是「今天機器慢了一點」。**

* 太緊（2×）→ CI 的 runner 一忙就紅，而一條會亂叫的測試三個禮拜之後就沒有
  人相信了（`tools/bench.py` 的時間欄用 2× 容差是因為它跑在**家用機**上，
  而這一份跑在共用的 runner 上 —— 同樣的道理要不同的數字）。
* 太鬆（1000×）→ 那是一道幾年都不會響的關（`test_size_ceilings.py` 的
  `test_the_general_ceiling_is_not_vacuous` 講的是同一句話）。

⚠ **它們量的是 UI 那一段，不是引擎。** 這裡沒有跑任何一張卡：結果是手捏的
dict，所以量到的純粹是「把 6,000 筆東西放進畫面上要多久」。
"""
from __future__ import annotations

import sys
import time
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))

#: 這個 KPI 講的「一批」有多大。M2 寫的是 10,000，這裡用 6,000 —— 那是外部
#: 檢視清單指名的數字，而兩者在同一個量級上（門檻抓的是量級，不是常數）。
N = 6000

#: 量到的基準（秒，2026-09-08 容器內）→ 門檻 = 基準 × 20。
#: **每一列都要能講出「這一下使用者在等什麼」**，不然它只是一個數字。
BUDGET = {
    # 跑完之後按 Results —— 使用者在等一個視窗出現。
    "results_open": 0.5,
    # 同一批鋪進縮圖網格。虛擬捲動的整個立身條件就是這一格（M2）。
    "gallery_fill": 0.5,
    # 拖門檻的那一下：每一格都要重算「哪一類有幾顆」。**這一格最緊** ——
    # 它在拖曳的過程中每幾毫秒就發生一次，慢一點就是整條拖不動。
    "verdict_refresh": 0.2,
}


@pytest.fixture(scope="module")
def qapp():
    from PySide6.QtWidgets import QApplication
    app = QApplication.instance() or QApplication([])
    yield app


def _rows(n: int = N):
    return [{"defect_id": str(i), "ok": True, "score": float(i % 97),
             "bin": i % 2, "features": {"glv_mean": float(i % 55)}}
            for i in range(n)]


@pytest.fixture
def loaded(qapp):
    """一個裝了 6,000 筆結果的 Studio（**不跑引擎** —— 量的是畫面那一段）。"""
    from d4t.ui.studio import StudioWindow
    win = StudioWindow()
    rows = _rows()
    win.trial_results = rows
    win.trial_scores = [r["score"] for r in rows]
    try:
        yield win, rows
    finally:
        win.close()


def _took(fn, repeat: int = 3) -> float:
    """跑幾次取**最快的那一次**。

    取最快而不是平均：這一份要量的是「這段程式碼要花多久」，而共用 runner 上
    的慢是別人造成的。最快的那一次最接近沒有干擾時的樣子 —— 平均會把一次
    排程延遲整個帶進來，而那正是讓這種測試變得會亂叫的原因。
    """
    best = float("inf")
    for _ in range(repeat):
        t0 = time.perf_counter()
        fn()
        best = min(best, time.perf_counter() - t0)
    return best


def test_opening_results_on_a_full_lot_is_not_a_wait(loaded, qapp):
    win, _rows_ = loaded
    def _go():
        win.results.set_features(["glv_mean"], default="glv_mean")
        win.results.show()
        qapp.processEvents()
    took = _took(_go)
    assert took < BUDGET["results_open"], (
        "6,000 顆下開 Results 花了 %.3f s（門檻 %.2f s）。\n"
        "  這一格抓的是量級 —— 慢成這樣通常是有人在這條路上加了一個逐顆的迴圈。"
        % (took, BUDGET["results_open"]))


def test_filling_the_gallery_stays_virtual(loaded, qapp):
    """M2 的「單批 10,000 顆仍然流暢」講的就是這一格 —— 而它一直沒有被量過。"""
    win, _rows_ = loaded
    items = [{"defect_id": str(i), "score": float(i % 97), "bin": i % 2}
             for i in range(N)]
    def _go():
        win.gallery.set_items(items)
        qapp.processEvents()
    took = _took(_go)
    assert took < BUDGET["gallery_fill"], (
        "鋪 %d 顆縮圖花了 %.3f s（門檻 %.2f s）—— 虛擬捲動是不是壞掉了？"
        % (N, took, BUDGET["gallery_fill"]))


def test_dragging_the_threshold_keeps_up(loaded, qapp):
    """**這一格最緊**：它在拖曳的過程中每幾毫秒就發生一次。"""
    win, _rows_ = loaded
    took = _took(win._refresh_verdict, repeat=5)
    assert took < BUDGET["verdict_refresh"], (
        "重算判定段花了 %.3f s（門檻 %.2f s）—— 拖門檻會變成一格一格跳。"
        % (took, BUDGET["verdict_refresh"]))


def test_the_budget_is_not_vacuous():
    """一道幾年都不會響的關等於沒有關（同 `test_size_ceilings` 那條）。

    這裡問的是**門檻本身還在合理的量級上**：有人把它從 0.5 改成 60 的時候，
    這一條會要求他先解釋一下。
    """
    for name, limit in BUDGET.items():
        assert 0.01 < limit <= 1.0, \
            "%s 的門檻 %.3f s 已經不在「使用者感覺得到」的範圍裡了" % (name, limit)


def test_every_budget_line_is_actually_measured():
    """表上列著的每一格都要有一支測試在量它。

    沒有這一條的話，刪掉一支測試而忘了拿掉那一列，這張表會變成一份願望清單
    （`CLAUDE.md`：任何例外／基準清單都要有反向的那一支）。
    """
    src = Path(__file__).read_text(encoding="utf-8")
    for name in BUDGET:
        assert src.count('BUDGET["%s"]' % name) >= 2, \
            "BUDGET 上的 %s 沒有任何一支測試在用它" % name
