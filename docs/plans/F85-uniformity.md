# F85：把 PEAR 的均勻度搬進來（2026-09-07）

使用者：

> 「我想將 PEAR 專案的功能移植進 d4t studio 讓他成為一張卡片」
>
> 「1. 不用自己畫 ROI，直接接現有的 ROI 卡去定義區域即可
>  2. 主要是想區域看均勻度，然後還有輸出要向 PEAR 一樣有多種圖表
>     （然後也可以 custom 設定輸出圖表長怎樣）：直方圖 盒鬚圖 Heat map 圖
>     Position 圖等等」

四個決定（同一輪問答）：

| 問 | 答 |
|---|---|
| 要不要加 `Open image…` 入口 | **加** |
| 會接幾群 | **至多三群，預設兩群** |
| 均勻度指標預設吐哪幾個 | **`cv_pct` + `slope_x` + `slope_y`，其餘可勾** |
| 外觀設定 | **先做 (C)**：只做「看不看得懂」的那四項 |

---

## 0. 先講一件文件與程式碼已經漂掉的事

`CLAUDE.md` §6 與 `README.md` 的來源表都寫著：

> **PEAR** | GLV 統計 metric bank、Tukey 離群、**η²／Cohen's d**、CJK-safe 影像載入、SNR 正負號正典

而整個 repo **grep 不到 `cohens_d` 或 `attribute_separability`**。

`docs/plans/F11-phase2-features.md` 留著它的墓碑：

> `algo/stats.py`（`group_outliers` / `cohens_d` / `attribute_separability`，
> 85 行，vendored from PEAR）｜**沒有任何卡片**。只有 `algo/__init__` re-export
> 與 `tests/test_stats.py`

也就是說：**它進來過，因為零個呼叫者被清掉了，而兩份文件沒有跟上。**
這正是 `CLAUDE.md` §0 開頭那句話講的東西（「抄第二份出來的那份一定會漂移」），
只是這一次漂的方向相反 —— 文件講得比程式碼多。

這一輪把它**真的**搬回來，順便讓那兩張表變成真的。
另外 `d4t/ui/scope.py` 那張「不准刪的孤兒模組」表要加一列（見 §9）。

---

## 1. 這一輪做什麼、不做什麼

### 做

1. **`Open image…`** —— 第四個 Input 入口（一張圖 = 一顆 defect，沒有 KLARF）
2. **`uniformity`「Uniformity」** —— Measure 段一張新卡
3. **四種圖**，兩條路各畫一次：畫面上的儀表（QPainter）＋ 檔案裡的 SVG
4. **`output_uniformity`「Write uniformity」** —— Output 段一張新卡

### 不做（講清楚才不會被當成漏掉）

| 不做 | 為什麼 |
|---|---|
| 手放 ROI（點一下放一格／拉網格／對齊／方向鍵微調）| 使用者第 1 點明說不用。d4t 的框由 Region 卡產 |
| ROI JSON 匯入匯出 | 同上 —— 沒有手放框，就沒有「把手放的結果搬走」這件事 |
| PEAR 的 ROI pixel inspector（雙擊看一格的像素）| `GlvInspector` 已經在做很接近的事 |
| 外觀設定第二批（字級、粗體、顏色、點半徑、線寬）| 使用者選 (C)。理由見 §7 |
| 把均勻度折進 `glv_stats` | 見 §4.1 —— 那張卡的基底結構上做不到跨群比較 |

---

## 2. 概念對照

| PEAR | d4t | 現況 |
|---|---|---|
| **Group**（圓孔 vs 方孔）| **具名區域家族**（`epi` / `mg`）| ✅ `roi_reference` |
| **ROI**（一個量測框）| 家族底下的**一格框**（`ctx.roi_rects(name, shape)`）| ✅ |
| metric（GLV 統計量）| 同一份 bank（`algo/glv.py`，是 PEAR 的超集）| ✅ |
| 群組**內**逐 ROI 找異常 | `glv_stats` 的 `each box`（`_typical` / `_outlier` / `worst_*`）| ✅ 已經有 |
| **群組內均不均勻** | — | ❌ 本輪 |
| **群組之間誰分得開** | — | ❌ 本輪 |
| 四種圖 | — | ❌ 本輪 |

---

## 3. `Open image…`（Input 段第四個入口）

`CLAUDE.md` §5：**加／改一個入口＝改 `scope.INPUT_SOURCES`，不要動 UI。**
工具列的鈕與空白狀態的那一列都是從那張表長出來的。

