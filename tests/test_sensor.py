"""Test the Red Energy sensor platform."""
from __future__ import annotations

import pytest
from unittest.mock import AsyncMock, Mock, patch
from datetime import datetime, timedelta

from homeassistant.components.sensor import SensorDeviceClass, SensorStateClass
from homeassistant.const import UnitOfEnergy
from homeassistant.core import HomeAssistant
from homeassistant.config_entries import ConfigEntry

from custom_components.red_energy.const import (
    DOMAIN,
    SERVICE_TYPE_ELECTRICITY,
    SERVICE_TYPE_GAS,
    CONF_ENABLE_ADVANCED_SENSORS,
)
from custom_components.red_energy.sensor import (
    async_setup_entry,
    RedEnergyBaseSensor,
    RedEnergyUsageSensor,
    RedEnergyCostSensor,
    RedEnergyCostPerUnitSensor,
    RedEnergyTotalUsageSensor,
    RedEnergyDailyAverageSensor,
    RedEnergyMonthlyAverageSensor,
    RedEnergyPeakUsageSensor,
    RedEnergyEfficiencySensor,
)
from custom_components.red_energy.coordinator import RedEnergyDataCoordinator


# Mock data for testing
MOCK_CUSTOMER_DATA = {
    "id": "7053036",
    "name": "MR SCOTT WARREN",
    "email": "realscottwarren@gmail.com",
    "account_ids": ["7053036.8732834"],
}

MOCK_PROPERTY_DATA = {
    "id": "84953336",
    "name": "Unit 8, 4 Prince Street, Coffs Harbour",
    "address": {
        "street": "PRINCE STREET",
        "city": "COFFS HARBOUR",
        "state": "NSW",
        "postcode": "2450",
    },
    "services": [
        {
            "type": "electricity",
            "consumer_number": "4373002210",
            "active": True,
            "nmi": "4407105303",
        }
    ],
}

MOCK_USAGE_DATA = {
    "84953336": {
        "property": MOCK_PROPERTY_DATA,
        "services": {
            "electricity": {
                "consumer_number": "4373002210",
                "usage_data": {
                    "consumer_number": "4373002210",
                    "from_date": "2025-08-09",
                    "to_date": "2025-09-06",
                    "usage_data": [
                        {"date": "2025-08-09", "usage": 20.5, "cost": 6.5, "unit": "kWh"},
                        {"date": "2025-08-10", "usage": 18.2, "cost": 5.8, "unit": "kWh"},
                        {"date": "2025-08-11", "usage": 22.1, "cost": 7.0, "unit": "kWh"},
                    ],
                    "total_usage": 60.8,
                    "total_cost": 19.3,
                },
                "last_updated": "2025-09-06T10:00:00Z",
            }
        }
    }
}

MOCK_COORDINATOR_DATA = {
    "customer": MOCK_CUSTOMER_DATA,
    "properties": [MOCK_PROPERTY_DATA],
    "usage_data": MOCK_USAGE_DATA,
    "last_update": datetime.now().isoformat(),
}


@pytest.fixture
def mock_coordinator():
    """Create a mock coordinator."""
    coordinator = Mock(spec=RedEnergyDataCoordinator)
    coordinator.data = MOCK_COORDINATOR_DATA
    coordinator.last_update_success = True
    
    # Mock coordinator methods
    coordinator.get_latest_usage = Mock(return_value=22.1)
    coordinator.get_total_cost = Mock(return_value=19.3)
    coordinator.get_total_usage = Mock(return_value=60.8)
    coordinator.get_service_usage = Mock(return_value=MOCK_USAGE_DATA["84953336"]["services"]["electricity"])
    
    return coordinator


@pytest.fixture
def mock_config_entry():
    """Create a mock config entry."""
    config_entry = Mock(spec=ConfigEntry)
    config_entry.entry_id = "test_entry_id"
    config_entry.options = {CONF_ENABLE_ADVANCED_SENSORS: False}
    return config_entry


@pytest.fixture
def mock_hass():
    """Create a mock Home Assistant instance."""
    hass = Mock(spec=HomeAssistant)
    hass.data = {
        DOMAIN: {
            "test_entry_id": {
                "coordinator": Mock(),
                "selected_accounts": ["84953336"],
                "services": [SERVICE_TYPE_ELECTRICITY],
            }
        }
    }
    return hass


