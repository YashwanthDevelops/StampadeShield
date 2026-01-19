#!/usr/bin/env python3
"""
╔═══════════════════════════════════════════════════════════╗
║                    STAMPEDE SHIELD                        ║
║              Passage Detector for Doorways                ║
╚═══════════════════════════════════════════════════════════╝

Counts passage events using ultrasonic sensor distance readings.
Implements a state machine to accurately detect people passing through.

Author: StampedeShield Team
Version: 2.0
"""

import time
from collections import deque
from enum import Enum
from typing import Optional, Dict, List


class PassageState(Enum):
    """States for the passage detection state machine."""
    BASELINE = "BASELINE"       # Doorway is clear
    APPROACH = "APPROACH"       # Someone approaching
    PASSAGE = "PASSAGE"         # Someone passing through
    COOLDOWN = "COOLDOWN"       # Waiting before next detection


class PassageDetector:
    """
    Detects and counts passage events through a doorway.
    
    Uses a state machine to track:
    - BASELINE: Doorway clear (~300cm)
    - APPROACH: Someone getting closer (<150cm)
    - PASSAGE: Someone passing through (<50cm for 200ms+)
    - COOLDOWN: Brief pause to avoid double-counting
    
    Also calculates:
    - Flow rate (passages per minute)
    - Velocity (rate of change of flow)
    """
    
    def __init__(self, config: Optional[Dict] = None):
        """
        Initialize the passage detector.
        
        Args:
            config: Dictionary with thresholds:
                - PASSAGE_THRESHOLD: Distance (cm) to count as passage (default: 50)
                - PRESENCE_THRESHOLD: Distance (cm) to detect approach (default: 150)
                - MIN_PASSAGE_DURATION: Minimum ms at close range (default: 200)
                - PASSAGE_COOLDOWN: Cooldown ms between passages (default: 800)
                - BASELINE_DISTANCE: Expected empty doorway distance (default: 300)
                - RETURN_THRESHOLD: Distance (cm) to return to baseline (default: 150)
                - RETURN_DURATION: Minimum ms at far range to reset (default: 500)
        """
        # Default configuration
        default_config = {
            "PASSAGE_THRESHOLD": 50,        # cm - someone is passing
            "PRESENCE_THRESHOLD": 150,      # cm - someone approaching
            "MIN_PASSAGE_DURATION": 200,    # ms - minimum time for valid passage
            "PASSAGE_COOLDOWN": 800,        # ms - cooldown between passages
            "BASELINE_DISTANCE": 300,       # cm - empty doorway
            "RETURN_THRESHOLD": 150,        # cm - distance to return to baseline
            "RETURN_DURATION": 500          # ms - time at far range to reset
        }
        
        # Merge provided config with defaults
        self.config = {**default_config, **(config or {})}
        
        # State machine
        self.state = PassageState.BASELINE
        self.state_enter_time = 0.0
        
        # Passage counting
        self.passage_count = 0
        self.passage_timestamps: deque = deque(maxlen=1000)  # Store last 1000 passages
        
        # Tracking variables
        self.last_distance = self.config["BASELINE_DISTANCE"]
        self.close_start_time: Optional[float] = None
        self.far_start_time: Optional[float] = None
        self.cooldown_start_time: Optional[float] = None
        
        # Flow rate tracking
        self.flow_rate_history: deque = deque(maxlen=60)  # Last 60 flow rate samples
        self.last_flow_rate = 0.0
        self.last_flow_rate_time = 0.0
        
        # Statistics
        self.total_approaches = 0
        self.false_approaches = 0  # Approached but didn't pass
        self.min_distance_seen = self.config["BASELINE_DISTANCE"]
    
    def process_reading(self, distance: float, timestamp: Optional[float] = None) -> Dict:
        """
        Process a single ultrasonic distance reading.
        
        Args:
            distance: Distance reading in centimeters
            timestamp: Unix timestamp (uses current time if None)
            
        Returns:
            Dictionary with:
            - event: "PASSAGE", "APPROACH", "CLEAR", or None
            - count: Total passage count
            - state: Current state name
            - flow_rate: Current passages per minute
        """
        if timestamp is None:
            timestamp = time.time()
        
        # Convert timestamp to milliseconds for internal use
        ts_ms = timestamp * 1000
        
        # Track minimum distance for debugging
        if distance < self.min_distance_seen:
            self.min_distance_seen = distance
        
        # Store last distance
        self.last_distance = distance
        
        # Initialize result
        result = {
            "event": None,
            "count": self.passage_count,
            "state": self.state.value,
            "flow_rate": self.get_flow_rate()
        }
        
        # State machine processing
        if self.state == PassageState.BASELINE:
            result = self._process_baseline(distance, ts_ms, result)
            
        elif self.state == PassageState.APPROACH:
            result = self._process_approach(distance, ts_ms, result)
            
        elif self.state == PassageState.PASSAGE:
            result = self._process_passage(distance, ts_ms, result)
            
        elif self.state == PassageState.COOLDOWN:
            result = self._process_cooldown(distance, ts_ms, result)
        
        # Update result with latest count and state
        result["count"] = self.passage_count
        result["state"] = self.state.value
        
        return result
    
    def _process_baseline(self, distance: float, ts_ms: float, result: Dict) -> Dict:
        """Process reading in BASELINE state."""
        presence_threshold = self.config["PRESENCE_THRESHOLD"]
        
        if distance < presence_threshold:
            # Someone is approaching
            self._change_state(PassageState.APPROACH, ts_ms)
            self.total_approaches += 1
            result["event"] = "APPROACH"
        
        return result
    
    def _process_approach(self, distance: float, ts_ms: float, result: Dict) -> Dict:
        """Process reading in APPROACH state."""
        passage_threshold = self.config["PASSAGE_THRESHOLD"]
        baseline_distance = self.config["BASELINE_DISTANCE"]
        min_duration = self.config["MIN_PASSAGE_DURATION"]
        
        if distance < passage_threshold:
            # Very close - potential passage
            if self.close_start_time is None:
                self.close_start_time = ts_ms
            
            # Check if close long enough
            close_duration = ts_ms - self.close_start_time
            if close_duration >= min_duration:
                # Valid passage detected!
                self._register_passage(ts_ms)
                self._change_state(PassageState.PASSAGE, ts_ms)
                result["event"] = "PASSAGE"
        else:
            # Reset close timer if not close enough
            self.close_start_time = None
            
            # Check if returning to baseline
            if distance > self.config["RETURN_THRESHOLD"]:
                if self.far_start_time is None:
                    self.far_start_time = ts_ms
                
                far_duration = ts_ms - self.far_start_time
                if far_duration >= self.config["RETURN_DURATION"]:
                    # Person left without passing
                    self._change_state(PassageState.BASELINE, ts_ms)
                    self.false_approaches += 1
                    result["event"] = "CLEAR"
                    self.far_start_time = None
            else:
                self.far_start_time = None
        
        return result
    
    def _process_passage(self, distance: float, ts_ms: float, result: Dict) -> Dict:
        """Process reading in PASSAGE state."""
        return_threshold = self.config["RETURN_THRESHOLD"]
        return_duration = self.config["RETURN_DURATION"]
        
        if distance > return_threshold:
            # Person is leaving
            if self.far_start_time is None:
                self.far_start_time = ts_ms
            
            far_duration = ts_ms - self.far_start_time
            if far_duration >= return_duration:
                # Transition to cooldown
                self._change_state(PassageState.COOLDOWN, ts_ms)
                self.cooldown_start_time = ts_ms
                self.far_start_time = None
        else:
            # Reset far timer if still close
            self.far_start_time = None
        
        return result
    
    def _process_cooldown(self, distance: float, ts_ms: float, result: Dict) -> Dict:
        """Process reading in COOLDOWN state."""
        cooldown_duration = self.config["PASSAGE_COOLDOWN"]
        
        if self.cooldown_start_time is not None:
            elapsed = ts_ms - self.cooldown_start_time
            if elapsed >= cooldown_duration:
                # Cooldown complete
                self._change_state(PassageState.BASELINE, ts_ms)
                self.cooldown_start_time = None
                result["event"] = "CLEAR"
        
        return result
    
    def _change_state(self, new_state: PassageState, ts_ms: float):
        """Change to a new state."""
        self.state = new_state
        self.state_enter_time = ts_ms
        self.close_start_time = None
    
    def _register_passage(self, ts_ms: float):
        """Register a valid passage event."""
        self.passage_count += 1
        self.passage_timestamps.append(ts_ms / 1000.0)  # Store as seconds
        self.min_distance_seen = self.config["BASELINE_DISTANCE"]  # Reset
    
    def get_flow_rate(self, window_seconds: int = 60) -> float:
        """
        Calculate passages per minute over a time window.
        
        Args:
            window_seconds: Time window in seconds (default: 60)
            
        Returns:
            Float representing passages per minute
        """
        if not self.passage_timestamps:
            return 0.0
        
        now = time.time()
        cutoff = now - window_seconds
        
        # Count passages within window
        recent_passages = sum(1 for ts in self.passage_timestamps if ts >= cutoff)
        
        # Calculate rate (passages per minute)
        rate = (recent_passages / window_seconds) * 60
        
        return round(rate, 2)
    
    def get_velocity(self) -> float:
        """
        Calculate rate of change of flow rate (acceleration).
        
        Positive = flow increasing
        Negative = flow decreasing
        Zero = stable flow
        
        Returns:
            Float representing change in passages per minute per minute
        """
        current_rate = self.get_flow_rate(window_seconds=30)
        now = time.time()
        
        # Store for velocity calculation
        self.flow_rate_history.append((now, current_rate))
        
        # Need at least 2 samples
        if len(self.flow_rate_history) < 2:
            return 0.0
        
        # Compare to rate from 30 seconds ago
        old_time, old_rate = self.flow_rate_history[0]
        time_diff = now - old_time
        
        if time_diff < 1:
            return 0.0
        
        # Calculate velocity (change per minute)
        velocity = ((current_rate - old_rate) / time_diff) * 60
        
        return round(velocity, 2)
    
    def get_statistics(self) -> Dict:
        """
        Get detailed statistics about passage detection.
        
        Returns:
            Dictionary with various statistics
        """
        return {
            "passage_count": self.passage_count,
            "total_approaches": self.total_approaches,
            "false_approaches": self.false_approaches,
            "conversion_rate": (
                round(self.passage_count / self.total_approaches * 100, 1)
                if self.total_approaches > 0 else 0
            ),
            "flow_rate_1min": self.get_flow_rate(60),
            "flow_rate_5min": self.get_flow_rate(300),
            "velocity": self.get_velocity(),
            "current_state": self.state.value,
            "min_distance_seen": self.min_distance_seen
        }
    
    def reset(self):
        """Reset all counters and state."""
        self.state = PassageState.BASELINE
        self.state_enter_time = 0.0
        self.passage_count = 0
        self.passage_timestamps.clear()
        self.flow_rate_history.clear()
        self.total_approaches = 0
        self.false_approaches = 0
        self.close_start_time = None
        self.far_start_time = None
        self.cooldown_start_time = None
        self.last_distance = self.config["BASELINE_DISTANCE"]
        self.min_distance_seen = self.config["BASELINE_DISTANCE"]
        self.last_flow_rate = 0.0


