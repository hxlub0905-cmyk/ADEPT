# F99：外部 UI/UX 評審的修正（2026-09-08）

2026-09-08 一份以 UI/UX 設計師角度做的評審（實際開起 Studio、載 recipe、選卡、
試跑、判定、Results，在 1440×900 與 1366×768、light 與 dark 上截圖）。結論一句：
**引擎與設計系統是 A，畫面組合是 B−，首次使用的可理解度是 C+。** 使用者定調
「將修正建議加入待辦事項後開始修正」；版面配置那一項另開 [F100](F100-workbench-layout.md)。

這一份記的是**每一項改了什麼、住在哪、怎麼驗**。三個 P0 全部符合 F83 那句
「UI 的路壞掉不會讓任何測試變紅」——動畫被測試關掉、fit_screen 只量開窗、
標題重疊沒有人量過寬度——所以每一項都配一條會真的開視窗或量幾何的測試。

## P0

| # | 症狀 | 改了什麼 | 在哪 | 測試 |
|---|---|---|---|---|
| P0-1 | 第二次按 fit／1:1／切 Build 模式丟 `RuntimeError: Internal C++ object (QVariantAnimation) already deleted` | `DeleteWhenStopped` 之後那個殼還握在 `_view_anim` 上；動畫結束時放掉（`_forget_anim`），停動畫前先問殼在不在（`_stop_anim`）。`_tween_nodes`（tidy）同一族同一修法 | `ui/canvas.py` | `test_ui_canvas_animation.py` 三條「跑完再按一次」 |
| P0-2 | GLV 儀表板三張直方圖的標題左右兩段疊在一起 | `paint_note_header` 改吃 `header_boxes`：右段先拿寬度（最多一半）、左段拿剩下的、尾段只在還有位子時畫，每一段各自省略 | `ui/inspectors.py` | `test_ui_panels_pr2.py::test_the_shared_header_never_overlaps_itself` |
| P0-3 | 載入 recipe 選到 GLV 之後 `minimumSizeHint` 1,334、視窗被撐到 1,495（1366 那台裝不下） | 由 F100 解掉：影像進工作台、空白狀態進捲軸（它藏著的那一頁 468 px 是右欄硬最小寬度的來源）、游標讀數 150 → 100 | `ui/studio.py`、`ui/workbench.py` | `test_ui_workbench.py::test_the_studio_fits_the_fab_pc_after_loading_and_picking_a_card` |
| P0-4 | 截字截在最重要的字上：Verdict 膠囊「:han one box is off」、Results 縮圖「more than on…」、設定區 Region 格「…between_columns, be」 | 膠囊最小寬度跟著字走；縮圖停在上面有 tooltip 讀整句（tile 是畫的，走 `viewportEvent`）；接線格的值換行 | `ui/feature_text.py`、`ui/gallery.py`、`ui/wiring_slot.py` | `test_ui_f99_clipping.py` |

## P1

| # | 改了什麼 | 在哪 | 測試 |
|---|---|---|---|
| P1-1 | 空白處右鍵 → 整個卡片庫的選單（照 `step.GROUPS` 分組）；把線拖到空白處放開 → 只列接得上的卡，挑了就加在那裡並把線接上（線是使用者拉的，不違反鐵則 10） | `ui/card_menu.py`（純函式：`grouped` / `compatible` / `input_param_for`）＋ `canvas.add_menu_requested` / `link_dropped` ＋ studio 兩支轉呼叫 | `test_ui_f99_gestures.py` |
| P1-2 | 預覽停在選到的卡時 Verdict 膠囊旁邊說「preview stops at “glv” — press Esc to run the decision too」 | `studio.verdict_note`（純函式）＋ 一顆 `paramHint` | `test_ui_f99_clipping.py` |
| P1-3 | Region 卡標題帶區域名：`ROI · on_pattern`（量測卡與影像卡不帶） | `canvas._NodeItem.title` | `test_ui_f99_clipping.py` |
| P1-4 | 卡片庫徽章 `needs test` → `needs a “test” stream`；卡片第三行用 `ParamSpec.label`（字串版 `info["summary"]` 維持鍵名給狀態列與測試） | `library.missing_words`、`studio._node_summary(use_labels=)` | `test_ui_widgets.py`、`test_ui_f11_canvas_truth.py` |
| P1-5 | 試跑完每張卡右上角 `24 ok · 0.3 s` 或 `3 failed`（traces 折成每卡一行） | `canvas.run_status_from` / `run_text` / `set_run_status` | `test_ui_f99_gestures.py` |
| P1-7 | 選到判定樹的一步時儀表板淡掉並寫「showing “glv” — the card picked last」 | `studio.gauge_note` | `test_ui_f99_gestures.py` |
| P1-8 | Ctrl+C / Ctrl+V / Ctrl+D。設定帶走、接線不帶；貼在原位右下 40 px；一步復原；掛在畫布上（同 Delete） | `ui/clipboard.py`、`edit_plan.copyable_params` | `test_ui_f99_gestures.py` |
| F100 | 畫布橫躺全寬在上、工作台三格在下、Verdict 常駐列 | `ui/workbench.py`，計畫書 F100 | `test_ui_workbench.py` ＋ 重寫的四支版面測試 |

