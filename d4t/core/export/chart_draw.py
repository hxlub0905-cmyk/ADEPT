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
from .chart_frame import (
    COL_COL, COL_REGION, COL_ROW, COL_X, COLUMNS_FIXED, Frame,
)
from .uniformity_charts import (  # noqa: PLC2701 — 見檔頭：刻度只該有一份
    REGION_COLOURS, _axis_names, _empty, _esc, _fmt, _frame, _head,
    _is_dark, _mark_colour, _nice_ticks, _opacity, _span, _text_attrs,
    _xlabels, _ylabels, draw_refs, fill_attrs, heat_hex, seq_hex,
)

__all__ = ["draw", "PRESETS", "preset_spec", "metric_columns"]

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

    if sp.get(spec_mod.ROLE_FACET):
        return _facets(frame, sp, st, int(width), int(height))
    drawer = _MARKS.get(str(sp["mark"]))
    if drawer is None:
        # 封閉字彙（`chart_spec.MARKS`）—— 走到這裡表示有人加了一種 mark 卻沒
        # 有在這裡畫它，而那要說出來，不是畫一張空白。有一條測試對著這件事。
        return _empty(width, height,
                      "nothing here can draw a '%s'" % sp["mark"])
    return drawer(frame, sp, st, int(width), int(height))


# --------------------------------------------------------------------------- #
# 預設 —— **打開時不准是一片空白**（計畫書 §5）
# --------------------------------------------------------------------------- #
#: 「這一欄是使用者量出來的統計量」的佔位符。哪一欄要有**資料**才知道
#: （欄名跟著量測卡走），所以預設存的是佔位符，`preset_spec` 才把它換掉。
METRIC, METRIC2 = "@metric", "@metric2"

#: ``(名字, 一句白話, spec 樣板)``。**順序就是畫面上由左到右的順序。**
#:
#: 為什麼要有這個東西：graph builder 最容易讓不寫 code 的人卡住的就是
#: 「面前一張白紙」（推廣鐵則）。所以打開一定落在一個**看得懂名字**的組合
#: 上，使用者從那裡開始改 —— JMP 自己也是這樣。
#:
#: ⚠ **這跟「拿第一欄當預設」是兩回事**（F88 第二刀刻意不做的那件）。那個是
#: 隨便挑一欄，畫出來是一團疊在同一點的圓、而且看起來像設定好了；這個是一張
#: **有名字、有意思**的圖，而名字就寫在那顆膠囊上。
#:
#: ⚠ **`Histogram` 不在這裡**：直方圖要先分箱再數個數，而長表上沒有「幾個」
#: 那一欄 —— 那是資料轉換，不是一種記號（同 §14.1 的結論）。
PRESETS: Tuple[Tuple[str, str, Dict[str, str]], ...] = (
    ("Two numbers", "Do these two move together?",
     {"mark": spec_mod.MARK_POINT, "x": METRIC, "y": METRIC2,
      "color": COL_REGION}),
    ("Across the image", "Is the field tilted from one side to the other?",
     {"mark": spec_mod.MARK_POINT, "x": COL_X, "y": METRIC,
      "color": COL_REGION}),
    ("Spread per region", "How spread out is each region?",
     {"mark": spec_mod.MARK_BOX, "x": COL_REGION, "y": METRIC}),
    ("Row by row", "One line per row of boxes.",
     {"mark": spec_mod.MARK_LINE, "x": COL_X, "y": METRIC,
      "color": COL_ROW}),
    ("Where it is uneven", "A cell per box, coloured by the value.",
     {"mark": spec_mod.MARK_CELL, "x": COL_COL, "y": COL_ROW,
      "color": METRIC}),
)


def metric_columns(frame: Optional[Frame]) -> List[str]:
    """使用者**量出來**的那幾欄（不含位置與大小那幾格幾何欄）。

    ⚠ 幾何欄（`x`/`y`/`w`/`h`/`box`）是數字，但它們不是「量出來的東西」——
    一個預設把 `w` 放到 Y 軸上，讀起來像是在問「框有多寬」，而那不是任何人
    的問題。
    """
    if frame is None:
        return []
    return [c for c in frame.numeric_columns() if c not in COLUMNS_FIXED]


