# -*- coding: utf-8 -*-
# d4t chart settings dialog — authored 2026-09-07 (F87).
"""PEAR 那個 **Chart settings** 對話框的 d4t 版。

版型：一列一個東西，屬性橫著擺
------------------------------
PEAR 那個對話框的價值有一半在排列方式 —— **「刻度上的數字」是一列，
它的大小／粗體／顏色橫著排在同一列上**。攤成「字級」「粗體」「顏色」
三列的話，讀的人要先在腦裡把它們兜回同一個東西才看得懂。

所以列怎麼分不是這一份決定的，是 `core.pipeline.chart_style.ROWS` ——
那是「這一組設定怎麼分群」，跟畫面用什麼元件無關（同 `decide_tree` 的立場）。
這一份只負責**把那張表變成 widget**。

三條規矩
--------
1. **上下界只有一份** —— 每一格的範圍問 `chart_style.bounds()`，不在這裡抄。
   抄一份的那天，使用者打得進一個滑桿拉不到的值（或反過來）。
2. **顏色的預設是「自動」不是某個色碼** —— 空字串＝跟著區域色走。所以每一
   格顏色是「一顆色塊 ＋ 一顆 ×」：× 才是回到自動的路，而它要**看得見**
   （藏在右鍵裡的功能對不會寫 code 的人等於不存在）。
3. **沒顯示的覆寫要留著** —— 使用者把熱圖取消勾選之後再來調設定，熱圖的
   標題不該被這個對話框安靜地清掉。它們原封不動搬回輸出（`_extra`）。
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional, Sequence

from PySide6.QtCore import Signal
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QCheckBox, QColorDialog, QDialog, QDialogButtonBox, QDoubleSpinBox,
    QFrame, QGridLayout, QHBoxLayout, QLabel, QLineEdit, QPushButton,
    QScrollArea, QSpinBox, QTabWidget, QVBoxLayout, QWidget,
)

from ..core.export import uniformity_charts as uc
from ..core.pipeline import chart_style as cs
from .uniformity_window import ChartView, chart_style_for
from .theme import TOKENS
from .widgets import apply_button_cursors, small_button

__all__ = ["ChartSettingsDialog", "ColourButton"]

#: 只收整數的那幾格（柱子數、刻度數）—— 「24.5 根柱子」沒有意思。
_INT_KEYS = ("bins", "xticks", "yticks")

#: 每一格旁邊那一句（tooltip）。**每一格都要有一句**（鐵則 3 的精神：
#: 這裡不是 ParamSpec，但看的人是同一批）。
_TIPS: Dict[str, str] = {
    "tick_size": "How big the numbers along the axes are.",
    "tick_bold": "Make those numbers bold.",
    "tick_color": "Colour of those numbers. Empty follows the theme.",
    "axis_size": "How big the axis names and the chart frame text are.",
    "axis_bold": "Make the axis names bold.",
    "axis_color": "Colour of the axis names. Empty follows the theme.",
    "point_size": "Radius of the dot drawn for each box.",
    "point_color": "Colour of those dots. Empty follows each region's colour.",
    "line_width": "Thickness of the trend line, the median line and the box "
                  "outlines.",
    "line_color": "Colour of those lines. Empty follows each region's colour.",
    "value_name": "What the value axis is called. Empty uses the metric's "
                  "own name.",
    "bins": "How many bars the histogram is cut into.",
    "xticks": "How many labelled ticks along the bottom.",
    "yticks": "How many labelled ticks up the side.",
    "points": "Draw a dot for every box. Turn it off when there are hundreds "
              "of boxes and they smear together.",
    "whiskers": "Draw the whiskers on the box plot.",
    "percent": "Histogram shows share of boxes instead of a count. Use it "
               "when two regions have very different box counts.",
    "equal_cells": "Draw the heat map as a plain grid - every cell the same "
                   "size, one slot per row and column. That is what a die map "
                   "looks like, and it is what makes two cells comparable at "
                   "a glance. Turn it off to draw each cell true to scale "
                   "(area then follows the spacing, which this chart is not "
                   "measuring). The heat painted on the image is always true "
                   "to scale - it has to line up with the picture.",
    "map_values": "Print the number inside each heat map cell, where the cell "
                  "is wide enough to hold it.",
    "lock": "Pin the value scale to the range below, so two runs can be put "
            "side by side. Off means every chart picks its own range - which "
            "is right for one run and misleading for two.",
    "lo": "Bottom of the locked value scale.",
    "hi": "Top of the locked value scale.",
}

#: 每張圖那五格在畫面上的字。
_PER_LABELS: Dict[str, str] = {
    "title": "Title",
    "xlabel": "Bottom axis name",
    "ylabel": "Side axis name",
    "xticks": "Ticks across",
    "yticks": "Ticks up the side",
}

_PER_TIPS: Dict[str, str] = {
    "title": "Line of text above this chart. Empty uses the chart's name.",
    "xlabel": "Name of the bottom axis on this chart.",
    "ylabel": "Name of the side axis on this chart.",
    "xticks": "How many labelled ticks along the bottom of this chart.",
    "yticks": "How many labelled ticks up the side of this chart.",
}


class ColourButton(QWidget):
    """一顆色塊 ＋ 一顆 ×。空字串＝**自動**（跟著區域色／主題走）。"""

    #: 值變了（即時預覽接這個）。
    changed = Signal(str)

    #: 色塊最小寬度 —— 高度是 QSS 的事，這一個是「`auto` 四個字要放得下」。
    SWATCH_W = 58

    def __init__(self, value: str = "", tip: str = "",
                 parent: Optional[QWidget] = None):
        super().__init__(parent)
        lay = QHBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(4)
        self._value = str(value or "")
        # **尺寸交給 QSS 的 `shape`，不寫在這裡**（F7-23：以前六個呼叫端各自
        # 寫死一組，於是同一種視覺語言沒有兩顆一樣大）。這裡只說寬一點的那顆
        # 至少要放得下 `auto` 那四個字。
        self.swatch = small_button("", tip=tip, shape="wide", parent=self)
        self.swatch.setMinimumWidth(self.SWATCH_W)
        self.swatch.clicked.connect(self._pick)
        self.clear_btn = small_button(
            "\u00d7", tip="Back to the automatic colour", shape="square",
            parent=self)
        self.clear_btn.clicked.connect(lambda: self.set_value(""))
        lay.addWidget(self.swatch, 0)
        lay.addWidget(self.clear_btn, 0)
        lay.addStretch(1)
        self.setMinimumWidth(self.SWATCH_W + 4 + 24)
        self._paint()          # 建構時只畫，不發訊號（還沒有人接）

    def value(self) -> str:
        return self._value

    def set_value(self, text: str) -> None:
        text = str(text or "")
        if text == self._value:
            return
        self._value = text
        self._paint()
        self.changed.emit(self._value)

    #: 兩顆都自己帶底 —— QSS 的 ``ghost`` 是**透明**的，套在這裡的話
    #: 「auto」那一格讀起來像一行字，而它是按得下去的東西（推廣鐵則：
    #: 看不出是按鈕的按鈕等於沒有）。
    _FRAME = "border:1px solid %s;border-radius:4px;" % TOKENS["border_input"]

    def _paint(self) -> None:
        if self._value:
            self.swatch.setText("")
            self.swatch.setStyleSheet("background:%s;%s"
                                      % (self._value, self._FRAME))
        else:
            self.swatch.setText("auto")
            self.swatch.setStyleSheet(
                "background:%s;color:%s;%s"
                % (TOKENS["bg_surface"], TOKENS["text_hint"], self._FRAME))
        self.clear_btn.setEnabled(bool(self._value))
        self.clear_btn.setStyleSheet(
            "background:%s;color:%s;%s"
            % (TOKENS["bg_surface"],
               TOKENS["text_primary"] if self._value
               else TOKENS["text_disabled"], self._FRAME))

    def _pick(self) -> None:
        start = QColor(self._value) if self._value else QColor("#5fd0a0")
        got = QColorDialog.getColor(start, self, "Pick a colour")
        if got.isValid():
            self.set_value(got.name())


def _caption(text: str, parent: QWidget) -> QLabel:
    lab = QLabel(str(text), parent)
    lab.setObjectName("paramHint")
    return lab


def _number(key: str, parent: QWidget) -> QWidget:
    """一格數字 —— 範圍問 `chart_style.bounds()`，不在這裡寫死。"""
    lo, hi = cs.bounds(key) or (0.0, 1.0)
    if key in _INT_KEYS:
        box = QSpinBox(parent)
        box.setRange(int(lo), int(hi))
        box.setValue(int(cs.DEFAULTS[key]))
    else:
        box = QDoubleSpinBox(parent)
        box.setDecimals(1)
        box.setSingleStep(0.5)
        box.setRange(float(lo), float(hi))
        box.setValue(float(cs.DEFAULTS[key]))
    box.setFixedWidth(78)
    if _TIPS.get(key):
        box.setToolTip(_TIPS[key])
    return box


def _num_value(box: QWidget) -> Any:
    v = box.value()
    return int(v) if isinstance(box, QSpinBox) else round(float(v), 4)


def _sample_series() -> Dict[str, Any]:
    """預覽用的樣本 —— **兩個區域、有斜率、有一顆離群**。

    為什麼不是隨便一組數字：這幾格設定要調的東西各自需要不同的東西才看得出
    來 —— 顏色要**兩群**、`slope` 那條線要有斜度、盒鬚的鬚要有離群點、
    直方圖的柱數要有足夠的框。一組平的資料會讓半數設定「看起來沒反應」。
    """
    from ..core.export import uniformity_charts as uc

    # ⚠ **格子數要少**：預覽只有 380×210，12 欄的話一格只剩 20 px —— 那個
    # 尺寸下什麼都看不出來，而「每一格裡印出值」那一格會**看起來沒反應**
    # （它有一條「放不下就不印」的規矩，印一半的數字比不印糟）。
    # 3×3 兩群 = 6 欄，一格約 40 px，剛好放得下一個數字。
    notes = []
    for k, (name, base, x0) in enumerate(
            (("region A", 112.0, 40), ("region B", 124.0, 340))):
        n = 9
        vals = [base + 1.4 * (i % 3) + 2.6 * (i // 3) for i in range(n)]
        vals[4] += 6.0 if k == 0 else -5.0          # 一顆離群，鬚才看得出來
        notes.append({"region": name, "prefix": name, "spread": {
            "stats": {"value": vals},
            "cx": [float(x0 + 80 * (i % 3)) for i in range(n)],
            "cy": [float(40 + 80 * (i // 3)) for i in range(n)],
            "rects": [[x0 + 80 * (i % 3), 40 + 80 * (i // 3), 56, 56]
                      for i in range(n)],
            "boxes": list(range(n))}})
    return uc.chart_series(notes, "value")


class ChartSettingsDialog(QDialog):
    """改 `chart_style` 那一格。``value()`` 回**格式化過的字串**。

    模態 —— 這裡沒有「一邊拉一邊看」（曲線編輯器那個理由不成立：這些是
    離散的設定，不是拖出來的形狀），而套用之後彈出視窗會當場重畫。
    """

    #: 每一張預覽至少多高（再矮就只剩一團色塊）。
    PREVIEW_H = 210

    def __init__(self, look: str = "", kinds: Optional[Sequence[str]] = None,
                 parent: Optional[QWidget] = None,
                 series: Optional[Dict[str, Any]] = None,
                 axis: str = uc.AXIS_X):
        super().__init__(parent)
        #: profile 沿哪一個軸（只影響那一張）—— 卡片上那一格說了算。
        self._axis = str(axis or uc.AXIS_X)
        #: 預覽吃的那一顆。沒給就用內建的樣本 —— 一個**空**的預覽區讀起來是
        #: 「壞了」，而使用者調的是外觀，樣本足以看出每一格的效果。
        #: 是不是樣本會寫在預覽上方（不然他會以為那是自己的資料）。
        self._series = dict(series or {})
        self._is_sample = not (self._series.get("groups") or [])
        if self._is_sample:
            self._series = _sample_series()
        self._live = True
        self.setWindowTitle("Chart settings")
        self.setModal(True)
        self.resize(1020, 680)

        self._kinds: List[str] = [k for k in (kinds if kinds is not None
                                              else uc.CHARTS) if k in uc.CHARTS]
        try:
            style = cs.parse_style(look)
        except cs.ChartStyleError:
            style = {}
        # 沒顯示在這個對話框上的每張圖覆寫（見檔頭第 3 條）——原封不動帶回去。
        self._extra = {k: v for k, v in style.items()
                       if "." in str(k) and str(k).split(".", 1)[0]
                       not in self._kinds}

        self.globals: Dict[str, QWidget] = {}
        self.per: Dict[str, Dict[str, QWidget]] = {}
        self.views: Dict[str, ChartView] = {}

        root = QVBoxLayout(self)
        root.setContentsMargins(12, 12, 12, 12)
        root.setSpacing(8)

        head = QLabel(
            "How the four charts look. Everything here travels with the "
            "recipe, so the next run - and anyone you hand the recipe to - "
            "gets the same charts.", self)
        head.setWordWrap(True)
        head.setObjectName("paramHint")
        root.addWidget(head)

        # **兩欄。** 一欄疊下來的話「每張圖自己的字」整段落在摺線底下 ——
        # 而那正是使用者指名要的那一段（標題、軸名）。左邊是「四張圖共用的
        # 長相」，右邊是「這一張自己的字」，兩句話各佔一欄。
        body = QWidget(self)
        inner = QHBoxLayout(body)
        inner.setContentsMargins(0, 0, 0, 0)
        inner.setSpacing(12)
        left = QVBoxLayout()
        left.setSpacing(12)
        left.addWidget(self._look_group(body))
        left.addWidget(self._numbers_group(body))
        left.addWidget(self._scale_group(body))
        left.addStretch(1)
        inner.addLayout(left, 3)
        right = self._per_chart_group(body)
        # 分頁列擠到要出捲動箭頭的話，第四張圖（Heat map）就藏起來了 ——
        # 一張看不到的分頁等於那張圖的標題改不了。
        right.setMinimumWidth(430)
        inner.addWidget(right, 2)

        scroll = QScrollArea(self)
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        scroll.setWidget(body)
        root.addWidget(scroll, 1)

        buttons = QDialogButtonBox(
            QDialogButtonBox.Ok | QDialogButtonBox.Cancel, parent=self)
        reset = QPushButton("Reset to defaults", self)
        reset.setToolTip("Put every setting on this page back to the way it "
                         "started. Nothing is written until you press OK.")
        reset.clicked.connect(self.reset)
        buttons.addButton(reset, QDialogButtonBox.ResetRole)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        root.addWidget(buttons)

        self.set_value(style)
        self._connect_live()
        self.refresh_preview()
        apply_button_cursors(self)

    # -- 即時預覽 -----------------------------------------------------------
    def _connect_live(self) -> None:
        """每一格改動 → 重畫預覽。

        ⚠ **逐個型別接**，不要用一支泛用的 ``QWidget.changed`` —— Qt 沒有那個
        東西，而漏接一種的下場是那一格「調了沒反應」，比沒有預覽更糟
        （使用者會以為那個設定壞了）。有一條測試逐格檢查每一個 widget 都接上
        了（`test_every_editor_moves_the_preview`）。
        """
        for w in list(self.globals.values()) + [
                e for f in self.per.values() for e in f.values()]:
            if isinstance(w, ColourButton):
                w.changed.connect(self.refresh_preview)
            elif isinstance(w, QCheckBox):
                w.toggled.connect(self.refresh_preview)
            elif isinstance(w, QLineEdit):
                w.textChanged.connect(self.refresh_preview)
            elif isinstance(w, (QSpinBox, QDoubleSpinBox)):
                w.valueChanged.connect(self.refresh_preview)

    def set_series(self, series: Optional[Dict[str, Any]]) -> None:
        """換一份預覽資料（`Chart look` 那一列由 Studio 餵這一顆的）。"""
        got = dict(series or {})
        self._is_sample = not (got.get("groups") or [])
        self._series = _sample_series() if self._is_sample else got
        self.refresh_preview()

    def refresh_preview(self, *_a) -> None:
        """把現在畫面上的設定畫成圖。**壞值不准擋路** —— 使用者正在打字，
        中途一定會經過打不完的狀態。"""
        if not self._live or not self.views:
            return
        try:
            style = self.value()
        except Exception:                  # noqa: BLE001 — 見 docstring
            return
        metric = str(self._series.get("metric") or "")
        for kind, view in self.views.items():
            try:
                # **跟寫出去的走同一支**（`chart_style_for`）。直接叫
                # `chart_style.style_for` 的那一版少了卡片那一半，於是
                # `Name of the value axis` 那一格在預覽上完全沒有反應。
                view.set_data(self._series,
                              chart_style_for(style, kind, self._axis, metric))
            except Exception:              # noqa: BLE001 — 鐵則 7 的 UI 版
                continue

    # -- 版型 ---------------------------------------------------------------
    def _section(self, title: str, parent: QWidget) -> QFrame:
        box = QFrame(parent)
        box.setObjectName("card")
        lay = QVBoxLayout(box)
        lay.setContentsMargins(10, 8, 10, 10)
        lay.setSpacing(6)
        lab = QLabel(str(title), box)
        lab.setObjectName("inspectorHeader")
        lay.addWidget(lab)
        return box

    def _look_group(self, parent: QWidget) -> QFrame:
        """`chart_style.ROWS` → 一列一個東西，屬性橫著擺。"""
        box = self._section("Text, dots and lines", parent)
        grid = QGridLayout()
        grid.setHorizontalSpacing(10)
        grid.setVerticalSpacing(6)
        # **同一種東西要在同一欄**：`Data points` 只有兩格，而它的「colour」
        # 若跟著往左靠，就會落在上面兩列的「bold」底下 —— 四列讀起來像四種
        # 不同的表。所以顏色固定在最後一欄，其餘的由左往右填。
        slots = max(len(props) for _t, props in cs.ROWS)
        for r, (title, props) in enumerate(cs.ROWS):
            name = QLabel(str(title), box)
            name.setMinimumWidth(96)
            grid.addWidget(name, r, 0)
            left = 0
            for key, column in props:
                if key.endswith("_color"):
                    i = slots - 1
                else:
                    i = left
                    left += 1
                grid.addWidget(_caption(column, box), r, 1 + i * 2)
                if key.endswith("_color"):
                    w = ColourButton(cs.DEFAULTS[key], _TIPS.get(key, ""), box)
                elif key in cs.DEFAULTS and isinstance(cs.DEFAULTS[key], bool):
                    w = QCheckBox("", box)
                    w.setToolTip(_TIPS.get(key, ""))
                else:
                    w = _number(key, box)
                self.globals[key] = w
                grid.addWidget(w, r, 2 + i * 2)
        grid.setColumnStretch(1 + slots * 2, 1)
        box.layout().addLayout(grid)
        return box

    def _row(self, grid: QGridLayout, r: int, key: str, title: str,
             owner: QWidget, editor: QWidget) -> None:
        lab = QLabel(str(title), owner)
        lab.setMinimumWidth(160)
        if _TIPS.get(key):
            lab.setToolTip(_TIPS[key])
            editor.setToolTip(_TIPS[key])
        grid.addWidget(lab, r, 0)
        grid.addWidget(editor, r, 1)
        grid.setColumnStretch(2, 1)
        self.globals[key] = editor

    def _numbers_group(self, parent: QWidget) -> QFrame:
        box = self._section("What is drawn", parent)
        grid = QGridLayout()
        grid.setHorizontalSpacing(10)
        grid.setVerticalSpacing(6)
        name = QLineEdit(box)
        name.setPlaceholderText("the metric's own name")
        self._row(grid, 0, "value_name", "Name of the value axis", box, name)
        self._row(grid, 1, "bins", "Histogram bars", box, _number("bins", box))
        self._row(grid, 2, "xticks", "Ticks across",
                  box, _number("xticks", box))
        self._row(grid, 3, "yticks", "Ticks up the side",
                  box, _number("yticks", box))
        self._row(grid, 4, "points", "A dot for every box",
                  box, QCheckBox("", box))
        self._row(grid, 5, "whiskers", "Whiskers on the box plot",
                  box, QCheckBox("", box))
        self._row(grid, 6, "percent", "Histogram in %",
                  box, QCheckBox("", box))
        self._row(grid, 7, "equal_cells", "Heat map: every cell the same size",
                  box, QCheckBox("", box))
        self._row(grid, 8, "map_values", "Heat map: print the value in each cell",
                  box, QCheckBox("", box))
        box.layout().addLayout(grid)
        return box

    def _scale_group(self, parent: QWidget) -> QFrame:
        box = self._section("Value scale", parent)
        why = QLabel(
            "Leave this off for one run. Turn it on when two runs have to be "
            "read side by side - otherwise each chart picks its own range and "
            "two bars of the same height mean different things.", box)
        why.setWordWrap(True)
        why.setObjectName("paramHint")
        box.layout().addWidget(why)
        grid = QGridLayout()
        grid.setHorizontalSpacing(10)
        grid.setVerticalSpacing(6)
        lock = QCheckBox("", box)
        self._row(grid, 0, "lock", "Lock the scale", box, lock)
        self._row(grid, 1, "lo", "Bottom", box, _number("lo", box))
        self._row(grid, 2, "hi", "Top", box, _number("hi", box))
        for key in ("lo", "hi"):
            self.globals[key].setDecimals(3)
            self.globals[key].setSingleStep(1.0)
        lock.toggled.connect(self._sync_lock)
        box.layout().addLayout(grid)
        return box

    def _sync_lock(self, on: bool) -> None:
        for key in ("lo", "hi"):
            self.globals[key].setEnabled(bool(on))

    def _per_chart_group(self, parent: QWidget) -> QWidget:
        box = self._section("Each chart's own words", parent)
        if self._is_sample:
            said = QLabel("Previews below use sample data - your run's "
                          "numbers are not loaded here.", box)
            said.setWordWrap(True)
            said.setObjectName("paramHint")
            box.layout().addWidget(said)
        tabs = QTabWidget(box)
        # 四張分頁一定要同時看得見 —— 捲動箭頭後面那一張的標題就改不到了。
        tabs.setUsesScrollButtons(False)
        for kind in self._kinds:
            page = QWidget(tabs)
            grid = QGridLayout(page)
            grid.setHorizontalSpacing(10)
            grid.setVerticalSpacing(6)
            fields: Dict[str, QWidget] = {}
            keys = [k for k in cs.PER_CHART_KEYS
                    if k in uc.PER_CHART_APPLIES.get(kind, cs.PER_CHART_KEYS)]
            for r, key in enumerate(keys):
                lab = QLabel(_PER_LABELS.get(key, key), page)
                lab.setMinimumWidth(120)
                lab.setToolTip(_PER_TIPS.get(key, ""))
                if key in ("xticks", "yticks"):
                    lo, hi = cs.bounds(key) or (2.0, 20.0)
                    w = QSpinBox(page)
                    # 最小值 −1 當「沒有覆寫」——  specialValueText 讓那一格
                    # 說出來，而不是留一個看起來像 1 的數字。
                    w.setRange(int(lo) - 1, int(hi))
                    w.setSpecialValueText("same for all")
                    w.setValue(int(lo) - 1)
                    w.setFixedWidth(120)
                else:
                    w = QLineEdit(page)
                    w.setPlaceholderText("the chart decides")
                w.setToolTip(_PER_TIPS.get(key, ""))
                grid.addWidget(lab, r, 0)
                grid.addWidget(w, r, 1)
                fields[key] = w
            grid.setColumnStretch(1, 1)
            # **即時預覽**（使用者 2026-09-07：「Chart setting 我是希望能支援
            # 即時 preview（在編輯器內就可以預覽）」）。放在**這一張圖自己的
            # 分頁裡**：你在改 Box plot 的標題，那張 Box plot 就在正下方。
            # 全域那幾格（字級、顏色、線寬）也會當場反映在這一張上。
            view = ChartView(kind, page)
            view.setMinimumHeight(self.PREVIEW_H)
            grid.addWidget(view, len(keys), 0, 1, 2)
            grid.setRowStretch(len(keys), 1)
            self.views[kind] = view
            self.per[kind] = fields
            tabs.addTab(page, uc.CHART_LABELS.get(kind, kind))
        box.layout().addWidget(tabs, 1)
        return box

    # -- 值 -----------------------------------------------------------------
    def set_value(self, style: object) -> None:
        """把一份設定放進畫面上。缺的鍵＝預設（`chart_style.DEFAULTS`）。"""
        d = style if isinstance(style, dict) else cs.parse_style(style)
        # 灌值的時候先關掉預覽：二十幾格各觸發一次，畫面會抖一下，而中途那
        # 幾張畫的是**半套**設定。最後統一畫一次。
        was, self._live = self._live, False
        for key, w in self.globals.items():
            got = d.get(key, cs.DEFAULTS[key])
            if isinstance(w, ColourButton):
                w.set_value(str(got or ""))
            elif isinstance(w, QCheckBox):
                w.setChecked(bool(got))
            elif isinstance(w, QLineEdit):
                w.setText(str(got or ""))
            else:
                w.setValue(int(got) if isinstance(w, QSpinBox) else float(got))
        self._sync_lock(bool(self.globals["lock"].isChecked()))
        for kind, fields in self.per.items():
            for key, w in fields.items():
                got = d.get("%s.%s" % (kind, key))
                if isinstance(w, QSpinBox):
                    w.setValue(int(got) if got is not None else w.minimum())
                else:
                    w.setText(str(got or ""))
        self._live = was
        self.refresh_preview()

    def reset(self) -> None:
        """全部回預設 —— **包含收起來的那些覆寫**（按鈕上就是這樣寫的）。"""
        self._extra = {}
        self.set_value({})

    def value(self) -> str:
        """畫面上的東西 → `chart_style` 那一格的字串（只含跟預設不一樣的）。"""
        out: Dict[str, Any] = dict(self._extra)
        for key, w in self.globals.items():
            if isinstance(w, ColourButton):
                out[key] = w.value()
            elif isinstance(w, QCheckBox):
                out[key] = bool(w.isChecked())
            elif isinstance(w, QLineEdit):
                out[key] = w.text().strip()
            else:
                out[key] = _num_value(w)
        for kind, fields in self.per.items():
            for key, w in fields.items():
                if isinstance(w, QSpinBox):
                    if w.value() > w.minimum():
                        out["%s.%s" % (kind, key)] = int(w.value())
                else:
                    text = w.text().strip()
                    if text:
                        out["%s.%s" % (kind, key)] = text
        return cs.format_style(out)
