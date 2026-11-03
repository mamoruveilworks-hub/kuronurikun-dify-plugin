"""Small client for the Kuronuri-kun API (https://kuronurikun.com/docs)."""

from __future__ import annotations

from typing import Any

import requests

BASE_URL = "https://kuronurikun.com"
# Full URLs are written out so that the only outbound host is easy to audit.
ENDPOINTS = {
    "/v1/mask": "https://kuronurikun.com/v1/mask",
    "/v1/unmask": "https://kuronurikun.com/v1/unmask",
}
TIMEOUT = (10, 60)  # (connect, read) seconds


class KuronurikunError(Exception):
    """An error returned by the Kuronuri-kun API, with a message for the user."""


def _detail(response: requests.Response) -> str:
    try:
        detail = response.json().get("detail")
    except ValueError:
        detail = None
    if isinstance(detail, list):  # validation errors
        detail = "; ".join(str(d.get("msg", d)) for d in detail)
    return str(detail or response.text[:300] or f"HTTP {response.status_code}")


def post(path: str, api_key: str, payload: dict[str, Any]) -> dict[str, Any]:
    if not api_key:
        raise KuronurikunError("API key is not set. Get one for free at https://kuronurikun.com")
    try:
        response = requests.post(
            ENDPOINTS[path],
            json=payload,
            headers={"X-API-Key": api_key, "User-Agent": "kuronurikun-dify-plugin/0.1.0"},
            timeout=TIMEOUT,
        )
    except requests.RequestException as exc:
        raise KuronurikunError(f"Could not reach {BASE_URL}: {exc}") from exc

    if response.status_code == 200:
        return response.json()
    message = _detail(response)
    if response.status_code == 401:
        raise KuronurikunError(f"Invalid API key. {message}")
    if response.status_code == 403:
        raise KuronurikunError(f"This mapping_token was issued with a different API key. {message}")
    if response.status_code == 429:
        raise KuronurikunError(f"Rate or monthly quota limit reached. {message}")
    raise KuronurikunError(f"Kuronuri-kun API error (HTTP {response.status_code}): {message}")
