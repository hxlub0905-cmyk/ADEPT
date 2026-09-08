# F85：把 PEAR 的均勻度搬進來（2026-09-07）

使用者：

> 「我想將 PEAR 專案的功能移植進 d4t studio 讓他成為一張卡片」
>
> 「1. 不用自己畫 ROI，直接接現有的 ROI 卡去定義區域即可
>  2. 主要是想區域看均勻度，然後還有輸出要向 PEAR 一樣有多種圖表
>     （然後也可以 custom 設定輸出圖表長怎樣）：直方圖 盒鬚圖 Heat map 圖
>     Position 圖等等」

---

## 0. 這一份推翻了自己的第一版

第一版（同日稍早）的結論是「開一張新的 `uniformity` 卡」，理由寫的是：

> `MultiSourceStep.run` 的迴圈一次只給子類一個區域，所以跨群比較**結構上做不到**，
> 因此均勻度不可能折進 `glv_stats` 當一個 method。

使用者問了一句「**是有必要新開卡嗎**」，而那個理由**站不住**：

1. **子類可以覆寫 `run()`。** 而且乾淨的寫法是「先 `super().run()`，再多跑一段」
   —— 不是重寫迴圈。那是「基底預設不做」，不是「做不到」，我把前者寫成了後者。
2. **更要命的是那個論證用錯了規矩。** 我援引 F19 的「改變『量得出什麼』的選擇
   是岔路，不是 method」，但那條規矩的判準是**「這個參數問的是使用者的樣品，
   還是問軟體」**。而 `cv_pct` 問的跟 `glv_stats` 已經在吐的 `_typical` /
   `_outlier` 是**同一個樣品、同一組框、同一批像素** —— 它不是岔路，是同一個
   問題的第三種講法。

同一輪使用者對兩群比較（η² / Cohen's d）說**「不要」**。那一半本來就是我提議
的，不是他要的（原話是「兩群比較也可以加」）—— 而它一走，覆寫 `run` 的需求
也跟著走了，剩下的部分連基底都不用碰。

**所以這一輪不開新的量測卡。** 記在這裡是因為第一版已經 commit 過
（`4763e96`），而一份被推翻的計畫書如果只是被覆蓋掉，下一個人會重走一次
同樣的彎路。

### 那個決定的判準，留給下一次用

| | 折進 `glv_stats` | 新開一張卡 |
|---|---|---|
| 使用者接線 | **一次** | 兩次（同一個 ROI 拉兩條）|
| 設 `metrics` | **一次** | 兩次，而且**可以設得不一樣，畫面上看不出來** |
| 像素算幾次 | **一次** | 兩次 |
| 卡片庫多幾張 | 0 | 1 |

第二列是決定性的那一條，而 `glv_stats` 自己的 docstring 早就罵過同一件事
（舊 `roi_compare`：「使用者得放兩張卡、接兩次線，而那兩張卡各自有機會設得
不一樣」）。

**而「那張卡會不會太大」是可以量的**：`glv_stats` 現在 1,962 行、15 個參數
（repo 最大的一張），但新的那一格標 `show_when=("across_boxes", ("each box",))`，
而預設是 `pooled` —— **不用它的人看到的參數格數一格都沒有變。**

---

## 1. 範圍

### 做

| # | 東西 | 在哪 |
|---|---|---|
| 1 | **`Open image…`** —— 第四個 Input 入口（一張圖 = 一顆 defect，沒有 KLARF）| `ui/scope.py` + `ingest/dataset.py` |
| 2 | **`glv_stats` 加一格 `report`** —— 五個均勻度數字，只在 `each box` 時出現 | `steps/glv_stats.py` |
| 3 | **四種圖** —— 進既有的 `GlvInspector`，外加 SVG 版 | `ui/inspectors.py` + `core/export/` |
| 4 | **`output_uniformity`「Write uniformity」** —— Output 段一張新卡 | `steps/output.py` 或新模組 |

### 不做

