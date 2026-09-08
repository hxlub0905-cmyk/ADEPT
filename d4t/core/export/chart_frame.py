# -*- coding: utf-8 -*-
# d4t chart frame — authored 2026-09-07 (F88 第一刀).
"""**一張長表：一列一格框。**

為什麼要它（`docs/plans/F88-graph-builder.md` §2）
--------------------------------------------------
`uniformity_charts.chart_series` 產的是「四張圖各自需要的形狀」
（``groups[{name, colour, values, cx, cy, rects}]``）—— 也就是**資料的形狀
跟著圖走**。graph builder 要的相反：**一份資料，很多種看法**。

    region   box   x     y    row  col   glv_mean  glv_std  …
    epi      0     70    90   0    0     112.0     2.1
    epi      1     160   90   0    1     112.9     2.0
    mg       0     600   90   0    0     128.3     3.4

一列一格框，**每一個量出來的統計量各一欄**，而畫圖那一側只需要說「拿哪一欄」。

⚠ **這一支就算之後不做 graph builder 也值得**：長表直接寫得成 CSV，而
「一格框一列」是現在完全沒有的東西 —— `defects.csv` 是**一顆 defect 一列**，
看不到格。所以第一刀單獨出貨就有價值。

``row`` / ``col``：這一格在第幾列第幾欄
---------------------------------------
每一格框現在只知道自己 ``y=270``，**不知道自己在第 3 列**。而那個分群
`algo.uniformity.cell_edges` 已經在做了（熱圖排格子用的同一支），所以這兩欄
幾乎免費 —— 有了它們，「一列一條線」就不是一種新圖，只是「顏色 = row」。

⚠ **列與欄是整張表一起分的，不是一個區域分一次。** 兩個區域擺在同一片場上
時，`epi` 的第 0 列跟 `mg` 的第 0 列要是**同一列**，不然「顏色 = row」畫出來
的線會對不齊，而畫面上不會說。
"""
from __future__ import annotations

import csv
import io
from typing import Any, Dict, List, Optional, Sequence, Tuple

import numpy as np

__all__ = ["COLUMNS_FIXED", "Frame", "build_frame", "write_csv"]

#: 每一列一定有的那幾欄（順序就是 CSV 的欄序）。
COL_REGION = "region"
COL_BOX = "box"
COL_X, COL_Y = "x", "y"
COL_W, COL_H = "w", "h"
COL_ROW, COL_COL = "row", "col"

COLUMNS_FIXED: Tuple[str, ...] = (COL_REGION, COL_BOX, COL_X, COL_Y,
                                  COL_W, COL_H, COL_ROW, COL_COL)

#: 欄名 → **給人看的字**（F89-2，2026-09-08）。
#:
#: 為什麼要有這一層（使用者問「工程師會不會看不懂」）：選單裡以前是原始欄名
#: —— `region, box, x, y, w, h, row, col, glv_median…`。其中 **`x` / `y` 是
#: 框中心的座標**，但它們擺在「Across the bottom」旁邊，讀起來就是「X 軸」；
#: 挑 `y` 想畫「數值」的人會拿到位置，而那張圖畫得出來、有數字、而且答錯了
#: 問題。卡片的參數早就有這一層（`ParamSpec.label`，`range_from` →
#: `Borrow range from`），長表的欄一直沒有。
#:
#: ⚠ **只加顯示的字，鍵一個都不動** —— `spec` 裡存的還是 `x`，所以 recipe
#: 一個位元都沒變。沒列的欄（使用者量出來的統計量）就顯示它自己的名字：
#: `glv_median` 對製程工程師**本來就是**一句話，翻譯它反而是多的。
COLUMN_LABELS: Dict[str, str] = {
    COL_REGION: "Region",
    COL_BOX: "Box number",
    COL_X: "Box centre X (px)",
    COL_Y: "Box centre Y (px)",
    COL_W: "Box width (px)",
    COL_H: "Box height (px)",
    COL_ROW: "Which row of boxes",
    COL_COL: "Which column of boxes",
}


def column_label(name: str) -> str:
    """一欄在畫面上叫什麼。沒登記的（量出來的統計量）就是它自己的名字。"""
    return COLUMN_LABELS.get(str(name), str(name))


