# This file is copied from the Kuronuri-kun API (app/table.py) by tools/sync_plugin_engine.py.
# Do not edit it here; edit the original and run the script again.
"""表形式（TSV / CSV）の見出し行から列の種類を判定し、セルを丸ごと検出する。

表では「氏名」「生年月日」などの手がかりが見出し行にしかなく、値の近くにないため、
文章向けのルールでは拾えない。そこで見出しで列を特定し、その列の全セルを対象にする。
"""

from __future__ import annotations

import re
from typing import Iterator

from .entities import EntityType

# 見出しのキーワード → 種類。上から順に判定する（「クレジットカード番号」を先に拾うため）。
HEADER_RULES: list[tuple[re.Pattern, EntityType]] = [
    # 「クレジットカード有効期限」をカード番号と取り違えないよう、有効期限を先に判定する
    (re.compile(r"有効期限|有効期間|expir|^exp\.?$|valid ?thru", re.I), EntityType.CARD_EXPIRY),
    (re.compile(r"クレジット|カード番号|card", re.I), EntityType.CREDIT_CARD),
    (re.compile(r"マイナンバー|個人番号|my ?number", re.I), EntityType.MY_NUMBER),
    (re.compile(r"免許"), EntityType.DRIVERS_LICENSE),
    (re.compile(r"口座"), EntityType.BANK_ACCOUNT),
    (re.compile(r"生年月日|誕生日|birth|dob", re.I), EntityType.DATE_OF_BIRTH),
    (re.compile(r"メール|mail", re.I), EntityType.EMAIL),
    (re.compile(r"電話|携帯|TEL|phone|FAX", re.I), EntityType.PHONE),
    (re.compile(r"郵便|〒|zip|postal", re.I), EntityType.POSTAL_CODE),
    (re.compile(r"住所|所在地|address", re.I), EntityType.ADDRESS),
    (re.compile(r"^IP|IPアドレス|ip ?address", re.I), EntityType.IP_ADDRESS),
    (re.compile(r"年齢|^age$|^歳$", re.I), EntityType.AGE),
    (re.compile(r"性別|gender|^sex$", re.I), EntityType.GENDER),
    # 「Company Name」を氏名（name）と取り違えないよう、氏名より先に判定する
    (re.compile(r"会社|社名|勤務先|企業|所属|法人名|組織名|company|employer|organization", re.I), EntityType.COMPANY),
    (re.compile(r"氏名|名前|姓名|フルネーム|ふりがな|フリガナ|ひらがな|カタカナ|よみ|名義|^姓$|^名$|name", re.I),
     EntityType.PERSON),
]

# 見出しで列が特定できるのは強い根拠。住所セルの一部だけを拾う文章向けルール(0.95)より優先し、
# 「東京都江東区豊洲1-2-3 豊洲ビル5F」のような建物名までセル全体を伏せる。
SCORE = 0.96
_LINE = re.compile(r"[^\n]*\n?")


def _lines(text: str) -> list[tuple[int, str]]:
    """(行頭の位置, 改行を除いた行) の一覧。"""
    out = []
    for m in _LINE.finditer(text):
        if m.group() == "" and m.start() == len(text):
            break
        out.append((m.start(), m.group().rstrip("\r\n")))
    return out


def _cells(line: str, sep: str) -> list[tuple[int, int]]:
    """行内の各セルの (開始, 終了)。前後の空白と引用符は含めない。"""
    spans, pos = [], 0
    for raw in line.split(sep):
        s, e = pos, pos + len(raw)
        while s < e and line[s] in " \t\"'":
            s += 1
        while e > s and line[e - 1] in " \t\"'":
            e -= 1
        spans.append((s, e))
        pos += len(raw) + 1
    return spans


def _column_types(line: str, sep: str) -> dict[int, EntityType]:
    cells = [line[s:e] for s, e in _cells(line, sep)]
    # 見出しはラベルの並び。数字や@を含む行（＝データや文章）は見出しとみなさない
    if len(cells) < 2 or any(re.search(r"[0-9@]", c) for c in cells):
        return {}
    types = {}
    for i, header in enumerate(cells):
        if not header or len(header) > 30:
            continue
        for pattern, etype in HEADER_RULES:
            if pattern.search(header):
                types[i] = etype
                break
    return types


def detect_table(t: str) -> Iterator[tuple[EntityType, int, int, float]]:
    lines = _lines(t)
    i = 0
    while i < len(lines):
        _, header = lines[i]
        sep = "\t" if "\t" in header else ("," if "," in header else None)
        if sep is None:
            i += 1
            continue
        ncols = header.count(sep) + 1
        types = _column_types(header, sep)
        if not types:
            i += 1
            continue
        # 見出しと同じ列数の行が続く間をデータ行とみなす
        j = i + 1
        while j < len(lines) and lines[j][1].count(sep) + 1 == ncols:
            offset, row = lines[j]
            for col, (s, e) in enumerate(_cells(row, sep)):
                if col in types and s < e:
                    yield types[col], offset + s, offset + e, SCORE
            j += 1
        i = max(j, i + 1)
