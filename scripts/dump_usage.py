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
from custom_components.red_energy.data_validation import validate_properties_data, validate_usage_data


async def main() -> int:
    if load_dotenv:
        load_dotenv()

    username = os.getenv("RED_USERNAME")
    password = os.getenv("RED_PASSWORD")
    client_id = os.getenv("RED_CLIENT_ID")
    service_type = os.getenv("RED_SERVICE", "electricity").lower()
    days = int(os.getenv("RED_DAYS", "30"))

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

        raw_props = await api.get_properties()
        props = validate_properties_data(raw_props, client_id=client_id)
        if not props:
            print("No properties available after validation")
            return 3

        # Pick first property with requested service
        target = None
        for p in props:
            for s in p.get("services", []):
                if s.get("type") == service_type and s.get("consumer_number"):
                    target = (p, s)
                    break
            if target:
                break

        if not target:
            print(f"No property found with service {service_type}")
            return 4

        prop, svc = target
        consumer_number = svc["consumer_number"]
        end_date = datetime.now()
        start_date = end_date - timedelta(days=days)
        raw_usage = await api.get_usage_data(consumer_number, start_date, end_date)
        usage = validate_usage_data(raw_usage)
        print({
            "property_id": prop.get("id"),
            "service_type": service_type,
            "from": usage.get("from_date"),
            "to": usage.get("to_date"),
            "total_usage": usage.get("total_usage"),
            "total_cost": usage.get("total_cost"),
            "days": len(usage.get("usage_data", [])),
        })

    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))