| 不做 | 為什麼 |
|---|---|
| **新的量測卡** | §0 |
| **η² / Cohen's d** | 使用者：「不要」 |
| 手放 ROI（點一下放一格／拉網格／對齊／方向鍵微調）| 使用者第 1 點明說不用。d4t 的框由 Region 卡產 |
| ROI JSON 匯入匯出 | 沒有手放框，就沒有「把手放的結果搬走」這件事 |
| PEAR 的 ROI pixel inspector | `GlvInspector` 已經在做很接近的事 |
| Tukey 離群**格數** | §3.3 —— `glv_boxes_over_k` 已經在回答同一句話 |
| 外觀設定第二批（字級、粗體、顏色、點半徑、線寬）| 使用者選 (C)。理由見 §6 |

---

## 2. 概念對照

| PEAR | d4t | 現況 |
|---|---|---|
| **Group**（圓孔 vs 方孔）| **具名區域家族**（`epi` / `mg`）| ✅ `roi_reference` |
| **ROI**（一個量測框）| 家族底下的一格框（`ctx.roi_rects(name, shape)`）| ✅ |
| metric（GLV 統計量）| 同一份 bank（`algo/glv.py`，是 PEAR 的超集）| ✅ |
| 逐 ROI 量、找最極端的那一格 | `glv_stats` 的 `each box`（`_typical` / `_outlier` / `_outlier_box`）| ✅ 已經有 |
| **這一群框均不均勻** | 本輪：`report` 那一格 | ❌ |
| **值跟位置的關係** | 本輪：`slope_x` / `slope_y` ＋ 兩張圖 | ❌ |
| 四種圖 | 本輪 | ❌ |
| 群組之間誰分得開 | **不做**（使用者：「不要」）| — |

**`each box` 已經在逐框量了，per-box 的值就在手上** —— 這一輪加的是「那一串值
怎麼收尾」，不是重新量一次。

---

## 3. `glv_stats` 加一格 `report`

### 3.1 參數

```python
ParamSpec(
    name="report", type="multi_choice",
    default="cv_pct,slope_x,slope_y",
    choices=["range", "range_pct", "cv_pct", "slope_x", "slope_y"],
    section="3 · How to find it",
    show_when=("across_boxes", (EACH_BOX,)),
    label="How even are the boxes",
    ...)
```

**預設三個**（使用者定調）：`cv_pct` ＋ `slope_x` ＋ `slope_y` ——
「均不均勻」加「有沒有斜掉」，兩句話就是這個問題的全部。

`show_when` 綁 `across_boxes`：`pooled` 的時候一整群框被當成一堆像素，
「這幾格之間差多少」根本問不出來 —— 那一格不該只是**沒有數字**，
它該**不在畫面上**。

### 3.2 特徵名

沿用 `each box` 既有的後綴文法（`<前綴>_<量>_<後綴>`）：

| 名字（接兩群、勾了全部時）| 意思 |
|---|---|
| `epi_glv_median_range` | 最亮那格 − 最暗那格 |
| `epi_glv_median_range_pct` | ↑ 佔平均的 % |
| `epi_glv_median_cv_pct` | 標準差佔平均的 %（**預設**）|
| `epi_glv_median_slope_x` | 左到右**每 100 px** 變多少（**預設**）|
| `epi_glv_median_slope_y` | 上到下每 100 px 變多少（**預設**）|

只接一個區域、一條流時前綴是空的（`glv_median_cv_pct`）—— `stream_prefix` /
`region_prefix` 既有的行為，這一輪一個字都不改。

⚠ **`slope_*` 的單位是「每 100 px」，不是「每 px」。** PEAR 就是這樣報的，
理由是每 px 的斜率在真實資料上是 0.00x 那種數字，於是 CSV 上整欄看起來都是 0
——「都很平」，而且**沒有任何錯誤訊息**。單位要同時進 `ParamSpec.unit` 與
feature 的說明。

### 3.3 為什麼**不**做 Tukey 離群格數

第一版列了 `outliers`（幾格是 Tukey 離群）。查過之後拿掉，兩個理由：

1. **`glv_boxes_over_k` 已經在回答同一句話**（F68：「超過 k σ 的有幾格」，
   外加 `_frac`）。加第二個「有幾格怪怪的」＝ 同一件事兩個名字，而
   `CLAUDE.md` 對這件事的判詞是「CSV 上沒有任何線索說它們是同一個」。
