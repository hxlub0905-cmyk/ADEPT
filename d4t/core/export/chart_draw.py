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

    drawer = _MARKS.get(str(sp["mark"]))
    if drawer is None:
        # 封閉字彙（`chart_spec.MARKS`）—— 走到這裡表示有人加了一種 mark 卻沒
        # 有在這裡畫它，而那要說出來，不是畫一張空白。有一條測試對著這件事。
        return _empty(width, height,
                      "nothing here can draw a '%s'" % sp["mark"])
    return drawer(frame, sp, st, int(width), int(height))


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
        # ⚠ **整欄都是數字的話照數字排。** 長條圖把一條數值軸當槽用時，
        # 「第一次出現的順序」是長表的列序 —— 於是 125 那根會落在 115 左邊，
        # 而那張圖看起來完全正常。名字那一種沒有這個問題（也沒有正確的排法，
        # 所以照接線的順序）。
        self.numeric = bool(seen) and all(_ok(v) for v in seen)
        if self.numeric:
            seen.sort(key=float)
        self.slots = seen or [""]

    def at(self, value: Any, a: float, b: float) -> Optional[float]:
        s = "" if value is None else str(value)
        if s not in self.slots:
            return None
        step = (b - a) / float(len(self.slots))
        return a + step * (self.slots.index(s) + 0.5)

    #: 超過這麼多槽就開始跳著標。**槽照樣是全部**（記號一個都不少），
    #: 少的只是標籤 —— 18 個標籤擠在 580 px 上會疊成一條看不懂的黑線，
    #: 而那正是 render 出來才看到的（F88 ③）。
    LABEL_ALL_UPTO = 12

    def ticks(self, want: int) -> List[str]:
        n = len(self.slots)
        if n <= max(self.LABEL_ALL_UPTO, int(want)):
            return list(self.slots)
        step = int(math.ceil(n / float(max(2, int(want)))))
        return [self.slots[i] for i in range(0, n, step)]

    def label(self, t: Any) -> str:
        # 整欄都是數字的話照數字印 —— `str(114.81174999999998)` 不是一個
        # 使用者看得懂的刻度（`_fmt` 是四張老圖用的同一支）。
        return _fmt(float(t)) if self.numeric else str(t)


def _scale(frame: Frame, column: str, lo_hi=None, band: bool = False):
    """一欄 → 一支 scale。**類別欄走 band，其餘走 linear。**

    ``band=True`` 是長條圖用的：長條有寬度，而寬度在連續軸上沒有意義
    （兩個很近的值會疊在一起，看起來像一根特別粗的）。
    """
    if band or str(column) in CATEGORY_COLUMNS:
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
    """一格框一個記號。"""
    plot = _Plot(frame, sp, style, width, height)
    radius_of = _radii(frame, str(sp.get("size") or ""), style)
    filled = bool(style.get("point_fill"))
    line_w = float(style.get("line_width", 1.6) or 1.6) / 1.6

    for row in frame.rows:
        x, y = plot.x_at(row), plot.y_at(row)
        if x is None or y is None:
            continue                    # **算不出來的那一格不畫**（不是畫在 0）
        ink = plot.colour_of(row)
        face = ("fill='%s'" % ink) if filled else "fill='none'"
        plot.out.append("<circle cx='%.1f' cy='%.1f' r='%.2f' %s stroke='%s' "
                        "stroke-width='%.1f'/>"
                        % (x, y, radius_of(row), face, ink, max(0.6, line_w)))
    return plot.finish()


