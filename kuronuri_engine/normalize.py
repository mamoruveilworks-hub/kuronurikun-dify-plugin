# This file is copied from the Kuronuri-kun API (app/normalize.py) by tools/sync_plugin_engine.py.
# Do not edit it here; edit the original and run the script again.
"""照合用の正規化。

全角英数字や各種ハイフンを半角に寄せるが、文字数は必ず1対1で保つ。
こうすることで、正規化後のテキストで見つけた位置をそのまま元テキストの位置として使える。
（NFKCは「㈱」→「(株)」のように文字数が変わるので使わない）
"""

from __future__ import annotations

import re

# ハイフン・長音・ダッシュ類（電話番号や番地でよく混ざる）
_DASHES = "‐‑‒–—―−－ｰ"


def _build_table() -> dict[int, str]:
    table: dict[int, str] = {}
    # 全角ASCII（！〜～）→ 半角
    for code in range(0xFF01, 0xFF5F):
        table[code] = chr(code - 0xFEE0)
    for ch in _DASHES:
        table[ord(ch)] = "-"
    table[ord("　")] = " "  # 全角スペース
    return table


_TABLE = _build_table()


# 長音記号「ー」は単語（「メール」など）にも使うので、数字に挟まれたときだけハイフンとみなす。
# 日本語入力で「０９０ー１２３４ー５６７８」のように打たれることが多い。
_CHOON_BETWEEN_DIGITS = re.compile(r"(?<=\d)ー(?=\d)")


def normalize(text: str) -> str:
    """文字数を保ったまま照合用に正規化する。"""
    out = text.translate(_TABLE)
    out = _CHOON_BETWEEN_DIGITS.sub("-", out)
    assert len(out) == len(text)  # 1対1変換の保証
    return out
