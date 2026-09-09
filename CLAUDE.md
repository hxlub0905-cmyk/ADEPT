# CLAUDE.md — d4t 操作手冊

給 Claude Code／開發者的**動手指南**。這一份會被讀進每一個 session，
所以它刻意只留「不知道就會做錯」的東西；**參考資料一律放在 `docs/`，用到才讀**。

> **每次 session 結束請更新 [`SESSION_LOG.md`](SESSION_LOG.md) 最上方。**

---

## 0. 先讀哪一份（每個主題只有一個家）

同一件事只寫在一個地方 —— 抄第二份出來的那份一定會漂移
（2026-08 實際發生過：程式碼刪了五份範例 recipe，四份文件裡只有一份跟上，
而 `tools/doctor.py` 因此對每台機器給出一個**錯的**診斷）。

| 你要知道的事 | 去哪 | 什麼時候要讀 |
|---|---|---|
| **環境限制**：兩台機器、剪貼簿是唯一通道、為什麼工具都 stdlib-only | [`AGENTS.md`](AGENTS.md) | **動手之前**（不知道會把必要設計當成過度設計刪掉）|
| 怎麼加卡片、鐵則、開發流程 | 這一份 | 一直 |
| **怎麼做 EBI ↔ API characterization**（給使用者的操作手冊：線接哪、每格填什麼、報表怎麼讀、出事了照什麼順序查）| [`docs/USING-CHARACTERIZATION.md`](docs/USING-CHARACTERIZATION.md) | 要動 `pair_source` / `H2H` / `output_char` 的參數或說明之前 |
| **怎麼看一片區域均不均勻**（給使用者的操作手冊：那五個數字、四張圖各回答哪一句話、兩批要比的時候先鎖尺度、出事了照什麼順序查）| [`docs/USING-UNIFORMITY.md`](docs/USING-UNIFORMITY.md) | 要動 `glv_stats` 的 `report` 那一格、`output_uniformity`，或四張圖的畫法之前 |
| **怎麼用 CD 那張卡**（給使用者的操作手冊：每一格什麼時候動、數字會往哪走）| [`docs/USING-CD.md`](docs/USING-CD.md) | 要動 CD 卡的參數、help 文字或輸出名字之前 |
| **怎麼用 Golden Cell 產一批模擬資料**（給使用者的操作手冊：每一格什麼意思、輸出長什麼樣、出事了照什麼順序查）| [`docs/USING-SIMGEN.md`](docs/USING-SIMGEN.md) | 要動 `simgen` 視窗（`ui/gc_generator.py` / `gc_paint.py`）或 `tools/make_lot_from_gc.py` 的參數之前 |
| **架構**：三段式心智模型、資料模型（影像流 vs 具名區域）、目錄結構 | [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) | 動到 pipeline／資料流之前 |
| **已知的坑**（80+ 條，只增不減）| [`docs/PITFALLS.md`](docs/PITFALLS.md) | 動到 Qt 繪圖／快取／批次平行／KLARF 寫回／recipe 遷移之前，**先搜關鍵字** |
| **進度與 phase 計畫** | [`docs/ROADMAP.md`](docs/ROADMAP.md) | 想知道「接下來做什麼」 |
| **為什麼長成這樣**：需求訪談結論、六個來源專案的脈絡 | [`docs/HANDOVER.md`](docs/HANDOVER.md) | 第一次接手；想改一個「看起來多餘」的設計之前 |
| **授權**：d4t 是專有／內部使用（[`LICENSE`](LICENSE)）、vendoring 來源的授權、第三方相依（PySide6 的 LGPL）| [`docs/LICENSING.md`](docs/LICENSING.md) | **加相依套件之前**（`LICENSE` 的 carve-out 與 §4 的表**兩邊都要加**，測試會擋）、要 vendor 新東西、或有人問「這能不能給別人用」之前 |
| 廠內待驗證的假設、受限機器的部署 | [`docs/FAB-VALIDATION.md`](docs/FAB-VALIDATION.md) | 要動 KLARF／單位／搬運時 |
| **上游 GLAS 的介面**（label map／合成 gray／alignment；d4t 不解析 layout）| [`docs/GLAS-INTERFACE.md`](docs/GLAS-INTERFACE.md) | 要動 ROI 第三條路、或要請 GLAS 改東西時 |
| 逐輪的決策與理由 | [`SESSION_LOG.md`](SESSION_LOG.md)（近期）＋ [`docs/history/`](docs/history/) | 查「這個決定當初為什麼這樣下」|

**加一份新文件之前先問：這個主題已經有家了嗎。** 有的話寫進那一份。

### ⚠ 名字含糊的代價：**bundle**

上面那條規矩的鏡像。`bundle` 曾經同時指兩個不相干的東西（一張 Output 卡、
以及整個 repo 打包成的單檔），而它們從不出現在同一段程式碼裡 —— 所以會混淆的
是**人**：2026-08-26 一整輪對話裡兩個意思交替使用，使用者問「bundle 在這邊是
什麼」。那一輪量過代價、決定兩個都不改名（改 key 要付一道遷移）；錢後來在 F38
因為別的理由付掉了（`output_bundle` 折進 `output_report`），混淆才跟著消失。
**下一個含糊的名字不會這麼剛好。**

現在這個字只剩一個意思 —— `bundle/d4t_bundle.py`，公司機拿程式碼的唯一路徑
（政策擋 .zip、proxy 不讓逐檔抓；`tools/release.py` 產它）。兩條規矩：

* **不改它的名字。** `docs/NO-GIT-SETUP.md` 寫著那個檔名，而那台機器不能跑
  git —— 改名等於讓一份寫下來的程序在一台救不了的機器上失效。
* **不要再造第二個 `bundle`。**

---

## 1. 這是什麼

**d4t** = *defect* 的 numeronym（頭字母 + 中間字數 + 尾字母，跟 i18n / k8s / n8n 同一套）。
名字底下永遠釘一行全稱：**d4t — defect**。
半導體 E-beam Inspection 的彈性 ADC 工具：讀 patch/RSEM 影像 + KLARF，
用「步驟卡片組 pipeline」對每顆 defect 算分、分 bin、寫回 KLARF。

