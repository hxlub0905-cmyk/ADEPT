# -*- coding: utf-8 -*-
# d4t uniformity charts — authored 2026-09-07 (F85).
"""這一群框的四種看法 → 四張圖（**手寫 SVG，零新相依**）。

PEAR 的 Analysis 視窗有四種圖，而它們回答的是四句不同的話：

==============  ==========  ==========  ==================================
值              X 軸        一個點      回答
==============  ==========  ==========  ==================================
``box``         區域        一格框      這幾群各自散多開
``histogram``   灰階值      一格框      值怎麼散開、有沒有兩座山
``profile``     框中心 X/Y  一格框      **有沒有斜掉**
``map``         框的 (x,y)  一格框      不均勻在**哪裡**
==============  ==========  ==========  ==================================

四種都是「**一格框一個點**」—— 一致，所以切換的時候使用者不必重新學「現在
一個點是什麼」。

⚠ **這跟 `export/boxplot.py` 那張盒鬚圖不是同一個東西。**
那一張是「一個盒子＝判定樹的一片葉子，一個點＝一顆 defect」（整批的圖）；
這裡是「一個盒子＝一個區域，一個點＝一格框」（一張圖之內的圖）。兩者在畫面上
長得一模一樣，而「一個點是什麼」是唯一的差別 —— 那正是最容易在半年後被誰
順手合併的形狀。合併的下場是一張畫得出來、看起來正常、而意思是錯的圖。

**``box`` 那一種直接用 `boxplot.build_boxplot_svg`**（同一支函式、同一組
Tukey 鬚）—— 它吃的正好是 ``{name, values, colour}``，而盒鬚圖的幾何跟
「一個點是什麼」無關。同一種圖畫兩份的那天，兩張圖的鬚會不一樣長。

為什麼是 SVG 不是繪圖套件
-------------------------
`export/boxplot.py` 的檔頭寫過一次，這裡逐字適用：公司機是用複製檔案更新的，
多一個套件就是多一件在受限機器上會裝不起來的事。

為什麼顏色是參數
----------------
`core` 不得 import Qt（鐵則 1），所以主題查不到。呼叫端給 —— 跟 `boxplot`
與 `decide_tree.verdict_rows` 同一個理由。:data:`REGION_COLOURS` 是
**`ui.theme.REGION_COLORS` 的副本**，給沒有 UI 的呼叫端（CLI、Output 卡）
當退路；兩份要一致，`tests/test_export_uniformity.py` 守著。
"""
from __future__ import annotations

import math
from typing import Any, Dict, List, Optional, Sequence, Tuple

import numpy as np

# 這四支是 SVG 的共用零件，**唯一出處在 `boxplot.py`**。從那裡 import 而不是
# 抄一份：刻度算法漂掉的那天，同一份報表上兩張圖的軸會對不起來。
# （第三個消費者出現的時候，該做的是把它們搬進 `export/svg.py`，不是再抄一份。）
from .boxplot import (  # noqa: PLC2701 — 見上
    _esc, _fmt, _nice_ticks, build_boxplot_svg,
)

__all__ = [
    "CHARTS", "CHART_LABELS", "REGION_COLOURS", "AXES",
    "chart_series", "build_chart_svg", "build_charts_page",
]

#: 四種圖的值（recipe / 參數用的 id，不要改）。
CHART_BOX, CHART_HIST = "box", "histogram"
CHART_PROFILE, CHART_MAP = "profile", "map"
CHARTS: Tuple[str, ...] = (CHART_BOX, CHART_HIST, CHART_PROFILE, CHART_MAP)

#: 畫面與檔名上的字（使用者 2026-09-07 定調 ``position profile``）。
CHART_LABELS: Dict[str, str] = {
    CHART_BOX: "Box plot",
    CHART_HIST: "Histogram",
    CHART_PROFILE: "Position profile",
    CHART_MAP: "Heat map",
}

#: `profile` 沿哪一個軸。
AXIS_X, AXIS_Y = "x", "y"
AXES: Tuple[str, ...] = (AXIS_X, AXIS_Y)

