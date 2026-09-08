#!/usr/bin/env python3
# d4t 吞吐量基準 — authored 2026-09-08.
"""量「一顆 defect 要多久、多大」，並把它凍成一份基準。

    python tools/bench.py            # 量一次並寫出 tests/fixtures/bench_baseline.json
    python tools/bench.py --check    # 只比對，不寫檔（超出容差就回非零）
    python tools/bench.py --check --tolerance 1.5    # 收緊時間那幾欄的容差

為什麼需要這支
--------------
`tools/freeze_golden.py` 凍住的是**數字**，這一支凍的是**時間與大小**。
2026-09-08 那份體檢量到的：這個 repo 有 3,442 支測試、三份黃金值、九條卡片
不變量 —— 而**沒有任何一條會在整條 pipeline 慢三倍的時候變紅**。

而「單批 10,000 顆仍然流暢」這句話從 M2 就寫在 README 上，從來沒有被量過。
唯一量過的兩個數字（2026-09-08，4 核容器、`recipes/rsem-worst-box.json`）
還帶著兩個意外：

* **4 個 worker 只換到 1.45×**，不是 3–4×；
* **快取零收益** —— 那份 recipe 的影像段只有一張 load 卡，checkpoint 落在 0，
  等於沒有東西可以快取。

所以這一支刻意用 `die_to_die_basic.json`（load → normalize×2 → subtract →
denoise → cd → glv）：它有**真的影像段**，快取才問得出真話。

嚴的欄位與寬的欄位（這支的設計重點）
------------------------------------
時間會隨機器變，大小與快取行為不會。所以 `--check` 分兩種比法：

* **寬（時間）** —— `ms_per_defect_*`：預設容差 2.0×。跨機器比對時它只是
  「有沒有慢一個數量級」的煙霧偵測器。
* **嚴（結構）** —— `result_bytes_per_defect` / `cache_files` /
  `cache_bytes_per_defect`：
  這幾個是**決定性的**，±2% 以內。一顆 defect 的結果 payload 突然變大 50%，
  講的是「每顆多了一批特徵」；快取存下來的份數變了，講的是 checkpoint 的
  位置動了（`cache_files` 是 0 就代表這份 recipe 根本沒有影像段可以快取）。
  這兩件事跟機器無關，所以它們比時間更值得守。

為什麼記憶體量的是 payload 而不是 RSS
-------------------------------------
真正要回答的問題是「10,000 顆的結果整批留在記憶體裡會怎樣」
（`run_batch` 回傳的是一整個 list）。RSS 量到的是 numpy/OpenCV 的 arena、
行程池、Qt 有沒有載入 —— 跨機器與跨 OS 完全不可比，而且在 Windows 上
（家用機）連 `resource` 都沒有。payload 大小是**可攜、決定性、而且正好是那個
問題的答案**：一顆多少 byte × 10,000。

為什麼不進 CI
-------------
理由跟 `freeze_golden.py` 一字不差：時間欄在 CI runner 上會漂，而一道會隨機
變紅的關很快就變成一道大家學會忽略的關。**這是給人跑的工具**，不是測試。
`tests/test_bench_tool.py` 只驗這支工具本身跑得動、比得動。

本檔與 `tools/` 其他工具一樣是 stdlib-only 的入口，第三方套件都在函式內 lazy
import（`tests/test_offline_tools.py` 會掃）。
"""
from __future__ import annotations

import argparse
import json
import os
import platform
import shutil
import sys
import tempfile
import time

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BASELINE = os.path.join(REPO_ROOT, "tests", "fixtures", "bench_baseline.json")
RECIPE_DIR = os.path.join(REPO_ROOT, "tests", "fixtures", "recipes")

#: 量哪一份 recipe、用哪一種合成資料、幾顆、什麼 seed。
#:
#: 形狀刻意跟 `freeze_golden.CASES` 一樣 —— 兩支工具問的是同一批東西的兩面
#: （算出什麼 vs 花了多久），沒有理由長得不一樣。
#:
#: **`die_to_die_basic` 是刻意選的**：它是唯一一份有完整影像段的 fixture
#: recipe，而影像段正是快取唯一會作用的地方。挑一份沒有影像段的來量，
#: 快取那三欄會永遠是 0（見模組說明）。
#:
#: n=24：夠讓每顆的成本穩下來（前幾顆帶著 import 與 warm-up），又不會讓這支
#: 工具跑成一分鐘。
CASES = (
    # (recipe 檔名,            產生器,        n,  seed)
    ("die_to_die_basic.json", "make_sample", 24, 7),
)

#: 時間欄的預設容差（倍數）。
#:
#: 2.0 很寬，那是刻意的：這支的用途是「**有沒有慢一個數量級**」，不是
#: 「有沒有慢 8%」。要在同一台機器上抓細微退步的話用 `--tolerance 1.2`。
DEFAULT_TOLERANCE = 2.0

