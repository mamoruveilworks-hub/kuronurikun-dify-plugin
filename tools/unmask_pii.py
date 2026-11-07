from collections.abc import Generator
from typing import Any

from dify_plugin import Tool
from dify_plugin.entities.tool import ToolInvokeMessage

from tools import local
from tools.client import KuronurikunError, post


class UnmaskPiiTool(Tool):
    def _invoke(self, tool_parameters: dict[str, Any]) -> Generator[ToolInvokeMessage, None, None]:
        text = tool_parameters.get("text") or ""
        # Dify text inputs can carry stray spaces or line breaks around an inserted variable.
        token = str(tool_parameters.get("mapping_token") or "").strip()
        if not token:
            # Nothing was masked with style=tag (or the token is missing): return the text unchanged.
            restored = text
        elif token.startswith(local.LOCAL_TOKEN_PREFIX):
            # Masked inside this plugin: restored here as well, without any network request.
            try:
                restored = local.unmask(text, token)
            except local.LocalError as exc:
                raise KuronurikunError(str(exc)) from exc
        elif not token.startswith(local.API_TOKEN_PREFIX):
            raise KuronurikunError(
                "The mapping_token input does not contain a token from \"Mask personal information\" "
                f"(a token starts with \"{local.LOCAL_TOKEN_PREFIX}\" or \"{local.API_TOKEN_PREFIX}\"). "
                "In the restore node, set mapping_token to the mapping_token variable of the mask node, "
                "not its text or json."
            )
        else:
            restored = post(
                "/v1/unmask", self.runtime.credentials.get("api_key", ""), {"text": text, "mapping_token": token}
            )["text"]
        # "text" is a reserved output name of Dify's tool node, so a different variable name is used.
        yield self.create_variable_message("restored_text", restored)
        yield self.create_text_message(restored)