class TestSensorSetup:
    """Test sensor setup and creation."""

    @pytest.mark.asyncio
    async def test_async_setup_entry_basic_sensors(self, mock_hass, mock_config_entry, mock_coordinator):
        """Test that basic sensors are created correctly."""
        # Setup mock data
        mock_hass.data[DOMAIN]["test_entry_id"]["coordinator"] = mock_coordinator
        
        entities = []
        async_add_entities = Mock(side_effect=lambda new_entities: entities.extend(new_entities))
        
        await async_setup_entry(mock_hass, mock_config_entry, async_add_entities)
        
        # Should create 4 basic sensors per account/service combination
        # (usage, cost, cost_per_unit, total_usage)
        expected_count = 1 * 1 * 4  # 1 account * 1 service * 4 sensors
        assert len(entities) == expected_count
        
        # Check sensor types
        sensor_types = [entity._sensor_type for entity in entities]
        assert "daily_usage" in sensor_types
        assert "total_cost" in sensor_types
        assert "cost_per_unit" in sensor_types
        assert "total_usage" in sensor_types

    @pytest.mark.asyncio
    async def test_async_setup_entry_with_advanced_sensors(self, mock_hass, mock_config_entry, mock_coordinator):
        """Test that advanced sensors are created when enabled."""
        # Enable advanced sensors
        mock_config_entry.options = {CONF_ENABLE_ADVANCED_SENSORS: True}
        mock_hass.data[DOMAIN]["test_entry_id"]["coordinator"] = mock_coordinator
        
        entities = []
        async_add_entities = Mock(side_effect=lambda new_entities: entities.extend(new_entities))
        
        await async_setup_entry(mock_hass, mock_config_entry, async_add_entities)
        
        # Should create 8 sensors total (4 basic + 4 advanced)
        expected_count = 1 * 1 * 8  # 1 account * 1 service * 8 sensors
        assert len(entities) == expected_count
        
        # Check advanced sensor types
        sensor_types = [entity._sensor_type for entity in entities]
        assert "daily_average" in sensor_types
        assert "monthly_average" in sensor_types
        assert "peak_usage" in sensor_types
        assert "efficiency" in sensor_types


class TestRedEnergyBaseSensor:
    """Test the base sensor class."""

    def test_base_sensor_initialization(self, mock_coordinator, mock_config_entry):
        """Test base sensor initialization."""
        sensor = RedEnergyBaseSensor(
            mock_coordinator, mock_config_entry, "84953336", "electricity", "test_sensor"
        )
        
        assert sensor._property_id == "84953336"
        assert sensor._service_type == "electricity"
        assert sensor._sensor_type == "test_sensor"
        assert "Unit 8, 4 Prince Street, Coffs Harbour" in sensor._attr_name
        assert sensor._attr_unique_id == "red_energy_test_entry_id_84953336_electricity_test_sensor"

    def test_base_sensor_available(self, mock_coordinator, mock_config_entry):
        """Test sensor availability."""
        sensor = RedEnergyBaseSensor(
            mock_coordinator, mock_config_entry, "84953336", "electricity", "test_sensor"
        )
        
        assert sensor.available is True
        
        # Test unavailable when coordinator fails
        mock_coordinator.last_update_success = False
        assert sensor.available is False


class TestRedEnergyUsageSensor:
    """Test the usage sensor."""

    def test_usage_sensor_initialization_electricity(self, mock_coordinator, mock_config_entry):
        """Test usage sensor initialization for electricity."""
        sensor = RedEnergyUsageSensor(mock_coordinator, mock_config_entry, "84953336", SERVICE_TYPE_ELECTRICITY)
        
        assert sensor._attr_device_class == SensorDeviceClass.ENERGY
        assert sensor._attr_native_unit_of_measurement == UnitOfEnergy.KILO_WATT_HOUR
        assert sensor._attr_state_class == SensorStateClass.TOTAL_INCREASING

    def test_usage_sensor_initialization_gas(self, mock_coordinator, mock_config_entry):
        """Test usage sensor initialization for gas."""
        sensor = RedEnergyUsageSensor(mock_coordinator, mock_config_entry, "84953336", SERVICE_TYPE_GAS)
        
        assert sensor._attr_device_class == SensorDeviceClass.ENERGY
        assert sensor._attr_native_unit_of_measurement == "MJ"
        assert sensor._attr_state_class == SensorStateClass.TOTAL_INCREASING

    def test_usage_sensor_native_value(self, mock_coordinator, mock_config_entry):
        """Test usage sensor native value."""
        sensor = RedEnergyUsageSensor(mock_coordinator, mock_config_entry, "84953336", SERVICE_TYPE_ELECTRICITY)
        
        assert sensor.native_value == 22.1
        mock_coordinator.get_latest_usage.assert_called_once_with("84953336", SERVICE_TYPE_ELECTRICITY)