#: 區域色 —— `ui.theme.REGION_COLORS` 的副本（見檔頭）。
REGION_COLOURS: Tuple[str, ...] = (
    "#5fd0a0", "#f0b429", "#7aa7ff", "#f07aa7",
    "#9ad14b", "#d18ef0", "#4bd1c8", "#f08a5f")

#: 熱圖的色階 —— 冷到熱。**刻意不含區域色的任何一個**：這張圖上顏色的意思是
#: 「值多少」，而不是「這是哪一群」。兩種意思共用一個顏色的話，讀圖的人得先
#: 決定現在是哪一種。
HEAT_RAMP: Tuple[str, ...] = (
    "#2b3a67", "#3d6fa8", "#4aa3a2", "#c9c05a", "#e8913c", "#c0392b")

_AXIS = "#98a2b3"
_TEXT = "#444"
_MUTED = "#777"
_GRID = "#e8eaee"
#: 趨勢線 —— **炭黑，不是琥珀**。
#:
#: PEAR 用琥珀畫它，而 PEAR 的規矩是「no group is ever amber」（琥珀被留給
#: 趨勢線與色階中點）。那條規矩在 d4t **不成立**，而且是兩次不成立：
#:
#: * `theme.REGION_COLORS` 的第 2 個就是 ``#f0b429`` —— 接第二個區域時，
#:   那一群的 profile 實線與它的趨勢虛線會是同一個顏色。實測畫出來看不出
#:   哪條是哪條（2026-09-07 的第一版就是這樣）。
#: * 琥珀在 d4t 已經有一個意思了：**最異常的那一格**
#:   （`overlay.ROI_WINNER_COLOR`、畫布上的粗框）。同一個顏色在同一份報表裡
#:   講兩件事，使用者得先決定現在是哪一種。
#:
#: 炭黑離八個區域色都很遠，而且它讀起來就是「註解」而不是「資料」——
#: 一條最小平方線本來就是註解。
_TREND = "#3a3f4b"

_MISSING = "-"

#: 一張圖**畫得完**所需要的最小尺寸。
#:
#: ⚠ 這不是美觀下限，是**正確性**下限。每一支 `_svg_*` 都把圖區夾在
#: ``max(80, height - 上留白 - 下留白)`` —— 也就是高度不夠時圖區**不會跟著
#: 縮**，於是內容比 viewBox 還高，而 SVG 的 viewBox 會**把超出的部分切掉**。
#: 實測（2026-09-07）：儀表把 profile 畫在 126 px 高的格子裡，斜率那一行
#: （整張圖唯一的數字）被切掉一半，而圖看起來完全正常。
#:
#: 所以 :func:`build_chart_svg` 把尺寸夾在這裡，讓呼叫端**縮整張圖**（等比
#: 例畫小）而不是切內容。字會變小，但沒有一樣東西不見。
MIN_WIDTH, MIN_HEIGHT = 220, 170