# ═══════════════════════════════════════════════════════════
#                       TEST SUITE
# ═══════════════════════════════════════════════════════════

def run_test(name: str, detector: PassageDetector, readings: List[float], 
             interval_ms: int = 100, expected_count: int = None):
    """
    Run a test scenario.
    
    Args:
        name: Test name
        detector: PassageDetector instance
        readings: List of distance readings
        interval_ms: Time between readings in ms
        expected_count: Expected passage count
    """
    print(f"\n{'='*60}")
    print(f"TEST: {name}")
    print(f"{'='*60}")
    print(f"Readings: {readings}")
    print(f"Interval: {interval_ms}ms between readings")
    print()
    
    detector.reset()
    base_time = time.time()
    
    events = []
    
    for i, distance in enumerate(readings):
        timestamp = base_time + (i * interval_ms / 1000.0)
        result = detector.process_reading(distance, timestamp)
        
        # Print state transitions
        event_str = f"  [{i:2d}] Dist: {distance:5.1f}cm → State: {result['state']:10s}"
        if result["event"]:
            event_str += f" | Event: {result['event']}"
            events.append(result["event"])
        print(event_str)
    
    # Final results
    print()
    print(f"Results:")
    print(f"  Passages Detected: {detector.passage_count}")
    print(f"  Events: {events}")
    
    if expected_count is not None:
        if detector.passage_count == expected_count:
            print(f"  ✓ PASS (expected {expected_count})")
        else:
            print(f"  ✗ FAIL (expected {expected_count}, got {detector.passage_count})")
    
    return detector.passage_count


