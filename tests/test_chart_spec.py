# -*- coding: utf-8 -*-
"""`chart_spec`：**一張圖 = 哪一欄放到哪一個角色上，加一種記號**（F88 ②）。"""
import pytest

from d4t.core.pipeline import chart_spec as cs


# --------------------------------------------------------------------------- #
# 1. round-trip 是 identity（鐵則 9）
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize("text", [
    "",
    '{"mark":"point","x":"glv_mean","y":"glv_std"}',
    '{"color":"region","mark":"point","x":"x","y":"glv_median"}',
    '{"color":"row","mark":"point","size":"w","x":"col","y":"glv_mean"}',
    '{"color":"row","mark":"line","x":"x","y":"glv_mean"}',
    '{"mark":"bar","x":"region","y":"glv_mean"}',
])
def test_round_trip_is_identity(text):
    """``to_json_dict → from_json_dict`` 是 `run_batch` 送 recipe 進 worker
    的路 —— 它一旦不是 identity，`workers=1` 與 `workers=2` 會算出不同的東西。
    """
    once = cs.format_spec(cs.parse_spec(text))
    assert once == text
    assert cs.format_spec(cs.parse_spec(once)) == once


def test_the_keys_are_sorted_so_two_ways_of_saying_it_look_the_same():
    """手打的與編輯器產出的要**逐字相同**，不然 recipe 的 diff 全是噪音。"""
    a = cs.format_spec({"y": "b", "x": "a", "mark": "point"})
    b = cs.format_spec('{"mark":"point","y":"b","x":"a"}')
    assert a == b == '{"mark":"point","x":"a","y":"b"}'


def test_nothing_picked_writes_nothing():
    """一份沒用到這張圖的 recipe，那一格是**空的** —— diff 才乾淨。"""
    assert cs.format_spec("") == ""
    assert cs.format_spec({"mark": "point"}) == ""


# --------------------------------------------------------------------------- #
# 2. 驗的是形狀，不是欄位存不存在
# --------------------------------------------------------------------------- #
def test_a_column_nobody_measured_is_not_an_error_here():
    """「`glv_std` 這一欄有沒有」要有資料才知道，而存 recipe 的時候沒有資料。

    擋在這裡的話，使用者換一個 metric 就得先把圖刪掉才存得起來。
    """
    got = cs.parse_spec('{"mark":"point","x":"nobody_measures_this","y":"a"}')
    assert got["x"] == "nobody_measures_this"


def test_a_mark_nobody_can_draw_is_an_error():
    """記號是**封閉字彙** —— 那個字要怎麼畫是 `export` 的事，而一個沒有人畫
    得出來的字要當場說，不是跑完一批之後看到一張空白。"""
    with pytest.raises(cs.ChartSpecError) as e:
        cs.parse_spec('{"mark":"hexbin","x":"a","y":"b"}')
    assert "hexbin" in str(e.value)


def test_a_role_nobody_defined_is_an_error():
    with pytest.raises(cs.ChartSpecError):
        cs.parse_spec('{"mark":"point","shape":"region"}')


def test_broken_json_says_so_in_plain_words():
    with pytest.raises(cs.ChartSpecError) as e:
        cs.parse_spec("{not json")
    assert "JSON" in str(e.value)


# --------------------------------------------------------------------------- #
# 3. 「還沒設定完」跟「畫不出來」是兩件事
# --------------------------------------------------------------------------- #
def test_missing_roles_names_what_is_still_needed():
    assert cs.missing_roles("") == ["x", "y"]
    assert cs.missing_roles('{"mark":"point","x":"a"}') == ["y"]
    assert cs.missing_roles('{"mark":"point","x":"a","y":"b"}') == []


def test_every_mark_declares_what_it_needs_and_what_it_uses():
    """加一種記號而忘了登記的症狀是「那張圖畫不出來而畫面上不說為什麼」。"""
    for mark in cs.MARKS:
        assert mark in cs.REQUIRED, mark
        assert mark in cs.USES, mark
        assert set(cs.REQUIRED[mark]) <= set(cs.USES[mark]), mark
        assert set(cs.USES[mark]) <= set(cs.ROLES), mark


def test_every_role_has_a_plain_sentence():
    """鐵則 3 的精神：看的人是同一批（不會寫 code 的製程工程師）。"""
    for role in cs.ROLES:
        said = cs.ROLE_HELP.get(role, "")
        assert said and said.endswith("."), role


def test_describe_is_a_sentence_not_a_json_dump():
    """卡片上那一格是**唯讀的摘要** —— 使用者讀的是它，不是那串 JSON。"""
    said = cs.describe('{"color":"region","mark":"point","x":"a","y":"b"}')
    assert "{" not in said
    assert "b" in said and "a" in said and "region" in said
    assert "pick" in cs.describe("")


# --------------------------------------------------------------------------- #
# 4. 三種記號（F88 第三刀）
# --------------------------------------------------------------------------- #
def test_a_role_this_mark_cannot_use_is_dropped_not_kept():
    """一份折線圖的 spec 帶著一個 `size` 的話，換回散點時它會**突然生效**，
    而使用者不記得設過。"""
    got = cs.format_spec({"mark": "line", "x": "a", "y": "b", "size": "c"})
    assert "size" not in got


def test_every_mark_is_named_and_explained():
    """膠囊上要有字、tooltip 要有一句話（鐵則 3 的精神）。"""
    for mark in cs.MARKS:
        assert cs.MARK_LABELS.get(mark), mark
        said = cs.MARK_HELP.get(mark, "")
        assert said and said.endswith("."), mark


def test_describe_says_which_kind_of_chart_it_is():
    """三種之後「這是哪一種圖」不再是廢話 —— 卡片上那一格要說出來。"""
    said = cs.describe('{"mark":"bar","x":"region","y":"glv_mean"}')
    assert cs.MARK_LABELS["bar"] in said
