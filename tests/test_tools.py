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


def _tool(cls):
    return cls(runtime=ToolRuntime(credentials={"api_key": "pmk_test"}, user_id="u", session_id="s"), session=None)


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
