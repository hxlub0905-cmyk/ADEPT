# F100：畫布橫躺在上面、工作台在下面 — authored 2026-09-08.
"""`docs/history/plans/F100-workbench-layout.md` 的驗收。

兩層：`WorkbenchLayout` 本身（純幾何，拿真的 QSplitter 但不開 Studio，
快）；以及**在 1366×768 上真的開一次 Studio、載 recipe、選一張卡、量幾何**
—— 那是 F99 P0-3 的關門，也是這個 repo 第一條「畫面長什麼樣」的測試
（F99 P2-7 的雛形）。

⚠ 這裡量的是**幾何**不是像素：`minimumSizeHint`、splitter 的 sizes、widget
的 geometry。像素會跟字型漂，幾何不會。
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))
sys.path.insert(0, str(REPO / "tools"))

RECIPE = REPO / "recipes" / "rsem-worst-box.json"
#: 廠內機台旁那台 PC 的螢幕（`docs/history/plans/F100-workbench-layout.md` §1）。
SMALL = (1366, 768)


@pytest.fixture(scope="module")
def qapp():
    from PySide6.QtWidgets import QApplication

    from d4t.ui import theme
    app = QApplication.instance() or QApplication([])
    theme.apply_theme(app, "light")
    yield app


def _splitters(qapp):
    from PySide6.QtCore import Qt
    from PySide6.QtWidgets import QSplitter, QWidget
    host = QWidget()
    host.resize(1000, 700)
    column = QSplitter(Qt.Vertical, host)
    canvas = QWidget(column)
    workbench = QSplitter(Qt.Horizontal, column)
    for _ in range(3):
        workbench.addWidget(QWidget(workbench))
    column.addWidget(canvas)
    column.addWidget(workbench)
    column.resize(1000, 700)
    host.show()
    qapp.processEvents()
    return host, column, workbench, canvas


# --------------------------------------------------------------------------- #
# 1. WorkbenchLayout 本身
# --------------------------------------------------------------------------- #
def test_tune_opens_the_workbench_and_keeps_the_canvas_floor(qapp):
    from d4t.ui import workbench as wb
    host, column, bench, canvas = _splitters(qapp)
    lay = wb.WorkbenchLayout(column, bench, canvas)
    assert lay.mode == "tune" and lay.open is True
    lay.apply("tune", remember=False)
    qapp.processEvents()
    top, bottom = column.sizes()
    assert top >= wb.CANVAS_MIN_PX, "畫布低於保底：%s" % column.sizes()
    assert bottom > 0, "Tune 模式工作台要開著（影像住在裡面）"
    assert canvas.minimumHeight() == wb.CANVAS_MIN_PX
    host.close()


def test_build_collapses_the_workbench(qapp):
    from d4t.ui import workbench as wb
    host, column, bench, canvas = _splitters(qapp)
    lay = wb.WorkbenchLayout(column, bench, canvas)
    assert lay.apply("build") == "build"
    qapp.processEvents()
    assert column.sizes()[1] == 0
    assert lay.open is False
    assert lay.set_open(True) is False, "Build 模式下不准把工作台推回來"
    assert lay.apply("nonsense") == "build", "不認得的名字什麼都不做"
    host.close()


def test_selection_reopens_a_closed_workbench_but_never_closes_it(qapp):
    from d4t.ui import workbench as wb
    host, column, bench, canvas = _splitters(qapp)
    lay = wb.WorkbenchLayout(column, bench, canvas)
    lay.apply("tune", remember=False)
    lay.set_open(False)
    assert column.sizes()[1] == 0
    lay.on_selection(True)
    assert lay.open is True and column.sizes()[1] > 0
    lay.on_selection(False)
    assert lay.open is True, "取消選取不收工作台 —— 影像住在裡面"
    host.close()


def test_only_tune_ratios_are_remembered(qapp):
    """Build 的「畫布 100% / 工作台 0」不是使用者調出來的比例，不存。"""
    from d4t.ui import workbench as wb
    host, column, bench, canvas = _splitters(qapp)
    saved = {}
    lay = wb.WorkbenchLayout(column, bench, canvas,
                             save=lambda k, v: saved.__setitem__(k, list(v)))
    lay.apply("tune", remember=False)
    qapp.processEvents()
    column.setSizes([300, 400])
    lay.apply("build")                  # remember=True：把 Tune 的存起來
    assert wb.SPLIT_KEYS["tune"] in saved
    saved.clear()
    lay.apply("tune")                   # 從 Build 切回來：沒有東西好存
    assert wb.SPLIT_KEYS["build"] not in saved
    lay.remember()
    assert wb.WORKBENCH_COLUMNS_KEY in saved
    host.close()


def test_a_saved_ratio_below_the_floor_is_ignored(qapp):
    """舊那一格存的是「畫布 2 / 設定 3」—— 套上去畫布會低於保底，所以不吃。"""
    from d4t.ui import workbench as wb
    host, column, bench, canvas = _splitters(qapp)
    lay = wb.WorkbenchLayout(column, bench, canvas,
                             load=lambda k, n: [80, 620] if n == 2 else None)
    lay.apply("tune", remember=False)
    qapp.processEvents()
    assert column.sizes()[0] >= wb.CANVAS_MIN_PX
    host.close()


def test_switching_from_build_to_tune_folds_the_library(qapp):
    """從 Build 切回 Tune：卡片區收成 rail，那 200 px 給工作台。"""
    from d4t.ui import workbench as wb

    class Lib:
        def __init__(self):
            self.calls = []

        def toggle_group(self, g):
            self.calls.append(g)

    host, column, bench, canvas = _splitters(qapp)
    lib = Lib()
    lay = wb.WorkbenchLayout(column, bench, canvas, lib)
    lay.apply("tune", remember=False)
    assert lib.calls == [], "開窗時不收 —— 空白狀態下卡片清單是第一眼要看的"
    lay.apply("build")
    lay.apply("tune")
    assert lib.calls == [None]
    host.close()


# --------------------------------------------------------------------------- #
# 2. 真的開一次 Studio，在 1366×768 上量
# --------------------------------------------------------------------------- #
@pytest.fixture
def small_screen():
    from PySide6.QtCore import QRect

    from d4t.ui import fit_screen
    fit_screen.FORCE_RECT = QRect(0, 0, *SMALL)
    yield SMALL
    fit_screen.FORCE_RECT = None


@pytest.fixture
def lot(tmp_path_factory):
    from make_sample_rsem import generate
    return generate(str(tmp_path_factory.mktemp("f100")), n=6, seed=3)


def test_the_studio_fits_the_fab_pc_after_loading_and_picking_a_card(
        qapp, small_screen, lot):
    """F99 P0-3 的關門：以前載入之後 `minimumSizeHint` 變成 1,334、視窗被撐到
    1,495 —— 而 U1 的 fit_screen 只守開窗那一刻。"""
    from d4t.ui import fit_screen
    from d4t.ui import workbench as wb
    from d4t.ui.studio import StudioWindow
    w, h = small_screen
    win = StudioWindow(show_welcome_on_start=False)
    win.PROMPT_ON_CLOSE = False          # 同 test_ui_f99_gestures：lazy import 來不及讓 conftest 關它
    fit_screen.fit(win, w, h)
    win.show()
    qapp.processEvents()
    assert win.load_recipe_path(str(RECIPE), sync=True) is True
    assert win.load_dataset_path(lot["klarf"], sync=True) is True
    qapp.processEvents()
    assert win.select_node("glv") is True
    qapp.processEvents()
    try:
        hint = win.minimumSizeHint()
        assert hint.width() <= w, \
            "載入之後最小寬度 %d 超過 %d" % (hint.width(), w)
        assert win.width() <= w and win.height() <= h, win.size()
        # 畫布吃滿中欄的寬度（v2：中欄 ＝ 卡片庫與右欄之間的整塊）
        assert win.pipeline.width() >= win.main_column.width() - 2
        # 而且高度有保底（Tune 模式）
        assert win.layout_mode() == "tune"
        assert win.canvas_column.sizes()[0] >= wb.CANVAS_MIN_PX
        # v3：設定區（中欄下半）與儀表（右欄下半）**左右相鄰**、垂直範圍重疊
        # —— U8「儀表挨著參數」；影像在儀表上面，寬度跟儀表一樣（直方圖要的
        # 是寬度，影像要的是高度，右欄兩個都給得起）。
        # ⚠ geometry() 是各自父元件的座標；三塊住在不同的 splitter 裡，要先
        # 換到視窗座標才比得了。
        from PySide6.QtCore import QPoint, QRect

        def on_window(widget) -> QRect:
            return QRect(widget.mapTo(win, QPoint(0, 0)), widget.size())

        a, b = on_window(win.stack), on_window(win.gauge_pane)
        assert a.width() > 0 and b.width() > 0, (a, b)
        assert min(a.bottom(), b.bottom()) > max(a.top(), b.top()), \
            "設定區與儀表沒有併排：%s vs %s" % (a, b)
        assert a.width() >= 500, "設定區要拿到整個中欄的寬：%s" % a
        pv = on_window(win.preview_pane)
        assert pv.width() >= 300, "右欄太窄：%s" % pv
        assert b.width() >= 300, "儀表要拿到右欄的寬：%s" % b
        assert pv.bottom() <= b.top() + 12, "影像在儀表上面：%s vs %s" % (pv, b)
        assert win.verdict_strip.isVisibleTo(win)
        # Build：工作台與右欄都收掉，畫布吃滿
        win.set_layout_mode("build")
        qapp.processEvents()
        assert win.canvas_column.sizes()[1] == 0
        assert win.layout_modes.preview_width() == 0
        assert win.pipeline.width() >= win.width() - win.library.width() - 24
        win.set_layout_mode("tune")
        qapp.processEvents()
        assert win.layout_modes.preview_width() > 0
    finally:
        win.close()


def test_the_verdict_strip_sits_under_the_image(qapp):
    """Verdict 跟這一顆的圖挨著（v2）：住在右欄影像下面，不在工作台裡。"""
    from d4t.ui.studio import StudioWindow
    win = StudioWindow(show_welcome_on_start=False)
    win.PROMPT_ON_CLOSE = False
    try:
        assert win.preview_pane.isAncestorOf(win.verdict_strip)
        assert not win.workbench.isAncestorOf(win.verdict_strip)
        assert not win.canvas_column.isAncestorOf(win.verdict_strip)
        root = win.root_splitter
        assert [root.widget(i) for i in range(root.count())] == [
            win.library, win.main_column, win.right_column]
        assert [win.right_column.widget(i) for i in range(2)] == [
            win.preview_pane, win.gauge_pane]
    finally:
        win.close()


def test_build_folds_the_preview_column_and_tune_brings_it_back(qapp):
    """純幾何：右欄在 Build 收到 0、Tune 回來；只在 Tune 記寬度。"""
    from PySide6.QtCore import Qt
    from PySide6.QtWidgets import QSplitter, QWidget

    from d4t.ui import workbench as wb
    host, column, bench, canvas = _splitters(qapp)
    root = QSplitter(Qt.Horizontal, host)
    lib = QWidget(root)
    preview = QWidget(root)
    root.addWidget(lib)
    root.addWidget(column)
    root.addWidget(preview)
    root.resize(1300, 700)
    root.show()
    qapp.processEvents()
    saved = {}
    lay = wb.WorkbenchLayout(column, bench, canvas, root=root, preview_index=2,
                             save=lambda k, v: saved.__setitem__(k, list(v)))
    lay.apply("tune", remember=False)
    qapp.processEvents()
    assert lay.preview_width() > 0
    lay.apply("build")
    qapp.processEvents()
    assert lay.preview_width() == 0
    lay.apply("tune")
    qapp.processEvents()
    assert lay.preview_width() > 0
    lay.remember()
    assert wb.ROOT_COLUMNS_KEY in saved
    host.close()