**最高指導原則：站點差異封裝進 recipe，不封裝進程式碼。**
第二原則：**推廣鐵則** —— 目標使用者是不會寫 code 的製程/設備工程師。
任何讓他們看不懂或會爆錯誤訊息的設計，都是 bug。

一句話的心智模型（完整版見 [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md)）：

```
【影像段】把圖變乾淨可比 → 【算法段】從圖量出數字 → 【ADC 判定】score → bin → 寫回 KLARF
```

### 目前收起來的一件事（不是漏掉的）

engine 還在做（**Phase 1「讓數字可信」已於 2026-08-16 收斂**，下一步是
Phase 2），使用者定調**先把引擎做對，再回頭做產品化**（見
[`docs/ROADMAP.md`](docs/ROADMAP.md)）：

- **範本庫是空的**（`examples/` 已移除），Studio 的「用範例資料試一次」與
  「Templates…」兩個入口收起來了 —— 開關在 `ui/scope.py`。

**出貨的 recipe 在 [`recipes/`](recipes/)**（2026-08-26），走 `Open recipe…`
不走範本庫，而且**每一份都有測試真的跑一次**
（`tests/test_shipped_recipes.py`）—— 舊的 `examples/` 就是因為沒人測而爛掉的。
加一份新的就在那支測試裡加一段。**目前只有一份**：RSEM 逐框挑最異常的那一格
（F73）。EBI↔API characterization 與 patch 的 dSNR 分布（F36）2026-09-02 由
使用者指定刪掉 —— 卡片（`pair_source` / `output_char` / GLV 的 compare）
一個都沒有動，走的是那條路的人自己拉線。

⚠ 那支測試有一張 **`ALLOWED_ERRORS`**（哪一份 recipe 允許哪一條 lint error），
而它配著一支**反向的**測試：例外修好了卻沒從表上拿掉的話，那份 recipe 從此少
一條防線而測試照樣綠。**表現在是空的**（唯一那條「模板是一張影像、塞不進
JSON」隨 patch 那份一起走了），但機制留著 ——
**任何「例外清單」都要有那支反向測試**，不然它就是一張只會變長的紙。

**存檔 recipe 2026-08-26 做回來了**（F34，[`docs/history/plans/F34-save-recipe.md`](docs/history/plans/F34-save-recipe.md)）。
`Recipe.save()`、工具列的「Save recipe…」、`Ctrl+S`（存回原檔）與
`Ctrl+Shift+S`（另存）都在。⚠ 它帶來一個**以前不存在的後果**：Studio 載入時做的
UI 層遷移（門檻 → 判定樹）現在會被存回磁碟。那是對的（存出跟畫面不一樣的東西
才是說謊），但寫在 `_adopt_threshold_as_a_tree` 裡的「反正存不了檔」那句話
已經作廢 —— 見 `Recipe.save` 的說明。

---

## 2. 鐵則（違反 = 測試會擋）

1. **`d4t/core` 不得 import Qt**。UI 只透過 callback 與 core 互動。
2. **Python 3.9 相容語法**（廠內機器可能是舊版）。測試以 `ast.parse(feature_version=(3,9))` 掃全套件。
3. **每個 ParamSpec 的 `help` 必填**且要是白話。`register_step` 會拒絕沒有 help 的卡片。
4. **每個 Step 要有合理 default 與 min/max**。使用者填爆的值必須擋在 `validate_params`，
   不能讓它跑到演算法裡炸。
5. **檔案寫入一律 atomic**（`.tmp` + `os.replace`）。
6. **KLARF 寫回必須無損**：沒被改到的 byte 要與原檔逐位元組相同（`klarf_core` 的 span-splice）。
7. **單顆 defect 出錯不得殺掉整批**（`run_defect` 從不 raise，回 `ok=False`）。
8. **repo 裡不得有未遮蔽的廠內識別碼**（Lot／Wafer／機台／device／recipe 名稱／
   廠區代號／缺陷分類名稱）。測試 fixture 也一樣 —— 它們斷言的是**結構**，
   值遮蔽掉一條測試都不會壞。`tests/test_no_real_fab_data.py` 會擋。
9. **recipe 的遷移只能靠「舊東西在不在」判斷，不能靠「新東西不在」。**
   後者分不出「舊檔案靠舊預設」與「新 recipe 靠新預設」，而
   `to_json_dict → from_json_dict` 是 `run_batch` 送 recipe 進 worker 的路 ——
   它一旦不是 identity，`workers=1` 與 `workers=2` 就會算出不同的分數。
   真的發生過（見 `docs/PITFALLS.md`）。
10. **資料從哪來由「線」決定，而畫布上每一條線都是使用者拉的**（F9）。
    影像流的身分是 `(節點, 埠)`，不是一個全域名字 —— 同一條 `ref` 分岔成兩支
    才成立。由此來的三條規矩：**加卡不准順手接線**（自動接的線與使用者拉的線
    會落在同一個輸入，而只有一條算數）、**一個輸入埠只能有一條線**
    （`validate` 會報 `ambiguous-input`）、**任何會影響影像段結果的東西都要進
    快取簽章**（改接線可以完全不動參數，簽章看不見線就會回舊影像）。
    這一段踩過六個「跑得完、有數字、而且是錯的」，全部記在 `docs/PITFALLS.md`
    與 `docs/history/plans/F9-dag-streams.md`。

    **具名區域完全一樣（F12 起有線，F42 起同一套機制）**：一張卡用到的每一個
    區域，畫布上都要有一條線指到定義它的那張卡（虛線 + 菱形埠），而那條線
    **就住在 `recipe.edges` 裡**（`[來源, 區域名, 這張卡, 參數名]`）——
    `roi="epi"` 那一格是從線**水合**出來的值，不寫進 JSON。判準只有一支：
    `recipe.is_region_edge`。三條由此而來：

    * **順序也只看線**（F17-①）。把 Region 卡拖到量測卡右邊不會再讓量測卡
      先跑 —— 那個 bug 是 F42 的起點，第七個「跑得完、有數字、而且是錯的」。
    * **同一條 route 上兩張卡不准定義同名區域**（`duplicate-region`，error）。
      引擎的 `ctx.set_roi` 是同名覆寫，名字唯一才讓「線指的那張卡」＝
      「引擎真的給的那個框」恆成立 —— 那是引擎一行都不用改的原因。
    * **手寫 recipe 從此要寫那條線**；舊檔案由 `version < RECIPE_VERSION`
      的遷移補，`tools/doctor.py` 的「recipe 格式」那一項會提醒。

    見 `docs/history/plans/F42-region-edges-plan-b.md`（F12 §3 於該輪推翻，
    其他部分 —— 埠、虛線、唯讀參數格、同進同出 —— 全部保留）。

