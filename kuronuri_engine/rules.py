# This file is copied from the Kuronuri-kun API (app/rules.py) by tools/sync_plugin_engine.py.
# Do not edit it here; edit the original and run the script again.
"""ルールベースの検出器群。

各検出器は (正規化済みテキスト) を受け取り、(type, start, end, score) の候補を返す。
位置は正規化前後で共通（normalize は1対1変換のため）。
"""

from __future__ import annotations

import re
from typing import Callable, Iterator

from . import names
from .entities import EntityType
from .validators import (
    digits_only,
    has_card_prefix,
    is_valid_date,
    is_valid_ipv4,
    is_valid_luhn,
    is_valid_my_number,
    to_gregorian_year,
)

Candidate = tuple[EntityType, int, int, float]
Detector = Callable[[str], Iterator[Candidate]]

KANJI = "㐀-䶿一-鿿々〆ヶ"
KATA = "ァ-ヺー"  # ァ〜ヺ と 長音
HIRA = "ぁ-ゖ"

# 前方の文脈に特定キーワードがあるか
def _has_context(text: str, start: int, end: int, before: re.Pattern, after: re.Pattern | None = None,
                 window_before: int = 20, window_after: int = 6) -> bool:
    if before.search(text[max(0, start - window_before):start]):
        return True
    if after is not None and after.search(text[end:end + window_after]):
        return True
    return False


# ---------------------------------------------------------------- メール
_EMAIL = re.compile(
    r"(?<![A-Za-z0-9._%+\-])[A-Za-z0-9._%+\-]+@[A-Za-z0-9\-]+(?:\.[A-Za-z0-9\-]+)*\.[A-Za-z]{2,}(?![A-Za-z0-9])"
)


def detect_email(t: str) -> Iterator[Candidate]:
    for m in _EMAIL.finditer(t):
        yield EntityType.EMAIL, m.start(), m.end(), 0.99


# ---------------------------------------------------------------- 電話番号
# 区切りは「-」「()」「の」（口語の「080の1234の5678」）。空白は「) 」の後だけ許可し、
# 隣り合う別の番号をつなげてしまわないようにする。
_PHONE = re.compile(r"(?<![\d\-+])(?:\+81[\- ]?)?\(?\d(?:\d|-|の|\) ?|\(){7,18}\d(?![\d\-])")
_PHONE_CTX = re.compile(r"(電話|TEL|Tel|tel|携帯|連絡先|☎|FAX|Fax|fax)")
_PHONE_SPACED = re.compile(
    r"(?<![\d\-+])(?P<cc>\+81 ?)?(?P<a>0?\d{1,4}) (?P<b>\d{1,4}) (?P<c>\d{4})(?![\d\-])"
)


def _looks_like_short_mobile(s: str, d: str) -> bool:
    """「090-1234-567」のような桁不足の携帯番号か。

    区切りがあれば先頭のかたまりで判断する（「06-0225-1234」は大阪の市外局番06なので固定電話）。
    """
    first = re.split(r"[\-()の ]", s.lstrip("("), maxsplit=1)[0]
    if first != s:
        return first in {"050", "060", "070", "080", "090"}
    return d[:3] in {"050", "060", "070", "080", "090"}


def detect_phone(t: str) -> Iterator[Candidate]:
    for m in _PHONE.finditer(t):
        s, start = m.group(), m.start()
        if s.startswith("(") and ")" not in s:
            # 「（090-1234-5678）」の開きかっこは番号を囲んでいるだけ。市外局番のかっこ「(03)1234-5678」とは違うので外す
            s, start = s[1:], start + 1
        d = digits_only(s)
        if s.startswith("+81"):
            d = "0" + d[2:].lstrip("0")
        if not d.startswith("0"):
            continue
        has_sep = any(c in s for c in "-()の")
        if len(d) == 11 and (d[:3] in {"070", "080", "090", "050"} or d.startswith("0800")):
            score = 0.95 if has_sep else 0.85
        elif len(d) == 10 and d.startswith("0120"):
            score = 0.9
        elif len(d) == 10 and d[1] != "0" and not _looks_like_short_mobile(s, d):
            # 固定電話。区切りなし10桁は他の番号と紛らわしいので文脈必須
            if has_sep:
                score = 0.9
            elif _has_context(t, start, m.end(), _PHONE_CTX, window_before=12):
                score = 0.85
            else:
                continue
        else:
            continue
        yield EntityType.PHONE, start, m.end(), score

    # スペース区切り（「090 1234 5678」）。隣り合う別の数字をつなげないよう、桁の並びを厳密に決める。
    #   携帯（050/070/080/090）3-4-4 … 形が特徴的なのでそのまま
    #   固定電話（合計10桁）           … 「電話」「TEL」などの言葉が近くにあるときだけ
    for m in _PHONE_SPACED.finditer(t):
        d = "".join(g for g in m.group("a", "b", "c") if g)
        if m.group("cc"):
            d = "0" + d.lstrip("0")
        has_ctx = _has_context(t, m.start(), m.end(), _PHONE_CTX, window_before=12)
        if len(d) == 11 and d[:3] in {"050", "070", "080", "090"} and len(m.group("b")) == 4:
            yield EntityType.PHONE, m.start(), m.end(), 0.9 if has_ctx else 0.85
        elif len(d) == 10 and d[1] != "0" and d[:3] not in {"050", "070", "080", "090"} and has_ctx:
            yield EntityType.PHONE, m.start(), m.end(), 0.85