```python
InputSource(
    key="image", kinds=("folder",), title="Open image…", short="Image…",
    what="One image file, on its own - it becomes a single defect.",
    icon="image", has_klarf=False),
```

`kinds` 仍然是 `folder`（**不新增第五種 `dataset.kind`**）—— 資料形狀
一模一樣（`images={"single": …}`、沒有座標、寫不回 KLARF），
多一個 kind 等於讓 `SUPPORTED_KINDS`、`recipe_is_supported`、
`tests/test_ui_input_kinds.py` 全部多一列，換到零。

`ingest/dataset.py` 加一支 `load_image_file(path) -> Dataset`：
`load_folder` 的單檔版，共用同一支 `_IMAGE_EXTS` 與同一句多頁 TIFF 的警告
（那句話要改成指向 `Open stack…`，跟現在逐字一樣）。

**代價**：資料集標籤仍然說 `folder · defect 1 / 1 · no KLARF`。
「入口叫 image、標籤說 folder」是一個小誤差 —— 我傾向留著（kind 是資料形狀，
不是入口名），但如果覺得刺眼，改的是標籤那一句話不是 kind。

---

## 4. `uniformity`「Uniformity」（Measure 段）

### 4.1 這一輪最重要的結構發現：**它不能繼承 `MultiSourceStep`**

`MultiSourceStep.run` 的迴圈長這樣（`steps/_util.py:1441`）：

```python
for key in self.source_list(p):
    for region in regions:
        one = dict(p, **{self.REGION: region})   # ← 一次一個區域
        feats = self.measure(ctx, img, one)
```

也就是說：**子類的 `measure` 一次只看得到一個區域。** 那是刻意的設計
（「子類不必知道接了幾個區域」），而它對 GLV / CD / Focus 全部成立 ——
因為那三張卡問的都是「**這一塊**是多少」。

但 η² 與 Cohen's d 問的是「**這幾塊之間**分不分得開」，它們**必須同時看到所有
區域**。所以：

> **決定**：`UniformityStep` 直接繼承 `Step`，自己寫迴圈。
> 均勻度那一半照樣逐區域算（跟基底做的一樣），跨群那一半在迴圈**外面**算。

⚠ 那個「自己寫迴圈」有兩件事一定要照抄基底的行為，否則名字會漂：

* `stream_prefix` / `region_prefix` —— **只接一條／一個時前綴是空的**。
  這不是美觀問題：那是 d4t 全部量測卡的既有文法，兩張卡兩種寫法的話，
  同一份 CSV 上會有 `cv_pct` 與 `epi_cv_pct` 兩種欄名而看不出關係。
* `CURRENT_REGION_INDEX` —— 區域的**顏色**照它挑（`theme.REGION_COLORS`）。
  各自從自己那邊數的話，`"top,bot"` 在一邊是 0/1、在另一邊是 1/0，
  而**顏色指錯區域比沒有顏色糟得多**（`_util.py` 原話）。

這兩支我打算從 `MultiSourceStep` 抽成模組級函式，兩邊共用 —— 不是複製。

### 4.2 為什麼不折進 `glv_stats` 的 method

`CLAUDE.md` §3 有一條「同一個家族的做法收成一張卡的 `method`」，這裡**不適用**，
三個理由由重到輕：

1. **結構上做不到**（§4.1）。`glv_stats` 是 `MultiSourceStep`，它的 `measure`
   看不到第二個區域。
2. **F19 那條分界**：「改變『量得出什麼』的那種選擇是岔路，不是 method」。
   GLV 問「這一塊多亮」，Uniformity 問「這一群框之間差多少」—— 兩個問題。
3. `glv_stats` 已經是 repo 裡參數最多的一張卡（docstring 120 行）。

**代價量過**：兩張卡都接同一個區域的話，同一組像素會被算兩次
（每格框的灰階統計）。實測基準在 `roi_reference` 的 docstring 裡
（N=5295 的框、`glv_stats` 約 105 ms／顆）—— 也就是最壞情況多約 100 ms／顆。
而使用者這一輪的用法（PEAR 的替代品）**多半只會放 Uniformity 一張**，
那筆錢不會付。

### 4.3 參數

