# 試跑抽哪幾顆 — authored 2026-09-08 (X3).
"""**「First 200」在一片 wafer 上是一個統計陷阱。**

`run_batch(limit=200)` 拿的是 ``items[:200]`` —— KLARF 順序的前 200 顆。而
KLARF 通常照**掃描順序**排：前 200 顆很可能集中在少數幾個 die，或者根本是同
一個 cluster 的鄰居。在那一批上調好的門檻，整批一跑就崩，而**畫面上沒有任何
東西提示過這件事** —— 使用者只知道「試跑看起來很好」。

三種模式，一句話各自的用途
--------------------------
=========== ================================================================
``first``   KLARF 順序的前 N 顆。**留著，而且仍然是預設** —— 它是唯一
            「每次都一樣、而且跟上一版比得起來」的一種，調參數的時候要的正
            是那個。陷阱不在這個模式，在於它以前是**唯一**的一種。
``random``  整批裡隨機 N 顆。要回答「這組門檻在整片上站不站得住」時用它。
``strata``  照 KLARF 的某一欄分層，各層照比例抽。缺陷分類（CLASSNUMBER）
            分布很不平均，隨機抽很容易讓稀少的那一類一顆都沒抽到 —— 而那一
            類常常正是使用者在調的那一類。
=========== ================================================================

⚠ **種子要記得下來。** 一次「random 200」跑出漂亮的結果而重現不了，等於沒有
跑過。:func:`pick` 因此**永遠**回一個種子（沒給就自己生一個），呼叫端把它寫
進 run 紀錄；同一個種子 ＋ 同一份 items ＝ 同一批顆，逐顆相同。

⚠ 這一支**不 import Qt，也不 import numpy**（鐵則 1／stdlib-only 的工具鏈）。
它拿的是一串 item、回的是一串 item。
"""
from __future__ import annotations

import random
from typing import Any, Dict, List, Optional, Sequence, Tuple

__all__ = ["MODES", "DEFAULT_MODE", "describe", "new_seed", "pick"]

#: 認得的模式。**順序＝UI 上由左到右的順序**（`first` 排第一，它是預設）。
MODES = ("first", "random", "strata")

DEFAULT_MODE = "first"

#: 給使用者看的字：模式 → (工具列上的字, 一句白話)。
#:
#: 工具列那一格以前寫死是「First」，於是換了抽樣方式而畫面沒有變 ——
#: 那正是這個功能最危險的失敗方式（跑的東西變了、看的人不知道）。
_WORDS = {
    "first": ("First", "The first N in KLARF order - repeatable, but they are "
                       "often clustered in a few dies"),
    "random": ("Random", "N drawn at random from the whole lot - the honest "
                         "check that a threshold holds wafer-wide"),
    "strata": ("Stratified", "N drawn in proportion from each value of a "
                             "KLARF column, so rare classes still show up"),
}


def describe(mode: str) -> Tuple[str, str]:
    """(工具列上的字, 一句白話)。不認得的模式退回 ``first``。"""
    return _WORDS.get(str(mode or ""), _WORDS[DEFAULT_MODE])


def new_seed() -> int:
    """生一個種子。**範圍刻意小到人抄得動**（六位數）—— 它會被寫進 run 紀錄，
    而使用者要能把它唸給同事聽。"""
    return random.randrange(100000, 999999)


def _value_of(item: Any, column: str) -> str:
    """這一顆在那一欄的值（一律 str、strip 過）。取不到回空字串。

    跟 `RouteBy` 同一套：KLARF 的值都是字串，``"1"`` 與 ``" 1"`` 要落在同一層
    （`CLAUDE.md` §5 那一段的規矩，不要在這裡發明第二套）。
    """
    fields = getattr(item, "fields", None) or {}
    try:
        return str(fields.get(str(column).upper(), "") or "").strip()
    except Exception:              # noqa: BLE001 — 抽樣不准害死一次跑
        return ""


def pick(items: Sequence[Any], limit: int, mode: str = DEFAULT_MODE,
         seed: Optional[int] = None,
         column: str = "CLASSNUMBER") -> Tuple[List[Any], Dict[str, Any]]:
    """挑出這一次要跑的顆，回 ``(挑到的, 這一次的抽樣紀錄)``。

    紀錄長 ``{"mode", "seed", "column", "n", "of"}`` —— 它進 run 紀錄，
    而「怎麼重現這一次」就寫在裡面。

    **回傳順序永遠是原始順序**（不是抽中的順序）。`run_batch` 的契約是
    「回傳順序 = 原始 item 順序」，而下游的 KLARF 寫回、結果表、縮圖全部
    依賴它 —— 抽樣不該把那件事改掉。
    """
    pool = list(items or [])
    n = max(0, min(int(limit), len(pool)))
    use = str(mode or DEFAULT_MODE)
    if use not in MODES:
        use = DEFAULT_MODE
    note: Dict[str, Any] = {"mode": use, "seed": None, "column": "",
                            "n": n, "of": len(pool)}
    if n == 0 or not pool:
        return [], note
    if use == "first":
        # 不消耗種子：`first` 每次都一樣，給它一個種子只會讓紀錄看起來像
        # 隨機的（而那是一句謊）。
        return pool[:n], note

    s = int(seed) if seed is not None else new_seed()
    note["seed"] = s
    rng = random.Random(s)

    if use == "random":
        chosen = rng.sample(range(len(pool)), n)
        return [pool[i] for i in sorted(chosen)], note

    # ---- strata ----------------------------------------------------------
    note["column"] = str(column or "").upper()
    layers: Dict[str, List[int]] = {}
    for i, it in enumerate(pool):
        layers.setdefault(_value_of(it, column), []).append(i)
    # 那一欄整批都是空的（沒 carry、或這份 KLARF 沒有這一欄）→ **退成
    # random 並在紀錄裡說出來**。硬分一層的話它跟 random 一模一樣，而紀錄會
    # 說它是分層的 —— 跑得完、有數字、而且紀錄是錯的。
    if len(layers) <= 1:
        note["mode"] = "random"
        note["column"] = ""
        chosen = rng.sample(range(len(pool)), n)
        return [pool[i] for i in sorted(chosen)], note

    # 每層照比例，**每一層至少一顆**（稀少的那一類正是使用者在調的那一類，
    # 而「照比例」對一個只有 3 顆的類別算出來是 0）。
    keys = sorted(layers)
    quota = {k: 1 for k in keys}
    left = n - len(keys)
    if left < 0:
        # 層比要抽的顆還多 —— 隨機挑 n 層，各一顆。
        for k in rng.sample(keys, len(keys) - n):
            quota.pop(k)
        left = 0
    if left > 0:
        weights = [(k, len(layers[k]) / float(len(pool))) for k in quota]
        for k, w in weights:
            quota[k] += int(left * w)
    picked: List[int] = []
    for k, want in quota.items():
        want = min(want, len(layers[k]))
        picked.extend(rng.sample(layers[k], want))
    # 四捨五入會少幾顆 —— 從還沒抽到的裡面補滿，不然「200」講的是假話。
    if len(picked) < n:
        rest = [i for i in range(len(pool)) if i not in set(picked)]
        picked.extend(rng.sample(rest, min(n - len(picked), len(rest))))
    picked = picked[:n]
    return [pool[i] for i in sorted(picked)], note