# ---------------------------------------------------------------- 12桁番号（マイナンバー / 運転免許）
# 区切りは「なし」か「4-4-4で統一」のみ。「20261027-0001」のような番号を拾わないため
_TWELVE = re.compile(r"(?<![\d\-])\d{4}(?P<sep>[\- ]?)\d{4}(?P=sep)\d{4}(?![\d\-])")
_MYNUM_CTX = re.compile(r"(マイナンバー|個人番号)")
_LICENSE_CTX = re.compile(r"(免許)")


def detect_twelve_digit(t: str) -> Iterator[Candidate]:
    for m in _TWELVE.finditer(t):
        s, e = m.start(), m.end()
        if _has_context(t, s, e, _LICENSE_CTX, window_before=15):
            yield EntityType.DRIVERS_LICENSE, s, e, 0.97
            continue
        valid = is_valid_my_number(m.group())
        ctx = _has_context(t, s, e, _MYNUM_CTX, window_before=15)
        if valid and ctx:
            yield EntityType.MY_NUMBER, s, e, 0.99
        elif valid:
            yield EntityType.MY_NUMBER, s, e, 0.9
        elif ctx:
            # 検査数字が合わなくても、マイナンバーと明記されていれば伏せるべき
            yield EntityType.MY_NUMBER, s, e, 0.75


# ---------------------------------------------------------------- クレジットカード
_CARD = re.compile(r"(?<![\d\-])\d(?:[\- ]?\d){12,18}(?![\d\-])")
_CARD_CTX = re.compile(r"(カード|card|Card|CARD)")


def detect_credit_card(t: str) -> Iterator[Candidate]:
    for m in _CARD.finditer(t):
        s = m.group()
        if not is_valid_luhn(s):
            continue
        if has_card_prefix(s):
            yield EntityType.CREDIT_CARD, m.start(), m.end(), 0.95
        elif _has_context(t, m.start(), m.end(), _CARD_CTX, window_before=15):
            yield EntityType.CREDIT_CARD, m.start(), m.end(), 0.85


# ---------------------------------------------------------------- 郵便番号
_POSTAL_MARK = re.compile(r"〒 ?(\d{3}-?\d{4})(?![\d\-])")
_POSTAL = re.compile(r"(?<![\d\-])\d{3}-\d{4}(?![\d\-])")


def detect_postal(t: str) -> Iterator[Candidate]:
    for m in _POSTAL_MARK.finditer(t):
        yield EntityType.POSTAL_CODE, m.start(1), m.end(1), 0.99
    for m in _POSTAL.finditer(t):
        yield EntityType.POSTAL_CODE, m.start(), m.end(), 0.85


# ---------------------------------------------------------------- 生年月日
_ERA = r"(明治|大正|昭和|平成|令和|[MTSHR])"
_DATE_KANJI = re.compile(
    _ERA.replace("(", "(?P<era>", 1) + r"? ?"
    r"(?P<y>\d{1,4}|元) ?年 ?(?P<m>\d{1,2}) ?月 ?(?P<d>\d{1,2}) ?日"
)
_DATE_SEP = re.compile(
    r"(?<![\d.\-/])" + _ERA.replace("(", "(?P<era>", 1) + r"?\.?"
    r"(?P<y>\d{4}|\d{1,2})[/.\-](?P<m>\d{1,2})[/.\-](?P<d>\d{1,2})(?![\d.\-/])"
)
_DOB_BEFORE = re.compile(r"(生年月日|誕生日|生まれ|出生|DOB|[Bb]irth)")
_DOB_AFTER = re.compile(r"^ ?(生まれ|生|誕生)")


def detect_dob(t: str) -> Iterator[Candidate]:
    for pattern in (_DATE_KANJI, _DATE_SEP):
        for m in pattern.finditer(t):
            era, y = m.group("era"), m.group("y")
            if era is None and len(y) != 4:
                continue
            year = to_gregorian_year(era, y)
            if not is_valid_date(year, int(m.group("m")), int(m.group("d"))):
                continue
            if _has_context(t, m.start(), m.end(), _DOB_BEFORE, _DOB_AFTER):
                yield EntityType.DATE_OF_BIRTH, m.start(), m.end(), 0.9


