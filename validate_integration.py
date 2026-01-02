#!/usr/bin/env python3
"""Quick test validation - run imports and basic checks"""

import sys
import traceback

test_results = {}

print("=" * 70)
print("ASTRAGUARD-AI TEST VALIDATION")
print("=" * 70)

# Test 1: Error Handling Module
print("\n[1] Testing Error Handling Module...")
try:
    from core.error_handling import (
        AstraGuardException,
        ModelLoadError,
        AnomalyEngineError,
        PolicyEvaluationError,
        StateTransitionError,
        ErrorSeverity,
        ErrorContext,
        classify_error,
        log_error,
        handle_component_error,
        safe_execute,
    )
    from core.component_health import ComponentHealth, SystemHealthMonitor, HealthStatus
    print("✅ Error handling module loaded successfully")
    test_results["error_handling"] = "PASS"
except Exception as e:
    print(f"❌ Error handling module failed: {e}")
    test_results["error_handling"] = "FAIL"
    traceback.print_exc()

# Test 2: Mission Phase Policy Engine
print("\n[2] Testing Mission Phase Policy Engine...")
try:
    from state_machine.mission_phase_policy_engine import (
        MissionPhasePolicyEngine,
        SeverityLevel,
        EscalationLevel,
        PolicyDecision,
    )
    from config.mission_phase_policy_loader import MissionPhasePolicyLoader
    
    loader = MissionPhasePolicyLoader()
    engine = MissionPhasePolicyEngine(loader.get_policy())
    print("✅ Mission phase policy engine initialized")
    test_results["policy_engine"] = "PASS"
except Exception as e:
    print(f"❌ Mission phase policy engine failed: {e}")
    test_results["policy_engine"] = "FAIL"
    traceback.print_exc()

# Test 3: State Machine
print("\n[3] Testing State Machine...")
try:
    from state_machine.state_engine import StateMachine, MissionPhase, SystemState
    
    sm = StateMachine()
    phase = sm.get_current_phase()
    print(f"✅ State machine initialized (phase: {phase.value})")
    test_results["state_machine"] = "PASS"
except Exception as e:
    print(f"❌ State machine failed: {e}")
    test_results["state_machine"] = "FAIL"
    traceback.print_exc()

# Test 4: Phase-Aware Handler
print("\n[4] Testing Phase-Aware Anomaly Handler...")
try:
    from anomaly_agent.phase_aware_handler import PhaseAwareAnomalyHandler
    
    handler = PhaseAwareAnomalyHandler(sm, loader)
    print("✅ Phase-aware anomaly handler initialized")
    test_results["phase_aware_handler"] = "PASS"
except Exception as e:
    print(f"❌ Phase-aware handler failed: {e}")
    test_results["phase_aware_handler"] = "FAIL"
    traceback.print_exc()

# Test 5: Anomaly Detection
print("\n[5] Testing Anomaly Detection...")
try:
    from anomaly.anomaly_detector import detect_anomaly
    
    data = {"voltage": 8.0, "temperature": 25.0, "gyro": 0.01}
    is_anomalous, score = detect_anomaly(data)
    print(f"✅ Anomaly detection working (anomalous: {is_anomalous}, score: {score:.2f})")
    test_results["anomaly_detection"] = "PASS"
except Exception as e:
    print(f"❌ Anomaly detection failed: {e}")
    test_results["anomaly_detection"] = "FAIL"
    traceback.print_exc()

# Test 6: Memory Store
print("\n[6] Testing Memory Store...")
try:
    from memory_engine.memory_store import AdaptiveMemoryStore
    import numpy as np
    
    memory = AdaptiveMemoryStore()
    embedding = np.random.rand(10)
    memory.write(embedding, {"severity": 0.5})
    print("✅ Memory store working")
    test_results["memory_store"] = "PASS"
except Exception as e:
    print(f"❌ Memory store failed: {e}")
    test_results["memory_store"] = "FAIL"
    traceback.print_exc()

# Test 7: Recurrence Scorer
print("\n[7] Testing Recurrence Scorer...")
try:
    from memory_engine.recurrence_scorer import RecurrenceScorer
    
    scorer = RecurrenceScorer()
    print("✅ Recurrence scorer initialized")
    test_results["recurrence_scorer"] = "PASS"
except Exception as e:
    print(f"❌ Recurrence scorer failed: {e}")
    test_results["recurrence_scorer"] = "FAIL"
    traceback.print_exc()

# Test 8: End-to-End Flow
print("\n[8] Testing End-to-End Flow...")
try:
    # Create an anomaly
    decision = handler.handle_anomaly(
        anomaly_type='power_fault',
        severity_score=0.75,
        confidence=0.85
    )
    
    assert 'recommended_action' in decision
    assert 'mission_phase' in decision
    print(f"✅ End-to-end flow working (action: {decision['recommended_action']})")
    test_results["end_to_end"] = "PASS"
except Exception as e:
    print(f"❌ End-to-end flow failed: {e}")
    test_results["end_to_end"] = "FAIL"
    traceback.print_exc()

# Summary
print("\n" + "=" * 70)
print("TEST SUMMARY")
print("=" * 70)

passed = sum(1 for v in test_results.values() if v == "PASS")
failed = sum(1 for v in test_results.values() if v == "FAIL")

for test_name, result in test_results.items():
    status = "✅" if result == "PASS" else "❌"
    print(f"{status} {test_name}: {result}")

print(f"\nTotal: {passed}/{len(test_results)} tests passed")

if failed > 0:
    print(f"⚠️  {failed} tests failed")
    sys.exit(1)
else:
    print("✅ All validation tests passed!")
    sys.exit(0)
