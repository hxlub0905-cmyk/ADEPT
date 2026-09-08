# 規模的天花板 — authored 2026-09-08.
"""**這個 repo 的每一道關都在問「數字對不對」，沒有一道在問「東西多大」。**

3,442 支測試、三份黃金值、七條卡片不變量、逐位元組的決定論 —— 全部長在
**正確性**那一條軸上。而 2026-09-08 量出來的：

* ``d4t/ui/studio.py`` 在 2026-09-02 是 5,244 行（`CLAUDE.md` 記的）、09-08 是
  6,942 行，而**中間沒有任何一輪是在動它**；
* 同一段時間 ``StudioWindow`` 從 261 個方法 / 386 個 ``self.*`` 名字長到
  268 / 393。

沒有人決定要加那些行，它們是**漂進來的**。這一份就是那把缺的尺。

它買到的不是「不准變大」
------------------------
一道天花板擋不住任何事 —— 它做的是把 drift 變成 **diff 裡的一行**：那一輪的
作者必須在同一個 commit 裡把上限從 6,942 改成 7,180，而那一行改動就是 code
review 的全部內容。「這一輪把判定那塊的三支方法搬進來」是合法的理由，
「順手」不是。

五條設計規則（違反的話它會變成一張只會變長的紙）
------------------------------------------------
1. **設在現在的值，不留 buffer。** 留 500 行餘裕 ＝ 那道關在餘裕用完之前是
   關著的。
2. **每一格附一句「為什麼是這個數字」**（下面每一格都有）。沒有那句話，
   下一個人的反射動作就是 +500。
3. **配一支反向測試** —— 實際值掉下來夠多而上限沒跟著降，也要紅。這是
   `CLAUDE.md` 已經寫下來的規矩：*任何「例外清單」都要有那支反向測試*
   （`tests/test_shipped_recipes.py` 的 ``ALLOWED_ERRORS`` 是先例）。
4. **一張表、一個家。** 數字只住在這裡，**不要在 `CLAUDE.md` 抄第二份** ——
   那正是 2026-08 那次 `tools/doctor.py` 對每台機器給出錯診斷的病根。
5. **調高要在同一個 commit 裡說理由。**

它守不到的三件事（明講，免得有人以為它是保證）
----------------------------------------------
* **它分不出好的成長與壞的成長。** 加一張卡讓 ``inspectors.py`` 多 40 行是
  健康的，``studio.py`` 多 40 行通常不是 —— 這裡只會說「變大了」，判斷仍然
  是人的。
* **它不會讓設計變好。** 只買到「變大是一個決定」；真正的拆分還是要做。
* **反射性上調 ＝ 劇場。** 這是唯一會讓它失效的方式，而擋它的只有規則 2 和 5。

⚠ 這一份**不 import Qt**（它讀原始碼、用 ``ast`` 解析），所以它跑在核心那一批
裡，幾百毫秒就有答案。
"""
from __future__ import annotations

import ast
import re
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))

import d4t.core.steps                                    # noqa: E402,F401
from d4t.core.pipeline.step import REGISTRY              # noqa: E402

#: 掃哪幾個目錄。
#:
#: **`bundle/` 不在裡面**：`bundle/d4t_bundle.py` 是 `tools/release.py` 產出來
#: 的（3.7 MB、32,000 行），它的大小是「repo 有多大」的鏡像，不是一個人寫出來
#: 的檔案。對產出物設上限只會得到一道每次 commit 都要調的關。
#:
#: **`tests/` 也不在裡面**：測試檔變長通常是好事（多守一件事），而這一份要抓
#: 的是「沒有人決定卻變大」，那件事發生在出貨的程式碼上。
SCOPE = ("d4t", "tools", "fab_probe")