# ---------------------------------------------------------------- 銀行口座
_BANK_NAME = rf"(?:ゆうちょ銀行|[{KANJI}{KATA}A-Za-z]{{1,12}}?(?:銀行|信用金庫|信金|信用組合|労働金庫|農業協同組合))"
_BRANCH = rf"(?:[{KANJI}{KATA}A-Za-z0-9]{{1,10}}?(?:支店|出張所|営業部))"
_ACCOUNT = re.compile(
    rf"(?:{_BANK_NAME} ?)?(?:{_BRANCH} ?)?"
    r"(?:(?:普通|当座|貯蓄|総合)(?:預金)? ?(?:口座)? ?(?:番号)?|口座番号) ?(?:は|:|：)? ?(?:No\.? ?)?\d{7}(?!\d)"
)
_YUCHO = re.compile(r"記号 ?(?:は|:)? ?1\d{4}[\- ]?(?:番号 ?(?:は|:)? ?)?\d{8}(?!\d)")


def detect_bank_account(t: str) -> Iterator[Candidate]:
    for m in _ACCOUNT.finditer(t):
        yield EntityType.BANK_ACCOUNT, m.start(), m.end(), 0.95
    for m in _YUCHO.finditer(t):
        yield EntityType.BANK_ACCOUNT, m.start(), m.end(), 0.95


# ---------------------------------------------------------------- IPアドレス
# 直前が英字（v1.2.3.4、ver1.2.3.4 など）のものはバージョン番号とみなして除外
_IPV4 = re.compile(r"(?<![\d.A-Za-z])(?:\d{1,3}\.){3}\d{1,3}(?![\d.])")


_VERSION_CTX = re.compile(r"(バージョン|[Vv]er\.?|[Vv]ersion|リリース|版)")


def detect_ip(t: str) -> Iterator[Candidate]:
    for m in _IPV4.finditer(t):
        if not is_valid_ipv4(m.group()):
            continue
        # 「バージョン1.2.3.4」「Ver 1.2.3.4」はバージョン番号
        if _has_context(t, m.start(), m.end(), _VERSION_CTX, window_before=8):
            continue
        yield EntityType.IP_ADDRESS, m.start(), m.end(), 0.8


# ---------------------------------------------------------------- 住所
PREFECTURES = (
    "北海道 青森県 岩手県 宮城県 秋田県 山形県 福島県 茨城県 栃木県 群馬県 埼玉県 千葉県 東京都 神奈川県 "
    "新潟県 富山県 石川県 福井県 山梨県 長野県 岐阜県 静岡県 愛知県 三重県 滋賀県 京都府 大阪府 兵庫県 "
    "奈良県 和歌山県 鳥取県 島根県 岡山県 広島県 山口県 徳島県 香川県 愛媛県 高知県 福岡県 佐賀県 長崎県 "
    "熊本県 大分県 宮崎県 鹿児島県 沖縄県"
).split()

# 住所の構成文字：漢字・カタカナ・数字・ハイフン。
# ひらがなは「さいたま市」「つくば市」のように市区町村名の一部のときだけ許す。
_ADDR_BODY = rf"(?:[{KANJI}{KATA}0-9\-]|[{HIRA}]{{1,6}}(?=[市区町村郡]))+"
_ADDR_PREF = re.compile(rf"(?:{'|'.join(PREFECTURES)}){_ADDR_BODY}")
# 都道府県なしの「横浜市中区本町1-2-3」型（番地まであるものに限定）
_ADDR_CITY = re.compile(rf"(?<![{KANJI}])[{KANJI}]{{1,5}}[市区町村]{_ADDR_BODY}")

# 住所の後ろにくっつきがちな語・住所ではない語の手前で切る
_ADDR_CUT = re.compile(r"(電話|TEL|携帯|メール|連絡先|郵便|〒|在住|在勤|在学|出身|付近|周辺|近辺|方面|生まれ|住所)")
_ADDR_LEAD = re.compile(r"^(現住所|住所|所在地|本籍地?)")


def _trim_address(t: str, start: int, end: int) -> tuple[int, int]:
    seg = t[start:end]
    lead = _ADDR_LEAD.match(seg)
    if lead:
        start += lead.end()
        seg = t[start:end]
    cut = _ADDR_CUT.search(seg)
    if cut and cut.start() > 0:
        end = start + cut.start()
    while end > start and t[end - 1] == "-":
        end -= 1
    return start, end


# 番地の後ろに続く建物名・部屋番号（「… 1-2-3 グランフロント大阪タワーA 10階」「… 201号室」）
_BUILDING_SUFFIX = (
    "ビル|マンション|ハイツ|コーポ|荘|タワー|レジデンス|アパート|ハウス|パレス|プラザ|ヒルズ|コート|テラス|"
    "メゾン|カーサ|ガーデン|館|棟|寮"
)
_ADDR_EXTRA = re.compile(
    rf" ?(?:[{KANJI}{KATA}A-Za-z0-9・\-]{{0,30}}(?:{_BUILDING_SUFFIX})[A-Za-z0-9\-]{{0,4}}"
    rf"|\d{{1,4}}(?:階|F|号室|号)|#\d{{1,4}})"
)


