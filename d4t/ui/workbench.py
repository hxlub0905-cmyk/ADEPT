# 版面模式：畫布在上、工作台在下 — authored 2026-09-08 (F100).
"""``WorkbenchLayout`` —— Build / Tune 兩種版面的**狀態與幾何**，不建 widget。

主視窗的版面（F100，`docs/plans/F100-workbench-layout.md`）::

    ┌─庫─┬──────────── 畫布（全寬、橫流）────────────┐
    │    ├───────────────┬──────────────┬─────────────┤
    │    │ 設定區        │ 儀表板       │ 預覽影像    │
    │    ├───────────────┴──────────────┴─────────────┤
    │    │ Verdict …                                   │
    └────┴────────────────────────────────────────────┘

* **Build** —— 工作台收到 0，畫布吃滿右邊整塊。看全貌、接線、排版。
* **Tune** —— 工作台開著（影像住在裡面，所以**開窗就開著**），畫布保底
  :data:`CANVAS_MIN_PX`、預設 :data:`CANVAS_SHARE_TUNE`。調參數、看影像。

為什麼是一個獨立的類別而不是 `StudioWindow` 的幾支方法：`studio.py` 是這個 repo
唯一會自己長大的檔案（`CLAUDE.md` §4、`tests/test_size_ceilings.py`），而版面
模式的邏輯——哪一根 splitter 設成多少、記在哪一格 QSettings、什麼時候收卡片庫
——跟「接訊號、轉呼叫」不是同一件事。這裡純幾何，只碰 splitter 與卡片庫的
公開 API，所以測試可以不開整個 Studio 就問它。

⚠ ``QSplitter.setSizes`` 要 widget **真的排過版**才算得出來（`docs/PITFALLS.md`
的老坑）——所以 :meth:`apply` 不在建構期呼叫，主視窗的 ``showEvent`` 第一次
show 才套（跟 U5 之前一樣）。
"""
from __future__ import annotations

from typing import Callable, List, Optional, Sequence

__all__ = [
    "WorkbenchLayout", "MODES", "CANVAS_MIN_PX", "CANVAS_SHARE_TUNE",
    "COLUMN_STRETCH", "SPLIT_KEYS", "WORKBENCH_COLUMNS_KEY",
]

#: 兩種版面。`tune` 是預設——開窗看到的就是它。
MODES = ("build", "tune")
#: Tune 模式畫布的保底高度（px）。768 高的螢幕扣掉工具列、Verdict 列、Problems
#: 列與狀態列之後主欄約 600 px，200 就是評審說的「35%」。用 px 不用比例，因為
#: 保底要跟著螢幕走：1080 的螢幕上 35% 是 300 px，而畫布在那裡不需要更高。
CANVAS_MIN_PX = 200
#: Tune 模式畫布預設佔主欄的比例（使用者拖過之後記他的）。
CANVAS_SHARE_TUNE = 0.40
#: 工作台三格（設定區｜儀表板｜預覽影像）的伸縮比。設定區裝的是可以拖的滑桿、
#: 影像要寬度看得清楚，儀表是讀的東西——所以兩邊寬、中間窄。
COLUMN_STRETCH = (3, 2, 3)
#: 兩種模式各自的「畫布 / 工作台」比例存在哪一格 QSettings。
#:
#: **兩格而不是一格**（U5 的理由沒變）：使用者在 Build 裡把畫布拉高、在 Tune 裡把
#: 工作台拉高，那是兩個不同的偏好。
#: ⚠ Tune 那一格是**新名字**：舊那一格（``ui/canvas_split``）存的是「畫布 2 /
#: 設定 3」，套到新版面上畫布會低於保底。換名字等於升級那一天重設一次——
#: 代價寫在計畫書 §6。
SPLIT_KEYS = {"build": "ui/canvas_split_build",
              "tune": "ui/canvas_split_tune_f100"}
#: 工作台三格的寬度存在哪一格。
WORKBENCH_COLUMNS_KEY = "ui/workbench_columns"