# --------------------------------------------------------------------------- #
# 資料層 —— **畫面與檔案吃的是同一份**
# --------------------------------------------------------------------------- #
def chart_series(notes: Sequence[Any], metric: str = "",
                 colours: Sequence[str] = ()) -> Dict[str, Any]:
    """`ctx.meta["glv_hist"]` 的那幾條 → 畫圖要的數字。

    **Qt-free、無繪圖** —— 這是「兩份繪圖程式碼吃同一支」的那個「同一支」。
    畫面上的儀表與寫出去的 SVG 各畫各的，但兩邊的**數字**只有這一個出處；
    各自算一次的話，圖上那一點與 CSV 上那一格會在某一天分岔，而那一天畫面上
    看起來完全正常。

    回 ``{"metric", "metrics", "groups": [{name, colour, values, cx, cy,
    rects}]}``。``metric`` 沒給就用第一條有東西的那一個。
    沒有任何一條帶 ``spread``（沒開 ``report``、或走 pooled）時 ``groups``
    是空的 —— 呼叫端要說得出「沒有東西可畫」跟「畫出來是平的」的差別。
    """
    pal = list(colours) or list(REGION_COLOURS)
    groups: List[Dict[str, Any]] = []
    metrics: List[str] = []
    for note in (notes or ()):
        if not isinstance(note, dict):
            continue
        spread = note.get("spread")
        if not isinstance(spread, dict):
            continue
        stats = spread.get("stats") or {}
        for m in stats:
            if m not in metrics:
                metrics.append(str(m))
    want = str(metric or "") or (metrics[0] if metrics else "")
    for note in (notes or ()):
        if not isinstance(note, dict):
            continue
        spread = note.get("spread")
        if not isinstance(spread, dict):
            continue
        values = (spread.get("stats") or {}).get(want)
        if not values:
            continue
        cx = list(spread.get("cx") or ())
        cy = list(spread.get("cy") or ())
        # 值與位置**共用索引**是所有位置計算的前提 —— 對不上就整組不畫
        # （同 `set_marks` 的規矩：畫一半比不畫糟）。
        if len(cx) != len(values) or len(cy) != len(values):
            continue
        name = str(note.get("region") or "") or str(note.get("prefix") or "")
        groups.append({
            "name": name or "region",
            "colour": pal[len(groups) % len(pal)],
            "values": [float(v) for v in values],
            "cx": [float(v) for v in cx],
            "cy": [float(v) for v in cy],
            "rects": [list(r) for r in (spread.get("rects") or ())],
        })
    return {"metric": want, "metrics": metrics, "groups": groups}


# --------------------------------------------------------------------------- #
# 共用的一點幾何
# --------------------------------------------------------------------------- #
def _span(values: Sequence[float], lock: Optional[Sequence[Any]] = None
          ) -> Tuple[float, float]:
    """要畫的範圍 —— **鎖了就用鎖的**（見 `build_chart_svg` 的 ``style``）。

    auto 縮放在看一批的時候是對的，兩批擺在一起就會騙人：各自挑各自的範圍，
    一樣高的柱子其實不一樣高。所以鎖定是這一輪唯一非做不可的外觀設定。
    """
    if lock:
        try:
            lo, hi = float(lock[0]), float(lock[1])
            if math.isfinite(lo) and math.isfinite(hi) and hi > lo:
                return lo, hi
        except (TypeError, ValueError, IndexError):
            pass
    arr = np.asarray([v for v in values], dtype=np.float64).ravel()
    arr = arr[np.isfinite(arr)]
    if arr.size == 0:
        return 0.0, 1.0
    lo, hi = float(arr.min()), float(arr.max())
    if hi <= lo:
        pad = abs(lo) * 0.05 or 0.5
        return lo - pad, hi + pad
    pad = (hi - lo) * 0.06
    return lo - pad, hi + pad


def _heat_hex(t: float) -> str:
    """0–1 → 色階上的一個顏色（線性內插，兩端夾住）。"""
    if not math.isfinite(t):
        return _MUTED
    t = min(1.0, max(0.0, float(t)))
    pos = t * (len(HEAT_RAMP) - 1)
    i = min(len(HEAT_RAMP) - 2, int(pos))
    f = pos - i
    a, b = HEAT_RAMP[i], HEAT_RAMP[i + 1]
    out = []
    for k in (1, 3, 5):
        ca, cb = int(a[k:k + 2], 16), int(b[k:k + 2], 16)
        out.append(int(round(ca + (cb - ca) * f)))
    return "#%02x%02x%02x" % tuple(out)


def _frame(o: List[str], x: float, y: float, w: float, h: float) -> None:
    """圖區的外框 —— 一張報表裡的圖需要的那道最基本的家具。"""
    o.append("<rect x='%.1f' y='%.1f' width='%.1f' height='%.1f' fill='none' "
             "stroke='%s' stroke-width='1'/>" % (x, y, w, h, _AXIS))


