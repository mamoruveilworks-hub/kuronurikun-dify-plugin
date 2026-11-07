"""Local processing: detect and mask personal information inside the plugin.

The text never leaves Dify. The mask tool only reports the number of characters to the Kuronuri-kun API
(/v1/usage) to count usage against the plan. The detection engine in kuronuri_engine/ is the same one
the Kuronuri-kun API uses.
"""

from __future__ import annotations

import base64
import json
import zlib
from typing import Any

import kuronuri_engine as engine

MAX_TEXT_LENGTH = 100_000
LOCAL_TOKEN_PREFIX = "pml1."
API_TOKEN_PREFIX = "pm1."

MODE_LOCAL = "local"
MODE_API = "api"


class LocalError(ValueError):
    """A problem with the input, with a message for the user."""


def mode_of(credentials: dict[str, Any]) -> str:
    """Where to process text. Installs from version 0.1.0 have no mode setting, so they keep using the API."""
    mode = (credentials or {}).get("mode")
    return mode if mode in (MODE_LOCAL, MODE_API) else MODE_API


def _encode(mapping: dict[str, str]) -> str:
    raw = zlib.compress(json.dumps({"m": mapping}, ensure_ascii=False).encode())
    return LOCAL_TOKEN_PREFIX + base64.urlsafe_b64encode(raw).rstrip(b"=").decode()


def _decode(token: str) -> dict[str, str]:
    body = token[len(LOCAL_TOKEN_PREFIX):]
    try:
        data = json.loads(zlib.decompress(base64.urlsafe_b64decode(body + "=" * (-len(body) % 4))))
        mapping = data["m"]
    except Exception as exc:  # broken or truncated token
        raise LocalError("The mapping_token is broken. Pass the mapping_token output of the mask node unchanged.") from exc
    if not isinstance(mapping, dict):
        raise LocalError("The mapping_token is broken. Pass the mapping_token output of the mask node unchanged.")
    return {str(k): str(v) for k, v in mapping.items()}


def mask(text: str, style: str = "tag", extra: list[str] | None = None) -> dict[str, Any]:
    """Same shape as the API's /v1/mask response: masked_text, entities, mapping_token."""
    if len(text) > MAX_TEXT_LENGTH:
        raise LocalError(f"The text is too long ({len(text):,} characters). The limit is {MAX_TEXT_LENGTH:,}.")
    try:
        mask_style = engine.MaskStyle(style)
    except ValueError:
        mask_style = engine.MaskStyle.TAG
    extra_types = [engine.EntityType(name) for name in (extra or []) if name in engine.EntityType.__members__]
    found = engine.detect(text, None, 0.5, extra_types)
    result = engine.mask(text, found, mask_style)
    token = _encode(result.mapping) if mask_style is engine.MaskStyle.TAG and result.mapping else None
    return {
        "masked_text": result.masked_text,
        "mapping_token": token,
        "entities": [
            {"type": e.type.value, "start": e.start, "end": e.end, "score": e.score} for e in found
        ],
    }


def unmask(text: str, token: str) -> str:
    return engine.unmask(text, _decode(token))
