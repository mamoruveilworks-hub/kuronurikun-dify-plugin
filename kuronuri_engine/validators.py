# This file is copied from the Kuronuri-kun API (app/validators.py) by tools/sync_plugin_engine.py.
# Do not edit it here; edit the original and run the script again.
"""番号や日付の妥当性チェック。誤検出を減らすための要。"""

from __future__ import annotations

import datetime as dt
import ipaddress

# 和暦の元年（西暦）
ERA_START = {
    "明治": 1868, "M": 1868,
    "大正": 1912, "T": 1912,
    "昭和": 1926, "S": 1926,
    "平成": 1989, "H": 1989,
    "令和": 2019, "R": 2019,
}


def digits_only(s: str) -> str:
    return "".join(c for c in s if c.isascii() and c.isdigit())


def is_valid_my_number(number: str) -> bool:
    """マイナンバー（個人番号）のチェックデジット検証。

    先頭11桁を右から n=1..11 と数え、重み Q_n = n+1 (n<=6) / n-5 (n>=7)。
    余り r = Σ(P_n × Q_n) mod 11 とし、r<=1 なら 0、それ以外は 11-r が検査用数字。
    """
    d = digits_only(number)
    if len(d) != 12 or len(set(d)) == 1:  # 000000000000 のような値は除外
        return False
    body = d[:11]
    total = 0
    for n in range(1, 12):
        p = int(body[11 - n])
        q = n + 1 if n <= 6 else n - 5
        total += p * q
    r = total % 11
    check = 0 if r <= 1 else 11 - r
    return check == int(d[11])


def is_valid_luhn(number: str) -> bool:
    """クレジットカード番号のLuhnチェック。"""
    d = digits_only(number)
    if not 13 <= len(d) <= 19 or len(set(d)) == 1:
        return False
    total = 0
    for i, ch in enumerate(reversed(d)):
        n = int(ch)
        if i % 2 == 1:
            n *= 2
            if n > 9:
                n -= 9
        total += n
    return total % 10 == 0


def has_card_prefix(number: str) -> bool:
    """主要ブランドの番号体系（先頭桁）に合うか。"""
    d = digits_only(number)
    return (
        d.startswith("4")                                   # Visa
        or d[:2] in {"51", "52", "53", "54", "55"}          # Mastercard
        or 2221 <= int(d[:4]) <= 2720                       # Mastercard 2系
        or d[:2] in {"34", "37"}                            # Amex
        or 3528 <= int(d[:4]) <= 3589                       # JCB
        or d[:2] in {"36", "38", "39"} or d[:3] in {"300", "301", "302", "303", "304", "305"}  # Diners
        or d.startswith("6011") or d.startswith("65")       # Discover
    )


def to_gregorian_year(era: str | None, year: str) -> int | None:
    """和暦・西暦の年を西暦に変換する。元年にも対応。"""
    y = 1 if year == "元" else int(year)
    if era is None:
        return y
    start = ERA_START.get(era)
    if start is None:
        return None
    return start + y - 1


def is_valid_date(year: int | None, month: int, day: int) -> bool:
    if year is None or not 1868 <= year <= dt.date.today().year:
        return False
    try:
        d = dt.date(year, month, day)
    except ValueError:
        return False
    return d <= dt.date.today()  # 生年月日は未来日にならない


def is_valid_ipv4(s: str) -> bool:
    try:
        ipaddress.IPv4Address(s)
    except ValueError:
        return False
    # バージョン番号（1.2.3.4 など）との混同を避けるため 0.x.x.x は除外
    return not s.startswith("0.")