def _ylabels(o: List[str], ticks: Sequence[float], lo: float, hi: float,
             x: float, y: float, h: float, w: float, size: int = 10) -> None:
    for t in ticks:
        ty = y + h - (t - lo) / (hi - lo) * h
        o.append("<line x1='%.1f' y1='%.1f' x2='%.1f' y2='%.1f' stroke='%s' "
                 "stroke-width='1'/>" % (x, ty, x + w, ty, _GRID))
        o.append("<text x='%.1f' y='%.1f' font-size='%d' fill='%s' "
                 "text-anchor='end'>%s</text>"
                 % (x - 6, ty + 3, size, _TEXT, _esc(_fmt(t))))


def _axis_names(o: List[str], style: Dict[str, Any], width: int, height: int,
                px: float, py: float, pw: float, ph: float,
                xdef: str, ydef: str) -> None:
    xl = str(style.get("xlabel") or "") or xdef
    yl = str(style.get("ylabel") or "") or ydef
    if xl:
        o.append("<text x='%.1f' y='%d' font-size='11' fill='%s' "
                 "text-anchor='middle'>%s</text>"
                 % (px + pw / 2, height - 8, _TEXT, _esc(xl)))
    if yl:
        cy = py + ph / 2
        o.append("<text x='12' y='%.1f' font-size='11' fill='%s' "
                 "text-anchor='middle' transform='rotate(-90 12 %.1f)'>%s"
                 "</text>" % (cy, _TEXT, cy, _esc(yl)))