| 段 | 參數 | 型別 | 預設 | 說明 |
|---|---|---|---|---|
| 1 在哪量 | `source` | `image_key`（in）| `test` | 拉線決定，設定區唯讀 |
| | `roi` | `region_keys`（in）| — | 拉線決定，**一到三條** |
| 2 量什麼 | `metrics` | `multi_choice` | `glv_median` | 跟 GLV 卡同一份 bank |
| 3 要哪些均勻度數字 | `report` | `multi_choice` | `cv_pct,slope_x,slope_y` | 見 §4.4 |
| 4 兩群比較 | `compare_groups` | `bool` | `True`（接 2+ 群才顯示）| 見 §4.5 |
| | `outlier_k` | `float` | `1.5` | Tukey 的 k，`advanced` |

`show_when` 用法：`compare_groups` 只在接 2 個以上區域時才有意義 ——
但 `show_when` 只看得到**參數值**，看不到接了幾條線。所以它**永遠顯示**，
而接一群時它算不出東西、一格都不寫（F19：「算不出來的那一格不寫」）；
`configuration_issues` 講一句話（「只接了一群，兩群比較不會有數字」）。

### 4.4 特徵名

文法固定是 **哪一塊 → 量什麼 → 什麼統計**，跟現有的 `epi_glv_median_typical`
逐字同一套：

| 名字（接兩群時）| 意思 |
|---|---|
| `epi_glv_median_range` | 最亮那格 − 最暗那格 |
| `epi_glv_median_range_pct` | ↑ 佔平均的 % |
| `epi_glv_median_cv_pct` | 標準差佔平均的 %（**預設**）|
| `epi_glv_median_slope_x` | 左到右每 100 px 變多少（**預設**）|
| `epi_glv_median_slope_y` | 上到下每 100 px 變多少（**預設**）|
| `epi_glv_median_outliers` | 幾格是 Tukey 離群 |
| `epi_glv_median_n` | 這一群量得出來的有幾格 |

**只接一群時前綴是空的**（`glv_median_cv_pct`）—— §4.1 那條既有文法。

⚠ **`slope_x` 的單位是「每 100 px」，不是「每 px」。** PEAR 就是這樣報的，
理由是每 px 的斜率在真實資料上是 0.00x 那種數字，CSV 上看起來全部都是 0。
單位要進 `ParamSpec` 的 `unit` 與 feature 的說明兩邊。

### 4.5 兩群比較 —— η² 與 Cohen's d 是**兩種形狀**

| | 問的是 | 出幾個數字 |
|---|---|---|
| **η²** | 這幾群整體分不分得開（0–1）| 每個量 **1 個** |
| **Cohen's d** | A 比 B 大幾個標準差 | 每個量 **每一對各 1 個** |

使用者定調**至多三群**，所以 Cohen's d 最多 3 對：

| 名字 | 幾群時出現 |
|---|---|
| `sep_glv_median_eta2` | 2 或 3 群 |
| `epi_vs_mg_glv_median_d` | 2 群 |
| `epi_vs_mg_…_d` / `epi_vs_sti_…_d` / `mg_vs_sti_…_d` | 3 群 |

**上限釘在 3**（`configuration_issues` 對第四條線報一句話）。
理由不是實作困難，是 Cohen's d 的對數是 n(n−1)/2 —— 4 群是 6 對、5 群是 10 對，
乘上勾了幾個量，CSV 會爆掉，而那件事在畫布上完全看不出來。

`sep_` 這個前綴**不帶區域名**（它本來就是「所有群一起」的數字）。
⚠ 這讓它跟 `cmp_`（GLV 的比較家族）在同一份 CSV 上並存 —— 兩者不同：
`cmp_` 是「這一塊 vs 那一塊」的一個差值，`sep_` 是「這幾群分不分得開」的
一個效果量。F18「名字要分家族」那條規矩要的正是這個。

### 4.6 欄位數的實際大小

3 群 × 3 個量 × 7 欄 ＝ **63 欄**，加 η²（3）與 Cohen's d（9）＝ **75 欄**。

所以 §4.3 的 `report` 是**可勾的**，預設只給三個
（`cv_pct` / `slope_x` / `slope_y` ＝ 「均不均勻」＋「有沒有斜掉」）。
預設組合是 2 群 × 1 個量 × 3 欄 ＝ **6 欄** —— 那才是打開卡片看到的樣子。

---

## 5. 四種圖

### 5.1 四種圖分別是什麼

