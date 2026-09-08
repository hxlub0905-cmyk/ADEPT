# U4：當機、斷電、被砍掉之後救得回來 — authored 2026-09-08.
"""**關窗有網（`_ask_unsaved`），當機沒有。**

驗收條件是「kill process 後重開，救回的 recipe 與 kill 前的 model 逐項相同」。
沒有辦法在測試裡真的 kill 一個 process，所以這一支拆成**兩半**：

* 「kill 前」＝ 那份草稿真的在磁碟上，而且它的內容是 model 的
  ``to_json_dict()`` **逐項相同**（不是「差不多」）；
* 「重開」＝ 一個全新的視窗吃那份草稿，套出來的 model 跟原本那個逐項相同。

⚠ 這一支自己接管 `autosave.DIR` 與 `ASK_ON_START`：測試不准寫到開發者真正的
``~/.d4t``，也不准跳 modal 對話框（headless 會永遠停在那裡）。
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))

pytest.importorskip("PySide6")

from PySide6.QtWidgets import QApplication              # noqa: E402

from d4t.ui import autosave                             # noqa: E402
from d4t.ui import studio as studio_mod                 # noqa: E402
from d4t.ui import theme as theme_mod                   # noqa: E402

sys.path.insert(0, str(REPO / "tests"))
from conftest import first_source                       # noqa: E402


@pytest.fixture(scope="module")
def qapp():
    app = QApplication.instance() or QApplication([])
    theme_mod.apply_theme(app)
    yield app


@pytest.fixture
def draft_dir(tmp_path):
    before_dir, before_ask = autosave.DIR, autosave.ASK_ON_START
    autosave.DIR = str(tmp_path / "home")
    autosave.ASK_ON_START = False          # modal 會讓 headless 測試卡死
    yield Path(autosave.DIR)
    autosave.DIR, autosave.ASK_ON_START = before_dir, before_ask


@pytest.fixture
def window(qapp, draft_dir):
    win = studio_mod.StudioWindow(show_welcome_on_start=False)
    win.autosave.start()                   # 測試裡預設是關的（見 studio）
    yield win
    win.autosave.stop()
    win.close()


# --------------------------------------------------------------------------- #
# 檔案那一半
# --------------------------------------------------------------------------- #
def test_what_lands_on_disk_is_exactly_the_model(window, draft_dir):
    """**逐項相同**，不是「差不多」—— 救回來的東西要能繼續調參。"""
    first_source(window)
    window._on_add_requested("glv_stats")
    assert window.autosave.write_now(), "什麼都沒有寫出來"

    data = autosave.load()
    assert data is not None
    assert data["recipe"] == window.model.to_recipe().to_json_dict()


def test_the_write_is_atomic(window, draft_dir):
    first_source(window)
    path = window.autosave.write_now()
    assert os.path.isfile(path)
    assert not os.path.exists(path + ".tmp"), (
        "鐵則 5：寫到一半的草稿比沒有草稿更糟 —— 它會讓那句「要救回來嗎」"
        "指向一個載不起來的檔案")


def test_an_empty_canvas_throws_the_old_draft_away(window, draft_dir):
    """清空畫布、關掉、再開 —— **不可以**被問要不要救回剛剛刪掉的東西。"""
    nid = first_source(window)
    window.autosave.write_now()
    assert autosave.load() is not None

    window._on_remove_requested(nid)
    assert window.autosave.write_now() == ""
    assert autosave.load() is None


def test_which_file_it_came_from_comes_back_too(window, draft_dir, tmp_path):
    """救回來之後 ``Ctrl+S`` 要知道存回哪 —— 那份資訊本來就在草稿裡。"""
    first_source(window)
    window.recipe_path = str(tmp_path / "mine.json")
    window.autosave.write_now()
    assert autosave.load()["source_path"] == str(tmp_path / "mine.json")


# --------------------------------------------------------------------------- #
# 重開那一半
# --------------------------------------------------------------------------- #
def test_a_fresh_window_gets_the_same_model_back(qapp, window, draft_dir):
    """驗收條件本身：**救回的 recipe 與 kill 前的 model 逐項相同**。"""
    first_source(window)
    window._on_add_requested("glv_stats")
    before = window.model.to_recipe().to_json_dict()
    window.autosave.write_now()
    # ⚠ 這裡**不 close** —— close 會清掉草稿（那是正常關窗），而要模擬的是
    # 「沒有走到 closeEvent 就沒了」。
    window.autosave.stop()

    fresh = studio_mod.StudioWindow(show_welcome_on_start=False)
    try:
        assert autosave.restore_into(fresh, autosave.load()) is True
        assert fresh.model.to_recipe().to_json_dict() == before
        assert fresh.model.dirty is True, "救回來的東西還沒有存過"
    finally:
        fresh.autosave.stop()
        fresh.close()


def test_a_clean_close_takes_the_draft_with_it(qapp, draft_dir):
    """正常關窗＝已經問過「要不要存」了，草稿留著只會下次再問一次。"""
    win = studio_mod.StudioWindow(show_welcome_on_start=False)
    win.autosave.start()
    first_source(win)
    win.autosave.write_now()
    assert autosave.load() is not None
    win.close()
    assert autosave.load() is None


def test_a_saved_draft_is_not_worth_asking_about(draft_dir):
    """存過了的草稿跟磁碟上那一份一樣 —— 沒有什麼好救的。"""
    autosave.save({"routes": {}}, "/tmp/x.json", dirty=False)
    assert autosave.describe(autosave.load()) == ""
    autosave.save({"routes": {}}, "/tmp/x.json", dirty=True)
    assert "x.json" in autosave.describe(autosave.load())


def test_the_question_says_which_pipeline_and_when(draft_dir):
    """一句「要救回上次的東西嗎」答不出使用者唯一的問題：*上次是哪一次*。"""
    autosave.save({"routes": {"ebi_patch": {}}}, "", dirty=True)
    text = autosave.describe(autosave.load())
    assert "not saved anywhere yet" in text
    assert ":" in text, "沒有時間 —— 那句話就答不出「上次是哪一次」"


def test_a_broken_draft_does_not_stop_the_window_from_opening(qapp, draft_dir):
    """**一張網不准擋路。** 壞掉的草稿只是被丟掉，不是一個開不起來的 Studio。"""
    os.makedirs(str(draft_dir), exist_ok=True)
    Path(autosave.path()).write_text("{ not json at all", encoding="utf-8")
    assert autosave.load() is None

    autosave.save({"steps": "this is not a recipe"}, "", dirty=True)
    win = studio_mod.StudioWindow(show_welcome_on_start=False)
    try:
        assert autosave.restore_into(win, autosave.load()) is False
    finally:
        win.autosave.stop()
        win.close()


def test_it_does_not_write_while_the_tests_run_unless_asked(qapp, draft_dir):
    """開一次 Studio 就往開發者的 ``~/.d4t`` 寫一份草稿 —— **那是個 bug**。"""
    win = studio_mod.StudioWindow(show_welcome_on_start=False)
    try:
        assert win.autosave.armed() is False
        first_source(win)
        assert win.autosave.write_now() == ""
        assert autosave.load() is None
    finally:
        win.close()
