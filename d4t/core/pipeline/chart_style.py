# -*- coding: utf-8 -*-
# d4t chart style — authored 2026-09-07 (F87).
"""圖表長什麼樣 —— **一格參數裝得下的一整組設定**。

為什麼是一格，不是二十五格
--------------------------
使用者要 PEAR 那種 chart settings（字級、粗體、顏色、線寬、鎖定範圍、每張圖
的標題與軸名）。攤成 ParamSpec 是二十五列，而 d4t 的參數面板是**一列一格** ——
二十五列排成一條就是一面牆，讀的人要從頭掃到尾才知道哪一列管什麼。

`tone` 卡的 ``type="curve"`` 是這件事的前例：**一個複雜的值裝在一格參數裡，
配一個專屬編輯器**（色調曲線用拖的）。這一支是同一個形狀，`cell_rois` 也是。

編碼
----
JSON 物件，鍵是**扁平的字串**，而且**只存跟預設不一樣的那些**：

    {"tick_size": 12, "tick_bold": true, "box.title": "EPI uniformity"}

* 全域的鍵直接寫（``tick_size``）；
* 某一張圖自己的覆寫寫成 ``<圖>.<鍵>``（``profile.ylabel``）。

只存差異有兩個實際的好處：recipe 乾淨（一份沒改過設定的 recipe 那一格是空
字串），而且**改預設值的時候舊檔案跟著改** —— 那是對的，一個沒有人動過的
外觀不該被凍在半年前的樣子。

⚠ **這一支不認識任何一張圖的名字。** 它只驗**形狀**（鍵合不合法、值在不在
範圍內）。哪幾張圖存在是 `export/uniformity_charts` 的事 —— 這裡知道那件事的話，
`pipeline/` 就開始依賴 `export/`，而那個方向是反的。

⚠ **round-trip 必須是 identity**（鐵則 9）。`format_style(parse_style(x))`
穩定：鍵排序、浮點數統一位數、等於預設值的一律丟掉。
"""
from __future__ import annotations

import json
from typing import Any, Dict, List, Optional, Tuple

__all__ = [
    "ChartStyleError", "DEFAULTS", "GLOBAL_KEYS", "PER_CHART_KEYS", "ROWS",
    "bounds", "parse_style", "format_style", "style_for", "describe",
]


class ChartStyleError(ValueError):
    """一句白話（同 `curve.CurveError`）—— 使用者看得到這句話。"""


#: ``""`` = 跟著區域色走（PEAR 的 auto）。
#:
#: **顏色的預設不是一個顏色，是「自動」**：使用者八成不想手動指定每一群的
#: 顏色，他只想在某一個特例上蓋掉。存一個具體的色碼當預設的話，主題換了、
#: 區域色換了，這一格會**安靜地把它們釘死**。
AUTO = ""

#: 每一格的 ``(預設值, 最小, 最大)``。**最小/最大是給 UI 的滑桿與驗證共用的
#: 同一份** —— 兩份會漂，而漂掉的那天使用者打得進一個 UI 拉不到的值。
_NUM: Dict[str, Tuple[float, float, float]] = {
    # 刻度上的數字
    "tick_size": (10.0, 5.0, 28.0),
    # 軸名與圖框
    "axis_size": (11.0, 5.0, 28.0),
    # 每一格框的記號
    "point_size": (2.6, 0.5, 12.0),
    # profile 線、中位線、盒子外框
    "line_width": (1.6, 0.4, 6.0),
    # ⚠ **填色的濃度是一個倍率，不是一個絕對值。**
    #
    # 每一種圖自己那個淡度是設計過的（直方圖的柱 0.45、盒鬚圖的盒子 0.18 ——
    # 盒鬚圖上的墨水本來就多，同樣濃度會糊成一團）。一格絕對的 opacity 會把
    # 那個關係抹平，而且**沒有一個值能同時等於今天的兩個**；倍率則是 1.0 就
    # 逐位元組不變，往上調投影機看得清楚、往下調幾乎只剩外框。
    "fill_strength": (1.0, 0.0, 3.0),
    # 直方圖切幾根柱
    "bins": (24.0, 4.0, 128.0),
    # 兩軸各幾個刻度
    "xticks": (5.0, 2.0, 20.0),
    "yticks": (5.0, 2.0, 20.0),
    # 鎖定的數值範圍（`lock` 關著的時候這兩個不作用）
    "lo": (0.0, -1e9, 1e9),
    "hi": (0.0, -1e9, 1e9),
}

