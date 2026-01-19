#!/usr/bin/env python3
"""
╔═══════════════════════════════════════════════════════════╗
║                    STAMPEDE SHIELD                        ║
║             Zone Detector for Corner Monitoring           ║
╚═══════════════════════════════════════════════════════════╝

Detects zone occupancy state using ultrasonic + PIR sensor data.
States: CLEAR, OCCUPIED, CROWDED

Author: StampedeShield Team
Version: 2.0
"""

import time
from enum import Enum
from typing import Optional, Dict, List, Tuple


class ZoneState(Enum):
    """Zone occupancy states."""
    CLEAR = "CLEAR"
    OCCUPIED = "OCCUPIED"
    CROWDED = "CROWDED"


class ZoneDetector:
    """
    Detects zone occupancy state for corner monitoring nodes.
    
    States:
    - CLEAR: distance > 200cm for 2+ seconds
    - OCCUPIED: distance < 200cm AND PIR triggered
    - CROWDED: distance < 80cm for 1+ second
    """
    
    def __init__(self, zone_id: str, config: Optional[Dict] = None):
        """
        Initialize the zone detector.
        
        Args:
            zone_id: Zone identifier ("A" or "B")
            config: Dictionary with thresholds:
                - ZONE_CLEAR_DIST: 200 (cm)
                - ZONE_CROWDED_DIST: 80 (cm)
                - CLEAR_CONFIRM_TIME: 2.0 (seconds)
                - CROWDED_CONFIRM_TIME: 1.0 (seconds)
        """
        self.zone_id = zone_id
        
        # Default configuration
        default_config = {
            "ZONE_CLEAR_DIST": 200,
            "ZONE_CROWDED_DIST": 80,
            "CLEAR_CONFIRM_TIME": 2.0,
            "CROWDED_CONFIRM_TIME": 1.0
        }
        
        self.config = {**default_config, **(config or {})}
        
        # Current state
        self.state = ZoneState.CLEAR
        self.state_start_time = 0.0
        
        # Pending state tracking (for time-based confirmation)
        self.pending_state: Optional[ZoneState] = None
        self.pending_start_time: Optional[float] = None
        
        # Sensor values
        self.last_distance = 400.0
        self.last_pir = 0
        self.last_timestamp = 0.0
        
        # Statistics
        self.pir_trigger_count = 0
        self.confirmed_human_count = 0
    
    def process_reading(self, distance: float, pir: int, 
                        timestamp: Optional[float] = None) -> Dict:
        """
        Process sensor readings and determine zone state.
        
        Args:
            distance: Ultrasonic distance in centimeters
            pir: PIR sensor value (0 or 1)
            timestamp: Unix timestamp (uses current time if None)
            
        Returns:
            Dictionary with:
            - zone: Zone ID
            - state: "CLEAR", "OCCUPIED", or "CROWDED"
            - duration: Seconds in current state
            - confirmed_human: Whether PIR validated presence
        """
        if timestamp is None:
            timestamp = time.time()
        
        # Track PIR triggers
        if pir == 1:
            self.pir_trigger_count += 1
        
        # Store previous state
        previous_state = self.state
        
        # Determine target state from readings
        target_state = self._determine_target_state(distance, pir)
        
        # Apply time-based confirmation
        new_state = self._apply_confirmation(target_state, timestamp)
        
        # Update state if changed
        if new_state != previous_state:
            self.state = new_state
            self.state_start_time = timestamp
        
        # Check if human confirmed
        confirmed_human = (pir == 1 and self.state != ZoneState.CLEAR)
        if confirmed_human:
            self.confirmed_human_count += 1
        
        # Store last values
        self.last_distance = distance
        self.last_pir = pir
        self.last_timestamp = timestamp
        
        # Calculate duration in current state
        duration = timestamp - self.state_start_time
        
        return {
            "zone": self.zone_id,
            "state": self.state.value,
            "duration": round(duration, 2),
            "confirmed_human": confirmed_human
        }
    
    def _determine_target_state(self, distance: float, pir: int) -> ZoneState:
        """
        Determine target state based on current readings.
        
        Logic:
        - CROWDED: distance < 80cm
        - OCCUPIED: distance < 200cm AND PIR = 1
        - CLEAR: distance > 200cm
        """
        clear_dist = self.config["ZONE_CLEAR_DIST"]
        crowded_dist = self.config["ZONE_CROWDED_DIST"]
        
        if distance < crowded_dist:
            return ZoneState.CROWDED
        elif distance < clear_dist and pir == 1:
            return ZoneState.OCCUPIED
        elif distance >= clear_dist:
            return ZoneState.CLEAR
        else:
            # Distance < 200 but no PIR - keep current or default to OCCUPIED
            if self.state == ZoneState.CLEAR:
                return ZoneState.CLEAR  # Need PIR to confirm occupancy
            return self.state
    
    def _apply_confirmation(self, target_state: ZoneState, 
                            timestamp: float) -> ZoneState:
        """
        Apply time-based confirmation for state transitions.
        
        - CLEAR requires 2+ seconds
        - CROWDED requires 1+ second
        - OCCUPIED is instant (when PIR confirms)
        """
        # If target matches current state, reset pending
        if target_state == self.state:
            self.pending_state = None
            self.pending_start_time = None
            return self.state
        
        # Get required confirmation time
        confirm_times = {
            ZoneState.CLEAR: self.config["CLEAR_CONFIRM_TIME"],
            ZoneState.CROWDED: self.config["CROWDED_CONFIRM_TIME"],
            ZoneState.OCCUPIED: 0.0  # Instant with PIR
        }
        
        required_time = confirm_times[target_state]
        
        # Instant transitions
        if required_time == 0:
            self.pending_state = None
            self.pending_start_time = None
            return target_state
        
        # Start new pending state
        if target_state != self.pending_state:
            self.pending_state = target_state
            self.pending_start_time = timestamp
            return self.state
        
        # Check if confirmation time met
        if self.pending_start_time is not None:
            elapsed = timestamp - self.pending_start_time
            if elapsed >= required_time:
                self.pending_state = None
                self.pending_start_time = None
                return target_state
        
        return self.state
    
    def get_occupancy_score(self) -> float:
        """
        Calculate occupancy score from 0.0 (empty) to 1.0 (crowded).
        
        Returns:
            Float between 0.0 and 1.0
        """
        clear_dist = self.config["ZONE_CLEAR_DIST"]
        crowded_dist = self.config["ZONE_CROWDED_DIST"]
        
        distance = self.last_distance
        pir = self.last_pir
        
        # Calculate base score from distance
        if distance >= clear_dist:
            distance_score = 0.0
        elif distance <= crowded_dist:
            distance_score = 1.0
        else:
            # Linear interpolation between crowded and clear
            range_size = clear_dist - crowded_dist
            distance_score = (clear_dist - distance) / range_size
        
        # Boost score if PIR is triggered
        if pir == 1:
            distance_score = min(1.0, distance_score + 0.2)
        
        return round(distance_score, 3)
    
    def get_state_info(self) -> Dict:
        """Get current state information."""
        return {
            "zone": self.zone_id,
            "state": self.state.value,
            "occupancy_score": self.get_occupancy_score(),
            "last_distance": self.last_distance,
            "last_pir": self.last_pir,
            "pir_triggers": self.pir_trigger_count,
            "confirmed_humans": self.confirmed_human_count
        }
    
    def reset(self):
        """Reset detector to initial state."""
        self.state = ZoneState.CLEAR
        self.state_start_time = 0.0
        self.pending_state = None
        self.pending_start_time = None
        self.last_distance = 400.0
        self.last_pir = 0
        self.pir_trigger_count = 0
        self.confirmed_human_count = 0


