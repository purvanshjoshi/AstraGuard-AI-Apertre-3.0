"""Tests for HIL satellite simulator base class."""

import pytest
from astraguard.hil.simulator.base import (
    SatelliteSimulator,
    StubSatelliteSimulator,
    TelemetryPacket,
)


@pytest.mark.asyncio
async def test_base_class_structure():
    """Test SatelliteSimulator base class structure through stub implementation."""
    sim = StubSatelliteSimulator("SAT001")
    
    # Test telemetry generation
    packet = await sim.generate_telemetry()
    assert isinstance(packet, TelemetryPacket)
    assert packet.satellite_id == "SAT001"
    assert "battery_voltage" in packet.data
    assert "attitude_quat" in packet.data
    assert "temperature" in packet.data
    assert "orbit_altitude" in packet.data
    
    # Test fault injection
    await sim.inject_fault("power_brownout", severity=0.8, duration=30.0)
    
    # Test history
    history = sim.get_telemetry_history()
    assert len(history) > 0
    assert history[0].satellite_id == "SAT001"


@pytest.mark.asyncio
async def test_lifecycle():
    """Test simulator lifecycle methods."""
    sim = StubSatelliteSimulator("SAT002")
    
    # Test initial state
    assert sim._running is False
    
    # Test start
    sim.start()
    assert sim._running is True
    
    # Test stop
    sim.stop()
    assert sim._running is False


@pytest.mark.asyncio
async def test_telemetry_history():
    """Test telemetry history tracking."""
    sim = StubSatelliteSimulator("SAT003")
    
    # Generate multiple packets
    for _ in range(5):
        await sim.generate_telemetry()
    
    history = sim.get_telemetry_history()
    assert len(history) == 5
    
    # Verify history is a copy (not reference)
    history.clear()
    new_history = sim.get_telemetry_history()
    assert len(new_history) == 5


@pytest.mark.asyncio
async def test_fault_injection_voltage_drop():
    """Test that power_brownout fault causes voltage drop."""
    sim = StubSatelliteSimulator("SAT004")
    
    # Normal operation
    normal_packet = await sim.generate_telemetry()
    normal_voltage = normal_packet.data["battery_voltage"]
    assert normal_voltage == 8.4
    
    # Inject fault
    await sim.inject_fault("power_brownout")
    
    # Fault operation
    fault_packet = await sim.generate_telemetry()
    fault_voltage = fault_packet.data["battery_voltage"]
    assert fault_voltage == 6.5
    assert fault_voltage < normal_voltage


@pytest.mark.asyncio
async def test_multiple_satellites():
    """Test multiple independent simulator instances."""
    sim1 = StubSatelliteSimulator("SAT_A")
    sim2 = StubSatelliteSimulator("SAT_B")
    
    packet1 = await sim1.generate_telemetry()
    packet2 = await sim2.generate_telemetry()
    
    assert packet1.satellite_id == "SAT_A"
    assert packet2.satellite_id == "SAT_B"
    assert packet1.data is not packet2.data
