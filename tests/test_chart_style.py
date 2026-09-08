# -*- coding: utf-8 -*-
"""`d4t.core.pipeline.chart_style`（F87）—— 一格參數裝得下的一整組設定。

headless、零 Qt。這一份守四件事：

1. **round-trip 是 identity**（鐵則 9）—— 那一格會被 `to_json_dict →
   from_json_dict` 走一趟，那是 `run_batch` 送 recipe 進 worker 的路；
2. **只存跟預設不一樣的** —— 一份沒動過外觀的 recipe 那一格是空字串；
3. **壞值擋在打字的當下，而且是一句白話**（鐵則 4）；
4. **這一支不認識任何一張圖的名字** —— 知道的話 `pipeline/` 就開始依賴
   `export/`，而那個方向是反的。
"""
from __future__ import annotations

import pytest

from d4t.core.pipeline import chart_style as cs  # noqa: E402
from d4t.core.pipeline.chart_style import (
    DEFAULTS, PER_CHART_KEYS, ROWS, ChartStyleError, describe, format_style,
    parse_style, style_for,
)


# --------------------------------------------------------------------------- #
# 1. round-trip 與「只存差異」
# --------------------------------------------------------------------------- #
def test_nothing_changed_is_the_empty_string():
    """一份沒動過外觀的 recipe 那一格是空的 —— diff 乾淨。"""
    assert format_style({}) == ""
    assert format_style("") == ""
    assert parse_style("") == {}
    assert parse_style(None) == {}


def test_a_value_equal_to_the_default_is_not_stored():
    """存了的話，改預設值的那天舊檔案會被凍在半年前的樣子。"""
    assert format_style({"tick_size": DEFAULTS["tick_size"]}) == ""
    assert format_style({"points": DEFAULTS["points"]}) == ""


def test_the_round_trip_is_identity():
    """鐵則 9：`to_json_dict → from_json_dict` 一旦不是 identity，
    `workers=1` 與 `workers=2` 就會算出不同的東西。"""
    src = ('{"tick_size":12,"tick_bold":true,"box.title":"EPI",'
           '"lock":true,"lo":10,"hi":200,"point_size":3.25}')
    once = format_style(parse_style(src))
    assert format_style(parse_style(once)) == once


def test_integers_stay_integers():
    """`12.0` 與 `12` 在 JSON 上是兩個字串，而 round-trip 要穩定。"""
    assert '"tick_size":12' in format_style({"tick_size": 12.0})
    assert "12.0" not in format_style({"tick_size": 12.0})


def test_the_keys_come_out_sorted():
    """順序不穩的話，同一組設定會產生兩種字串 —— diff 會亂跳。"""
    a = format_style({"tick_bold": True, "tick_size": 12})
    b = format_style({"tick_size": 12, "tick_bold": True})
    assert a == b


# --------------------------------------------------------------------------- #
# 2. 壞值 —— 擋在打字的當下，而且講得出為什麼
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize("bad,word", [
    ('{"tick_size":99}', "outside"),
    ('{"tick_size":1}', "outside"),
    ('{"nope":1}', "not a chart setting"),
    ('{"tick_bold":1}', "true or false"),
    ('{"tick_color":"red"}', "#4a90d9"),
    ('{"map.tick_color":"#ffffff"}', "cannot be set per chart"),
    ("not json", "not valid JSON"),
    ('[1,2]', "JSON object"),
])
def test_a_bad_value_says_what_is_wrong(bad, word):
    with pytest.raises(ChartStyleError) as e:
        parse_style(bad)
    assert word in str(e.value), str(e.value)


def test_an_empty_colour_means_follow_the_region():
    """**顏色的預設不是一個顏色，是「自動」。**

    存一個具體的色碼當預設的話，主題換了、區域色換了，這一格會安靜地把它們
    釘死。
    """
    assert DEFAULTS["tick_color"] == ""
    assert format_style({"tick_color": ""}) == ""
    assert parse_style('{"point_color":"#4a90d9"}') == {"point_color": "#4a90d9"}


# --------------------------------------------------------------------------- #
# 3. 展開給畫圖那一側
# --------------------------------------------------------------------------- #
def test_a_per_chart_override_only_reaches_that_chart():
    d = parse_style('{"box.title":"EPI","tick_size":12}')
    assert style_for(d, "box")["title"] == "EPI"
    assert style_for(d, "map")["title"] == ""
    assert style_for(d, "map")["tick_size"] == 12      # 全域的照樣到


def test_the_lock_becomes_the_shape_the_charts_understand():
    """`build_chart_svg` 的 ``style`` 契約一個字都沒變 —— 只是現在由這裡組出來。"""
    off = style_for(parse_style('{"lo":10,"hi":200}'))
    assert off["vlock"] is None and off["hlock"] is None, \
        "沒開 lock 卻鎖住了"
    on = style_for(parse_style('{"lock":true,"lo":10,"hi":200}'))
    assert on["vlock"] == (10.0, 200.0) and on["hlock"] == on["vlock"]


