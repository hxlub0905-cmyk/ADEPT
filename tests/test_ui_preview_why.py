# U11：單顆預覽就看得到完整回溯 — authored 2026-09-08.
"""**回溯以前只有一條路：跑一整批 → Results → 點 score/bin。**

而使用者手上明明就有這一顆的每一個數字 —— 預覽已經算完了。那條路要求他先
跑一批（幾分鐘），只為了問一句「這一顆為什麼判成這樣」。

機制本來就在（`verdict_trace` 吃的是**特徵**，不是一批結果；
`highlight_path` 早就接上畫布了）—— 缺的只是入口。

這一支鎖住的：

0. ⚠ 底下一律問 ``isHidden()`` 而不是 ``isVisible()``：視窗還沒 ``show()``
   的時候每一個子元件的 ``isVisible()`` 都是 False（`docs/PITFALLS.md`），
   那樣問的話這幾條會**永遠是綠的**；
1. **沒跑整批就答得出來**（驗收條件本身）；
2. 那一行**點得下去**，而且點的是同一支（連結 → `toggle_preview_why`）；
3. **RichText 的跳脫**：路徑裡有 ``>``（``contrast > 120``），不跳脫的話那一段
   會被當成標籤吃掉 —— 使用者看到的是一句少了半截的話，而**沒有任何錯誤**；
4. 換一顆 defect 的時候面板要跟著換，**講不出來就收起來** —— 一份停在上一顆
   的回溯，旁邊配著這一顆的影像，是這個 repo 最怕的那個形狀。
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))
sys.path.insert(0, str(REPO / "tools"))

pytest.importorskip("PySide6")

from PySide6.QtWidgets import QApplication              # noqa: E402

from d4t.ui import studio as studio_mod                 # noqa: E402
from d4t.ui import theme as theme_mod                   # noqa: E402
from d4t.ui import welcome as welcome_mod               # noqa: E402

RSEM_RECIPE = REPO / "recipes" / "rsem-worst-box.json"


@pytest.fixture(scope="module")
def qapp():
    app = QApplication.instance() or QApplication([])
    theme_mod.apply_theme(app)
    yield app


@pytest.fixture(scope="module")
def rsem_lot(tmp_path_factory):
    from make_sample_rsem import generate
    return generate(str(tmp_path_factory.mktemp("why")), n=6, seed=11)


@pytest.fixture
def window(qapp, rsem_lot):
    """載了資料、載了一份**出貨的** recipe，而且**沒有跑整批**。"""
    win = studio_mod.StudioWindow(show_welcome_on_start=False)
    assert win.load_dataset_path(rsem_lot["klarf"], sync=True) is True
    assert win.load_recipe_path(str(RSEM_RECIPE), sync=True) is True
    win.refresh_preview(sync=True)
    yield win
    win.close()


# --------------------------------------------------------------------------- #
# 跳脫（純函式）
# --------------------------------------------------------------------------- #
def test_the_path_is_escaped_before_it_becomes_a_link():
    """``contrast > 120`` 裡那個 ``>`` 不跳脫的話會被當成標籤吃掉。"""
    markup = studio_mod.StudioWindow._decide_path_markup(
        "Path:  missing? no > contrast & tone < 5")
    assert "&gt;" in markup and "&amp;" in markup and "&lt;" in markup
    assert 'href="#why"' in markup


def test_no_path_means_no_link():
    """**不放一個點了沒事的連結。**"""
    assert studio_mod.StudioWindow._decide_path_markup("") == ""


# --------------------------------------------------------------------------- #
# 驗收條件：沒跑整批就看得到
# --------------------------------------------------------------------------- #
def test_a_single_preview_answers_why_without_running_the_batch(window):
    """**驗收條件本身。**"""
    assert not window.trial_results, "這條測試的前提是「還沒跑整批」"
    assert window.decide_path.text(), "預覽算完了卻沒有路徑那一行"

    assert window.toggle_preview_why() is True
    assert window.why_preview.isHidden() is False
    rows = window.why_preview.rows()
    assert rows, "面板開了卻是空的"
    # **問過的每一題都要在上面**，而且每一題都講得出「拿什麼比」——
    # 那是這個面板存在的理由。（``head`` 那幾列是分段標題，沒有名字。）
    steps = [r for r in rows if r.get("kind") == "step"]
    assert steps, rows
    assert all(r.get("name") and r.get("expr") for r in steps), steps
    # 而且講的是**這一顆**。
    assert window.why_preview.defect_id() == str(
        window.dataset.items[0].defect_id)


def test_the_line_itself_is_the_entry(window):
    """點那一行走的是同一支 —— 不是第二條會漂掉的路。"""
    assert window.why_preview.isHidden() is True
    window.decide_path.linkActivated.emit("#why")
    QApplication.processEvents()
    assert window.why_preview.isHidden() is False
    # 再點一次收起來（同一個手勢開關同一件事）。
    window.decide_path.linkActivated.emit("#why")
    QApplication.processEvents()
    assert window.why_preview.isHidden() is True


def test_it_follows_the_defect_you_are_looking_at(window):
    """換一顆 → 面板換一份。停在上一顆的話，數字跟旁邊的影像不是同一顆。"""
    window.toggle_preview_why()
    first = window.why_preview.defect_id()

    assert window.set_defect_index(1) is True
    window.refresh_preview(sync=True)
    QApplication.processEvents()
    assert window.why_preview.isHidden() is False
    assert window.why_preview.defect_id() != first
    assert window.why_preview.defect_id() == str(
        window.dataset.items[1].defect_id)


def test_taking_the_decision_away_closes_it(window):
    """**講不出來就收起來** —— 不是留著一份沒有主人的說明。

    ⚠ 走的是 `model.use_decide(False)`，不是 `window.remove_decision()`：
    後者**先跳一個 QMessageBox 問過**（那是對的 —— 一顆 ✕ 不該默默吃掉三層
    樹），而一個 modal 對話框在 headless 測試裡不會讓測試失敗，它會讓測試
    **永遠停在那裡**（`tests/conftest.py` 檔頭那句話）。這一條要驗的是
    「判定沒了之後面板怎麼辦」，不是那個確認框。
    """
    window.toggle_preview_why()
    assert window.why_preview.isHidden() is False

    window.model.use_decide(False)
    window.refresh_preview(sync=True)
    QApplication.processEvents()
    assert window.why_preview.isHidden() is True
    assert window.decide_path.text() == "", "判定沒了，那一行還在"


def test_without_a_decision_it_says_so_rather_than_opening_an_empty_panel(qapp):
    """沒有判定的 recipe：**說一句話**，不是開一個空面板。"""
    win = studio_mod.StudioWindow(show_welcome_on_start=False)
    try:
        assert win.toggle_preview_why() is False
        assert win.why_preview.isHidden() is True
        assert "nothing to replay" in win.status_text()
    finally:
        win.close()


def test_the_shipped_recipe_really_is_the_one_being_replayed(window):
    """這一支走的是**出貨的那一份**，不是測試自己造的東西。

    X4 讓範本庫指向 `recipes/`，而這一條順帶證明那份 recipe 從
    「載進來 → 預覽 → 回溯」整條路都活著。
    """
    assert welcome_mod.RECIPES_DIR / "rsem-worst-box.json" == RSEM_RECIPE
    assert window.model.kind == "rsem"
    assert window.model.decide is not None
