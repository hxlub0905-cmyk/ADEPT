# d4t — 只重跑判定段（2026-09-09）。
"""使用者：「將 Results 內的 Run all & write 更改為 re-run 鍵，可以根據 ADC 的
設定快速 Re-run（因為 feature 應該都算了？）」。

`rerun_decision` 拿**已經算好的 features** 重走判定：每一行 let 重算（含
「跟整批比」的）、上一次判定失敗的顆救回來、影像一顆都不碰。
`measurement_signature` 說「這批 features 還是不是現在這份 recipe 會算出來的」
—— 不是的話 Studio 走整批重跑，不拿舊數字配新量測卡。
"""
from __future__ import annotations

import copy

import d4t.core.steps  # noqa: F401 — 觸發卡片註冊
from d4t.core.pipeline.batch import (
    measurement_signature, redecide, rerun_decision,
)
from d4t.core.pipeline.recipe import (
    DecideSpec, Let, Recipe, RecipeNode, ScoreSpec, TreeLeaf, TreeStep,
)


def _recipe(when="a > 5", lets=None):
    return Recipe(
        recipe_id="r", routes={"ebi_patch": ["load", "glv", "out"]},
        nodes={"load": RecipeNode("load", "load_patch", {}),
               "glv": RecipeNode("glv", "glv_stats",
                                 {"source": "test", "metrics": "glv_median"}),
               "out": RecipeNode("out", "output_report",
                                 {"folder": "/tmp/x"})},
        score=ScoreSpec(expr="", threshold=0.0, bins={"below": 0, "above": 1}),
        decide=DecideSpec(
            let=lets if lets is not None else [Let(name="a", expr="glv_median * 2")],
            tree=TreeStep(when=when, yes=TreeLeaf(bin=1, label="hot"),
                          no=TreeLeaf(bin=0, label="quiet"))))


def _rows():
    def row(i, v, ok=True):
        return {"defect_id": "d%d" % i, "ok": ok, "error": None,
                "features": {"glv_median": v}, "score": None, "bin": 0 if ok else None,
                "traces": [{"node_id": "load", "ok": True, "ms": 1.0},
                           {"node_id": "glv", "ok": True, "ms": 2.0}]}
    return [row(1, 1.0), row(2, 4.0), row(3, 10.0)]


def test_rerun_walks_the_new_tree_on_the_stored_numbers():
    rows = _rows()
    assert rerun_decision(_recipe("a > 5"), rows) == 3
    assert [r["bin"] for r in rows] == [0, 1, 1]        # a = 2, 8, 20
    assert rerun_decision(_recipe("a > 10"), rows) == 3
    assert [r["bin"] for r in rows] == [0, 0, 1]
    assert all(r["features"]["a"] == r["features"]["glv_median"] * 2 for r in rows)


def test_rerun_recomputes_a_scaled_let_from_its_new_formula():
    """`redecide` 把「跟整批比」的行拿掉（值已經是最終的）；Re-run 不行 ——
    使用者可能剛改了那一行的算式。錨（`_raw`）要拔掉重算。"""
    lets = [Let(name="z", expr="glv_median", scale="z")]
    rows = _rows()
    rerun_decision(_recipe("z > 0", lets), rows)
    first = [r["features"]["z_raw"] for r in rows]
    assert first == [1.0, 4.0, 10.0]
    lets2 = [Let(name="z", expr="glv_median * 10", scale="z")]
    rerun_decision(_recipe("z > 0", lets2), rows)
    assert [r["features"]["z_raw"] for r in rows] == [10.0, 40.0, 100.0], \
        "錨沒拔掉：z_raw 還是舊算式的值"
    # 中位數那顆的 z 是 0，其他兩顆一負一正
    zs = [r["features"]["z"] for r in rows]
    assert zs[1] == 0.0 and zs[0] < 0 < zs[2]


def test_rerun_revives_a_defect_whose_decision_failed_last_time():
    """量測都好、上一次判定炸了（樹指到不存在的名字）→ 修好樹按 Re-run，
    那顆要重新有 bin。`redecide` 預設不救（跟以前一字不差）。"""
    rows = _rows()
    # 樹上問不到的名字算「否」（F30），要讓判定真的炸得用 let 指到不存在的名字
    bad = [Let(name="a", expr="nosuch * 2")]
    assert rerun_decision(_recipe("a > 5", bad), rows) == 0
    assert all(r["ok"] is False and r["bin"] is None for r in rows)
    assert all(str(r["error"]).startswith("[score]") for r in rows)
    untouched = copy.deepcopy(rows)
    assert redecide(_recipe("a > 5"), untouched) == 0, "redecide 不救，那是 Re-run 的事"
    assert rerun_decision(_recipe("a > 5"), rows) == 3
    assert [r["bin"] for r in rows] == [0, 1, 1]
    assert all(r["ok"] and r["error"] is None for r in rows)


def test_a_defect_that_failed_in_a_card_stays_failed():
    rows = _rows()
    rows[0]["ok"] = False
    rows[0]["bin"] = None
    rows[0]["traces"][1]["ok"] = False
    assert rerun_decision(_recipe("a > 5"), rows) == 2
    assert rows[0]["ok"] is False and rows[0]["bin"] is None


def test_the_measurement_signature_ignores_the_decision_and_the_output_cards():
    base = measurement_signature(_recipe("a > 5"))
    assert measurement_signature(_recipe("a > 999")) == base, "改樹不算"
    other_let = _recipe("a > 5", [Let(name="b", expr="glv_median")])
    assert measurement_signature(other_let) == base, "改 let 不算"
    r = _recipe("a > 5")
    r.nodes["out"].params["folder"] = "/somewhere/else"
    assert measurement_signature(r) == base, "Output 卡的資料夾不算"
    r.recipe_id = "renamed"
    assert measurement_signature(r) == base
    r.nodes["glv"].params["metrics"] = "glv_median,glv_max"
    assert measurement_signature(r) != base, "量測卡的一格參數 → 每個數字都變"
    r2 = _recipe("a > 5")
    r2.nodes["glv"].enabled = False
    assert measurement_signature(r2) != base, "停用一張量測卡也算"