2. **名字會差一個字母。** `_outlier`（既有：最極端那格的**值**）與
   `_outliers`（新的：**幾格**）在 CSV 上會並排，一個是灰階、一個是計數。
   那是最難發現的那種撞名。

真的需要 IQR 版而不是 σ 版的話，那是「`glv_boxes_over_k` 換一種算法」的討論，
不是多一個特徵。

### 3.4 這一格**不**碰 `run()`

均勻度全部算在 `measure()` 裡（它拿得到這一個區域的每一格值）。
基底 `MultiSourceStep` 一行不改，`stream_prefix` / `region_prefix` /
`CURRENT_REGION_INDEX` 全部照舊 —— 這是 §0 那個決定省下來的東西。

---

## 4. 四種圖

### 4.1 四種圖分別是什麼

| 值 | 畫面上的字 | X | 一個點 | 回答 |
|---|---|---|---|---|
| `box` | Box plot | 區域 | 一格框 | 這幾群各自的分布 |
| `histogram` | Histogram | 灰階值 | 一格框 | 值怎麼散開 |
| `profile` | Position profile | 框中心的 X 或 Y | 一格框 | 有沒有斜掉 |
| `map` | Heat map | 框的 (x, y) | 一格框（顏色＝值）| 不均勻在**哪裡** |

四種都是「**一格框一個點**」—— 一致，不會混。

### 4.2 ⚠ 這跟現在的盒鬚圖**不是同一個東西**

`output_report` 的 `boxplot` 是：**一個盒子＝判定樹的一片葉子，一個點＝一顆
defect**（整批的圖）。這一輪的是：**一個盒子＝一個區域，一個點＝一格框**
（一張圖之內的圖）。

兩者不共用，也不打算共用。寫在這裡是因為它們在畫面上長得一模一樣，而「一個點
是什麼」是唯一的差別 —— 那正是最容易在半年後被誰「順手合併」的形狀。

### 4.3 ~~畫面上進 `GlvInspector`~~ —— 圖住在 **Write uniformity 的儀表**

> ⚠ 這一節換過。原本寫的是「四種圖是 `GlvInspector` 多一排切換」。

動手時發現 `GlvInspector` 給不了那一排切換：儀表面板只有**一個**分頁鈕
（`Inspector.tab_title`），沒有「同一張卡好幾種看法」的機制。硬加的話，
畫面上會多一排**只在儀表裡有意義**的按鈕 —— 那個選擇既不進 recipe、也跟
任何一格參數對不起來。

而**「畫哪幾張」本來就是一格參數** —— `Write uniformity` 的 `charts`。
所以圖住在那張卡的儀表上：選到它，上半是「會寫哪幾個檔」（Write KLARF 那條
硬規則），下半就是那幾張圖本人。**選到卡就看到它會產出什麼**，是這一排
Output 儀表本來的意思。

`GlvInspector` 因此**一行都沒有動**。

### 4.4 ~~兩份繪圖程式碼~~ —— **只需要一份**

> ⚠ **這一節整個推翻了。** 留著原本的推論與它錯在哪，因為那個錯誤差一點
> 就變成這一輪最貴的技術債（風險表第一行本來就是它）。

**原本寫的**：畫面上一份 QPainter、檔案裡一份 SVG，理由是鐵則 1
（`core` 不准 import Qt），而 core 產 SVG、Studio 顯示那條路走不得，因為
**「`QtSvg` 不是相依」**。

**那句話是錯的。** `QtSvg` 與 `QtSvgWidgets` 就裝在 **`PySide6-Essentials`**
裡（`pip show PySide6-Essentials` 列得出 `QtSvg.abi3.so`），而
`requirements.txt` 的 `PySide6>=6.5` 早就把它帶進來了。它不是要另外裝的
東西 —— 我把「Qt 的一個獨立模組」當成了「一個獨立的套件」。

**所以現在是一份**：`core/export/uniformity_charts.py` 產 SVG，
`UniformityPreviewInspector` 用 `QSvgRenderer` 把**同一個字串**畫到面板上。
畫面上看到的跟寫出去的逐位元組相同。