#: 這幾欄是**類別**（可以放到「顏色」「分組」上），其餘是數值。
#:
#: ⚠ ``row`` / ``col`` 是整數，但它們是**類別**不是量 —— 「第 3 列」比
#: 「第 1 列」大兩列這件事沒有意義，而把它們畫在數值軸上會讓人以為有。
CATEGORY_COLUMNS: Tuple[str, ...] = (COL_REGION, COL_ROW, COL_COL)


class Frame(object):
    """一張長表。**純資料** —— 不畫圖、不認識任何一種圖。"""

    def __init__(self, columns: Sequence[str],
                 rows: Sequence[Dict[str, Any]],
                 categories: Optional[Sequence[str]] = None,
                 labels: Optional[Dict[str, str]] = None) -> None:
        self.columns: List[str] = [str(c) for c in columns]
        self.rows: List[Dict[str, Any]] = [dict(r) for r in rows]
        #: ⚠ **哪幾欄是類別，是這一張表自己的事**（F89-4）。以前它讀模組層的
        #: `CATEGORY_COLUMNS`，而那是「一列一格框」那張表的清單 —— 第二張表
        #: （一列一顆 defect）的 `die_x` 會被當成一個量，於是「第 3 欄的 die
        #: 比第 1 欄大兩欄」這件沒有意義的事被畫成一條連續軸。
        self.categories: Tuple[str, ...] = tuple(
            categories if categories is not None else CATEGORY_COLUMNS)
        #: 這一張表的欄名 → 給人看的字（沒登記的就是它自己的名字）。
        self.labels: Dict[str, str] = dict(
            labels if labels is not None else COLUMN_LABELS)

    def __len__(self) -> int:
        return len(self.rows)

    def column(self, name: str) -> List[Any]:
        """一整欄（缺值是 ``None`` —— **不要跳過**，索引要對得上其他欄）。"""
        return [r.get(str(name)) for r in self.rows]

    def numeric_columns(self) -> List[str]:
        """可以放到 X / Y / 大小 上的那幾欄。"""
        return [c for c in self.columns if c not in self.categories]

    def category_columns(self) -> List[str]:
        """可以放到 顏色 / 分組 上的那幾欄。"""
        return [c for c in self.columns if c in self.categories]

    def label(self, name: str) -> str:
        """一欄在畫面上叫什麼（見 `column_label`）。"""
        return self.labels.get(str(name), str(name))

    def values(self, name: str) -> List[float]:
        """一欄裡**畫得出來的**那些數（跳過缺值與 NaN）。"""
        out: List[float] = []
        for v in self.column(name):
            try:
                f = float(v)
            except (TypeError, ValueError):
                continue
            if np.isfinite(f):
                out.append(f)
        return out

    def to_csv(self) -> str:
        """整張表 → CSV。**欄序固定**（`COLUMNS_FIXED` 在前，統計量照量出來
        的順序在後）—— 兩次跑出來欄序不一樣的話，diff 讀不動。"""
        buf = io.StringIO()
        w = csv.DictWriter(buf, fieldnames=self.columns,
                           lineterminator="\n", extrasaction="ignore")
        w.writeheader()
        for r in self.rows:
            w.writerow({c: _cell(r.get(c)) for c in self.columns})
        return buf.getvalue()


def _cell(value: Any) -> Any:
    """CSV 上一格。**算不出來的留白**，不是 0 也不是 nan（同 `glv_stats`
    的規矩：「0」讀起來是「量到了而且是零」）。"""
    if value is None:
        return ""
    try:
        f = float(value)
    except (TypeError, ValueError):
        return value
    if not np.isfinite(f):
        return ""
    return int(f) if float(f).is_integer() and abs(f) < 1e12 else repr(f)


