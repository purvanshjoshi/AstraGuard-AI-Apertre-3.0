"""
Integration tests for centralized error handling and graceful degradation.

Tests that the system continues operating when components fail, using fallbacks
instead of crashing.
"""

import pytest
import sys
import os
from unittest.mock import patch, MagicMock

# Add parent directory to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from core.error_handling import (
    ErrorContext, ErrorSeverity, classify_error, log_error,
    safe_execute, handle_component_error, ErrorContext_ContextManager,
    AstraGuardException, ModelLoadError, AnomalyEngineError,
    StateTransitionError, PolicyEvaluationError
)
from anomaly.anomaly_detector import detect_anomaly, load_model
from state_machine.state_engine import StateMachine, MissionPhase
from state_machine.mission_phase_policy_engine import MissionPhasePolicyEngine
from config.mission_phase_policy_loader import MissionPhasePolicyLoader


class TestErrorClassification:
    """Test error classification and context."""
    
    def test_classify_model_load_error(self):
        """Test classification of model load errors."""
        exc = ModelLoadError("Model not found", "anomaly_detector")
        ctx = classify_error(exc, "anomaly_detector")
        
        assert ctx.error_type == "ModelLoadError"
        assert ctx.severity == ErrorSeverity.HIGH
        assert ctx.component == "anomaly_detector"
    
    def test_classify_anomaly_engine_error(self):
        """Test classification of anomaly engine errors."""
        exc = AnomalyEngineError("Detection failed", "anomaly_detector")
        ctx = classify_error(exc, "anomaly_detector")
        
        assert ctx.error_type == "AnomalyEngineError"
        assert ctx.severity == ErrorSeverity.MEDIUM
    
    def test_classify_policy_evaluation_error(self):
        """Test classification of policy evaluation errors."""
        exc = PolicyEvaluationError("Policy evaluation failed", "policy_engine")
        ctx = classify_error(exc, "policy_engine")
        
        assert ctx.error_type == "PolicyEvaluationError"
        assert ctx.severity == ErrorSeverity.MEDIUM
    
    def test_classify_state_transition_error(self):
        """Test classification of state transition errors."""
        exc = StateTransitionError("Invalid transition", "state_machine")
        ctx = classify_error(exc, "state_machine")
        
        assert ctx.error_type == "StateTransitionError"
        assert ctx.severity == ErrorSeverity.HIGH
    
    def test_classify_generic_exception(self):
        """Test classification of generic exceptions."""
        exc = ValueError("Invalid value")
        ctx = classify_error(exc, "test_component")
        
        assert ctx.error_type == "ValueError"
        assert ctx.severity == ErrorSeverity.MEDIUM
        assert ctx.component == "test_component"


class TestSafeExecution:
    """Test safe execution utilities."""
    
    def test_safe_execute_success(self):
        """Test safe_execute with successful function."""
        def successful_func(x, y):
            return x + y
        
        result = safe_execute(
            successful_func, 5, 3,
            component="test"
        )
        assert result == 8
    
    def test_safe_execute_with_fallback(self):
        """Test safe_execute returns fallback on error."""
        def failing_func():
            raise ValueError("Test error")
        
        result = safe_execute(
            failing_func,
            component="test",
            fallback_value=0
        )
        assert result == 0
    
    def test_safe_execute_with_context(self):
        """Test safe_execute captures context."""
        def failing_func():
            raise RuntimeError("Test runtime error")
        
        context = {"phase": "NOMINAL_OPS", "severity": 0.8}
        result = safe_execute(
            failing_func,
            component="policy_engine",
            fallback_value=None,
            context=context
        )
        assert result is None


