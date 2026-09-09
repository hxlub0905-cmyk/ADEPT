"""`docs/plans/` 是**進行中**的計畫書；做完不再改的搬進 `docs/history/plans/`。

2026-09-09 量到的：`docs/plans/` 裡 8 份，其中 7 份對應的功能早就出貨
（F78–F82 在 09-03、F99／F100 在 09-08），而檔頭沒有任何一句話說它做到哪。
「這一份還在動嗎」要翻 SESSION_LOG 才答得出來 —— 那是把狀態抄在另一份的
反面：狀態根本沒寫。規矩：**每一份計畫書前 5 行要有一句「狀態：」**；
寫「已收斂」的請搬去 history（CLAUDE.md §4 本來就這樣說）。
"""
from __future__ import annotations

import re
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parent.parent
PLANS = sorted((REPO / "docs" / "plans").glob("*.md"))


def test_there_are_plans_or_the_folder_is_gone():
    """空資料夾不會讓下面那條變成「什麼都沒測而且是綠的」。"""
    assert PLANS or not (REPO / "docs" / "plans").exists()


@pytest.mark.parametrize("path", PLANS, ids=[p.name for p in PLANS])
def test_an_open_plan_says_where_it_stands(path):
    head = "".join(path.read_text(encoding="utf-8").splitlines(keepends=True)[:5])
    assert "狀態：" in head, (
        "%s 前 5 行沒有「狀態：」—— 寫一句它做到哪；已收斂的搬進 docs/history/plans/"
        % path.name)


@pytest.mark.parametrize("path", PLANS, ids=[p.name for p in PLANS])
def test_a_plan_that_says_it_is_done_has_moved_out(path):
    head = "".join(path.read_text(encoding="utf-8").splitlines(keepends=True)[:5])
    m = re.search(r"狀態：([^\n]*)", head)
    assert m
    status = m.group(1).strip().lstrip("*").strip()
    assert not status.startswith("已收斂"), (
        "%s 說自己已收斂，卻還在 docs/plans/ —— 搬去 docs/history/plans/" % path.name)
