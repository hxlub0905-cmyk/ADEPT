# -*- coding: utf-8 -*-
# d4t uniformity chart window — authored 2026-09-07 (F87).
"""均勻度那四張圖**自己的視窗**。

為什麼不塞在右側儀表裡（使用者 2026-09-07：「右側 Uniformity folder 直接把
預覽的圖放上來好像也很奇怪」）
------------------------------------------------------------------------
同意，而且理由有三個：

1. **讀不動** —— 那個面板窄，四張排成 2×2 每張只剩約 250×180；
2. **破壞節奏** —— 另外三張 Output 儀表都是一份乾淨的「會寫哪幾個檔」清單；
3. **答錯了問題** —— 那一排儀表回答的是「按下去會發生什麼」，不是
   「結果長怎樣」。

把圖塞進去是繞路，不是設計：它們在 UI 裡**沒有別的家**，所以就近放了。
這一份就是那個家。先例是畫布自己的彈出視窗（F8-UI D 案，`canvas.popout_requested`）。

⚠ **這裡不畫任何一張圖。** 圖是 `core/export/uniformity_charts` 產的 SVG，
這一份只把**同一個字串**畫到畫面上（`QSvgRenderer`）—— 畫面上看到的跟寫出去
的逐位元組相同。那是 F85 §4.4 的結論，而它是這整個功能最重要的不變量：
「畫面上的圖跟報表裡的圖不一樣，而兩張都畫得出來」是這個 repo 最貴的那種 bug。
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional, Sequence

from PySide6.QtCore import QRectF, Qt, Signal
from PySide6.QtGui import QColor, QPainter
from PySide6.QtWidgets import (
    QGridLayout, QHBoxLayout, QLabel, QSizePolicy, QVBoxLayout, QWidget,
)

from ..core.export import uniformity_charts as uc
from .theme import TOKENS
from .widgets import small_button

__all__ = ["ChartView", "UniformityWindow", "chart_style_for", "fit_into"]


def chart_style_for(look: str, kind: str, axis: str = uc.AXIS_X,
                    metric: str = "") -> Dict[str, Any]:
    """一張圖真正要用的那一份設定 —— **跟寫出去的走同一支**。

    ``chart_style.style_for`` 只做「全域 ＋ 這張圖的覆寫」；還有兩件事住在
    **卡片**上（`OutputUniformityStep._style_for`）：這張圖預設叫什麼，以及
    「值那一軸」的名字要落在哪一軸（直方圖是 X、profile 是 Y）。

    ⚠ **UI 這一側只准有這一個入口。** 少走這一支的下場是真的踩過的：設定
    編輯器裡的預覽直接叫 `chart_style.style_for`，於是改 `Name of the value
    axis` 那一格**畫面完全沒有反應** —— 而那一格在寫出去的檔案裡是有作用的。
    「預覽跟輸出不一樣」正是這整個功能最貴的那種 bug。
    """
    from ..core.pipeline import get_step

    try:
        card = get_step("output_uniformity")
        p = card.validate_params({"folder": "x", "look": str(look or ""),
                                  "axis": str(axis or uc.AXIS_X),
                                  "metric": str(metric or "")})
        return card()._style_for(str(kind), p, str(metric or ""))
    except Exception:                     # noqa: BLE001 — 顯示用，不能擋畫面
        return {}


def fit_into(size: Any, box: QRectF) -> QRectF:
    """把 ``size`` **等比例置中**塞進 ``box``。

    ``QSvgRenderer.render(p, rect)`` 會把 viewBox 拉滿整個 rect —— 圖比格子瘦
    的時候那是把圖橫向拉扁，而一張被拉扁的散佈圖讀起來是另一組資料。
    """
    w, h = float(size.width()), float(size.height())
    if w <= 0 or h <= 0:
        return QRectF(box)
    k = min(box.width() / w, box.height() / h)
    dw, dh = w * k, h * k
    return QRectF(box.left() + (box.width() - dw) / 2.0,
                  box.top() + (box.height() - dh) / 2.0, dw, dh)


class ChartView(QWidget):
    """一張圖。**每次重畫都重新產一份 SVG** —— 那正是設定改了會當場變的原因。

    重產的成本是幾毫秒（手寫字串，沒有繪圖後端），而快取一份舊的 SVG 換到的
    是「設定改了但畫面沒變」那一類 bug。
    """

    MIN_W, MIN_H = 260, 200

    def __init__(self, kind: str, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.kind = str(kind)
        self._series: Dict[str, Any] = {}
        self._style: Dict[str, Any] = {}
        self.setMinimumSize(self.MIN_W, self.MIN_H)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)

    def set_data(self, series: Dict[str, Any],
                 style: Optional[Dict[str, Any]] = None) -> None:
        self._series = dict(series or {})
        self._style = dict(style or {})
        self.update()

    def svg(self) -> str:
        """這一格現在畫的那份 SVG（測試讀它，不去讀畫素）。"""
        return uc.build_chart_svg(self._series, self.kind, self._style,
                                  width=max(self.MIN_W, self.width()),
                                  height=max(self.MIN_H, self.height()))

    def paintEvent(self, event) -> None:      # noqa: D102, N802
        p = QPainter(self)
        try:
            p.setRenderHint(QPainter.Antialiasing, True)
            p.fillRect(self.rect(), QColor(TOKENS["bg_surface"]))
            if not (self._series.get("groups") or []):
                p.setPen(QColor(TOKENS["text_secondary"]))
                p.drawText(QRectF(self.rect()), int(Qt.AlignCenter),
                           "no boxes to plot")
                return
            try:
                from PySide6.QtSvg import QSvgRenderer
            except ImportError:               # noqa: BLE001 — 不准擋畫面
                p.setPen(QColor(TOKENS["text_secondary"]))
                p.drawText(QRectF(self.rect()),
                           int(Qt.AlignCenter | Qt.TextWordWrap),
                           "Charts need QtSvg, which is part of PySide6.")
                return
            try:
                r = QSvgRenderer(bytearray(self.svg(), "utf-8"))
                r.render(p, fit_into(r.viewBoxF().size(), QRectF(self.rect())))
            except Exception:                 # noqa: BLE001 — 鐵則 7 的 UI 版
                return
        finally:
            p.end()


class UniformityWindow(QWidget):
    """四張圖 ＋ 一顆 `Chart settings…`。

    **設定改了這裡當場變** —— 那才是調它的方式，不是改完跑一次去開檔案看。
    改完的字串由 :attr:`style_changed` 送回去，主視窗做 ``model.set_param``：
    這一份不碰模型（它連 recipe 長什麼樣都不知道），只說出請求 —— 跟
    `CrossInspector.param_requested` 同一條界線。
    """

    #: 使用者按了套用 → ``chart_style`` 那一格的新字串。
    style_changed = Signal(str)

    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent, Qt.Window)
        self.setWindowTitle("Uniformity charts")
        self.resize(940, 700)
        self._series: Dict[str, Any] = {}
        self._look = ""
        self._axis = uc.AXIS_X
        self._metric = ""
        self._kinds: List[str] = list(uc.CHARTS)

        root = QVBoxLayout(self)
        root.setContentsMargins(12, 10, 12, 12)
        root.setSpacing(8)

        bar = QHBoxLayout()
        bar.setSpacing(8)
        self.head = QLabel("", self)
        self.head.setObjectName("inspectorHeader")
        bar.addWidget(self.head, 1)
        self.settings_btn = small_button(
            "Chart settings…", shape="wide",
            tip=("Titles, axis names, tick counts, text size and colour, "
                 "marker and line width - and whether the value scale is "
                 "locked. It travels with the recipe."),
            parent=self)
        self.settings_btn.clicked.connect(self.open_settings)
        bar.addWidget(self.settings_btn, 0)
        root.addLayout(bar)

        self.grid = QGridLayout()
        self.grid.setSpacing(10)
        root.addLayout(self.grid, 1)
        self.views: Dict[str, ChartView] = {}

    # -- 資料 ---------------------------------------------------------------
    def set_context(self, series: Dict[str, Any], look: str = "",
                    axis: str = uc.AXIS_X, metric: str = "",
                    kinds: Optional[Sequence[str]] = None) -> None:
        """餵一顆 defect 的資料 ＋ 那張卡現在的設定。"""
        self._series = dict(series or {})
        self._look = str(look or "")
        self._axis = str(axis or uc.AXIS_X)
        self._metric = str(metric or self._series.get("metric") or "")
        want = [k for k in (kinds if kinds is not None else uc.CHARTS)
                if k in uc.CHARTS]
        if want != self._kinds or not self.views:
            self._kinds = want or list(uc.CHARTS)
            self._rebuild()
        self._refresh()

    def _rebuild(self) -> None:
        """勾選變了才重建格子 —— 每次餵資料都拆掉重建會讓視窗閃一下。"""
        while self.grid.count():
            item = self.grid.takeAt(0)
            w = item.widget()
            if w is not None:
                w.setParent(None)
                w.deleteLater()
        self.views = {}
        cols = 2 if len(self._kinds) > 1 else 1
        for i, kind in enumerate(self._kinds):
            view = ChartView(kind, self)
            self.grid.addWidget(view, i // cols, i % cols)
            self.views[kind] = view

    def style_for(self, kind: str) -> Dict[str, Any]:
        """一張圖的設定 —— 見 :func:`chart_style_for`（UI 這一側唯一的入口）。"""
        return chart_style_for(self._look, kind, self._axis, self._metric)

    def _refresh(self) -> None:
        for kind, view in self.views.items():
            view.set_data(self._series, self.style_for(kind))
        groups = self._series.get("groups") or []
        boxes = sum(len(g.get("values") or ()) for g in groups)
        self.head.setText(
            "%s  ·  %d region(s), %d box(es)"
            % (self._metric or "—", len(groups), boxes)
            if groups else "Nothing to plot yet")

    # -- 設定 ---------------------------------------------------------------
    def open_settings(self) -> None:
        """開設定，套用之後**當場重畫**並把新字串送出去。"""
        from .chart_settings import ChartSettingsDialog

        # **把這一顆的資料帶進去** —— 編輯器裡的預覽畫的就是你正在看的那一批
        # 框，不是樣本。調外觀最需要的正是「用我自己的資料看」。
        dlg = ChartSettingsDialog(self._look, self._kinds, self,
                                  series=self._series, axis=self._axis)
        if dlg.exec():
            self._look = dlg.value()
            self._refresh()
            self.style_changed.emit(self._look)

    def look(self) -> str:
        return self._look