class TestRedEnergyCostSensor:
    """Test the cost sensor."""

    def test_cost_sensor_initialization(self, mock_coordinator, mock_config_entry):
        """Test cost sensor initialization."""
        sensor = RedEnergyCostSensor(mock_coordinator, mock_config_entry, "84953336", SERVICE_TYPE_ELECTRICITY)
        
        assert sensor._attr_device_class == SensorDeviceClass.MONETARY
        assert sensor._attr_native_unit_of_measurement == "AUD"
        assert sensor._attr_state_class == SensorStateClass.TOTAL

    def test_cost_sensor_native_value(self, mock_coordinator, mock_config_entry):
        """Test cost sensor native value."""
        sensor = RedEnergyCostSensor(mock_coordinator, mock_config_entry, "84953336", SERVICE_TYPE_ELECTRICITY)
        
        assert sensor.native_value == 19.3
        mock_coordinator.get_total_cost.assert_called_once_with("84953336", SERVICE_TYPE_ELECTRICITY)


class TestRedEnergyCostPerUnitSensor:
    """Test the new cost per unit sensor."""

    def test_cost_per_unit_sensor_initialization_electricity(self, mock_coordinator, mock_config_entry):
        """Test cost per unit sensor initialization for electricity."""
        sensor = RedEnergyCostPerUnitSensor(mock_coordinator, mock_config_entry, "84953336", SERVICE_TYPE_ELECTRICITY)
        
        assert sensor._attr_device_class == SensorDeviceClass.MONETARY
        assert sensor._attr_native_unit_of_measurement == "AUD/kWh"
        assert sensor._attr_state_class == SensorStateClass.MEASUREMENT

    def test_cost_per_unit_sensor_initialization_gas(self, mock_coordinator, mock_config_entry):
        """Test cost per unit sensor initialization for gas."""
        sensor = RedEnergyCostPerUnitSensor(mock_coordinator, mock_config_entry, "84953336", SERVICE_TYPE_GAS)
        
        assert sensor._attr_device_class == SensorDeviceClass.MONETARY
        assert sensor._attr_native_unit_of_measurement == "AUD/MJ"
        assert sensor._attr_state_class == SensorStateClass.MEASUREMENT

    def test_cost_per_unit_sensor_native_value(self, mock_coordinator, mock_config_entry):
        """Test cost per unit sensor native value calculation."""
        sensor = RedEnergyCostPerUnitSensor(mock_coordinator, mock_config_entry, "84953336", SERVICE_TYPE_ELECTRICITY)
        
        # 19.3 / 60.8 = 0.3174 AUD/kWh
        expected_value = round(19.3 / 60.8, 4)
        assert sensor.native_value == expected_value
        
        mock_coordinator.get_total_cost.assert_called_with("84953336", SERVICE_TYPE_ELECTRICITY)
        mock_coordinator.get_total_usage.assert_called_with("84953336", SERVICE_TYPE_ELECTRICITY)

    def test_cost_per_unit_sensor_native_value_zero_usage(self, mock_coordinator, mock_config_entry):
        """Test cost per unit sensor with zero usage."""
        mock_coordinator.get_total_usage.return_value = 0.0
        
        sensor = RedEnergyCostPerUnitSensor(mock_coordinator, mock_config_entry, "84953336", SERVICE_TYPE_ELECTRICITY)
        
        assert sensor.native_value is None

    def test_cost_per_unit_sensor_native_value_none_data(self, mock_coordinator, mock_config_entry):
        """Test cost per unit sensor with None data."""
        mock_coordinator.get_total_cost.return_value = None
        mock_coordinator.get_total_usage.return_value = None
        
        sensor = RedEnergyCostPerUnitSensor(mock_coordinator, mock_config_entry, "84953336", SERVICE_TYPE_ELECTRICITY)
        
        assert sensor.native_value is None