| 值 | 畫面上的字 | X | 一個點 | 回答 |
|---|---|---|---|---|
| `box` | Box plot | 區域 | 一格框 | 這幾群各自的分布 |
| `histogram` | Histogram | 灰階值 | 一格框 | 值怎麼散開 |
| `profile` | Across the field | 框中心的 X 或 Y | 一格框 | 有沒有斜掉 |
| `map` | Heat map | 框的 (x, y) | 一格框（顏色＝值）| 不均勻在**哪裡** |

四種都是「**一格框一個點**」—— 一致，不會混。

### 5.2 ⚠ 這跟現在的盒鬚圖**不是同一個東西**

`output_report` 的 `boxplot` 是：**一個盒子＝判定樹的一片葉子，一個點＝一顆
defect**（整批的圖）。這一輪的是：**一個盒子＝一個區域，一個點＝一格框**
（一張圖之內的圖）。

兩者不能共用，也不打算共用。這件事寫在這裡，是因為它們在畫面上長得一模一樣，
而「一個點是什麼」是唯一的差別 —— 那正是最容易在半年後被誰「順手合併」的形狀。

### 5.3 兩份繪圖程式碼，以及為什麼不能只有一份

| 要什麼 | 住哪 | 現有先例 |
|---|---|---|
| 畫面上看 | `d4t/ui/uniformity_inspector.py`（QPainter）| `AlignInspector` 畫整批位移散佈圖 |
| 檔案裡 | `d4t/core/export/uniformity_charts.py`（**手寫 SVG，零新套件**）| `export/boxplot.py`、`klarf_core._svg_wafer` |

**這是鐵則 1 的直接後果**：`core` 不准 import Qt，而檔案輸出必須在 core
（批次跑在沒有畫面的地方）。現在的盒鬚圖就是這樣活著的。

考慮過的第三條路 —— **core 產 SVG、Studio 用 `QSvgWidget` 顯示** —— 這一輪
**不走**，兩個理由：

1. `QtSvg` 現在**不是相依**（`requirements.txt` 只有 numpy / opencv /
   tifffile / PySide6 / openpyxl，而 QtSvg 是 PySide6 的一個獨立模組）。
   多一個在受限機器上會裝不起來的東西，換到的是「少寫一份繪圖程式碼」。
2. 儀表要 hover（滑到哪一格框，那一格亮起來）—— 靜態 SVG 給不了。

**代價誠實寫下來**：兩份程式碼會漂。防線是 §8 的測試 ——
兩份吃**同一支** `core` 算出來的資料（`uniformity_series()`），
所以會漂的是畫法不是數字，而數字才是報表上被引用的東西。

### 5.4 要跟著搬的兩支「不顯眼但關鍵」的函式

`jitter_tolerance` 與 `cluster_positions`（PEAR `analysis.py`）。

它們解的問題是：**框的中心差幾個 px，算不算同一欄。** PEAR 是因為手放框才需要
它；d4t 的框由卡片產，看起來應該很整齊 —— 但 `roi_reference` 的
`stripes in the image` 走的是次像素邊緣定位，出來的中心**本來就不是整數**，
而 `layout layers` 從 label map 拆矩形，一條 45° 斜帶會拆出 5,295 個階梯狀的
小塊。兩條路都會踩到。

不搬的下場是 `profile` 那張圖「一格框一個轉折」而不是「一欄一個轉折」，
以及 `map` 的格子碎成一堆細條 —— PEAR 的 README 逐字描述過這個症狀
（「a grid of eight columns shatters into thirty-odd slivers」）。

---

## 6. `output_uniformity`「Write uniformity」（Output 段）

### 6.1 為什麼是新卡，不是併進 `Write report`

`Write report` 是「整批跑完寫**一份總表**」；這幾張圖是「**一張圖之內**的分布」。
硬併進去 = 一張卡有兩種跑法，而 d4t 踩過這個坑（F50，`ui/output_band.py`
被刪掉的理由：**框的意思是「這幾個是一組」，真相卻是「跑的時間不一樣」**）。

### 6.2 名字怎麼區分

Output 段現有的文法是「Write ＋ 寫什麼出去」：

| 卡 | 一句話（會寫進 help，這才是真正區分它們的東西）|
|---|---|
| **Write report** | 整批跑完一份總表 —— 每顆 defect 一列，加判定結果的盒鬚圖 |
| **Write KLARF** | 把分數與分類寫回原本那份 KLARF |
| **Write comparison** | 兩份資料點對點對照 |
| **Write uniformity** | 一張圖裡的區域分布 —— 每一格框一個點，四種看法 |