---

## 3. 加一張新卡片（最常見的工作）

```python
# d4t/core/steps/my_card.py
from ..pipeline.context import Context
from ..pipeline.step import CATEGORY_ALGO, ParamSpec, Step, StepError, register_step

@register_step
class MyCardStep(Step):
    key = "my_card"                    # recipe JSON 用的 id
    label = "我的卡片"                  # UI 顯示
    category = CATEGORY_ALGO           # image / algo / adc
    help = "一行白話：這張卡做什麼。"      # 必填
    params = [
        ParamSpec(name="source", type="image_key", default="diff",
                  help="要分析哪個影像流。"),
        ParamSpec(name="k", type="int", default=3, min=1, max=99,
                  help="視窗大小（越大越平滑）。"),
    ]
    reads = ["diff"]; writes = []; features_out = ["my_metric"]

    def run(self, ctx: Context, params):
        p = self.validate_params(params)
        img = ctx.require_image(p["source"])       # 缺影像會拋帶說明的 ContextError
        ctx.add_feature("my_metric", float(...))   # 演算法請呼叫 d4t.core.algo.*
        return ctx
```

`steps/__init__.py` import 它即完成註冊 —— **UI 與引擎零修改**，卡片庫自動出現。
param 相依 I/O（例如輸出流名稱由參數決定）覆寫 `resolve_reads/resolve_writes/resolve_features`。

> **一張卡是一次處理，寫出去的正好等於接進來的**（F7-19／F7-20）。Enhance 卡
> 繼承 `MultiStreamStep`（`steps/_util.py`）：吃 `streams`（一串影像流）、
> 只實作 `build_op` 回一個 `img -> img`，迴圈交給基底。接 test 也接 ref，
> 兩條就吃**同一組設定** —— 那正是「兩張圖還比得起來」的前提。
> 要讓兩條流吃**不同**設定才放兩張卡。
>
> 真正的不變量是**畫布不能說謊**：卡片動到的每一條流，畫面上都要有一條線。
> （F7-18 的「一張卡一條流」是當時達成它的手段，不是不變量本身 —— 見計畫書
> §23.1。`also_apply` 那種「藏在控制列的第二條流」仍然不准回來。）
> 需要「借另一條流的資訊」時，那件事要有自己的參數（例：`normalize` 的
> `range_from`），型別是 `image_key` —— 它在畫布上就是第二條接進來的線。

> **同一個家族的做法收成一張卡的 `method`**（F7-10／F7-20）。四種正規化、
> 五種去背景、四種去雜訊各是一張卡的下拉，不是十三張卡 —— 卡片庫多一列，
> 使用者就要多讀一段說明才知道該用哪一個。**方法相依的參數用
> `ParamSpec.show_when`**（例 `show_when=("method", ("percentile",))`），
> 不要在 help 裡寫「（這個方法用不到）」那種道歉。
> 注意 `show_when` 是**顯示**規則不是驗證規則：藏起來的參數照樣有預設值，
> 卡片自己要保證用不到的參數不影響結果（`resolve_reads` 也一樣）。
> 但**「可以同時做」的東西不要做成四選一** —— `tone` 的亮度／gamma／反相是
> 幾個預設不作用的旋鈕，因為使用者常常要一起用。
>
> **改變「量得出什麼」的那種選擇是岔路，不是 method**（F19 第二批）。CD 卡最
> 上面的「一條線／一團東西」問的是樣品，而且它決定了後面哪幾格**算不算數**
> （方向對一團東西沒有意義）—— 那種要用 `show_when` 把不適用的收起來，不是攤
> 在那裡讓使用者猜。判準仍然是那一句：**這個參數問的是使用者的樣品，還是問
> 軟體**。反過來，兩支都成立的那一格（CD 的門檻高度）就**共用同一格、同一支
> 函式** —— 分成兩份的那天，同一句話會長出兩種意思。

> **參數名是 recipe 的鍵，不是給人看的字**（F7-9）。`ParamSpec` 有選填的
> `label`：有就顯示 label，沒有就顯示 `name`。`range_from` 對製程工程師不是
> 一句話，`Borrow range from` 才是。同理，「一串影像流」請用 `type="image_keys"`
> 而不是 `str` —— 值的格式一樣（逗號分隔字串），但 UI 認得它是**接線的結果**。
>
> **`image_key` / `image_keys` 的欄位在設定區是唯讀的**（F9-6，使用者定調：
> 「他會很亂連」）。來源只在畫布上拉線決定，設定區只顯示現在接的是什麼。
> 所以卡片吃影像流的參數請務必用這兩個型別 —— 用 `str` 的話它會變成一個
> 打得進去、但畫布上沒有對應線條的自由文字框。
>
> **吃具名區域的參數同理，用 `region_key` / `region_keys` 並宣告
> `direction="in"`**（F12，2026-08-19）。區域在畫布上是**菱形埠 + 一條虛線**，
> 那一格一樣唯讀。用 `str` 的下場更糟：畫面上兩張卡看起來互不相干，而拿掉上游
> 那張 Region 卡，量測卡不會報錯 —— 它會**安靜地改量整張圖**。
> 區域**產出**的名字不走參數，由 `resolve_regions_out` 宣告
> （`<name>_center` 那種是算出來的，不是某一格填的字）。
>
> **單數／複數的意思跟影像流一字不差**（F13-⑥）：`region_keys`（一串）是
> 「同一件事做在好幾個區域上」，第二條線**累加**，而每個數字會自動帶上
> 區域名前綴（`epi_glv_mean` / `mg_glv_mean`；只接一個時名字跟以前逐字相同）；
> `region_key`（單一角色，例 `glv_stats` 的 `reference_region`「跟誰比」）第二條線是
> **取代**。量測卡的迴圈在 `MultiSourceStep`，子類只實作 `measure` —— 它不必
> 知道接了幾條流，也不必知道接了幾個區域。