def main():
    """Run all tests."""
    print("\n")
    print("╔═══════════════════════════════════════════════════════════╗")
    print("║                    STAMPEDE SHIELD                        ║")
    print("║              Passage Detector - Test Suite                ║")
    print("╚═══════════════════════════════════════════════════════════╝")
    
    # Create detector with default config
    config = {
        "PASSAGE_THRESHOLD": 50,
        "PRESENCE_THRESHOLD": 150,
        "MIN_PASSAGE_DURATION": 200,
        "PASSAGE_COOLDOWN": 800,
        "BASELINE_DISTANCE": 300,
        "RETURN_THRESHOLD": 150,
        "RETURN_DURATION": 500
    }
    
    detector = PassageDetector(config)
    
    # ═══════════════════════════════════════════════════════════
    # TEST 1: Normal person walking through
    # ═══════════════════════════════════════════════════════════
    readings_1 = [300, 250, 200, 150, 100, 60, 40, 35, 40, 60, 100, 150, 200, 250, 300]
    run_test(
        "Person walks through doorway",
        detector,
        readings_1,
        interval_ms=100,  # 100ms between readings = realistic sensor rate
        expected_count=1
    )
    
    # ═══════════════════════════════════════════════════════════
    # TEST 2: Person approaches but turns back
    # ═══════════════════════════════════════════════════════════
    readings_2 = [300, 250, 200, 150, 100, 80, 100, 150, 200, 250, 300, 300, 300, 300, 300]
    run_test(
        "Person approaches but leaves (no passage)",
        detector,
        readings_2,
        interval_ms=100,
        expected_count=0
    )
    
    # ═══════════════════════════════════════════════════════════
    # TEST 3: Two people quickly passing
    # ═══════════════════════════════════════════════════════════
    # Need enough time between passages for cooldown
    readings_3 = [
        300,  # Baseline
        100, 50, 40, 35, 40, 50, 100,  # First person
        200, 250, 300,  # Clear
        300, 300, 300, 300, 300, 300, 300, 300, 300,  # Cooldown (800ms)
        100, 50, 40, 35, 40, 50, 100,  # Second person
        200, 250, 300   # Clear
    ]
    run_test(
        "Two people passing (with cooldown gap)",
        detector,
        readings_3,
        interval_ms=100,
        expected_count=2
    )
    
    # ═══════════════════════════════════════════════════════════
    # TEST 4: Quick pass (too fast - should still count)
    # ═══════════════════════════════════════════════════════════
    readings_4 = [300, 100, 40, 40, 40, 100, 300, 300, 300]
    run_test(
        "Quick pass (edge case)",
        detector,
        readings_4,
        interval_ms=100,  # 300ms at close range
        expected_count=1
    )
    
    # ═══════════════════════════════════════════════════════════
    # TEST 5: Too brief (should NOT count)
    # ═══════════════════════════════════════════════════════════
    readings_5 = [300, 100, 40, 100, 300, 300]
    run_test(
        "Too brief pass (only 100ms close - should NOT count)",
        detector,
        readings_5,
        interval_ms=100,  # Only 100ms at close range
        expected_count=0
    )
    
    # ═══════════════════════════════════════════════════════════
    # TEST 6: Person standing in doorway
    # ═══════════════════════════════════════════════════════════
    readings_6 = [300, 100, 50, 40, 40, 40, 40, 40, 40, 40, 40, 100, 300, 300]
    run_test(
        "Person standing in doorway (single passage)",
        detector,
        readings_6,
        interval_ms=100,
        expected_count=1
    )
    
    # ═══════════════════════════════════════════════════════════
    # TEST 7: Noisy readings (realistic sensor noise)
    # ═══════════════════════════════════════════════════════════
    readings_7 = [
        298, 302, 295,  # Baseline noise
        180, 155, 140,  # Approach
        85, 55, 42, 38, 45, 52,  # Pass through
        95, 140, 175, 210,  # Leaving
        280, 295, 305, 298  # Back to baseline
    ]
    run_test(
        "Noisy sensor readings (realistic)",
        detector,
        readings_7,
        interval_ms=100,
        expected_count=1
    )
    
    # ═══════════════════════════════════════════════════════════
    # SUMMARY
    # ═══════════════════════════════════════════════════════════
    print("\n")
    print("═" * 60)
    print("TEST SUMMARY")
    print("═" * 60)
    
    stats = detector.get_statistics()
    print(f"  Final Statistics:")
    print(f"    Total Passages: {stats['passage_count']}")
    print(f"    Total Approaches: {stats['total_approaches']}")
    print(f"    False Approaches: {stats['false_approaches']}")
    print(f"    Conversion Rate: {stats['conversion_rate']}%")
    print()
    
    # ═══════════════════════════════════════════════════════════
    # LIVE SIMULATION
    # ═══════════════════════════════════════════════════════════
    print("\n")
    print("═" * 60)
    print("LIVE SIMULATION (5 seconds)")
    print("═" * 60)
    print("Simulating real-time readings...\n")
    
    detector.reset()
    
    # Simulate 5 seconds of readings at 5Hz (every 200ms)
    import random
    
    start_time = time.time()
    simulated_time = start_time
    
    # Simulate: approach, pass, clear, approach, pass, clear
    pattern = (
        [300] * 5 +      # 1 sec baseline
        [200, 150, 100, 60, 45, 40, 45, 60, 100, 150, 200] +  # 2.2 sec pass
        [250, 300] * 5 + # 2 sec cooldown
        [200, 100, 50, 40, 50, 100, 200] +  # 1.4 sec pass
        [250, 300] * 3   # Clear
    )
    
    for i, dist in enumerate(pattern):
        # Add some noise
        noisy_dist = dist + random.uniform(-5, 5)
        noisy_dist = max(10, noisy_dist)
        
        result = detector.process_reading(noisy_dist, simulated_time)
        
        if result["event"]:
            elapsed = simulated_time - start_time
            print(f"  [{elapsed:5.2f}s] {result['event']:10s} | Count: {result['count']} | Flow: {result['flow_rate']:.1f}/min")
        
        simulated_time += 0.2  # 200ms intervals
    
    print(f"\nFinal Count: {detector.passage_count}")
    print(f"Flow Rate: {detector.get_flow_rate():.1f} passages/min")
    print(f"Velocity: {detector.get_velocity():.2f} (change/min)")
    
    print("\n✓ All tests complete!\n")


if __name__ == "__main__":
    main()