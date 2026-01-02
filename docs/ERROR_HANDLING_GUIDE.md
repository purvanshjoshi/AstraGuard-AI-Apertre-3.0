# Centralized Error Handling & Graceful Degradation

## Overview

AstraGuard-AI implements a centralized error-handling and graceful degradation layer that ensures system resilience. When core components encounter errors, the system:

1. **Catches** the error via centralized error-handling utilities
2. **Classifies** the error by type and severity
3. **Logs** structured error information with context
4. **Activates** appropriate fallback behavior
5. **Marks** the system status as DEGRADED (if applicable)
6. **Continues** normal operation instead of crashing

## Key Components

### 1. Error Handling Module (`core/error_handling.py`)

Provides custom exception hierarchy and error handling utilities:

```python
# Custom Exceptions (domain-specific)
- ModelLoadError          # Model initialization failures
- AnomalyEngineError      # Anomaly detection failures
- PolicyEvaluationError   # Policy evaluation failures
- StateTransitionError    # State machine failures
- MemoryEngineError       # Memory store failures

# Error Severity Levels
- CRITICAL    # System-level failure
- HIGH        # Component failure, fallback needed
- MEDIUM      # Operation failure, retry recommended
- LOW         # Non-critical warning

# Key Functions
- classify_error()        # Classify exception into ErrorContext
- log_error()             # Structured error logging
- handle_component_error()# Decorator for error handling
- safe_execute()          # Execute function with built-in error handling
```

### 2. Health Monitoring (`core/component_health.py`)

Centralized system health monitoring:

```python
# Component Health Status
- HEALTHY     # Operating normally
- DEGRADED    # Using fallback, but functional
- FAILED      # Unrecoverable state
- UNKNOWN     # Status not yet determined

# SystemHealthMonitor (Singleton)
- register_component()    # Register a component for monitoring
- mark_healthy()          # Mark component as healthy
- mark_degraded()         # Mark component as degraded with error
- mark_failed()           # Mark component as failed
- is_system_healthy()     # Check overall system status
- is_system_degraded()    # Check if system is degraded
- get_system_status()     # Get full status JSON
```

## Graceful Degradation Behavior

### Model Loading / Anomaly Engine

**Failure Scenario:** Model file missing or corrupted

**What Happens:**
1. `load_model()` catches the error
2. System switches to heuristic mode (conservative thresholds)
3. Logs: `{"component": "anomaly_detector", "status": "DEGRADED", "mode": "heuristic"}`
4. Anomaly detection continues using fallback logic
5. Dashboard shows "⚠️ DEGRADED" status

**Code:**
```python
from anomaly.anomaly_detector import detect_anomaly

is_anomalous, score = detect_anomaly(telemetry_data)
# Returns safe defaults even if model is unavailable
```

### Anomaly Detection / Policy Evaluation

**Failure Scenario:** Invalid telemetry data or policy engine error

**What Happens:**
1. Error is caught in `handle_anomaly()` or `evaluate()`
2. Function returns safe default decision (NO_ACTION, LOG_ONLY)
3. Logs structured error with mission phase and anomaly context
4. System continues processing next telemetry tick
5. No cascading failures to dashboard or state machine

**Code:**
```python
from anomaly_agent.phase_aware_handler import PhaseAwareAnomalyHandler

decision = handler.handle_anomaly(
    anomaly_type='power_fault',
    severity_score=0.75,
    confidence=0.85
)
# Returns {"recommended_action": "LOG_ONLY", ...} even on error
```

### State Machine / State Transitions

**Failure Scenario:** Invalid phase transition or state update error

**What Happens:**
1. `set_phase()` catches StateTransitionError
2. State reverts to last known-good state
3. Logs: `{"component": "state_machine", "status": "DEGRADED", "reason": "invalid_transition"}`
4. System continues in safe fallback state
5. Prevents impossible state combinations

