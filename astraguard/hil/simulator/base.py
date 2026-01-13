"""
Abstract base class and utilities for satellite HIL simulation.

This module provides the foundational SatelliteSimulator abstract base class
that powers all HIL testing for AstraGuard swarm behaviors.
"""

from abc import ABC, abstractmethod
from typing import Dict, Any, List, Optional
from datetime import datetime
from pydantic import BaseModel
import uuid


class TelemetryPacket(BaseModel):
    """Temporary telemetry packet model - will migrate to schemas/telemetry.py in #486."""
    
    timestamp: datetime
    satellite_id: str
    data: Dict[str, Any]


class SatelliteSimulator(ABC):
    """
    Abstract base class for all CubeSat HIL simulation.
    
    Defines the core interface that all satellite simulator implementations must follow,
    including telemetry generation, fault injection, and lifecycle management.
    """
    
    def __init__(self, sat_id: str):
        """
        Initialize a satellite simulator.
        
        Args:
            sat_id: Unique identifier for this satellite
        """
        self.sat_id = sat_id
        self._running = False
        self._telemetry_history: List[TelemetryPacket] = []
    
    @abstractmethod
    async def generate_telemetry(self) -> TelemetryPacket:
        """
        Generate one telemetry packet for this satellite.
        
        Returns:
            TelemetryPacket with current satellite state
        """
        pass
    
    @abstractmethod
    async def inject_fault(
        self, 
        fault_type: str, 
        severity: float = 1.0, 
        duration: float = 60.0
    ) -> None:
        """
        Inject configurable fault into satellite simulation.
        
        Args:
            fault_type: Type of fault to inject (e.g., 'power_brownout', 'thermal_spike')
            severity: Fault severity on scale 0.0-1.0
            duration: Fault duration in seconds
        """
        pass
    
    def start(self) -> None:
        """Mark simulator as running (for orchestration)."""
        self._running = True
    
    def stop(self) -> None:
        """Mark simulator as stopped."""
        self._running = False
    
    def get_telemetry_history(self) -> List[TelemetryPacket]:
        """
        Get copy of telemetry history.
        
        Returns:
            List of all recorded TelemetryPackets
        """
        return self._telemetry_history.copy()
    
    def record_telemetry(self, packet: TelemetryPacket) -> None:
        """
        Internal method: append telemetry packet to history.
        
        Args:
            packet: TelemetryPacket to record
        """
        self._telemetry_history.append(packet)


class StubSatelliteSimulator(SatelliteSimulator):
    """
    Temporary concrete implementation of SatelliteSimulator for testing.
    
    Generates realistic LEO telemetry values and simulates fault states.
    This stub will be replaced by specialized implementations in subsequent PRs.
    """
    
    def __init__(self, sat_id: str):
        """Initialize stub simulator."""
        super().__init__(sat_id)
        self._fault_active = False
        self._fault_type: Optional[str] = None
    
    async def generate_telemetry(self) -> TelemetryPacket:
        """
        Generate LEO satellite telemetry.
        
        Returns telemetry with voltage drop when fault is active.
        """
        import random
        
        timestamp = datetime.now()
        
        # Nadir-pointing attitude quaternion [w, x, y, z]
        attitude_quat = [0.707, 0.0, 0.0, 0.707]
        
        # Simulate voltage drop during power brownout fault
        if self._fault_active and self._fault_type == "power_brownout":
            battery_voltage = 6.5
        else:
            battery_voltage = 8.4
        
        data = {
            "attitude_quat": attitude_quat,
            "battery_voltage": battery_voltage,
            "temperature": 20 + random.uniform(-5, 5),
            "orbit_altitude": 520000,  # LEO altitude in meters
        }
        
        packet = TelemetryPacket(
            timestamp=timestamp,
            satellite_id=self.sat_id,
            data=data
        )
        self.record_telemetry(packet)
        return packet
    
    async def inject_fault(
        self, 
        fault_type: str, 
        severity: float = 1.0, 
        duration: float = 60.0
    ) -> None:
        """
        Inject fault into stub simulator.
        
        Args:
            fault_type: Type of fault
            severity: Fault severity (0.0-1.0)
            duration: Fault duration in seconds
        """
        self._fault_active = True
        self._fault_type = fault_type
        print(
            f"Sat {self.sat_id}: Injected {fault_type} fault "
            f"(severity={severity}, duration={duration}s)"
        )
