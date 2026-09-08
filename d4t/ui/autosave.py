# 當機、斷電、被關掉 —— 蓋到一半的 pipeline 不可以就這樣沒了 — authored 2026-09-08 (U4).
"""**關窗有網，當機沒有。**

現況（2026-09-08 量的）：`QSettings` 只記主題與版面，recipe 只有 ``Ctrl+S``；
關窗時 `studio._ask_unsaved` 會攔一次，而**當機、斷電、工作管理員砍掉**沒有
任何東西接住 —— ``UNDO_DEPTH = 60`` 那 60 步全部活在 process 裡。

而使用者在這個工具裡花最久的那件事，正好就是「蓋一條 pipeline 再調兩小時」。

為什麼是另一個檔，不是「自動存回原檔」
--------------------------------------
自動存回他的 recipe 會**改掉他的檔案**，而他可能正在試一個他不打算留下來的
改動。所以草稿住在 ``~/.d4t/autosave.json``，跟他的 recipe 完全分開；下次
開窗時**問一句**再還原，不是默默載進去。

「問一句」也是刻意的：一份三天前的草稿被安靜地套上來，比它消失更糟 ——
使用者看到的是一條他不記得自己蓋過的 pipeline，而畫布上沒有任何東西說它
是從哪裡來的（推廣鐵則）。

節流
----
每一次 model 變動就寫一次的話，拖一格滑桿會寫幾十次。所以走一個
``QTimer``：**變動只是重排那個計時器**，安靜下來 :data:`INTERVAL_MS`
之後才真的寫。代價是最後那 1.5 秒可能丟掉 —— 那換到的是「拖滑桿不會卡」，
而拖滑桿正是使用者一整天在做的事。

⚠ 寫檔一律 atomic（``.tmp`` + ``os.replace``，鐵則 5）。這一份的整個意義就是
「當機的那一刻磁碟上有東西」，而一份寫到一半的 JSON 比沒有更糟 —— 它會讓
下次開窗的那句「要救回來嗎」指向一個載不起來的檔案。
"""
from __future__ import annotations

import json
import os
import time
from typing import Any, Dict, Optional

from PySide6.QtCore import QObject, QTimer

__all__ = [
    "FILENAME", "INTERVAL_MS", "DIR", "ASK_ON_START", "folder", "path",
    "save", "load", "clear", "describe", "restore_into", "offer_restore",
    "AutosaveGuard",
]

#: 開窗時要不要問那一句。**測試整批關掉** —— 一個 modal 對話框在 headless
#: 測試裡不會讓測試失敗，它會讓測試永遠停在那裡（同 `studio.PROMPT_ON_CLOSE`）。
ASK_ON_START = True

#: 草稿的檔名。
FILENAME = "autosave.json"

#: 安靜多久之後才真的寫（毫秒）。
#:
#: 1.5 秒是「一格滑桿拖完」與「使用者以為已經存好了」之間的那個數字：更短會
#: 在拖曳過程中一直寫，更長則會讓「剛剛改的那一下」常常來不及進檔案。
INTERVAL_MS = 1500

#: 草稿放哪（``""`` = ``~/.d4t``）。測試用的鉤子，同 `crashlog.LOG_DIR`。
DIR = ""


def folder() -> str:
    """``~/.d4t``（跟 `crashlog` 同一個家：使用者找得到、不需要管理員權限）。"""
    return str(DIR) if DIR else os.path.join(os.path.expanduser("~"), ".d4t")


def path() -> str:
    return os.path.join(folder(), FILENAME)


def save(recipe_json: Dict[str, Any], source_path: str = "",
         dirty: bool = True) -> str:
    """寫一份草稿；回傳寫到哪（寫不出去回 ``""``，**不拋**）。

    ``source_path`` 是「這份草稿本來是哪個檔」—— 救回來之後 ``Ctrl+S`` 才知道
    要存回哪裡。沒有原檔（從頭蓋的）就是空字串。

    ``dirty`` 是**存過了沒有**。存過的草稿仍然寫（當機之後救回來的東西要跟
    畫面上一致），但 :func:`describe` 會照它決定要不要問那一句 —— 一份跟磁碟
    上一模一樣的草稿沒有什麼好救的。
    """
    payload = {
        "at": float(time.time()),
        "source_path": str(source_path or ""),
        "dirty": bool(dirty),
        "recipe": dict(recipe_json or {}),
    }
    dest = path()
    tmp = dest + ".tmp"
    try:
        os.makedirs(os.path.dirname(dest), exist_ok=True)
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(payload, f, ensure_ascii=False)
        os.replace(tmp, dest)
        return dest
    except (OSError, TypeError, ValueError):
        # 存不了草稿**不准擋住任何事** —— 它是一張網，不是一個功能。
        return ""


def load() -> Optional[Dict[str, Any]]:
    """讀回草稿；沒有／讀不動／不是這個形狀 → ``None``。"""
    try:
        with open(path(), "r", encoding="utf-8") as f:
            data = json.load(f)
    except (OSError, ValueError, UnicodeDecodeError):
        return None
    if not isinstance(data, dict) or not isinstance(data.get("recipe"), dict):
        return None
    return data if data["recipe"] else None


def clear() -> None:
    """把草稿刪掉（正常關窗時）。刪不掉就算了。"""
    for name in (path(), path() + ".tmp"):
        try:
            os.remove(name)
        except OSError:
            pass


