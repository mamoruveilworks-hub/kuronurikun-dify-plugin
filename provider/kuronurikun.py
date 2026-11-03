from typing import Any

from dify_plugin import ToolProvider
from dify_plugin.errors.tool import ToolProviderCredentialValidationError

from tools.client import KuronurikunError, post


class KuronurikunProvider(ToolProvider):
    def _validate_credentials(self, credentials: dict[str, Any]) -> None:
        """Check the API key without using the monthly quota.

        /v1/unmask is not counted. With a valid key and a dummy token the API answers 400
        (the token cannot be decrypted); with an invalid key it answers 401.
        """
        try:
            post("/v1/unmask", credentials.get("api_key", ""), {"text": "check", "mapping_token": "pm1.check"})
        except KuronurikunError as exc:
            message = str(exc)
            if "HTTP 400" in message:
                return  # the key was accepted; only the dummy token was rejected
            raise ToolProviderCredentialValidationError(message) from exc