賠掉的是 hover（滑到哪一格框、那一格亮起來）。那筆帳划算：`GlvInspector`
的直方圖本來也沒有 hover，而「畫面上的圖跟報表裡的圖不一樣，而兩張都畫得
出來」是這個 repo 最貴的那種 bug。

⚠ 一份帶來一個**新的**坑，而它當場就踩到了：每一支 `_svg_*` 把圖區夾在
``max(80, height − 上下留白)``，所以格子不夠高時內容比 viewBox 高，而
**SVG 會把超出的切掉**。實測儀表把 profile 畫在 126 px 高的格子裡，
斜率那一行（整張圖唯一的數字）被切掉一半，**而圖看起來完全正常**。
解法是 `MIN_WIDTH` / `MIN_HEIGHT`：**夾住尺寸，不夾內容** —— 呼叫端把整張圖
等比例縮小（`_fit`），字變小但沒有一樣東西不見。

### 4.5 要跟著搬的兩支「不顯眼但關鍵」的函式

`jitter_tolerance` 與 `cluster_positions`（PEAR `analysis.py`）。

它們解的是：**框的中心差幾個 px，算不算同一欄。** PEAR 是因為手放框才需要它；
d4t 的框由卡片產、看起來應該很整齊 —— 但 `roi_reference` 的
`stripes in the image` 走次像素邊緣定位，中心**本來就不是整數**，而
`layout layers` 從 label map 拆矩形，一條 45° 斜帶會拆出 5,295 個階梯狀小塊
（`roi_reference` docstring 的實測表）。兩條路都會踩到。

不搬的症狀 PEAR 的 README 逐字描述過：**八欄的網格碎成三十幾條細條**。

---

## 5. `output_uniformity`「Write uniformity」（Output 段）

### 5.1 為什麼這一張**還是**要新開

跟量測那一半的理由完全無關：`Write report` 是「整批跑完寫**一份總表**」，
這幾張圖是「**一張圖之內**的分布」。硬併進去 = 一張卡有兩種跑法，而 d4t 踩過
這個坑（F50，`ui/output_band.py` 被刪掉的理由：**框的意思是「這幾個是一組」，
真相卻是「跑的時間不一樣」**）。

### 5.2 名字怎麼區分

Output 段現有的文法是「Write ＋ 寫什麼出去」。真正區分它們的是 help 那一句話，
不是名字：

| 卡 | 一句話 |
|---|---|
| **Write report** | 整批跑完一份總表 —— 每顆 defect 一列，加判定結果的盒鬚圖 |
| **Write KLARF** | 把分數與分類寫回原本那份 KLARF |
| **Write comparison** | 兩份資料點對點對照 |
| **Write uniformity** | 一張圖裡的區域分布 —— 每一格框一個點，四種看法 |

先例：`pair_source`（掛第二份資料）↔ `Write comparison` 就是「一張量測卡配
一張輸出卡」。

### 5.3 逐顆的圖住在一張跨顆的卡上

Output 卡是 `CATEGORY_BATCH`（跑完全部才跑一次），而這些圖是逐顆的。機制已經有：
`BatchContext.rerun(item)` 重跑一顆拿回它的 Context（有快取時只跑算法段）。

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

## 6. 外觀設定：第一批做什麼

使用者選 **(C)**。

### 做

| 項目 | 為什麼非有不可 |
|---|---|
| 畫哪幾種圖 | — |
| 圖的標題、X／Y 軸名 | 報告裡要用 |
| **鎖定數值範圍** | **這一項最重要**。auto 縮放在看一批時是對的，兩批擺在一起就會騙人 —— 各自挑各自的範圍，一樣高的柱子其實不一樣高（PEAR `ChartSettingsDialog` 的 docstring 就是在講這件事）|
| 要不要畫資料點／鬚 | 框很多時點會糊成一團 |

### 不做（第二批）

字級、粗體、顏色、資料點半徑、線寬。

