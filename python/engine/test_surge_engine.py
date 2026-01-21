#!/usr/bin/env python3
"""Test SurgeEngine with simulated data."""

import sys
import time
sys.path.insert(0, '..')

from surge_engine import SurgeEngine

def test_state_transitions():
    print("=== SurgeEngine State Transition Test ===\n")
    
    engine = SurgeEngine()
    
    # Scenario 1: CLEAR/NORMAL state
    print("--- Scenario 1: Normal Conditions ---")
    normal_data = {
        "A": {"dist": 250, "pir": 0, "wifi": 3, "sound": 40},
        "B": {"dist": 280, "pir": 0, "wifi": 2, "sound": 35},
        "C": {"dist": 300, "pir": 0, "wifi": 2, "sound": 30}
    }
    for _ in range(5):
        result = engine.process(normal_data)
        time.sleep(0.1)
    print(f"State: {result.state}, Risk: {result.risk_score}")
    assert result.risk_score < 0.4, f"Expected low risk, got {result.risk_score}"
    
    # Scenario 2: ELEVATED state - increasing crowd
    print("\n--- Scenario 2: Busy Conditions ---")
    busy_data = {
        "A": {"dist": 80, "pir": 1, "wifi": 15, "sound": 65},
        "B": {"dist": 100, "pir": 1, "wifi": 12, "sound": 60},
        "C": {"dist": 120, "pir": 0, "wifi": 10, "sound": 55}
    }
    for _ in range(10):
        result = engine.process(busy_data)
        time.sleep(0.1)
    print(f"State: {result.state}, Risk: {result.risk_score}")
    print(f"Devices: {result.device_count}, Clusters: {result.cluster_count}")
    
    # Scenario 3: CRITICAL/SURGE state
    print("\n--- Scenario 3: Surge Conditions ---")
    surge_data = {
        "A": {"dist": 30, "pir": 1, "wifi": 30, "sound": 90},
        "B": {"dist": 40, "pir": 1, "wifi": 28, "sound": 85},
        "C": {"dist": 35, "pir": 1, "wifi": 25, "sound": 88}
    }
    for _ in range(15):
        result = engine.process(surge_data)
        time.sleep(0.1)
    print(f"State: {result.state}, Risk: {result.risk_score}")
    print(f"Devices: {result.device_count}, Clusters: {result.cluster_count}")
    print(f"Velocity: {result.velocity}")
    
    # Visualize zone states
    print(f"\nZone States: {result.zone_states}")
    
    print("\n=== Test Completed Successfully ===")

if __name__ == "__main__":
    test_state_transitions()