def _ends_with_town_number(body: str) -> bool:
    """都道府県なしで、市・区のあとに町名と番地の数字で終わるもの（「京都市左京区下鴨泉川町59」）。

    正規表現だと、長い漢字の連続で極端に遅くなるので、文字列の操作で判定する。
    """
    head = body.rstrip("0123456789")
    if len(head) == len(body) or not head or head[-1] == "-":
        return False
    return ("市" in head or "区" in head) and any(c in head for c in "町村通条丁")


def _extend_building(t: str, end: int) -> int:
    """番地の後ろに建物名・階・部屋番号が続いていれば、そこまで住所に含める（2つまで）。"""
    for _ in range(2):
        m = _ADDR_EXTRA.match(t, end)
        if not m or m.end() == end:
            break
        end = m.end()
    return end


def detect_address(t: str) -> Iterator[Candidate]:
    for m in _ADDR_PREF.finditer(t):
        s, e = _trim_address(t, m.start(), m.end())
        body = t[s:e]
        if not re.search("[市区町村郡]", body):
            continue  # 都道府県だけなら個人を特定しない
        has_number = bool(re.search(r"\d|丁目|番地|番|号", body))
        if has_number:
            e = _extend_building(t, e)
        yield EntityType.ADDRESS, s, e, 0.95 if has_number else 0.8
    for m in _ADDR_CITY.finditer(t):
        s, e = _trim_address(t, m.start(), m.end())
        body = t[s:e]
        if re.search(r"\d+(丁目|番|-)", body):
            yield EntityType.ADDRESS, s, _extend_building(t, e), 0.75
        elif _ends_with_town_number(body):
            yield EntityType.ADDRESS, s, _extend_building(t, e), 0.7


# ---------------------------------------------------------------- 個人識別符号（パスポート・基礎年金番号・健康保険）
# 個人情報保護法で、マイナンバーや運転免許証番号と同じ「個人識別符号」とされる番号。
# 番号の形だけでは商品コードなどと区別できないので、近くに手がかりの言葉があるときだけ伏せる。

_PASSPORT = re.compile(r"(?<![A-Za-z0-9])[A-Z]{2}\d{7}(?![A-Za-z0-9])")
_PASSPORT_CTX = re.compile(r"(旅券|パスポート|[Pp]assport|PASSPORT)")
_PENSION = re.compile(r"(?<![\d\-])\d{4}-?\d{6}(?![\d\-])")
_PENSION_CTX = re.compile(r"(基礎年金番号|年金番号|年金手帳)")
_INSURANCE_CTX = re.compile(r"(保険証|被保険者|健康保険|保険者番号|資格確認書)")
# 「記号 12345678 番号 01」「保険者番号：06123456」「枝番 00」
_INSURANCE_FIELD = re.compile(r"(?:保険者番号|記号|番号|枝番)(?: ?(?:[:：]|は)? ?)(?P<v>[0-9A-Za-z\-]{1,12})")


def detect_id_codes(t: str) -> Iterator[Candidate]:
    for m in _PASSPORT.finditer(t):
        if _has_context(t, m.start(), m.end(), _PASSPORT_CTX, window_before=20):
            yield EntityType.PASSPORT, m.start(), m.end(), 0.95
    for m in _PENSION.finditer(t):
        if _has_context(t, m.start(), m.end(), _PENSION_CTX, window_before=15):
            yield EntityType.PENSION_NUMBER, m.start(), m.end(), 0.95
    for ctx in _INSURANCE_CTX.finditer(t):
        # 手がかりの言葉から60文字以内の「記号」「番号」などの値を伏せる
        window_end = min(len(t), ctx.end() + 60)
        for m in _INSURANCE_FIELD.finditer(t, ctx.start(), window_end):
            if any(c.isdigit() for c in m.group("v")):
                yield EntityType.HEALTH_INSURANCE, m.start("v"), m.end("v"), 0.9


