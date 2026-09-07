# -*- coding: utf-8 -*-
# d4t chart draw — authored 2026-09-07 (F88 第二刀).
"""**一張長表 ＋ 一份 spec → 一張 SVG。**

計畫書 `docs/plans/F88-graph-builder.md` §4。

裡面只有兩件事一般化：

* **scale** —— 一欄 → 畫布座標。`linear`（數值）與 `band`（類別）。
* **mark** —— 一列（或一群）→ 一段 SVG。這一刀只有 `point`。

⚠ **`chart_style` 一格都不動。** 字級、線寬、填色、鎖定範圍走的是同一支
`resolve_style`，因為它們本來就是「長什麼樣」而不是「畫什麼」。四張舊圖與
這一張因此在同一頁上長得一樣 —— 那正是它們會並排在同一份報表裡的理由。

⚠ **軸與刻度借 `uniformity_charts` 的那幾支**（`_nice_ticks` / `_frame` /
`_xlabels` / `_ylabels`）。各寫一份的話，同一份報表裡兩張圖的刻度算法會不一
樣，而那件事沒有人看得出來為什麼。
"""
from __future__ import annotations

import math
from typing import Any, Dict, List, Optional, Sequence, Tuple

from ..pipeline import chart_spec as spec_mod
from .chart_frame import CATEGORY_COLUMNS, Frame
from .uniformity_charts import (  # noqa: PLC2701 — 見檔頭：刻度只該有一份
    REGION_COLOURS, _axis_names, _empty, _esc, _fmt, _frame, _head,
    _mark_colour, _nice_ticks, _span, _text_attrs, _xlabels, _ylabels,
    heat_hex, seq_hex,
)

__all__ = ["draw"]

_AXIS = "#98a2b3"
_TEXT = "#444"
_MUTED = "#777"


def draw(frame: Frame, spec: object, style: Optional[Dict[str, Any]] = None,
         width: int = 640, height: int = 420) -> str:
    """一張圖。**畫不出來時回一張說得出原因的圖**，不是空字串。

    ⚠ 那一條跟 `build_chart_svg` 一字不差：呼叫端把它塞進 HTML，而一個消失
    的區塊讀起來是「這裡本來就沒有東西」。
    """
    st = dict(style or {})
    sp = spec_mod.parse_spec(spec)
    need = spec_mod.missing_roles(sp)
    if need:
        return _empty(width, height,
                      "pick %s to draw this chart" % " and ".join(need))
    if not len(frame):
        return _empty(width, height, "no boxes to plot")

    xs = frame.column(sp["x"])
    ys = frame.column(sp["y"])
    if all(v is None for v in xs):
        return _empty(width, height, "no column called '%s'" % sp["x"])
    if all(v is None for v in ys):
        return _empty(width, height, "no column called '%s'" % sp["y"])

    if str(sp["mark"]) == spec_mod.MARK_POINT:
        return _points(frame, sp, st, int(width), int(height))
    # 封閉字彙（`chart_spec.MARKS`）—— 走到這裡表示有人加了一種 mark 卻沒有
    # 在這裡畫它，而那要說出來，不是畫一張空白。
    return _empty(width, height, "nothing here can draw a '%s'" % sp["mark"])


# --------------------------------------------------------------------------- #
# scale
# --------------------------------------------------------------------------- #
class _Linear(object):
    """數值軸。**鎖住的範圍照鎖的**（同 `_span`）。"""

    kind = "linear"

    def __init__(self, values: Sequence[Any], lo_hi=None) -> None:
        self.lo, self.hi = _span([v for v in values if _ok(v)], lo_hi)

    def at(self, value: Any, a: float, b: float) -> Optional[float]:
        if not _ok(value):
            return None
        span = (self.hi - self.lo) or 1.0
        return a + (float(value) - self.lo) / span * (b - a)

    def ticks(self, want: int) -> List[float]:
        return _nice_ticks(self.lo, self.hi, max(2, int(want)))

    def label(self, t: float) -> str:
        return _fmt(t)


class _Band(object):
    """類別軸：一格一個槽，記號落在槽的中間。

    ⚠ **槽的順序是值第一次出現的順序**，不是字母序 —— 區域的順序是使用者
    在畫布上接線的順序，而那個順序在別的圖上（盒鬚圖、圖例）也是一樣的。
    """

    kind = "band"

    def __init__(self, values: Sequence[Any], lo_hi=None) -> None:
        seen: List[str] = []
        for v in values:
            s = "" if v is None else str(v)
            if s not in seen:
                seen.append(s)
        self.slots = seen or [""]

    def at(self, value: Any, a: float, b: float) -> Optional[float]:
        s = "" if value is None else str(value)
        if s not in self.slots:
            return None
        step = (b - a) / float(len(self.slots))
        return a + step * (self.slots.index(s) + 0.5)

    def ticks(self, want: int) -> List[str]:
        return list(self.slots)

    def label(self, t: Any) -> str:
        return str(t)


