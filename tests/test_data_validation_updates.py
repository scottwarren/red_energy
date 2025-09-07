"""Test the data validation updates made today."""
from __future__ import annotations

import pytest
from unittest.mock import Mock

from custom_components.red_energy.data_validation import (
    validate_customer_data,
    validate_properties_data,
    validate_single_property,
    validate_usage_data,
    validate_address,
    DataValidationError,
)


class TestCustomerDataValidation:
    """Test customer data validation with new field mappings."""

    def test_validate_customer_data_with_customer_number(self):
        """Test customer data validation using customerNumber as ID."""
        raw_data = {
            "customerNumber": 7053036,
            "name": "MR SCOTT WARREN",
            "email": "realscottwarren@gmail.com",
            "accounts": [
                {"customerNumber": 7053036, "accountNumber": 8732834, "role": "PRIMAR"}
            ],
            "phone": "0405 557 783"
        }
        
        result = validate_customer_data(raw_data)
        
        # Should use customerNumber as the ID
        assert result["id"] == "7053036"
        assert result["customerNumber"] == "7053036"
        assert result["name"] == "MR SCOTT WARREN"
        assert result["email"] == "realscottwarren@gmail.com"
        assert result["account_ids"] == ["7053036.8732834"]
        assert result["phone"] == "0405 557 783"

    def test_validate_customer_data_missing_customer_number(self):
        """Test customer data validation with missing customerNumber."""
        raw_data = {
            "name": "MR SCOTT WARREN",
            "email": "realscottwarren@gmail.com",
            "accounts": []
        }
        
        with pytest.raises(DataValidationError, match="Missing required customer field: customerNumber"):
            validate_customer_data(raw_data)


class TestPropertyDataValidation:
    """Test property data validation with new field mappings."""

    def test_validate_single_property_with_consumers(self):
        """Test property validation mapping consumers to services."""
        raw_data = {
            "propertyPhysicalNumber": 84953336,
            "propertyNumber": "84953336.8732834",
            "accountNumber": 8732834,
            "address": {
                "street": "PRINCE STREET",
                "suburb": "COFFS HARBOUR",
                "state": "NSW",
                "postcode": "2450",
                "displayAddresses": {
                    "shortForm": "Unit 8, 4 Prince Street, Coffs Harbour"
                }
            },
            "consumers": [
                {
                    "consumerNumber": 4373002210,
                    "utility": "E",
                    "nmi": "4407105303",
                    "status": "ON",
                    "meterType": "INTERVAL"
                }
            ]
        }
        
        result = validate_single_property(raw_data)
        
        # Should use propertyPhysicalNumber as ID
        assert result["id"] == "84953336"
        assert result["prop_number"] == "84953336"
        assert result["name"] == "Unit 8, 4 Prince Street, Coffs Harbour"
        assert result["account_ids"] == ["8732834"]
        
        # Should map consumers to services
        services = result["services"]
        assert len(services) == 1
        assert services[0]["type"] == "electricity"  # 'E' mapped to 'electricity'
        assert services[0]["consumer_number"] == "4373002210"
        assert services[0]["active"] is True
        assert services[0]["nmi"] == "4407105303"
        assert services[0]["meter_type"] == "INTERVAL"

    def test_validate_single_property_gas_service(self):
        """Test property validation with gas service."""
        raw_data = {
            "propertyPhysicalNumber": 84953337,
            "accountNumber": 8732835,
            "address": {"street": "TEST STREET", "suburb": "TEST CITY", "state": "VIC", "postcode": "3000"},
            "consumers": [
                {
                    "consumerNumber": 4373002211,
                    "utility": "G",  # Gas
                    "nmi": "4407105304",
                    "status": "ON",
                    "meterType": "BASIC"
                }
            ]
        }
        
        result = validate_single_property(raw_data)
        
        services = result["services"]
        assert len(services) == 1
        assert services[0]["type"] == "gas"  # 'G' mapped to 'gas'
        assert services[0]["consumer_number"] == "4373002211"

    def test_validate_single_property_missing_property_physical_number(self):
        """Test property validation with missing propertyPhysicalNumber."""
        raw_data = {
            "accountNumber": 8732834,
            "address": {},
            "consumers": []
        }
        
        with pytest.raises(DataValidationError, match="Property missing required 'propertyPhysicalNumber' field"):
            validate_single_property(raw_data)

    def test_validate_properties_data_list(self):
        """Test properties data validation with list input."""
        raw_data = [
            {
                "propertyPhysicalNumber": 84953336,
                "accountNumber": 8732834,
                "address": {"street": "PRINCE STREET", "suburb": "COFFS HARBOUR", "state": "NSW", "postcode": "2450"},
                "consumers": [
                    {
                        "consumerNumber": 4373002210,
                        "utility": "E",
                        "nmi": "4407105303",
                        "status": "ON",
                        "meterType": "INTERVAL"
                    }
                ]
            }
        ]
        
        result = validate_properties_data(raw_data)
        
        assert len(result) == 1
        assert result[0]["id"] == "84953336"
        assert len(result[0]["services"]) == 1
        assert result[0]["services"][0]["type"] == "electricity"