# ---------------------------------------------------------------- 氏名（ヒューリスティック）
_NAME = rf"(?:[{KANJI}]{{1,4}} ?[{KANJI}]{{1,4}}|[{KATA}]{{2,10}}(?:[ ・][{KATA}]{{2,10}})?)"
# 氏名が続く項目名。長いものを先に並べる（「契約者名」を「契約者」+「名…」と読まないように）
_NAME_KEYS = (
    "契約者名|申込者名|申込人名?|顧客名|お客様名|お客さま名|利用者名|会員名|受取人名?|依頼人名?|名義人|"
    "担当者名|ご担当者様?|ご担当|担当者|宛名|患者名|患者|"
    r"氏名\((?:漢字|カナ|フリガナ)\)|カナ氏名|お名前|氏名|名前|名義|契約者|申込者"
)
_NAME_BY_KEYWORD = re.compile(
    rf"(?:{_NAME_KEYS})(?:は|:|：| )? ?(?P<name>{_NAME})"
)
# 読みがな欄（ひらがなでも書かれる）
_READING_BY_KEYWORD = re.compile(
    rf"(?:フリガナ|ふりがな|よみがな|ヨミガナ|カナ)(?:は|:|：| )? ?(?P<name>[{KATA}]{{2,10}}(?: [{KATA}]{{2,10}})?|[{HIRA}]{{2,10}} [{HIRA}]{{2,10}})"
)
# 敬称。「様式」「様子」「様相」「様態」は敬称ではない
_HONORIFIC = r"(?:様(?![式子相態])|さん|ちゃん|くん|君|氏|殿|先生)"
_NAME_BY_HONORIFIC = re.compile(
    rf"(?<![{KANJI}{KATA}])(?P<name>[{KANJI}]{{2,4}} ?[{KANJI}]{{0,3}}|[{KATA}]{{2,8}})(?={_HONORIFIC})"
)
# 読みがなを括弧で添えた氏名：「佐藤 花子（さとう はなこ）様」（括弧は正規化で半角になる）
_NAME_WITH_READING = re.compile(
    rf"(?<![{KANJI}{KATA}])(?P<name>[{KANJI}]{{1,4}} ?[{KANJI}]{{1,4}})\((?P<reading>[{HIRA}{KATA} ・]{{2,20}})\)(?={_HONORIFIC})"
)
# 役職付き：「鈴木部長」「伊藤課長」。「営業部長」のような部署名＋役職と区別するため、部署によく使う語は除く
_TITLES = (
    "取締役|執行役員|会長|社長|副社長|専務|常務|本部長|部長|次長|課長|係長|主任|室長|院長|"
    "教授|准教授|講師|弁護士|税理士|会計士|司法書士|行政書士"
)
_NAME_BY_TITLE = re.compile(
    rf"(?<![{KANJI}{KATA}])(?P<name>[{KANJI}]{{2,4}})(?=(?:{_TITLES})(?:代理|補佐)?(?![{KANJI}]))"
)
_NOT_NAME_BEFORE_TITLE = {
    "営業", "総務", "人事", "経理", "財務", "法務", "広報", "企画", "開発", "技術", "製造", "品質", "購買",
    "事業", "本部", "支店", "支社", "代表", "副", "専務", "常務", "取締", "執行", "統括", "担当", "事務",
    "情報", "経営", "管理", "業務", "生産", "物流", "販売", "商品", "研究", "設計", "システム", "総合",
    "学部", "大学", "病院", "医院", "学校", "銀行", "会社", "当社", "弊社", "貴社", "御社", "同社", "新任",
    "前任", "後任", "歴代", "現", "元", "前", "新", "各", "同", "名誉", "特任", "客員", "顧問", "相談",
    "推進", "戦略", "改革", "対策", "運営", "運用", "保守", "調達", "資材", "監査", "審査", "渉外", "国際",
    "海外", "国内", "地域", "広告", "宣伝", "編集", "制作", "教育", "研修", "採用", "労務", "庶務", "秘書",
    "社外", "社内", "常勤", "非常勤", "臨時", "代理", "補佐", "準備", "設立", "創業", "初代", "二代目",
    "工場", "研究所", "本社", "営業所", "出張所", "店舗", "病棟", "医局", "外来", "診療", "看護",
}
# 敬称がつくが人名ではない語
_NOT_NAME = {
    "お客", "客", "皆", "皆々", "御社", "貴社", "弊社", "先方", "奥", "神", "仏", "王", "本人", "ご本人",
    "各位", "お子", "親御", "利用者", "会員", "担当", "担当者", "病院", "医師", "患者", "生徒", "児童",
    "学生", "家族", "皆様", "上", "殿", "お父", "お母", "お兄", "お姉", "旦那", "奥方", "ホテル", "チーム",
    "スタッフ", "メンバー", "ユーザー", "ゲスト", "オーナー", "カスタマー", "サポート", "センター",
    # 「氏名：未記入」のように、氏名欄に入りがちな人名以外の語
    "未記入", "記入", "不明", "未定", "空欄", "非公開", "省略", "必須", "任意", "以下", "下記", "上記",
    "別紙", "同上", "変更", "確認", "入力", "なし", "ナシ", "無し", "未入力", "記載", "要確認",
}
_NOT_NAME_SUFFIX = tuple("者長員社部課会係局省庁所院校店様方人")


def _plausible_name(name: str) -> bool:
    n = name.strip()
    return n not in _NOT_NAME and not n.endswith(_NOT_NAME_SUFFIX)


