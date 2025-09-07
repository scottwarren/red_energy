#!/usr/bin/env python3
import asyncio
import os
import sys
from typing import Any, Dict

import aiohttp

try:
    from dotenv import load_dotenv
except Exception:
    load_dotenv = None

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from custom_components.red_energy.api import RedEnergyAPI  # type: ignore
from custom_components.red_energy.data_validation import (
    validate_customer_data,
    validate_properties_data,
)


def _mask(value: str, keep: int = 6) -> str:
    if not value:
        return ""
    if len(value) <= keep:
        return "*" * len(value)
    return value[:keep] + "…" + "*" * (len(value) - keep - 1)


async def main() -> int:
    if load_dotenv:
        load_dotenv()

    username = os.getenv("RED_USERNAME")
    password = os.getenv("RED_PASSWORD")
    client_id = os.getenv("RED_CLIENT_ID")
    verbose = os.getenv("DEBUG_VERBOSE", "0") in ("1", "true", "True")

    if not username or not password or not client_id:
        print("Missing env vars. Please set RED_USERNAME, RED_PASSWORD, RED_CLIENT_ID in .env")
        return 2

    timeout = aiohttp.ClientTimeout(total=60)
    async with aiohttp.ClientSession(timeout=timeout) as session:
        api = RedEnergyAPI(session)

        print("Step 1: Okta session token…")
        try:
            session_token, expires_at = await api._get_session_token(username, password)  # type: ignore[attr-defined]
            print({
                "ok": True,
                "session_token": _mask(session_token, keep=8),
                "expires_at": expires_at,
            })
        except Exception as err:
            print({"ok": False, "error": f"{err}"})
            return 1

        print("Step 2: Discovery…")
        discovery = await api._get_discovery_data()  # type: ignore[attr-defined]
        print({
            "authorization_endpoint": discovery.get("authorization_endpoint"),
            "token_endpoint": discovery.get("token_endpoint"),
            "issuer": discovery.get("issuer"),
        })

        print("Step 3: PKCE…")
        code_verifier = api._generate_code_verifier()  # type: ignore[attr-defined]
        code_challenge = api._generate_code_challenge(code_verifier)  # type: ignore[attr-defined]
        print({"code_challenge": _mask(code_challenge, keep=10)})

        print("Step 4: Authorization code…")
        auth_endpoint = discovery["authorization_endpoint"]
        auth_code = await api._get_authorization_code(auth_endpoint, session_token, client_id, code_challenge)  # type: ignore[attr-defined]
        print({"auth_code": _mask(auth_code, keep=10)})

        print("Step 5: Token exchange…")
        token_endpoint = discovery["token_endpoint"]
        await api._exchange_code_for_tokens(token_endpoint, auth_code, client_id, code_verifier)  # type: ignore[attr-defined]
        # Access token stored internally; we won't print it
        print({"access_token": "received", "refresh_token": "received-or-null"})

        print("Step 6: Customer data…")
        customer_raw = await api.get_customer_data()
        customer_norm = validate_customer_data(dict(customer_raw)) if isinstance(customer_raw, dict) else {}
        if verbose:
            print({"raw": customer_raw, "normalized": customer_norm})
        else:
            print({k: customer_norm.get(k) for k in ("id", "name", "email")})

        print("Step 7: Properties…")
        props_raw = await api.get_properties()
        props_norm = []
        try:
            props_norm = validate_properties_data(list(props_raw or []), client_id=client_id)
        except Exception:
            pass
        if verbose:
            print({"raw": props_raw, "normalized": props_norm})
        else:
            def summarize(items):
                out = []
                for p in (items or []):
                    services = p.get("services", []) or []
                    out.append({
                        "id": p.get("id"),
                        "name": p.get("name"),
                        "service_types": [s.get("type") for s in services],
                        "consumer_present": [bool(s.get("consumer_number")) for s in services],
                    })
                return out
            print({
                "raw": summarize(props_raw),
                "normalized": summarize(props_norm),
            })

        print("Done.")
        return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))