def preset_spec(name: str, frame: Optional[Frame]) -> str:
    """一個預設的名字 ＋ 這一顆的長表 → 一份**填好欄名**的 spec 字串。

    佔位符換不掉（那一顆沒有量出任何統計量）就回空字串 —— 一份指著不存在的
    欄的 spec 會畫出一句「no column called '@metric'」，那比空的更難懂。
    """
    for got, _why, template in PRESETS:
        if got != str(name):
            continue
        mine = metric_columns(frame)
        if not mine:
            return ""
        out: Dict[str, str] = {}
        for key, value in template.items():
            if value == METRIC:
                value = mine[0]
            elif value == METRIC2:
                # 只有一個統計量的時候「兩個數字」退回跟位置比 —— 同一欄畫
                # 兩次得到的是一條 45° 直線，那張圖看起來像壞了。
                value = mine[1] if len(mine) > 1 else COL_X
            out[key] = value
        return spec_mod.format_spec(out)
    return ""


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


class _Log(object):
    """對數軸（F89-5）。**零與負值沒有位置，所以那幾格不畫。**

    ⚠ 畫在軸底的話讀起來是「它很小」，而真相是「它畫不出來」—— 那兩件事在
    一張缺陷尺寸圖上差很多。跳過幾格由 :attr:`dropped` 說出來，呼叫端把它
    寫在軸名旁邊。
    """

    kind = "linear"          # 對外它就是一條連續軸（`_ticks` 走同一條路）

    def __init__(self, values: Sequence[Any], lo_hi=None) -> None:
        good = [float(v) for v in values if _ok(v) and float(v) > 0.0]
        self.dropped = sum(1 for v in values if _ok(v) and float(v) <= 0.0)
        lo, hi = _span(good, lo_hi)
        # 鎖定的範圍也可能帶進一個 <= 0 的下界 —— 那時候退到最小的正值。
        if lo <= 0:
            lo = min(good) if good else 1.0
        if hi <= lo:
            hi = lo * 10.0
        self.lo, self.hi = float(lo), float(hi)
        self._llo, self._lhi = math.log10(self.lo), math.log10(self.hi)

    def at(self, value: Any, a: float, b: float) -> Optional[float]:
        if not _ok(value) or float(value) <= 0.0:
            return None
        span = (self._lhi - self._llo) or 1.0
        return a + (math.log10(float(value)) - self._llo) / span * (b - a)

    def ticks(self, want: int) -> List[float]:
        """**整數次方**（1, 10, 100…）—— 那才是讀 log 軸的方式。

        跨不到兩個數量級的時候補上 2 與 5 那兩檔，不然整張圖只剩一兩個刻度。
        """
        first, last = int(math.floor(self._llo)), int(math.ceil(self._lhi))
        out: List[float] = []
        steps = (1, 2, 5) if (last - first) <= 2 else (1,)
        for p in range(first, last + 1):
            for m in steps:
                v = m * (10.0 ** p)
                if self.lo <= v <= self.hi:
                    out.append(v)
        return out or [self.lo, self.hi]

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


def _scale(frame: Frame, column: str, lo_hi=None, band: bool = False,
           log: bool = False):
    """一欄 → 一支 scale。**類別欄走 band，其餘走 linear。**

    ``band=True`` 是長條圖用的：長條有寬度，而寬度在連續軸上沒有意義
    （兩個很近的值會疊在一起，看起來像一根特別粗的）。
    """
    # ⚠ **問這一張表**，不是問模組層那張清單 —— 「哪幾欄是類別」是每一張表
    # 自己的事（`Frame.categories`）。第二張表（一列一顆 defect）的 `die_x`
    # 走錯的話，「第 3 欄的 die 比第 1 欄大兩欄」會被畫成一條連續軸。
    if band or str(column) in frame.categories:
        return _Band(frame.column(column))
    if log:
        return _Log(frame.column(column), lo_hi)
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
            width: int, height: int, scale_frame: Optional[Frame] = None
            ) -> str:
    """一格框一個記號。"""
    plot = _Plot(frame, sp, style, width, height, scale_frame=scale_frame)
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


