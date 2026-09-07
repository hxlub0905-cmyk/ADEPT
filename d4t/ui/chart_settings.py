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

from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QCheckBox, QColorDialog, QDialog, QDialogButtonBox, QDoubleSpinBox,
    QFrame, QGridLayout, QHBoxLayout, QLabel, QLineEdit, QPushButton,
    QScrollArea, QSpinBox, QTabWidget, QVBoxLayout, QWidget,
)

from ..core.export import uniformity_charts as uc
from ..core.pipeline import chart_style as cs
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
        self._paint()

    def value(self) -> str:
        return self._value

    def set_value(self, text: str) -> None:
        self._value = str(text or "")
        self._paint()

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


class ChartSettingsDialog(QDialog):
    """改 `chart_style` 那一格。``value()`` 回**格式化過的字串**。

    模態 —— 這裡沒有「一邊拉一邊看」（曲線編輯器那個理由不成立：這些是
    離散的設定，不是拖出來的形狀），而套用之後彈出視窗會當場重畫。
    """

    def __init__(self, look: str = "", kinds: Optional[Sequence[str]] = None,
                 parent: Optional[QWidget] = None):
        super().__init__(parent)
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
        apply_button_cursors(self)

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
        tabs = QTabWidget(box)
        # 四張分頁一定要同時看得見 —— 捲動箭頭後面那一張的標題就改不到了。
        tabs.setUsesScrollButtons(False)
        for kind in self._kinds:
            page = QWidget(tabs)
            grid = QGridLayout(page)
            grid.setHorizontalSpacing(10)
            grid.setVerticalSpacing(6)
            fields: Dict[str, QWidget] = {}
            for r, key in enumerate(cs.PER_CHART_KEYS):
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
            grid.setRowStretch(len(cs.PER_CHART_KEYS), 1)
            self.per[kind] = fields
            tabs.addTab(page, uc.CHART_LABELS.get(kind, kind))
        box.layout().addWidget(tabs, 1)
        return box

    # -- 值 -----------------------------------------------------------------
    def set_value(self, style: object) -> None:
        """把一份設定放進畫面上。缺的鍵＝預設（`chart_style.DEFAULTS`）。"""
        d = style if isinstance(style, dict) else cs.parse_style(style)
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