# ═══════════════════════════════════════════════════════════
#                       TEST SUITE
# ═══════════════════════════════════════════════════════════

def print_result(idx: int, distance: float, pir: int, result: Dict):
    """Print formatted test result."""
    state_emoji = {
        "CLEAR": "🟢",
        "OCCUPIED": "🟡", 
        "CROWDED": "🔴"
    }
    pir_emoji = "🔴" if pir == 1 else "⚪"
    emoji = state_emoji.get(result["state"], "⚪")
    
    human = "✓ Human" if result["confirmed_human"] else ""
    
    print(f"  [{idx:2d}] Dist: {distance:5.1f}cm | PIR: {pir_emoji} | "
          f"State: {emoji} {result['state']:10s} | {human}")


def run_test(name: str, detector: ZoneDetector,
             readings: List[Tuple[float, int]], interval_ms: int = 200):
    """Run a test scenario."""
    print(f"\n{'='*60}")
    print(f"TEST: {name}")
    print(f"{'='*60}")
    
    detector.reset()
    base_time = time.time()
    
    for i, (distance, pir) in enumerate(readings):
        timestamp = base_time + (i * interval_ms / 1000.0)
        result = detector.process_reading(distance, pir, timestamp)
        print_result(i, distance, pir, result)
    
    print(f"\n  Final State: {detector.state.value}")
    print(f"  Occupancy Score: {detector.get_occupancy_score()}")
    print(f"  Confirmed Humans: {detector.confirmed_human_count}")


