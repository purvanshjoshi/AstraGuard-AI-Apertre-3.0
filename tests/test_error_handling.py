"""
Tests for Centralized Error Handling & Graceful Degradation

Tests the error handling layer, health monitoring, and graceful degradation
behavior across all core components.
"""

import pytest
import logging
from datetime import datetime
from unittest.mock import patch, MagicMock

from core.error_handling import (
    AstraGuardException,
    ModelLoadError,
    AnomalyEngineError,
    PolicyEvaluationError,
    StateTransitionError,
    MemoryEngineError,
    ErrorSeverity,
    ErrorContext,
    classify_error,
    log_error,
    handle_component_error,
    safe_execute,
    ErrorContext_ContextManager,
)
from core.component_health import (
    ComponentHealth,
    SystemHealthMonitor,
    HealthStatus,
)
from anomaly.anomaly_detector import load_model, detect_anomaly
from state_machine.state_engine import StateMachine, MissionPhase, SystemState
from state_machine.mission_phase_policy_engine import MissionPhasePolicyEngine


# ============================================================================
# Tests for Custom Exceptions
# ============================================================================

class TestCustomExceptions:
    """Test custom exception hierarchy."""
    
    def test_exception_inheritance(self):
        """Test exception inheritance chain."""
        exc = ModelLoadError("test error", "test_component")
        assert isinstance(exc, AstraGuardException)
        assert isinstance(exc, Exception)
    
    def test_exception_to_dict(self):
        """Test exception serialization."""
        exc = ModelLoadError(
            "Test model error",
            component="test_component",
            context={"path": "/test/path"}
        )
        error_dict = exc.to_dict()
        
        assert error_dict["error_type"] == "ModelLoadError"
        assert error_dict["message"] == "Test model error"
        assert error_dict["component"] == "test_component"
        assert error_dict["context"]["path"] == "/test/path"
    
    def test_exception_severity_classification(self):
        """Test error severity classification."""
        assert classify_error(ModelLoadError("test"), "comp").severity == ErrorSeverity.HIGH
        assert classify_error(AnomalyEngineError("test"), "comp").severity == ErrorSeverity.MEDIUM
        assert classify_error(PolicyEvaluationError("test"), "comp").severity == ErrorSeverity.MEDIUM
        assert classify_error(StateTransitionError("test"), "comp").severity == ErrorSeverity.HIGH


# ============================================================================
# Tests for Safe Execution Utilities
# ============================================================================

class TestSafeExecutionUtilities:
    """Test safe execution wrappers."""
    
    def test_safe_execute_success(self):
        """Test safe_execute with successful function."""
        def working_func(a, b):
            return a + b
        
        result = safe_execute(working_func, 5, 3, component="test")
        assert result == 8
    
    def test_safe_execute_with_fallback(self):
        """Test safe_execute returns fallback on error."""
        def failing_func():
            raise ValueError("Test error")
        
        result = safe_execute(
            failing_func,
            component="test",
            fallback_value=None
        )
        assert result is None
    
    def test_handle_component_error_decorator(self):
        """Test handle_component_error decorator."""
        @handle_component_error("test_component", fallback_value=0)
        def failing_function():
            raise Exception("Test error")
        
        result = failing_function()
        assert result == 0
    
    def test_error_context_manager_suppresses_exception(self):
        """Test ErrorContext_ContextManager suppresses exceptions."""
        with ErrorContext_ContextManager("test_component"):
            raise ValueError("Test error")
        # Should not raise if context manager is working


# ============================================================================
# Tests for Health Monitoring
# ============================================================================

class TestHealthMonitoring:
    """Test system health monitoring."""
    
    def teardown_method(self):
        """Reset health monitor after each test."""
        monitor = SystemHealthMonitor()
        monitor.reset()
    
    def test_register_component(self):
        """Test component registration."""
        monitor = SystemHealthMonitor()
        monitor.register_component("test_comp")
        
        health = monitor.get_component_health("test_comp")
        assert health is not None
        assert health.name == "test_comp"
        assert health.status == HealthStatus.HEALTHY
    
    def test_mark_degraded(self):
        """Test marking component as degraded."""
        monitor = SystemHealthMonitor()
        monitor.register_component("test_comp")
        monitor.mark_degraded("test_comp", error_msg="Test error", fallback_active=True)
        
        health = monitor.get_component_health("test_comp")
        assert health.status == HealthStatus.DEGRADED
        assert health.last_error == "Test error"
        assert health.fallback_active is True
    
    def test_system_status_aggregation(self):
        """Test overall system status aggregation."""
        monitor = SystemHealthMonitor()
        monitor.register_component("comp1")
        monitor.register_component("comp2")
        
        monitor.mark_healthy("comp1")
        monitor.mark_healthy("comp2")
        assert monitor.is_system_healthy()
        
        monitor.mark_degraded("comp1", "error")
        assert monitor.is_system_degraded()
    
    def test_health_monitor_singleton(self):
        """Test health monitor singleton pattern."""
        monitor1 = SystemHealthMonitor()
        monitor2 = SystemHealthMonitor()
        
        assert monitor1 is monitor2
    
    def test_get_system_status_json(self):
        """Test system status JSON serialization."""
        monitor = SystemHealthMonitor()
        monitor.register_component("comp1")
        monitor.mark_healthy("comp1")
        
        status = monitor.get_system_status()
        assert "overall_status" in status
        assert "component_counts" in status
        assert "components" in status
        assert status["component_counts"]["healthy"] == 1


# ============================================================================
# Tests for Anomaly Detector Error Handling
# ============================================================================