> **一張卡同時吐「自己的量」與「比出來的量」時，名字要分家族**（F18，
> 2026-08-21）。`glv_median` 是這一塊自己的灰階、`cmp_delta_median` 是跟參照
> 比出來的，而**比的是哪個統計量落在尾巴** —— 使用者可以一次挑好幾個統計量，
> 那是唯一不撞的寫法。理由不是整齊：這些名字會排在同一份 CSV、同一條分數
> 表達式裡，而「這個數字是誰跟誰算出來的」在那兩個地方沒有別的線索。
> 改名要**連同分數表達式一起遷移**，而對照表住在那張卡上
> （`Step.legacy_feature_renames`），不是住在 `recipe.py`。

> **卡片庫由上而下的順序 = `steps/__init__.py` 的 import 順序**（F29，
> 2026-08-25）。`list_steps()` 就是照 `REGISTRY` 的插入序回，不排序 ——
> 所以加一張卡要**放在它該出現的位置**，不是接在檔案最後。
> 這一條是踩出來的：2026-08-25 使用者說「Measure 的 card 順序幫我改命名&重排：
> GLV → CD → Focus index」，那一輪改了 import 順序、也在那裡寫下這句話，
> **而畫面上一格都沒有動** —— 當時 `list_steps` 是照 `key` 的字母序排的
> （CD、Focus index、GLV）。整個改動看起來完成了，全套測試也全綠，因為沒有
> 任何一條測試問過「使用者看到的第一張是哪一張」。現在有了：
> `tests/test_card_library_order.py`。

> **使用者面的字走 `ui/strings.py`，卡片名與階段名不走**（F98 U14，
> 2026-09-08）。翻譯層擺在**共用的那幾支** —— `_tool_button`、`small_button`、
> `_HintLabel.set_full_text`（每一句 `ParamSpec.help`）、狀態列 —— 所以加一張
> 卡、加一句 help 都**不必做任何事**，它自動就在待翻清單上。鍵就是英文原句，
> 缺翻譯就回原句。
>
> ⚠ **`Step.label` 與 `step.GROUPS` 的標題不准進 catalog**：它們是 recipe JSON
> 的鄰居與廠內的共同語彙，翻掉的話同一份 recipe 在兩台機器上講的是兩個名字。
> 三條測試守著，其中一條直接檢查出貨的 `zh_TW.json` 裡沒有任何卡片名。
> 還缺哪些句子跑 `python tools/i18n_todo.py`（**不是掃原始碼** —— 大部分句子
> 在原始碼裡看起來不像要翻的東西）。

> **一格選項＝一排膠囊（圖 + 字），不是下拉**（F68 第二輪，2026-09-01，
> 使用者：「我認為設定區都要變成這樣 icon 膠囊 + 文字，並且視覺模型可能要
> 接近會比較好」）。型別是 `chip_choice`：`choices` 每一個值配一個
> `icons`（畫它的那支住在 `d4t/ui/glyphs.py`，共通文法寫在那份的檔頭）、
> 一句 `choice_help`（tooltip），拼不對的值再補一格 `choice_labels`
> （`zscore` → `Z-score`；那張表**只放例外**）。值的格式跟 `choice`
> 一字不差，所以 recipe JSON 不受影響。
>
> `type="choice"`（純下拉）與 `icon_choice`（只有圖、名字退到 tooltip）
> 這一輪都退場了：前者留著當「這一排真的畫不出圖」的退路，但
> `tests/test_ui_widgets.py::test_no_card_anywhere_still_shows_a_bare_dropdown`
> 會擋 —— 那正是停下來想一下的地方；後者**刪掉**了（同一個面板上兩種長相，
> 使用者要學兩次，而圖是掃視時的錨點、字才是意思）。

> **把 `min`/`max` 填好，滑桿是免費的**（F7-8）。ParamForm 看到有上下界的
> `int`/`float` 就自動配一支跟數字框雙向綁定的滑桿。這不只是好看 ——
> 使用者是一邊拖一邊看影像決定值的，「先想好一個數字再輸入」那個順序是反的。
> `type="curve"` 則會拿到一張可以自己拉的色調曲線編輯器（見 `pipeline/curve.py`）。

> **卡片自動做的每一個決定，都要變成一個使用者畫得出分布的數字**（F19）。
> 有 `auto` 選項的參數，就要有一個特徵說出它這一顆選了什麼（CD 的
> `cd_axis_deg` / `cd_bright`）。理由不是完整性：`target="auto"` 在一批 patch
> 上逐顆挑了不同的極性，於是 `cd_median` 那一欄同時裝著「線寬 6.5」與
> 「溝寬 9.4」**兩群**數字 —— 每一顆都吐得出正常的值，而 CSV 上沒有任何線索。
> 同一族的還有「量得準不準」（`glv_pixels` / `cd_n`）：**算不出來的那一格不寫**
> （不是 0、也不是 NaN），但「為什麼沒寫」要留得下來。

> **量測卡要在影像上標出它正在量哪裡**：覆寫 `Step.overlay_marks(ctx, params)`
> 回 `(線段, 每條線上的點, 要畫粗的那一條)`，正規化座標，預設什麼都不畫。
> 這是**整個 Measure 段共用**的一條路（F19 建的，F18 §9.0 指名要的）——
> 讀 meta 的程式碼住在**那張卡**上，UI 只負責畫。
> ⚠ 它跟區域框**不同來源**：框從 model 推導（recipe 說要看哪裡），標記來自跑完
> 的 context（這一顆真的量到了什麼）。混在一起的話，「框還在但標記沒了」這個
> 最有用的狀態就講不出來。

---

## 4. 開發流程

```bash
python -m venv .venv && .venv\Scripts\activate      # Windows
pip install -r requirements.txt && pip install pytest ruff

ruff check                                         # 靜態檢查（幾秒，先跑這個）
QT_QPA_PLATFORM=offscreen pytest -q                # 全部測試（Windows 不用設）
python tools/make_sample.py /tmp/lot --n 100       # 產合成資料
python -m d4t gui                                # 開 Studio
python -m d4t run <recipe>.json /tmp/lot/LOT_SYN.001 \
    --workers 4 --cache /tmp/cache --db /tmp/runs.db --csv features.csv
```

