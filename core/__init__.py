"""
AstraGuard Core - Error Handling & Health Management

This package provides centralized error handling, graceful degradation,
and system health monitoring for AstraGuard components.
"""

from .error_handling import (
    AstraGuardException,
    ModelLoadError,
    AnomalyEngineError,
    PolicyEvaluationError,
    StateTransitionError,
    MemoryEngineError,
    handle_component_error,
    safe_execute,
)
from .component_health import (
    ComponentHealth,
    SystemHealthMonitor,
    HealthStatus,
)

__all__ = [
    # Exceptions
    "AstraGuardException",
    "ModelLoadError",
    "AnomalyEngineError",
    "PolicyEvaluationError",
    "StateTransitionError",
    "MemoryEngineError",
    # Error handling
    "handle_component_error",
    "safe_execute",
    # Health monitoring
    "ComponentHealth",
    "SystemHealthMonitor",
    "HealthStatus",
]