def build_frame(notes: Sequence[Any],
                metrics: Optional[Sequence[str]] = None) -> Frame:
    """``ctx.meta["glv_hist"]`` 的那幾條 → 一張長表。

    ``metrics`` 沒給就用**出現過的每一個統計量**（照第一次出現的順序）。
    沒有 ``spread`` 的 note 跳過（那是走 pooled 的，沒有逐格的數字）。

    ⚠ **值與位置共用索引**是所有位置計算的前提（同 `chart_series`）——
    對不上的那一條整個跳過，不要畫一半。
    """
    picked: List[str] = [str(m) for m in (metrics or ())]
    kept: List[Tuple[str, Dict[str, Any]]] = []
    for note in (notes or ()):
        if not isinstance(note, dict):
            continue
        spread = note.get("spread")
        if not isinstance(spread, dict):
            continue
        stats = spread.get("stats") or {}
        n = _length(stats, spread)
        if n <= 0:
            continue
        name = str(note.get("region") or "") or str(note.get("prefix") or "")
        kept.append((name or "region", spread))
        if not picked:
            for m in stats:
                if str(m) not in picked:
                    picked.append(str(m))

    if not kept:
        return Frame(list(COLUMNS_FIXED), [])

    # ⚠ **列與欄整張表一起分**（見模組說明）——各分各的話，兩個區域的
    # 「第 0 列」會是不同的兩件事。
    all_cx = [c for _n, sp in kept for c in (sp.get("cx") or ())]
    all_cy = [c for _n, sp in kept for c in (sp.get("cy") or ())]
    col_of = _slot_index(all_cx)
    row_of = _slot_index(all_cy)

    rows: List[Dict[str, Any]] = []
    for name, sp in kept:
        stats = sp.get("stats") or {}
        cx = list(sp.get("cx") or ())
        cy = list(sp.get("cy") or ())
        rects = [tuple(r) for r in (sp.get("rects") or ())]
        boxes = list(sp.get("boxes") or ())
        n = _length(stats, sp)
        for i in range(n):
            rect = rects[i] if i < len(rects) else (None, None, None, None)
            x = float(cx[i]) if i < len(cx) else None
            y = float(cy[i]) if i < len(cy) else None
            row = {
                COL_REGION: name,
                COL_BOX: int(boxes[i]) if i < len(boxes) else i,
                COL_X: x, COL_Y: y,
                COL_W: _num(rect[2]), COL_H: _num(rect[3]),
                COL_COL: col_of(x), COL_ROW: row_of(y),
            }
            for m in picked:
                vals = stats.get(m) or ()
                row[m] = float(vals[i]) if i < len(vals) else None
            rows.append(row)
    return Frame(list(COLUMNS_FIXED) + picked, rows)


def _length(stats: Dict[str, Any], spread: Dict[str, Any]) -> int:
    """這一條有幾格 —— **每一串都要一樣長**，否則回 0（整條跳過）。"""
    lens = {len(v or ()) for v in stats.values()}
    if len(lens) != 1:
        return 0
    n = lens.pop()
    for key in ("cx", "cy"):
        got = spread.get(key)
        if got is not None and len(got) != n:
            return 0
    return int(n)


def _num(value: Any) -> Optional[float]:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _slot_index(positions: Sequence[Any]):
    """一串位置 → ``位置 -> 第幾格`` 的查表（走 `cell_edges` 的同一套分群）。"""
    from ..algo import uniformity as unif

    centres, _edges = unif.cell_edges([p for p in positions if p is not None])

    def at(value: Any) -> Optional[int]:
        if value is None or centres.size == 0:
            return None
        return int(np.abs(centres - float(value)).argmin())

    return at


# --------------------------------------------------------------------------- #
# 第二張長表：**一列一顆 defect**（F89-4）
# --------------------------------------------------------------------------- #
#: 一列一顆時的固定欄。
LOT_ID = "defect_id"
LOT_SCORE, LOT_BIN, LOT_OK = "score", "bin", "measured"
LOT_DIE_X, LOT_DIE_Y = "die_x", "die_y"
LOT_UM_X, LOT_UM_Y = "x_um", "y_um"

LOT_COLUMNS_FIXED: Tuple[str, ...] = (LOT_ID, LOT_OK, LOT_SCORE, LOT_BIN,
                                      LOT_DIE_X, LOT_DIE_Y,
                                      LOT_UM_X, LOT_UM_Y)

#: 這幾欄是**類別**（`die_x` / `die_y` 是晶片在晶圓上的第幾格，不是量）。
LOT_CATEGORY_COLUMNS: Tuple[str, ...] = (LOT_ID, LOT_OK, LOT_BIN,
                                         LOT_DIE_X, LOT_DIE_Y)

LOT_COLUMN_LABELS: Dict[str, str] = {
    LOT_ID: "Defect",
    LOT_OK: "Measured without error",
    LOT_SCORE: "Score",
    LOT_BIN: "Class (bin)",
    LOT_DIE_X: "Die column",
    LOT_DIE_Y: "Die row",
    LOT_UM_X: "X in the die (um)",
    LOT_UM_Y: "Y in the die (um)",
}