_BOOL: Dict[str, bool] = {
    "tick_bold": False,
    "axis_bold": False,
    #: 每一格框畫不畫記號（框幾百個的時候關掉，不然點會糊成一團）
    "points": True,
    #: Position profile 的圓圈**填滿**（預設是空心的）。
    #: 空心在點很多的時候看得到互相重疊，實心在投影片上比較看得見 ——
    #: 兩種都對，看你要給誰看。
    "point_fill": False,
    #: 盒鬚圖畫不畫鬚
    "whiskers": True,
    #: 直方圖畫比例而不是次數（兩群框數差很多時才有意義）
    "percent": False,
    #: ⚠ **熱圖那張圖的每一格畫一樣大**（`equal cells`，PEAR 的預設）。
    #:
    #: 照實鋪的話每一格的邊界落在鄰居的中線上 —— 間距不平均、或少了一格，
    #: 相鄰兩格的**面積就明顯不一樣**，而**面積不是這張圖在量的東西**。
    #: 排成格子之後每一格都一樣大，那才是一張 die map 該有的樣子，兩格也才
    #: 一眼比得起來；軸上仍然標著每一欄代表的位置。
    #:
    #: 關掉它就回到照實鋪（要看真實的空間關係時才需要）。
    #: **只影響那張獨立的圖** —— 疊在影像上的那一層永遠照實鋪，因為它畫在
    #: 影像上，位置要對得起來。
    "equal_cells": True,
    #: 熱圖每一格裡印出那個值（放得下才印）。
    "map_values": False,
    #: ⚠ **鎖住數值範圍。** 這一格是這一組裡唯一「不只是好不好看」的 ——
    #: auto 縮放在看一批時是對的，兩批擺在一起就會騙人（每張圖各自挑各自的
    #: 範圍，於是一樣高的柱子其實不一樣高），而圖上沒有任何線索說這件事。
    "lock": False,
}

_TEXT: Dict[str, str] = {
    "tick_color": AUTO,
    "axis_color": AUTO,
    "point_color": AUTO,
    "line_color": AUTO,
    #: 柱子／盒子／實心記號的**填色**。空 = 跟著那一群自己的顏色走。
    #: ⚠ 接兩個以上區域時填成同一色，圖例就分不出誰是誰 —— 跟
    #: `point_color` / `line_color` 同一個取捨。
    "fill_color": AUTO,
    #: 表示「大小」的色階：``""`` = 單色（由淺到深），``"rainbow"`` = 彩虹。
    #:
    #: 通用規則是單一色相：彩虹在中段會製造出資料裡沒有的假邊界。但半導體的
    #: wafer map 慣例就是彩虹 —— **兩種都留，預設單色**
    #: （使用者 2026-09-07：「兩種都可 預設單色」）。
    "ramp": AUTO,
    #: 值那一軸要叫什麼（`glv_mean` → `Gray level`）。四張圖共用 ——
    #: 它在盒鬚圖是 Y、直方圖是 X、profile 是 Y、熱圖是色條，而那正是使用者
    #: 會想改的那一個。**其餘的軸名是每張圖自己的**（見 PER_CHART_KEYS）。
    "value_name": "",
}

#: 全域的鍵（不帶圖名前綴）。
GLOBAL_KEYS: Tuple[str, ...] = tuple(sorted(
    set(_NUM) | set(_BOOL) | set(_TEXT)))

#: 每張圖自己的**文字**覆寫。沒有全域版本 —— 它們的「預設」是「這種圖自己
#: 決定」（`build_chart_svg` 的 ``xdef`` / ``ydef``），不是某個固定的字。
_PER_TEXT: Tuple[str, ...] = ("title", "xlabel", "ylabel")

#: 可以**每張圖各給一份**的鍵（寫成 ``<圖>.<鍵>``）。
#:
#: 為什麼標題與軸名是每張圖的，而字級顏色是全域的：四張圖的 X 軸是四件不同
#: 的事（區域／灰階值／位置／位置），一組共用的名字**一定有三張是錯的**；
#: 而「刻度的字要多大」在四張圖上是同一個問題。
PER_CHART_KEYS: Tuple[str, ...] = ("title", "xlabel", "ylabel",
                                   "xticks", "yticks")

