# This file is copied from the Kuronuri-kun API (app/entities.py) by tools/sync_plugin_engine.py.
# Do not edit it here; edit the original and run the script again.
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class EntityType(str, Enum):
    """検出対象の個人情報の種類。"""

    PERSON = "PERSON"                    # 氏名（ルール層では敬称・キーワード手がかりのみ）
    ADDRESS = "ADDRESS"                  # 住所（都道府県から始まるもの）
    PHONE = "PHONE"                      # 電話番号
    EMAIL = "EMAIL"                      # メールアドレス
    POSTAL_CODE = "POSTAL_CODE"          # 郵便番号
    DATE_OF_BIRTH = "DATE_OF_BIRTH"      # 生年月日（文脈で判定、和暦対応）
    MY_NUMBER = "MY_NUMBER"              # マイナンバー（チェックデジット検証）
    CREDIT_CARD = "CREDIT_CARD"          # クレジットカード番号（Luhn検証）
    BANK_ACCOUNT = "BANK_ACCOUNT"        # 銀行口座（銀行名・支店名・種別・番号）
    DRIVERS_LICENSE = "DRIVERS_LICENSE"  # 運転免許証番号（文脈で判定）
    IP_ADDRESS = "IP_ADDRESS"            # IPv4アドレス
    PASSPORT = "PASSPORT"                # 旅券（パスポート）番号（英字2文字＋数字7桁、文脈で判定）
    PENSION_NUMBER = "PENSION_NUMBER"    # 基礎年金番号（4桁-6桁、文脈で判定）
    HEALTH_INSURANCE = "HEALTH_INSURANCE"  # 健康保険の記号・番号・保険者番号（文脈で判定）
    # ↓ オプション（既定では伏せない。単体では個人を特定しにくいが、組み合わせると特定につながるもの）
    AGE = "AGE"                          # 年齢（45歳 / 30代 / 年齢：45）
    GENDER = "GENDER"                    # 性別（性別：女 / 45歳男性）
    COMPANY = "COMPANY"                  # 会社名・法人名（株式会社〇〇 / 〇〇(株)）
    CARD_EXPIRY = "CARD_EXPIRY"          # カードの有効期限（05/28）


# 指定したときだけ検出する種類
OPTIONAL_TYPES = frozenset({EntityType.AGE, EntityType.GENDER, EntityType.COMPANY, EntityType.CARD_EXPIRY})
# 既定で検出する種類
DEFAULT_TYPES = frozenset(EntityType) - OPTIONAL_TYPES


@dataclass(frozen=True)
class Entity:
    type: EntityType
    start: int  # 元テキストでの開始位置（文字単位）
    end: int    # 終了位置（この位置の文字は含まない）
    text: str
    score: float

    @property
    def length(self) -> int:
        return self.end - self.start

    def overlaps(self, other: "Entity") -> bool:
        return self.start < other.end and other.start < self.end
