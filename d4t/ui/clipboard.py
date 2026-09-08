# 卡片的剪貼簿 — authored 2026-09-08 (F99 P1-8).
"""Ctrl+C / Ctrl+V / Ctrl+D 的**內容**；`StudioWindow` 只留三支轉呼叫。

有 undo 卻沒有 copy 是很少見的組合；學會 Ctrl+Z 的人一定會試 Ctrl+C。

兩條規矩：

* **剪貼簿是視窗自己的**，不進系統剪貼簿。這裡複製的是「一張卡的設定」，貼到
  別的程式裡沒有意義，而系統剪貼簿上的字貼進來也不是卡。
* **設定帶走、接線不帶**（`edit_plan.copyable_params` 講理由）：貼上的那張卡
  是乾淨的（F10），線要使用者自己拉。

純 model 操作，不碰 Qt，所以測試不用開視窗。
"""
from __future__ import annotations

from typing import Any, Callable, Dict, List, Optional, Sequence, Tuple

from ..core.pipeline.step import ParamError
from . import edit_plan

__all__ = ["Snapshot", "snapshot", "paste", "OFFSET"]

#: 貼上的卡相對原位偏多少（畫布座標）—— 看得出是一張新的、又看得出從哪來。
OFFSET = 40.0

#: 一張卡的複本：``(step_key, 帶得走的參數, (x, y))``。
Snapshot = Tuple[str, Dict[str, Any], Tuple[float, float]]


def snapshot(model: Any, ids: Sequence[str],
             pos_of: Callable[[str], Optional[Tuple[float, float]]]) -> List[Snapshot]:
    """把 ``ids`` 那幾張卡拍下來。不存在的 id 跳過。"""
    out: List[Snapshot] = []
    for nid in ids:
        node = model.nodes.get(str(nid))
        if node is None:
            continue
        pos = pos_of(str(nid)) or (0.0, 0.0)
        out.append((str(node.step),
                    edit_plan.copyable_params(node.step, node.params),
                    (float(pos[0]), float(pos[1]))))
    return out


def paste(model: Any, items: Sequence[Snapshot],
          say: Callable[[str, str], None]) -> List[Tuple[str, Tuple[float, float]]]:
    """貼上：每一張 `add_step` ＋ 逐格 `set_param`，**一步復原**（`compound`）。
    回 ``[(新 id, 該放的位置), …]``；放的動作在畫布，不在這裡。

    舊卡帶著現在不合法的值（卡片改過規格）：那一格留預設，不讓整張貼不上。
    """
    made: List[Tuple[str, Tuple[float, float]]] = []
    with model.compound("paste"):
        for step_key, params, (x, y) in items:
            try:
                nid = model.add_step(str(step_key))
            except (KeyError, ParamError) as e:
                say("Could not paste “%s”: %s" % (step_key, e), "error")
                continue
            for name, value in dict(params or {}).items():
                try:
                    model.set_param(nid, name, value)
                except ParamError:
                    pass
            made.append((nid, (x + OFFSET, y + OFFSET)))
    return made
