# 對比度是算出來的，現在也要是守住的 — authored 2026-09-08 (F99 P2-3).
"""`theme.py` 裡每一個顏色都是**量過**才定的（`contrast_ratio` / `AA_SMALL` /
`readable_on` 就住在那裡，docstring 記著舊值 1.89、2.90 那些數字）——但沒有一條
測試問過「現在還是嗎」。下一次有人調 ``text_hint`` 亮一點，兩個主題裡有一個會
安靜地掉到 AA 以下，而那正是 2026-09-08 外部評審說「投資報酬率最高的一條測試」。

門檻分兩層，而且**照現況設**（同 F90 那把尺：先量再設，調高要有人簽名）：

* 正文與次要文字（``text_primary`` / ``text_secondary``）對每一層底色 ≥ 4.5
  （WCAG AA 小字）。
* 提示文字（``text_hint``）≥ 3.0 —— 它刻意淡（那是「這一行不重要」的意思），
  WCAG 對大字與 UI 元件的門檻就是 3.0；掉到 3.0 以下就是看不見了。
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))

from d4t.ui import theme  # noqa: E402

TEXT = {"text_primary": 4.5, "text_secondary": 4.5, "text_hint": 3.0}
GROUNDS = ("bg_page", "bg_panel", "bg_surface", "bg_elevated")


@pytest.mark.parametrize("name", sorted(theme.PALETTES))
@pytest.mark.parametrize("text", sorted(TEXT))
@pytest.mark.parametrize("ground", GROUNDS)
def test_text_reads_on_every_ground_in_every_theme(name, text, ground):
    pal = theme.PALETTES[name]
    ratio = theme.contrast_ratio(pal[text], pal[ground])
    assert ratio >= TEXT[text], (
        "%s：%s（%s）疊在 %s（%s）上只有 %.2f，門檻 %.1f"
        % (name, text, pal[text], ground, pal[ground], ratio, TEXT[text]))


#: 主要鈕（白字疊在 accent 上）的門檻，**照現況設**：light 是 4.6 過 AA；
#: dark 的 accent（``#4b8bf5``）量到 **3.33** —— WCAG 對粗體大字與 UI 元件的
#: 3.0 過得了，AA 小字的 4.5 過不了。要不要把 dark 的 accent 壓深一階是**調色
#: 盤的決定**（它同時是焦點框、連結、選取框的顏色），不在一條測試裡偷偷做；
#: 這裡先把 3.33 釘住不准再掉，而下面那條反向測試在它真的修到 4.5 的那天
#: 會叫，提醒把這格例外拿掉（`CLAUDE.md`：例外清單要配反向測試）。
ACCENT_FLOOR = {"light": 4.5, "dark": 3.0}


@pytest.mark.parametrize("name", sorted(theme.PALETTES))
def test_the_accent_button_label_reads(name):
    """主要鈕：白字疊在 accent 上。"""
    pal = theme.PALETTES[name]
    fg = pal.get("accent_text", pal.get("focus_ring_inverse", "#ffffff"))
    ratio = theme.contrast_ratio(fg, pal["accent"])
    assert ratio >= ACCENT_FLOOR.get(name, 4.5), (name, pal["accent"], ratio)


def test_the_dark_accent_exception_is_still_needed():
    """反向測試：dark 的 accent 一旦真的到 4.5，上面那格例外就該拿掉。"""
    pal = theme.PALETTES["dark"]
    fg = pal.get("accent_text", pal.get("focus_ring_inverse", "#ffffff"))
    ratio = theme.contrast_ratio(fg, pal["accent"])
    assert ratio < 4.5, ("dark 的 accent 現在 %.2f 已經過 AA 了 —— 把 ACCENT_FLOOR "
                         "的 dark 那格改回 4.5" % ratio)


@pytest.mark.parametrize("name", sorted(theme.PALETTES))
def test_semantic_text_reads_on_its_own_tint(name):
    """success / danger / warning 三組各自的 `_text` 疊在自己的 `_bg` 上。"""
    pal = theme.PALETTES[name]
    for fam in ("success", "danger", "warning"):
        fg, bg = pal.get("%s_text" % fam), pal.get("%s_bg" % fam)
        if fg and bg:
            ratio = theme.contrast_ratio(fg, bg)
            assert ratio >= 4.5, "%s：%s_text 疊 %s_bg 只有 %.2f" % (name, fam, fam, ratio)


@pytest.mark.parametrize("name", sorted(theme.PALETTES))
def test_every_stage_count_colour_clears_aa(name):
    """`count_color` 存在的理由就是這一句（舊值在 light 是 1.89）。"""
    before = theme.current_theme()
    theme.set_theme(name)
    try:
        from d4t.core.pipeline.step import GROUP_ORDER
        for gid in GROUP_ORDER:
            col = theme.count_color(gid)
            ratio = theme.contrast_ratio(col, theme.TOKENS["bg_panel"])
            assert ratio >= theme.AA_SMALL - 1e-6, (name, gid, col, ratio)
    finally:
        theme.set_theme(before)
