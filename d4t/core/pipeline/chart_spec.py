# -*- coding: utf-8 -*-
# d4t chart spec — authored 2026-09-07 (F88 第二刀).
"""**一張圖 = 哪一欄放到哪一個角色上，加一種記號。**

計畫書 `docs/plans/F88-graph-builder.md` §3。

    {"mark": "point", "x": "glv_mean", "y": "glv_std", "color": "region"}

為什麼這件事比它看起來小
------------------------
現在那四張圖已經是這個文法了，只是被寫死成四個組合 —— 而**熱圖跟散佈圖只差
在「顏色綁的是區域還是統計量」**。所以使用者要的那幾張圖不是新功能，是同一
個引擎的幾種角色配置。

跟 `chart_style` 的分工
-----------------------
* `chart_spec`（這一支）＝ **畫什麼**：哪一欄、哪一種記號。
* `chart_style` ＝ **長什麼樣**：字級、線寬、填色、鎖定範圍。

兩支都住在 `pipeline/` 因為兩份都進 recipe，而且**兩支都不 import `export`**。

⚠ **驗的是形狀，不是欄位存不存在。** 「`glv_std` 這一欄有沒有」要有資料才
知道，而 recipe 存的時候沒有資料 —— 那是**跑的時候**一條說得出話的警告
（同 `Which number to plot` 打錯時畫布上那條黃字），不是一個存不下去的錯誤。
存不下去的話，使用者換一個 metric 就得先把圖刪掉。

⚠ **mark 是一組封閉的字彙**（:data:`MARKS`）。「那個字要怎麼畫」是 `export`
的事 —— 這一支只認得那幾個字。跟 `chart_style` 不認識任何一張圖的名字是同一
條規矩，而那條規矩已經付過一次帳（F87：style 的解析住在卡片上，於是四個呼叫
端都得繞一圈，而少繞的那一個就是預覽沒有反應的那個 bug）。

⚠ **round-trip 必須是 identity**（鐵則 9）。
"""
from __future__ import annotations

import json
from typing import Any, Dict, List, Tuple

__all__ = [
    "ChartSpecError", "MARKS", "MARK_HELP", "MARK_LABELS",
    "ROLES", "ROLE_HELP", "REQUIRED",
    "parse_spec", "format_spec", "describe",
]


class ChartSpecError(ValueError):
    """一句白話（同 `chart_style.ChartStyleError`）—— 使用者看得到這句話。"""


#: 記號。**封閉字彙** —— 加一種要同時在 `export.chart_draw` 有人畫它，
#: 而那件事有測試對著（少一支的症狀是那張圖畫不出來而畫面上不說為什麼）。
MARK_POINT = "point"
MARK_LINE = "line"
MARK_BAR = "bar"
MARK_BOX = "box"
MARK_CELL = "cell"
MARKS: Tuple[str, ...] = (MARK_POINT, MARK_LINE, MARK_BAR, MARK_BOX,
                          MARK_CELL)

#: 每一種記號一句白話（編輯器上那一排膠囊的 tooltip）。
MARK_HELP: Dict[str, str] = {
    MARK_POINT: "A dot per box. Use it to see whether two numbers move "
                "together.",
    MARK_LINE: "A line through the boxes, in order of the bottom axis. Use it "
               "when the bottom axis has an order - position, row, column.",
    MARK_BAR: "A bar per box. Use it when the bottom axis is a name rather "
              "than a number, and you are comparing heights.",
    MARK_BOX: "One box per group along the bottom - the middle half, the "
              "median, and the whiskers. Use it to compare how spread out "
              "several groups are.",
    MARK_CELL: "A grid of coloured cells. Pick what the colour means - this "
               "is the heat map, but over any two columns you like.",
}

#: 每一種記號畫面上叫什麼（`MARK_LINE` 這個鍵不是給人看的字）。
MARK_LABELS: Dict[str, str] = {
    MARK_POINT: "Dots", MARK_LINE: "Line", MARK_BAR: "Bars",
    MARK_BOX: "Boxes", MARK_CELL: "Cells",
}

#: 角色。順序就是編輯器上由上而下的順序。
ROLE_X, ROLE_Y = "x", "y"
ROLE_COLOR, ROLE_SIZE = "color", "size"
ROLES: Tuple[str, ...] = (ROLE_X, ROLE_Y, ROLE_COLOR, ROLE_SIZE)

#: 每一個角色一句白話（編輯器上那一行 tooltip）。
ROLE_HELP: Dict[str, str] = {
    ROLE_X: "Which number runs across the bottom.",
    ROLE_Y: "Which number runs up the side.",
    ROLE_COLOR: "What the colour means. A category (region, row, column) "
                "gives each one its own colour; a number gives a light-to-"
                "dark scale.",
    ROLE_SIZE: "Which number the marker's size follows. Leave it empty for "
               "one size - size is the hardest channel to read, so use it "
               "only when the two axes are already spoken for.",
}

#: 每一種記號**非有不可**的角色。
REQUIRED: Dict[str, Tuple[str, ...]] = {
    MARK_POINT: (ROLE_X, ROLE_Y),
    MARK_LINE: (ROLE_X, ROLE_Y),
    MARK_BAR: (ROLE_X, ROLE_Y),
    MARK_BOX: (ROLE_X, ROLE_Y),
    # ⚠ **格子非有顏色不可。** 一片沒有顏色的格子什麼都沒說 —— 而它跟
    # 「還沒挑完」在畫面上長得一模一樣，所以它是必填而不是一個預設。
    MARK_CELL: (ROLE_X, ROLE_Y, ROLE_COLOR),
}