# ---------------------------------------------------------------- 氏名（辞書＋文脈）
# 敬称や項目名がない名前（「渡邉亮です。」、署名欄の「山田 太郎」）を、よくある姓・名の辞書で見つける。
#   姓＋名（2文字以上の名）               … 文中のどこでも
#   姓＋名（1文字の名：「正」「明」など） … 普通の言葉と紛らわしいので、強い文脈があるときだけ
#   姓だけ                                … 「〇〇です」「〇〇と申します」「担当の〇〇」などの文脈があるときだけ
#   ローマ字（Taro Yamada / YAMADA Taro）… どちらかが辞書のローマ字の姓
_KANJI_RUN = re.compile(rf"[{KANJI}]+(?: [{KANJI}]+)?")
_SELF_INTRO_AFTER = re.compile(r"(?:です|と申します|でございます|と言います|といいます|より|拝)")
_SELF_INTRO_BEFORE = re.compile(r"(?:担当の|担当[:：] ?|担当 |私[、 ]?|わたくし[、 ]?|当方[、の]?|差出人[:：] ?|送信者[:：] ?)$")
_ROMAJI_NAME = re.compile(r"(?<![A-Za-z])([A-Z][a-z]{1,11}|[A-Z]{2,12}) ([A-Z][a-z]{1,11}|[A-Z]{2,12})(?![A-Za-z])")
# 「Suzuki Motor」「Honda Civic」のような会社名・商品名・地名の語
_ROMAJI_NOT_NAME = frozenset(w.lower() for w in """
Motor Motors Corporation Corp Inc Co Ltd Group Bank Holdings Electric Industries Industry Trading Securities
Pharmaceutical Shoji Sangyo Kogyo Seisakusho Castle Station Line University Hospital Park Garden Street City
Hall Building Tower Japan Tokyo Osaka Kyoto Civic Accord Fit Jimny Swift Prius Corolla Rice Ramen Sushi
""".split())
# 丁寧な名乗り（「〇〇の佐々木でございます」）。会社名などの後に「の」が来ても名前とみなす
_POLITE_INTRO_AFTER = re.compile(r"(?:と申します|でございます)")


def _split_full_name(run: str) -> tuple[str, str] | None:
    """「山田太郎」「山田 太郎」を（姓, 名）に分ける。辞書の姓＋名で全体がちょうど埋まるときだけ。"""
    if " " in run:
        sur, giv = run.split(" ", 1)
        ok = (sur in names.SURNAMES or sur in names.SHORT_SURNAMES) and giv in names.GIVEN_NAMES
        return (sur, giv) if ok else None
    for i in range(min(4, len(run) - 1), 0, -1):  # 長い姓を優先（「佐々木」を「佐」で切らない）
        sur, giv = run[:i], run[i:]
        if (sur in names.SURNAMES or sur in names.SHORT_SURNAMES) and giv in names.GIVEN_NAMES:
            return sur, giv
    return None


def _intro_context(t: str, start: int, end: int) -> bool:
    """名乗りの文脈か（「〇〇です」「担当の〇〇」など）。"""
    if _SELF_INTRO_AFTER.match(t, end):
        before = t[max(0, start - 8):start]
        if start == 0 or t[start - 1] in "\n。、 「(（" or _SELF_INTRO_BEFORE.search(before):
            return True
    return bool(_SELF_INTRO_BEFORE.search(t[max(0, start - 8):start]))


def _strong_context(t: str, start: int, end: int) -> bool:
    """名乗りの文脈か、行にその名前しかない（署名欄など）か。"""
    if _intro_context(t, start, end):
        return True
    line_start = t.rfind("\n", 0, start) + 1
    line_end = t.find("\n", end)
    line_end = len(t) if line_end == -1 else line_end
    return t[line_start:start].strip() == "" and t[end:line_end].strip() == ""


def detect_person_by_dictionary(t: str) -> Iterator[Candidate]:
    for m in _KANJI_RUN.finditer(t):
        run, s, e = m.group(), m.start(), m.end()
        if len(run) > 9:
            continue
        full = _split_full_name(run)
        if full:
            sur, giv = full
            if len(giv) >= 2:
                yield EntityType.PERSON, s, e, 0.75 if len(sur) >= 2 else 0.7
            elif _strong_context(t, s, e):
                yield EntityType.PERSON, s, e, 0.7
            continue
        if " " not in run and (run in names.SURNAMES or run in names.SHORT_SURNAMES):
            polite = _POLITE_INTRO_AFTER.match(t, e) and s > 0 and t[s - 1] == "の"
            if polite or _intro_context(t, s, e):
                yield EntityType.PERSON, s, e, 0.7 if len(run) >= 2 else 0.6
    for m in _ROMAJI_NAME.finditer(t):
        a, b = m.group(1).lower(), m.group(2).lower()
        if (a in names.ROMAJI_SURNAMES) == (b in names.ROMAJI_SURNAMES):
            continue  # 片方だけが姓のときに限る
        if a in _ROMAJI_NOT_NAME or b in _ROMAJI_NOT_NAME:
            continue
        yield EntityType.PERSON, m.start(), m.end(), 0.7