class WorkbenchLayout:
    """Build / Tune 的狀態機。

    ``column`` 是直向的 QSplitter（``widget(0)`` 畫布、``widget(1)`` 工作台），
    ``workbench`` 是工作台那根橫向的 QSplitter（設定區｜儀表板｜預覽影像）。
    ``load`` / ``save`` 是主視窗那兩支讀寫 QSettings 的函式（測試時 ``load``
    永遠回 ``None``，那是它自己的規矩）。
    """

    def __init__(self, column, workbench, pipeline, library=None, *,
                 load: Optional[Callable[[str, int], Optional[List[int]]]] = None,
                 save: Optional[Callable[[str, Sequence[int]], None]] = None):
        self.column = column
        self.workbench = workbench
        self.pipeline = pipeline
        self.library = library
        self._load = load or (lambda _key, _n: None)
        self._save = save or (lambda _key, _sizes: None)
        self.mode: str = "tune"
        #: 工作台現在攤開著嗎（**明確狀態**，不去問 ``isVisible``）。
        #: Tune 模式開窗就是 True——影像住在裡面。
        self.open: bool = True
        self._columns_applied = False
        pipeline.setMinimumHeight(CANVAS_MIN_PX)
        for i, s in enumerate(COLUMN_STRETCH):
            if i < workbench.count():
                workbench.setStretchFactor(i, s)
        # 設定區不准被拖到 0：那是使用者現在在改的東西。影像那一格也是。
        # 儀表板可以（它是讀的東西，有人會想把影像拉寬）。
        for i in (0, 2):
            if i < workbench.count():
                workbench.setCollapsible(i, False)

    # ---- 查詢 ------------------------------------------------------------
    def total(self) -> int:
        return int(sum(self.column.sizes()) or self.column.height())

    def canvas_share(self) -> float:
        """畫布現在佔主欄的比例（0–1）。"""
        sizes = list(self.column.sizes())
        tot = sum(sizes)
        return (sizes[0] / float(tot)) if tot else 0.0

    # ---- 換模式 ----------------------------------------------------------
    def apply(self, mode: str, remember: bool = True) -> str:
        """換版面。回真的套上去的那一個（不認得的名字什麼都不做）。

        ``remember=True`` 時先把**現在**這個模式的比例記下來——只記 Tune：
        Build 的「畫布 100% / 工作台 0」不是使用者調出來的比例，存下來下次
        照著還原他會看到一個從來沒有調成那樣的版面。
        """
        use = str(mode or "")
        if use not in MODES:
            return self.mode
        was = self.mode
        if remember and was == "tune" and self.open:
            sizes = list(self.column.sizes())
            if sum(sizes):
                self._save(SPLIT_KEYS["tune"], sizes)
        self.mode = use
        self._restore_columns()
        if use == "build":
            self.open = False
            self.column.setSizes([self.total(), 0])
        else:
            self.open = True
            self._open_workbench()
            # 從 Build 切過來：卡片區收成 rail，那 200 px 給工作台。**只在切換
            # 的時候**——開窗時卡片清單是空白狀態下第一眼要看的東西。
            if was == "build" and self.library is not None:
                try:
                    self.library.toggle_group(None)
                except Exception:        # noqa: BLE001 — 版面不准擋在卡片庫上
                    pass
        return use

    def set_open(self, on: bool) -> bool:
        """攤開／收起工作台（Tune 模式）。Build 模式下什麼都不做。"""
        if self.mode == "build":
            return False
        self.open = bool(on)
        if self.open:
            self._open_workbench()
        else:
            self.column.setSizes([self.total(), 0])
        return self.open

    def on_selection(self, has_selection: bool) -> None:
        """選到卡片：收起來的工作台要打開。取消選取**不**收——影像住在裡面。"""
        if self.mode == "tune" and has_selection and not self.open:
            self.set_open(True)

    # ---- 關窗 ------------------------------------------------------------
    def remember(self) -> None:
        """關窗時把使用者拖過的分隔線存起來。"""
        if self.mode == "tune" and self.open:
            sizes = list(self.column.sizes())
            if sum(sizes):
                self._save(SPLIT_KEYS["tune"], sizes)
        cols = list(self.workbench.sizes())
        if sum(cols):
            self._save(WORKBENCH_COLUMNS_KEY, cols)

    # ---- internals ---------------------------------------------------------
    def _open_workbench(self) -> None:
        total = self.total()
        saved = self._load(SPLIT_KEYS["tune"], 2)
        if saved and sum(saved) and saved[0] >= CANVAS_MIN_PX:
            self.column.setSizes(saved)
            return
        canvas = max(CANVAS_MIN_PX, int(total * CANVAS_SHARE_TUNE))
        self.column.setSizes([canvas, max(0, total - canvas)])

    def _restore_columns(self) -> None:
        """工作台三格的寬度：存過就用存的，沒有就照 :data:`COLUMN_STRETCH`。
        只套一次——之後是使用者自己拖的。"""
        if self._columns_applied:
            return
        self._columns_applied = True
        n = self.workbench.count()
        saved = self._load(WORKBENCH_COLUMNS_KEY, n)
        if saved and sum(saved):
            self.workbench.setSizes(saved)
            return
        total = int(sum(self.workbench.sizes()) or self.workbench.width())
        if total <= 0:
            return
        weights = list(COLUMN_STRETCH[:n]) or [1] * n
        wsum = float(sum(weights)) or 1.0
        self.workbench.setSizes([int(total * w / wsum) for w in weights])