def _empty(width: int, height: int, why: str) -> str:
    """**畫不出來仍然回一張圖**（`boxplot` 的同一條規矩）。

    呼叫端把它塞進 HTML，而一個消失的區塊讀起來是「這裡本來就沒有東西」。
    """
    return ("<svg xmlns='http://www.w3.org/2000/svg' width='%d' height='%d' "
            "viewBox='0 0 %d %d'><rect width='%d' height='%d' fill='#fff'/>"
            "<text x='%d' y='%d' font-size='12' fill='%s' "
            "text-anchor='middle'>%s</text></svg>"
            % (width, height, width, height, width, height,
               width // 2, height // 2, _MUTED, _esc(why)))


def _head(width: int, height: int, title: str) -> List[str]:
    o = ["<svg xmlns='http://www.w3.org/2000/svg' width='%d' height='%d' "
         "viewBox='0 0 %d %d'>" % (width, height, width, height),
         "<rect width='%d' height='%d' fill='#fff'/>" % (width, height)]
    if title:
        o.append("<text x='%d' y='20' font-size='13' fill='%s' "
                 "text-anchor='middle'>%s</text>"
                 % (width // 2, _TEXT, _esc(title)))
    return o


# --------------------------------------------------------------------------- #
# 直方圖
# --------------------------------------------------------------------------- #
def _svg_histogram(series: Dict[str, Any], style: Dict[str, Any],
                   width: int, height: int) -> str:
    """值怎麼散開 —— 每一群一疊半透明的柱子，共用同一把尺。

    ``percent`` 打開時每一群畫的是**自己的比例**，所以框數差很多的兩群也
    比得起來（PEAR 的 ``%`` 那顆開關）。
    """
    groups = [g for g in series.get("groups") or [] if g.get("values")]
    if not groups:
        return _empty(width, height, "no boxes to plot")
    bins = max(4, min(128, int(style.get("bins") or 24)))
    pct = bool(style.get("percent", False))
    allv = [v for g in groups for v in g["values"]]
    lo, hi = _span(allv, style.get("vlock"))
    edges = np.linspace(lo, hi, bins + 1)

    counts = []
    for g in groups:
        c, _ = np.histogram(np.asarray(g["values"], dtype=np.float64), bins=edges)
        c = c.astype(np.float64)
        if pct and c.sum() > 0:
            c = c / c.sum() * 100.0
        counts.append(c)
    top = float(max((c.max() for c in counts), default=0.0)) or 1.0

    pad_l, pad_r = 62, 16
    pad_t = 30 if style.get("title") else 12
    pad_b = 56
    pw = max(80, width - pad_l - pad_r)
    ph = max(80, height - pad_t - pad_b)
    o = _head(width, height, str(style.get("title") or ""))
    ticks = _nice_ticks(0.0, top, int(style.get("yticks") or 5))
    _ylabels(o, ticks, 0.0, top, pad_l, pad_t, ph, pw)
    _frame(o, pad_l, pad_t, pw, ph)

    bw = pw / bins
    for g, c in zip(groups, counts):
        for i, v in enumerate(c):
            if v <= 0:
                continue
            bh = v / top * ph
            o.append("<rect x='%.2f' y='%.2f' width='%.2f' height='%.2f' "
                     "fill='%s' fill-opacity='0.45' stroke='%s' "
                     "stroke-width='0.6'/>"
                     % (pad_l + i * bw, pad_t + ph - bh, max(0.6, bw - 0.6),
                        bh, g["colour"], g["colour"]))
    for t in _nice_ticks(lo, hi, int(style.get("xticks") or 5)):
        tx = pad_l + (t - lo) / (hi - lo) * pw
        o.append("<text x='%.1f' y='%.1f' font-size='10' fill='%s' "
                 "text-anchor='middle'>%s</text>"
                 % (tx, pad_t + ph + 15, _TEXT, _esc(_fmt(t))))
    _legend(o, groups, pad_l, pad_t + ph + 32)
    _axis_names(o, style, width, height, pad_l, pad_t, pw, ph,
                str(series.get("metric") or "value"),
                "share of the group (%)" if pct else "boxes")
    o.append("</svg>")
    return "".join(o)


def _legend(o: List[str], groups: Sequence[Dict[str, Any]],
            x: float, y: float) -> None:
    """一群一個色塊 ＋ 名字 ＋ **n**（框數）。

    ``n`` 不是裝飾：兩群的框數差十倍時，同樣高的柱子講的是完全不同的事。
    """
    cur = x
    for g in groups:
        o.append("<rect x='%.1f' y='%.1f' width='9' height='9' fill='%s'/>"
                 % (cur, y - 8, g["colour"]))
        text = "%s (n=%d)" % (g["name"], len(g["values"]))
        o.append("<text x='%.1f' y='%.1f' font-size='10' fill='%s'>%s</text>"
                 % (cur + 13, y, _TEXT, _esc(text)))
        cur += 22 + 6.2 * len(text)


# --------------------------------------------------------------------------- #
# Position profile —— 有沒有斜掉
# --------------------------------------------------------------------------- #
def _svg_profile(series: Dict[str, Any], style: Dict[str, Any],
                 width: int, height: int) -> str:
    """值 vs 框中心的位置。三種線，各一個顏色（PEAR §4 的規矩）：

    * **點** —— 一格框一個（空心，免得跟線糊在一起）
    * **profile**（實線，區域色壓深）—— 同一欄的框收成一個點。
      **這是讀平不平的那條線。**
    * **trend**（虛線，琥珀）—— 穿過每一格的最小平方線，斜率標在圖上
      （每 100 px）

    參照線畫在底層、資料畫在上層 —— 反過來的話趨勢線會蓋掉它本來要被拿來
    比較的那條 profile。
    """
    from ..algo import uniformity as unif

    groups = [g for g in series.get("groups") or [] if g.get("values")]
    if not groups:
        return _empty(width, height, "no boxes to plot")
    axis = str(style.get("axis") or AXIS_X).lower()
    axis = axis if axis in AXES else AXIS_X
    key = "cy" if axis == AXIS_Y else "cx"

    allv = [v for g in groups for v in g["values"]]
    allp = [p for g in groups for p in g[key]]
    lo, hi = _span(allv, style.get("vlock"))
    plo, phi = _span(allp, style.get("plock"))

    pad_l, pad_r = 62, 16
    pad_t = 30 if style.get("title") else 12
    pad_b = 56
    pw = max(80, width - pad_l - pad_r)
    ph = max(80, height - pad_t - pad_b)
    o = _head(width, height, str(style.get("title") or ""))
    _ylabels(o, _nice_ticks(lo, hi, int(style.get("yticks") or 5)),
             lo, hi, pad_l, pad_t, ph, pw)
    _frame(o, pad_l, pad_t, pw, ph)

    def sx(p: float) -> float:
        return pad_l + (p - plo) / (phi - plo) * pw

    def sy(v: float) -> float:
        return pad_t + ph - (v - lo) / (hi - lo) * ph

    notes: List[str] = []
    for g in groups:
        pos, vals = g[key], g["values"]
        # ---- 底層：群平均那條淡虛線（完全平的 profile 會落在上面）--------
        mean = float(np.mean(vals))
        o.append("<line x1='%.1f' y1='%.1f' x2='%.1f' y2='%.1f' stroke='%s' "
                 "stroke-width='1' stroke-dasharray='2 3' stroke-opacity='0.5'"
                 "/>" % (pad_l, sy(mean), pad_l + pw, sy(mean), g["colour"]))
        # ---- 底層：趨勢線 -------------------------------------------------
        fit = unif.linear_trend(pos, vals)
        if fit is not None:
            slope, intercept = fit
            o.append("<line x1='%.1f' y1='%.1f' x2='%.1f' y2='%.1f' "
                     "stroke='%s' stroke-width='1.6' stroke-dasharray='6 4'/>"
                     % (sx(plo), sy(slope * plo + intercept),
                        sx(phi), sy(slope * phi + intercept), _TREND))
            notes.append("%s: %s / 100 px"
                         % (g["name"], _fmt(slope * unif.SLOPE_UNIT_PX)))
        else:
            notes.append("%s: %s" % (g["name"], _MISSING))
        # ---- 上層：profile 線 ---------------------------------------------
        px_, pv = unif.profile_by_position(pos, vals)
        if px_.size >= 2:
            pts = " ".join("%.1f,%.1f" % (sx(a), sy(b))
                           for a, b in zip(px_, pv))
            o.append("<polyline points='%s' fill='none' stroke='%s' "
                     "stroke-width='2'/>" % (pts, g["colour"]))
        # ---- 上層：每一格框 ------------------------------------------------
        if style.get("points", True):
            r = float(style.get("point_size") or 2.6)
            for a, b in zip(pos, vals):
                o.append("<circle cx='%.1f' cy='%.1f' r='%.1f' fill='none' "
                         "stroke='%s' stroke-width='1'/>"
                         % (sx(a), sy(b), r, g["colour"]))
    for t in _nice_ticks(plo, phi, int(style.get("xticks") or 5)):
        o.append("<text x='%.1f' y='%.1f' font-size='10' fill='%s' "
                 "text-anchor='middle'>%s</text>"
                 % (sx(t), pad_t + ph + 15, _TEXT, _esc(_fmt(t))))
    o.append("<text x='%.1f' y='%.1f' font-size='10' fill='%s'>slope %s</text>"
             % (pad_l, pad_t + ph + 32, _TREND, _esc("; ".join(notes))))
    _axis_names(o, style, width, height, pad_l, pad_t, pw, ph,
                "box centre %s (px)" % axis.upper(),
                str(series.get("metric") or "value"))
    o.append("</svg>")
    return "".join(o)


# --------------------------------------------------------------------------- #
# Heat map —— 不均勻在哪裡
# --------------------------------------------------------------------------- #
def _svg_map(series: Dict[str, Any], style: Dict[str, Any],
             width: int, height: int) -> str:
    """框放在自己的 (x, y) 上，顏色＝值，旁邊一條色條。

    每一格畫的是 `algo.uniformity.cell_boxes` 算出來的**那一塊**（到鄰居中線
    為止），不是框本身：量到的只有框裡面，框與框之間是沒有量的，而把值鋪滿
    那一塊等於用最近的一次真實量測去填它 —— 於是整片的梯度看起來是一片梯度，
    不是一排小色塊。

    ⚠ **只畫第一群。** 兩群的框疊在同一張 (x, y) 上，後畫的會蓋掉先畫的，
    而畫面上看不出被蓋掉這件事。要比兩群請看另外三張圖 —— 那三張的 X 軸
    分得開兩群，這一張的 X 軸是位置。
    """
    from ..algo import uniformity as unif

    groups = [g for g in series.get("groups") or [] if g.get("values")]
    if not groups:
        return _empty(width, height, "no boxes to plot")
    g = groups[0]
    vals = g["values"]
    lo, hi = _span(vals, style.get("hlock"))
    rects = [tuple(r) for r in (g.get("rects") or ())]
    if len(rects) != len(vals):
        return _empty(width, height, "box positions do not line up")

    cells = unif.cell_boxes(rects)
    xs = [c[0] for c in cells] + [c[2] for c in cells]
    ys = [c[1] for c in cells] + [c[3] for c in cells]
    x0, x1 = min(xs), max(xs)
    y0, y1 = min(ys), max(ys)
    if x1 <= x0 or y1 <= y0:
        return _empty(width, height, "boxes have no extent")

    pad_l, pad_r = 46, 84            # 右邊留給色條
    pad_t = 30 if style.get("title") else 12
    pad_b = 44
    pw = max(60, width - pad_l - pad_r)
    ph = max(60, height - pad_t - pad_b)
    # **等比例** —— 位置圖上長寬比不對的話，一片方形的排列會看起來是長方形，
    # 而使用者是拿它去對真實影像的。
    scale = min(pw / (x1 - x0), ph / (y1 - y0))
    dw, dh = (x1 - x0) * scale, (y1 - y0) * scale
    ox = pad_l + (pw - dw) / 2.0
    oy = pad_t + (ph - dh) / 2.0

    o = _head(width, height, str(style.get("title") or ""))
    for (cx0, cy0, cx1, cy1), v in zip(cells, vals):
        t = 0.5 if hi <= lo else (float(v) - lo) / (hi - lo)
        o.append("<rect x='%.2f' y='%.2f' width='%.2f' height='%.2f' "
                 "fill='%s' stroke='none'/>"
                 % (ox + (cx0 - x0) * scale, oy + (cy0 - y0) * scale,
                    max(0.5, (cx1 - cx0) * scale),
                    max(0.5, (cy1 - cy0) * scale), _heat_hex(t)))
    if style.get("points", True):
        # 量到的那個框仍然描出來 —— 「這一塊的顏色是從哪一格量來的」
        for (rx, ry, rw, rh) in rects:
            o.append("<rect x='%.2f' y='%.2f' width='%.2f' height='%.2f' "
                     "fill='none' stroke='#ffffff' stroke-opacity='0.55' "
                     "stroke-width='0.8'/>"
                     % (ox + (rx - x0) * scale, oy + (ry - y0) * scale,
                        rw * scale, rh * scale))
    _frame(o, ox, oy, dw, dh)

    # ---- 色條 -------------------------------------------------------------
    bx, bw_ = width - pad_r + 16, 14
    for i in range(64):
        t = 1.0 - i / 63.0
        o.append("<rect x='%.1f' y='%.2f' width='%d' height='%.2f' fill='%s' "
                 "stroke='none'/>"
                 % (bx, pad_t + i * ph / 64.0, bw_, ph / 64.0 + 0.6,
                    _heat_hex(t)))
    o.append("<rect x='%.1f' y='%.1f' width='%d' height='%.1f' fill='none' "
             "stroke='%s' stroke-width='1'/>" % (bx, pad_t, bw_, ph, _AXIS))
    for t, ty in ((hi, pad_t + 4), (lo, pad_t + ph)):
        o.append("<text x='%.1f' y='%.1f' font-size='10' fill='%s'>%s</text>"
                 % (bx + bw_ + 4, ty, _TEXT, _esc(_fmt(t))))
    if style.get("hlock"):
        o.append("<text x='%.1f' y='%.1f' font-size='9' fill='%s'>locked</text>"
                 % (bx + bw_ + 4, pad_t + ph / 2, _MUTED))
    o.append("<text x='%.1f' y='%d' font-size='10' fill='%s'>%s - %s</text>"
             % (pad_l, height - 10, _MUTED, _esc(g["name"]),
                _esc(str(series.get("metric") or "value"))))
    if len(groups) > 1:
        # 蓋掉別群這件事**要講出來**（見 docstring 的警告）
        o.append("<text x='%d' y='%d' font-size='10' fill='%s' "
                 "text-anchor='end'>%d more region(s) not shown</text>"
                 % (width - pad_r, height - 10, _MUTED, len(groups) - 1))
    o.append("</svg>")
    return "".join(o)


# --------------------------------------------------------------------------- #
# 對外
# --------------------------------------------------------------------------- #
def build_chart_svg(series: Dict[str, Any], kind: str = CHART_BOX,
                    style: Optional[Dict[str, Any]] = None,
                    width: int = 640, height: int = 420) -> str:
    """一張圖。``kind`` 見 :data:`CHARTS`；認不得的字當 ``box``。

    ``style`` 的每一格都是**選填的覆寫**（空的就自己決定）::

        title    圖上方那一行字
        xlabel   X 軸的名字（空的用這種圖的預設）
        ylabel   Y 軸的名字
        vlock    (lo, hi) —— **鎖住值那一軸**。見 `_span` 的說明
        plock    (lo, hi) —— 鎖住位置那一軸（profile）
        hlock    (lo, hi) —— 鎖住顏色那一軸（map）
        axis     profile 沿 "x" 還是 "y"
        points   要不要畫每一格框（框很多時關掉）
        whiskers 盒鬚圖要不要畫鬚
        bins     直方圖幾個柱
        percent  直方圖畫比例而不是次數
        xticks / yticks   幾個刻度
    """
    st = dict(style or {})
    k = str(kind or CHART_BOX)
    # **夾住尺寸，不夾內容**（見 `MIN_WIDTH` 的警告）。呼叫端把回來的圖
    # 等比例縮進它那一格 —— 縮小的圖讀得完，切掉的圖讀不完而且看不出來。
    width = max(int(width), MIN_WIDTH)
    height = max(int(height), MIN_HEIGHT)
    if k == CHART_HIST:
        return _svg_histogram(series, st, width, height)
    if k == CHART_PROFILE:
        return _svg_profile(series, st, width, height)
    if k == CHART_MAP:
        return _svg_map(series, st, width, height)
    # 盒鬚圖走 `boxplot` 那一支（同一組 Tukey 鬚，見檔頭）
    groups = [g for g in series.get("groups") or [] if g.get("values")]
    if not groups:
        return _empty(width, height, "no boxes to plot")
    return build_boxplot_svg(
        [{"name": g["name"], "values": g["values"], "colour": g["colour"]}
         for g in groups],
        title=str(st.get("title") or ""),
        subtitle=str(st.get("subtitle") or ""),
        width=width, height=height)


def build_charts_page(series: Dict[str, Any], kinds: Sequence[str],
                      title: str, subtitle: str = "",
                      style: Optional[Dict[str, Any]] = None) -> str:
    """幾張圖一頁（由上往下）—— 走 `boxplot.build_boxplot_page` 的版型。

    版型共用而不是抄一份：兩頁在同一份報表資料夾裡並排，字級不一樣的那天
    沒有人會知道為什麼。
    """
    from .boxplot import build_boxplot_page

    st = dict(style or {})
    charts = []
    for k in (kinds or CHARTS):
        kk = str(k)
        if kk not in CHARTS:
            continue
        one = dict(st)
        one.setdefault("title", CHART_LABELS.get(kk, kk))
        charts.append({"name": CHART_LABELS.get(kk, kk),
                       "svg": build_chart_svg(series, kk, one)})
    return build_boxplot_page(charts, title, subtitle=subtitle)