class TestAddressValidation:
    """Test address validation with new field mappings."""

    def test_validate_address_suburb_mapping(self):
        """Test address validation mapping suburb to city."""
        raw_data = {
            "street": "PRINCE STREET",
            "suburb": "COFFS HARBOUR",  # API uses 'suburb'
            "state": "NSW",
            "postcode": "2450",
            "displayAddress": "UNIT 8  4 PRINCE STREET\nCOFFS HARBOUR  NSW  2450",
            "displayAddresses": {
                "shortForm": "Unit 8, 4 Prince Street, Coffs Harbour"
            }
        }
        
        result = validate_address(raw_data)
        
        assert result["street"] == "PRINCE STREET"
        assert result["city"] == "COFFS HARBOUR"  # Should map suburb to city
        assert result["state"] == "NSW"
        assert result["postcode"] == "2450"
        assert result["display_address"] == "UNIT 8  4 PRINCE STREET\nCOFFS HARBOUR  NSW  2450"
        assert result["short_form"] == "Unit 8, 4 Prince Street, Coffs Harbour"

    def test_validate_address_fallback_to_city(self):
        """Test address validation fallback from suburb to city."""
        raw_data = {
            "street": "TEST STREET",
            "city": "TEST CITY",  # No suburb, use city
            "state": "VIC",
            "postcode": "3000"
        }
        
        result = validate_address(raw_data)
        
        assert result["city"] == "TEST CITY"

    def test_validate_address_empty_data(self):
        """Test address validation with empty data."""
        result = validate_address({})
        
        assert result["street"] == ""
        assert result["city"] == ""
        assert result["state"] == ""
        assert result["postcode"] == ""


class TestUsageDataValidation:
    """Test usage data validation with new structure."""

    def test_validate_usage_data_array_input(self):
        """Test usage data validation with array input (new API structure)."""
        raw_data = [
            {
                "usageDate": "2025-08-09",
                "halfHours": [
                    {
                        "intervalStart": "2025-08-09T00:00:00+10:00",
                        "primaryConsumptionTariffComponent": "OFFPEAK",
                        "consumptionKwh": 0.241,
                        "consumptionDollar": 0.07,
                        "consumptionDollarIncGst": 0.0742,
                        "generationKwh": 0.0
                    },
                    {
                        "intervalStart": "2025-08-09T00:30:00+10:00",
                        "primaryConsumptionTariffComponent": "OFFPEAK",
                        "consumptionKwh": 0.242,
                        "consumptionDollar": 0.07,
                        "consumptionDollarIncGst": 0.0742,
                        "generationKwh": 0.0
                    }
                ]
            },
            {
                "usageDate": "2025-08-10",
                "halfHours": [
                    {
                        "intervalStart": "2025-08-10T00:00:00+10:00",
                        "primaryConsumptionTariffComponent": "OFFPEAK",
                        "consumptionKwh": 0.200,
                        "consumptionDollar": 0.06,
                        "consumptionDollarIncGst": 0.066,
                        "generationKwh": 0.0
                    }
                ]
            }
        ]
        
        result = validate_usage_data(raw_data, "4373002210")
        
        assert result["consumer_number"] == "4373002210"
        assert result["from_date"] == "2025-08-09"
        assert result["to_date"] == "2025-08-10"
        
        # Should aggregate half-hour intervals to daily totals
        usage_data = result["usage_data"]
        assert len(usage_data) == 2
        
        # First day: 0.241 + 0.242 = 0.483 kWh, 0.0742 + 0.0742 = 0.1484 AUD (rounded to 0.15)
        assert usage_data[0]["date"] == "2025-08-09"
        assert usage_data[0]["usage"] == 0.483
        assert usage_data[0]["cost"] == 0.15  # Rounded to 2 decimal places
        assert usage_data[0]["unit"] == "kWh"
        
        # Second day: 0.200 kWh, 0.066 AUD (rounded to 0.07)
        assert usage_data[1]["date"] == "2025-08-10"
        assert usage_data[1]["usage"] == 0.200
        assert usage_data[1]["cost"] == 0.07  # Rounded to 2 decimal places
        
        # Total: 0.483 + 0.200 = 0.683 kWh (rounded to 0.68), 0.15 + 0.07 = 0.22 AUD
        assert result["total_usage"] == 0.68  # Rounded to 2 decimal places
        assert result["total_cost"] == 0.22  # Rounded to 2 decimal places

    def test_validate_usage_data_not_list(self):
        """Test usage data validation with non-list input."""
        raw_data = {"invalid": "structure"}
        
        with pytest.raises(DataValidationError, match="Usage data must be a list"):
            validate_usage_data(raw_data, "4373002210")

    def test_validate_usage_data_empty_list(self):
        """Test usage data validation with empty list."""
        result = validate_usage_data([], "4373002210")
        
        assert result["consumer_number"] == "4373002210"
        assert result["from_date"] == ""
        assert result["to_date"] == ""
        assert result["usage_data"] == []
        assert result["total_usage"] == 0.0
        assert result["total_cost"] == 0.0

    def test_validate_usage_data_missing_usage_date(self):
        """Test usage data validation with missing usageDate."""
        raw_data = [
            {
                "halfHours": [
                    {
                        "consumptionKwh": 0.241,
                        "consumptionDollarIncGst": 0.0742
                    }
                ]
            }
        ]
        
        result = validate_usage_data(raw_data, "4373002210")
        
        # Should skip entries without usageDate
        assert result["usage_data"] == []
        assert result["total_usage"] == 0.0
        assert result["total_cost"] == 0.0