class TestRedEnergyTotalUsageSensor:
    """Test the total usage sensor."""

    def test_total_usage_sensor_initialization(self, mock_coordinator, mock_config_entry):
        """Test total usage sensor initialization."""
        sensor = RedEnergyTotalUsageSensor(mock_coordinator, mock_config_entry, "84953336", SERVICE_TYPE_ELECTRICITY)
        
        assert sensor._attr_device_class == SensorDeviceClass.ENERGY
        assert sensor._attr_native_unit_of_measurement == UnitOfEnergy.KILO_WATT_HOUR
        assert sensor._attr_state_class == SensorStateClass.TOTAL

    def test_total_usage_sensor_native_value(self, mock_coordinator, mock_config_entry):
        """Test total usage sensor native value."""
        sensor = RedEnergyTotalUsageSensor(mock_coordinator, mock_config_entry, "84953336", SERVICE_TYPE_ELECTRICITY)
        
        assert sensor.native_value == 60.8
        mock_coordinator.get_total_usage.assert_called_once_with("84953336", SERVICE_TYPE_ELECTRICITY)


class TestRedEnergyDailyAverageSensor:
    """Test the daily average sensor."""

    def test_daily_average_sensor_initialization(self, mock_coordinator, mock_config_entry):
        """Test daily average sensor initialization."""
        sensor = RedEnergyDailyAverageSensor(mock_coordinator, mock_config_entry, "84953336", SERVICE_TYPE_ELECTRICITY)
        
        assert sensor._attr_device_class == SensorDeviceClass.ENERGY
        assert sensor._attr_native_unit_of_measurement == UnitOfEnergy.KILO_WATT_HOUR
        assert sensor._attr_state_class == SensorStateClass.MEASUREMENT

    def test_daily_average_sensor_native_value(self, mock_coordinator, mock_config_entry):
        """Test daily average sensor native value calculation."""
        sensor = RedEnergyDailyAverageSensor(mock_coordinator, mock_config_entry, "84953336", SERVICE_TYPE_ELECTRICITY)
        
        # (20.5 + 18.2 + 22.1) / 3 = 20.27
        expected_value = round((20.5 + 18.2 + 22.1) / 3, 2)
        assert sensor.native_value == expected_value

    def test_daily_average_sensor_native_value_no_data(self, mock_coordinator, mock_config_entry):
        """Test daily average sensor with no data."""
        mock_coordinator.get_service_usage.return_value = {"usage_data": {"usage_data": []}}
        
        sensor = RedEnergyDailyAverageSensor(mock_coordinator, mock_config_entry, "84953336", SERVICE_TYPE_ELECTRICITY)
        
        assert sensor.native_value == 0


class TestRedEnergyMonthlyAverageSensor:
    """Test the monthly average sensor."""

    def test_monthly_average_sensor_initialization(self, mock_coordinator, mock_config_entry):
        """Test monthly average sensor initialization."""
        sensor = RedEnergyMonthlyAverageSensor(mock_coordinator, mock_config_entry, "84953336", SERVICE_TYPE_ELECTRICITY)
        
        assert sensor._attr_device_class == SensorDeviceClass.ENERGY
        assert sensor._attr_native_unit_of_measurement == UnitOfEnergy.KILO_WATT_HOUR
        assert sensor._attr_state_class == SensorStateClass.MEASUREMENT

    def test_monthly_average_sensor_native_value(self, mock_coordinator, mock_config_entry):
        """Test monthly average sensor native value calculation."""
        sensor = RedEnergyMonthlyAverageSensor(mock_coordinator, mock_config_entry, "84953336", SERVICE_TYPE_ELECTRICITY)
        
        # 60.8 * (30.44 / 30) = 61.69
        expected_value = round(60.8 * (30.44 / 30), 2)
        assert sensor.native_value == expected_value


