#!/usr/bin/env python3
"""
Quick verification that all components are integrated and working
"""
import sys
import traceback

def test_error_handling_module():
    """Test error handling module"""
    try:
        from core.error_handling import (
            AstraGuardException,
            ModelLoadError,
            AnomalyEngineError,
            PolicyEvaluationError,
            StateTransitionError,
            MemoryEngineError,
            ErrorSeverity,
            ErrorContext,
        )
        print("✓ Error handling module imports")
        return True
    except Exception as e:
        print(f"✗ Error handling module: {e}")
        traceback.print_exc()
        return False

def test_component_health_module():
    """Test component health module"""
    try:
        from core.component_health import (
            SystemHealthMonitor,
            ComponentHealth,
            HealthStatus,
        )
        monitor = SystemHealthMonitor()
        print("✓ Component health module imports and initializes")
        return True
    except Exception as e:
        print(f"✗ Component health module: {e}")
        traceback.print_exc()
        return False

def test_anomaly_detector():
    """Test anomaly detector with error handling"""
    try:
        from anomaly.anomaly_detector import detect_anomaly, load_model
        load_model()
        result = detect_anomaly({"voltage": 8.0, "temperature": 25.0, "gyro": 0.0})
        print(f"✓ Anomaly detector works: {result}")
        return True
    except Exception as e:
        print(f"✗ Anomaly detector: {e}")
        traceback.print_exc()
        return False

def test_state_machine():
    """Test state machine with error handling"""
    try:
        from state_machine.state_engine import StateMachine, MissionPhase
        sm = StateMachine()
        current = sm.get_current_phase()
        print(f"✓ State machine initialized: {current}")
        sm.set_phase(MissionPhase.NOMINAL_OPS)
        print(f"✓ Phase transition works: {sm.get_current_phase()}")
        return True
    except Exception as e:
        print(f"✗ State machine: {e}")
        traceback.print_exc()
        return False

def test_policy_engine():
    """Test policy engine"""
    try:
        from state_machine.mission_phase_policy_engine import MissionPhasePolicyEngine
        from config.mission_phase_policy_loader import MissionPhasePolicyLoader
        loader = MissionPhasePolicyLoader()
        engine = MissionPhasePolicyEngine(loader.get_policy())
        print("✓ Policy engine initialized")
        return True
    except Exception as e:
        print(f"✗ Policy engine: {e}")
        traceback.print_exc()
        return False

def test_phase_aware_handler():
    """Test phase-aware handler"""
    try:
        from anomaly_agent.phase_aware_handler import PhaseAwareAnomalyHandler
        from state_machine.state_engine import StateMachine
        from config.mission_phase_policy_loader import MissionPhasePolicyLoader
        
        sm = StateMachine()
        loader = MissionPhasePolicyLoader()
        handler = PhaseAwareAnomalyHandler(sm, loader)
        print("✓ Phase-aware handler initialized")
        return True
    except Exception as e:
        print(f"✗ Phase-aware handler: {e}")
        traceback.print_exc()
        return False

def main():
    print("=" * 70)
    print("Verifying AstraGuard-AI Error Handling Integration")
    print("=" * 70)
    print()
    
    tests = [
        ("Error Handling Module", test_error_handling_module),
        ("Component Health Module", test_component_health_module),
        ("Anomaly Detector", test_anomaly_detector),
        ("State Machine", test_state_machine),
        ("Policy Engine", test_policy_engine),
        ("Phase-Aware Handler", test_phase_aware_handler),
    ]
    
    results = []
    for name, test_func in tests:
        print(f"Testing {name}...")
        passed = test_func()
        results.append((name, passed))
        print()
    
    print("=" * 70)
    print("Summary")
    print("=" * 70)
    
    passed_count = sum(1 for _, passed in results if passed)
    total_count = len(results)
    
    for name, passed in results:
        status = "✓ PASS" if passed else "✗ FAIL"
        print(f"{status}: {name}")
    
    print()
    print(f"Overall: {passed_count}/{total_count} tests passed")
    
    if passed_count == total_count:
        print("\n✅ All integration tests passed!")
        return 0
    else:
        print(f"\n❌ {total_count - passed_count} integration test(s) failed")
        return 1

if __name__ == "__main__":
    sys.exit(main())
