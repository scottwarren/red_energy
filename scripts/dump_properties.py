#!/usr/bin/env python3
import asyncio
import os
import sys
from datetime import datetime, timedelta

import aiohttp

try:
    from dotenv import load_dotenv
except Exception:
    load_dotenv = None

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from custom_components.red_energy.api import RedEnergyAPI
from custom_components.red_energy.data_validation import validate_properties_data


async def main() -> int:
    if load_dotenv:
        load_dotenv()

    username = os.getenv("RED_USERNAME")
    password = os.getenv("RED_PASSWORD")
    client_id = os.getenv("RED_CLIENT_ID")

    if not username or not password or not client_id:
        print("Missing env vars. Please set RED_USERNAME, RED_PASSWORD, RED_CLIENT_ID in .env")
        return 2

    timeout = aiohttp.ClientTimeout(total=60)
    async with aiohttp.ClientSession(timeout=timeout) as session:
        api = RedEnergyAPI(session)
        print("Authenticating...")
        ok = await api.authenticate(username, password, client_id)
        if not ok:
            print("Auth failed")
            return 1

        print("Fetching properties (raw)...")
        raw = await api.get_properties()
        print(raw)

        print("Validating/normalizing properties…")
        props = validate_properties_data(list(raw or []), client_id=client_id)

        print(f"Properties (normalized): {len(props)}")
        for i, p in enumerate(props, 1):
            services = [{
                "type": s.get("type"),
                "consumer_number": s.get("consumer_number"),
                "active": s.get("active")
            } for s in p.get("services", [])]
            print({
                "index": i,
                "id": p.get("id"),
                "name": p.get("name"),
                "address": p.get("address", {}),
                "services": services,
            })

    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))