**`ruff check` 先跑**（2026-09-03 加，設定在 `pyproject.toml` 的 `[tool.ruff]`，
CI 有一個獨立的 lint job）。它幾秒就有答案，而測試要三分半 —— 一個打錯的名字
不值得等那麼久。它掃的是 `d4t/` `tools/` `fab_probe/` `conftest.py`，**不掃
`tests/`**（理由寫在設定裡：UI 測試刻意 lazy import Qt，ruff 在那裡會報 1,217
條誤報）。

⚠ **`--fix` 要看過再收。** 第一次跑的時候它自動刪掉了 `ingest/pair_source.py`
一個「這個模組自己沒用到」的 import —— 而那是一個**轉出口**，`studio.py` 與
`__main__.py` 都在用 `pair_ingest.columns_of(...)`。F401 問的是「這個檔案有沒有
用到」，答不出「別人有沒有透過這個檔案用到」。轉出口請留 `# noqa: F401` 加一句
為什麼（`__init__.py` 整份免除，那是設定裡的 per-file-ignores）。

**跑測試的方式很重要**（不照做會浪費很多時間）：

- 開發迴圈**只跑改到的測試檔**：`pytest -q tests/test_xxx.py`。
- 核心（`--ignore-glob="*test_ui_*"`）約 3 分半，隨時可以跑。
- **UI 測試不要用一個行程跑整套** —— Qt 物件不會因為測試結束就消失，於是後面
  每開一個視窗都要跟愈來愈多的殘留物一起做版面計算，時間是**超線性**的。
  CI 上實測：一個行程 **1:39:09**，分兩批 **7 分鐘**。要跑就逐檔跑：

  ```bash
  python tools/run_tests.py            # 全套，逐檔一個行程 + 最慢的幾個
  python tools/run_tests.py --fast     # 略過 UI（commit 前記得跑一次完整的）
  ```

  ⚠ **這裡以前寫的是 `for f in tests/test_ui_*.py; do pytest -q "$f"; done`，
  而那是 bash —— 家用機是 Windows（上面那行 `.venv\Scripts\activate`），
  PowerShell 不吃那個語法。** 也就是一份寫給某台機器的程序，在那台機器上跑
  不動；跟 `docs/NO-GIT-SETUP.md` 那個「按 blob 頁的複製鈕」是同一類問題，
  同一天（2026-09-03）一起修的。`run_tests.py` 是 stdlib-only 的 Python，
  兩台都跑得動。

### 三把尺：正確性以外的兩條軸（F90，2026-09-08）

在這之前，這個 repo 的每一道關都在問**「數字對不對」**（黃金值、九條卡片
不變量、round-trip identity、逐位元組的決定論），而**沒有一道在問「東西多大」
或「跑多久」**。症狀量得出來：`studio.py` 在**沒有任何一輪動它**的一週長了
181 行，而「單批 10,000 顆仍然流暢」從 M2 寫在 README 上，從來沒有被量過。

| 尺 | 在哪 | 什麼時候會叫 |
|---|---|---|
| **規模** | `tests/test_size_ceilings.py`（進核心那一批，不碰 Qt，3 秒）| 凍住的五支檔案變長、沒列名的檔案超過 2,200 行、`d4t/ui` 按卡片名字分支的地方超過 23 個、`StudioWindow` 超過 268 方法／393 個 `self.*`、遷移超過 19 道 |
| **時間** | `tools/bench.py`（**家用機**，同 `freeze_golden.py` 的形狀）| 手動跑 `--check`。時間欄容差 2×（機器會漂），**結構欄嚴 ±2%**（每顆的結果 payload、快取存下幾份 —— 那兩個跟機器無關）|
| **藏起來的參數** | `tests/test_card_invariants.py` 的 **I9** | 一個 `show_when` 藏起來的參數改變了結果或宣告。registry 有 91 個參數掛 `show_when`（`roi_reference` 一張卡 33 個），在這條之前那是**靠人記得** |

**天花板的意思不是「不准變大」，是「變大要有人簽名」** —— 上限就寫在測試裡，
要調高就得在同一個 commit 裡改那個數字**並說一句為什麼**，而那句話就是 code
review 的內容。五條設計規則（設在現在的值、每格附理由、配反向測試、一張表一個
家、調高要說理由）寫在 `test_size_ceilings.py` 的檔頭。

⚠ **`bench.py` 的基準是在容器裡凍的**（Linux / numpy 2.4.6 / cv2 5.0）。
家用機第一次跑 `--check` 會看到一行「這份基準是在別的環境凍的」——
那時候重凍一次（`python tools/bench.py`），**但結構那兩欄跨機器照樣要對得上**。

**每次改完之後**（**家用機**，公司機不能執行 git）：

```bash
git add -A && python tools/release.py && git add -A
```

`git add` 要在前面 —— 兩個產出都是從 `git ls-files` 產的，還沒 add 的新檔案會
**安靜地不在裡面**。`tests/test_offline_tools.py` 會擋住它們過期。
哪一支工具在哪一台機器跑，見 [`AGENTS.md`](AGENTS.md) §4.5。

新功能請開 `docs/plans/F<n>-<name>.md`（沿用 GLAS/MMH 慣例），完成後更新
`SESSION_LOG.md`；做完不再改的計畫書搬進 `docs/history/plans/`。

### 新的 UI 面板一律開新模組（不要塞進 `studio.py`）

`StudioWindow` 是這個 repo 裡唯一一個**自己會長大**的類別。寫下這一段時它是
5,244 行 / 229 個方法，三天後 6,017，再三天 6,761 —— **一週多長了 1,517 行，
而中間沒有任何一輪是在動它**。F76 那一輪從它手上拿走了兩支方法
（`_feature_sections` / `_feature_specs`），而它同一輪又多了判定那一塊的三支
—— 淨值仍然是往上。

⚠ **它現在有幾行、幾個方法、幾個 `self.*`，去 `tests/test_size_ceilings.py`
看，這裡不抄第二份。** 那是 F90 那把尺自己的第四條設計規則（「一張表、一個
家」），而它防的正是 2026-08 那次 `tools/doctor.py` 對每台機器給出錯診斷的
病根 —— 抄出來的那一份一定會漂。上面那幾個數字留著是因為它們講的是**一段
歷史**（漂移長什麼樣），不是「現在多大」。

