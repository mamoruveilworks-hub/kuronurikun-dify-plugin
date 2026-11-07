"""Tests for the Kuronuri-kun Dify plugin. HTTP calls are mocked; no network is used.

Run from the plugin directory:
    pip install -r requirements.txt pytest
    python -m pytest tests
"""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from dify_plugin.entities.tool import ToolRuntime  # noqa: E402

from tools import client  # noqa: E402
from tools.mask_pii import MaskPiiTool, parse_extra  # noqa: E402
from tools.unmask_pii import UnmaskPiiTool  # noqa: E402


class FakeResponse:
    def __init__(self, status, body):
        self.status_code = status
        self._body = body
        self.text = str(body)

    def json(self):
        return self._body


@pytest.fixture
def calls(monkeypatch):
    sent = []
    replies = []

    def fake_post(url, json, headers, timeout):
        sent.append({"url": url, "json": json, "headers": headers})
        return replies.pop(0)

    monkeypatch.setattr(client.requests, "post", fake_post)
    return sent, replies


def _tool(cls, credentials=None):
    creds = {"api_key": "pmk_test"} if credentials is None else credentials
    return cls(runtime=ToolRuntime(credentials=creds, user_id="u", session_id="s"), session=None)


def _variables(messages):
    out = {}
    for m in messages:
        name = getattr(m.message, "variable_name", None)
        if name:
            out[name] = m.message.variable_value
    return out


def test_mask_returns_variables(calls):
    sent, replies = calls
    replies.append(FakeResponse(200, {
        "masked_text": "[PERSON_1]様の電話は[PHONE_1]",
        "mapping_token": "pm1.tok",
        "entities": [{"type": "PERSON"}, {"type": "PHONE"}],
    }))
    msgs = list(_tool(MaskPiiTool).invoke({"text": "山田太郎様の電話は090-1234-5678", "extra_entities": "age, company"}))
    assert _variables(msgs) == {
        "masked_text": "[PERSON_1]様の電話は[PHONE_1]", "mapping_token": "pm1.tok", "entity_count": 2,
    }
    assert sent[0]["url"] == "https://kuronurikun.com/v1/mask"
    assert sent[0]["headers"]["X-API-Key"] == "pmk_test"
    assert sent[0]["json"] == {"text": "山田太郎様の電話は090-1234-5678", "style": "tag", "extra_entities": ["AGE", "COMPANY"]}


def test_mask_empty_text_makes_no_request(calls):
    sent, _ = calls
    msgs = list(_tool(MaskPiiTool).invoke({"text": ""}))
    assert _variables(msgs)["masked_text"] == "" and sent == []


def test_unmask(calls):
    sent, replies = calls
    replies.append(FakeResponse(200, {"text": "山田太郎様、承知しました。"}))
    msgs = list(_tool(UnmaskPiiTool).invoke({"text": "[PERSON_1]様、承知しました。", "mapping_token": "pm1.tok"}))
    assert _variables(msgs) == {"restored_text": "山田太郎様、承知しました。"}
    assert sent[0]["json"] == {"text": "[PERSON_1]様、承知しました。", "mapping_token": "pm1.tok"}


def test_unmask_without_token_returns_text_unchanged(calls):
    sent, _ = calls
    msgs = list(_tool(UnmaskPiiTool).invoke({"text": "abc", "mapping_token": ""}))
    assert _variables(msgs) == {"restored_text": "abc"} and sent == []


def test_unmask_strips_spaces_around_token(calls):
    sent, replies = calls
    replies.append(FakeResponse(200, {"text": "ok"}))
    list(_tool(UnmaskPiiTool).invoke({"text": "[PERSON_1]", "mapping_token": " pm1.tok\n"}))
    assert sent[0]["json"]["mapping_token"] == "pm1.tok"


def test_unmask_wrong_variable_explains_without_request(calls):
    sent, _ = calls
    with pytest.raises(client.KuronurikunError, match="mapping_token variable of the mask node"):
        list(_tool(UnmaskPiiTool).invoke({"text": "x", "mapping_token": "[PERSON_1]様の電話は"}))
    assert sent == []


@pytest.mark.parametrize("status,needle", [(401, "Invalid API key"), (403, "different API key"), (429, "limit")])
def test_errors_are_readable(calls, status, needle):
    _, replies = calls
    replies.append(FakeResponse(status, {"detail": "x"}))
    with pytest.raises(client.KuronurikunError, match=needle):
        list(_tool(MaskPiiTool).invoke({"text": "abc"}))


def test_parse_extra():
    assert parse_extra("age, Gender、UNKNOWN") == ["AGE", "GENDER"]
    assert parse_extra(None) == []


# ---------------------------------------------------------------- local mode (text stays in Dify)

LOCAL = {"mode": "local", "api_key": "pmk_test"}


