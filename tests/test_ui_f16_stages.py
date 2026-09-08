# d4t tests — F16：畫布上的段落
"""段落的順序只有一個真相。

**2026-09-08（U9）：那兩份合併成一份了。** 順序、標題、副標現在都住在
`core/pipeline/step.py::GROUPS`，`GROUP_ORDER` 由它推導，而 UI 只讀不寫 ——
`LibraryPanel.GROUPS` 那個常數不存在了。

⚠ 所以這一份的第一條測試**換了問題**。以前它問「兩份一不一樣」，而合併之後
那句話是恆真的（兩邊是同一個物件），也就是 F40 那種**永遠不會失敗的斷言**
—— 比沒有斷言更糟，因為它會讓下一個人以為有人在守。現在它問的是那件事的
**因**：UI 上沒有第二份，而畫面上的區塊真的是從 `step.GROUPS` 長出來的。

⚠ **2026-08-27（Phase 3）刪了 ``the_absorbed_algo_cards_never_read_an_image_stream``。**
它掃的是「`feature_math` / `feature_fill`，以及任何掛在 ``GROUP_ALGO`` 上的卡，
都不准讀影像流」。那兩張卡刪掉之後 —— 而 ``GROUP_ALGO`` **本來就零張卡** ——
那個迴圈的本體**再也不會執行一次**，而測試照樣綠。

那正是 F40 那支恆綠零斷言測試的形狀（`docs/history/plans/F40-stack-agreement.md` §1），
只是這一次是我們自己親手做出來的。**一條永遠不會執行的斷言比沒有斷言更糟**：
它會讓下一個人以為那條規矩有人在守。
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from d4t.core.pipeline import step as step_mod   # noqa: E402 — Qt-free
from d4t.core.pipeline.step import (      # noqa: E402 — Qt-free
    GROUPS as STAGE_GROUPS, GROUP_ORDER, GROUP_OUTPUT, REGISTRY,
)
import d4t.core.steps  # noqa: F401,E402 — 觸發卡片註冊


def _import_qt(g):
    from PySide6.QtWidgets import QApplication
    from d4t.ui import widgets as widgets_mod
    g["QApplication"] = QApplication
    g["widgets_mod"] = widgets_mod


@pytest.fixture(scope="module")
def qapp():
    _import_qt(globals())
    app = QApplication.instance() or QApplication([])
    yield app


def test_the_library_keeps_no_copy_of_the_order(qapp):
    """**UI 上不准再有第二份**（U9 的驗收條件）。

    `LibraryPanel.GROUPS` 曾經是 `GROUP_ORDER` 的第二份，多帶標題與副標，
    靠這一份測試綁著不漂。而一條測試是補丁不是解法：它擋得住「兩份不一致」，
    擋不住「改的人根本不知道有第二份」—— 順序、標題、副標是同一件事的三半，
    分開存的那天就開始漂了。
    """
    panel = widgets_mod.LibraryPanel
    assert not any("GROUPS" == n for n in vars(panel)), (
        "LibraryPanel 又自己長出一份 GROUPS 了 —— 段落的順序、標題與副標"
        "住在 core/pipeline/step.py 的 GROUPS，UI 只讀不寫。")
    assert panel._GROUPS is STAGE_GROUPS, \
        "卡片庫畫的不是 step.GROUPS 那一份"


def test_the_order_is_derived_from_the_one_table(qapp):
    """`GROUP_ORDER` 是從 `GROUPS` 推出來的，不是另外打的一串字。"""
    assert tuple(GROUP_ORDER) == tuple(g for g, _t, _s in STAGE_GROUPS)


def test_the_sections_on_screen_come_from_that_table(qapp):
    """真的開一個卡片庫出來，區塊標題要逐字等於那張表。

    上面兩條問的是資料，這一條問的是**畫面** —— 中間那一段（`_make_header`
    怎麼用它）壞掉的話，前兩條照樣綠。
    """
    panel = widgets_mod.LibraryPanel()
    try:
        assert panel.section_titles() == [t for _g, t, _s in STAGE_GROUPS]
    finally:
        panel.deleteLater()


def test_every_stage_has_a_title_and_a_subtitle(qapp):
    """新加一段的人最容易漏掉副標，而 rail 上只剩一個看不懂的字。"""
    for gid, title, sub in STAGE_GROUPS:
        assert title.strip(), "段落 %r 沒有標題" % gid
        assert sub.strip(), "段落 %r 沒有副標（rail 上會只剩一個字）" % gid


def test_the_stages_are_in_the_order(qapp):
    """段落照使用者定的順序（而且是**七段**）。

    F16（2026-08-20）定的是八段；F24 §5 把 Algo 段解散進判定（算式住進
    working numbers、補值變成「missing ⇒」、跨顆換算變成「跟整批比」），
    而「動段落要使用者再點一次頭」那條規矩履行過了（2026-08-24：
    「那三件事接著做」）。
    """
    order = list(GROUP_ORDER)
    assert GROUP_OUTPUT in order
    assert order == ["input", "enhance", "region", "measure",
                     "compare", "adc", "output"], order


def test_the_algo_group_is_gone_for_good(qapp):
    """``GROUP_ALGO`` 這個常數 2026-08-28 刪掉了（F48，使用者定調）。

    **這一條是翻面來的，不是新加的。** 以前它寫的是
    ``assert GROUP_ALGO not in GROUP_ORDER`` —— 那是「收起來」的證據
    （常數還在，只是不在順序裡）。「刪掉」的證據剛好相反：那個名字要問不到。
    F41 §3 為了同一個理由翻過兩條測試，這是第三條。

    順便守住那個**很容易誤刪的鄰居**：`CATEGORY_ALGO` 是另一個軸（「這張卡
    吐數字」，每一張量測卡都是它），三段式心智模型裡的 ``"algo"`` 段
    （`welcome._SEG_LINES`、`theme.seg_color`）也還活著。兩個都不准跟著走。
    """
    assert not hasattr(step_mod, "GROUP_ALGO"), (
        "GROUP_ALGO 回來了 —— 它 2026-08-28 刪掉了（外掛卡宣告 group=\"algo\" "
        "的話卡片庫列不出來，改宣告 GROUP_MEASURE）")
    assert step_mod.CATEGORY_ALGO == "algo", (
        "CATEGORY_ALGO 是另一個軸，不該跟著 GROUP_ALGO 一起被刪")

    from d4t.ui import welcome as welcome_mod
    assert "algo" in [seg for seg, _line in welcome_mod._SEG_LINES], (
        "三段式心智模型的算法段不見了 —— 那跟卡片庫的 Algo 分區不是同一個東西")


def test_output_cards_are_the_end_of_the_line():
    """Output 段的卡是 end point：不吐影像流、也不吐特徵。

    使用者：「他就是個 end point」。這一條讓「Output 卡順手多吐一個數字」
    這種便利功能停在加卡的那一刻 —— 一旦它吐了東西，下游就接得上它，
    而「這一段是最後一段」這句話就不再成立。
    """
    for key, cls in sorted(REGISTRY.items()):
        if cls.resolve_group() != GROUP_OUTPUT:
            continue
        params = {p.name: p.default for p in cls.params}
        assert not cls.resolve_writes(params), \
            "Output 卡 %r 吐了影像流：%s" % (key, cls.resolve_writes(params))
        assert not cls.resolve_features(params), \
            "Output 卡 %r 吐了特徵：%s" % (key, cls.resolve_features(params))