**理由要留著**：PEAR 那個對話框的價值有一半在**排版**（一列一個東西：刻度數字
／軸名／資料點／線條，每列橫著擺 大小・粗體・顏色），排列本身就在說明哪一列
管什麼。d4t 的參數格是**一列一格**，攤平之後那個說明就沒了。要做得對就得開一個
`ui/chart_settings.py`，而那要等到知道實際有幾列才排得出來 —— 現在排等於猜。

**這個決定可逆**：對話框跟參數格的差別**只在畫面，不在存哪裡** —— 兩種都是寫進
同一張卡的參數、存進 recipe。第二批要做的時候，換的是編輯器不是儲存格式。

---

## 7. 要搬的 PEAR 程式碼

新增 `d4t/core/algo/uniformity.py`，從 `pear/core/analysis.py` 搬
（**無演算法改動**）：

| 函式 | 做什麼 |
|---|---|
| `uniformity` | range / range_pct / std / cv_pct |
| `linear_trend` | 最小平方斜率（`slope_*` 的來源）|
| `roi_center` / `group_positions` | 框中心，跟值同一個索引 |
| `jitter_tolerance` / `cluster_positions` | §4.5 |
| `cell_edges` | heat map 的格線 |
| `profile_by_position` | position 圖的那條 profile 線 |

**不搬**：`cohens_d` / `attribute_separability`（使用者：「不要」）、
`group_outliers`（§3.3）。

⚠ 計畫書原本寫「`uniformity.py` 一開始只有一個呼叫者，要進 `ui/scope.py`
那張『不准刪的孤兒模組』表」。**做完之後那句話不成立**：它有兩個真的呼叫者
（`steps/glv_stats.py` 與 `export/uniformity_charts.py`），不是孤兒，寫上去
會是一句**指著錯東西的說明**（F84 那條「搬家的時候理由要跟著搬」的反面）。

真正的風險降了一階，而它值得寫在這裡：`cell_boxes` / `profile_by_position` /
`cluster_positions` / `cell_edges` / `jitter_tolerance` 這五支**只有 heat map
與 position profile 兩張圖在用**。哪天那兩張圖被拿掉，它們就一起變成孤兒。
`tests/test_uniformity.py` 是那張便利貼。

---

## 8. 一件文件已經漂掉的事，這一輪要順手修

`CLAUDE.md` §6 與 `README.md` 的來源表都寫著：

> **PEAR** | GLV 統計 metric bank、Tukey 離群、**η²／Cohen's d**、CJK-safe 影像載入、SNR 正負號正典

而整個 repo **grep 不到 `cohens_d` 或 `attribute_separability`**。
`docs/plans/F11-phase2-features.md` 留著墓碑：它進來過（`algo/stats.py`，85 行），
因為零個呼叫者被當死碼清掉，而兩份文件沒有跟上。

第一版計畫書打算「把它搬回來讓那兩張表變成真的」。使用者說不要 ——
**所以要修的是文件那一邊**：把那兩張表的「η²／Cohen's d」拿掉。

留著不改的話，下一個人會照著那張表去 `import`，然後發現東西不在
（那正是 `CLAUDE.md` §0 開頭在講的事：抄第二份出來的那份一定會漂）。

**「Tukey 離群」那一項留著**：`export/boxplot.py` 的 1.5×IQR 鬚是真的在用。

---

## 9. 測試

| 檔案 | 守什麼 |
|---|---|
| `tests/test_uniformity.py`（新，headless）| 完全平的 → `cv_pct == 0` / `slope == 0`；線性斜坡 → 斜率算得準（**含「每 100 px」那個係數**）；退化輸入（空、一格、std≈0）**回 None 或 0，不 raise**；`jitter_tolerance` 的兩種輸入（真的抖動 vs 真的稀疏，**後者不准合併**）|
| `tests/test_steps.py`（加）| `report` 勾了什麼就吐什麼、沒勾的**一格都不寫**；`pooled` 時那一格不出現；一群／兩群的前綴逐字 |
| `tests/test_ui_input_kinds.py`（加）| `Open image…` 進得來、單檔 = 1 顆、標籤說 no KLARF |
| `tests/test_ui_inspectors.py`（加）| 四種圖各 `grab()` 一次 —— **只建構 widget 不會跑 `paintEvent`**，繪圖的 bug 會整個漏掉（PEAR `CLAUDE.md` §3 逐字寫過這一條）|
| `tests/test_export.py`（加）| SVG 四種都產得出來、是合法 XML、數字跟 `uniformity_series()` 對得起來 |
| `tests/test_shipped_recipes.py`（加）| 出貨一份 recipe 真的跑一次（見 §11）|