# --------------------------------------------------------------------------- #
# 三種 mark 共用的那一半 —— **版面只有一份**
# --------------------------------------------------------------------------- #
class _Plot(object):
    """圖區、兩支 scale、顏色、外框與刻度 —— 每一種 mark 都要的那一組。

    ⚠ 各寫一份的下場這個 repo 很熟：三張圖的留白差幾個 px，並排在同一頁上
    看起來像三種東西；而「刻度畫在記號之前」那條規矩只要漏掉一次，格線就會
    從資料上壓過去。所以它只有這一份。
    """

    def __init__(self, frame: Frame, sp: Dict[str, Any],
                 style: Dict[str, Any], width: int, height: int,
                 band_x: bool = False) -> None:
        self.frame, self.sp, self.style = frame, sp, style
        self.width, self.height = width, height
        self.colour_of, self.legend = _colours(
            frame, str(sp.get("color") or ""), style)

        self.pad_l, pad_r = 58, 18
        self.pad_t = 30 if style.get("title") else 14
        pad_b = 46 + (14 if self.legend else 0)
        self.pw = max(60, width - self.pad_l - pad_r)
        self.ph = max(60, height - self.pad_t - pad_b)

        # **鎖定的是「值那一軸」，而在這張圖上那是 Y。** X 也是一個統計量，
        # 但同一組鎖定範圍套到兩條意思不同的軸上會把圖擠成一條線 —— 兩批要
        # 並排比的時候，鎖住 Y 就夠了（同 `_span` 那條「鎖住的照鎖的」）。
        self.sx = _scale(frame, sp["x"], band=band_x)
        self.sy = _scale(frame, sp["y"], style.get("vlock"))

        self.out = _head(width, height, str(style.get("title") or ""))
        _frame(self.out, self.pad_l, self.pad_t, self.pw, self.ph)
        # ⚠ **刻度先畫**：`_ylabels` 順手畫橫格線，而格線是背景 —— 畫在記號
        # 之後會從記號上壓過去（`_svg_profile` 也是這個順序）。
        _ticks(self.out, self.sx, self.sy, self.pad_l, self.pad_t,
               self.pw, self.ph, style)

    def x_at(self, row: Dict[str, Any]) -> Optional[float]:
        return self.sx.at(row.get(self.sp["x"]), self.pad_l,
                          self.pad_l + self.pw)

    def y_at(self, row: Dict[str, Any]) -> Optional[float]:
        # Y 由下往上
        return self.sy.at(row.get(self.sp["y"]), self.pad_t + self.ph,
                          self.pad_t)

    def finish(self) -> str:
        _axis_names(self.out, self.style, self.width, self.height,
                    self.pad_l, self.pad_t, self.pw, self.ph,
                    str(self.sp["x"]), str(self.sp["y"]))
        if self.legend:
            _legend(self.out, self.legend, self.pad_l, self.height - 8,
                    self.style)
        self.out.append("</svg>")
        return "".join(self.out)


def _by_colour(frame: Frame, sp: Dict[str, Any]) -> List[List[Dict[str, Any]]]:
    """照顏色那一欄把列分群（沒有顏色角色就是一群）。

    ⚠ **群的順序是值第一次出現的順序** —— 跟 `_Band` 的槽、跟圖例一樣。
    三個地方講同一件事的時候，順序也該是同一個。
    """
    column = str(sp.get("color") or "")
    if not column:
        return [list(frame.rows)]
    order: List[str] = []
    groups: Dict[str, List[Dict[str, Any]]] = {}
    for row in frame.rows:
        key = "" if row.get(column) is None else str(row.get(column))
        if key not in groups:
            order.append(key)
            groups[key] = []
        groups[key].append(row)
    return [groups[k] for k in order]


# --------------------------------------------------------------------------- #
# mark：line
# --------------------------------------------------------------------------- #
def _lines(frame: Frame, sp: Dict[str, Any], style: Dict[str, Any],
           width: int, height: int) -> str:
    """一群一條折線 —— 「一列一條線」就是 `Colour = row`（計畫書 §9-2）。"""
    plot = _Plot(frame, sp, style, width, height)
    line_w = max(0.6, float(style.get("line_width", 2.0) or 2.0))
    dots = bool(style.get("points", True))
    radius = float(style.get("point_size", 2.6) or 2.6)
    filled = bool(style.get("point_fill"))

    for group in _by_colour(frame, sp):
        pts = []
        for row in group:
            x, y = plot.x_at(row), plot.y_at(row)
            if x is None or y is None:
                continue        # **算不出來的那一格不畫**（不是畫在 0）
            pts.append((x, y, row))
        if not pts:
            continue
        # ⚠ **照 X 排過才連** —— 長表的列序是「哪個區域的第幾格框」，照那個
        # 順序連起來的話，線會在圖上來回折，而那是一團看起來有意義的雜訊。
        pts.sort(key=lambda t: t[0])
        ink = plot.colour_of(pts[0][2])
        if len(pts) > 1:
            plot.out.append(
                "<polyline points='%s' fill='none' stroke='%s' "
                "stroke-width='%.1f' stroke-linejoin='round'/>"
                % (" ".join("%.1f,%.1f" % (x, y) for x, y, _r in pts),
                   ink, line_w))
        if dots:
            face = ("fill='%s'" % ink) if filled else "fill='#fff'"
            for x, y, _r in pts:
                plot.out.append(
                    "<circle cx='%.1f' cy='%.1f' r='%.2f' %s stroke='%s' "
                    "stroke-width='%.1f'/>"
                    % (x, y, radius, face, ink, max(0.6, line_w * 0.75)))
    return plot.finish()