#: **凍住的那幾支**：上限就是 2026-09-08 的實際行數，一行都不留。
#:
#: 為什麼是這五支而不是「全部」：這五支是 2026-09-08 那份體檢點名的
#: —— 前四支是接線層與遷移層（成長跟功能不成比例），`canvas.py` 則單純是
#: 超過下面那個一般上限而且不該再漂。其他 138 支走 :data:`GENERAL_CEILING`。
FILE_CEILINGS = {
    # 自繪圖示、按鈕、控制項全部在一支。真正的解法是把那幾群圖示切出去
    # （`CLAUDE.md` §4 已經寫著「切 widgets.py 那幾群自繪圖示最好拆、風險最低」），
    # 而那件事的前置是黃金值三份全綠 —— 已經成立了。
    "d4t/ui/widgets.py": 7139,
    # 接線層（建 widget、接訊號、轉呼叫）。`CLAUDE.md` §4：新的面板一律開新
    # 模組，不要塞進這裡。這一格就是那句話的執行機構。
    "d4t/ui/studio.py": 6942,
    # 19 道 `_migrate_*` 住在這裡（見下面 `recipe_migrations`）。它會用跟
    # `studio.py` 完全一樣的機制長成第二個 `studio.py`。
    "d4t/core/pipeline/recipe.py": 3732,
    # 逐卡儀表板。這一支變長**通常是健康的**（加一張卡就多一個面板），所以
    # 這一格比其他四格更常需要調高 —— 那沒關係，重點是調高時有人看見。
    "d4t/ui/inspectors.py": 3622,
    # 節點畫布。沒有被點名，只是它超過一般上限，凍住免得它安靜地漂。
    "d4t/ui/canvas.py": 2705,
}

#: 沒被列名的檔案共用的上限。
#:
#: 2,200 是量出來的：扣掉上面那五支之後最長的是 `steps/glv_stats.py` 2,101 行，
#: 次高 `steps/output.py` 2,016、`ingest/klarf_core.py` 1,982。所以這個數字給
#: 現役的大檔約 100–200 行的呼吸空間，而**一支新檔案一寫就超過 2,200 行**這件
#: 事本來就該先講一句話。
GENERAL_CEILING = 2200


def _lines(rel: str) -> int:
    return len((REPO / rel).read_text(encoding="utf-8").splitlines())


def _all_sources():
    for base in SCOPE:
        for path in sorted((REPO / base).rglob("*.py")):
            yield path.relative_to(REPO).as_posix()


# --------------------------------------------------------------------------- #
# 「按卡片名字分支」的地方有幾個
# --------------------------------------------------------------------------- #
#: **這兩張表是設計好的擴充點，不算耦合。**
#:
#: `inspectors.INSPECTORS`（一張卡一個面板）與 `inspectors.BY_METHOD`
#: （同一張卡的不同 method 不同面板）就是「加一張卡要在 UI 註冊一個面板」那條
#: 明講的路 —— `inspector_for()` 讀的正是這兩張，沒註冊的卡落回通用的特徵表。
#: 把它們算進去的話，這個指標量到的會是「卡片有幾張」，不是「耦合有多深」。
SANCTIONED_TABLES = {"INSPECTORS", "BY_METHOD"}


def _is_shouty(name: str) -> bool:
    """`STARTER_STEP` / `_PAIR_CARDS` 這種模組級常數名。"""
    return name.lstrip("_").isupper()