#: 全部的預設值（**唯一出處** —— UI、驗證、SVG 三邊都問這裡）。
DEFAULTS: Dict[str, Any] = {}
for _k, (_d, _lo, _hi) in _NUM.items():
    DEFAULTS[_k] = _d
DEFAULTS.update(_BOOL)
DEFAULTS.update(_TEXT)

#: 編輯器上的**列**：``(標題, [(鍵, 欄名), …])``。
#:
#: PEAR 那個對話框的價值有一半在這個排列 —— **一列一個東西、屬性橫著擺**。
#: 住在 core 而不是 UI：它描述的是「這一組設定怎麼分群」，而那件事跟畫面用
#: 什麼元件無關（同 `decide_tree.verdict_rows` 的立場）。
ROWS: Tuple[Tuple[str, Tuple[Tuple[str, str], ...]], ...] = (
    ("Tick values", (("tick_size", "size"), ("tick_bold", "bold"),
                     ("tick_color", "colour"))),
    ("Axis names", (("axis_size", "size"), ("axis_bold", "bold"),
                    ("axis_color", "colour"))),
    # ⚠ ``point_fill`` **不在這裡**：它是「空心還是實心」——一個要哪一種長相
    # 的問題，所以它在下面那一區是一排兩顆膠囊（`BOOL_CHIPS`）。
    # 兩邊都放過一次，而後放的那個把前面的從 `globals` 裡蓋掉 —— 於是這一列
    # 的「filled」勾選框看得到、按得下、**什麼都不會發生**。
    # 使用者 2026-09-07 一眼看出來：「Icon 很漂亮，但有全應用進去嗎」。
    ("Data points", (("point_size", "radius"), ("point_color", "colour"))),
    ("Lines", (("line_width", "width"), ("line_color", "colour"))),
    ("Fills", (("fill_strength", "strength"), ("fill_color", "colour"))),
)


def bounds(name: str) -> Optional[Tuple[float, float]]:
    """``name`` 的 ``(最小, 最大)``；不是數字的鍵回 ``None``。

    **編輯器上的每一格都問這裡。** 上一段說了「最小/最大是給 UI 與驗證共用的
    同一份」—— 那句話要成立就得有一個公開的入口，不然 UI 只能自己抄一份
    （而抄出來的那一份就是會漂的那一份，見 CLAUDE.md §0）。
    """
    got = _NUM.get(str(name))
    return (got[1], got[2]) if got else None


def _split(key: str) -> Tuple[str, str]:
    """``"box.title"`` → ``("box", "title")``；``"tick_size"`` → ``("", …)``。"""
    if "." in key:
        chart, _, name = key.partition(".")
        return chart.strip(), name.strip()
    return "", key.strip()


def _coerce(name: str, value: Any, where: str) -> Any:
    """一個值 → 正規化過的值（不合法就是一句白話）。"""
    if name in _NUM:
        default, lo, hi = _NUM[name]
        try:
            v = float(value)
        except (TypeError, ValueError):
            raise ChartStyleError(
                "%s should be a number, not %r" % (where, value)) from None
        if not (lo <= v <= hi):
            raise ChartStyleError(
                "%s is %g, which is outside %g–%g" % (where, v, lo, hi))
        # **整數就存成整數** —— `12.0` 與 `12` 在 JSON 上是兩個字串，而
        # round-trip 要是 identity（鐵則 9）。四位小數是這個面板拉得出來的
        # 最細精度（同 `curve.format_curve`）。
        v = round(v, 4)
        return int(v) if float(v).is_integer() else v
    if name in _BOOL:
        if isinstance(value, bool):
            return value
        raise ChartStyleError("%s should be true or false, not %r"
                              % (where, value))
    if name == "ramp":
        text = "" if value is None else str(value).strip()
        if text not in ("", "rainbow"):
            raise ChartStyleError(
                "%s should be empty (a light-to-dark single colour) or "
                "'rainbow'" % where)
        return text
    if name in _TEXT or name in _PER_TEXT:
        text = "" if value is None else str(value)
        if name.endswith("_color") and text and not _is_hex(text):
            raise ChartStyleError(
                "%s should be a colour like #4a90d9, or empty to follow the "
                "region's own colour" % where)
        return text
    raise ChartStyleError("'%s' is not a chart setting" % where)


