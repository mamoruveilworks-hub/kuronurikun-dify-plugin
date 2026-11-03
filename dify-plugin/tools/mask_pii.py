from collections.abc import Generator
from typing import Any

from dify_plugin import Tool
from dify_plugin.entities.tool import ToolInvokeMessage

from tools.client import post

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

        if not text:
            result: dict[str, Any] = {"masked_text": "", "mapping_token": None, "entities": []}
        else:
            result = post("/v1/mask", self.runtime.credentials.get("api_key", ""), payload)

        masked_text = result.get("masked_text", "")
        token = result.get("mapping_token") or ""
        yield self.create_variable_message("masked_text", masked_text)
        yield self.create_variable_message("mapping_token", token)
        yield self.create_variable_message("entity_count", len(result.get("entities", [])))
        yield self.create_json_message(result)
        yield self.create_text_message(masked_text)