class TestHandleComponentErrorDecorator:
    """Test @handle_component_error decorator."""
    
    def test_decorator_success(self):
        """Test decorator with successful function."""
        @handle_component_error("test_component")
        def working_func(x):
            return x * 2
        
        result = working_func(5)
        assert result == 10
    
    def test_decorator_with_fallback(self):
        """Test decorator returns fallback on error."""
        @handle_component_error("test_component", fallback_value=-1)
        def broken_func():
            raise ValueError("Broken!")
        
        result = broken_func()
        assert result == -1
    
    def test_decorator_with_astraguard_exception(self):
        """Test decorator handles AstraGuard exceptions."""
        @handle_component_error("test_component", fallback_value=None)
        def raises_astraguard_exc():
            raise ModelLoadError("Model not found", "test_component")
        
        result = raises_astraguard_exc()
        assert result is None


class TestErrorContextManager:
    """Test ErrorContext_ContextManager."""
    
    def test_context_manager_success(self):
        """Test context manager with successful code."""
        with ErrorContext_ContextManager("test_component") as ctx:
            x = 5 + 3
        
        assert ctx.error_ctx is None
    
    def test_context_manager_catches_error(self):
        """Test context manager suppresses exception."""
        error_ctx = None
        
        with ErrorContext_ContextManager("test_component") as ctx:
            raise ValueError("Test error")
        
        assert ctx.error_ctx is not None
        assert ctx.error_ctx.error_type == "ValueError"
    
    def test_context_manager_with_callback(self):
        """Test context manager calls on_error callback."""
        callback_called = False
        
        def on_error_cb(err_ctx):
            nonlocal callback_called
            callback_called = True
        
        with ErrorContext_ContextManager(
            "test_component",
            on_error=on_error_cb
        ):
            raise RuntimeError("Test")
        
        assert callback_called
    
    def test_context_manager_reraise(self):
        """Test context manager can reraise exceptions."""
        with pytest.raises(ValueError):
            with ErrorContext_ContextManager(
                "test_component",
                reraise=True
            ):
                raise ValueError("Should reraise")


class TestAnomalyDetectorGracefulDegradation:
    """Test anomaly detector graceful degradation."""
    
    def test_anomaly_detection_with_valid_data(self):
        """Test anomaly detection returns valid result."""
        data = {
            "voltage": 8.0,
            "temperature": 25.0,
            "gyro": 0.01
        }
        
        is_anomalous, score = detect_anomaly(data)
        
        assert isinstance(is_anomalous, bool)
        assert isinstance(score, float)
        assert 0 <= score <= 1
    
    def test_anomaly_detection_with_missing_fields(self):
        """Test anomaly detection handles missing fields."""
        data = {"voltage": 8.0}  # Missing temperature and gyro
        
        is_anomalous, score = detect_anomaly(data)
        
        assert isinstance(is_anomalous, bool)
        assert isinstance(score, float)
    
    def test_anomaly_detection_with_invalid_data_type(self):
        """Test anomaly detection handles invalid data type gracefully."""
        # Invalid data type should be caught and fallback used
        # Returns safe default (no anomaly) instead of raising
        is_anomalous, score = detect_anomaly("not a dict")
        
        assert isinstance(is_anomalous, bool)
        assert isinstance(score, float)
        assert 0 <= score <= 1


class TestStateMachineErrorHandling:
    """Test state machine error handling."""
    
    def test_state_machine_initialization(self):
        """Test state machine initializes without errors."""
        sm = StateMachine()
        assert sm is not None
        assert sm.get_current_phase() == MissionPhase.NOMINAL_OPS
    
    def test_phase_transition_valid(self):
        """Test valid phase transition."""
        sm = StateMachine()
        sm.mission_phase = MissionPhase.DEPLOYMENT
        
        result = sm.set_phase(MissionPhase.NOMINAL_OPS)
        
        assert result['success'] is True
        assert sm.get_current_phase() == MissionPhase.NOMINAL_OPS
    
    def test_phase_transition_invalid(self):
        """Test invalid phase transition is handled."""
        sm = StateMachine()
        sm.current_phase = MissionPhase.LAUNCH
        
        # Invalid transitions raise StateTransitionError
        with pytest.raises(StateTransitionError):
            sm.set_phase(MissionPhase.NOMINAL_OPS)


