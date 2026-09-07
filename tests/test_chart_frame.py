# F88 第一刀：一列一格框的長表（`core/export/chart_frame.py`）。
"""鎖的都是不變量：一列一格框、**列與欄整張表一起分**、算不出來的留白、
欄序固定、對不上的整條跳過。

計畫書：`docs/plans/F88-graph-builder.md` §2。
"""
from __future__ import annotations

import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))

from d4t.core.export.chart_frame import (  # noqa: E402
    CATEGORY_COLUMNS, COLUMNS_FIXED, Frame, build_frame,
)


def _note(name, base, x0=40, cols=3, rows=2, std=True):
    n = cols * rows
    stats = {"glv_mean": [base + i for i in range(n)]}
    if std:
        stats["glv_std"] = [1.0 + 0.1 * i for i in range(n)]
    return {"region": name, "prefix": name, "spread": {
        "stats": stats,
        "cx": [float(x0 + 90 * (i % cols)) for i in range(n)],
        "cy": [float(40 + 90 * (i // cols)) for i in range(n)],
        "rects": [[x0 + 90 * (i % cols), 40 + 90 * (i // cols), 60, 60]
                  for i in range(n)],
        "boxes": list(range(n))}}


def test_one_row_per_box():
    f = build_frame([_note("epi", 110.0), _note("mg", 128.0, x0=400)])
    assert len(f) == 12
    assert f.columns[:len(COLUMNS_FIXED)] == list(COLUMNS_FIXED)
    # 統計量照**量出來的順序**接在後面（不是字母序）
    assert f.columns[len(COLUMNS_FIXED):] == ["glv_mean", "glv_std"]


def test_rows_and_columns_are_split_across_the_whole_table():
    """⚠ **列與欄是整張表一起分的，不是一個區域分一次。**

    兩個區域擺在同一片場上時，`epi` 的第 0 列跟 `mg` 的第 0 列要是**同一
    列** —— 各分各的話，「顏色 = row」畫出來的線會對不齊，而畫面上不會說。
    """
    f = build_frame([_note("epi", 110.0, x0=40), _note("mg", 128.0, x0=400)])
    by = {}
    for r in f.rows:
        by.setdefault(r["region"], []).append((r["row"], r["col"]))
    # 同樣的兩列（y 一樣）→ 同樣的 row 編號
    assert sorted({r for r, _c in by["epi"]}) == [0, 1]
    assert sorted({r for r, _c in by["mg"]}) == [0, 1]
    # 左右擺開 → 欄編號接續，不重疊
    assert sorted({c for _r, c in by["epi"]}) == [0, 1, 2]
    assert sorted({c for _r, c in by["mg"]}) == [3, 4, 5]


def test_row_and_col_are_categories_not_quantities():
    """「第 3 列」比「第 1 列」大兩列這件事沒有意義 —— 畫在數值軸上會讓人
    以為有。"""
    f = build_frame([_note("epi", 110.0)])
    assert set(CATEGORY_COLUMNS) <= set(f.columns)
    for c in ("region", "row", "col"):
        assert c in f.category_columns() and c not in f.numeric_columns()
    for c in ("x", "y", "glv_mean"):
        assert c in f.numeric_columns()


def test_a_missing_number_is_left_blank_not_zero():
    """**算不出來的留白**（同 `glv_stats` 的規矩：「0」讀起來是「量到了而且
    是零」）。"""
    a = _note("epi", 110.0)
    b = _note("mg", 128.0, x0=400, std=False)     # 這一群沒有 glv_std
    f = build_frame([a, b])
    lines = f.to_csv().strip().split("\n")
    assert lines[0].endswith("glv_mean,glv_std")
    mg = [ln for ln in lines if ln.startswith("mg,")]
    assert mg and all(ln.endswith(",") for ln in mg), "缺的那一欄要留白"
    assert not any(ln.endswith(",0") for ln in mg)


def test_a_mismatched_note_is_dropped_whole():
    """值與位置**共用索引**是所有位置計算的前提 —— 對不上就整條不要，
    不要畫一半（同 `chart_series` / `set_marks` 的規矩）。"""
    bad = _note("epi", 110.0)
    bad["spread"]["cx"] = bad["spread"]["cx"][:3]      # 位置少了一半
    f = build_frame([bad, _note("mg", 128.0, x0=400)])
    assert {r["region"] for r in f.rows} == {"mg"}


def test_two_metrics_of_different_length_drop_the_note():
    bad = _note("epi", 110.0)
    bad["spread"]["stats"]["glv_std"] = [1.0, 2.0]
    f = build_frame([bad])
    assert len(f) == 0


def test_pooled_notes_have_nothing_to_offer():
    """走 pooled 的那幾條沒有逐格的數字（`spread` 是 None）。"""
    f = build_frame([{"region": "epi", "spread": None}, {"nope": 1}])
    assert len(f) == 0 and f.columns == list(COLUMNS_FIXED)


def test_the_csv_column_order_is_stable():
    """兩次跑出來欄序不一樣的話，diff 讀不動。"""
    notes = [_note("epi", 110.0), _note("mg", 128.0, x0=400)]
    assert build_frame(notes).to_csv() == build_frame(notes).to_csv()


def test_values_skips_what_cannot_be_drawn():
    f = Frame(["v"], [{"v": 1.0}, {"v": None}, {"v": float("nan")},
                      {"v": "x"}, {"v": 3.0}])
    assert f.values("v") == [1.0, 3.0]
    assert len(f.column("v")) == 5, "取一整欄不准跳過 —— 索引要對得上"


def test_a_named_metric_list_wins():
    f = build_frame([_note("epi", 110.0)], metrics=["glv_std"])
    assert f.columns[-1] == "glv_std" and "glv_mean" not in f.columns


def test_the_box_table_is_written_like_the_defect_table(tmp_path):
    """**兩份 CSV 躺在同一個資料夾裡，寫法就要一樣。**

    `report.write_csv` 用 ``utf-8-sig``（Excel 雙擊直接開不亂碼）。這一份走
    一般 UTF-8 的話，同一個資料夾裡一個開起來正常、一個區域名變亂碼 ——
    而使用者沒有任何線索知道為什麼。
    """
    from d4t.core.export.chart_frame import write_csv

    path = tmp_path / "boxes.csv"
    write_csv(Frame(["region", "v"], [{"region": "磊晶", "v": 1.5}]),
              str(path))
    raw = path.read_bytes()
    assert raw[:3] == b"\xef\xbb\xbf", "沒有 BOM —— Excel 會把中文開成亂碼"
    assert "磊晶" in raw[3:].decode("utf-8")
    # atomic（鐵則 5）：不留 .tmp
    assert not (tmp_path / "boxes.csv.tmp").exists()


def test_the_two_csv_files_format_numbers_the_same_way():
    """同一個數字在兩張表上要長一樣 —— 不然對照的人會以為是兩個數字。"""
    import csv as _csv
    import io as _io

    from d4t.core.export import report as _report

    buf = _io.StringIO()
    _csv.writer(buf).writerow([132.79999999999998])
    theirs = buf.getvalue().strip()
    mine = Frame(["v"], [{"v": 132.79999999999998}]).to_csv()
    assert mine.strip().split("\n")[1] == theirs
    assert hasattr(_report, "write_csv")