def test_a_lock_with_no_range_is_still_auto():
    """開了開關但上下界一樣 —— 那不是一個範圍，退回 auto 而不是畫出一條線。"""
    assert style_for(parse_style('{"lock":true}'))["vlock"] is None


def test_every_key_is_readable_even_when_nobody_set_it():
    """取用口要查得到每一格 —— 漏掉預設值的那一次會是 KeyError 而不是
    「沒有覆寫」。"""
    st = style_for({}, "whatever")
    for key in list(DEFAULTS) + ["title", "xlabel", "ylabel"]:
        assert key in st, key


# --------------------------------------------------------------------------- #
# 4. 分層：這一支不准認識任何一張圖
# --------------------------------------------------------------------------- #
def test_it_does_not_know_the_names_of_the_charts():
    """知道的話 `pipeline/` 就開始依賴 `export/`，而那個方向是反的。

    所以任何識別字都當成一張圖的名字 —— 它只驗**形狀**。
    """
    d = parse_style('{"someday_a_new_chart.title":"x"}')
    assert style_for(d, "someday_a_new_chart")["title"] == "x"

    # 真正的不變量是**它不 import export**（第一版問的是「原始碼裡有沒有出現
    # 那幾個字」，而那條測試抓到的是我自己寫在檔頭解釋這件事的註解 —— 一支
    # 會誤報的測試比沒有測試更糟）。
    import ast as _ast
    import d4t.core.pipeline.chart_style as mod
    tree = _ast.parse(open(mod.__file__, encoding="utf-8").read())
    for node in _ast.walk(tree):
        if isinstance(node, _ast.ImportFrom):
            assert "export" not in str(node.module or ""), node.module
        elif isinstance(node, _ast.Import):
            for a in node.names:
                assert "export" not in a.name, a.name


def test_the_editor_rows_are_data_not_layout():
    """哪幾列、每列有哪幾欄住在 core —— 那是「這組設定怎麼分群」，
    跟畫面用什麼元件無關（同 `decide_tree.verdict_rows` 的立場）。"""
    assert ROWS and all(len(cols) >= 2 for _title, cols in ROWS)
    for _title, cols in ROWS:
        for key, _col in cols:
            assert key in DEFAULTS, key


def test_the_summary_line_says_something_useful():
    """卡片上那一格是唯讀摘要（設定在編輯器裡改）。"""
    assert describe("") == "default"
    assert "1 change" in describe(parse_style('{"tick_size":12}'))
    assert "scale locked" in describe(parse_style('{"lock":true,"hi":9,"lo":1}'))


def test_per_chart_keys_are_the_ones_that_differ_per_chart():
    """字級在四張圖上是同一個問題；X 軸名不是（四張圖的 X 是四件不同的事）。"""
    assert set(PER_CHART_KEYS) == {"title", "xlabel", "ylabel",
                                   "xticks", "yticks"}
    assert "tick_size" not in PER_CHART_KEYS


# --------------------------------------------------------------------------- #
# F89-3：規格線／參考線
# --------------------------------------------------------------------------- #
def test_a_reference_line_can_be_a_bare_number_or_a_named_one():
    assert cs.parse_refs("120") == [("", 120.0)]
    assert cs.parse_refs("USL=132") == [("USL", 132.0)]


def test_reference_lines_come_back_sorted_by_value():
    """兩個人打同一組線要得到**逐字相同**的字串（round-trip 是 identity）。"""
    got = cs.parse_refs("USL=132, 120, LSL=112.5")
    assert [v for _n, v in got] == [112.5, 120.0, 132.0]
    assert cs.format_refs(got) == "LSL=112.5, 120, USL=132"


def test_the_reference_line_round_trip_is_identity():
    text = cs.format_style({"ref_lines": "USL=132, LSL=112"})
    assert text == '{"ref_lines":"LSL=112, USL=132"}'
    assert cs.format_style(cs.parse_style(text)) == text


def test_something_that_is_not_a_number_says_so_in_plain_words():
    with pytest.raises(cs.ChartStyleError) as e:
        cs.parse_refs("abc")
    assert "USL=132" in str(e.value), "錯誤訊息要示範正確的寫法"


def test_a_name_cannot_hide_a_separator():
    with pytest.raises(cs.ChartStyleError):
        cs.parse_refs([("a,b", 1.0)])


def test_too_many_lines_is_refused_with_the_reason():
    """五條以上的橫線會把圖蓋掉，而那時候該問的是「這張圖是不是問錯了問題」。"""
    with pytest.raises(cs.ChartStyleError) as e:
        cs.parse_refs("1,2,3,4,5,6")
    assert str(cs.MAX_REFS) in str(e.value)