**Code:**
```python
from state_machine.state_engine import StateMachine, MissionPhase

try:
    state_machine.set_phase(MissionPhase.NOMINAL_OPS)
except StateTransitionError as e:
    # Already handled internally with fallback to safe state
    pass
```

## Structured Logging

All errors are logged with consistent structured information:

```python
{
    "timestamp": "2026-01-02T10:30:45.123456",
    "error_type": "AnomalyEngineError",
    "component": "anomaly_detector",
    "severity": "high",
    "message": "Invalid input data",
    "context": {
        "mission_phase": "NOMINAL_OPS",
        "severity_score": -0.5,
        "fallback_activated": True
    }
}
```

This enables:
- Easy debugging and issue tracking
- Monitoring for degradation patterns
- Audit trails for safety-critical operations
- Integration with external logging systems

## Dashboard Integration

The dashboard can query system health status:

```python
from core.component_health import SystemHealthMonitor

monitor = SystemHealthMonitor()
status = monitor.get_system_status()

# Returns:
{
    "overall_status": "degraded",  # or "healthy", "failed"
    "component_counts": {
        "healthy": 5,
        "degraded": 1,
        "failed": 0
    },
    "components": {
        "anomaly_detector": {
            "status": "degraded",
            "last_error": "Model file not found",
            "fallback_active": True
        },
        ...
    }
}
```

**Dashboard Display:**
```
🟢 System Status: HEALTHY
🟡 System Status: DEGRADED  ⚠️ 1 component degraded
🔴 System Status: FAILED    ❌ System non-operational
```

## Configuration

Error handling behavior can be customized via environment variables or config files:

```python
# Environment Variables
ASTRAGUARD_ENABLE_FALLBACKS=true       # Enable graceful degradation
ASTRAGUARD_ERROR_LOG_LEVEL=DEBUG       # Logging level
ASTRAGUARD_DEGRADATION_THRESHOLD=1    # Max degraded components before system FAILED

# Config File (future)
error_handling:
  enable_fallbacks: true
  log_structured: true
  degradation_threshold: 1
```

## Testing Error Handling

Example test for graceful degradation:

```python
def test_anomaly_detector_handles_invalid_input():
    """Test that anomaly detector gracefully handles invalid input."""
    from anomaly.anomaly_detector import detect_anomaly
    
    # Invalid input should not crash
    is_anomalous, score = detect_anomaly(None)
    
    assert isinstance(is_anomalous, bool)
    assert 0 <= score <= 1
    # System continues with safe default

def test_policy_engine_fallback_on_invalid_phase():
    """Test that policy engine handles invalid phase gracefully."""
    from state_machine.mission_phase_policy_engine import MissionPhasePolicyEngine
    
    engine = MissionPhasePolicyEngine(policy)
    
    # Invalid phase should not crash
    decision = engine.evaluate(
        mission_phase=None,  # Invalid
        anomaly_type='power_fault',
        severity_score=0.75
    )
    
    # Returns safe decision
    assert decision['recommended_action'] == 'LOG_ONLY'
```

## Best Practices

1. **Always use centralized error handling** - Don't add custom try/except blocks
   
2. **Return safe defaults on error** - Never let an error propagate and crash
   
3. **Log with context** - Include mission phase, severity, component name
   
4. **Mark degradation clearly** - Don't silently fail; update health status
   
5. **Monitor health status** - Dashboard should show HEALTHY/DEGRADED/FAILED
   
6. **Test failure scenarios** - Verify fallback behavior works as expected

## Files Modified

- `core/error_handling.py` - Central error handling utilities
- `core/component_health.py` - System health monitoring
- `anomaly/anomaly_detector.py` - Integrated error handling + fallback mode
- `state_machine/state_engine.py` - Integrated error handling for transitions
- `state_machine/mission_phase_policy_engine.py` - Integrated error handling for policies
- `tests/test_error_handling.py` - Comprehensive test suite
