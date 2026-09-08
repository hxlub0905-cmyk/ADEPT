# 在畫面上標「這顆是真的 / 這顆是誤報」 — authored 2026-09-08 (X2).
"""``ground_truth.json`` 以前只能用手打，而目標使用者不會寫 code。

缺口長什麼樣
------------
正確率那條路整套都在：`core.export.summarize` 算得出來、CLI 有
``--ground-truth``、Studio 載資料時會**自動撿 KLARF 旁邊的
``ground_truth.json``**（`studio._load_ground_truth_beside`）。

只有一件事沒有做：**那個檔要使用者自己寫出來。** 而 `CLAUDE.md` 的第二原則
寫著「目標使用者是不會寫 code 的製程/設備工程師」—— 於是「準確率」這個功能
實際上只有開發者用得到，別人拿到 d4t 只能盲調門檻。

這一份不是標注介面
------------------
完整的標注介面在 Phase 3。這裡是**最小的那一版**：結果表上選幾列，按 R
（real）或 N（nuisance），寫回同一個檔。工程師 review 前 100 顆本來就是日常
工作 —— 現在那個動作發生在 d4t 外面，這一份只是把它搬進來。

三條規矩
--------
1. **格式與自動撿的那份逐字相同**（``{defect_id: {"is_real": bool}}``，
   `tools/make_sample.py` 寫的就是這個），所以標完的檔 CLI 的
   ``run --ground-truth`` 直接吃得下 —— 不然這裡等於發明了第二種答案卷。
2. **寫檔是 atomic**（``.tmp`` + ``os.replace``，鐵則 5）。使用者標到第 60 顆
   時當機，前 59 顆不可以變成半個 JSON。
3. **不覆蓋不認得的東西**：檔案裡本來就有的鍵（``type``、別人加的欄位）原封
   留著，只換 ``is_real``。答案卷可能是別的工具產的，而這一份沒有資格決定
   那些欄位不重要。
"""
from __future__ import annotations

import json
import os
from typing import Any, Dict, Optional, Sequence

__all__ = [
    "FILENAME", "path_for", "read", "merge", "write", "counts",
    "is_real_of", "summary_text", "marks_from_rows",
]

#: 答案卷的檔名 —— 這個字串**同時**是 `studio._load_ground_truth_beside`
#: 猜的那個名字與 `tools/make_sample.py` 寫的那個名字。三處對不上的話，
#: 標完之後畫面上不會有任何變化，而沒有任何錯誤訊息。
FILENAME = "ground_truth.json"


def path_for(dataset: Any) -> str:
    """這一份資料集的答案卷該放哪裡（放不了回 ``""``）。

    **KLARF 旁邊**是第一選擇，因為那正是自動撿的時候找的地方。沒有 KLARF 的
    兩種輸入（``tiff_stack`` / ``folder``）退而求其次放在**第一張影像的資料夾**
    —— 使用者眼中「那批資料在哪」就是那個資料夾。
    """
    src = str(getattr(getattr(dataset, "klarf", None), "source_path", "") or "")
    if src:
        return os.path.join(os.path.dirname(os.path.abspath(src)), FILENAME)
    for item in list(getattr(dataset, "items", None) or [])[:1]:
        for ref in (getattr(item, "images", None) or {}).values():
            path = str(getattr(ref, "path", "") or "")
            if path:
                return os.path.join(os.path.dirname(os.path.abspath(path)),
                                    FILENAME)
    return ""


def read(path: str) -> Dict[str, Any]:
    """讀一份答案卷；不存在／讀不動／不是一個 dict → ``{}``。

    ⚠ 只吞「檔案的問題」（`studio._load_ground_truth_beside` 同一條教訓）：
    一個打錯的名字要當場炸掉，不可以長得跟「這份資料沒有答案卷」一樣。
    """
    try:
        with open(str(path), "r", encoding="utf-8") as f:
            data = json.load(f)
    except (OSError, ValueError, UnicodeDecodeError):
        return {}
    return dict(data) if isinstance(data, dict) else {}


