#!/usr/bin/env python3
"""
Script to fetch and display usage data for all consumer numbers found in properties.
This helps understand the complete data structure for all accounts.
"""
import asyncio
import os
import sys
from datetime import datetime, timedelta
from typing import Any, Dict, List

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
    validate_usage_data,
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

    if not username or not password or not client_id:
        print("Missing env vars. Please set RED_USERNAME, RED_PASSWORD, RED_CLIENT_ID in .env")
        return 2

    timeout = aiohttp.ClientTimeout(total=60)
    async with aiohttp.ClientSession(timeout=timeout) as session:
        api = RedEnergyAPI(session)

        print("=== RED ENERGY COMPLETE DATA DUMP ===\n")

        # Step 1: Authenticate
        print("1. Authenticating...")
        try:
            session_token, expires_at = await api._get_session_token(username, password)
            print(f"✓ Session token: {_mask(session_token, keep=8)}")
        except Exception as err:
            print(f"✗ Authentication failed: {err}")
            return 1

        # Step 2: Get discovery data
        discovery = await api._get_discovery_data()

        # Step 3: PKCE flow
        code_verifier = api._generate_code_verifier()
        code_challenge = api._generate_code_challenge(code_verifier)

        # Step 4: Get authorization code
        auth_endpoint = discovery["authorization_endpoint"]
        auth_code = await api._get_authorization_code(auth_endpoint, session_token, client_id, code_challenge)

        # Step 5: Exchange for tokens
        token_endpoint = discovery["token_endpoint"]
        await api._exchange_code_for_tokens(token_endpoint, auth_code, client_id, code_verifier)
        print("✓ Authentication complete\n")

        # Step 6: Get customer data
        print("2. Customer Information:")
        customer_raw = await api.get_customer_data()
        customer_norm = validate_customer_data(dict(customer_raw))

        print(f"  Customer ID: {customer_norm.get('id')}")
        print(f"  Name: {customer_norm.get('name')}")
        print(f"  Email: {customer_norm.get('email')}")
        print(f"  Account IDs: {customer_norm.get('account_ids')}")
        print()

        # Step 7: Get properties and extract all consumer numbers
        print("3. Properties and Services:")
        properties_raw = await api.get_properties()
        properties_norm = validate_properties_data(list(properties_raw or []), client_id=client_id)

        all_consumers = []
        for i, prop in enumerate(properties_norm):
            print(f"  Property {i+1}: {prop.get('name')}")
            print(f"    ID: {prop.get('id')}")
            print(f"    Address: {prop.get('address', {}).get('short_form', 'N/A')}")

            services = prop.get('services', [])
            print(f"    Services ({len(services)}):")
            for j, service in enumerate(services):
                consumer_num = service.get('consumer_number')
                service_type = service.get('type')
                nmi = service.get('nmi', 'N/A')
                active = service.get('active', False)

                print(f"      {j+1}. {service_type.upper()} - Consumer: {consumer_num}, NMI: {nmi}, Active: {active}")

                if consumer_num:
                    all_consumers.append({
                        'consumer_number': consumer_num,
                        'service_type': service_type,
                        'property_name': prop.get('name'),
                        'nmi': nmi,
                    })
            print()

        # Step 8: Get usage data for all consumers
        print("4. Usage Data for All Consumers:")
        if not all_consumers:
            print("  No consumers found to fetch usage data for.")
            return 0

        for i, consumer in enumerate(all_consumers):
            print(f"  Consumer {i+1}: {consumer['consumer_number']} ({consumer['service_type']})")
            print(f"    Property: {consumer['property_name']}")
            print(f"    NMI: {consumer['nmi']}")

            try:
                # Get usage data for the last 30 days
                to_date = datetime.now()
                from_date = to_date - timedelta(days=30)

                usage_raw = await api.get_usage_data(
                    consumer['consumer_number'],
                    from_date,
                    to_date
                )
                print(f"    Raw usage data keys: {list(usage_raw.keys()) if isinstance(usage_raw, dict) else 'Not a dict'}")

                # Try to validate and show summary
                try:
                    usage_norm = validate_usage_data(usage_raw, consumer['consumer_number'])
                    print(f"    Validated usage entries: {len(usage_norm.get('usage_data', []))}")
                    print(f"    Total usage: {usage_norm.get('total_usage', 0)} kWh")
                    print(f"    Total cost: ${usage_norm.get('total_cost', 0)}")
                    print(f"    Date range: {usage_norm.get('from_date', 'N/A')} to {usage_norm.get('to_date', 'N/A')}")
                except Exception as validation_err:
                    print(f"    Validation failed: {validation_err}")
                    print(f"    Raw data sample: {str(usage_raw)[:500]}...")

            except Exception as usage_err:
                print(f"    ✗ Failed to fetch usage: {usage_err}")

            print()

        print("=== COMPLETE DATA DUMP FINISHED ===")
        return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