#: 決定性的那幾欄，容許的相對誤差。
#:
#: 不寫 0 是因為 `result_bytes_per_defect` 裡有浮點數的字串表示 ——
#: numpy 換一個 minor 版本可能讓某一個數字多印一位。2% 遠小於任何真正的
#: 「每顆多了一批特徵」。
EXACT_RTOL = 0.02

#: 哪幾欄用嚴格的比法。
EXACT_FIELDS = ("result_bytes_per_defect", "cache_files",
                "cache_bytes_per_defect")

#: 外推到幾顆 —— README 上那句「單批 10,000 顆仍然流暢」的那個數字。
EXTRAPOLATE_TO = 10000


def _load_case(gen, n, seed, workdir):
    """產一份合成 lot 並載進來。"""
    sys.path.insert(0, REPO_ROOT)
    sys.path.insert(0, os.path.join(REPO_ROOT, "tools"))
    from d4t.core.ingest.dataset import load_dataset

    module = __import__(gen)
    lot = module.generate(workdir, n=n, seed=seed)
    return load_dataset(lot["klarf"])


def _time_run(recipe, dataset, workers, cache_dir=None):
    """跑一次整批，回 ``(秒, 結果 list)``。"""
    from d4t.core.pipeline.batch import run_batch

    t0 = time.perf_counter()
    results = run_batch(recipe, dataset, workers=workers, cache_dir=cache_dir)
    return time.perf_counter() - t0, results


def measure(recipe_file, gen, n, seed):
    """量一個 case，回一份純資料（沒有路徑、沒有時間戳）。"""
    sys.path.insert(0, REPO_ROOT)
    sys.path.insert(0, os.path.join(REPO_ROOT, "tools"))
    import d4t.core.steps                                    # noqa: F401
    from d4t.core.pipeline import Recipe
    from d4t.core.pipeline.batch import pin_cv2_deterministic
    from d4t.core.pipeline.cache import StageCache

    pin_cv2_deterministic()
    recipe = Recipe.load(os.path.join(RECIPE_DIR, recipe_file))
    workdir = tempfile.mkdtemp(prefix="d4t_bench_")
    cache_dir = os.path.join(workdir, "cache")
    try:
        dataset = _load_case(gen, n, seed, os.path.join(workdir, "lot"))
        workers = min(4, os.cpu_count() or 1)

        # ---- 序列 ----
        secs_1, results = _time_run(recipe, dataset, workers=1)
        # ---- 平行 ----
        secs_n, _ = _time_run(recipe, dataset, workers=workers)
        # ---- 冷快取 → 熱快取 ----
        secs_cold, _ = _time_run(recipe, dataset, workers=1, cache_dir=cache_dir)
        secs_warm, _ = _time_run(recipe, dataset, workers=1, cache_dir=cache_dir)
        stats = StageCache(cache_dir).stats()

        payload = len(json.dumps(results, default=str).encode("utf-8"))
        row = {
            "n": n,
            "workers": workers,
            "ms_per_defect_w1": round(secs_1 / n * 1000.0, 3),
            "ms_per_defect_wn": round(secs_n / n * 1000.0, 3),
            "ms_per_defect_cache_cold": round(secs_cold / n * 1000.0, 3),
            "ms_per_defect_cache_warm": round(secs_warm / n * 1000.0, 3),
            "result_bytes_per_defect": round(payload / n, 1),
            # ⚠ `StageCache.stats()` 回的是**磁碟現況**（`n_files` / `bytes`），
            # 不是 hit/miss 計數 —— 第一版寫 `stats.get("hits")`，於是這兩欄
            # 永遠是 0，而「快取沒在做事」跟「我讀錯鍵」長得一模一樣。
            # 現在量的是「影像段真的被存下來幾份」：這是決定性的，而且
            # checkpoint 落在 0（沒有影像段可存）時它就是 0，一眼看得出來。
            "cache_files": int(stats.get("n_files", 0)),
            "cache_bytes_per_defect": round(stats.get("bytes", 0) / n, 1),
        }
        # 兩個「所以呢」的數字。它們是上面那幾欄推出來的，不參與 --check
        # 的比對（比了等於同一件事比兩次），但它們是人真正會讀的兩行。
        row["parallel_speedup"] = round(secs_1 / secs_n, 2) if secs_n else 0.0
        row["cache_speedup"] = round(secs_cold / secs_warm, 2) if secs_warm else 0.0
        return row
    finally:
        shutil.rmtree(workdir, ignore_errors=True)


def _env():
    """這份基準是在什麼上面量的 —— 跨機器比對時看得出是不是蘋果比橘子。"""
    versions = {}
    for mod in ("numpy", "cv2"):
        try:
            versions[mod] = __import__(mod).__version__
        except Exception:                       # pragma: no cover — 沒裝就不寫
            versions[mod] = "?"
    return {
        "python": platform.python_version(),
        "platform": platform.system(),
        "cpu_count": os.cpu_count() or 0,
        "numpy": versions["numpy"],
        "cv2": versions["cv2"],
    }


