# PR-2（2d/2e/2f）：Subtract / 輸出預覽 / Focus 三塊新面板 + 共用 header。
"""鎖的都是不變量：資料同源（面板畫的是引擎 note 的那一份）、輸出預覽
永不寫檔、未跑就有、focus 單顆即有數字、每個註冊面板自己講空狀態。
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pytest

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))

pytest.importorskip("PySide6")

from PySide6.QtCore import QRectF  # noqa: E402
from PySide6.QtGui import QPainter, QPixmap  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402

import d4t.core.steps  # noqa: F401,E402
from d4t.core.pipeline import get_step  # noqa: E402
from d4t.core.pipeline.context import Context  # noqa: E402
from d4t.ui import inspectors as insp_mod  # noqa: E402
from d4t.ui import theme as theme_mod  # noqa: E402


@pytest.fixture(scope="module")
def qapp():
    app = QApplication.instance() or QApplication([])
    theme_mod.apply_theme(app, "light")
    yield app


def _paint(insp, w=360, h=160):
    """畫一次不准炸（同 `test_the_panel_paints_in_both_themes` 的煙霧法）。"""
    pix = QPixmap(w, h)
    pix.fill()
    p = QPainter(pix)
    try:
        insp.paint_body(p, QRectF(4, 4, w - 8, h - 8))
    finally:
        p.end()


# --------------------------------------------------------------------------- #
# Subtract（2d）
# --------------------------------------------------------------------------- #
def _subtract_ctx():
    rng = np.random.default_rng(11)
    ctx = Context(images={"test": rng.normal(120, 6, (48, 48)).astype(np.float32),
                          "ref": rng.normal(100, 6, (48, 48)).astype(np.float32)})
    ctx.track_changes = True
    get_step("subtract")().run(ctx, {"a": "test", "b": "ref",
                                     "op": "subtract", "absolute": False,
                                     "out": "diff"})
    return ctx


def test_the_subtract_panel_draws_what_the_engine_noted(qapp):
    ctx = _subtract_ctx()
    insp = insp_mod.SubtractInspector()
    insp.set_context("sub", params={"a": "test", "b": "ref", "out": "diff"},
                     meta=dict(ctx.meta))
    assert insp.has_data() is True
    note = ctx.meta["subtract"]["diff"]
    # 資料同源：summary 上的數字就是 note 裡的那幾個（不重算）。
    assert "%+.2f" % note["median"] in insp.summary()
    assert "MAD %.2f" % note["mad"] in insp.summary()
    _paint(insp)


def test_the_subtract_panel_without_a_preview_says_why(qapp):
    insp = insp_mod.SubtractInspector()
    insp.set_context("sub", params={"out": "diff"}, meta={})
    assert insp.has_data() is False
    assert "stripes" in insp.empty_reason(), "要講出行列平均是幹嘛的"


# --------------------------------------------------------------------------- #
# 輸出預覽（2e）
# --------------------------------------------------------------------------- #
def test_the_report_preview_lists_files_and_follows_the_ticks(qapp):
    insp = insp_mod.ReportPreviewInspector()
    insp.set_context("out", params={"folder": "/tmp/x",
                                    "contents": "table,excel"})
    names = [f["name"] for f in insp.plan()]
    assert names == ["defects.csv", "report.xlsx"], "照勾選，照寫入順序"
    # 改勾選 → 清單跟著變（同一份 params 流，選到卡即時）。
    insp.set_context("out", params={"folder": "/tmp/x", "contents": "report"})
    assert [f["name"] for f in insp.plan()] == ["report.html"]


def test_a_recipe_without_the_contents_key_previews_the_defaults(qapp):
    """「鍵不在」＝還沒設過＝預設那幾樣（不是一個都沒勾）——
    跟 `configuration_issues` / `run_batch` 同一句話。"""
    insp = insp_mod.ReportPreviewInspector()
    insp.set_context("out", params={"folder": "/tmp/x"})
    names = [f["name"] for f in insp.plan()]
    assert "report.html" in names and "defects.csv" in names
    assert "recipe.json" in names
    assert any(n.startswith("images/") for n in names), \
        "有報表時圖進 images/（跟 run_batch 同一條 nested 規則）"


def test_the_preview_never_touches_the_disk(qapp, tmp_path):
    target = tmp_path / "out"
    insp = insp_mod.ReportPreviewInspector()
    insp.set_context("out", params={"folder": str(target)})
    assert insp.has_data() is True, "**未跑就有** —— 這正是它存在的理由"
    insp.plan()
    insp.summary()
    _paint(insp)
    assert not target.exists(), "預覽寫了檔 —— 那它就不是預覽"


def _unif_meta(n=24, metric="glv_mean"):
    """引擎寫的那一份（`glv_stats._note_distribution` 的 `spread`）。"""
    vals = [112.0 + i * 2.4 for i in range(n)]
    vals[min(9, n - 1)] += 14.0
    return {"glv_hist": [{
        "region": "cells", "prefix": "cells", "boxes": n, "n": 1600,
        "bins": [0] * 64,
        "spread": {
            "stats": {metric: vals},
            "cx": [float(40 + 70 * (i % 6) + 20) for i in range(n)],
            "cy": [float(40 + 70 * (i // 6) + 20) for i in range(n)],
            "rects": [[40 + 70 * (i % 6), 40 + 70 * (i // 6), 40, 40]
                      for i in range(n)],
            "boxes": list(range(n))}}]}


def test_the_uniformity_preview_lists_the_files_and_draws_the_charts(qapp):
    """**畫面上看到的就是會寫出去的那一張** —— 同一支 `chart_series`、
    同一支 `build_chart_svg`、同一組 style。

    這一條守的是計畫書風險表的第一行（「兩份繪圖程式碼漂掉」）：F85 動手時
    發現 QtSvg 就裝在 PySide6 裡，所以那兩份收成了一份，而這裡問的是
    **它真的還是一份**。
    """
    insp = insp_mod.UniformityPreviewInspector()
    insp.set_context("out", params={"folder": "/tmp/x", "metric": "glv_mean",
                                    "charts": "box,histogram,profile,map"},
                     meta=_unif_meta())
    names = [f["name"] for f in insp.plan()]
    assert any(n.endswith(".html") for n in names)
    assert sum(1 for n in names if n.endswith(".svg")) == 4
    assert insp.charts() == ["box", "histogram", "profile", "map"]
    assert len(insp.series()["groups"]) == 1
    assert "24 box(es)" in insp.summary()
    _paint(insp, 680, 520)          # 畫一次不准炸


def test_the_uniformity_preview_says_why_there_is_nothing_to_draw(qapp):
    """沒有逐框數字時 —— **原因通常是上游那張卡，不是這一張**。

    一個空的圖區讀起來是「畫壞了」，而真相是「Gray level 還停在 pooled」。
    """
    insp = insp_mod.UniformityPreviewInspector()
    insp.set_context("out", params={"folder": "/tmp/x", "charts": "box"},
                     meta={"glv_hist": [{"region": "cells", "spread": None}]})
    assert insp.series()["groups"] == []
    _paint(insp, 400, 220)


def test_the_uniformity_preview_survives_a_panel_too_small_for_a_chart(qapp):
    """面板縮到畫不下 —— 不畫，但**不准炸、也不准畫壞**（鐵則 7 的 UI 版）。"""
    insp = insp_mod.UniformityPreviewInspector()
    insp.set_context("out", params={"folder": "/tmp/x", "charts": "box,map"},
                     meta=_unif_meta())
    for w, h in ((360, 160), (120, 80), (40, 30)):
        _paint(insp, w, h)


def test_a_chart_is_never_clipped_to_fit(qapp):
    """**尺寸夾住，內容不夾。**

    每一支 `_svg_*` 都把圖區夾在 `max(80, …)`，所以高度不夠時內容會比
    viewBox 高，而 SVG 會**把超出的切掉** —— 實測 126 px 高的格子把斜率
    那一行（整張圖唯一的數字）切掉一半，而圖看起來完全正常。
    """
    from d4t.core.export import uniformity_charts as uc
    insp = insp_mod.UniformityPreviewInspector()
    insp.set_context("out", params={"folder": "/tmp/x", "metric": "glv_mean",
                                    "charts": "profile"}, meta=_unif_meta())
    svg = uc.build_chart_svg(insp.series(), "profile", {}, width=40, height=30)
    assert "viewBox='0 0 %d %d'" % (uc.MIN_WIDTH, uc.MIN_HEIGHT) in svg
    assert "/ 100 px" in svg, "斜率那一行是整張圖唯一的數字，不准被夾掉"


def test_the_char_preview_is_fixed_four_plus_columns(qapp):
    insp = insp_mod.CharPreviewInspector()
    insp.set_context("out", params={"folder": "/tmp/x",
                                    "columns": "pair_found,match_dist_nm"})
    names = [f["name"] for f in insp.plan()]
    assert "report.html" in names and "defects.csv" in names
    assert "recipe.json" in names
    assert any("images/" in n for n in names)
    assert any("2 ticked" in str(v) for _, v in insp._lines()), \
        "欄數要講出來（點對點報表的欄是使用者勾的）"
    _paint(insp)


# --------------------------------------------------------------------------- #
# Focus（2e）
# --------------------------------------------------------------------------- #
def test_focus_shows_numbers_for_a_single_defect_before_any_batch(qapp):
    ctx = Context(images={"test": np.random.default_rng(2)
                          .normal(128, 30, (64, 64)).astype(np.uint8)})
    get_step("focus_quality")().run(ctx, {"source": "test"})
    insp = insp_mod.FocusInspector()
    insp.set_context("f", params={"source": "test"}, batch=[],
                     meta=dict(ctx.meta))
    assert insp.has_data() is True, "單顆就有 —— 不必等跑完一批"
    assert "lapvar" in insp.summary()
    got = "%.4g" % ctx.features["focus_lapvar"]
    assert got in insp.summary(), "面板上的數字就是引擎算的那一份"
    _paint(insp)


def test_focus_mentions_the_8bit_caveat_only_as_display(qapp):
    assert "8-bit" in insp_mod.FocusInspector.HINT


# --------------------------------------------------------------------------- #
# 共用 header + 空狀態（2f）
# --------------------------------------------------------------------------- #
def test_the_shared_header_names_the_stream_and_n(qapp):
    left, right = insp_mod.note_header(
        {"stream": "diff", "region": "epi", "n": 400, "n_raw": 500}, "epi")
    assert left.startswith("diff"), "來源流永遠在最前面"
    assert "epi" in left
    assert right == "n=400 of 500 px", "旋鈕丟過像素要講"
    left2, right2 = insp_mod.note_header({"stream": "test", "n": 9}, "")
    assert left2 == "test" and right2 == "n=9 px"


def test_every_registered_panel_says_why_in_its_own_words(qapp):
    """`Inspector.empty_reason` 的預設是退路不是家 —— 註冊過的面板都要
    自己講（泛用的一句話答不出「所以我現在該做什麼」）。"""
    classes = set(insp_mod.INSPECTORS.values())
    for table in insp_mod.BY_METHOD.values():
        classes |= {c for c in table.values() if c is not None}
    lazy = [c.__name__ for c in classes
            if c.empty_reason is insp_mod.Inspector.empty_reason]
    assert not lazy, "還在用預設空狀態句的面板：%s" % sorted(lazy)
