"""API contract tests to validate expected response formats."""
from __future__ import annotations

import pytest
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock
from datetime import datetime


class _MockAIOHTTPResponse:
    def __init__(self, *, status: int = 200, json_data=None, text_data: str = "", headers: dict | None = None):
        self.status = status
        self._json_data = json_data
        self._text_data = text_data
        self.headers = headers or {}

    async def json(self):
        return self._json_data

    async def text(self):
        return self._text_data

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return False

    def raise_for_status(self):
        if self.status >= 400:
            raise RuntimeError(f"HTTP {self.status}")


def _mock_session(method_map: dict[str, _MockAIOHTTPResponse]):
    """Create a mocked aiohttp session with get/post returning mapped results by URL prefix."""
    session = MagicMock()

    class _RequestCM:
        def __init__(self, resp: _MockAIOHTTPResponse):
            self._resp = resp
        async def __aenter__(self):
            return self._resp
        async def __aexit__(self, exc_type, exc, tb):
            return False

    def _select(url: str):
        for prefix, resp in method_map.items():
            if url.startswith(prefix):
                return _RequestCM(resp)
        raise AssertionError(f"Unexpected URL called: {url}")

    session.get = MagicMock(side_effect=lambda url, *a, **kw: _select(url))
    session.post = MagicMock(side_effect=lambda url, *a, **kw: _select(url))
    return session


@pytest.mark.asyncio
async def test_get_customer_data_format():
    from custom_components.red_energy.api import RedEnergyAPI

    customer_payload = {"id": "cust-1", "name": "Jane Doe", "email": "jane@example.com"}

    session = _mock_session({
        "https://selfservice.services.retail.energy/v1/customers/current": _MockAIOHTTPResponse(json_data=customer_payload)
    })

    api = RedEnergyAPI(session)
    api._access_token = "token"
    data = await api.get_customer_data()

    assert isinstance(data, dict)
    assert set(["id", "name"]).issubset(data.keys())


@pytest.mark.asyncio
async def test_get_properties_accepts_both_list_and_nested_format():
    from custom_components.red_energy.api import RedEnergyAPI

    list_payload = [
        {"id": "prop-1", "name": "Home"},
        {"id": "prop-2", "name": "Office"},
    ]
    nested_payload = {"properties": list_payload}

    # First call: list format
    session_list = _mock_session({
        "https://selfservice.services.retail.energy/v1/properties": _MockAIOHTTPResponse(json_data=list_payload)
    })
    api_list = RedEnergyAPI(session_list)
    api_list._access_token = "token"
    props1 = await api_list.get_properties()
    assert isinstance(props1, list)
    assert len(props1) == 2

    # Second call: nested format
    session_nested = _mock_session({
        "https://selfservice.services.retail.energy/v1/properties": _MockAIOHTTPResponse(json_data=nested_payload)
    })
    api_nested = RedEnergyAPI(session_nested)
    api_nested._access_token = "token"
    props2 = await api_nested.get_properties()
    assert isinstance(props2, list)
    assert len(props2) == 2


@pytest.mark.asyncio
async def test_get_usage_data_format():
    from custom_components.red_energy.api import RedEnergyAPI

    usage_payload = {
        "consumer_number": "elec-123",
        "from_date": "2025-01-01",
        "to_date": "2025-01-31",
        "usage_data": [
            {"date": "2025-01-01", "usage": 10.0, "cost": 2.8, "unit": "kWh"},
            {"date": "2025-01-02", "usage": 12.0, "cost": 3.36, "unit": "kWh"},
        ],
        "total_usage": 22.0,
        "total_cost": 6.16,
    }

    session = _mock_session({
        "https://selfservice.services.retail.energy/v1/usage/interval": _MockAIOHTTPResponse(json_data=usage_payload)
    })

    api = RedEnergyAPI(session)
    api._access_token = "token"
    data = await api.get_usage_data("elec-123", datetime(2025, 1, 1), datetime(2025, 1, 31))

    assert isinstance(data, dict)
    assert "usage_data" in data and isinstance(data["usage_data"], list)
    assert {"total_usage", "total_cost"}.issubset(data.keys())


@pytest.mark.asyncio
async def test_authentication_happy_path_contract():
    """Validate the shape of each auth step without real network calls."""
    from custom_components.red_energy.api import RedEnergyAPI

    discovery_data = {
        "authorization_endpoint": "https://auth.example/authorize",
        "token_endpoint": "https://auth.example/token",
    }
    # Step responses
    okta_resp = _MockAIOHTTPResponse(json_data={"status": "SUCCESS", "sessionToken": "sess", "expiresAt": "ts"})
    discovery_resp = _MockAIOHTTPResponse(json_data=discovery_data)
    # Redirect carries code
    redirect_headers = {
        "Location": "au.com.redenergy://callback?code=abc123&state=xyz",
    }
    auth_code_resp = _MockAIOHTTPResponse(status=302, headers=redirect_headers)
    token_resp = _MockAIOHTTPResponse(json_data={
        "access_token": "at",
        "refresh_token": "rt",
        "expires_in": 3600,
    })

    session = MagicMock()

    class _RequestCM:
        def __init__(self, resp: _MockAIOHTTPResponse):
            self._resp = resp
        async def __aenter__(self):
            return self._resp
        async def __aexit__(self, exc_type, exc, tb):
            return False

    def _post(url, *a, **kw):
        if url.endswith("/api/v1/authn"):
            return _RequestCM(okta_resp)
        if url.endswith("/token"):
            return _RequestCM(token_resp)
        raise AssertionError(f"Unexpected POST {url}")

    def _get(url, *a, **kw):
        if url.endswith("/.well-known/openid-configuration"):
            return _RequestCM(discovery_resp)
        if url.startswith("https://auth.example/authorize"):
            return _RequestCM(auth_code_resp)
        raise AssertionError(f"Unexpected GET {url}")

    session.post = MagicMock(side_effect=_post)
    session.get = MagicMock(side_effect=_get)

    api = RedEnergyAPI(session)
    ok = await api.authenticate("u", "p", "client")
    assert ok is True

