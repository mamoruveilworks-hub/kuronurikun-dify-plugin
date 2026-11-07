# This file is copied from the Kuronuri-kun API (app/engine.py) by tools/sync_plugin_engine.py.
# Do not edit it here; edit the original and run the script again.
"""検出エンジン：全検出器を走らせ、重なりを解消して結果を返す。"""

from __future__ import annotations

import bisect
from typing import Iterable

from .entities import DEFAULT_TYPES, OPTIONAL_TYPES, Entity, EntityType
from .normalize import normalize
from .rules import DETECTORS


def _resolve_overlaps(cands: list[Entity]) -> list[Entity]:
    """スコアが高い順・長い順に採用し、既に採用したものと重なる候補は捨てる。

    採用済みの区間は重ならないので、開始位置で並べておけば「直前と直後の1つずつ」を見るだけで
    重なりを判定できる（二分探索）。候補が数万件あっても速い。
    """
    starts: list[int] = []
    chosen: list[Entity] = []
    for c in sorted(cands, key=lambda e: (-e.score, -e.length, e.start)):
        i = bisect.bisect_right(starts, c.start)
        if i > 0 and chosen[i - 1].end > c.start:
            continue
        if i < len(chosen) and chosen[i].start < c.end:
            continue
        starts.insert(i, c.start)
        chosen.insert(i, c)
    return chosen


def _propagate_names(text: str, found: list[Entity]) -> list[Entity]:
    """一度氏名と判定した文字列は、文中の他の出現箇所も氏名として扱う。

    例：「西山俊之様」で検出 →「西山俊之です」の方も伏せる。
    同じ名前が何百回出てきても、名前ごとに1回だけ探す（候補が爆発的に増えないように）。
    """
    best: dict[str, float] = {}
    spans: set[tuple[int, int]] = set()
    for e in found:
        if e.type is EntityType.PERSON:
            spans.add((e.start, e.end))
            if e.score > best.get(e.text, 0.0):
                best[e.text] = e.score
    extra: list[Entity] = []
    for name, score in best.items():
        pos = text.find(name)
        while pos != -1:
            if (pos, pos + len(name)) not in spans:
                extra.append(Entity(EntityType.PERSON, pos, pos + len(name), name, round(score * 0.95, 3)))
            pos = text.find(name, pos + 1)
    return found + extra


def resolve_types(
    types: Iterable[EntityType] | None = None,
    extra: Iterable[EntityType] | None = None,
) -> set[EntityType]:
    """検出する種類を決める。

    types を指定すればその種類だけ（オプションの種類も含められる）。
    省略すれば既定の種類。extra はそこに追加する種類。
    """
    wanted = set(types) if types else set(DEFAULT_TYPES)
    if extra:
        wanted |= set(extra)
    return wanted


def detect(
    text: str,
    types: Iterable[EntityType] | None = None,
    min_score: float = 0.5,
    extra: Iterable[EntityType] | None = None,
) -> list[Entity]:
    """テキストから個人情報を検出する。

    types / extra で種類を選ぶ（resolve_types を参照）。min_score 未満の候補は捨てる。
    """
    wanted = resolve_types(types, extra)
    norm = normalize(text)

    cands: list[Entity] = []
    for detector in DETECTORS:
        for etype, start, end, score in detector(norm):
            # 指定されていないオプションの種類は、重なり解消にも参加させない。
            # （例：会社名の候補が氏名の候補に勝ってから捨てられ、氏名まで消えるのを防ぐ）
            if etype in OPTIONAL_TYPES and etype not in wanted:
                continue
            if start < end:
                cands.append(Entity(etype, start, end, text[start:end], score))

    cands = _propagate_names(text, cands)
    # 種類の絞り込みは重なり解消の「後」に行う。
    # 先に絞ると、本来は別種類（例：電話番号）として扱うべき部分が誤った種類で残るため。
    resolved = _resolve_overlaps(cands)
    return [e for e in resolved if e.type in wanted and e.score >= min_score]