def _scale(frame: Frame, column: str, lo_hi=None):
    """一欄 → 一支 scale。**類別欄走 band，其餘走 linear。**"""
    if str(column) in CATEGORY_COLUMNS:
        return _Band(frame.column(column))
    return _Linear(frame.column(column), lo_hi)


def _ok(value: Any) -> bool:
    try:
        return math.isfinite(float(value))
    except (TypeError, ValueError):
        return False


# --------------------------------------------------------------------------- #
# mark：point
# --------------------------------------------------------------------------- #
def _points(frame: Frame, sp: Dict[str, Any], style: Dict[str, Any],
            width: int, height: int) -> str:
    colour_of, legend = _colours(frame, str(sp.get("color") or ""), style)
    radius_of = _radii(frame, str(sp.get("size") or ""), style)

    pad_l, pad_r = 58, 18
    pad_t = 30 if style.get("title") else 14
    pad_b = 46 + (14 if legend else 0)
    pw = max(60, width - pad_l - pad_r)
    ph = max(60, height - pad_t - pad_b)

    # **鎖定的是「值那一軸」，而在這張圖上那是 Y。** X 也是一個統計量，
    # 但同一組鎖定範圍套到兩條意思不同的軸上會把圖擠成一條線 —— 兩批要並排
    # 比的時候，鎖住 Y 就夠了（同 `_span` 那條「鎖住的照鎖的」）。
    sx = _scale(frame, sp["x"])
    sy = _scale(frame, sp["y"], style.get("vlock"))

    o = _head(width, height, str(style.get("title") or ""))
    _frame(o, pad_l, pad_t, pw, ph)

    # ⚠ **刻度先畫**：`_ylabels` 順手畫橫格線，而格線是背景 —— 畫在點之後
    # 會從點上壓過去（`_svg_profile` 也是這個順序）。
    _ticks(o, sx, sy, pad_l, pad_t, pw, ph, style)

    filled = bool(style.get("point_fill"))
    line_w = float(style.get("line_width", 1.6) or 1.6) / 1.6
    for i in range(len(frame)):
        row = frame.rows[i]
        x = sx.at(row.get(sp["x"]), pad_l, pad_l + pw)
        y = sy.at(row.get(sp["y"]), pad_t + ph, pad_t)   # Y 由下往上
        if x is None or y is None:
            continue                    # **算不出來的那一格不畫**（不是畫在 0）
        ink = colour_of(row)
        face = ("fill='%s'" % ink) if filled else "fill='none'"
        o.append("<circle cx='%.1f' cy='%.1f' r='%.2f' %s stroke='%s' "
                 "stroke-width='%.1f'/>"
                 % (x, y, radius_of(row), face, ink, max(0.6, line_w)))

    _axis_names(o, style, width, height, pad_l, pad_t, pw, ph,
                str(sp["x"]), str(sp["y"]))
    if legend:
        _legend(o, legend, pad_l, height - 8, style)
    o.append("</svg>")
    return "".join(o)


# --------------------------------------------------------------------------- #
# 顏色與大小
# --------------------------------------------------------------------------- #
def _colours(frame: Frame, column: str, style: Dict[str, Any]):
    """``一列 -> 顏色``，外加圖例（沒有顏色角色時圖例是空的）。

    * **類別**（區域、第幾列、第幾欄）→ 一個一個顏色，**照固定順序發、不循環**
      （超過就併成一個「其他」，因為第 9 個生出來的顏色跟前面某一個一定像）。
    * **數值** → 由淺到深的單色階（使用者 2026-09-07 定調「兩種都可 預設單色」；
      彩虹是 `Colour ramp` 那一格切過去的）。
    """
    fallback = _mark_colour(style, "point", REGION_COLOURS[0])
    if not column:
        return (lambda _row: fallback), []

    if column in CATEGORY_COLUMNS:
        seen: List[str] = []
        for v in frame.column(column):
            s = "" if v is None else str(v)
            if s not in seen:
                seen.append(s)
        pal = list(REGION_COLOURS)
        # ⚠ **不循環。** 第 9 個併成「其他」——循環的話兩群會同色，而圖例上
        # 看起來是兩列，圖上分不出來。
        top = seen[:len(pal)]
        other = _MUTED
        mapping = {name: pal[i] for i, name in enumerate(top)}
        legend = [(n, mapping[n]) for n in top]
        if len(seen) > len(pal):
            legend.append(("other (%d)" % (len(seen) - len(pal)), other))

        def by_name(row):
            return mapping.get(str(row.get(column) or ""), other)

        return by_name, legend

    vals = frame.values(column)
    # 顏色那一軸的鎖定跟熱圖同一格（兩張圖上「顏色＝值多少」是同一件事）。
    lo, hi = _span(vals, style.get("hlock"))
    rainbow = str(style.get("ramp", "")) == "rainbow"

    def by_value(row):
        v = row.get(column)
        if not _ok(v):
            return _MUTED
        t = 0.5 if hi <= lo else (float(v) - lo) / (hi - lo)
        return heat_hex(t) if rainbow else seq_hex(t)

    return by_value, [("%s %s" % (_fmt(lo), "→"), seq_hex(0.0)),
                      (_fmt(hi), heat_hex(1.0) if rainbow else seq_hex(1.0))]


