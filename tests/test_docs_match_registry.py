"""文件裡寫的「幾張卡」「幾份 recipe」要跟 registry 與 `recipes/` 對得上。

2026-09-09 量到的：`CLAUDE.md` 說出貨 recipe「目前只有一份」、`ROADMAP.md`
說「目前三份」、實際兩份；`README.md` 說卡片 18 張可見 17 張、registry 是
19 與 18。四處數字三種答案 —— 而 `CLAUDE.md` §0 自己宣導的就是「同一件事只
寫在一個地方，抄出來的那份一定會漂」。這一支把那幾個數字釘回真值：文件可以
寫數字，但寫了就要對。

不想被這支測試管的做法只有一種：**把那句話裡的數字拿掉**，改成連結。
"""
from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parent.parent
_CN = {1: "一", 2: "兩", 3: "三", 4: "四", 5: "五", 6: "六", 7: "七", 8: "八", 9: "九"}


def _registry():
    import d4t.core.steps  # noqa: F401 — 註冊
    from d4t.core.pipeline.step import list_steps
    from d4t.ui import scope
    keys = [s.key for s in list_steps()]
    visible = [k for k in keys if k not in scope.HIDDEN_STEPS]
    return len(keys), len(visible)


def _shipped():
    return sorted(p for p in (REPO / "recipes").glob("*.json")
                  if json.loads(p.read_text(encoding="utf-8")))


def _text(rel: str) -> str:
    return (REPO / rel).read_text(encoding="utf-8")


def test_the_readme_counts_the_cards_the_registry_has():
    registered, visible = _registry()
    m = re.search(r"(\d+) 張步驟卡片（卡片庫現行可見 (\d+) 張", _text("README.md"))
    assert m, "README.md 那句「N 張步驟卡片（卡片庫現行可見 M 張」不見了"
    assert (int(m.group(1)), int(m.group(2))) == (registered, visible), (
        "README.md 說 %s 張／可見 %s 張，registry 是 %d／%d"
        % (m.group(1), m.group(2), registered, visible))


def test_the_architecture_tree_counts_the_cards_the_registry_has():
    registered, visible = _registry()
    m = re.search(r"註冊 (\d+) 張，卡片庫可見 (\d+) 張", _text("docs/ARCHITECTURE.md"))
    assert m, "docs/ARCHITECTURE.md 那句「註冊 N 張，卡片庫可見 M 張」不見了"
    assert (int(m.group(1)), int(m.group(2))) == (registered, visible), m.group(0)


@pytest.mark.parametrize("rel", ["CLAUDE.md", "docs/ROADMAP.md"])
def test_the_docs_count_the_shipped_recipes(rel):
    n = len(_shipped())
    text = _text(rel)
    hits = re.findall(r"目前(?:只有)?([一兩二三四五六七八九十\d]+)份", text)
    assert hits, "%s 裡沒有「目前 N 份」那句話了 —— 改了句型就把這條測試一起改" % rel
    want = {str(n), _CN[n]} if n in _CN else {str(n)}
    bad = [h for h in hits if h not in want]
    assert not bad, "%s 說出貨 recipe「目前%s份」，recipes/ 裡是 %d 份" % (rel, bad, n)


def test_no_doc_names_the_next_card_by_number():
    """「加第 18 張卡的人」那種句子每加一張卡就過期一次 —— 不准用數字指下一張。"""
    for rel in ("CLAUDE.md", "README.md", "docs/ROADMAP.md", "docs/ARCHITECTURE.md"):
        assert not re.search(r"第 ?\d+ 張卡", _text(rel)), rel
