# -*- coding: utf-8 -*-
# F85：均勻度的四種圖 — authored 2026-09-07.
"""`output_uniformity` —— **一張影像之內，一格框一個點**。

跟 `output_report` 的盒鬚圖差別只有一個，而那個差別就是它存在的理由：
那一張是「一個盒子＝判定樹的一片葉子，一個點＝一顆 defect」（整批），
這一張是「一個盒子＝一個區域，一個點＝一格框」（一張圖之內）。
兩者在畫面上長得一模一樣。

鎖在這裡的五件事：

1. 一顆寫五個檔（一頁 ＋ 一張圖一個 SVG）——**一份文件要的是一張圖一個檔**；
2. 沒有逐框數字的時候**不寫空白頁**，而且講出來（原因通常是 Gray level
   還停在 pooled）；
3. 預覽（`planned_files`）跟真的寫出來的**檔名對得上**；
4. 鎖定範圍真的傳得到圖上；
5. 「一張圖都沒勾」在畫布上就擋得住，不是跑完一批才講。
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))
sys.path.insert(0, str(REPO / "tools"))

import d4t.core.steps  # noqa: F401,E402 — 觸發卡片註冊
from d4t.core.export import uniformity_charts as uc               # noqa: E402
from d4t.core.ingest.dataset import load_dataset                  # noqa: E402
from d4t.core.pipeline import (                                   # noqa: E402
    get_step, run_batch, run_batch_steps,
)
from d4t.core.pipeline.recipe import (                            # noqa: E402
    Edge, Recipe, RecipeNode, ScoreSpec, hydrate_regions,
)

KIND = "rsem"


@pytest.fixture(scope="module")
def lot(tmp_path_factory):
    from make_sample_rsem import generate
    return generate(str(tmp_path_factory.mktemp("unif")), n=3, seed=11)


@pytest.fixture(scope="module")
def dataset(lot):
    return load_dataset(lot["klarf"])


def recipe_for(folder, glv=None, **over):
    """一張大圖 → 鋪一組 ROI → Gray level(each box) → Write uniformity。

    **這就是使用者的用法**（PEAR 的替代品），所以測試走的是同一條路。
    """
    params = {"folder": str(folder), "metric": "glv_mean", "limit": 0}
    params.update(over)
    gp = {"source": "single", "across_boxes": "each box",
          "metrics": "glv_mean,glv_median", "judge": "glv_mean"}
    gp.update(glv or {})
    r = Recipe(
        recipe_id="unif_demo",
        routes={KIND: ["load", "roi", "glv", "out"]},
        nodes={
            "load": RecipeNode("load", "load_single", {"out": "single"}),
            "roi": RecipeNode("roi", "roi_reference", {
                "method": "stripes in the image", "source": "single",
                "roi_out": "cells", "place": "crossing", "pick": "none",
                "output_prefix": "cells"}),
            "glv": RecipeNode("glv", "glv_stats", gp),
            "out": RecipeNode("out", "output_uniformity", params),
        },
        edges=[Edge("load", "roi", "single", "source"),
               Edge("roi", "glv", "cells", "roi"),
               Edge("load", "glv", "single", "source")],
        score=ScoreSpec(expr="glv_worst_score", threshold=3.0,
                        bins={"below": 0, "above": 1}))
    # ⚠ **手搭的 Recipe 要自己水合區域線。** `roi="cells"` 那一格是從線上
    # 算出來的、不寫進 JSON（鐵則 10），而 `from_json_dict` 才會做這件事 ——
    # 少了這一行，GLV 那張卡的 `roi` 是空的，於是它安靜地退回「量整張圖」，
    # 吐的是 pooled 的裸名而不是逐框的後綴。跑得完、有數字、而且是錯的。
    hydrate_regions(r.nodes, r.edges)
    return r


def run(dataset, folder, glv=None, **over):
    r = recipe_for(folder, glv=glv, **over)
    rows = run_batch(r, dataset, workers=1)
    bctx = run_batch_steps(r, dataset, rows)
    assert not bctx.errors, bctx.errors
    return bctx, rows


# --------------------------------------------------------------------------- #
# 1. 寫出什麼
# --------------------------------------------------------------------------- #
def test_every_defect_gets_a_page_and_one_file_per_figure(dataset, tmp_path):
    """**一份文件要的是一張圖一個檔** —— 從一頁裡把 SVG 剪出來是使用者
    做不到的事，所以兩種都寫。"""
    out = tmp_path / "unif"
    bctx, rows = run(dataset, out)
    # ⚠ 好幾顆的時候多一份 `index.html`（F86）—— 它不是任何一顆的頁面
    pages = [p for p in sorted(out.glob("*.html")) if p.name != "index.html"]
    assert len(pages) == len(rows) > 0
    for page in pages:
        stem = page.stem
        for kind in uc.CHARTS:
            assert (out / ("%s-%s.svg" % (stem, kind))).is_file(), kind
        text = page.read_text(encoding="utf-8")
        assert text.count("<svg") == len(uc.CHARTS)
    assert str(out) in bctx.outputs


def test_only_the_ticked_charts_are_drawn(dataset, tmp_path):
    out = tmp_path / "two"
    _bctx, rows = run(dataset, out, charts="histogram,map")
    assert sorted(p.name.split("-")[-1] for p in out.glob("*.svg")) == \
        sorted(["histogram.svg", "map.svg"] * len(rows))


def test_the_preview_names_match_what_is_really_written(dataset, tmp_path):
    """寫出前一定先預覽（M5 的硬規則），而預覽跟真跑要對得上 ——
    儀表列的檔名跟真的寫出來的不一樣，比沒有預覽糟。"""
    out = tmp_path / "plan"
    card = get_step("output_uniformity")
    planned = card.planned_files({"folder": str(out), "charts": "box,profile"})
    run(dataset, out, charts="box,profile")
    real = {p.name for p in out.iterdir()}
    for row in planned:
        pattern = row["name"].replace("<defect>", "")
        assert any(name.endswith(pattern) for name in real), row


# --------------------------------------------------------------------------- #
# 2. 沒有逐框數字的時候
# --------------------------------------------------------------------------- #
def test_pooled_writes_nothing_and_says_why(dataset, tmp_path):
    """走 pooled ⇒ 「這幾格之間」不存在。

    **不寫一張空白頁** —— 一張畫得出來但沒有意義的圖比沒有圖糟。而
    一個空資料夾跟「這張卡沒被跑到」在畫面上長得一模一樣，所以要講。
    """
    out = tmp_path / "pooled"
    bctx, _ = run(dataset, out, glv={"across_boxes": "pooled"})
    assert list(out.glob("*.html")) == []
    assert any("each box" in w for w in bctx.warnings), bctx.warnings


def test_nothing_ticked_is_caught_on_the_canvas_not_after_the_run(tmp_path):
    """跑一整批才講「你什麼都沒勾」是最貴的講法。"""
    card = get_step("output_uniformity")
    issues = card.configuration_issues({"folder": str(tmp_path), "charts": ""})
    assert issues and "Tick at least one" in issues[0]
    assert card.configuration_issues({"folder": str(tmp_path),
                                      "charts": "box"}) == []


def test_a_folder_that_is_a_file_is_caught_too(tmp_path):
    """跟另外兩張寫資料夾的卡走同一支 `path_issue`。"""
    f = tmp_path / "notafolder.txt"
    f.write_text("x", encoding="utf-8")
    issues = get_step("output_uniformity").configuration_issues(
        {"folder": str(f), "charts": "box"})
    assert issues and "not a folder" in issues[0]


# --------------------------------------------------------------------------- #
# 3. 設定真的傳得到圖上
# --------------------------------------------------------------------------- #
def test_locking_the_scale_reaches_every_chart(dataset, tmp_path):
    """鎖定是這一輪唯一非做不可的外觀設定，所以它要**真的鎖到圖上**。"""
    out = tmp_path / "lock"
    run(dataset, out, value_lo=0.0, value_hi=255.0)
    hist = next(out.glob("*-histogram.svg")).read_text(encoding="utf-8")
    heat = next(out.glob("*-map.svg")).read_text(encoding="utf-8")
    assert ">250<" in hist or ">200<" in hist      # 鎖到 0–255 才有的刻度
    assert "locked" in heat                        # 色階鎖住要在圖上說


def test_an_unset_lock_leaves_every_chart_scaling_itself(dataset, tmp_path):
    """兩格都是 0（預設）⇒ auto。0 不是哨兵值 —— 判準是「上界沒有高過下界」。"""
    out = tmp_path / "auto"
    run(dataset, out)
    assert "locked" not in next(out.glob("*-map.svg")).read_text(encoding="utf-8")


def test_the_value_name_replaces_the_statistic_id_on_the_axis(dataset,
                                                              tmp_path):
    """`glv_mean` 在報告裡不是一句話，`Gray level` 才是。"""
    out = tmp_path / "named"
    run(dataset, out, value_name="Gray level")
    prof = next(out.glob("*-profile.svg")).read_text(encoding="utf-8")
    assert "Gray level" in prof


def test_the_profile_axis_switches_what_it_plots_against(dataset, tmp_path):
    a, b = tmp_path / "ax", tmp_path / "ay"
    run(dataset, a, axis="x")
    run(dataset, b, axis="y")
    sx = next(a.glob("*-profile.svg")).read_text(encoding="utf-8")
    sy = next(b.glob("*-profile.svg")).read_text(encoding="utf-8")
    assert "centre X" in sx and "centre Y" in sy


def test_a_metric_nobody_measured_draws_nothing_rather_than_the_wrong_one(
        dataset, tmp_path):
    """打錯統計量名字 ⇒ **不要安靜換一個**（同 `metrics` 那一格的立場）。"""
    out = tmp_path / "bogus"
    bctx, _ = run(dataset, out, metric="glv_nope")
    assert list(out.glob("*.html")) == []
    assert any("each box" in w for w in bctx.warnings)


# --------------------------------------------------------------------------- #
# 4. 這張卡在 Output 段的身分
# --------------------------------------------------------------------------- #
def test_it_is_a_batch_card_that_writes_nothing_into_the_pipeline():
    card = get_step("output_uniformity")
    p = {"folder": "/tmp/x", "charts": "box"}
    assert card.resolve_reads(p) == []
    assert card.resolve_writes(p) == []
    assert card.resolve_features(p) == []


def test_its_help_points_at_the_other_card_for_the_other_question():
    """兩張卡在畫面上長得一模一樣，所以**help 那一句話就是它們的分界**。"""
    card = get_step("output_uniformity")
    assert "Write report" in card.help
    assert "each box" in card.help


# --------------------------------------------------------------------------- #
# F86：檔名、數字、索引頁、打錯的統計量
# --------------------------------------------------------------------------- #
def test_the_files_are_not_called_overlay(dataset, tmp_path):
    """**這幾張不是疊圖。**

    第一版借了 `overlay.overlay_filename()`，於是檔名長成
    `overlay_field-box.svg` —— 而我要的只有它「把 / : 換成底線」那一半。
    前綴是搭便車來的，意思是錯的。
    """
    out = tmp_path / "names"
    run(dataset, out)
    names = [p.name for p in out.iterdir()]
    assert names, "什麼都沒寫"
    assert not any(n.startswith("overlay_") for n in names), names


def test_a_defect_id_that_is_not_a_legal_filename_still_writes():
    """消毒那一半**要留著**：RSEM 的 id 是從檔名來的，一顆 id 裡有 `/` 或
    `:` 的 defect 會讓寫檔整個失敗，而症狀是「少了幾張圖」（鐵則 7 把例外
    吃掉了）。"""
    from d4t.core.export.overlay import safe_stem
    assert safe_stem("LOT/1:2") == "LOT_1_2"
    assert safe_stem("") == "unknown"


def test_the_page_carries_the_numbers_not_just_the_pictures(dataset, tmp_path):
    """那一頁本來就該是「一顆的答案」。

    在這之前它只有四張 SVG —— 看圖的人得另外開 CSV 才知道 CV% 是多少。
    """
    out = tmp_path / "numbers"
    run(dataset, out)
    page = next(out.glob("*.html")).read_text(encoding="utf-8")
    assert "<table class='unif'" in page, "頁面上沒有數字表"
    assert "CV" in page and "left" in page       # 散多開 ＋ 往哪邊斜
    assert "boxes" in page


def test_the_numbers_on_the_page_are_the_ones_in_the_csv(dataset, tmp_path):
    """**同一顆的 CV% 不准有兩個。**

    摘要表的數字是從那一顆的 features 拿的，不在畫圖那一側重算 —— 重算的
    那一份會漂，而 CSV 與報告頁上出現兩個 CV% 的那天，沒有人看得出哪一個
    是對的。
    """
    from d4t.core.export import uniformity_charts as uc
    out = tmp_path / "same"
    _bctx, rows = run(dataset, out)
    feats = rows[0]["features"]
    notes = []          # 直接問那一支，避免再跑一次 pipeline
    got = uc.summary_rows({"metric": "glv_mean",
                           "groups": [{"name": "cells", "values": [1.0, 2.0]}]},
                          feats)
    assert got[0]["cells"].get("cv_pct") == feats.get("glv_mean_cv_pct")
    assert notes == []


def test_one_defect_gets_no_index_page(dataset, tmp_path):
    """**一顆的時候不寫索引**：那一顆的頁面本來就是答案，多一個檔只是多一層
    要點進去的東西。"""
    out = tmp_path / "single"
    run(dataset, out, limit=1)
    assert not (out / "index.html").exists()
    assert len(list(out.glob("*.html"))) == 1


def test_several_defects_get_an_entry_page(dataset, tmp_path):
    """20 顆會寫出 20 個 HTML ＋ 80 個 SVG 躺在同一個資料夾裡 —— 沒有入口的話
    要一個一個點。"""
    out = tmp_path / "many"
    _bctx, rows = run(dataset, out)
    if len(rows) < 2:
        pytest.skip("這份合成資料只有一顆")
    index = out / "index.html"
    assert index.is_file()
    text = index.read_text(encoding="utf-8")
    for r in rows:
        assert str(r["defect_id"]) in text, "索引頁少了一顆"
    assert text.count("<a href=") == len(rows)
    assert "CV" in text, "索引頁上要有數字，不然挑不出該點哪一顆"


def test_a_statistic_nobody_measured_is_caught_on_the_canvas():
    """打成 `glv_mena` 的下場是四張圖全空、**沒有任何訊息**。

    那一格是自由文字，而 d4t 對「指名上游東西」的欄位向來有型別。它不是
    特徵名（是統計量 id），所以落在既有的 `stale-feature-ref` 之外 ——
    要有自己的一條。
    """
    from d4t.core.pipeline import validate
    r = recipe_for("/tmp/x")
    assert [i for i in validate(r, kind=KIND)] == []
    r.nodes["out"].params["metric"] = "glv_mena"
    bad = [i for i in validate(r, kind=KIND)
           if i.code == "unknown-chart-metric"]
    assert bad, "打錯的統計量沒有被講出來"
    assert "glv_mean" in bad[0].detail, "要說得出上游到底量了什麼"


def test_pooled_upstream_is_caught_on_the_canvas():
    """走 pooled 的話這張卡跑得完、資料夾出得來、裡面什麼都沒有。"""
    from d4t.core.pipeline import validate
    r = recipe_for("/tmp/x", glv={"across_boxes": "pooled"})
    got = [i for i in validate(r, kind=KIND)
           if i.code == "charts-need-each-box"]
    assert got, "pooled 沒有被講出來"
    assert "Odd box out" in got[0].detail, "要指名那顆鈕"