def _radii(frame: Frame, column: str, style: Dict[str, Any]):
    """``一列 -> 半徑``。沒有大小角色就整組同一個。"""
    base = float(style.get("point_size", 2.6) or 2.6)
    if not column or column in CATEGORY_COLUMNS:
        return lambda _row: base
    vals = frame.values(column)
    lo, hi = (min(vals), max(vals)) if vals else (0.0, 0.0)

    def at(row):
        v = row.get(column)
        if not _ok(v) or hi <= lo:
            return base
        # **面積跟著值走，不是半徑** —— 半徑線性放大時，兩倍的值看起來是四倍。
        t = (float(v) - lo) / (hi - lo)
        return base * math.sqrt(0.25 + 3.75 * t)

    return at


# --------------------------------------------------------------------------- #
# 家具
# --------------------------------------------------------------------------- #
def _ticks(o: List[str], sx, sy, px: float, py: float, pw: float, ph: float,
           style: Dict[str, Any]) -> None:
    xt = sx.ticks(int(style.get("xticks", 5) or 5))
    if sx.kind == "linear":
        _xlabels(o, xt, lambda t: sx.at(t, px, px + pw) or px,
                 py + ph + 11, style)
    else:
        # ⚠ **類別軸不能走 `_xlabels`** —— 那一支把刻度當數字格式化
        # （`_fmt`），而一個區域名餵進去是一句看不懂的 TypeError。
        # 兩條軸都要問 scale 自己的 `label`，這是 band 軸的整個重點。
        size, weight, ink = _text_attrs(style, "tick", _TEXT)
        for t in xt:
            x = sx.at(t, px, px + pw)
            if x is None:
                continue
            o.append("<text x='%.1f' y='%.1f' font-size='%g' font-weight='%s' "
                     "fill='%s' text-anchor='middle'>%s</text>"
                     % (x, py + ph + 11 + size * 0.5, size, weight, ink,
                        _esc(sx.label(t))))
    yt = sy.ticks(int(style.get("yticks", 5) or 5))
    if sy.kind == "linear":
        # ⚠ 這一支要寬度（它順手畫格線）—— 少一個引數的話 `w`
        # 會收到 style 那個 dict，而症狀是一句看不懂的 TypeError。
        _ylabels(o, yt, sy.lo, sy.hi, px, py, ph, pw, style)
    else:
        size, weight, ink = _text_attrs(style, "tick", _TEXT)
        for t in yt:
            y = sy.at(t, py + ph, py)
            if y is None:
                continue
            o.append("<text x='%.1f' y='%.1f' font-size='%g' font-weight='%s' "
                     "fill='%s' text-anchor='end'>%s</text>"
                     % (px - 6, y + size * 0.35, size, weight, ink,
                        _esc(sy.label(t))))


def _legend(o: List[str], legend: Sequence[Tuple[str, str]], x: float,
            y: float, style: Dict[str, Any]) -> None:
    """**兩群以上一定有圖例**（顏色不能是唯一的身分線索）。"""
    size, weight, ink = _text_attrs(style, "tick", _MUTED)
    at = float(x)
    for name, colour in legend:
        o.append("<rect x='%.1f' y='%.1f' width='8' height='8' fill='%s'/>"
                 % (at, y - 7, colour))
        o.append("<text x='%.1f' y='%.1f' font-size='%g' font-weight='%s' "
                 "fill='%s'>%s</text>"
                 % (at + 11, y, size, weight, ink, _esc(name)))
        at += 11 + 7.0 + size * 0.62 * max(4, len(str(name)))
