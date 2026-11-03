# Kuronuri-kun (Japanese PII Masking)

**Author:** kuronurikun
**Version:** 0.1.0
**Type:** tool
**Source repository:** https://github.com/mamoruveilworks-hub/kuronurikun-dify-plugin

## Overview

Kuronuri-kun detects personal information in **Japanese text** and replaces it with placeholders such as `[PERSON_1]` before the text reaches an LLM. After the LLM answers, it restores the placeholders to the original values. The same person always gets the same placeholder, so the LLM can still follow who is who.

It recognizes Japanese-specific formats that general-purpose detectors often miss: names (with honorifics, job titles, field labels, and a dictionary of common names), addresses, phone numbers, email addresses, postal codes, dates of birth (including Japanese era dates), My Number, bank accounts, credit card numbers, driver's license numbers, passport numbers, basic pension numbers, and health insurance numbers.

```text
Input:   山田太郎様の電話は090-1234-5678です。
Masked:  [PERSON_1]様の電話は[PHONE_1]です。
Restored answer: 山田太郎様、090-1234-5678へ本日中にお電話いたします。
```

## Setup

1. Get a free API key (100,000 characters per month) at https://kuronurikun.com (no credit card required).
2. Install this plugin from the Dify Marketplace.
3. Open **Tools > Kuronuri-kun** and enter your API key (it starts with `pmk_`). The plugin checks the key without using your quota.

## Usage

The plugin provides two tools.

| Tool | Inputs | Outputs |
|---|---|---|
| Mask personal information (`mask_pii`) | `text`, `style` (tag / block / asterisk / redact), `extra_entities` (optional: AGE, GENDER, COMPANY, CARD_EXPIRY) | `masked_text`, `mapping_token`, `entity_count` |
| Restore personal information (`unmask_pii`) | `text`, `mapping_token` | `restored_text` |

### Example chatflow

```text
Start
  -> Mask personal information   (text = sys.query)
  -> LLM                         (user prompt = Mask.masked_text)
  -> Restore personal information (text = LLM.text, mapping_token = Mask.mapping_token)
  -> Answer                      (Restore.restored_text)
```

Tips:

- **Mask before the LLM.** Place the mask step in the workflow before the LLM node. Giving the tool to an agent is not enough, because the agent's LLM reads the original text before deciding to call the tool.
- **Do not enable LLM memory** in the chatflow, or earlier unmasked messages will be sent to the LLM.
- Ask the LLM in the system prompt to keep placeholders such as `[PERSON_1]` unchanged.
- Use the same API key for masking and restoring. A `mapping_token` expires after 24 hours.
- Detection is rule- and dictionary-based. It handles common formats well but may miss rare names; review important data by a human as well.

## Connection requirements

The plugin calls the HTTPS endpoint `https://kuronurikun.com` (`/v1/mask` and `/v1/unmask`). Your Dify instance must be able to reach this host.

## Pricing

Usage is counted by the number of characters masked; restoring is free. Free: 100,000 characters per month. Lite: 980 JPY per month for 1,000,000 characters. Pro: 4,980 JPY per month for 10,000,000 characters. See https://kuronurikun.com/#pricing

## Privacy

Text is processed in memory in the AWS Tokyo region and is not stored or logged. See [PRIVACY.md](PRIVACY.md).

## Support

- Website and API documentation: https://kuronurikun.com/docs
- Feedback (missed detections, feature requests): https://kuronurikun.com/feedback
- Contact: support@kuronurikun.com
