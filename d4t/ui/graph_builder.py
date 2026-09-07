# -*- coding: utf-8 -*-
# d4t graph builder — authored 2026-09-07 (F88 第二刀).
"""**哪一欄放到哪一個角色上** —— `chart_spec` 那一格的編輯器。

為什麼它是插槽，不是一張圖表清單（計畫書 `docs/plans/F88-graph-builder.md` §5）
--------------------------------------------------------------------------
JMP 的 Graph Builder 之所以好用，是因為使用者想的是「我要看 A 跟 B 的關係」，
不是「我要一張散佈圖」。**先挑欄、圖自己長出來**比「先挑圖、再回答它問的
幾個問題」少一步猜測，而那一步正是不會寫 code 的製程工程師卡住的地方。

⚠ **這裡只挑欄，不決定長相。** 字級、線寬、顏色、鎖定範圍全都住在
`chart_style`（`Chart settings…` 那個對話框）。兩份分家的理由跟
`chart_spec` 模組說明上那一段一字不差：**畫什麼**與**長什麼樣**是兩個問題，
而把它們塞進同一個對話框的那天，那個對話框會變成一張沒有人讀得完的表。

⚠ **選單是從資料長出來的**（`Frame.columns`），不是一張寫死的清單。
所以這一份不認得 `glv_median` 這種字 —— 換一個 metric、換一張量測卡，
選單自己會變。寫死一份的那天，使用者的欄位在選單上找不到。

⚠ **預覽跟寫出去的走同一支** `build_chart_svg`（同 `ChartSettingsDialog`）。
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional, Sequence

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QComboBox, QDialog, QDialogButtonBox, QGridLayout, QLabel, QVBoxLayout,
    QWidget,
)

from ..core.export import uniformity_charts as uc
from ..core.pipeline import chart_spec as cspec
from .uniformity_window import ChartView, chart_style_for
from .widgets import ChoiceChips

__all__ = ["GraphBuilderDialog", "NONE_WORD", "PICK_WORD", "SpecEditor"]

#: 「空著」那一格顯示的字。**不是空白** —— 一個空的下拉讀起來是「壞了」。
NONE_WORD = "(none)"

#: 非有不可的那幾格**還沒挑**時顯示的字。跟 :data:`NONE_WORD` 是兩件事：
#: 「不用」是一個決定，「還沒挑」不是 —— 而兩個都對應到空字串，所以
#: `missing_roles` 說得出「這張圖還缺什麼」。
#:
#: ⚠ **不要拿第一欄當預設。** 第一版就是那樣：打開對話框，X 與 Y 都自動
#: 落在 `region` 上，於是一張沒有人設定過的圖看起來像設定好了 ——
#: 而它畫出來是一團疊在同一個點上的圓。
PICK_WORD = "(pick one)"

#: 哪幾個角色只吃數字。類別（區域名、第幾列、第幾欄）落在 X 上是有意思的
#: （一排點），落在**大小**上不是 —— 「region B 比 region A 大」沒有意義。
NUMERIC_ONLY = (cspec.ROLE_SIZE,)

#: 每一種記號的圖示（`ui.glyphs`）。**一格選項＝一排膠囊（圖 + 字）**，
#: 不是下拉 —— 這是 F68 那條規矩，而它在這裡尤其站得住腳：三種記號講的正是
#: 「這張圖長什麼形狀」，那本來就畫得出來。
#:
#: ⚠ **盒子與格子借的是既有的兩張圖**（`whisk_on` / `cells_equal`）。它們畫的
#: 正是這兩種記號，而 `ui.glyphs` 是一套**共用的字彙**，不是一張一對一的表 ——
#: 再畫兩張長得幾乎一樣的圖，維護的人以後要猜哪一張才是「真的那個盒子」。
MARK_ICONS = {cspec.MARK_POINT: "mark_dots",
              cspec.MARK_LINE: "mark_line",
              cspec.MARK_BAR: "mark_bars",
              cspec.MARK_BOX: "whisk_on",
              cspec.MARK_CELL: "cells_equal"}


class SpecEditor(QWidget):
    """一排記號 ＋ 四個角色，一列一個下拉。``spec()`` 回**格式化過的字串**。"""

    #: 記號換了 —— 呼叫端要重畫預覽（下拉自己的 `currentTextChanged` 蓋不到
    #: 這一顆，而換記號會改變整張圖的長相）。
    changed = Signal()

    def __init__(self, spec: str = "", columns: Optional[Sequence[str]] = None,
                 parent: Optional[QWidget] = None,
                 numeric: Optional[Sequence[str]] = None):
        super().__init__(parent)
        self._cols = [str(c) for c in (columns or ())]
        # 沒說哪幾欄是數字就當全部都是 —— 少一份資料不該讓選單變空的。
        self._numeric = ([str(c) for c in numeric]
                         if numeric is not None else list(self._cols))
        try:
            got = cspec.parse_spec(spec)
        except cspec.ChartSpecError:
            got = dict(cspec.EMPTY)
        self._mark = str(got.get("mark") or cspec.MARK_POINT)

        grid = QGridLayout(self)
        grid.setContentsMargins(0, 0, 0, 0)
        grid.setHorizontalSpacing(10)
        grid.setVerticalSpacing(6)
        grid.setColumnStretch(1, 1)
        self.boxes: Dict[str, QComboBox] = {}
        self._labels: Dict[str, QLabel] = {}
        row = 0

        # ⚠ **只有一種記號的時候不問。** 一格答了也沒用的設定比沒有那一格更糟
        # （第二刀就是這樣：那時 `MARKS` 只有 `point`）。
        self.marks: Optional[ChoiceChips] = None
        if len(cspec.MARKS) > 1:
            lab = QLabel("Drawn as", self)
            self.marks = ChoiceChips(
                list(cspec.MARKS),
                [MARK_ICONS.get(m, "mark_dots") for m in cspec.MARKS],
                self._mark, helps=dict(cspec.MARK_HELP),
                labels=dict(cspec.MARK_LABELS), parent=self)
            self.marks.changed.connect(self._on_mark)
            grid.addWidget(lab, row, 0)
            grid.addWidget(self.marks, row, 1)
            row += 1

        for role in cspec.ROLES:
            lab = QLabel(_role_word(role), self)
            lab.setToolTip(cspec.ROLE_HELP[role])
            self._labels[role] = lab
            box = QComboBox(self)
            box.setToolTip(cspec.ROLE_HELP[role])
            for text in self._choices(role):
                box.addItem(text)
            want = str(got.get(role) or "")
            box.setCurrentIndex(max(0, box.findText(want) if want else 0))
            self.boxes[role] = box
            grid.addWidget(lab, row, 0)
            grid.addWidget(box, row, 1)
            row += 1
        if not self.boxes:                      # pragma: no cover — 封閉字彙
            grid.addWidget(QLabel("nothing to set up here", self), 0, 0, 1, 2)
        self._grid = grid
        self._sync_roles()

    def _on_mark(self, mark: str) -> None:
        self._mark = str(mark)
        self._sync_roles()
        self.changed.emit()

    def _sync_roles(self) -> None:
        """換了記號 → **用不到的角色收起來**（`chart_spec.USES`）。

        ⚠ 收起來**不等於清掉**：把記號換成折線再換回來，原本挑的「大小」
        還在（同 `ChartSettingsDialog` 那條「沒顯示的覆寫要留著」）。
        欄位留在 widget 上，只是不顯示 —— 而 :meth:`spec` 會問 `uses`，
        所以存出去的那一份不會帶著一個這種記號用不到的角色。
        """
        for role, box in self.boxes.items():
            on = cspec.uses({"mark": self._mark}, role)
            box.setVisible(on)
            lab = self._labels.get(role)
            if lab is not None:
                lab.setVisible(on)

    def _choices(self, role: str) -> List[str]:
        """這一個角色挑得到哪幾欄。

        第一格是「還沒挑」（見 :data:`PICK_WORD` / :data:`NONE_WORD`）——
        必填的那幾個角色講的是「還沒挑」，選填的講的是「不用」。
        """
        pool = (self._numeric if role in NUMERIC_ONLY else self._cols)
        need = role in cspec.REQUIRED.get(self._mark, ())
        return [PICK_WORD if need else NONE_WORD] + list(pool)

    def spec(self) -> str:
        out: Dict[str, Any] = {"mark": self._mark}
        for role, box in self.boxes.items():
            # 用不到的角色由 `format_spec` 丟掉（規則只有一份，住在那裡）——
            # 這裡照樣把每一格填進去，那是「收起來不等於清掉」的另一半：
            # 換回散點時原本挑的「大小」還在畫面上。
            text = str(box.currentText())
            out[role] = "" if text in (NONE_WORD, PICK_WORD) else text
        return cspec.format_spec(out)


def _role_word(role: str) -> str:
    """角色的名字。**不是那個鍵** —— ``x`` 對製程工程師不是一句話。"""
    return {cspec.ROLE_X: "Across the bottom",
            cspec.ROLE_Y: "Up the side",
            cspec.ROLE_COLOR: "Colour means",
            cspec.ROLE_SIZE: "Size means"}.get(str(role), str(role))


class GraphBuilderDialog(QDialog):
    """`SpecEditor` ＋ **一張跟著改的預覽**。``value()`` 回那一格的新字串。"""

    #: 預覽那一塊的高度（跟 `ChartSettingsDialog.PREVIEW_H` 同一個尺度）。
    PREVIEW_H = 260

    def __init__(self, spec: str = "", frame: Any = None,
                 parent: Optional[QWidget] = None, look: str = "",
                 metric: str = ""):
        super().__init__(parent)
        self.setWindowTitle("Chart")
        self.setModal(True)
        self.resize(560, 620)
        self._frame = frame
        self._look = str(look or "")
        self._metric = str(metric or "")

        cols = list(getattr(frame, "columns", ()) or ())
        numeric = list(getattr(frame, "numeric_columns", lambda: cols)())

        root = QVBoxLayout(self)
        root.setContentsMargins(12, 10, 12, 12)
        root.setSpacing(8)

        head = QLabel("Pick which measured number goes where. The chart "
                      "below follows what you pick.", self)
        head.setObjectName("paramHint")
        head.setWordWrap(True)
        root.addWidget(head)

        self.editor = SpecEditor(spec, cols, self, numeric=numeric)
        root.addWidget(self.editor)
        for box in self.editor.boxes.values():
            box.currentTextChanged.connect(self.refresh_preview)
        # 換記號也要重畫 —— 那顆膠囊改的是整張圖的長相，不只是一格。
        self.editor.changed.connect(self.refresh_preview)

        self.view = ChartView(uc.CHART_CUSTOM, self)
        self.view.setMinimumHeight(self.PREVIEW_H)
        root.addWidget(self.view, 1)

        buttons = QDialogButtonBox(
            QDialogButtonBox.Ok | QDialogButtonBox.Cancel, parent=self)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        root.addWidget(buttons)
        self.refresh_preview()

    def refresh_preview(self, *_a) -> None:
        """**畫不出來就讓它說出原因** —— `chart_draw` 已經會畫那句話
        （「pick x and y to draw this chart」），所以這裡什麼都不擋。"""
        self.view.set_data(
            {}, chart_style_for(self._look, uc.CHART_CUSTOM, uc.AXIS_X,
                                self._metric),
            frame=self._frame, spec=self.editor.spec())

    def value(self) -> str:
        return self.editor.spec()
