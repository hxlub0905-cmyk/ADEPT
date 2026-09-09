# X3：試跑抽哪幾顆 — authored 2026-09-08.
"""**「First 200」在一片 wafer 上是一個統計陷阱。**

KLARF 通常照掃描順序排，所以前 200 顆很可能集中在少數幾個 die 或同一個
cluster。在那一批上調好的門檻整批一跑就崩 —— 而畫面上沒有任何東西提示過。

⚠ 這一份跑在**核心那一批**（不 import Qt）。抽樣是一件純資料的事。
"""
from __future__ import annotations

import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))

from d4t.core.pipeline import sampling      # noqa: E402


class _Item:
    """一顆 defect 的最小替身 —— 抽樣只讀 `fields`。"""

    def __init__(self, i: int, cls: str = "1") -> None:
        self.defect_id = str(i)
        self.fields = {"CLASSNUMBER": cls}

    def __repr__(self) -> str:               # 失敗訊息讀得懂
        return "<%s cls=%s>" % (self.defect_id, self.fields["CLASSNUMBER"])


def _lot(n: int = 100, classes=("1",)):
    return [_Item(i, classes[i % len(classes)]) for i in range(n)]


# --------------------------------------------------------------------------- #
# 1. first —— 老行為，一個位元都不能變
# --------------------------------------------------------------------------- #
def test_first_is_exactly_the_old_slice():
    """`first` 仍然是預設，而且結果逐顆等於 `items[:n]`。

    這一條守的是「加了抽樣但沒有換掉任何人的行為」—— 沒有它，這個功能就是
    一次無聲的行為改動。
    """
    lot = _lot(50)
    got, note = sampling.pick(lot, 10)
    assert got == lot[:10]
    assert note["mode"] == "first"
    assert note["seed"] is None, "`first` 每次都一樣，給它種子只會讓紀錄說謊"


def test_asking_for_more_than_there_is_gives_everything():
    lot = _lot(5)
    got, note = sampling.pick(lot, 999)
    assert got == lot and note["n"] == 5 and note["of"] == 5


def test_an_empty_lot_is_not_an_error():
    got, note = sampling.pick([], 10)
    assert got == [] and note["n"] == 0


def test_an_unknown_mode_falls_back_to_first():
    """打錯的模式**不准安靜地隨機抽** —— 那會讓一次跑變成不可重現的。"""
    lot = _lot(20)
    got, note = sampling.pick(lot, 5, mode="raandom")
    assert got == lot[:5] and note["mode"] == "first"


# --------------------------------------------------------------------------- #
# 2. random —— 驗收條件本身
# --------------------------------------------------------------------------- #
def test_two_random_runs_pick_different_defects():
    """**驗收條件（上）**：同一份資料集連跑兩次隨機抽樣，選中的集合不同。"""
    lot = _lot(500)
    a, na = sampling.pick(lot, 50, mode="random")
    b, nb = sampling.pick(lot, 50, mode="random")
    assert na["seed"] != nb["seed"], "每次要自己生一個新種子"
    assert [x.defect_id for x in a] != [x.defect_id for x in b]


def test_the_same_seed_picks_the_same_defects():
    """**驗收條件（下）**：帶同一個種子則相同。

    一次跑出漂亮結果而重現不了，等於沒有跑過。
    """
    lot = _lot(500)
    a, _ = sampling.pick(lot, 50, mode="random", seed=4242)
    b, _ = sampling.pick(lot, 50, mode="random", seed=4242)
    assert [x.defect_id for x in a] == [x.defect_id for x in b]


def test_random_does_not_just_take_the_front():
    """整個陷阱就是「前 N 顆擠在少數 die」—— 隨機抽要真的散得開。"""
    lot = _lot(1000)
    got, _ = sampling.pick(lot, 100, mode="random", seed=7)
    assert max(int(x.defect_id) for x in got) > 500


def test_the_order_that_comes_back_is_the_original_order():
    """`run_batch` 的契約是「回傳順序 = 原始 item 順序」，而 KLARF 寫回、
    結果表、縮圖全部依賴它 —— 抽樣不該把那件事改掉。"""
    lot = _lot(200)
    got, _ = sampling.pick(lot, 30, mode="random", seed=11)
    ids = [int(x.defect_id) for x in got]
    assert ids == sorted(ids)


def test_no_defect_is_drawn_twice():
    lot = _lot(100)
    got, _ = sampling.pick(lot, 40, mode="random", seed=3)
    assert len({x.defect_id for x in got}) == 40