def describe(data: Optional[Dict[str, Any]]) -> str:
    """要問使用者的那一句 —— **講得出「那是什麼、什麼時候的」**，回 ``""`` = 不用問。

    一句「要救回上次的東西嗎」答不出使用者唯一的問題：*上次是哪一次*。
    所以這一句要帶上時間與原檔名。
    """
    if not data or not data.get("dirty"):
        return ""
    recipe = data.get("recipe") or {}
    n = len(recipe.get("steps") or recipe.get("routes") or {})
    when = time.strftime("%Y-%m-%d %H:%M",
                         time.localtime(float(data.get("at") or 0)))
    src = str(data.get("source_path") or "")
    what = ("“%s”" % os.path.basename(src)) if src else "a pipeline you had "\
        "not saved anywhere yet"
    return ("d4t closed last time without saving %s (last change %s%s).\n\n"
            "Bring it back?" % (what, when,
                                ", %d routes" % n if n else ""))


class AutosaveGuard(QObject):
    """把一個 `StudioWindow` 接上自動存檔 —— **宿主只多一個屬性**。

    刻意做成一個外掛的物件而不是 `StudioWindow` 上的三支方法：那個類別已經
    是 270 個方法的 god object（`tests/test_size_ceilings.py` 正在守它），
    而這件事跟主視窗的其他責任沒有任何耦合 —— 它只需要 ``window.model``
    與 ``window.recipe_path``。
    """

    def __init__(self, window: Any, interval_ms: int = INTERVAL_MS) -> None:
        super().__init__(window)
        self.window = window
        self.timer = QTimer(self)
        self.timer.setSingleShot(True)
        self.timer.setInterval(int(interval_ms))
        self.timer.timeout.connect(self.write_now)
        self._armed = True
        window.model.add_listener(self.touch)

    # ---- 對外 -------------------------------------------------------------
    def touch(self) -> None:
        """model 動了一下 —— **重排計時器**（見模組說明的節流）。"""
        if self._armed:
            self.timer.start()

    def rebind(self) -> None:
        """換過 model 之後重新掛 listener（`_apply_model` 走的那條路）。"""
        try:
            self.window.model.add_listener(self.touch)
        except Exception:                  # noqa: BLE001 — 網不准擋路
            pass
        self.touch()

    def write_now(self) -> str:
        """真的寫一次（計時器到、或關窗前想確保寫過）。"""
        if not self._armed:
            return ""
        model = getattr(self.window, "model", None)
        if model is None or not getattr(model, "node_order", None):
            # 空畫布沒有東西好救 —— 而**留著一份舊草稿更糟**：使用者清空了
            # 畫布、關掉、再開，然後被問要不要救回一條他剛剛才刪掉的 pipeline。
            clear()
            return ""
        try:
            data = model.to_recipe().to_json_dict()
        except Exception:                  # noqa: BLE001 — 網不准擋路
            return ""
        return save(data, str(getattr(self.window, "recipe_path", "") or ""),
                    bool(getattr(model, "dirty", True)))

    def start(self) -> None:
        """重新開始自動存（測試與「暫停過之後」用）。"""
        self._armed = True

    def armed(self) -> bool:
        return bool(self._armed)

    def stop(self) -> None:
        """不再自動存（關窗時；之後的 model 變動一律忽略）。"""
        self._armed = False
        self.timer.stop()


# --------------------------------------------------------------------------- #
# 救回來
# --------------------------------------------------------------------------- #
def restore_into(window: Any, data: Dict[str, Any]) -> bool:
    """把一份草稿套進一個 `StudioWindow`（不問，呼叫端負責問）。

    走的是 `StudioWindow._apply_model` —— **跟載入 recipe 完全同一條路**，
    所以區域線的水合、listener 重掛、面板刷新全部照舊。這裡自己重做一次的話，
    那條路上的每一個修正都要記得抄過來一次。
    """
    from d4t.core.pipeline import Recipe

    from .viewmodel import RecipeModel
    try:
        recipe = Recipe.from_json_dict(dict(data.get("recipe") or {}))
        window._apply_model(RecipeModel.from_recipe(recipe))
    except Exception:                      # noqa: BLE001 — 壞掉的草稿不准擋開窗
        return False
    # **原檔路徑要跟著回來**，不然 `Ctrl+S` 會問「存到哪」，而使用者的答案是
    # 「存回原來那個」—— 那份資訊本來就在草稿裡。
    window.recipe_path = str(data.get("source_path") or "") or None
    # 救回來的東西**還沒有存過**（磁碟上那一份還是舊的），所以是 dirty。
    window.model.dirty = True
    return True


def offer_restore(window: Any) -> bool:
    """開窗時問那一句；答「要」就套進去。回傳有沒有真的套。

    答「不要」就**把草稿刪掉** —— 留著的話下次開窗會再問一次同一件事，而
    使用者已經回答過了。
    """
    data = load()
    question = describe(data)
    if not question:
        clear()                            # 存過了 / 沒東西 → 不留垃圾
        return False
    if not ASK_ON_START:
        return False
    from PySide6.QtWidgets import QMessageBox

    box = QMessageBox(window)
    box.setIcon(QMessageBox.Question)
    box.setWindowTitle("Bring back your unsaved pipeline?")
    box.setText(question)
    box.setInformativeText(
        "d4t keeps a copy of what is on the canvas while you work, so a crash "
        "or a power cut does not take it with it. Saying no throws this copy "
        "away.")
    box.setStandardButtons(QMessageBox.Yes | QMessageBox.No)
    box.setDefaultButton(QMessageBox.Yes)
    if box.exec() != QMessageBox.Yes:
        clear()
        return False
    ok = restore_into(window, data)
    if ok:
        window._status("Brought back the pipeline you had not saved. Save it "
                       "(Ctrl+S) to keep it for good.")
    else:
        clear()
        window._status("The saved copy could not be read, so it was thrown "
                       "away.", "error")
    return ok