**突變驗證**（F82 的做法）：至少要證明「把 `slope` 的 100 拿掉」與「把
`jitter_tolerance` 的 4.0 門檻拿掉」兩個突變各有一條測試變紅。沒變紅的那一條
= 那個常數其實沒有人在守。

---

## 10. 要動的檔案

### 新增

```
d4t/core/algo/uniformity.py            ← 從 PEAR 搬的 ~180 行
d4t/core/export/uniformity_charts.py   ← 四種圖的 SVG
tests/test_uniformity.py
```

### 改

| 檔案 | 改什麼 |
|---|---|
| `d4t/core/steps/glv_stats.py` | 一格 `report` ＋ `measure()` 裡的收尾 |
| `d4t/core/steps/output.py` | `output_uniformity` |
| `d4t/ui/inspectors.py` | `UniformityPreviewInspector`（清單 ＋ 那幾張圖）；`GlvInspector` **一行沒動**（§4.3）|
| `d4t/ui/scope.py` | `INPUT_SOURCES` 加一列（孤兒表**不加** —— 見 §7） |
| `d4t/core/ingest/dataset.py` | `load_image_file` |
| `docs/LICENSING.md` | vendoring 來源表加 `algo/uniformity.py`（**測試會擋**）|
| `CLAUDE.md` / `README.md` | §8 —— 拿掉「η²／Cohen's d」|
| `SESSION_LOG.md` | 最上方一段 |

**卡片庫的順序不動** —— 這一輪不加量測卡。

### 完成之後（家用機）

```bash
ruff check
python tools/run_tests.py --fast
python tools/run_tests.py
python tools/freeze_golden.py --check     # ← 三份全綠，而且必須是「沒有變」
git add -A && python tools/release.py && git add -A
```

⚠ **黃金值必須一個數字都不動。** 新的 `report` 那一格預設**會**被寫進新加的卡
（`add_step` 走 `validate_params(cleared_inputs())`），但既有的 recipe 帶著自己
那一份參數，而且它們的 `across_boxes` 是 `pooled` —— 新那一格連算都不會算。
動了就是我碰到了不該碰的東西。

---

## 11. ~~未定~~ —— 三個都定了（使用者 2026-09-07）

1. **出貨一份 recipe：要。** `recipes/one-image-uniformity.json` ——
   一張大圖 → 鋪一組 ROI → GLV(each box ＋ report) → 四張圖，也就是使用者的
   用法本人。它的判定樹刻意只分「量不到」與「量到了」：**這份 recipe 不下
   判斷**，門檻是使用者的，而且每一層不一樣。
2. **Position 圖就叫 `Position profile`**（原本暫定 `Across the field`）。
3. **`Open image…` 的標籤仍然說 `folder`**，`kind` 不新增第五種。

## 12. 這一輪的風險（做完之後）

| 風險 | 症狀長怎樣 | 防線 |
|---|---|---|
| ~~兩份繪圖程式碼漂掉~~ | —— | **這個風險沒有了**（§4.4）：畫面與檔案是同一份 SVG |
| 小面板把圖切掉而看起來正常 | 斜率那一行不見了，而圖上其他東西都在 | `MIN_WIDTH`/`MIN_HEIGHT` ＋ `test_a_chart_is_never_clipped_to_fit` |
| `slope` 的單位被誰改成「每 px」 | CSV 上整欄變成 0.00x，看起來像「都很平」—— **沒有任何錯誤訊息** | §9 的突變測試 |
| ~~`GlvInspector` 被撐爆~~ | —— | **沒有了**（§4.3）：圖住在 `Write uniformity` 的儀表，GLV 那一張一行都沒動 |