def detect_person(t: str) -> Iterator[Candidate]:
    for m in _NAME_BY_KEYWORD.finditer(t):
        if _plausible_name(m.group("name")):
            yield EntityType.PERSON, m.start("name"), m.end("name"), 0.85
    for m in _READING_BY_KEYWORD.finditer(t):
        if _plausible_name(m.group("name")):
            yield EntityType.PERSON, m.start("name"), m.end("name"), 0.8
    for m in _NAME_WITH_READING.finditer(t):
        if _plausible_name(m.group("name")):
            yield EntityType.PERSON, m.start("name"), m.end("name"), 0.8
            yield EntityType.PERSON, m.start("reading"), m.end("reading"), 0.8
    for m in _NAME_BY_TITLE.finditer(t):
        name = m.group("name")
        if name not in _NOT_NAME_BEFORE_TITLE and not name.endswith(tuple(_NOT_NAME_BEFORE_TITLE)) and _plausible_name(name):
            yield EntityType.PERSON, m.start("name"), m.end("name"), 0.65
    for m in _NAME_BY_HONORIFIC.finditer(t):
        name = m.group("name")
        if _plausible_name(name):
            is_kata = re.fullmatch(f"[{KATA}]+", name) is not None
            yield EntityType.PERSON, m.start("name"), m.end("name"), 0.6 if is_kata else 0.7


# ================================================================ オプションの種類
# 既定では使われない（engine.detect で指定されたときだけ候補に残る）。

# ---------------------------------------------------------------- 年齢
_AGE_STOP = r"(?!\d|以上|以下|未満|超|から|まで|以降|以前)"
_AGE = re.compile(rf"(?<!\d)(?:満 ?)?(?P<n>\d{{1,3}}) ?(?:歳|才){_AGE_STOP}")
_AGE_BY_KEYWORD = re.compile(r"年齢 ?(?:は|:)? ?(?P<n>\d{1,3})(?: ?(?:歳|才))?(?!\d)")
# 「30代」「20代前半」（「10代目」「代表」「代金」などは除外）
_AGE_DECADE = re.compile(r"(?<!\d)[1-9]0 ?代(?:前半|後半|半ば)?(?![目表理金替わ])")


def detect_age(t: str) -> Iterator[Candidate]:
    for m in _AGE.finditer(t):
        if int(m.group("n")) <= 120:
            yield EntityType.AGE, m.start(), m.end(), 0.85
    for m in _AGE_BY_KEYWORD.finditer(t):
        if int(m.group("n")) <= 120:
            yield EntityType.AGE, m.start("n"), m.end(), 0.9
    for m in _AGE_DECADE.finditer(t):
        yield EntityType.AGE, m.start(), m.end(), 0.75


# ---------------------------------------------------------------- 性別
_GENDER_WORD = r"(?:男性|女性|男子|女子|男(?![性子])|女(?![性子]))"
_GENDER_BY_KEYWORD = re.compile(
    r"性別 ?(?:は|:)? ?(?P<g>男性|女性|男|女|その他|不明|回答しない|[MF](?![A-Za-z])|male|female|Male|Female)"
)
# 年齢と並んで書かれた性別（「45歳男性」「30代の女性」「女性、45歳」）
_GENDER_AFTER_AGE = re.compile(rf"(?:歳|才|代|前半|後半)(?:の)? ?(?P<g>{_GENDER_WORD})")
_GENDER_BEFORE_AGE = re.compile(rf"(?P<g>{_GENDER_WORD})[、, ]?(?:満 ?)?\d{{1,3}} ?(?:歳|才|代)")


def detect_gender(t: str) -> Iterator[Candidate]:
    for pattern, score in ((_GENDER_BY_KEYWORD, 0.95), (_GENDER_AFTER_AGE, 0.85), (_GENDER_BEFORE_AGE, 0.85)):
        for m in pattern.finditer(t):
            yield EntityType.GENDER, m.start("g"), m.end("g"), score


