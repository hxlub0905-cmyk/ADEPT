# U12：design token 不准再洩漏出來 — authored 2026-09-08.
"""**F7-23 修掉過一次的那件事，2026-09-08 量到它回流了。**

`d4t/ui` 底下有 40 支 `setStyleSheet()`，而其中十九支自己寫死了尺寸：
`font-size` 同時活著 9 / 10 / 11 / 12 / 15 五種、`border:1px` 十幾處、
`border-radius:8px` 三處（而「一塊面」的圓角 token 是 6px —— 那三個是漂出來
的）。每一個單看都無害，合起來就是「同一種東西在不同面板上長得不一樣，而沒有
任何東西擋得住它繼續漂」。

這一份就是那個「擋得住」。它問三件事，而**三件都是 F7-23 已經付過錢的**：
字級、線粗、圓角。

為什麼不是「任何 `\\d+px` 都不准」（那是外部檢視清單原本寫的做法）
--------------------------------------------------------------
掃過一次：`d4t/ui` 底下 300 多個 `\\d+px` 裡，絕大多數在**註解與 docstring**
裡（「埠畫出來 11px 寬」「離底只有 7px」），它們是解釋，不是設定。把它們一起
擋掉的結果是下一個人把說明裡的數字拿掉 —— 那讓程式碼變難懂，而畫面一點都沒
有變好。

`padding` 也刻意不擋：它是**這一個 widget 跟它裡面的字之間**的距離，本來就
一個地方一個值（chip 的 `4px 12px` 跟空狀態的 `10px` 沒有理由相等）。字級、
線粗、圓角不一樣 —— 那三個是**整個 app 的視覺語言**，一個變了其他都該跟著變。

⚠ 這一份配一支反向測試（`CLAUDE.md`：任何例外清單都要有那支反向的）——
`_ALLOWED` 上寫著的例外要真的還在，修好了卻沒拿掉的話那支檔案從此少一條防線
而測試照樣綠。
"""
from __future__ import annotations

import ast
import re
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))

#: 只問這三個屬性 —— 見上面「為什麼不是任何 px」。
_WATCHED = ("font-size", "border-radius", "border")

#: `border:` 後面帶的第一個長度就是線粗；`border-radius` 與 `font-size` 整個值。
_PX = re.compile(r"(font-size|border-radius|border)\s*:\s*([^;\"']*)")
_LITERAL = re.compile(r"\b\d+px\b")

#: **例外：檔案 → 還剩幾個**，每一列要講得出為什麼。
#:
#: 空的。一支都不剩是刻意的：這張表一旦有第一列，下一個人的反射動作就是加
#: 第二列。真的需要例外的時候，寫下來的那句話要是「這個尺寸跟別的地方無關」，
#: 而不是「這個改起來很麻煩」。
_ALLOWED: dict = {}


def _leaks(path: Path):
    """這支檔案裡，`setStyleSheet()` 的字串上寫死尺寸的地方。"""
    out = []
    for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
        if not isinstance(node, ast.Call):
            continue
        fn = node.func
        name = fn.attr if isinstance(fn, ast.Attribute) else getattr(fn, "id", "")
        if name != "setStyleSheet":
            continue
        for sub in ast.walk(node):
            if not (isinstance(sub, ast.Constant) and isinstance(sub.value, str)):
                continue
            for prop, value in _PX.findall(sub.value):
                if prop in _WATCHED and _LITERAL.search(value):
                    out.append((sub.lineno, prop, value.strip()))
    return out


def _ui_files():
    return [p for p in sorted((REPO / "d4t" / "ui").glob("*.py"))
            if p.name != "theme.py"]


@pytest.mark.parametrize("rel", [p.name for p in _ui_files()])
def test_no_panel_writes_its_own_size(rel):
    """字級、線粗、圓角只有一個家：`ui/theme.py` 的 TOKENS。"""
    path = REPO / "d4t" / "ui" / rel
    found = _leaks(path)
    allowed = _ALLOWED.get(rel, 0)
    assert len(found) <= allowed, (
        "%s 有 %d 個寫死的尺寸（允許 %d）：\n  %s\n"
        "  請改吃 token：字級 TOKENS['font_small'] 那一組、線粗 "
        "TOKENS['hairline']、圓角 TOKENS['radius_md']。\n"
        "  自繪那一面要數字的話用 theme.font_px() / theme.radius()。"
        % (rel, len(found), allowed,
           "\n  ".join("%d: %s: %s" % f for f in found)))


def test_the_allowlist_does_not_rot():
    """反向的那一支：表上寫著幾個，就要真的還有幾個。"""
    for rel, n in _ALLOWED.items():
        assert len(_leaks(REPO / "d4t" / "ui" / rel)) == n, (
            "%s 的例外從 %d 變了 —— 把 _ALLOWED 改對（修好了就整列拿掉）" % (rel, n))


def test_the_scale_has_a_number_side_too():
    """QSS 那一面吃字串、自繪那一面吃 int，而兩邊要是同一個數字。

    沒有 `font_px()` 的話，自繪的程式碼會寫 `setPixelSize(11)` —— 那就是同一個
    洩漏換一個出口。
    """
    from d4t.ui import theme
    for name in ("font_micro", "font_tiny", "font_small", "font_body",
                 "font_title"):
        assert theme.TOKENS[name].endswith("px")
        assert theme.font_px(name) == int(theme.TOKENS[name][:-2])
    assert theme.font_px("no_such_token") == 12, "不認得的名字要有一個能用的退路"


def test_the_scale_is_actually_a_scale():
    """五級要真的由小到大，而且不重複 —— 兩個同值的 token 是兩個名字一個意思。"""
    from d4t.ui import theme
    sizes = [theme.font_px(n) for n in ("font_micro", "font_tiny", "font_small",
                                        "font_body", "font_title")]
    assert sizes == sorted(sizes), sizes
    assert len(set(sizes)) == len(sizes), ("兩個字級撞在一起了：%s" % sizes)
