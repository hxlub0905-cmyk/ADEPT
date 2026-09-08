# U10：產品範圍收斂成 profile — authored 2026-09-08.
"""**那幾個旗標已經開始互相牽扯，而「一起設對」沒有任何東西在守。**

實例（F91 X4 那一輪付過的錢）：`SHOW_SAMPLE_ENTRIES` 一個旗標管兩個入口，
而它們的**死法不一樣** —— 範本庫的理由到期了，範例資料那條仍然是死路。合在
一起的下場是「打開其中一個順手把另一個也放回畫面上」，而那顆鈕按下去會撞牆
（推廣鐵則：按了撞牆的鈕比沒有那顆鈕更糟）。拆開之後又多了一個問題：三個旗標
要一起設對。

profile 把「這台機器要看到什麼」變成一句話。這一份守的是那句話真的算數。
"""
from __future__ import annotations

import ast
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))

from d4t.ui import scope                     # noqa: E402 — 不 import Qt


@pytest.fixture(autouse=True)
def _restore_profile():
    """**測試不准把 profile 留給下一支測試。**

    它是模組層的狀態，而模組在一個行程裡只 import 一次 —— 忘了還原的話，
    後面每一支測試看到的是這一支設的那一組，而失敗會出現在別的檔案上。
    """
    before = scope.current_profile()
    yield
    scope.use_profile(before)


def test_the_default_is_the_fab_machine():
    """目標使用者是廠內那台機器上的人 —— 預設就該是他看到的那一組。"""
    assert scope.DEFAULT_PROFILE == "fab"


def test_a_profile_sets_every_switch_it_names():
    scope.use_profile("dev")
    assert scope.SHOW_ROUTE_BY is True
    assert scope.HIDDEN_STEPS == ()
    scope.use_profile("fab")
    assert scope.SHOW_ROUTE_BY is False
    assert scope.HIDDEN_STEPS == ("align",)


def test_every_profile_sets_the_same_switches():
    """一組漏設一個旗標的話，那個旗標會**留著上一組的值** —— 而症狀是
    「換了 profile 但有一格沒變」，找起來要翻三個檔案。"""
    keys = [set(v) for v in scope.PROFILES.values()]
    assert all(k == keys[0] for k in keys), \
        "各組管的旗標不一樣：%s" % {n: sorted(v) for n, v in scope.PROFILES.items()}


def test_an_unknown_name_falls_back_instead_of_raising():
    """這是產品範圍的旋鈕，不是輸入驗證的地方 —— 打錯字不該讓 Studio 開不起來。"""
    assert scope.use_profile("no_such_profile") == "fab"
    assert scope.current_profile() == "fab"
    assert scope.use_profile("") == "fab"


def test_the_environment_decides_at_startup():
    """廠內那台是**點捷徑開的** —— 捷徑改得動環境變數，改不動命令列。"""
    assert scope.profile_from_env({"D4T_PROFILE": "dev"}) == "dev"
    assert scope.profile_from_env({}) == scope.DEFAULT_PROFILE
    assert scope.profile_from_env({"D4T_PROFILE": ""}) == scope.DEFAULT_PROFILE


def test_the_hidden_steps_really_disappear_from_the_library():
    """驗收條件：每個 profile 開窗後看得到的入口與它宣告的一致。

    這裡問的是**卡片庫真的少了那張卡**，不是「旗標的值對不對」—— 後者是
    上面那條，而兩條中間那一段（`visible_steps` 有沒有讀到新值）壞掉的話，
    只有這一條會紅。
    """
    from d4t.core.pipeline.step import list_steps
    import d4t.core.steps                    # noqa: F401 — 觸發註冊

    described = [s.describe() for s in list_steps()]
    scope.use_profile("dev")
    dev_keys = {d["key"] for d in scope.visible_steps(described)}
    scope.use_profile("fab")
    fab_keys = {d["key"] for d in scope.visible_steps(described)}
    assert "align" in dev_keys, "dev 應該看得到收起來的卡"
    assert "align" not in fab_keys


# --------------------------------------------------------------------------- #
# 「一個寫入端」那條規矩
# --------------------------------------------------------------------------- #
_FLAGS = ("SHOW_TEMPLATE_LIBRARY", "SHOW_SAMPLE_DATA", "SHOW_ROUTE_BY",
          "HIDDEN_STEPS")


def test_nobody_copies_a_flag_at_import_time():
    """**旗標要透過模組讀。**

    `from .scope import SHOW_ROUTE_BY` 拿到的是一份**當時的複本**，而
    `use_profile()` 改的是 scope 模組上的那個名字 —— 換了 profile 而那個模組
    停在舊值，症狀是「設定說關著、畫面上還在」，而它離設定很遠。

    這一條是踩出來的：`welcome.py` 本來就是這樣寫的（U10 那一輪改掉）。
    """
    bad = []
    for path in sorted((REPO / "d4t").rglob("*.py")):
        if path.name == "scope.py":
            continue
        for node in ast.parse(path.read_text(encoding="utf-8")).body:
            if not isinstance(node, ast.ImportFrom):
                continue
            if not str(node.module or "").endswith("scope"):
                continue
            for a in node.names:
                if a.name in _FLAGS:
                    bad.append("%s:%d 抄了 %s" % (path.name, node.lineno, a.name))
    assert not bad, (
        "這幾個地方在 import 時就把旗標的值抄走了：\n  %s\n"
        "  改成 `from . import scope` 再讀 `scope.<旗標>`。" % "\n  ".join(bad))


def test_the_flags_a_profile_names_are_real():
    """表上寫著的旗標要真的存在（打錯字的話它會安靜地建一個新的全域名字）。"""
    for name, switches in scope.PROFILES.items():
        for key in switches:
            assert hasattr(scope, key), "%s 那一組寫了不存在的旗標 %s" % (name, key)
