#!/usr/bin/env python3
"""Run all tests and report results"""

import subprocess
import sys

test_files = [
    "tests/test_mission_phase_policy_engine.py",
    "tests/test_phase_aware_anomaly_flow.py",
    "tests/test_memory_store.py",
    "tests/test_recurrence_scorer.py",
    "tests/test_error_handling.py",
]

print("=" * 70)
print("Running All Test Suites")
print("=" * 70)

total_passed = 0
total_failed = 0
results = []

for test_file in test_files:
    print(f"\n▶ Running {test_file}...")
    try:
        result = subprocess.run(
            [sys.executable, "-m", "pytest", test_file, "-q", "--tb=no"],
            capture_output=True,
            text=True,
            timeout=60
        )
        
        if result.returncode == 0:
            # Extract passed count from output
            output_lines = result.stdout.strip().split("\n")
            last_line = output_lines[-1] if output_lines else ""
            if "passed" in last_line:
                passed = int(last_line.split()[0])
                total_passed += passed
                results.append(f"✅ {test_file}: {passed} passed")
                print(f"  ✅ {passed} tests passed")
            else:
                results.append(f"✅ {test_file}: OK")
                print(f"  ✅ Tests passed")
        else:
            failed_line = result.stdout.strip().split("\n")[-1] if result.stdout else "Unknown error"
            results.append(f"❌ {test_file}: {failed_line}")
            print(f"  ❌ Failed: {failed_line}")
            total_failed += 1
            
    except subprocess.TimeoutExpired:
        results.append(f"⏱️  {test_file}: Timeout")
        print(f"  ⏱️  Timeout")
        total_failed += 1
    except Exception as e:
        results.append(f"❌ {test_file}: {str(e)}")
        print(f"  ❌ Error: {str(e)}")
        total_failed += 1

print("\n" + "=" * 70)
print("TEST SUMMARY")
print("=" * 70)
for result in results:
    print(result)

print(f"\nTotal: {total_passed} tests passed")
if total_failed > 0:
    print(f"⚠️  {total_failed} test suites had issues")
else:
    print("✅ All test suites completed successfully!")

sys.exit(0 if total_failed == 0 else 1)