## P2

| # | 改了什麼 | 在哪 | 測試 |
|---|---|---|---|
| P2-1 | `font_body` 12 → 13（對齊 QSS 的 `*`）；QSS 17 個寫死的字級全部改吃 `$font_*`、44 個 `1px solid` 改 `$hairline`；自繪那一面 26 處 `setPointSizeF(max(6.0, pt − 1.0))` 全改 `setPixelSize(theme.font_px(…))` | `ui/theme.py` ＋ 十支自繪模組 | `test_ui_design_tokens.py` 兩條新的 |
| P2-2 | `fields.GROUP_COLORS` 改存 token 名（暗色主題會跟）；三處 `#ffffff` 改 `focus_ring_inverse`；十幾處 `TOKENS.get(k, "#…")` 的影子調色盤拿掉 | `ui/fields.py` 等 | `theme.py` 以外零個 hex 字面值 |
| P2-3 | 對比度參數化測試：三種文字 × 四層底色 × 兩個主題、主要鈕、語意色、階段計數 | — | `test_ui_contrast.py`（dark 的 accent 量到 3.33，釘住並配反向測試） |
| P2-4 | `StageButton`、`VerdictChip`、縮圖牆補 accessible name | `ui/library.py`、`ui/feature_text.py`、`ui/gallery.py` | — |
| P2-5 | `library`、`problems_bar`、`welcome` 的使用者面句子走 `strings.tr` | 那三支 | 既有的 i18n 測試 |
| P2-6 | Help 鈕的小箭頭列出開著的視窗（工具列在 1366 上裝不下第十三顆鈕） | `ui/windows_menu.py` | `test_ui_f99_clipping.py` |
| P2-7 | 第一條「畫面長什麼樣」的測試：1366×768 開 Studio、載資料、選卡、量幾何 | — | `test_ui_workbench.py` |

## 順手修掉的兩個測試陷阱

* **`autosave.offer_restore` 在跑測試時會讀、會問、會刪使用者真正的那一份草稿。**
  一支被中途殺掉的工具（`tools/i18n_todo.py`）留下 `~/.d4t/autosave.json`，之後
  每一條會開 Studio 的測試都停在「Bring back your unsaved pipeline?」上。現在
  `DIR` 是預設而且在 pytest 裡 → 什麼都不碰（`test_ui_autosave.py`）。
* **conftest 那支關掉「要不要存」對話框的 autouse，只在 `d4t.ui.studio` 已經
  import 的時候有效**——在 fixture 裡才 import 的測試檔改不到類別屬性。
  `StudioWindow.__init__` 現在在 pytest 裡預設把它關掉。

## 沒做、或做了一半

* i18n 的 `results_table` 表頭沒接：那些欄名是特徵名，跟卡片名同一類（不翻）。
  「覆蓋率可信前不列出語言」——現在沒有任何地方列出語言，所以沒有東西要收。
* 埠標籤仍然只有 52 px（`_PORT_LABEL_W` 是 F79 格點對齊算進去的，改它要一起
  改欄距），但**改成切中間**：`between_columns` 與 `between_rows` 從後面切都是
  `betwee…`，切中間是 `betw…mns` 與 `betw…ows`，兩顆埠分得出來；角色前綴
  （`ref `）也留著。標題帶區域名之後那個截字不再是身分資訊的唯一出口。
* 卡片上的執行狀態（`24 ok · 0.3 s`）第一版畫在標題那一行的右邊，56% 縮放下
  把 `ROI · on_pattern` 擠成 `ROI · o…`——等於 P1-3 白做。搬到副標那一行。
* dark 主題的 accent 對比 3.33：調色盤的決定，測試釘住了現況。
