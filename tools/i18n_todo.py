#!/usr/bin/env python3
# 還有哪些句子沒有翻 — authored 2026-09-08 (U14).
"""開一次 Studio、逐張卡點過去，把**流過 `strings.tr()` 的每一句**收集起來，
再跟一份 catalog 比對，回報還缺哪些（照出現次數由多到少）。

為什麼是「跑一次」而不是「掃原始碼」
------------------------------------
翻譯層擺在共用的那幾支（工具列的鈕、`small_button`、參數說明、狀態列），
所以**大部分句子在原始碼裡看起來不像要翻的東西** —— 它們是 `ParamSpec.help`
的字串、是 `_tool_button` 的參數。掃原始碼答不出「哪些句子真的會被畫出來」，
跑一次就答得出來。

出現次數是**優先順序**：使用者看到最多次的那一句先翻。

    python tools/i18n_todo.py             # 看 zh_TW 還缺什麼
    python tools/i18n_todo.py --locale xx
    python tools/i18n_todo.py --stub      # 印一份可以直接貼的 JSON 骨架

⚠ 這一支要 Qt（它真的開一個視窗）。**家用機跑**，見 `AGENTS.md` §4.5。
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))

#: 點過這幾張卡 —— 一張卡的參數說明只有在它被選中時才會流過 `tr()`。
#: **不是全部的卡**：這是一份「夠不夠用」的取樣，不是一份完整性證明
#: （加了新卡而沒有加進來的話，它的說明句就不會出現在待翻清單上 ——
#: 所以這裡是 registry 的全部，不是手挑的幾張）。
def _all_cards():
    import d4t.core.steps                    # noqa: F401 — 觸發註冊
    from d4t.core.pipeline.step import REGISTRY
    return list(REGISTRY)


def harvest() -> dict:
    """開一次 Studio，回 ``{原句: 出現幾次}``。"""
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    # 這兩個旗標要在 import studio **之前**設 —— 一個 modal 對話框在沒有人
    # 看著的時候不會失敗，它會永遠停在那裡（U3／U4 學到的那一課）。
    from d4t.ui import autosave, crashlog, strings
    autosave.ASK_ON_START = False
    crashlog.SHOW_DIALOG = False

    from PySide6.QtWidgets import QApplication
    app = QApplication.instance() or QApplication([])
    from d4t.ui.studio import StudioWindow

    win = StudioWindow()
    strings.forget()
    for key in _all_cards():
        try:
            nid = win.model.add_step(key)
            win._refresh_all()
            win.select_node(nid)
            app.processEvents()
        except Exception:              # noqa: BLE001 — 收集用，一張卡失敗不擋
            continue
    out = strings.seen()
    win.close()
    return out


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--locale", default="zh_TW")
    ap.add_argument("--stub", action="store_true",
                    help="印一份可以直接貼進 catalog 的 JSON 骨架")
    args = ap.parse_args(argv)

    from d4t.ui import strings

    path = strings.LOCALE_DIR / ("%s.json" % args.locale)
    try:
        have = json.loads(path.read_text(encoding="utf-8"))
    except Exception:                  # noqa: BLE001
        have = {}
    seen = harvest()
    todo = [(t, n) for t, n in sorted(seen.items(), key=lambda kv: -kv[1])
            if t not in have]

    if args.stub:
        print(json.dumps({t: "" for t, _n in todo},
                         ensure_ascii=False, indent=2, sort_keys=True))
        return 0

    print("%s：%d 句已翻、%d 句還沒有（照出現次數）"
          % (args.locale, len(have), len(todo)))
    for text, n in todo[:40]:
        one = text if len(text) <= 68 else text[:65] + "…"
        print("  %3d  %s" % (n, one))
    if len(todo) > 40:
        print("  …還有 %d 句（`--stub` 印全部）" % (len(todo) - 40))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