def card_key_couplings():
    """``d4t/ui`` 底下**按卡片名字分支**的每一個地方。

    只認三種語法位置，所以不會把同名的字串誤算進來（實測驗過：
    ``widgets.py`` 的 ``setProperty("tone", …)`` 是 Qt 屬性、
    ``inspectors.py`` 的 ``{"subtract": "−"}`` 是運算子符號，兩者都不算）：

    1. **比較**：``node.step == "glv_stats"``、``not in ("load_patch", …)``；
    2. **模組級常數**：``STARTER_STEP = "load_patch"``、``HIDDEN_STEPS = ("align",)``
       （:data:`SANCTIONED_TABLES` 那兩張除外）；
    3. ``get_step("glv_stats")``。

    回 ``(檔名, 行號, 形式, 卡片 key)`` 的集合。
    """
    keys = set(REGISTRY)
    found = set()
    for path in sorted((REPO / "d4t" / "ui").rglob("*.py")):
        rel = path.relative_to(REPO).as_posix()
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.Compare):
                sides = [node.left] + list(node.comparators)
                for side in sides:
                    lits = [side] if isinstance(side, ast.Constant) else \
                        list(getattr(side, "elts", []))
                    for lit in lits:
                        if isinstance(lit, ast.Constant) and lit.value in keys:
                            found.add((rel, lit.lineno, "compare", lit.value))
            elif isinstance(node, (ast.Assign, ast.AnnAssign)):
                targets = node.targets if isinstance(node, ast.Assign) \
                    else [node.target]
                names = [t.id for t in targets if isinstance(t, ast.Name)]
                if not names or not any(_is_shouty(n) for n in names):
                    continue
                if any(n.lstrip("_") in SANCTIONED_TABLES for n in names):
                    continue
                for sub in (ast.walk(node.value) if node.value else []):
                    if isinstance(sub, ast.Constant) and sub.value in keys:
                        found.add((rel, sub.lineno, "const:" + names[0],
                                   sub.value))
            elif isinstance(node, ast.Call):
                fn = node.func
                name = fn.attr if isinstance(fn, ast.Attribute) \
                    else getattr(fn, "id", "")
                if name == "get_step":
                    for arg in node.args:
                        if isinstance(arg, ast.Constant) and arg.value in keys:
                            found.add((rel, arg.lineno, "get_step", arg.value))
    return found


def _class_shape(rel: str, cls_name: str):
    """一個類別的 ``(方法數, self.* 名字數)``。

    行數量的是「打了多少字」，這兩個數字量的是**耦合** —— 刪掉一段註解會讓
    行數變好看，不會讓這兩個變好看。
    """
    src = (REPO / rel).read_text(encoding="utf-8")
    for node in ast.walk(ast.parse(src)):
        if isinstance(node, ast.ClassDef) and node.name == cls_name:
            methods = [n for n in node.body
                       if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))]
            seg = ast.get_source_segment(src, node) or ""
            attrs = set(re.findall(r"self\.([A-Za-z_][A-Za-z0-9_]*)", seg))
            return len(methods), len(attrs)
    raise AssertionError("%s 裡找不到 class %s" % (rel, cls_name))


def _migration_count() -> int:
    src = (REPO / "d4t/core/pipeline/recipe.py").read_text(encoding="utf-8")
    return len([n for n in ast.walk(ast.parse(src))
                if isinstance(n, ast.FunctionDef)
                and n.name.startswith("_migrate")])


#: 不是行數的那幾把尺 —— ``名字: (上限, 為什麼是這個數字, 量它的函式)``。
COUNT_CEILINGS = {
    # 這一格守的是**整個專案的賣點**：「加一張卡，UI 與引擎零修改」。
    # 唯一會安靜殺掉那句話的，就是這個數字慢慢變大。
    # 2026-09-08 的 23 個：viewmodel 8、studio 10、inspectors 3、scope 1、
    # canvas 1。要加第 24 個之前先問：這件事能不能改成問卡片自己
    # （`Step` 上多一個宣告），而不是在 UI 裡問「你是不是那張卡」。
    "ui_card_key_coupling": (
        23,
        "d4t/ui 裡按卡片名字分支的地方（不含 INSPECTORS/BY_METHOD 兩張註冊表）",
        lambda: len(card_key_couplings()),
    ),
    # god object 的兩個投影。261 → 268（六天）。
    "studio_window_methods": (
        268,
        "StudioWindow 的方法數（2026-09-02 是 261）",
        lambda: _class_shape("d4t/ui/studio.py", "StudioWindow")[0],
    ),
    "studio_window_attributes": (
        393,
        "StudioWindow 的 self.* 名字數（2026-09-02 是 386）",
        lambda: _class_shape("d4t/ui/studio.py", "StudioWindow")[1],
    ),
    # 19 道遷移撐 3 個 RECIPE_VERSION，而且**只增不減** —— 沒有任何一份文件說
    # 過「舊到哪一版可以不再自動轉」。第 20 道要寫的時候，這一格會先問那句話。
    "recipe_migrations": (
        19,
        "recipe.py 裡 _migrate_* 的道數（RECIPE_VERSION 現在是 3）",
        _migration_count,
    ),
}