def _is_hex(text: str) -> bool:
    t = str(text).strip()
    return (len(t) == 7 and t[0] == "#"
            and all(c in "0123456789abcdefABCDEF" for c in t[1:]))


def parse_style(text: object) -> Dict[str, Any]:
    """JSON 字串 → ``{鍵: 值}``（**只含跟預設不一樣的**）。

    空字串／``None`` = 全部預設，回 ``{}`` —— 舊 recipe 沒有這一格也讀得動。
    """
    s = "" if text is None else str(text).strip()
    if not s:
        return {}
    if isinstance(text, dict):
        raw = dict(text)
    else:
        try:
            raw = json.loads(s)
        except ValueError as e:
            raise ChartStyleError(
                "the chart settings are not valid JSON (%s)" % e) from None
    if not isinstance(raw, dict):
        raise ChartStyleError("the chart settings should be a JSON object "
                              "like {\"tick_size\": 12}")
    out: Dict[str, Any] = {}
    for key, value in raw.items():
        chart, name = _split(str(key))
        if chart and name not in PER_CHART_KEYS:
            raise ChartStyleError(
                "'%s' cannot be set per chart (only %s can)"
                % (name, ", ".join(PER_CHART_KEYS)))
        if not chart and name not in DEFAULTS:
            raise ChartStyleError("'%s' is not a chart setting" % name)
        v = _coerce(name, value, str(key))
        # **等於預設就不存**（見模組說明）—— 但每張圖自己的覆寫沒有「預設」
        # 可比（它的預設是「跟著全域走」），所以只有空字串才丟。
        if chart:
            if v != "" or name not in ("title", "xlabel", "ylabel"):
                out[str(key)] = v
        elif v != DEFAULTS[name]:
            out[name] = v
    return out


def format_style(style: object) -> str:
    """``{鍵: 值}`` → 標準 JSON 字串（**排序過，所以 round-trip 穩定**）。

    什麼都沒改就回空字串 —— 一份沒動過外觀的 recipe 那一格是空的，
    diff 乾淨。
    """
    d = style if isinstance(style, dict) else parse_style(style)
    clean = parse_style(dict(d))
    if not clean:
        return ""
    return json.dumps(clean, sort_keys=True, separators=(",", ":"),
                      ensure_ascii=False)


def style_for(style: object, kind: str = "",
              extra: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """一張圖真正要用的那一份設定（全域 ＋ 那張圖自己的覆寫）。

    這是**畫圖那一側唯一的入口** —— `build_chart_svg` 的 ``style`` 契約
    一個字都沒有變，只是現在由這一支組出來。
    """
    d = style if isinstance(style, dict) else parse_style(style)
    # 每張圖自己的那三個沒有全域預設（見 `_PER_TEXT`），但**取用口一定要
    # 查得到** —— 少一格的話呼叫端每次都要 `.get(..., "")`，而漏掉那個預設值
    # 的那一次會是 KeyError 而不是「沒有覆寫」。
    out: Dict[str, Any] = dict(DEFAULTS)
    out.update({k: "" for k in _PER_TEXT})
    for key, value in d.items():
        chart, name = _split(str(key))
        if not chart:
            out[name] = value
    for key, value in d.items():
        chart, name = _split(str(key))
        if chart and chart == str(kind):
            out[name] = value
    out.update(dict(extra or {}))
    # 鎖定那一組換成畫圖那一側認得的形狀（``None`` = auto）。
    span = ((float(out["lo"]), float(out["hi"]))
            if bool(out.get("lock")) and float(out["hi"]) > float(out["lo"])
            else None)
    out["vlock"] = out["hlock"] = span
    return out


def describe(style: object) -> str:
    """卡片那一格上顯示的一句話（**參數格是唯讀的摘要，設定在編輯器裡改**）。"""
    d = style if isinstance(style, dict) else parse_style(style)
    if not d:
        return "default"
    locked = bool(d.get("lock"))
    n = len([k for k in d if k not in ("lock", "lo", "hi")])
    bits: List[str] = []
    if n:
        bits.append("%d change%s" % (n, "" if n == 1 else "s"))
    if locked:
        bits.append("scale locked")
    return " · ".join(bits) or "default"