def _sort_slots(plot: "_Plot", frame: Frame, sp: Dict[str, Any],
                style: Dict[str, Any]) -> None:
    """把槽照**值**重排（F89-5 的 `slot_order`）。

    「誰最差」在一排沒排過的長條裡要用眼睛找；排過之後那是第一眼。

    ⚠ **只有長條與盒鬚**（呼叫端給 `sortable=True`）。散佈圖與折線排過之後
    X 軸不再是那一欄的值，那是說謊；格子排過之後 wafer map 的兩條軸會被打亂，
    而那張圖的整個意思就是「哪一格在哪裡」。第一版把它放在 `_Plot` 裡對**所有**
    band 軸生效，而 `CUSTOM_BY_MARK` 的雙向測試當場說「表上說不讀，實際上讀
    了」。

    ⚠ 一個槽上有好幾格框的時候照**中位數**排。用平均的話一顆離群點會把整根
    拉走，而排序要回答的是「這一群典型上多高」。

    ⚠ **沒有值的槽排最後** —— 它不是「最小的那一個」，它是「沒有量到」。
    """
    order = str(style.get("slot_order", "") or "")
    if order not in ("asc", "desc") or plot.sx.kind != "band":
        return
    mid: Dict[str, float] = {}
    for slot in plot.sx.slots:
        got = sorted(float(r[sp["y"]]) for r in frame.rows
                     if str(r.get(sp["x"], "")) == slot
                     and _ok(r.get(sp["y"])))
        if got:
            mid[slot] = got[len(got) // 2]
    plot.sx.slots = sorted(
        plot.sx.slots,
        key=lambda s: (s not in mid,
                       (mid.get(s, 0.0) if order == "asc"
                        else -mid.get(s, 0.0))))


#: 一張圖最多切成幾格。**不是技術限制** —— 16 格之後每一格只剩 150 px，
#: 而那時候該做的是先篩一輪，不是把它們全部塞進一張圖。
MAX_FACETS = 16

#: 一格小圖再小就沒有意義了（軸名與刻度已經占掉大半）。
MIN_PANEL = 150


def _facets(frame: Frame, sp: Dict[str, Any], style: Dict[str, Any],
            width: int, height: int) -> str:
    """一欄的每一個值一張小圖，**共用同一組座標軸**（F89-5）。

    為什麼共用座標軸是重點
    ----------------------
    分開畫的四張圖各自縮放，於是**一樣高的柱子其實不一樣高** —— 那正是
    `lock` 那一格存在的理由，而分面把它變成不必想的事：這裡每一格的兩條軸
    都是用**整張表**算的（`scale_frame`），只有記號是那一格自己的。

    ⚠ 一張小圖是一個**巢狀 `<svg>`**，所以外面看到的仍然是一張圖、一個檔 ——
    F88 §8 當初不做分面的理由（「版面、匯出、報表都要跟著改」）因此沒有發生。

    ⚠ **值的順序是第一次出現的順序**（同 `_Band` 的槽、同圖例）。
    """
    column = str(sp.get(spec_mod.ROLE_FACET) or "")
    seen: List[str] = []
    for v in frame.column(column):
        got = "" if v is None else str(v)
        if got not in seen:
            seen.append(got)
    if not seen:
        return _empty(width, height, "no column called '%s'" % column)
    if len(seen) > MAX_FACETS:
        return _empty(width, height,
                      "that is %d panels; %d is the most that stays readable "
                      "- filter first, or drop the split" % (len(seen),
                                                             MAX_FACETS))

    cols = int(math.ceil(math.sqrt(len(seen))))
    rows = int(math.ceil(len(seen) / float(cols)))
    pw = max(MIN_PANEL, int(width // cols))
    ph = max(MIN_PANEL, int(height // rows))

    inner = dict(sp)
    inner.pop(spec_mod.ROLE_FACET, None)
    o = ["<svg xmlns='http://www.w3.org/2000/svg' width='%d' height='%d' "
         "viewBox='0 0 %d %d'><rect width='%d' height='%d' fill='#fff'/>"
         % (width, height, width, height, width, height)]
    for i, value in enumerate(seen):
        part = Frame([c for c in frame.columns],
                     [r for r in frame.rows
                      if ("" if r.get(column) is None
                          else str(r.get(column))) == value],
                     categories=frame.categories, labels=frame.labels)
        one = dict(style)
        # 每一格的標題是**那個值**（"epi" / "bin 2"）—— 整張圖的標題只印一次，
        # 在最上面那一格上會跟值打架。
        one["title"] = value or "(blank)"
        # ⚠ **圖例只印一次。** 每一格各印一份的話，同一組顏色在一頁上被講了
        # 四遍，而那幾行字佔的正是小圖最缺的高度（render 出來才看到的）。
        one["_no_legend"] = i > 0
        drawer = _MARKS.get(str(sp["mark"]))
        panel = drawer(part, inner, one, pw, ph, scale_frame=frame)
        # ⚠ **`<g transform>`，不是巢狀 `<svg>`。** 巢狀 `<svg>` 是合法的
        # SVG 1.1，而且瀏覽器開得起來 —— 但 Qt 的 renderer 走 **Svg Tiny
        # 1.2**，那一版沒有巢狀 `<svg>`，它會**整塊跳過**：於是寫出去的檔案
        # 是對的、Studio 裡的預覽是一片空白。那正好打破這整個功能的不變量
        # （「畫面上的圖跟寫出去的逐位元組相同」），而且是最壞的那個方向 ——
        # 檔案對、畫面錯。render 出來才看到的。
        o.append("<g transform='translate(%d,%d)'>%s</g>"
                 % ((i % cols) * pw, (i // cols) * ph,
                    panel[panel.index(">") + 1:-len("</svg>")]))
    o.append("</svg>")
    return "".join(o)


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
                 band_x: bool = False, band_y: bool = False,
                 sortable: bool = False,
                 scale_frame: Optional[Frame] = None) -> None:
        self.frame, self.sp, self.style = frame, sp, style
        # ⚠ **座標軸從哪一張表算**：分面時是**整張**表，記號才是這一格自己的
        # （`_facets`）。分開算的話每一格各自縮放，於是一樣高的柱子其實不一樣
        # 高 —— 而那正是分面比「四張分開的圖」強的地方。
        scale_frame = frame if scale_frame is None else scale_frame
        self.width, self.height = width, height
        # 顏色也要跨格一致 —— 同一個區域在第一格是綠的、在第三格變成琥珀色
        # 的話，那一頁沒有人讀得動。
        self.colour_of, self.legend = _colours(
            scale_frame, str(sp.get("color") or ""), style)

        self.pad_l, pad_r = 58, 18
        self.pad_t = 30 if style.get("title") else 14
        if style.get("_no_legend"):
            self.legend = []          # 分面時只有第一格印（見 `_facets`）
        pad_b = 46 + (14 if self.legend else 0)
        self.pw = max(60, width - self.pad_l - pad_r)
        self.ph = max(60, height - self.pad_t - pad_b)

        # **鎖定的是「值那一軸」，而在這張圖上那是 Y。** X 也是一個統計量，
        # 但同一組鎖定範圍套到兩條意思不同的軸上會把圖擠成一條線 —— 兩批要
        # 並排比的時候，鎖住 Y 就夠了（同 `_span` 那條「鎖住的照鎖的」）。
        self.sx = _scale(scale_frame, sp["x"], band=band_x)
        self.sy = _scale(scale_frame, sp["y"], style.get("vlock"),
                         band=band_y,
                         log=str(style.get("yscale", "")) == "log")
        # ⚠ **重排要在畫刻度之前。** 第一版在 `_bars` 裡才排，而 `_ticks`
        # 已經在這個建構子裡跑過了 —— 於是長條照新順序擺、標籤照舊順序印，
        # 兩邊對不起來。那比不排序糟得多：它畫得出來，而且是錯的。
        if sortable:
            _sort_slots(self, scale_frame, sp, style)

        self.out = _head(width, height, str(style.get("title") or ""))
        _frame(self.out, self.pad_l, self.pad_t, self.pw, self.ph)
        # ⚠ **刻度先畫**：`_ylabels` 順手畫橫格線，而格線是背景 —— 畫在記號
        # 之後會從記號上壓過去（`_svg_profile` 也是這個順序）。
        _ticks(self.out, self.sx, self.sy, self.pad_l, self.pad_t,
               self.pw, self.ph, style)
        # 規格線 —— **跟四張預設圖同一支**（`draw_refs`）。畫在記號之前：
        # 它是背景上的一條參考，不是資料。
        #
        # ⚠ 只有**數值軸**畫得出來。Y 是類別（band）的時候「132 在哪裡」沒有
        # 答案 —— 那時候一條線不畫，比畫在一個猜出來的位置好。
        if self.sy.kind == "linear":
            draw_refs(self.out, style, self.sy.lo, self.sy.hi, self.pad_l,
                      self.pad_t, self.pw, self.ph)

    def x_at(self, row: Dict[str, Any]) -> Optional[float]:
        return self.sx.at(row.get(self.sp["x"]), self.pad_l,
                          self.pad_l + self.pw)

    def y_at(self, row: Dict[str, Any]) -> Optional[float]:
        # Y 由下往上
        return self.sy.at(row.get(self.sp["y"]), self.pad_t + self.ph,
                          self.pad_t)

    def finish(self) -> str:
        # ⚠ **跳過幾格要說出來。** log 軸畫不了 0 與負值，而一張安靜少了三顆
        # 點的圖，跟一張本來就只有那幾顆的圖長得一模一樣。
        ylab = str(self.sp["y"])
        if getattr(self.sy, "dropped", None) is not None:
            skipped = int(self.sy.dropped or 0)
            ylab = ("%s (log; %d not shown, zero or below)" % (ylab, skipped)
                    if skipped else "%s (log)" % ylab)
        _axis_names(self.out, self.style, self.width, self.height,
                    self.pad_l, self.pad_t, self.pw, self.ph,
                    str(self.sp["x"]), ylab)
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
           width: int, height: int, scale_frame: Optional[Frame] = None
           ) -> str:
    """一群一條折線 —— 「一列一條線」就是 `Colour = row`（計畫書 §9-2）。"""
    plot = _Plot(frame, sp, style, width, height, scale_frame=scale_frame)
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
          width: int, height: int, scale_frame: Optional[Frame] = None
          ) -> str:
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
    plot = _Plot(frame, sp, style, width, height, band_x=True, sortable=True,
                 scale_frame=scale_frame)
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

    for centre, rows in buckets.items():
        # 一個槽裡不滿 `most` 根的話**置中**，不要靠左（靠左的話同一個槽的
        # 長條會跟隔壁槽的對不齊，看起來像位置有意思）。
        run = len(rows) * each + BAR_GAP * (len(rows) - 1)
        left0 = centre - run / 2.0
        for i, row in enumerate(rows):
            y = plot.y_at(row)
            top, bottom = min(y, zero), max(y, zero)
            ink = plot.colour_of(row)
            # ⚠ **走 `fill_attrs`**（柱子／盒子／實心記號共用的那一支）。
            # 第一版在這裡自己乘了一次 `fill_strength`，於是 `fill_color`
            # 對長條完全沒有作用 —— 而編輯器照樣把那一列顯示出來。
            # `CUSTOM_BY_MARK` 那條雙向測試抓到的。
            fill, alpha = fill_attrs(style, ink, 0.55)
            plot.out.append(
                "<rect x='%.1f' y='%.1f' width='%.1f' height='%.1f' "
                "fill='%s' fill-opacity='%s' stroke='%s' "
                "stroke-width='1'/>"
                % (left0 + i * (each + BAR_GAP), top, each,
                   max(0.5, bottom - top), fill, _opacity(alpha), ink))
    return plot.finish()


# --------------------------------------------------------------------------- #
# mark：box
# --------------------------------------------------------------------------- #
def _boxes(frame: Frame, sp: Dict[str, Any], style: Dict[str, Any],
           width: int, height: int, scale_frame: Optional[Frame] = None
           ) -> str:
    """一個槽一個盒子 —— 中間那一半、中位數、鬚。

    ⚠ **統計走 `boxplot.box_stats`，不在這裡再算一次。** 那一支已經定死了
    「鬚的端點是落在 1.5×IQR 之內的**真實資料點**，不是算出來的柵欄」——
    差別在圖上看得見（後者會畫出一條伸進沒有資料的地方的鬚）。各算一份的
    那天，同一份報表裡兩張盒鬚圖的鬚會不一樣長。
    """
    from .boxplot import box_stats

    plot = _Plot(frame, sp, style, width, height, band_x=True, sortable=True,
                 scale_frame=scale_frame)
    groups = _by_colour(frame, sp)

    # 槽 -> 那個槽上的那幾個盒子（照顏色的群序）
    buckets: Dict[float, List[Tuple[List[float], Dict[str, Any]]]] = {}
    for group in groups:
        by_slot: Dict[float, List[Dict[str, Any]]] = {}
        for row in group:
            centre = plot.x_at(row)
            if centre is None or not _ok(row.get(sp["y"])):
                continue        # **算不出來的那一格不畫**
            by_slot.setdefault(round(centre, 3), []).append(row)
        for centre, rows in by_slot.items():
            buckets.setdefault(centre, []).append(
                ([float(r[sp["y"]]) for r in rows], rows[0]))
    if not buckets:
        return plot.finish()

    slots = max(1, len(plot.sx.slots))
    span = (plot.pw / float(slots)) * BAR_SHARE
    most = max(len(v) for v in buckets.values())
    each = max(1.0, (span - BAR_GAP * (most - 1)) / float(most))
    line_w = float(style.get("line_width", 1.2) or 1.2)
    whiskers = bool(style.get("whiskers", True))
    # ⚠ **預設跟其他記號同一個**（`chart_style.DEFAULTS["points"]` 是 True）。
    # 第一版在這裡寫死 `False`，於是同一個開關對折線有作用、對盒子沒有 ——
    # 而編輯器照樣把那一列顯示出來。`CUSTOM_BY_MARK` 那條雙向測試抓到的。
    dots = bool(style.get("points", True))
    radius = float(style.get("point_size", 2.2) or 2.2)

    def at(v: float) -> Optional[float]:
        return plot.sy.at(v, plot.pad_t + plot.ph, plot.pad_t)

    for centre, entries in buckets.items():
        run = len(entries) * each + BAR_GAP * (len(entries) - 1)
        left0 = centre - run / 2.0
        for i, (values, row) in enumerate(entries):
            st = box_stats(values)
            if not st:
                continue
            ink = plot.colour_of(row)
            fill, alpha = fill_attrs(style, ink, 0.18)
            left = left0 + i * (each + BAR_GAP)
            mid = left + each / 2.0
            q1, q3, med = at(st["q1"]), at(st["q3"]), at(st["med"])
            if q1 is None or q3 is None or med is None:
                continue
            top, bottom = min(q1, q3), max(q1, q3)
            if whiskers:
                lo, hi = at(st["lo"]), at(st["hi"])
                if lo is not None and hi is not None:
                    plot.out.append(
                        "<path d='M%.1f %.1fV%.1fM%.1f %.1fH%.1fM%.1f %.1fH%.1f'"
                        " stroke='%s' stroke-width='%.1f' fill='none'/>"
                        % (mid, lo, hi, left + each * 0.25, lo,
                           left + each * 0.75, left + each * 0.25, hi,
                           left + each * 0.75, ink, line_w))
            plot.out.append(
                "<rect x='%.1f' y='%.1f' width='%.1f' height='%.1f' fill='%s' "
                "fill-opacity='%s' stroke='%s' stroke-width='%.1f'/>"
                % (left, top, each, max(0.5, bottom - top), fill,
                   _opacity(alpha), ink, line_w))
            plot.out.append(
                "<line x1='%.1f' y1='%.1f' x2='%.1f' y2='%.1f' stroke='%s' "
                "stroke-width='%.1f'/>"
                % (left, med, left + each, med, ink, line_w * 1.6))
            if dots:
                for v in values:
                    y = at(v)
                    if y is not None:
                        plot.out.append(
                            "<circle cx='%.1f' cy='%.1f' r='%.2f' fill='none' "
                            "stroke='%s' stroke-width='0.8'/>"
                            % (mid, y, radius, ink))
    return plot.finish()


# --------------------------------------------------------------------------- #
# mark：cell
# --------------------------------------------------------------------------- #
def _cells(frame: Frame, sp: Dict[str, Any], style: Dict[str, Any],
           width: int, height: int, scale_frame: Optional[Frame] = None
           ) -> str:
    """一格一個色塊 —— **熱圖，但兩條軸是你自己挑的**。

    ⚠ 兩條軸都當**槽**（每一格一樣大、鋪滿圖區）。那是熱圖預設的樣子，
    理由寫在 `heat_lattice`：照實鋪的話「間距不平均、或少了一格，相鄰兩格的
    面積就明顯不一樣」，而面積不是這張圖在量的東西。

    ⚠ 顏色走的是**跟熱圖同一條色階**（`ramp` 那一格同時管兩邊）—— 兩張圖
    並排時同一個顏色要是同一個意思。
    """
    column = str(sp.get("color") or "")
    plot = _Plot(frame, sp, style, width, height, band_x=True, band_y=True,
                 scale_frame=scale_frame)
    vals = (scale_frame or frame).values(column)
    lo, hi = _span(vals, style.get("hlock"))
    rainbow = str(style.get("ramp", "")) == "rainbow"
    show = bool(style.get("map_values"))

    nx = max(1, len(plot.sx.slots))
    ny = max(1, len(plot.sy.slots))
    cw, ch = plot.pw / float(nx), plot.ph / float(ny)
    size, _weight, _ink = _text_attrs(style, "tick", _TEXT)

    for row in frame.rows:
        cx, cy = plot.x_at(row), plot.y_at(row)
        v = row.get(column)
        if cx is None or cy is None or not _ok(v):
            continue            # **算不出來的那一格不畫**（留白，不是畫成 0）
        t = 0.5 if hi <= lo else (float(v) - lo) / (hi - lo)
        ink = heat_hex(t) if rainbow else seq_hex(t)
        plot.out.append(
            "<rect x='%.2f' y='%.2f' width='%.2f' height='%.2f' fill='%s'/>"
            % (cx - cw / 2.0, cy - ch / 2.0, cw, ch, ink))
        if show and cw >= 34 and ch >= 14:
            # **放得下才印**（印一半的數字比不印糟）—— 門檻、字重、以及
            # 「淺底印深字、深底印白字」那條規則**全部跟熱圖同一份**
            # （`_svg_map` ＋ `_is_dark`）。第一版在這裡自己寫了一條
            # `t > 0.55`，那就是同一句話長出兩種意思的起點。
            #
            # ⚠ 那條規則在色階中段**碰得到 3.2:1**（單色階 t≈0.49）——
            # 印在連續色階上的字本來就到不了 4.5:1。這裡不另外救它：色條是
            # 那張圖的尺，而 `boxes.csv` 是那份表。兩者都在。
            plot.out.append(
                "<text x='%.2f' y='%.2f' font-size='%g' font-weight='700' "
                "fill='%s' text-anchor='middle'>%s</text>"
                % (cx, cy + size * 0.35, min(size, ch * 0.5),
                   "#ffffff" if _is_dark(ink) else "#1f2430",
                   _esc(_fmt(float(v)))))
    return plot.finish()


#: ``mark -> 畫它的那一支``。**封閉字彙的另一半** —— `chart_spec.MARKS` 說
#: 有哪幾個字，這裡說每個字怎麼畫，而有一支測試問「兩邊有沒有對齊」。
_MARKS = {
    spec_mod.MARK_POINT: _points,
    spec_mod.MARK_LINE: _lines,
    spec_mod.MARK_BAR: _bars,
    spec_mod.MARK_BOX: _boxes,
    spec_mod.MARK_CELL: _cells,
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

    if column in frame.categories:
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
    if not column or column in frame.categories:
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
