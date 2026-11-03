# 個人情報黒塗りくん

**作者：** kuronurikun
**バージョン：** 0.1.0
**種類：** ツール
**ソース：** https://github.com/mamoruveilworks-hub/kuronurikun-dify-plugin

## 概要

日本語の文章から個人情報を見つけて `[PERSON_1]` のような記号に置き換え、LLMに渡す前に伏せます。LLMの回答に入った記号は、元の名前や番号に戻せます。同じ人には同じ記号が付くので、LLMは「誰が誰か」を区別したまま文章を理解できます。

氏名（敬称・役職・項目名・よくある姓名の辞書）、住所、電話番号、メールアドレス、郵便番号、生年月日（和暦を含む）、マイナンバー、口座番号、クレジットカード番号、運転免許証番号、パスポート番号、基礎年金番号、保険証の番号など、日本の書き方に合わせて見つけます。

```text
入力：山田太郎様の電話は090-1234-5678です。
伏せた文章：[PERSON_1]様の電話は[PHONE_1]です。
元に戻した回答：山田太郎様、090-1234-5678へ本日中にお電話いたします。
```

## 設定

1. https://kuronurikun.com で、無料のAPIキー（月10万文字まで）を発行します。クレジットカードは不要です。
2. Difyのマーケットプレイスから、このプラグインをインストールします。
3. 「ツール → 個人情報黒塗りくん」を開き、APIキー（`pmk_` で始まる値）を入れます。キーの確認では文字数を消費しません。

## 使い方

| ツール | 入力 | 出力 |
|---|---|---|
| 個人情報を伏せる（`mask_pii`） | `text`、`style`（tag / block / asterisk / redact）、`extra_entities`（任意：AGE, GENDER, COMPANY, CARD_EXPIRY） | `masked_text`、`mapping_token`、`entity_count` |
| 個人情報を元に戻す（`unmask_pii`） | `text`、`mapping_token` | `text` |

### チャットフローの例

```text
開始
  → 個人情報を伏せる   （text = sys.query）
  → LLM               （ユーザーのプロンプト = 伏せる.masked_text）
  → 個人情報を元に戻す （text = LLM.text、mapping_token = 伏せる.mapping_token）
  → 回答               （元に戻す.text）
```

注意：

- **伏せるのはLLMの前に。** ワークフローの順番として、LLMのブロックより前に置いてください。エージェントにツールとして渡すだけでは、ツールを呼ぶ前に元の文章がLLMに届いてしまいます。
- チャットフローでは、LLMの**会話の記憶（メモリ）をオンにしない**でください。過去の元の文章がLLMに渡ります。
- システムプロンプトで、`[PERSON_1]` などの記号を書き換えないようLLMに指示してください。
- 伏せるときと元に戻すときは、同じAPIキーを使ってください。`mapping_token` は24時間で無効になります。
- ルールと辞書で判定しているので、珍しい名前などは見逃すことがあります。大切なデータでは、人の目での確認と組み合わせてください。

## 接続先

`https://kuronurikun.com`（`/v1/mask` と `/v1/unmask`）にHTTPSで接続します。

## 料金

伏せた文字数で数えます（元に戻す処理は数えません）。Free：月10万文字まで無料。Lite：月980円で100万文字。Pro：月4,980円で1,000万文字。詳しくは https://kuronurikun.com/#pricing

## プライバシー

文章はAWSの東京リージョンでメモリ上で処理し、保存もログへの記録もしません。詳しくは [PRIVACY.md](../PRIVACY.md) と https://kuronurikun.com/legal/privacy をご覧ください。

## お問い合わせ

- APIドキュメント：https://kuronurikun.com/docs
- 見逃しの報告・ご要望：https://kuronurikun.com/feedback
- メール：support@kuronurikun.com