def build_lot_frame(rows: Sequence[Any],
                    items: Optional[Sequence[Any]] = None) -> Frame:
    """一批跑完的結果 → **一列一顆 defect** 的長表。

    為什麼要有第二張表（F89-4，使用者 2026-09-08：「可以設計的東西還是太少」）
    ------------------------------------------------------------------------
    :func:`build_frame` 是「**一顆之內**、一列一格框」，所以拿它畫得出來的問題
    全部被鎖在一張影像裡。而工程師真正常問的兩句是**跨顆**的：
    「這一批 400 顆怎麼散」「哪一個 die 特別差」。那不是 builder 缺旋鈕，
    是缺這一張表。

    ``rows`` 是 `run_batch` 回的那幾列（``defect_id / ok / score / bin /
    features``）。``items`` 選填 —— 給了就把**座標**也接上來
    （`DefectItem.die` 與 `xrel_nm` / `yrel_nm`），而 `die_x` × `die_y` 配一個
    統計量當顏色就是一張 **wafer map**。

    ⚠ **nm 換成 µm**：一顆 defect 的 die 內座標動輒是幾百萬 nm，而軸上印
    `4520000` 沒有人讀得動。除以 1000 是這裡唯一做的換算，而欄名寫著單位。

    ⚠ **算不出來的那一格留白**（``None``），不是 0 —— 沒有 KLARF 的那兩種輸入
    整欄都是空的，而「沒有座標」跟「座標在原點」是兩件事。
    """
    by_id: Dict[str, Any] = {}
    for it in (items or ()):
        got = str(getattr(it, "defect_id", "") or "")
        if got:
            by_id[got] = it

    picked: List[str] = []
    out: List[Dict[str, Any]] = []
    for row in (rows or ()):
        if not isinstance(row, dict):
            continue
        did = str(row.get("defect_id", "") or "")
        feats = row.get("features") or {}
        one: Dict[str, Any] = {
            LOT_ID: did,
            # 「這一顆量出來了嗎」是**類別**，而它值得在圖上分得出來：
            # 一批裡有幾顆整條 pipeline 出錯是使用者要先知道的事（鐵則 7 是
            # 「不殺整批」，不是「當作沒發生」）。
            LOT_OK: "yes" if row.get("ok") else "no",
            LOT_SCORE: _num(row.get("score")),
            LOT_BIN: "" if row.get("bin") is None else str(row.get("bin")),
            LOT_DIE_X: "", LOT_DIE_Y: "",
            LOT_UM_X: None, LOT_UM_Y: None,
        }
        item = by_id.get(did)
        if item is not None:
            die = getattr(item, "die", None)
            if die is not None and len(tuple(die)) == 2:
                one[LOT_DIE_X] = str(int(tuple(die)[0]))
                one[LOT_DIE_Y] = str(int(tuple(die)[1]))
            for key, attr in ((LOT_UM_X, "xrel_nm"), (LOT_UM_Y, "yrel_nm")):
                nm = _num(getattr(item, attr, None))
                one[key] = None if nm is None else round(nm / 1000.0, 4)
        for name, value in feats.items():
            got = str(name)
            if got not in picked:
                picked.append(got)
            one[got] = _num(value)
        out.append(one)

    # 特徵**照名字排**（一顆一顆量出來的順序不見得一樣，而選單跳來跳去讀不動）
    return Frame(list(LOT_COLUMNS_FIXED) + sorted(picked), out,
                 categories=LOT_CATEGORY_COLUMNS, labels=LOT_COLUMN_LABELS)


def write_csv(frame: Frame, path: str) -> str:
    """整張表 → 一個檔。**跟 `defects.csv` 走同一套寫法。**

    ⚠ 那件事不是細節：兩份 CSV 會躺在**同一個資料夾**裡，而
    `report.write_csv` 用的是 ``utf-8-sig``（Excel 雙擊直接開不亂碼）。
    這一份走一般的 UTF-8 的話，同一個資料夾裡兩個檔，一個開起來正常、一個
    區域名變亂碼 —— 而使用者沒有任何線索知道為什麼。

    借的是 `report` 那兩支私有的（同 `uniformity_charts` 借 `boxplot` 的
    `_esc` / `_fmt`）：**寫檔的規矩只該有一份**，而它已經在那裡了
    （atomic：`.tmp` + `os.replace`，鐵則 5）。
    """
    from .report import _atomic_replace, _ensure_parent  # noqa: PLC2701

    path = str(path)
    _ensure_parent(path)
    tmp = path + ".tmp"
    with io.open(tmp, "w", encoding="utf-8-sig", newline="") as f:
        f.write(frame.to_csv())
    return _atomic_replace(tmp, path)