def main():
    """Run all tests."""
    print("\n")
    print("╔═══════════════════════════════════════════════════════════╗")
    print("║                    STAMPEDE SHIELD                        ║")
    print("║              Zone Detector - Test Suite                   ║")
    print("╚═══════════════════════════════════════════════════════════╝")
    
    config = {
        "ZONE_CLEAR_DIST": 200,
        "ZONE_CROWDED_DIST": 80,
        "CLEAR_CONFIRM_TIME": 0.5,    # Reduced for testing
        "CROWDED_CONFIRM_TIME": 0.3   # Reduced for testing
    }
    
    detector = ZoneDetector("A", config)
    
    # ═══════════════════════════════════════════════════════════
    # TEST 1: Zone becomes OCCUPIED
    # ═══════════════════════════════════════════════════════════
    readings_1 = [
        # (distance, pir)
        (300, 0),  # Clear
        (280, 0),  # Clear
        (250, 0),  # Clear
        (180, 0),  # Close but no PIR
        (150, 1),  # Close + PIR = OCCUPIED
        (140, 1),  # Still occupied
        (160, 0),  # No PIR but still close
    ]
    run_test("Zone becomes OCCUPIED (PIR triggered)", detector, readings_1)
    
    # ═══════════════════════════════════════════════════════════
    # TEST 2: Zone becomes CROWDED
    # ═══════════════════════════════════════════════════════════
    readings_2 = [
        (250, 0),   # Clear
        (150, 1),   # Occupied
        (100, 1),   # Getting closer
        (70, 1),    # Very close - becoming crowded
        (60, 1),    # Crowded
        (50, 1),    # Very crowded
        (40, 1),    # Extremely crowded
    ]
    run_test("Zone becomes CROWDED", detector, readings_2)
    
    # ═══════════════════════════════════════════════════════════
    # TEST 3: Zone clears out
    # ═══════════════════════════════════════════════════════════
    readings_3 = [
        (50, 1),    # Crowded
        (80, 1),    # Still crowded
        (120, 0),   # Occupied
        (180, 0),   # Still occupied (no PIR to confirm)
        (220, 0),   # Clearing
        (250, 0),   # Clear
        (280, 0),   # Still clear
        (300, 0),   # Confirmed clear
    ]
    run_test("Zone clears out", detector, readings_3)
    
    # ═══════════════════════════════════════════════════════════
    # TEST 4: Full cycle simulation
    # ═══════════════════════════════════════════════════════════
    print(f"\n{'='*60}")
    print("TEST: Full Cycle Simulation")
    print("="*60)
    
    detector.reset()
    
    # Simulate realistic scenario
    scenario = [
        # Phase 1: Empty zone
        (320, 0), (310, 0), (305, 0), (300, 0),
        # Phase 2: Someone approaches
        (250, 0), (200, 0), (180, 1), (160, 1),
        # Phase 3: Zone occupied
        (140, 1), (130, 0), (150, 1), (145, 0),
        # Phase 4: Getting crowded
        (100, 1), (80, 1), (60, 1), (50, 1),
        # Phase 5: Crowded
        (45, 1), (40, 1), (50, 1), (55, 1),
        # Phase 6: Clearing out
        (80, 0), (120, 0), (180, 0), (220, 0),
        # Phase 7: Clear again
        (260, 0), (290, 0), (310, 0), (320, 0),
    ]
    
    base_time = time.time()
    
    print("\n  Phase progression:\n")
    phases = [
        (0, "Empty zone"),
        (4, "Approaching"),
        (8, "Occupied"),
        (12, "Getting crowded"),
        (16, "Crowded"),
        (20, "Clearing out"),
        (24, "Clear again")
    ]
    
    phase_idx = 0
    for i, (distance, pir) in enumerate(scenario):
        timestamp = base_time + (i * 0.2)
        
        # Print phase header
        if phase_idx < len(phases) and i == phases[phase_idx][0]:
            print(f"\n  📍 {phases[phase_idx][1]}:")
            phase_idx += 1
        
        result = detector.process_reading(distance, pir, timestamp)
        print_result(i, distance, pir, result)
    
    print(f"\n  ═══════════════════════════════")
    print(f"  Final Statistics:")
    print(f"  ═══════════════════════════════")
    info = detector.get_state_info()
    print(f"  Zone: {info['zone']}")
    print(f"  State: {info['state']}")
    print(f"  Occupancy Score: {info['occupancy_score']}")
    print(f"  PIR Triggers: {info['pir_triggers']}")
    print(f"  Confirmed Humans: {info['confirmed_humans']}")
    
    print("\n✓ All tests complete!\n")


if __name__ == "__main__":
    main()