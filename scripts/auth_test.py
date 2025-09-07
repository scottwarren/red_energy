import asyncio
import os
import sys
from datetime import datetime, timedelta

import aiohttp

try:
    from dotenv import load_dotenv
except Exception:  # pragma: no cover
    load_dotenv = None

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from custom_components.red_energy.api import RedEnergyAPI, RedEnergyAuthError


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
        try:
            print("Authenticating...")
            ok = await api.authenticate(username, password, client_id)
            print(f"Auth success: {ok}")

            print("Fetching customer data...")
            customer = await api.get_customer_data()
            print({"id": customer.get("id"), "name": customer.get("name"), "email": customer.get("email")})

            print("Fetching properties...")
            props = await api.get_properties()
            print(f"Properties found: {len(props)}")
            for p in props[:5]:
                print({"id": p.get("id"), "name": p.get("name")})

            return 0
        except RedEnergyAuthError as err:
            print(f"Authentication error: {err}")
            return 1
        except Exception as err:  # pragma: no cover
            print(f"Unexpected error: {err}")
            return 3


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))