# --------------------------------------------------------------------------- #
# mark：bar
# --------------------------------------------------------------------------- #
#: 兩根長條之間留的底色縫（dataviz 的規矩：相鄰的填色之間要有 2px 的縫，
#: 不然兩根不同顏色的長條會讀成一塊）。
BAR_GAP = 2.0
#: 一個槽裡長條佔多寬（其餘是槽與槽之間的呼吸）。
BAR_SHARE = 0.72


def _bars(frame: Frame, sp: Dict[str, Any], style: Dict[str, Any],
          width: int, height: int) -> str:
    """一格框一根長條。同一個槽裡的**並排**，不疊。

    ⚠ **不疊，也不合併。** 疊起來的長條只有最底下那一段是從同一條基線量的，
    其餘幾段要讀的人自己減 —— 而這張圖問的正是「誰比較高」。合併（取平均）
    更糟：它會憑空生出一個使用者沒有要求的統計量，而圖上沒有任何線索說那一
    根是三格框的平均。

    所以同一個槽裡有幾格框就並排幾根。**每一根一樣寬**（寬度用整張圖最擠的
    那個槽算），不然寬度會讀成一種意思。第一版只照顏色分群並排，於是同一群
    裡落在同一個槽的三格框**疊在一起畫**，看起來剛好像一張堆疊長條圖 ——
    render 出來才看到的（F88 ③）。
    """
    # X 一律當**槽**：長條有寬度，而寬度在連續軸上沒有意義（兩個很近的值會
    # 疊在一起，看起來像一根特別粗的）。
    plot = _Plot(frame, sp, style, width, height, band_x=True)
    groups = _by_colour(frame, sp)

    # 槽 -> 落在它上面的那幾根（照顏色的群序，所以同一群永遠在同一邊）
    buckets: Dict[float, List[Dict[str, Any]]] = {}
    base = plot.pad_t + plot.ph
    for group in groups:
        for row in group:
            centre = plot.x_at(row)
            if centre is None or plot.y_at(row) is None:
                continue        # **算不出來的那一格不畫**（不是畫成 0 高）
            buckets.setdefault(round(centre, 3), []).append(row)
    if not buckets:
        return plot.finish()

    slots = max(1, len(plot.sx.slots))
    span = (plot.pw / float(slots)) * BAR_SHARE
    most = max(len(v) for v in buckets.values())
    each = max(1.0, (span - BAR_GAP * (most - 1)) / float(most))

    # 值是負的時候長條要從 0 長下去，所以基線是「0 落在哪」而不是圖區底部。
    zero = plot.sy.at(0.0, base, plot.pad_t)
    if zero is None or not (plot.pad_t <= zero <= base):
        zero = base

    fill = min(1.0, 0.55 * float(style.get("fill_strength", 1.0) or 1.0))
    for centre, rows in buckets.items():
        # 一個槽裡不滿 `most` 根的話**置中**，不要靠左（靠左的話同一個槽的
        # 長條會跟隔壁槽的對不齊，看起來像位置有意思）。
        run = len(rows) * each + BAR_GAP * (len(rows) - 1)
        left0 = centre - run / 2.0
        for i, row in enumerate(rows):
            y = plot.y_at(row)
            top, bottom = min(y, zero), max(y, zero)
            ink = plot.colour_of(row)
            plot.out.append(
                "<rect x='%.1f' y='%.1f' width='%.1f' height='%.1f' "
                "fill='%s' fill-opacity='%.2f' stroke='%s' "
                "stroke-width='1'/>"
                % (left0 + i * (each + BAR_GAP), top, each,
                   max(0.5, bottom - top), ink, fill, ink))
    return plot.finish()


#: ``mark -> 畫它的那一支``。**封閉字彙的另一半** —— `chart_spec.MARKS` 說
#: 有哪幾個字，這裡說每個字怎麼畫，而有一支測試問「兩邊有沒有對齊」。
_MARKS = {
    spec_mod.MARK_POINT: _points,
    spec_mod.MARK_LINE: _lines,
    spec_mod.MARK_BAR: _bars,
}


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
            # ⚠ **不准寫 `row.get(column) or ""`。** `row` / `col` 的第一格
            # 是 **0**，而 `0 or ""` 是 `""` —— 於是第 0 列拿不到自己的顏色，
            # 畫出來是灰的，而圖例上它有顏色。render 出來才看到的（F88 ③）。
            got = row.get(column)
            return mapping.get("" if got is None else str(got), other)

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
