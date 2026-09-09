"""`d4t/core/log.py`：被吞掉的例外要留痕，而沒人接的時候一個位元組都不寫。"""
from __future__ import annotations

import ast
import logging
from pathlib import Path

import pytest

from d4t.core import log as d4t_log

REPO = Path(__file__).resolve().parent.parent
PKG = REPO / "d4t"
#: 這兩支自己就是「記錄錯誤的地方」，裡面的 except 是為了不遞迴，不算。
EXEMPT = {"d4t/ui/crashlog.py", "d4t/core/log.py"}


@pytest.fixture
def logfile(tmp_path):
    path = tmp_path / "d4t.log"
    h = d4t_log.attach_file(str(path))
    yield path
    d4t_log.detach(h)


def test_swallowed_writes_the_traceback_when_a_file_is_attached(logfile):
    try:
        raise ValueError("this one was swallowed on purpose")
    except ValueError:
        d4t_log.swallowed("test.here")
    text = logfile.read_text(encoding="utf-8")
    assert "swallowed in test.here" in text
    assert "ValueError: this one was swallowed on purpose" in text
    assert "Traceback" in text


def test_without_a_handler_nothing_is_written_or_printed(capsys, tmp_path):
    d4t_log.detach_all()
    try:
        raise RuntimeError("nobody is listening")
    except RuntimeError:
        d4t_log.swallowed("test.silent")
    out = capsys.readouterr()
    assert out.out == "" and out.err == ""
    assert not list(tmp_path.iterdir())
    assert not d4t_log.LOGGER.isEnabledFor(logging.DEBUG)


def test_attach_file_creates_the_folder(tmp_path):
    path = tmp_path / "deeper" / "still" / "d4t.log"
    h = d4t_log.attach_file(str(path))
    try:
        d4t_log.get("x").info("hello")
    finally:
        d4t_log.detach(h)
    assert path.exists() and "hello" in path.read_text(encoding="utf-8")


def test_a_batch_warning_reaches_the_log(logfile):
    from d4t.core.pipeline.context import BatchContext
    b = BatchContext()
    b.warn("something about the whole lot")
    assert "something about the whole lot" in logfile.read_text(encoding="utf-8")


def _is_broad(t) -> bool:
    return t is None or (isinstance(t, ast.Name) and t.id in ("Exception", "BaseException"))


def _swallows_silently(body) -> bool:
    if len(body) != 1:
        return False
    b = body[0]
    if isinstance(b, (ast.Pass, ast.Continue)):
        return True
    return isinstance(b, ast.Return) and (
        b.value is None or (isinstance(b.value, ast.Constant) and b.value.value is None))


def test_no_broad_except_swallows_without_leaving_a_trace():
    """``except Exception:`` 後面只有 ``pass`` / ``continue`` / ``return`` 的地方，
    要先呼叫 ``swallowed("模組.函式")``。2026-09-09 之前有 59 處，零處留痕。

    只管**寬的** except（``Exception`` / bare）。``except (TypeError, ValueError)``
    那種是刻意的解析退路（「壞字串一律當沒有」），不在這裡。
    """
    offenders = []
    for py in sorted(PKG.rglob("*.py")):
        rel = py.relative_to(REPO).as_posix()
        if rel in EXEMPT:
            continue
        tree = ast.parse(py.read_text(encoding="utf-8"), filename=str(py))
        for node in ast.walk(tree):
            if isinstance(node, ast.ExceptHandler) and _is_broad(node.type) \
                    and _swallows_silently(node.body):
                offenders.append("%s:%d" % (rel, node.lineno))
    assert not offenders, (
        "這些 except Exception 把例外吃掉而沒留痕；在 pass/continue/return 前面加一行 "
        "swallowed(\"模組.函式\")（from d4t.core.log import swallowed）：%s" % offenders)