先例已經在：`pair_source`（掛第二份資料）↔ `Write comparison`
就是「一張量測卡配一張輸出卡」。這一輪照做：**Uniformity ↔ Write uniformity**。

### 6.3 逐顆的圖住在一張跨顆的卡上

Output 卡是 `CATEGORY_BATCH`（跑完全部才跑一次），而這些圖是逐顆的。
機制已經有：`BatchContext.rerun(item)` 重跑一顆拿回它的 Context
（「出圖那幾張卡要重跑一次 pipeline 才拿得到像素」，有快取時只跑算法段）。

參數照 `output_report` 的形狀：

| 參數 | 說明 |
|---|---|
| `folder` | 寫到哪 |
| `charts` | `multi_choice`：要哪幾種圖（預設四種全開）|
| `limit` | 最多出幾顆的圖（**預設 20**，0 = 全部）|

⚠ **`limit` 預設不是 0。** 使用者這一輪是一張大圖（1 顆），怎麼設都一樣；
但一份 400 顆的 lot 接上這張卡會寫出 1,600 個檔案，而那件事在畫布上看不出來。
`output_report` 的 `limit` 預設是 0（全部），因為它出的是縮圖；這裡出的是
四張圖 × 每顆，量級不同。

---

## 7. 外觀設定：第一批做什麼

使用者選 **(C)**。

### 做（都住在 `output_uniformity` 與儀表上）

| 項目 | 為什麼非有不可 |
|---|---|
| 畫哪幾種圖 | — |
| 圖的標題、X／Y 軸名 | 報告裡要用 |
| **鎖定數值範圍** | **這一項最重要**。auto 縮放在看一批時是對的，兩批擺在一起就會騙人 —— 各自挑各自的範圍，一樣高的柱子其實不一樣高（PEAR `ChartSettingsDialog` 的 docstring 就是在講這件事）|
| 要不要畫資料點／鬚 | 框很多時點會糊成一團 |

### 不做（第二批）

字級、粗體、顏色、資料點半徑、線寬。

**為什麼現在不做，理由要留著**：PEAR 那個對話框的價值有一半在**排版**
（一列一個東西：刻度數字／軸名／資料點／線條，每列橫著擺 大小・粗體・顏色），
排列本身就在說明哪一列管什麼。d4t 的參數格是**一列一格**，攤平之後那個說明
就沒了。要做得對就得開一個 `ui/chart_settings.py`（`CLAUDE.md` §4：一塊新面板
＝一個新模組），而那要等到知道實際有幾列才排得出來 —— 現在排等於猜。

**這個決定不貴，而且可逆**：對話框跟參數格的差別**只在畫面，不在存哪裡** ——
兩種都是寫進同一張卡的參數、存進 recipe。所以第二批要做的時候，換的是編輯器
不是儲存格式，第一批不會白做。

---

## 8. 測試

| 檔案 | 守什麼 |
|---|---|
| `tests/test_uniformity.py`（新，headless）| `algo/uniformity.py` 全部：完全平的 → `cv_pct == 0` / `slope == 0`；線性斜坡 → 斜率算得準；退化輸入（空、一格、std≈0）**回 None 或 0，不 raise**；η² 兩群完全分開 → 接近 1、完全重疊 → 接近 0；Cohen's d 的符號方向；`jitter_tolerance` 的兩種輸入（真的抖動 vs 真的稀疏，後者**不准合併**）|
| `tests/test_steps.py`（加）| 卡片：一群／兩群／三群的特徵名逐字；第四群報 `configuration_issues`；接一群時**沒有前綴**；`report` 沒勾的欄**一格都不寫** |
| `tests/test_card_library_order.py`（改）| 卡片庫看到的順序（見 §10 的未定）|
| `tests/test_ui_input_kinds.py`（加）| `Open image…` 進得來、單檔 = 1 顆、標籤說 no KLARF |
| `tests/test_ui_inspectors.py`（加）| 四種圖各 `grab()` 一次（**只建構 widget 不會跑 `paintEvent`**，繪圖的 bug 會整個漏掉 —— PEAR 的 `CLAUDE.md` §3 逐字寫過這一條）|
| `tests/test_export.py`（加）| SVG 四種都產得出來、是合法 XML、數字跟 `uniformity_series()` 對得起來 |
| `tests/test_shipped_recipes.py`（加）| 出貨一份 recipe 真的跑一次（見 §10）|

