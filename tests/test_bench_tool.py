# `tools/bench.py` 這把尺自己會不會壞 — authored 2026-09-08.
"""**這一份不量效能，它量的是「那支量效能的工具」。**

`tools/bench.py` 刻意不進 CI（時間欄在 runner 上會漂，而一道會隨機變紅的關
很快就變成一道大家學會忽略的關）。但「不進 CI」不等於「沒有人守」——
一支沒有人跑得動的工具跟沒有那支工具是一樣的，而那正是 `examples/`
出事的方式（2026-08-16：五份範例 recipe 爛掉，因為沒有任何測試載過它們）。

所以這裡問三種問題，**沒有一種需要真的量效能**：

1. 比對的邏輯對不對（嚴的欄位嚴、寬的欄位寬）；
2. 基準檔還讀得動，而且欄位跟工具現在會產的對得上；
3. 沒有基準的時候，它講的是一句可以照做的話（而且**不會先白白量 20 秒**）。
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))
sys.path.insert(0, str(REPO / "tools"))

import bench                                              # noqa: E402

BASELINE = REPO / "tests" / "fixtures" / "bench_baseline.json"


def _row(**over):
    row = {
        "n": 24, "workers": 4,
        "ms_per_defect_w1": 100.0, "ms_per_defect_wn": 30.0,
        "ms_per_defect_cache_cold": 100.0, "ms_per_defect_cache_warm": 95.0,
        "result_bytes_per_defect": 800.0,
        "cache_files": 24, "cache_bytes_per_defect": 38000.0,
        "parallel_speedup": 3.3, "cache_speedup": 1.05,
    }
    row.update(over)
    return row


def _pair(new_row, old_row=None):
    old = {"env": {}, "cases": {"case": old_row or _row()}}
    new = {"env": {}, "cases": {"case": new_row}}
    return old, new


# --------------------------------------------------------------------------- #
# 1. 嚴的欄位嚴、寬的欄位寬
# --------------------------------------------------------------------------- #
def test_a_slower_run_inside_the_tolerance_is_fine():
    """時間欄慢了但還在容差內 → 不叫。

    這是這支工具**最常見**的情境：同一台機器上跑兩次，差 10–30% 是常態。
    這裡叫的話，它兩天內就會被 `--tolerance 99` 繞過去。
    """
    old, new = _pair(_row(ms_per_defect_w1=150.0))     # 1.5×，容差 2.0
    assert bench._compare(old, new, bench.DEFAULT_TOLERANCE) == []


def test_a_much_slower_run_is_reported():
    """慢一個數量級 → 一定要叫。這支工具的存在理由就是這一條。"""
    old, new = _pair(_row(ms_per_defect_w1=1000.0))    # 10×
    bad = bench._compare(old, new, bench.DEFAULT_TOLERANCE)
    assert [b[0] for b in bad] == ["case.ms_per_defect_w1"]


@pytest.mark.parametrize("field", bench.EXACT_FIELDS)
def test_a_deterministic_field_does_not_get_the_time_tolerance(field):
    """決定性的那幾欄不吃 2× 的容差 —— 它們跟機器無關。

    ``result_bytes_per_defect`` 變大 20% 講的是「每顆多了一批特徵」，
    ``cache_files`` 變了講的是 checkpoint 的位置動了。兩件事都是**行為變了**，
    而不是「這台機器今天比較忙」。用同一個容差蓋住它們的話，這支工具就只剩
    一個很鈍的碼表。
    """
    base = _row()
    old, new = _pair(_row(**{field: base[field] * 1.2}))
    bad = bench._compare(old, new, bench.DEFAULT_TOLERANCE)
    assert [b[0] for b in bad] == ["case.%s" % field], bad


def test_a_tiny_wobble_in_a_deterministic_field_is_still_fine():
    """±2% 以內不叫 —— 浮點數的字串表示會隨 numpy 版本差一位。"""
    old, new = _pair(_row(result_bytes_per_defect=800.0 * 1.01))
    assert bench._compare(old, new, bench.DEFAULT_TOLERANCE) == []


def test_a_derived_number_is_not_compared_twice():
    """``parallel_speedup`` / ``cache_speedup`` 是上面那幾欄推出來的。

    比它們等於同一件事比兩次，而且會製造一種很難讀的紅：時間欄已經叫過一次，
    倍率欄再叫一次同樣的事。
    """
    old, new = _pair(_row(parallel_speedup=1.0, cache_speedup=1.0))
    assert bench._compare(old, new, bench.DEFAULT_TOLERANCE) == []


def test_a_new_case_says_so_instead_of_crashing():
    """基準裡沒有這個 case → 講一句可以照做的話，不是 KeyError。"""
    old = {"env": {}, "cases": {}}
    new = {"env": {}, "cases": {"brand_new": _row()}}
    bad = bench._compare(old, new, bench.DEFAULT_TOLERANCE)
    assert len(bad) == 1 and "重跑" in bad[0][3]


# --------------------------------------------------------------------------- #
# 2. 基準檔跟工具還對得上
# --------------------------------------------------------------------------- #
def test_the_baseline_is_readable_and_says_where_it_came_from():
    """基準要帶著它是在什麼機器上量的 —— 不然跨機器比對是蘋果比橘子。"""
    data = json.loads(BASELINE.read_text(encoding="utf-8"))
    assert set(data) == {"env", "cases"}
    for key in ("python", "platform", "cpu_count", "numpy", "cv2"):
        assert key in data["env"], key


def test_the_baseline_covers_exactly_the_cases_the_tool_measures():
    """`CASES` 改了而基準沒重凍的話，`--check` 只會說「有一個新 case」——
    那句話在**每一次**執行都出現，於是它變成雜訊。這裡先擋下來。"""
    data = json.loads(BASELINE.read_text(encoding="utf-8"))
    expected = {bench._tag(r, g) for r, g, _n, _s in bench.CASES}
    assert set(data["cases"]) == expected


@pytest.mark.parametrize("field", bench.EXACT_FIELDS)
def test_every_strictly_compared_field_is_in_the_baseline(field):
    """嚴格比對的欄位要真的在基準裡 —— 不在的話 `_compare` 會安靜地跳過它。

    這一條守的是「例外清單的反向」那條規矩的變體：
    :data:`bench.EXACT_FIELDS` 上列一個基準裡沒有的名字，不會有任何東西叫，
    而那一欄從此**沒有人在守**。
    """
    data = json.loads(BASELINE.read_text(encoding="utf-8"))
    for tag, row in data["cases"].items():
        assert field in row, "%s 的基準少了 %s" % (tag, field)


def test_the_baseline_recipes_still_exist():
    """`CASES` 指的 recipe 要真的在磁碟上。"""
    for recipe_file, _gen, _n, _s in bench.CASES:
        assert (REPO / "tests" / "fixtures" / "recipes" / recipe_file).exists()


# --------------------------------------------------------------------------- #
# 3. 沒有基準的時候
# --------------------------------------------------------------------------- #
def test_a_missing_baseline_says_what_to_do_without_measuring_first(
        tmp_path, capsys, monkeypatch):
    """回 2、講出下一句話，而且**不先白白量 20 秒**。

    「不先量」是這一條真正在守的東西：`main()` 第一版把 `collect()` 放在檢查
    之前，於是一台還沒凍過基準的機器要等一次完整的量測，才被告知它做的那件事
    從一開始就不會成立。

    ⚠ 這裡以前用**時間**證明它沒有量（`elapsed < 2.0`）—— 而 2026-09-09 CI
    的一台 runner 在 `argparse` ＋ `os.path.exists` 上就停了 3.8 秒（PR #41，
    diff 一個字都沒碰 `bench.py`）。牆上時鐘證明不了「有沒有呼叫」；直接把
    `collect` 換成會炸的，呼叫到就是紅。
    """
    def _must_not_measure():
        raise AssertionError("它在報告『找不到基準』之前先量了")

    monkeypatch.setattr(bench, "collect", _must_not_measure)
    rc = bench.main(["--check", "--out", str(tmp_path / "nope.json")])
    assert rc == 2
    assert "先跑一次" in capsys.readouterr().out
