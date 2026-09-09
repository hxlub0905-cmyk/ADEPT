"""d4t — flexible multi-step ADC for semiconductor inspection.

讀 EBI patch（test+ref）或 RSEM 單張影像 + 對應 KLARF，
以「步驟卡片組 pipeline」把想法變成算法，對每顆 defect 算分、寫回 KLARF。
"""
__version__ = "0.1.0.dev0"  # M0: vendored core library


def build_id() -> str:
    """這一份程式碼的身分：``tools/FILELIST.txt`` 的 blob SHA 前 12 碼。

    跟 ``bundle/d4t_bundle.py`` 檔頭那一行 ``BUILD`` 是同一個數（2026-09-09）——
    公司機是解包來的、沒有 git，「我這台跑的是哪一版」只有這個答得出來。
    清單不在（例：pip 裝的、或搬到別處）就回 ``unknown``。
    """
    import hashlib
    import os

    path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                        "tools", "FILELIST.txt")
    try:
        with open(path, "rb") as f:
            data = f.read()
    except OSError:
        return "unknown"
    return hashlib.sha1(b"blob %d\0" % len(data) + data).hexdigest()[:12]


def version_line() -> str:
    """``python -m d4t --version`` 印的那一行。"""
    return "d4t %s (build %s)" % (__version__, build_id())