它還沒到「非拆不可」，但**拆分壓力已經在影響新功能該放哪裡**了 —— F22 的 commit
訊息裡就寫著「不塞進已經 5000 多行的 `studio.py`」，那是一個人在替一個結構問題
繞路。

所以規矩寫下來：**一塊新的面板／畫布元件＝一個新模組**。F22 的
`ui/decide_panel.py`、F24 的 `ui/tree_panel.py`／`ui/tree_scene.py`、F25 的
`ui/route_badge.py`、F27 的 `ui/verdict_band.py`／`ui/results_table.py`、
F44 的 `ui/region_words.py` 已經都是這樣做的 —— 這一段只是把它從「這次剛好這樣
做」變成「本來就這樣做」。**F91 的七支一起走同一條**：`ui/baseline.py`（跟上
一次比差多少）、`ui/truth_marks.py`（在表上標真缺陷／誤報）、
`ui/fit_screen.py`（視窗裝得進螢幕）、`ui/crashlog.py`（未預期錯誤的 log）、
`ui/autosave.py`（草稿與救回）、`ui/problems_bar.py`（常駐的「為什麼還不能跑」）
與 `ui/status_log.py`（狀態列說過的話）—— 六件事、七支模組，而 `studio.py`
只多了接線。**F99／F100（2026-09-08）再四支**：`ui/workbench.py`（Build／Tune
的幾何：畫布當導覽在上、設定區吃滿中欄下半、右欄上影像下儀表）、`ui/card_menu.py`（空白處右鍵與拖線
到空白處的「加一張卡」選單）、`ui/clipboard.py`（Ctrl+C/V/D）、
`ui/windows_menu.py`（Help 鈕的小箭頭列出開著的視窗）。**2026-09-09 再一支**：
`ui/splitters.py`（區域之間的細線 —— 把手 5px 抓得到、中間 1px 看得見；QSS 對
splitter 把手算尺寸不分方向，四種寫法都做不到，所以把手自己畫；`d4t/ui` 裡
不准再直接 `QSplitter(`，有測試數像素）。

> ⚠ 這張清單上以前還有 **F30 的 `ui/output_band.py`**，而它 2026-08-28 被
> **刪掉**了（F50）。規矩沒有變 —— 變的是那一塊該不該存在：那個框畫的是
> 「Output 這幾張卡整批跑一次」，而**框的意思是「這幾個是一組」，真相卻是
> 「跑的時間不一樣」**。編碼錯了，所以那件事現在是卡片自己的一條腳帶。
> **一塊新元件開一個新模組是對的；先問那一塊該不該是一塊。**`studio.py` 留給**接線**（建 widget、接訊號、轉呼叫），
不留給內容。

### 視窗、當機、草稿：三件會安靜做錯的事（F91，2026-09-08）

* **不要寫死視窗尺寸。** `widget.resize(1440, 900)` 在開發機（1920×1080）上
  看不出問題，在機台旁那台 1366×768 的 PC 上是「底部那排鈕在螢幕外面」——
  而 Qt 不會自己捲。改用 `fit_screen.fit(widget, w, h)`，它會先把
  **最小尺寸**降下來（不做這一步的話 `resize` 根本沒有效果）再取小的那個。
  有一條測試擋著 `d4t/ui` 裡再出現寫死的 `resize(w, h)`，另一條把每個頂層
  視窗真的開起來量 geometry。
  ⚠ **內容本身比螢幕高**的那種（`gc_generator` 量出來 1,144 px）縮視窗沒有
  用，要在**建構時**掛到 `fit_screen.scroll_host` / `scrolled` 上 ——
  事後把既有版面搬進捲軸在 PySide6 上是 **segfault**，不是例外。

* **測試不准寫進使用者真正的那幾個檔案。** `crashlog`（`~/.d4t/log`）、
  `autosave`（`~/.d4t/autosave.json`）、baseline（QSettings）三個都會寫磁碟，
  而測試寫進真的那一份的話，開發者下次開 Studio 會被問要不要救回一條測試造出
  來的 pipeline。三個都有具名的覆寫點（`crashlog.LOG_DIR` / `autosave.DIR` /
  `BaselineStore(settings)`），而 `StudioWindow` 在 `_running_under_pytest()`
  時預設把草稿關掉。**加第四個會寫磁碟的東西時，先把那個覆寫點做出來。**

* **會跳 modal 對話框的新東西要有一個關得掉的旗標。** `crashlog.SHOW_DIALOG`
  與 `autosave.ASK_ON_START` 跟 `studio.PROMPT_ON_CLOSE` 是同一件事：一個
  modal 對話框在 headless 測試裡不會讓測試失敗，它會讓測試**永遠停在那裡**。

⚠ **現在不要動 `studio.py` 本身**，但**理由已經換了一個**。
以前寫的是「那把尺（黃金值）是壞的」—— 那是真的，從 F19（08-21）到 08-23 兩天
沒有在守，而 **2026-08-23 已經重凍、三份全綠**（`docs/history/plans/F21-algo-and-roi.md`
§6 的後記、`SESSION_LOG.md`「黃金值重凍」）。**尺回來了，擋路的只剩順序**：
使用者定的是「先把引擎做對，再回頭產品化」。

所以真的要動的那一天，前置條件是**做得到而不是等得到**：先
`python tools/freeze_golden.py --check` 三份全綠 —— 那就是「改了但數字沒變」的
唯一證據，而這個 repo 踩過六次「跑得完、有數字、而且是錯的」。

### `widgets.py` 那一刀做完了（F93 U7，2026-09-08）

這一段以前的收尾是「再切 `widgets.py` 那幾群自繪圖示（最好拆、風險最低）」。
**那件事做完了**：7,140 行、24 個不相干的類別 → 八支，而 `widgets.py` 只剩
**123 行的轉出口**。`from .widgets import X` 那四十幾個呼叫端**一個字都沒有
改** —— 驗收是黃金值三份逐項相同 ＋ 既有 UI 測試全綠。

