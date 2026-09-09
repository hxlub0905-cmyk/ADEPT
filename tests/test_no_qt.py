"""M0 驗收：d4t 全套件零 Qt import（原始碼掃描 + 實際 import 檢查）。"""
from __future__ import annotations

import re
import sys
from pathlib import Path

PKG = Path(__file__).resolve().parent.parent / "d4t"
CORE = PKG / "core"
QT_PAT = re.compile(r"^\s*(import|from)\s+(PyQt\d?|PySide\d?|qtpy|Qt)\b", re.M)


def test_no_qt_in_core_source():
    """core 禁 Qt；d4t/ui 是唯一允許 Qt 的地方（__main__ 須 lazy import）。"""
    offenders = []
    for py in CORE.rglob("*.py"):
        if QT_PAT.search(py.read_text(encoding="utf-8")):
            offenders.append(str(py))
    main_py = PKG / "__main__.py"
    if main_py.exists() and QT_PAT.search(main_py.read_text(encoding="utf-8")):
        offenders.append(str(main_py))
    assert not offenders, f"Qt import found in: {offenders}"


def test_no_qt_after_import():
    """在**乾淨的子行程**裡 import core，然後看 Qt 有沒有被拖進來。

    以前是在測試行程裡直接看 ``sys.modules``，那讓這條測試變成**跟執行順序
    有關**：只要有任何一個 UI 測試檔排在 ``test_no_qt.py`` 前面跑過，Qt 就
    已經在 ``sys.modules`` 裡，這裡就會誤報 —— 而它報的位置離真正的原因
    （另一個檔案的 fixture）很遠，看訊息完全猜不到。加一支新測試檔就可能踩到，
    只因為檔名的字母序。子行程沒有這個問題：問的就是「單獨 import core 時
    會不會拉進 Qt」，而那本來就是這條測試唯一想問的事。
    """
    import subprocess

    code = (
        "import sys\n"
        "import d4t.core.algo, d4t.core.ingest, d4t.core.calibration\n"
        "qt = [m for m in sys.modules "
        "      if m.split('.')[0] in ('PyQt5','PyQt6','PySide2','PySide6')]\n"
        "print(','.join(sorted(qt)))\n"
    )
    proc = subprocess.run([sys.executable, "-c", code],
                          cwd=str(PKG.parent), capture_output=True, text=True)
    assert proc.returncode == 0, proc.stderr
    loaded = [m for m in proc.stdout.strip().split(",") if m]
    assert not loaded, f"Qt modules loaded: {loaded}"


def test_py39_syntax():
    import ast
    for py in PKG.rglob("*.py"):
        ast.parse(py.read_text(encoding="utf-8"), filename=str(py), feature_version=(3, 9))


def test_only_ui_test_files_import_qt_at_module_level():
    """**核心批（``--ignore-glob="*test_ui_*"``）不准需要 Qt。**

    2026-09-09 量到的：``test_glv_combinations.py`` 在模組層
    ``from PySide6.QtWidgets import …``，而它不叫 ``test_ui_*`` —— 於是「核心批
    在沒有 Qt 函式庫的機器上跑得動」這句話不成立：那台機器上核心批紅 34 條，
    全部是 ``libEGL.so.1``。分批的意思是「這一批不需要那個東西」，而檔名就是
    分批的判準，所以檔名要說實話。

    只掃**模組層**（top-level 的 ``import`` / ``from … import``）。函式或 fixture
    裡 lazy import 是允許的 —— 那是 ``PITFALLS.md`` 寫的做法 —— 但請配
    ``pytest.importorskip("PySide6.QtWidgets", exc_type=ImportError)``：
    ``importorskip("PySide6")`` 只擋「沒裝」，擋不住「裝了但開不了」
    （``import PySide6`` 成功、``PySide6.QtWidgets`` 炸在 ``libEGL``）；而
    pytest 9 起 ``importorskip`` 預設只認 ``ModuleNotFoundError``，``libEGL``
    那種是 ``ImportError``，所以 ``exc_type`` 那一格不能省。
    """
    import ast

    tests_dir = Path(__file__).resolve().parent
    offenders = []
    for py in sorted(tests_dir.glob("test_*.py")):
        if py.name.startswith("test_ui_"):
            continue
        tree = ast.parse(py.read_text(encoding="utf-8"), filename=str(py))
        for node in tree.body:
            names = []
            if isinstance(node, ast.Import):
                names = [a.name for a in node.names]
            elif isinstance(node, ast.ImportFrom) and node.module:
                names = [node.module]
            if any(n.split(".")[0] in ("PySide6", "PySide2", "PyQt5", "PyQt6")
                   for n in names):
                offenders.append("%s:%d" % (py.name, node.lineno))
    assert not offenders, (
        "這些非 test_ui_* 的檔案在模組層 import Qt，請改名成 test_ui_*，"
        "或改成函式內 lazy import 配 importorskip('PySide6.QtWidgets')：%s"
        % offenders)


def test_core_tests_guard_lazy_qt_imports_with_the_right_importorskip():
    """``pytest.importorskip("PySide6")`` 在非 UI 檔裡是一個**假的**守門：
    它只問「套件裝了沒」，答不出「開不開得了」。要問後者請用
    ``importorskip("PySide6.QtWidgets")``。"""
    tests_dir = Path(__file__).resolve().parent
    bad = []
    for py in sorted(tests_dir.glob("test_*.py")):
        if py.name.startswith("test_ui_") or py.name == "test_no_qt.py":
            continue
        for i, line in enumerate(py.read_text(encoding="utf-8").splitlines(), 1):
            if line.lstrip().startswith("#") or "importorskip(" not in line:
                continue
            if ("PySide6" in line
                    and '"PySide6.QtWidgets", exc_type=ImportError' not in line):
                bad.append("%s:%d" % (py.name, i))
    assert not bad, (
        "請改成 importorskip('PySide6.QtWidgets', exc_type=ImportError)：%s" % bad)