class TestIntegrationWithRealData:
    """Test integration with real API data structure."""

    def test_full_customer_property_usage_flow(self):
        """Test the complete flow from customer to usage data."""
        # Customer data (from real API)
        customer_data = {
            "customerNumber": 7053036,
            "name": "MR SCOTT WARREN",
            "email": "realscottwarren@gmail.com",
            "accounts": [
                {"customerNumber": 7053036, "accountNumber": 8732834, "role": "PRIMAR"}
            ]
        }
        
        # Property data (from real API)
        property_data = {
            "propertyPhysicalNumber": 84953336,
            "propertyNumber": "84953336.8732834",
            "accountNumber": 8732834,
            "address": {
                "street": "PRINCE STREET",
                "suburb": "COFFS HARBOUR",
                "state": "NSW",
                "postcode": "2450",
                "displayAddresses": {
                    "shortForm": "Unit 8, 4 Prince Street, Coffs Harbour"
                }
            },
            "consumers": [
                {
                    "consumerNumber": 4373002210,
                    "propertyNumber": "84953336.8732834",
                    "accountNumber": 8732834,
                    "entryDate": "2025-07-30",
                    "finalDate": None,
                    "status": "ON",
                    "nmi": "4407105303",
                    "nmiWithChecksum": "44071053030",
                    "utility": "E",
                    "meterType": "INTERVAL",
                    "chargeClass": "RES",
                    "solar": False
                }
            ]
        }
        
        # Usage data (from real API)
        usage_data = [
            {
                "usageDate": "2025-08-09",
                "halfHours": [
                    {
                        "intervalStart": "2025-08-09T00:00:00+10:00",
                        "primaryConsumptionTariffComponent": "OFFPEAK",
                        "consumptionKwh": 0.241,
                        "consumptionDollar": 0.07,
                        "consumptionDollarIncGst": 0.0742,
                        "generationKwh": 0.0
                    }
                ]
            }
        ]
        
        # Validate all data
        validated_customer = validate_customer_data(customer_data)
        validated_properties = validate_properties_data([property_data])
        validated_usage = validate_usage_data(usage_data, "4373002210")
        
        # Verify customer validation
        assert validated_customer["id"] == "7053036"
        assert validated_customer["name"] == "MR SCOTT WARREN"
        assert validated_customer["account_ids"] == ["7053036.8732834"]
        
        # Verify property validation
        assert len(validated_properties) == 1
        prop = validated_properties[0]
        assert prop["id"] == "84953336"
        assert prop["name"] == "Unit 8, 4 Prince Street, Coffs Harbour"
        assert len(prop["services"]) == 1
        assert prop["services"][0]["type"] == "electricity"
        assert prop["services"][0]["consumer_number"] == "4373002210"
        assert prop["services"][0]["nmi"] == "4407105303"
        
        # Verify usage validation
        assert validated_usage["consumer_number"] == "4373002210"
        assert validated_usage["total_usage"] == 0.24  # Rounded to 2 decimal places
        assert validated_usage["total_cost"] == 0.07  # Rounded to 2 decimal places
        assert len(validated_usage["usage_data"]) == 1
        assert validated_usage["usage_data"][0]["usage"] == 0.241  # Not rounded in individual entries
        assert validated_usage["usage_data"][0]["cost"] == 0.07  # Rounded to 2 decimal places