class TestRedEnergyPeakUsageSensor:
    """Test the peak usage sensor."""

    def test_peak_usage_sensor_initialization(self, mock_coordinator, mock_config_entry):
        """Test peak usage sensor initialization."""
        sensor = RedEnergyPeakUsageSensor(mock_coordinator, mock_config_entry, "84953336", SERVICE_TYPE_ELECTRICITY)
        
        assert sensor._attr_device_class == SensorDeviceClass.ENERGY
        assert sensor._attr_native_unit_of_measurement == UnitOfEnergy.KILO_WATT_HOUR
        assert sensor._attr_state_class == SensorStateClass.MEASUREMENT

    def test_peak_usage_sensor_native_value(self, mock_coordinator, mock_config_entry):
        """Test peak usage sensor native value."""
        sensor = RedEnergyPeakUsageSensor(mock_coordinator, mock_config_entry, "84953336", SERVICE_TYPE_ELECTRICITY)
        
        # Peak usage should be 22.1 (highest value in test data)
        assert sensor.native_value == 22.1


class TestRedEnergyEfficiencySensor:
    """Test the efficiency sensor."""

    def test_efficiency_sensor_initialization(self, mock_coordinator, mock_config_entry):
        """Test efficiency sensor initialization."""
        sensor = RedEnergyEfficiencySensor(mock_coordinator, mock_config_entry, "84953336", SERVICE_TYPE_ELECTRICITY)
        
        assert sensor._attr_native_unit_of_measurement == "%"
        assert sensor._attr_state_class == SensorStateClass.MEASUREMENT
        assert sensor._attr_icon == "mdi:leaf"

    def test_efficiency_sensor_native_value(self, mock_coordinator, mock_config_entry):
        """Test efficiency sensor native value calculation."""
        sensor = RedEnergyEfficiencySensor(mock_coordinator, mock_config_entry, "84953336", SERVICE_TYPE_ELECTRICITY)
        
        # Should return a value between 0-100
        value = sensor.native_value
        assert value is not None
        assert 0 <= value <= 100

    def test_efficiency_sensor_insufficient_data(self, mock_coordinator, mock_config_entry):
        """Test efficiency sensor with insufficient data."""
        mock_coordinator.get_service_usage.return_value = {
            "usage_data": {"usage_data": [{"usage": 10.0}]}  # Only 1 day of data
        }
        
        sensor = RedEnergyEfficiencySensor(mock_coordinator, mock_config_entry, "84953336", SERVICE_TYPE_ELECTRICITY)
        
        assert sensor.native_value is None


class TestDataValidationIntegration:
    """Test integration with data validation changes."""

    def test_sensor_handles_new_data_structure(self, mock_coordinator, mock_config_entry):
        """Test that sensors handle the new data validation structure."""
        # Test with the new data structure from our validation changes
        new_usage_data = {
            "84953336": {
                "property": {
                    "id": "84953336",
                    "name": "Unit 8, 4 Prince Street, Coffs Harbour",
                    "services": [
                        {
                            "type": "electricity",
                            "consumer_number": "4373002210",
                            "active": True,
                            "nmi": "4407105303",
                        }
                    ],
                },
                "services": {
                    "electricity": {
                        "consumer_number": "4373002210",
                        "usage_data": {
                            "consumer_number": "4373002210",
                            "from_date": "2025-08-09",
                            "to_date": "2025-09-06",
                            "usage_data": [
                                {"date": "2025-08-09", "usage": 20.5, "cost": 6.5, "unit": "kWh"},
                            ],
                            "total_usage": 20.5,
                            "total_cost": 6.5,
                        },
                        "last_updated": "2025-09-06T10:00:00Z",
                    }
                }
            }
        }
        
        mock_coordinator.data = {
            "customer": MOCK_CUSTOMER_DATA,
            "properties": [MOCK_PROPERTY_DATA],
            "usage_data": new_usage_data,
            "last_update": datetime.now().isoformat(),
        }
        
        # Test that sensors can handle the new structure
        sensor = RedEnergyCostPerUnitSensor(mock_coordinator, mock_config_entry, "84953336", SERVICE_TYPE_ELECTRICITY)
        
        # Should calculate cost per unit correctly
        expected_value = round(6.5 / 20.5, 4)
        assert sensor.native_value == expected_value
