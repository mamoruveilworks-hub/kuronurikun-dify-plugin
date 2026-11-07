# This file is copied from the Kuronuri-kun API (app/replace.py) by tools/sync_plugin_engine.py.
# Do not edit it here; edit the original and run the script again.
"""記号への置き換えと、元に戻す処理（暗号を使わない部分）。

Dify プラグインの「社外に出さない版」でもそのまま使うため、標準ライブラリだけで書いている。
tools/sync_plugin_engine.py でプラグインに写す。
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from enum import Enum

from .entities import Entity

_PLACEHOLDER = re.compile(r"\[([A-Z_]+)_(\d+)\]")


class MaskStyle(str, Enum):
    TAG = "tag"            # [PERSON_1]（可逆、LLM連携向け）
    ASTERISK = "asterisk"  # ****（文字数を保つ）
    BLOCK = "block"        # ■■■■（文字数を保つ黒塗り）
    REDACT = "redact"      # [個人情報]


@dataclass
class MaskResult:
    masked_text: str
    entities: list[Entity]
    mapping: dict[str, str]  # placeholder -> 元の値（TAG のときのみ）


def mask(text: str, entities: list[Entity], style: MaskStyle = MaskStyle.TAG) -> MaskResult:
    """検出結果に従ってテキストを置換する。

    TAG では同じ値には同じプレースホルダを振る（例：同じ人名は常に [PERSON_1]）。
    LLM が「誰が誰か」を区別できるようにするため。
    """
    counters: dict[str, int] = {}
    value_to_tag: dict[tuple[str, str], str] = {}
    mapping: dict[str, str] = {}

    parts: list[str] = []
    cursor = 0
    for e in sorted(entities, key=lambda x: x.start):
        parts.append(text[cursor:e.start])
        if style is MaskStyle.TAG:
            key = (e.type.value, e.text)
            tag = value_to_tag.get(key)
            if tag is None:
                counters[e.type.value] = counters.get(e.type.value, 0) + 1
                tag = f"[{e.type.value}_{counters[e.type.value]}]"
                value_to_tag[key] = tag
                mapping[tag] = e.text
            parts.append(tag)
        elif style is MaskStyle.ASTERISK:
            parts.append("*" * e.length)
        elif style is MaskStyle.BLOCK:
            parts.append("■" * e.length)
        else:
            parts.append("[個人情報]")
        cursor = e.end
    parts.append(text[cursor:])
    return MaskResult("".join(parts), entities, mapping)


def unmask(text: str, mapping: dict[str, str]) -> str:
    """プレースホルダを元の値に戻す。対応表にないものはそのまま残す。"""
    return _PLACEHOLDER.sub(lambda m: mapping.get(m.group(0), m.group(0)), text)