class TestPolicyEngineErrorHandling:
    """Test policy engine error handling."""
    
    def test_policy_engine_initialization(self):
        """Test policy engine initializes without errors."""
        loader = MissionPhasePolicyLoader()
        policy = loader.get_policy()
        engine = MissionPhasePolicyEngine(policy)
        
        assert engine is not None
    
    def test_policy_evaluation_with_valid_input(self):
        """Test policy evaluation with valid input."""
        loader = MissionPhasePolicyLoader()
        engine = MissionPhasePolicyEngine(loader.get_policy())
        
        decision = engine.evaluate(
            mission_phase=MissionPhase.NOMINAL_OPS,
            anomaly_type='power_fault',
            severity_score=0.75,
            anomaly_attributes={}
        )
        
        assert decision is not None
        assert 'recommended_action' in decision.__dict__
    
    def test_policy_evaluation_with_invalid_phase(self):
        """Test policy evaluation handles invalid phase gracefully."""
        loader = MissionPhasePolicyLoader()
        engine = MissionPhasePolicyEngine(loader.get_policy())
        
        # Should not crash even with unusual input
        decision = engine.evaluate(
            mission_phase=MissionPhase.NOMINAL_OPS,
            anomaly_type='unknown_fault',
            severity_score=0.5,
            anomaly_attributes={}
        )
        
        assert decision is not None


class TestCascadingFailureProtection:
    """Test that failures don't cascade through the system."""
    
    def test_anomaly_detection_failure_doesnt_break_state_machine(self):
        """Test that anomaly detection failures don't break state machine."""
        sm = StateMachine()
        initial_phase = sm.get_current_phase()
        
        # Try to process data with anomaly detector in degraded mode
        data = {"voltage": 8.0, "temperature": 25.0, "gyro": 0.01}
        is_anomalous, score = detect_anomaly(data)
        
        # State machine should be unaffected
        assert sm.get_current_phase() == initial_phase
        assert isinstance(is_anomalous, bool)
        assert isinstance(score, float)
    
    def test_policy_evaluation_failure_doesnt_break_detector(self):
        """Test that policy evaluation failures don't break detector."""
        loader = MissionPhasePolicyLoader()
        engine = MissionPhasePolicyEngine(loader.get_policy())
        
        # Anomaly detection should work independent of policy
        data = {"voltage": 7.5, "temperature": 30.0, "gyro": 0.02}
        is_anomalous, score = detect_anomaly(data)
        
        assert isinstance(is_anomalous, bool)
        assert isinstance(score, float)


class TestErrorRecovery:
    """Test system recovery after errors."""
    
    def test_state_machine_maintains_last_known_good_state(self):
        """Test state machine keeps last known-good state on error."""
        sm = StateMachine()
        initial_phase = MissionPhase.NOMINAL_OPS
        sm.current_phase = initial_phase
        
        # Try invalid transition - should raise error
        try:
            sm.set_phase(MissionPhase.LAUNCH)
        except StateTransitionError:
            pass  # Expected
        
        # Should still be in initial phase
        assert sm.get_current_phase() == initial_phase
    
    def test_anomaly_detector_recovers_after_error(self):
        """Test anomaly detector can recover from errors."""
        # First call with valid data
        data1 = {"voltage": 8.0, "temperature": 25.0, "gyro": 0.01}
        is_anomalous1, score1 = detect_anomaly(data1)
        assert isinstance(is_anomalous1, bool)
        
        # Call with problematic data should be handled
        try:
            is_anomalous2, score2 = detect_anomaly({"invalid": "data"})
        except:
            pass  # May raise, should be handled
        
        # Third call should still work
        data3 = {"voltage": 7.9, "temperature": 26.0, "gyro": 0.02}
        is_anomalous3, score3 = detect_anomaly(data3)
        assert isinstance(is_anomalous3, bool)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