新的元件請直接 import 拆出來的那幾支（`ui/fields.py`、`ui/chips.py`、
`ui/icons.py`、`ui/library.py`、`ui/histogram.py`、`ui/image_view.py`、
`ui/param_form.py`、`ui/buttons.py`、`ui/feature_text.py`），意思比較準。
**`widgets.py` 裡不准再有 class / def** —— 有一條測試問這句話
（`test_the_front_door_stayed_a_front_door`），因為沒有它的話三個月後那支
檔案會再長回來，而那正是 F90 那把尺量到的漂移。

⚠ 那一刀學到的一件事，下一次搬家會再用到：**「誰在用這個名字」不能只掃
import**。測試大量用屬性存取（`widgets_mod.METRIC_GROUP_ORDER`），而 grep 與
`ast` 的 import 掃描都看不到它 —— 第一版因此漏了 10 個名字。判準要是
「拆之前模組上有的每一個名字，拆之後 `hasattr` 還答得出來」。

---

## 5. 產品範圍開關

**Studio 吃四種輸入（2026-08-17，F11 Input-3）**，一種 source 一個入口：

**一種 source 一張卡**（F11 Input-4，使用者定調）：Input 段有兩張載入卡 ——
`load_patch`「Load images」（一顆好幾張，`channel_map` 命名）與 `load_single`
「Load one image」（一顆一張，`out` 命名）。**兩張都不看資料型別**，宣告只看
使用者看得到的值 —— 一張卡服務四種 source 的時候，畫布會說謊（那時候「這張卡吐
哪幾條流」有三個不同的答案，而畫布拿到的是錯的那一個）。

| kind | 什麼樣的資料 | 入口 |
|---|---|---|
| `ebi_patch` | KLARF + patch TIFF（每顆連續幾頁）| `Open KLARF…` |
| `rsem` | KLARF + 每顆一個影像檔 | `Open KLARF…`（自動判別）|
| `tiff_stack` | 一個多頁 TIFF、**沒有 KLARF** | `Open stack…`（問「一顆幾張」）|
| `folder` | 一個資料夾的單張影像、沒有 KLARF | `Open folder…` |

後兩種沒有 KLARF → 沒有座標、**寫不回 KLARF**，而那句話**常駐在資料集標籤上**
（`tiff_stack · defect 1 / 3 · no KLARF`）—— 不是等使用者按了 Export 才發現。

**第二份 lot 走另一條路**（F15，2026-08-19；**F33 於 2026-08-25 續完**）。
那份缺的「點對點包含圖的 report」現在是 `output_char` 那張卡，而它需要的兩個
資料缺口也補了：**配不到的那一顆會留下來**（`pair_found = 0`，繼續走到判定樹
—— 「EBI 根本沒偵測到」是 characterization 要數的一類，不是一個錯誤）與
**die 內排名**（`pair_die_rank` / `pair_die_total`，母體是第二份的完整清單）。
詳見 [`docs/history/plans/F33-ebi-characterization.md`](docs/history/plans/F33-ebi-characterization.md)。
以下是它現在的樣子：

`pair_source` 這張卡上的
`Open data…` 掛的是「拿來對照的那一份」（EBI ↔ RSEM(API) characterization），
它掛在 `Dataset.sources[代號]` 上，**不取代目前的資料集** —— main 決定批次跑幾
顆、走哪一條 route、KLARF 寫回誰。CLI 是 `--source 代號=路徑`（可以重複）。
**卡片不自己 `open()`**：讀檔在 ingest 層（`core/ingest/pair_source.attach`），
路徑不進 recipe，而第二份的身分要進快取簽章 —— 否則換一份而簽章看不見就回舊
影像（鐵則 9）。

`d4t/ui/scope.py` 仍然是這類「暫時不給看」的**唯一**去處，
**而「入口長什麼樣」也住在同一份**（F11 Input-5）。

**2026-09-08（F96 U10）起那幾個旗標由 profile 一次設好**：`fab`（預設，廠內
那台）／`dev`（收起來的全部打開）／`demo`。啟動時看 `D4T_PROFILE` ——
廠內那台是點捷徑開的，捷徑改得動環境變數、改不動命令列。

⚠ **旗標要透過模組讀**（`scope.SHOW_ROUTE_BY`），不准
`from .scope import SHOW_…` —— 那拿到的是一份**當時的複本**，換了 profile 而那
個模組停在舊值，症狀是「設定說關著、畫面上還在」。`welcome.py` 本來就是那樣寫
的，`tests/test_ui_scope_profiles.py` 現在擋著。

```python
SUPPORTED_KINDS = ("ebi_patch", "tiff_stack", "rsem", "folder")
HIDDEN_STEPS = ("align",)        # 收起來（引擎照認、舊 recipe 照跑）
                                 # ⚠ `feature_math` / `feature_fill` 2026-08-27
                                 # **刪掉**了（功能進了 `decide.let`）——
                                 # 先收起來、使用者確定之後再刪，那張對照表
                                 # 第一次跑完全程
SHOW_TEMPLATE_LIBRARY = True     # 工具列的 Templates…（F91 X4 打開）
SHOW_SAMPLE_DATA = False         # 「用範例資料試一次」（仍是死路，見下）
INPUT_SOURCES = (...)            # 三顆 Open 的字、圖示、一句白話說明
ATTACHMENTS = (...)              # 掛在已載入 lot 上的附加檔（GLAS 匯出）
```

**加／改一個入口＝改 `INPUT_SOURCES`，不要動 UI。** 工具列的按鈕與空白狀態
（「一開始進去看到的那一塊」）上的每一列都是從這張表長出來的。以前它們是三份
各自寫死的文字，於是工具列有三顆 Open、空白狀態卻只講 KLARF —— 帶著一個資料夾
的圖片進來的人，在整個畫面最大的那一塊上找不到自己那條路。

`SHOW_TEMPLATE_LIBRARY` / `SHOW_SAMPLE_DATA`（F91 X4，2026-09-08 從一個叫
`SHOW_SAMPLE_ENTRIES` 的旗標拆開）管兩個入口。**拆開是因為它們的死法不一樣**，
而一個共用旗標會讓打開其中一個順手把另一個也放回畫面上：

* **`Templates…`（`SHOW_TEMPLATE_LIBRARY = True`）** —— 2026-08-16 收起來的
  理由是「庫是空的」，而那是真的有機制：`welcome.RECIPES_DIR` 指的是
  ``examples/recipes``，一個同一天刪掉的路徑。現在它指 `recipes/`，那裡有出貨
  的 recipe 而且 `test_shipped_recipes.py` 逐份跑過 —— 理由到期，入口回來。