def is_real_of(entry: Any) -> Optional[bool]:
    """一筆答案 → ``True`` / ``False`` / ``None``（看不懂）。

    判讀走 `core.export.report._gt_is_real` —— **同一支**，因為畫面上打的勾
    與報表算出來的正確率必須是同一個判讀。自己再寫一份的那天，畫面說標了
    20 顆而報表只認得 12 顆，兩邊都不會報錯。
    """
    from d4t.core.export.report import _gt_is_real
    return _gt_is_real(entry)


def merge(existing: Optional[Dict[str, Any]],
          marks: Dict[str, Optional[bool]]) -> Dict[str, Any]:
    """把幾筆標記併進既有的答案卷（純函式，不碰檔案）。

    ``marks`` 的值：``True`` = 真缺陷、``False`` = 誤報、``None`` = **把這一顆
    的標記拿掉**（不是標成 False —— 「我還沒看」跟「我看過，是誤報」在正確率
    上是兩件完全不同的事，前者不進分母）。

    既有那一筆是 dict 的話只換 ``is_real``，其他鍵原封留著（見模組說明 §3）。
    """
    out: Dict[str, Any] = dict(existing or {})
    for raw_id, value in (marks or {}).items():
        did = str(raw_id)
        if value is None:
            out.pop(did, None)
            continue
        was = out.get(did)
        if isinstance(was, dict):
            entry = dict(was)
            entry["is_real"] = bool(value)
            out[did] = entry
        else:
            out[did] = {"is_real": bool(value)}
    return out


def write(path: str, data: Dict[str, Any]) -> str:
    """把答案卷寫出去（atomic，鐵則 5）。回傳寫到哪；寫不了拋 ``OSError``。

    **空的也要寫。** 使用者把最後一個標記拿掉時，留著一份舊檔等於下次開窗
    又把那些答案撿回來 —— 而他剛剛才決定它們不算數。
    """
    dest = str(path)
    folder = os.path.dirname(os.path.abspath(dest))
    if folder:
        os.makedirs(folder, exist_ok=True)
    tmp = dest + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(dict(data or {}), f, ensure_ascii=False, indent=2,
                  sort_keys=True)
    os.replace(tmp, dest)
    return dest


def counts(data: Optional[Dict[str, Any]]) -> Dict[str, int]:
    """``{"labelled", "real", "nuisance"}`` —— 看不懂的那幾筆不算進任何一格。"""
    real = nuisance = 0
    for entry in (data or {}).values():
        flag = is_real_of(entry)
        if flag is True:
            real += 1
        elif flag is False:
            nuisance += 1
    return {"labelled": real + nuisance, "real": real, "nuisance": nuisance}


def summary_text(data: Optional[Dict[str, Any]],
                 total: int = 0, path: str = "") -> str:
    """狀態列那一句：標了幾顆、寫去哪。

    **標了幾顆要跟「一共幾顆」放在一起**：「20 labelled」在一批 200 顆上與在
    一批 24 顆上的意思差很多，而使用者正在決定「再標幾顆才夠」。
    """
    c = counts(data)
    if not c["labelled"]:
        return "No defects labelled yet." + (
            "  Select rows in the table and press R (real) or N (nuisance).")
    text = "%d labelled" % c["labelled"]
    if total:
        text += " of %d" % int(total)
    text += " · %d real · %d nuisance" % (c["real"], c["nuisance"])
    if path:
        text += " · written to %s" % os.path.basename(str(path))
    return text


def marks_from_rows(defect_ids: Sequence[str],
                    value: Optional[bool]) -> Dict[str, Optional[bool]]:
    """選了幾列 → 一份 ``marks``（`merge` 吃的形狀）。"""
    return {str(d): value for d in defect_ids if str(d)}