# ---------------------------------------------------------------- 会社名
_CORP_FORM = (
    r"(?:株式会社|有限会社|合同会社|合資会社|合名会社|一般社団法人|一般財団法人|公益社団法人|公益財団法人|"
    r"医療法人(?:社団|財団)?|社会福祉法人|学校法人|宗教法人|特定非営利活動法人|NPO法人)"
)
_CORP_ABBR = r"(?:\(株\)|\(有\)|\(合\)|㈱|㈲)"
# 社名に使われる文字。ひらがなは助詞（の・と・は等）との区別がつかないので含めない
_CORP_NAME = rf"[{KANJI}{KATA}A-Za-z0-9&・.\-]{{1,25}}"
_COMPANY_PREFIX = re.compile(rf"(?:{_CORP_FORM}|{_CORP_ABBR}) ?{_CORP_NAME}")
_COMPANY_SUFFIX = re.compile(rf"(?<![{KANJI}{KATA}A-Za-z0-9&・])[{KANJI}{KATA}A-Za-z0-9&・.\-]{{1,25}}?(?:{_CORP_FORM}|{_CORP_ABBR})")
# 社名の前にくっつきがちな語（「弊社」「当社は」の「社」など）を除く
_COMPANY_LEAD = re.compile(r"^(?:弊社|当社|御社|貴社|同社|各社|勤務先|所属|会社名|社名|取引先|顧客|宛先)")


_CORP_NAME_TAIL = re.compile(rf"[{KANJI}{KATA}A-Za-z0-9&・.\-]+$")
# 前置型（株式会社〇〇）の社名の後ろにくっつきがちな語。ここで社名を切る
_CORP_CUT = re.compile(
    r"(勤務|在籍|所属|入社|退社|退職|出向|御中|様|殿|宛|代表|社長|会長|取締役|役員|部長|課長|係長|主任|社員|担当|"
    r"営業|総務|経理|人事|開発|本社|本店|支社|支店|営業所|事業部|事業所|工場|部|課|室|グループ|チーム)"
)


def detect_company(t: str) -> Iterator[Candidate]:
    for m in _COMPANY_PREFIX.finditer(t):
        # 「ABC(株)営業部」のように法人格の前に社名があるなら後置型なので、前置型としては扱わない
        before = _CORP_NAME_TAIL.search(t[max(0, m.start() - 25):m.start()])
        if before and _COMPANY_LEAD.sub("", before.group()):
            continue
        form = re.match(rf"(?:{_CORP_FORM}|{_CORP_ABBR}) ?", t[m.start():m.end()])
        name_start = m.start() + form.end()
        cut = _CORP_CUT.search(t, name_start + 1, m.end())  # 社名の1文字目では切らない
        end = cut.start() if cut else m.end()
        yield EntityType.COMPANY, m.start(), end, 0.9
    for m in _COMPANY_SUFFIX.finditer(t):
        s = m.start()
        lead = _COMPANY_LEAD.match(t[s:m.end()])
        if lead:
            s += lead.end()
        # 「株式会社」の前に社名がない（法人格だけ）のは対象外
        if re.fullmatch(f"{_CORP_FORM}|{_CORP_ABBR}", t[s:m.end()]):
            continue
        yield EntityType.COMPANY, s, m.end(), 0.85


# ---------------------------------------------------------------- カードの有効期限
_EXPIRY_VALUE = r"(?P<v>(?:0[1-9]|1[0-2]) ?/ ?(?:20)?\d{2}|20\d{2} ?年 ?(?:0?[1-9]|1[0-2]) ?月|(?:0?[1-9]|1[0-2]) ?月 ?/ ?\d{2} ?年)"
_EXPIRY_BY_KEYWORD = re.compile(
    rf"(?:有効期限|有効期間|Exp(?:iry|iration|ires)?\.?|EXP\.?|VALID THRU|Valid Thru|GOOD THRU)"
    rf"[^\d\n]{{0,6}}?{_EXPIRY_VALUE}(?![\d/])"
)
# キーワードがなくても、カード番号の近くにある「MM/YY」は有効期限とみなす
_EXPIRY_BARE = re.compile(r"(?<![\d/])(?P<v>(?:0[1-9]|1[0-2])/\d{2})(?![\d/:])")
_EXPIRY_CARD_CTX = re.compile(r"カード|card|Card|CARD|\d{4}[\- ]?\d{4}[\- ]?\d{4}[\- ]?\d{1,4}")


def detect_card_expiry(t: str) -> Iterator[Candidate]:
    for m in _EXPIRY_BY_KEYWORD.finditer(t):
        yield EntityType.CARD_EXPIRY, m.start("v"), m.end("v"), 0.95
    for m in _EXPIRY_BARE.finditer(t):
        if _has_context(t, m.start(), m.end(), _EXPIRY_CARD_CTX, window_before=40):
            yield EntityType.CARD_EXPIRY, m.start("v"), m.end("v"), 0.75


from .table import detect_table  # noqa: E402

DETECTORS: list[Detector] = [
    detect_table,
    detect_email,
    detect_phone,
    detect_twelve_digit,
    detect_credit_card,
    detect_postal,
    detect_dob,
    detect_bank_account,
    detect_ip,
    detect_id_codes,
    detect_address,
    detect_person,
    detect_person_by_dictionary,
    detect_age,
    detect_gender,
    detect_company,
    detect_card_expiry,
]