**突變驗證**（`F82` 的做法）：至少要證明「把 `slope` 的 100 拿掉」「把
`jitter_tolerance` 的 4.0 門檻拿掉」「把 η² 的分母換成 ss_between」三個
突變各有一條測試變紅。沒變紅的那一條 = 那個常數其實沒有人在守。

---

## 9. 要動的檔案

### 新增

```
d4t/core/algo/uniformity.py          ← PEAR analysis.py 搬過來的 ~240 行
d4t/core/steps/uniformity.py         ← 卡片
d4t/core/export/uniformity_charts.py ← 四種圖的 SVG
d4t/ui/uniformity_inspector.py       ← 四種圖的 QPainter
docs/plans/F85-uniformity.md         ← 這一份
```

從 PEAR `pear/core/analysis.py` 搬（**無演算法改動**）：
`uniformity` / `linear_trend` / `roi_center` / `group_positions` /
`jitter_tolerance` / `cluster_positions` / `cell_edges` /
`profile_by_position` / `group_outliers` / `cohens_d` /
`attribute_separability`。

### 改

| 檔案 | 改什麼 |
|---|---|
| `d4t/core/steps/__init__.py` | import 新卡（**位置＝卡片庫的順序**，見 §10）|
| `d4t/core/steps/_util.py` | `stream_prefix` / `region_prefix` 抽成模組級函式共用 |
| `d4t/ui/scope.py` | `INPUT_SOURCES` 加一列；**「不准刪的孤兒模組」那張表加 `uniformity.py` 一列**（它一開始只有一個呼叫者）|
| `d4t/ui/inspectors.py` | `INSPECTORS` 加兩列（卡片 + 輸出卡預覽）|
| `d4t/core/ingest/dataset.py` | `load_image_file` |
| `docs/LICENSING.md` | vendoring 來源表加 `algo/uniformity.py` 一列（**測試會擋**）|
| `CLAUDE.md` / `README.md` | 來源表的「η²／Cohen's d」現在是真的了（§0）|
| `SESSION_LOG.md` | 最上方一段 |

### 完成之後（家用機）

```bash
ruff check
python tools/run_tests.py --fast          # 開發迴圈
python tools/run_tests.py                 # commit 前完整跑一次
python tools/freeze_golden.py --check     # 三份全綠 ← 見下
git add -A && python tools/release.py && git add -A
```

⚠ **黃金值必須三份全綠而且是「沒有變」的那種綠。** 這一輪不改任何既有的卡，
所以三份黃金值**一個數字都不該動** —— 動了就是我碰到了不該碰的東西。
這是這個 repo 踩過六次「跑得完、有數字、而且是錯的」之後唯一的證據。

---

## 10. 未定（要你決定，或我動手時挑一個再回報）

1. **卡片庫的順序。** Measure 段現在是 **GLV → CD → Focus index**（使用者
   2026-08-25 親自排的），而 `list_steps()` 照 `steps/__init__.py` 的 import
   序回。Uniformity 放**最後**（GLV → CD → Focus index → Uniformity）還是
   放 GLV 後面？我傾向最後 —— 它是「量完之後再看這一群怎麼散」。
2. **出不出貨一份 recipe。** `recipes/` 現在只有一份（RSEM 逐框挑最異常的），
   而每一份都有測試真的跑一次。要不要加一份「一張大圖 → ROI → Uniformity →
   Write uniformity」當範例？我傾向要 —— 那也正好是你的用法。
3. **四種圖的畫面用字**（§5.1 那一欄）。`Across the field` 是我暫定的，
   PEAR 叫 position profile；你比較習慣哪一個？

---

## 11. 這一輪的三個風險

| 風險 | 症狀長怎樣 | 防線 |
|---|---|---|
| 兩份繪圖程式碼漂掉 | 畫面上的圖跟報表裡的圖不一樣，而**兩張都畫得出來** | 兩份吃同一支 `uniformity_series()`；測試比對數字不比對畫素 |
| `slope` 的單位被誰改成「每 px」 | CSV 上整欄變成 0.00x，看起來像「都很平」—— **完全沒有錯誤訊息** | §8 的突變測試那一條 |
| 三群的欄位爆炸 | 75 欄的 CSV，而畫布上只看到三條線 | 上限釘 3、`report` 預設只勾三個、`configuration_issues` 對第四條線講話 |
