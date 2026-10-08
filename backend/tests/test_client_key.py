from typing import Any

import pytest
from starlette.requests import Request

from app.api import deps
from app.core.config import Settings


def make_request(headers: dict[str, str] | None = None, host: str = "1.2.3.4") -> Request:
    scope: dict[str, Any] = {
        "type": "http",
        "headers": [(k.lower().encode(), v.encode()) for k, v in (headers or {}).items()],
        "client": (host, 5000),
    }
    return Request(scope)


def use_settings(monkeypatch: pytest.MonkeyPatch, **values: Any) -> None:
    monkeypatch.setattr(deps, "get_settings", lambda: Settings(**values))


def test_uses_the_connection_address_by_default(monkeypatch: pytest.MonkeyPatch) -> None:
    use_settings(monkeypatch)
    assert deps.client_key(make_request({"X-Forwarded-For": "9.9.9.9"})) == "1.2.3.4"


def test_ignores_a_forged_forwarded_header_unless_the_proxy_is_trusted(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    use_settings(monkeypatch, trust_proxy=False)
    assert deps.client_key(make_request({"X-Forwarded-For": "6.6.6.6, 7.7.7.7"})) == "1.2.3.4"


def test_trusted_proxy_uses_the_last_forwarded_value(monkeypatch: pytest.MonkeyPatch) -> None:
    # 最後一個是我們自己的代理加上去的；前面的值用戶端可以隨便填
    use_settings(monkeypatch, trust_proxy=True)
    assert deps.client_key(make_request({"X-Forwarded-For": "6.6.6.6, 7.7.7.7"})) == "7.7.7.7"


def test_trusted_proxy_without_the_header_falls_back_to_the_connection(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    use_settings(monkeypatch, trust_proxy=True)
    assert deps.client_key(make_request()) == "1.2.3.4"


def test_missing_client_is_one_shared_bucket(monkeypatch: pytest.MonkeyPatch) -> None:
    use_settings(monkeypatch)
    request = make_request()
    request.scope["client"] = None
    assert deps.client_key(request) == "unknown"
