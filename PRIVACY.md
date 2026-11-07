# Privacy Policy

This plugin has two processing modes. You choose one in the plugin settings (**Where to process text**).

## Inside this Dify (default)

- Detection and masking run inside the plugin process on your Dify. **The text is not sent to any external service.**
- To count usage against your plan, the mask tool sends only your Kuronuri-kun API key and **the number of characters** to `https://kuronurikun.com/v1/usage`. No text, placeholders, or results are sent. Restoring makes no request.
- The plugin does not store or log the text.
- The `mapping_token` contains the original values (compressed and encoded, not encrypted). It is returned to your workflow as an output variable and is not sent anywhere. Pass it only to the restore step, not to an LLM.

## Kuronuri-kun API

In this mode the plugin sends the text you pass to its tools to the Kuronuri-kun API (`https://kuronurikun.com`), operated in Japan.

### What data is sent

- **Mask personal information**: the text you provide, the masking style, and the optional additional types.
- **Restore personal information**: the text you provide (for example, an LLM answer containing placeholders) and the `mapping_token`.
- Your Kuronuri-kun API key, sent in the `X-API-Key` header to authenticate the request.

### What is collected, stored, and logged

- The text is processed in memory and discarded after each request. It is **not stored** and is **not written to logs**.
- The mapping between placeholders and original values is encrypted (AES-256-GCM) and returned to you as the `mapping_token`. The service does **not retain** it. The token is bound to the API key that created it and expires after 24 hours.
- For billing and quota, the service records the number of characters processed per API key per month and the number of requests. Access logs (time, source IP address, path, status, latency) are kept for 14 days and do not contain the text.
- Your API key is stored by Dify as an encrypted credential.

### Where data is processed and third parties

All processing takes place on Amazon Web Services in the Tokyo region (ap-northeast-1). Data is not sold or shared with third parties, except as required by law. This plugin does not handle any purchases; plan sign-up happens on the kuronurikun.com website.

## Full policy and contact

- Full privacy policy (Japanese): https://kuronurikun.com/legal/privacy
- Contact: support@kuronurikun.com