#: 每一種記號**用得到**的角色（沒列的收起來 —— 一格答了也沒用的設定比沒有
#: 那一格更糟，同 `export.GLOBAL_APPLIES` 那條規矩）。
#:
#: ⚠ **只有點用得到「大小」。** 一條線沒有大小，而一根長條的寬度是版面決定
#: 的、不是資料 —— 把值綁到寬度上等於畫出一張面積說謊的圖。
USES: Dict[str, Tuple[str, ...]] = {
    MARK_POINT: (ROLE_X, ROLE_Y, ROLE_COLOR, ROLE_SIZE),
    MARK_LINE: (ROLE_X, ROLE_Y, ROLE_COLOR),
    MARK_BAR: (ROLE_X, ROLE_Y, ROLE_COLOR),
    MARK_BOX: (ROLE_X, ROLE_Y, ROLE_COLOR),
    MARK_CELL: (ROLE_X, ROLE_Y, ROLE_COLOR),
}

#: 空的 spec（還沒設定）。
EMPTY: Dict[str, Any] = {"mark": MARK_POINT, ROLE_X: "", ROLE_Y: "",
                         ROLE_COLOR: "", ROLE_SIZE: ""}


def parse_spec(text: object) -> Dict[str, Any]:
    """JSON 字串 → ``{mark, x, y, color, size}``（缺的補空字串）。

    空字串／``None`` = 還沒設定，回 :data:`EMPTY` 的複本 —— 舊 recipe 沒有
    這一格也讀得動。
    """
    s = "" if text is None else str(text).strip()
    if isinstance(text, dict):
        raw: Dict[str, Any] = dict(text)
    elif not s:
        return dict(EMPTY)
    else:
        try:
            raw = json.loads(s)
        except ValueError as e:
            raise ChartSpecError(
                "the chart is not valid JSON (%s)" % e) from None
    if not isinstance(raw, dict):
        raise ChartSpecError('the chart should be a JSON object like '
                             '{"mark": "point", "x": "…", "y": "…"}')

    out = dict(EMPTY)
    for key, value in raw.items():
        name = str(key).strip()
        if name == "mark":
            mark = str(value or "").strip()
            if mark not in MARKS:
                raise ChartSpecError(
                    "'%s' is not a kind of mark; pick one of %s"
                    % (mark, ", ".join(MARKS)))
            out["mark"] = mark
            continue
        if name not in ROLES:
            raise ChartSpecError(
                "'%s' is not a role; pick one of %s"
                % (name, ", ".join(ROLES)))
        # ⚠ **欄名只驗是不是字串**，不驗它存不存在（見模組說明）。
        out[name] = "" if value is None else str(value).strip()
    return out


def format_spec(spec: object) -> str:
    """``{…}`` → 標準 JSON 字串（**排序過，所以 round-trip 穩定**）。

    什麼都沒設定就回空字串 —— 一份沒用到這張圖的 recipe 那一格是空的，
    diff 乾淨。
    """
    d = parse_spec(spec)
    if not any(str(d.get(r) or "") for r in ROLES):
        return ""
    clean = {"mark": d["mark"]}
    for role in ROLES:
        got = str(d.get(role) or "")
        # ⚠ **這一種記號用不到的角色不寫出去。** 一份折線圖的 spec 帶著一個
        # `size` 的話，換回散點時它會**突然生效**，而使用者不記得設過。
        # 規則住在這裡而不是編輯器：編輯器只是其中一個呼叫端，而手寫的
        # recipe 走的是 `validate_params`（它叫的正是這一支）。
        if got and role in USES.get(str(d["mark"]), ()):
            clean[role] = got
    return json.dumps(clean, sort_keys=True, separators=(",", ":"),
                      ensure_ascii=False)


def missing_roles(spec: object) -> List[str]:
    """這張圖**還缺哪幾個非有不可的角色**（空的就是全部缺）。

    這是「畫不出來」跟「還沒設定完」的分界，而呼叫端要說得出差別 ——
    一張空白的圖跟一句「還沒挑 Y 是哪一欄」是兩件事。
    """
    d = parse_spec(spec)
    return [r for r in REQUIRED.get(str(d["mark"]), ()) if not d.get(r)]


def uses(spec: object, role: str) -> bool:
    """這一種記號用不用得到這個角色（編輯器靠它收起來）。"""
    d = parse_spec(spec)
    return str(role) in USES.get(str(d["mark"]), ())


def describe(spec: object) -> str:
    """卡片那一格上顯示的一句話（參數格是唯讀的摘要，設定在編輯器裡改）。"""
    d = parse_spec(spec)
    need = missing_roles(d)
    if need:
        return "not set up yet - pick %s" % " and ".join(need)
    bits = ["%s, %s / %s" % (MARK_LABELS.get(d["mark"], d["mark"]),
                             d[ROLE_Y], d[ROLE_X])]
    if d.get(ROLE_COLOR):
        bits.append("coloured by %s" % d[ROLE_COLOR])
    if d.get(ROLE_SIZE):
        bits.append("sized by %s" % d[ROLE_SIZE])
    return " · ".join(bits)