def _slack(ceiling: int) -> int:
    """反向測試的門檻：掉到 ``上限 - slack`` 以下就要求把上限降下來。

    2%（至少 3）—— 大到不會被一次小刪改觸發，小到一次真正的拆分一定會踩到。
    """
    return max(3, ceiling // 50)


# --------------------------------------------------------------------------- #
# 正向：不准超過
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize("rel", sorted(FILE_CEILINGS))
def test_a_frozen_file_did_not_grow(rel):
    """凍住的那幾支不准變長。

    要調高的話：改 :data:`FILE_CEILINGS` 那一格，**並在同一個 commit 裡說明
    這一輪為什麼往它加東西**。那句話就是這道關的全部價值。
    """
    ceiling = FILE_CEILINGS[rel]
    actual = _lines(rel)
    assert actual <= ceiling, (
        "%s 現在 %d 行，超過上限 %d 行（+%d）。\n"
        "  這一輪真的該往這一支加東西嗎？`CLAUDE.md` §4：新的面板一律開新模組。\n"
        "  真的該加 → 把 FILE_CEILINGS 裡那一格改成 %d，並在 commit 訊息裡寫\n"
        "  一句為什麼。"
        % (rel, actual, ceiling, actual - ceiling, actual))


def test_an_unlisted_file_stays_under_the_general_ceiling():
    """沒被列名的檔案共用 :data:`GENERAL_CEILING`。

    一支新檔案一寫就超過 2,200 行的話，那件事本身該先講一句話 —— 而不是等它
    變成第六支要凍住的檔案。
    """
    too_big = [(rel, _lines(rel)) for rel in _all_sources()
               if rel not in FILE_CEILINGS and _lines(rel) > GENERAL_CEILING]
    assert not too_big, (
        "這幾支超過一般上限 %d 行：%s\n"
        "  要嘛把它拆小，要嘛把它加進 FILE_CEILINGS 並寫一句為什麼它該這麼大。"
        % (GENERAL_CEILING, too_big))


@pytest.mark.parametrize("name", sorted(COUNT_CEILINGS))
def test_a_counted_thing_did_not_grow(name):
    """不是行數的那幾把尺（耦合、god object、遷移道數）。"""
    ceiling, why, measure = COUNT_CEILINGS[name]
    actual = measure()
    assert actual <= ceiling, (
        "%s 現在是 %d，超過上限 %d（+%d）。\n"
        "  這一格量的是：%s\n"
        "  真的該漲 → 改 COUNT_CEILINGS 那一格並在 commit 訊息裡寫一句為什麼。"
        % (name, actual, ceiling, actual - ceiling, why))


# --------------------------------------------------------------------------- #
# 反向：縮小了，上限要跟著降
# --------------------------------------------------------------------------- #
# `CLAUDE.md`：**任何「例外清單」都要有那支反向的測試**，不然它就是一張只會
# 變長的紙。`tests/test_shipped_recipes.py` 的 ALLOWED_ERRORS 是先例 ——
# 例外修好了卻沒從表上拿掉的話，那份 recipe 從此少一條防線而測試照樣綠。
#
# 這裡是同一件事：`studio.py` 真的拆掉 2,000 行之後，上限如果還留在 6,942，
# 它就可以在沒有人注意的情況下**再長回來**，而那正是這一份要擋的事。
@pytest.mark.parametrize("rel", sorted(FILE_CEILINGS))
def test_a_shrunk_file_lowers_its_ceiling(rel):
    ceiling = FILE_CEILINGS[rel]
    actual = _lines(rel)
    assert actual > ceiling - _slack(ceiling), (
        "%s 只剩 %d 行，而上限還留在 %d —— 中間那 %d 行是白送的成長空間。\n"
        "  把 FILE_CEILINGS 裡那一格改成 %d，把拆分的成果鎖住。"
        % (rel, actual, ceiling, ceiling - actual, actual))


@pytest.mark.parametrize("name", sorted(COUNT_CEILINGS))
def test_a_shrunk_count_lowers_its_ceiling(name):
    ceiling, why, measure = COUNT_CEILINGS[name]
    actual = measure()
    assert actual > ceiling - _slack(ceiling), (
        "%s 只剩 %d，而上限還留在 %d。\n"
        "  這一格量的是：%s\n"
        "  把 COUNT_CEILINGS 那一格改成 %d，把成果鎖住。"
        % (name, actual, ceiling, why, actual))


# --------------------------------------------------------------------------- #
# 這把尺自己有沒有在量東西
# --------------------------------------------------------------------------- #
def test_every_frozen_file_exists():
    """表上列的檔案要真的在磁碟上 —— 改名或刪檔之後這一格會變成死的。"""
    missing = [rel for rel in FILE_CEILINGS if not (REPO / rel).exists()]
    assert not missing, "FILE_CEILINGS 上這幾支已經不存在了：%s" % missing


def test_the_general_ceiling_is_not_vacuous():
    """一般上限要真的貼著現役的大檔，不然它是一道永遠不會響的關。"""
    rest = [_lines(rel) for rel in _all_sources() if rel not in FILE_CEILINGS]
    assert rest, "掃不到任何檔案 —— SCOPE 設錯了？"
    assert max(rest) > GENERAL_CEILING * 0.85, (
        "沒被列名的檔案最長才 %d 行，而上限是 %d —— 差太多，這道關幾年都不會響。"
        % (max(rest), GENERAL_CEILING))


def test_the_coupling_metric_does_not_count_look_alikes():
    """指標本身要誠實：同名但不是卡片的字串不能算進來。

    實測過的兩個假陽性，兩個都必須**不**在結果裡：

    * ``widgets.py`` 的 ``setProperty("tone", tone)`` —— Qt 屬性，跟 `tone`
      那張卡無關；
    * ``inspectors.py`` 的 ``{"subtract": "−", "ratio": "÷"}`` —— 運算子符號表。

    這一條是這把尺的自我檢查：指標髒掉的話，凍住的那個數字就沒有意義。
    """
    hits = card_key_couplings()
    files = {rel for rel, _ln, _how, _key in hits}
    assert "d4t/ui/widgets.py" not in files, (
        "widgets.py 被算進去了 —— 它只有 Qt 的 setProperty(\"tone\", …)，"
        "指標把同名字串誤算成卡片耦合了：%s"
        % sorted(h for h in hits if h[0] == "d4t/ui/widgets.py"))
    ops = [h for h in hits if h[0] == "d4t/ui/inspectors.py" and h[2] == "compare"]
    assert not ops, "inspectors.py 的運算子符號表被算成比較了：%s" % ops


def test_the_sanctioned_tables_are_really_the_registration_path():
    """:data:`SANCTIONED_TABLES` 排除掉的那兩張，要真的是 UI 的註冊表。

    它們哪天改名或不再是擴充點的話，這裡會紅 —— 否則那個排除會安靜地
    變成「排除一張不存在的表」，而真正的註冊表開始被算進耦合裡。
    """
    src = (REPO / "d4t/ui/inspectors.py").read_text(encoding="utf-8")
    for name in SANCTIONED_TABLES:
        assert re.search(r"^%s\s*[:=]" % name, src, re.M), (
            "d4t/ui/inspectors.py 裡沒有叫 %s 的表了 —— "
            "SANCTIONED_TABLES 要跟著改" % name)
    assert "INSPECTORS.get(key)" in src, \
        "inspector_for() 不再讀 INSPECTORS 了 —— 註冊路徑換了，這張表要重看"