* **「用範例資料試一次」（`SHOW_SAMPLE_DATA = False`）** —— 仍然是死路，
  而且**修不掉旗標**：`run_demo` 產的是合成的 `ebi_patch` lot，而
  `TEMPLATE_RECIPE` 指的那份不存在、出貨的兩份是 `rsem` 與 `folder` route。
  要打開它得先有一份出貨的 ebi_patch recipe。有一支反向測試守著這句話。

`run_demo` / `RecipeLibraryDialog` 一行都沒動 —— 收起來的是入口不是能力。

`tests/test_ui_input_kinds.py`（原 `test_ui_patch_only.py`）鎖住四種都進得來、
沒有 KLARF 的兩種會講出來、而**「暫時收起來」的機制還在**。

**收起來（`HIDDEN_STEPS`）／刪掉／改名是三件不同的事，判準都是使用者說了哪一
句話**，不是你覺得那張卡有沒有用。2026-08-18 一天之內三種都發生過：

| 使用者說的 | 處置 | 代價 |
|---|---|---|
| 「之後真需要我再回來」（`align`）| **收起來**：卡片庫看不到，`get_step` 拿得到、舊 recipe 照跑、黃金值不動 | 加一個字串 |
| 「不需要這功能」（`cell_period`）／「完全沒用」（`pattern_ref`）| **刪掉**：`REGISTRY` 裡沒有，舊 recipe 開起來是一條 `unknown-step` | 依賴它的 fixture / 黃金值要一起處理 |
| 「拿回來 不過要改名字」（`golden_cell` → `pattern_ref`）| **改名**：要一道遷移 | key **加上**它寫出來的 feature 名（那些會被打進分數表達式）—— 只換一半等於沒換 |
| 「名字剪短一點」（`CD measure` → `CD`）| **只改 `label`** | 零：`key` 是 recipe 的鍵、feature 名是表達式的變數名，兩者都不准動 |

同一張卡（`pattern_ref`）走完了**刪掉 → 量代價 → 要回來 → 改名 → 收起來 →
刪掉**六步，最後一步是 2026-08-20（F16，使用者：「完全沒用，請直接拿掉」）。

2026-09-02（F74）同一天用掉兩列：`roi_mask` **刪掉**、`roi_reference` 的 label
從「Reference regions」**改成「ROI」**。⚠ **那次刪掉幾乎沒有代價** —— 零份
recipe、零份 fixture、零個黃金值在用它。所以下面那張價目表講的不是「刪一定貴」，
是**「先去量」**：貴不貴由「誰在用它」決定，而那件事 `grep` 得出來。

**而這一次代價真的付了**，值得記住價差長什麼樣：

| | 收起來（2026-08-18） | 刪掉（2026-08-20） |
|---|---|---|
| 動到什麼 | 一個字串 | 卡片、測試、fixture 的 rsem route、一組黃金值 |
| rsem route 的準確率 | 24/24（照跑）| **每一顆都判 bin 0**（seed 11/3/21 皆 12/24，而那 12 顆正好是沒有缺陷的那些）|
| 那條 route 還證明什麼 | 「單張影像也判得出缺陷」 | 只剩「跑得完、算得出分數」|

**不確定的時候先收起來**：成本是零，回復的成本是拿掉一個字串。使用者確定之後
再刪 —— 上面那張表就是「確定」值多少錢。

> ⚠ **`d4t/core/algo/` 底下有四支「呼叫者很少、但不准刪」的模組。**
> 每一次刪卡都會讓其中一支再少一個呼叫者，而那正是它被當成死碼順手清掉的時候。
>
> | 模組 | 為什麼留 | 誰還在呼叫 |
> |---|---|---|
> | `snr.py` | `snr_signed` 是**正負號慣例的規範出處**，GLV 的 `snr` 統計量照它做 | 只剩測試（`snr_map` 2026-08-25 刪） |
> | `histmatch.py` | `mask=` 是**「量與套用分開」的規範出處**，`range_from` 走同一套 | `normalize` 的 match（`use_within` 2026-09-02 刪） |
> | `period.py` | `estimate_period` / `choose_origin` 的相位搜尋是之後做 **pattern-frame ROI** 的唯一工具（patch 以 defect 為中心裁切，晶格相位逐顆不同）| `algo/template.py` 一個 |
> | `golden.py` | 疊 Golden Cell 模板要 `stack_cells` / `tile_coords` | 同上 |
>
> 2026-08-18 有一小時 `period` / `golden` 一個呼叫者都沒有。
> 便利貼：`tests/test_ui_input_kinds.py::test_period_module_is_not_orphaned`。

CLI 不受影響：`python -m d4t run` 照樣跑得動 rsem recipe。

---

## 6. 來源專案對照（vendoring）

每個 vendored 模組檔頭都註明來源與改動。原始專案：

> **授權那一面不在這裡** —— 逐支模組的來源清單、六個專案各自的授權狀態、
> 第三方相依的授權，全部住在 [`docs/LICENSING.md`](docs/LICENSING.md)
> （有測試守著兩張表不漂）。下面這張表講的是**技術脈絡**：誰提供了什麼。
> 六個專案都是同一個作者自己的，所以 vendoring 這件事沒有第三方授權義務；
> 真正有義務的是執行時的相依套件。

| 來源 | 提供了什麼 |
|---|---|
| **KLIP** | KLARF 1.2/1.8 無損引擎、TIFF page 對應、健檢 lint |
| **GLAS** | fine align、SEM loader、DAG 拓撲排序概念、ROI label map 契約 |
| **MMH** | recipe 架構原型、批次引擎模式、次像素邊緣定位、品質指標、KLARF 寫回 |
| **PEAR** | GLV 統計 metric bank、Tukey 離群、**均勻度與位置趨勢**（F85）、CJK-safe 影像載入 |
| **cell-period-estimator** | 週期估測、Golden Cell 堆疊、ghosting 分數 |
| **Perspective-Combination (Fusi³)** | 正規化、直方圖匹配、5-backend 對位、MultiROISet（~~SNR map~~ 2026-08-25 刪、~~blob 分割~~ 同日隨 `find_defect` 刪）|