@pytest.fixture
def usage_ok(calls):
    """Every request in local mode must be /v1/usage with the character count only."""
    sent, replies = calls
    for _ in range(5):
        replies.append(FakeResponse(200, {"allowed": True}))
    yield sent
    for request in sent:
        assert request["url"] == "https://kuronurikun.com/v1/usage"
        assert set(request["json"]) == {"characters"}


def test_local_mask_and_unmask_round_trip(usage_ok):
    text = "山田太郎様の電話は090-1234-5678です。山田様によろしく。"
    out = _variables(list(_tool(MaskPiiTool, LOCAL).invoke({"text": text})))
    assert out["masked_text"] == "[PERSON_1]様の電話は[PHONE_1]です。[PERSON_2]様によろしく。"
    assert out["mapping_token"].startswith("pml1.") and out["entity_count"] >= 2
    assert usage_ok == [{"url": "https://kuronurikun.com/v1/usage", "json": {"characters": len(text)},
                         "headers": usage_ok[0]["headers"]}]
    assert usage_ok[0]["headers"]["X-API-Key"] == "pmk_test"

    answer = "[PERSON_1]様、[PHONE_1]へ折り返します。"
    restored = _variables(list(_tool(UnmaskPiiTool, LOCAL).invoke(
        {"text": answer, "mapping_token": " " + out["mapping_token"] + "\n"}
    )))["restored_text"]
    assert restored == "山田太郎様、090-1234-5678へ折り返します。"
    assert len(usage_ok) == 1  # restoring is free and makes no request


def test_local_json_output_has_no_original_values(usage_ok):
    msgs = list(_tool(MaskPiiTool, LOCAL).invoke({"text": "山田太郎様の電話は090-1234-5678"}))
    blobs = [m.message.json_object for m in msgs if getattr(m.message, "json_object", None) is not None]
    assert blobs and "山田太郎" not in str(blobs) and "090-1234-5678" not in str(blobs)


def test_local_block_style_has_no_token(usage_ok):
    out = _variables(list(_tool(MaskPiiTool, LOCAL).invoke({"text": "電話は090-1234-5678", "style": "block"})))
    assert "■" in out["masked_text"] and out["mapping_token"] == ""


def test_local_extra_entities(usage_ok):
    out = _variables(list(_tool(MaskPiiTool, LOCAL).invoke({"text": "山田太郎様（35歳）", "extra_entities": "age"})))
    assert "35歳" not in out["masked_text"]


def test_local_over_quota_stops_before_masking(calls):
    sent, replies = calls
    replies.append(FakeResponse(429, {"detail": "over"}))
    with pytest.raises(client.KuronurikunError, match="limit"):
        list(_tool(MaskPiiTool, LOCAL).invoke({"text": "山田太郎様"}))
    assert sent[0]["json"] == {"characters": 5}


def test_local_without_key_is_explained(calls):
    sent, _ = calls
    with pytest.raises(client.KuronurikunError, match="API key is not set"):
        list(_tool(MaskPiiTool, {"mode": "local"}).invoke({"text": "山田太郎様"}))
    assert sent == []


def test_local_too_long_text_sends_nothing(calls):
    sent, _ = calls
    with pytest.raises(client.KuronurikunError, match="too long"):
        list(_tool(MaskPiiTool, LOCAL).invoke({"text": "あ" * 100_001}))
    assert sent == []


def test_local_broken_token_is_explained(calls):
    sent, _ = calls
    with pytest.raises(client.KuronurikunError, match="broken"):
        list(_tool(UnmaskPiiTool, LOCAL).invoke({"text": "x", "mapping_token": "pml1.%%%"}))
    assert sent == []


def test_api_token_still_restored_through_api_in_local_mode(calls):
    # A token made in API mode (pm1.) is restored through the API even after switching to local mode.
    sent, replies = calls
    replies.append(FakeResponse(200, {"text": "ok"}))
    list(_tool(UnmaskPiiTool, LOCAL).invoke({"text": "x", "mapping_token": "pm1.tok"}))
    assert sent[0]["url"] == "https://kuronurikun.com/v1/unmask"


def test_mode_of_keeps_old_installs_on_the_api():
    from tools.local import mode_of

    assert mode_of({"api_key": "pmk_x"}) == "api"  # installed with 0.1.0: no mode setting
    assert mode_of({"mode": "local", "api_key": "pmk_x"}) == "local"
    assert mode_of({"mode": "api", "api_key": "pmk_x"}) == "api"


def test_provider_requires_key(calls):
    from dify_plugin.errors.tool import ToolProviderCredentialValidationError

    from provider.kuronurikun import KuronurikunProvider

    with pytest.raises(ToolProviderCredentialValidationError):
        KuronurikunProvider()._validate_credentials({"mode": "local"})
