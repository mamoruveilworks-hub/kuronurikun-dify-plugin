from collections.abc import Generator
from typing import Any

from dify_plugin import Tool
from dify_plugin.entities.tool import ToolInvokeMessage

from tools.client import post


class UnmaskPiiTool(Tool):
    def _invoke(self, tool_parameters: dict[str, Any]) -> Generator[ToolInvokeMessage, None, None]:
        text = tool_parameters.get("text") or ""
        token = tool_parameters.get("mapping_token") or ""
        if not token:
            # Nothing was masked with style=tag (or the token is missing): return the text unchanged.
            restored = text
        else:
            restored = post(
                "/v1/unmask", self.runtime.credentials.get("api_key", ""), {"text": text, "mapping_token": token}
            )["text"]
        yield self.create_variable_message("text", restored)
        yield self.create_text_message(restored)