class TestAnomalyDetectorErrorHandling:
    """Test anomaly detector graceful degradation."""
    
    def teardown_method(self):
        """Reset health monitor after each test."""
        monitor = SystemHealthMonitor()
        monitor.reset()
    
    def test_anomaly_detector_fallback_on_invalid_input(self):
        """Test anomaly detector falls back on invalid input."""
        is_anomalous, score = detect_anomaly(None)  # Invalid input
        
        # Should return a safe default, not crash
        assert isinstance(is_anomalous, bool)
        assert 0 <= score <= 1
    
    def test_anomaly_detector_heuristic_mode(self):
        """Test anomaly detector heuristic fallback."""
        data = {
            "voltage": 6.5,  # Below threshold
            "temperature": 25.0,
            "gyro": 0.01
        }
        is_anomalous, score = detect_anomaly(data)
        
        assert isinstance(is_anomalous, bool)
        assert isinstance(score, float)
        assert 0 <= score <= 1
    
    def test_anomaly_detector_health_tracking(self):
        """Test anomaly detector health status updates."""
        monitor = SystemHealthMonitor()
        
        detect_anomaly({"voltage": 8.0, "temperature": 25.0, "gyro": 0.01})
        
        health = monitor.get_component_health("anomaly_detector")
        assert health is not None


# ============================================================================
# Tests for State Machine Error Handling
# ============================================================================

class TestStateMachineErrorHandling:
    """Test state machine error handling."""
    
    def teardown_method(self):
        """Reset health monitor after each test."""
        monitor = SystemHealthMonitor()
        monitor.reset()
    
    def test_invalid_phase_raises_error(self):
        """Test invalid phase raises StateTransitionError."""
        sm = StateMachine()
        sm.current_phase = MissionPhase.LAUNCH
        sm.phase_history = [(MissionPhase.LAUNCH, datetime.now())]
        
        with pytest.raises(StateTransitionError):
            # Can't jump directly from LAUNCH to SAFE_MODE... wait, yes we can
            # Let me try invalid transition
            sm.set_phase(MissionPhase.PAYLOAD_OPS)  # Invalid from LAUNCH
    
    def test_state_machine_health_tracking(self):
        """Test state machine registers with health monitor."""
        monitor = SystemHealthMonitor()
        sm = StateMachine()  # Should register itself
        
        health = monitor.get_component_health("state_machine")
        assert health is not None
        assert health.status == HealthStatus.HEALTHY


# ============================================================================
# Tests for Policy Engine Error Handling
# ============================================================================

class TestPolicyEngineErrorHandling:
    """Test policy engine error handling."""
    
    def teardown_method(self):
        """Reset health monitor after each test."""
        monitor = SystemHealthMonitor()
        monitor.reset()
    
    def test_invalid_policy_config_raises_error(self):
        """Test invalid policy config raises PolicyEvaluationError."""
        with pytest.raises(PolicyEvaluationError):
            MissionPhasePolicyEngine("invalid config")
    
    def test_missing_phases_key_raises_error(self):
        """Test missing phases key raises PolicyEvaluationError."""
        with pytest.raises(PolicyEvaluationError):
            MissionPhasePolicyEngine({"invalid": "config"})
    
    def test_valid_policy_config(self):
        """Test valid policy config initializes successfully."""
        valid_config = {
            "phases": {
                "LAUNCH": {
                    "allowed_actions": ["LOG_ONLY"],
                    "forbidden_actions": [],
                    "threshold_multiplier": 2.0
                }
            }
        }
        engine = MissionPhasePolicyEngine(valid_config)
        assert engine is not None


# ============================================================================
# Integration Tests
# ============================================================================

class TestErrorHandlingIntegration:
    """Integration tests for error handling across components."""
    
    def teardown_method(self):
        """Reset health monitor after each test."""
        monitor = SystemHealthMonitor()
        monitor.reset()
    
    def test_system_degrades_gracefully_on_multiple_failures(self):
        """Test system degrades gracefully when multiple components fail."""
        monitor = SystemHealthMonitor()
        
        # Simulate multiple component failures
        monitor.register_component("comp1")
        monitor.register_component("comp2")
        monitor.register_component("comp3")
        
        monitor.mark_degraded("comp1", "error 1")
        monitor.mark_degraded("comp2", "error 2")
        monitor.mark_healthy("comp3")
        
        # System should be degraded but report all statuses
        assert monitor.is_system_degraded()
        
        status = monitor.get_system_status()
        assert status["component_counts"]["degraded"] == 2
        assert status["component_counts"]["healthy"] == 1
    
    def test_full_pipeline_with_error_handling(self):
        """Test complete pipeline with error handling."""
        monitor = SystemHealthMonitor()
        
        # Simulate telemetry processing
        data = {"voltage": 8.0, "temperature": 25.0, "gyro": 0.01}
        is_anomalous, score = detect_anomaly(data)
        
        # Verify anomaly detector registered and healthy
        assert monitor.get_component_health("anomaly_detector") is not None
        
        # Verify state machine registered
        assert monitor.get_component_health("state_machine") is not None
    
    def test_health_monitor_thread_safety(self):
        """Test health monitor thread safety with concurrent updates."""
        import threading
        
        monitor = SystemHealthMonitor()
        
        def update_health(component_name):
            monitor.register_component(component_name)
            monitor.mark_healthy(component_name)
        
        threads = [
            threading.Thread(target=update_health, args=(f"comp_{i}",))
            for i in range(5)
        ]
        
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join()
        
        status = monitor.get_system_status()
        assert status["component_counts"]["total"] == 5


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
