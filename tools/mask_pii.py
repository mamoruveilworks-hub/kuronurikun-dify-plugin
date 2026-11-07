from collections.abc import Generator
from typing import Any

from dify_plugin import Tool
from dify_plugin.entities.tool import ToolInvokeMessage

from tools import local
from tools.client import KuronurikunError, post

OPTIONAL_TYPES = {"AGE", "GENDER", "COMPANY", "CARD_EXPIRY"}
STYLES = {"tag", "block", "asterisk", "redact"}


def parse_extra(raw: Any) -> list[str]:
    """'age, Gender' -> ['AGE', 'GENDER'] (unknown names are ignored)."""
    if not raw:
        return []
    names = [part.strip().upper() for part in str(raw).replace("、", ",").split(",")]
    return [name for name in names if name in OPTIONAL_TYPES]


class MaskPiiTool(Tool):
    def _invoke(self, tool_parameters: dict[str, Any]) -> Generator[ToolInvokeMessage, None, None]:
        text = tool_parameters.get("text") or ""
        style = tool_parameters.get("style") or "tag"
        if style not in STYLES:
            style = "tag"
        payload: dict[str, Any] = {"text": text, "style": style}
        extra = parse_extra(tool_parameters.get("extra_entities"))
        if extra:
            payload["extra_entities"] = extra

        credentials = self.runtime.credentials or {}
        if not text:
            result: dict[str, Any] = {"masked_text": "", "mapping_token": None, "entities": []}
        elif local.mode_of(credentials) == local.MODE_LOCAL:
            # Processed inside this plugin. Only the number of characters is sent, to count usage; never the text.
            if len(text) > local.MAX_TEXT_LENGTH:
                raise KuronurikunError(
                    f"The text is too long ({len(text):,} characters). The limit is {local.MAX_TEXT_LENGTH:,}."
                )
            post("/v1/usage", credentials.get("api_key", ""), {"characters": len(text)})
            try:
                result = local.mask(text, style, extra)
            except local.LocalError as exc:
                raise KuronurikunError(str(exc)) from exc
        else:
            result = post("/v1/mask", credentials.get("api_key", ""), payload)

        masked_text = result.get("masked_text", "")
        token = result.get("mapping_token") or ""
        yield self.create_variable_message("masked_text", masked_text)
        yield self.create_variable_message("mapping_token", token)
        yield self.create_variable_message("entity_count", len(result.get("entities", [])))
        # The json output leaves out the original values, so that wiring it to an LLM by mistake does not leak them.
        entities = [{k: v for k, v in e.items() if k != "text"} for e in result.get("entities", [])]
        yield self.create_json_message({"masked_text": masked_text, "mapping_token": token or None, "entities": entities})
        yield self.create_text_message(masked_text)