def _tag(recipe_file, gen):
    return "%s__%s" % (os.path.splitext(recipe_file)[0], gen)


def collect():
    return {
        "env": _env(),
        "cases": {_tag(r, g): measure(r, g, n, s) for r, g, n, s in CASES},
    }


def _print_case(tag, row):
    print("  %s" % tag)
    print("    一顆 defect：%.1f ms（序列）／%.1f ms（%d workers，%.2f×）"
          % (row["ms_per_defect_w1"], row["ms_per_defect_wn"],
             row["workers"], row["parallel_speedup"]))
    print("    快取：冷 %.1f ms → 熱 %.1f ms（%.2f×，存下 %d 份／每顆 %.0f KB）"
          % (row["ms_per_defect_cache_cold"], row["ms_per_defect_cache_warm"],
             row["cache_speedup"], row["cache_files"],
             row["cache_bytes_per_defect"] / 1024.0))
    mins = row["ms_per_defect_wn"] * EXTRAPOLATE_TO / 1000.0 / 60.0
    mb = row["result_bytes_per_defect"] * EXTRAPOLATE_TO / 1024.0 / 1024.0
    print("    外推 %d 顆：約 %.1f 分鐘，結果 payload 約 %.0f MB"
          % (EXTRAPOLATE_TO, mins, mb))


def _compare(old, new, tolerance):
    """回一張 ``(欄位, 舊, 新, 說明)`` 的差異清單（空的＝通過）。"""
    bad = []
    for tag, new_row in sorted(new["cases"].items()):
        old_row = old.get("cases", {}).get(tag)
        if old_row is None:
            bad.append((tag, "—", "(新的 case)", "基準裡沒有這一項，重跑一次凍結"))
            continue
        for field in sorted(new_row):
            if field in ("parallel_speedup", "cache_speedup", "n", "workers"):
                continue
            was, now = old_row.get(field), new_row[field]
            if was in (None, 0):
                continue
            ratio = float(now) / float(was)
            if field in EXACT_FIELDS:
                if abs(ratio - 1.0) > EXACT_RTOL:
                    bad.append(("%s.%s" % (tag, field), was, now,
                                "這一欄是決定性的（±%d%%）—— 變了代表行為變了，"
                                "不是機器變了" % int(EXACT_RTOL * 100)))
            elif ratio > tolerance:
                bad.append(("%s.%s" % (tag, field), was, now,
                            "慢了 %.2f×（容差 %.1f×）" % (ratio, tolerance)))
    return bad


def main(argv=None):
    ap = argparse.ArgumentParser(description="d4t 吞吐量基準")
    ap.add_argument("--check", action="store_true",
                    help="只比對現有基準，不寫檔")
    ap.add_argument("--tolerance", type=float, default=DEFAULT_TOLERANCE,
                    help="時間那幾欄容許慢幾倍（預設 %.1f）" % DEFAULT_TOLERANCE)
    ap.add_argument("--out", default=BASELINE, help="基準檔路徑")
    args = ap.parse_args(argv)

    # ⚠ **先看基準在不在，再開始量。** 反過來的話，一台還沒凍過基準的機器要
    # 先等 20 秒才被告知「找不到基準」—— 而那 20 秒量到的東西整份丟掉。
    if args.check and not os.path.exists(args.out):
        print("✗ 找不到基準 %s —— 先跑一次 `python tools/bench.py`" % args.out)
        return 2

    new = collect()
    print("量到的（%s / Python %s / numpy %s / cv2 %s / %d 核）："
          % (new["env"]["platform"], new["env"]["python"], new["env"]["numpy"],
             new["env"]["cv2"], new["env"]["cpu_count"]))
    for tag, row in sorted(new["cases"].items()):
        _print_case(tag, row)

    if not args.check:
        os.makedirs(os.path.dirname(args.out), exist_ok=True)
        tmp = args.out + ".tmp"
        with open(tmp, "w", encoding="utf-8") as fh:
            json.dump(new, fh, ensure_ascii=False, indent=2, sort_keys=True)
            fh.write("\n")
        os.replace(tmp, args.out)               # 鐵則 5：原子寫入
        print("→ 已寫入 %s" % args.out)
        return 0

    with open(args.out, encoding="utf-8") as fh:
        old = json.load(fh)
    if old.get("env") != new["env"]:
        print("⚠ 這份基準是在別的環境凍的（%s）—— 時間那幾欄不可比，"
              "決定性的那幾欄照樣要對得上。" % old.get("env"))
    bad = _compare(old, new, args.tolerance)
    if not bad:
        print("✓ 全部在容差內")
        return 0
    print("✗ %d 項超出容差：" % len(bad))
    for field, was, now, why in bad:
        print("    %-52s %s → %s（%s）" % (field, was, now, why))
    return 1


if __name__ == "__main__":                      # pragma: no cover
    sys.exit(main())