# --------------------------------------------------------------------------- #
# 3. strata —— 稀少的那一類正是使用者在調的那一類
# --------------------------------------------------------------------------- #
def test_a_rare_class_still_shows_up():
    """一個只有 3 顆的類別，「照比例」算出來是 0 —— 而那一類常常正是重點。"""
    lot = _lot(297) + [_Item(1000 + i, "9") for i in range(3)]
    got, note = sampling.pick(lot, 30, mode="strata", seed=5)
    assert note["mode"] == "strata" and note["column"] == "CLASSNUMBER"
    assert any(x.fields["CLASSNUMBER"] == "9" for x in got), \
        "稀少的那一層一顆都沒抽到"


def test_strata_still_returns_the_number_asked_for():
    """四捨五入會少幾顆 —— 補滿，不然畫面上那個「30」講的是假話。"""
    lot = _lot(300, classes=("1", "2", "3", "7"))
    got, _ = sampling.pick(lot, 30, mode="strata", seed=5)
    assert len(got) == 30


def test_strata_is_reproducible_too():
    lot = _lot(300, classes=("1", "2", "5"))
    a, _ = sampling.pick(lot, 40, mode="strata", seed=99)
    b, _ = sampling.pick(lot, 40, mode="strata", seed=99)
    assert [x.defect_id for x in a] == [x.defect_id for x in b]


def test_more_layers_than_defects_asked_for():
    """20 層抽 5 顆 —— 不該爆掉，也不該回 20 顆。"""
    lot = [_Item(i, str(i)) for i in range(20)]
    got, _ = sampling.pick(lot, 5, mode="strata", seed=1)
    assert len(got) == 5


def test_a_column_that_is_not_there_says_so_in_the_record():
    """那一欄整批是空的 → **退成 random 並在紀錄裡說出來**。

    硬分一層的話它跟 random 一模一樣，而紀錄會說它是分層的 —— 跑得完、
    有數字、而且紀錄是錯的（這個 repo 最怕的形狀）。
    """
    lot = _lot(100)
    for it in lot:
        it.fields = {}
    got, note = sampling.pick(lot, 20, mode="strata", seed=2)
    assert len(got) == 20
    assert note["mode"] == "random" and note["column"] == ""


def test_values_are_stripped_like_route_by_does():
    """KLARF 的值都是字串，`"1"` 與 `" 1"` 要落在同一層（跟 RouteBy 同一套）。"""
    lot = [_Item(i, " 1" if i % 2 else "1") for i in range(40)]
    got, note = sampling.pick(lot, 10, mode="strata", seed=4)
    assert note["mode"] == "random", "兩個值其實是同一層 → 只有一層 → 退成隨機"
    assert len(got) == 10


# --------------------------------------------------------------------------- #
# 4. 給使用者看的字
# --------------------------------------------------------------------------- #
def test_every_mode_has_a_word_and_a_reason():
    """工具列上那個字要跟著換 —— 跑的東西變了而畫面沒變是最危險的失敗方式。"""
    for mode in sampling.MODES:
        word, why = sampling.describe(mode)
        assert word.strip() and len(why.split()) > 4, mode
    assert sampling.describe("nonsense") == sampling.describe("first")


def test_the_seed_is_small_enough_to_read_out_loud():
    """它會被寫進 run 紀錄，而使用者要能把它唸給同事聽。"""
    for _ in range(20):
        assert 100000 <= sampling.new_seed() <= 999999


# --------------------------------------------------------------------------- #
# 5. 種子要讓使用者讀得到（不然它等於不存在）
# --------------------------------------------------------------------------- #
def test_the_seed_reaches_the_user(monkeypatch):
    """**一次「random 200」跑出漂亮結果而重現不了，等於沒有跑過。**

    種子存在 `sample_note` 上還不夠 —— Studio 不寫 runs.db（只有 CLI 寫），
    所以跑完那句話是使用者唯一讀得到它的地方。
    """
    import os
    import pytest
    pytest.importorskip("PySide6.QtWidgets", exc_type=ImportError)
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    from PySide6.QtWidgets import QApplication
    QApplication.instance() or QApplication([])
    from d4t.ui.studio import StudioWindow

    win = StudioWindow()
    try:
        win.sample_note = {"mode": "random", "seed": 424242, "n": 200,
                           "of": 6000}
        line = win._sample_line()
        assert "424242" in line, line
        assert "random" in line, line

        # `first` 是預設 —— 不必說（每一句多餘的話都在跟真正重要的那句搶注意）
        win.sample_note = {"mode": "first", "seed": None}
        assert win._sample_line() == ""

        # 退成 random 的時候要講**真的發生的那一個**，不是使用者選的那一個
        win.sample_note = {"mode": "random", "seed": 7, "column": ""}
        assert "random" in win._sample_line()
    finally:
        win.close()
