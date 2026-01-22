"""
╔═══════════════════════════════════════════════════════════╗
║                    STAMPEDE SHIELD                        ║
║              Surge Engine - Risk Calculator               ║
╚═══════════════════════════════════════════════════════════╝

Combines all processor data to calculate overall risk score.
Implements the 5-state model: CLEAR → NORMAL → ELEVATED → CRITICAL → SURGE

Author: StampedeShield Team
Version: 2.0
"""

import time
from typing import Dict, Optional, List, Tuple
from enum import Enum
from collections import deque

# Import processors
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

try:
    from processors.passage_detector import PassageDetector
    from processors.device_tracker import DeviceTracker
    from processors.cluster_detector import ClusterDetector
    from processors.zone_detector import ZoneDetector
except ImportError:
    # Fallback if running standalone
    PassageDetector = None
    DeviceTracker = None
    ClusterDetector = None
    ZoneDetector = None


class SystemState(Enum):
    """System-wide state levels."""
    CLEAR = 0
    NORMAL = 1
    ELEVATED = 2
    CRITICAL = 3
    SURGE = 4


class SurgeEngine:
    """
    Central risk calculation engine.
    
    Combines data from all sensors and processors to:
    1. Calculate component risk scores
    2. Apply weighted combination
    3. Determine system state with hysteresis
    4. Track state history
    """
    
    # State thresholds (risk score 0.0 - 1.0)
    STATE_THRESHOLDS = [0.15, 0.35, 0.55, 0.75]
    
    # State colors for visualization
    STATE_COLORS = {
        SystemState.CLEAR: "#22c55e",      # Green
        SystemState.NORMAL: "#3b82f6",     # Blue
        SystemState.ELEVATED: "#eab308",   # Yellow
        SystemState.CRITICAL: "#f97316",   # Orange
        SystemState.SURGE: "#ef4444"       # Red
    }
    
    def __init__(self, config: Optional[Dict] = None):
        """
        Initialize the surge engine.
        
        Args:
            config: Optional configuration:
                - ESCALATE_DELAY: Seconds before going UP a level (3.0)
                - DEESCALATE_DELAY: Seconds before going DOWN (10.0)
                - RISK_WEIGHTS: Dict of component weights
        """
        default_config = {
            "ESCALATE_DELAY": 3.0,
            "DEESCALATE_DELAY": 10.0,
            "RISK_WEIGHTS": {
                "flow_imbalance": 0.20,
                "entry_velocity": 0.20,
                "cluster_density": 0.30,
                "zone_blockage": 0.20,
                "sound_level": 0.10
            }
        }
        
        self.config = {**default_config, **(config or {})}
        
        # Current state
        self.state = SystemState.CLEAR
        self.state_start_time = time.time()
        
        # Pending state (for hysteresis)
        self.pending_state: Optional[SystemState] = None
        self.pending_start_time: Optional[float] = None
        
        # Risk tracking
        self.current_risk = 0.0
        self.component_risks: Dict[str, float] = {}
        
        # History
        self.risk_history: deque = deque(maxlen=300)  # 5 min at 1/sec
        self.state_history: deque = deque(maxlen=100)
        
        # Zone states
        self.zone_states: Dict[str, str] = {"A": "CLEAR", "B": "CLEAR", "C": "CLEAR"}
        
        # Metrics
        self.device_count = 0
        self.passage_rate = 0.0
        self.peak_risk = 0.0
        
        # Last sensor data
        self.last_data: Dict[str, Dict] = {}
    
    def process_sensor_data(self, sensor_data: Dict[str, Dict]) -> Dict:
        """
        Process raw sensor data from all nodes.
        
        Args:
            sensor_data: Dictionary of node_id -> sensor readings
                {
                    "A": {"dist": 150, "pir": 0, ...},
                    "B": {"dist": 200, "pir": 1, ...},
                    "C": {"dist": 80, "pir": 1, "sound": 65, ...}
                }
        
        Returns:
            Dictionary with:
            - risk_score: Overall risk (0.0 - 1.0)
            - state: Current system state name
            - zone_states: Per-zone states
            - component_risks: Individual risk components
            - device_count: Estimated device count
            - passage_rate: Passages per minute
        """
        timestamp = time.time()
        self.last_data = sensor_data
        
        # Calculate component risks
        self.component_risks = self._calculate_components(sensor_data)
        
        # Calculate weighted risk score
        weights = self.config["RISK_WEIGHTS"]
        self.current_risk = sum(
            self.component_risks.get(k, 0) * v
            for k, v in weights.items()
        )
        self.current_risk = max(0.0, min(1.0, self.current_risk))
        
        # Track peak
        if self.current_risk > self.peak_risk:
            self.peak_risk = self.current_risk
        
        # Update history
        self.risk_history.append((timestamp, self.current_risk))
        
        # Determine target state
        target_state = self._risk_to_state(self.current_risk)
        
        # Apply hysteresis
        new_state = self._apply_hysteresis(target_state, timestamp)
        
        # Update state if changed
        if new_state != self.state:
            self.state_history.append((timestamp, self.state, new_state))
            self.state = new_state
            self.state_start_time = timestamp
        
        # Update zone states
        self._update_zone_states(sensor_data)
        
        return {
            "risk_score": round(self.current_risk, 3),
            "state": self.state.name,
            "state_value": self.state.value,
            "state_color": self.STATE_COLORS[self.state],
            "zone_states": self.zone_states.copy(),
            "component_risks": self.component_risks.copy(),
            "device_count": self.device_count,
            "passage_rate": round(self.passage_rate, 1),
            "state_duration": round(timestamp - self.state_start_time, 1)
        }
    
    def _calculate_components(self, sensor_data: Dict) -> Dict[str, float]:
        """Calculate individual risk components."""
        components = {}
        
        if not sensor_data:
            return {k: 0.0 for k in self.config["RISK_WEIGHTS"]}
        
        # 1. Flow Imbalance (Entry vs Exit)
        # If entry is much faster than exit = danger
        entry_dist = sensor_data.get("A", {}).get("dist", 300)
        exit_dist = sensor_data.get("C", {}).get("dist", 300)
        
        # Lower distance at entry + higher at exit = bottleneck
        entry_pressure = max(0, (300 - entry_dist) / 300)
        exit_flow = max(0, (300 - exit_dist) / 300)
        
        if entry_pressure > 0.1:
            # More pressure at entry than exit = bad
            imbalance = max(0, entry_pressure - exit_flow * 0.5)
        else:
            imbalance = 0.0
        
        components["flow_imbalance"] = min(1.0, imbalance)
        
        # 2. Entry Velocity (how fast is crowd building)
        # Use distance change rate as proxy
        corridor_dist = sensor_data.get("B", {}).get("dist", 300)
        avg_dist = (entry_dist + corridor_dist + exit_dist) / 3
        
        # Calculate velocity from distance
        velocity_score = max(0, (300 - avg_dist) / 200)
        components["entry_velocity"] = min(1.0, velocity_score)
        
        # 3. Cluster Density
        # Based on minimum distance across all zones
        min_dist = min(entry_dist, corridor_dist, exit_dist)
        
        if min_dist < 50:
            cluster_score = 1.0
        elif min_dist < 100:
            cluster_score = 0.7
        elif min_dist < 150:
            cluster_score = 0.4
        else:
            cluster_score = max(0, (200 - min_dist) / 200)
        
        components["cluster_density"] = cluster_score
        
        # 4. Zone Blockage
        # Check if any zone is blocked (very low distance)
        blocked_zones = sum(1 for n in ["A", "B", "C"] 
                          if sensor_data.get(n, {}).get("dist", 300) < 80)
        components["zone_blockage"] = min(1.0, blocked_zones / 2)
        
        # 5. Sound Level (Node C only)
        sound = sensor_data.get("C", {}).get("sound", 40)
        if sound > 85:
            sound_score = 1.0
        elif sound > 70:
            sound_score = (sound - 70) / 15
        elif sound > 55:
            sound_score = (sound - 55) / 30
        else:
            sound_score = 0.0
        
        components["sound_level"] = sound_score
        
        # Update device count estimate (from distances)
        # Lower average distance = more people
        self.device_count = int((300 - avg_dist) / 20)
        self.device_count = max(0, self.device_count)
        
        # Update passage rate estimate
        door_dist = exit_dist
        if door_dist < 100:
            self.passage_rate = (100 - door_dist) / 5
        else:
            self.passage_rate = 0
        
        return components
    
    def _risk_to_state(self, risk: float) -> SystemState:
        """Convert risk score to state."""
        thresholds = self.STATE_THRESHOLDS
        
        if risk >= thresholds[3]:
            return SystemState.SURGE
        elif risk >= thresholds[2]:
            return SystemState.CRITICAL
        elif risk >= thresholds[1]:
            return SystemState.ELEVATED
        elif risk >= thresholds[0]:
            return SystemState.NORMAL
        else:
            return SystemState.CLEAR
    
    def _apply_hysteresis(self, target_state: SystemState, 
                          timestamp: float) -> SystemState:
        """Apply time-based hysteresis to prevent rapid state changes."""
        
        # Same state - no change needed
        if target_state == self.state:
            self.pending_state = None
            self.pending_start_time = None
            return self.state
        
        # Determine if escalating or de-escalating
        is_escalating = target_state.value > self.state.value
        
        # Get required delay
        if is_escalating:
            required_delay = self.config["ESCALATE_DELAY"]
        else:
            required_delay = self.config["DEESCALATE_DELAY"]
        
        # Different pending state - start new timer
        if target_state != self.pending_state:
            self.pending_state = target_state
            self.pending_start_time = timestamp
            return self.state
        
        # Check if delay has passed
        if self.pending_start_time is not None:
            elapsed = timestamp - self.pending_start_time
            if elapsed >= required_delay:
                self.pending_state = None
                self.pending_start_time = None
                return target_state
        
        return self.state
    
    def _update_zone_states(self, sensor_data: Dict):
        """Update per-zone state indicators."""
        for zone_id in ["A", "B", "C"]:
            if zone_id not in sensor_data:
                self.zone_states[zone_id] = "OFFLINE"
                continue
            
            dist = sensor_data[zone_id].get("dist", 300)
            
            if dist < 50:
                self.zone_states[zone_id] = "SURGE"
            elif dist < 100:
                self.zone_states[zone_id] = "CRITICAL"
            elif dist < 150:
                self.zone_states[zone_id] = "ELEVATED"
            elif dist < 200:
                self.zone_states[zone_id] = "NORMAL"
            else:
                self.zone_states[zone_id] = "CLEAR"
    
    def get_risk_trend(self, window_seconds: int = 30) -> str:
        """Get risk trend over time window."""
        if len(self.risk_history) < 10:
            return "stable"
        
        now = time.time()
        cutoff = now - window_seconds
        
        recent = [(ts, risk) for ts, risk in self.risk_history if ts >= cutoff]
        
        if len(recent) < 5:
            return "stable"
        
        # Compare first half to second half
        mid = len(recent) // 2
        first_avg = sum(r for _, r in recent[:mid]) / mid
        second_avg = sum(r for _, r in recent[mid:]) / (len(recent) - mid)
        
        diff = second_avg - first_avg
        
        if diff > 0.1:
            return "increasing"
        elif diff < -0.1:
            return "decreasing"
        else:
            return "stable"
    
    def should_alert(self) -> Tuple[bool, str]:
        """
        Check if an alert should be triggered.
        
        Returns:
            Tuple of (should_alert, reason)
        """
        if self.state == SystemState.SURGE:
            return True, "SURGE condition detected!"
        elif self.state == SystemState.CRITICAL:
            trend = self.get_risk_trend()
            if trend == "increasing":
                return True, "CRITICAL and risk increasing!"
            return True, "CRITICAL state reached"
        elif self.state == SystemState.ELEVATED:
            trend = self.get_risk_trend()
            if trend == "increasing":
                return True, "ELEVATED and risk increasing"
        
        return False, ""
    
    def get_statistics(self) -> Dict:
        """Get comprehensive engine statistics."""
        return {
            "current_risk": round(self.current_risk, 3),
            "peak_risk": round(self.peak_risk, 3),
            "state": self.state.name,
            "state_duration": round(time.time() - self.state_start_time, 1),
            "trend": self.get_risk_trend(),
            "zone_states": self.zone_states.copy(),
            "component_risks": self.component_risks.copy(),
            "device_count": self.device_count,
            "passage_rate": round(self.passage_rate, 1),
            "state_changes": len(self.state_history)
        }
    
    def reset(self):
        """Reset engine to initial state."""
        self.state = SystemState.CLEAR
        self.state_start_time = time.time()
        self.pending_state = None
        self.pending_start_time = None
        self.current_risk = 0.0
        self.peak_risk = 0.0
        self.component_risks.clear()
        self.risk_history.clear()
        self.state_history.clear()
        self.zone_states = {"A": "CLEAR", "B": "CLEAR", "C": "CLEAR"}
        self.device_count = 0
        self.passage_rate = 0.0


# ═══════════════════════════════════════════════════════════
#                       TEST SUITE
# ═══════════════════════════════════════════════════════════

def main():
    """Run surge engine tests."""
    print("\n")
    print("╔═══════════════════════════════════════════════════════════╗")
    print("║                    STAMPEDE SHIELD                        ║")
    print("║              Surge Engine - Test Suite                    ║")
    print("╚═══════════════════════════════════════════════════════════╝")
    
    engine = SurgeEngine()
    
    # Test scenarios
    scenarios = [
        {
            "name": "Empty Room",
            "data": {
                "A": {"dist": 350, "pir": 0},
                "B": {"dist": 320, "pir": 0},
                "C": {"dist": 300, "pir": 0, "sound": 35}
            }
        },
        {
            "name": "Normal Traffic",
            "data": {
                "A": {"dist": 180, "pir": 1},
                "B": {"dist": 200, "pir": 0},
                "C": {"dist": 160, "pir": 1, "sound": 50}
            }
        },
        {
            "name": "Getting Busy",
            "data": {
                "A": {"dist": 120, "pir": 1},
                "B": {"dist": 140, "pir": 1},
                "C": {"dist": 100, "pir": 1, "sound": 65}
            }
        },
        {
            "name": "Critical Crowd",
            "data": {
                "A": {"dist": 80, "pir": 1},
                "B": {"dist": 90, "pir": 1},
                "C": {"dist": 70, "pir": 1, "sound": 78}
            }
        },
        {
            "name": "SURGE!",
            "data": {
                "A": {"dist": 40, "pir": 1},
                "B": {"dist": 50, "pir": 1},
                "C": {"dist": 35, "pir": 1, "sound": 92}
            }
        }
    ]
    
    state_emoji = {
        "CLEAR": "🟢",
        "NORMAL": "🔵",
        "ELEVATED": "🟡",
        "CRITICAL": "🟠",
        "SURGE": "🔴"
    }
    
    print("\n" + "=" * 60)
    print("SCENARIO TESTS")
    print("=" * 60)
    
    for scenario in scenarios:
        print(f"\n📊 {scenario['name']}")
        print("-" * 40)
        
        result = engine.process_sensor_data(scenario["data"])
        
        emoji = state_emoji.get(result["state"], "⚪")
        
        print(f"  Risk Score: {result['risk_score']*100:.1f}%")
        print(f"  State: {emoji} {result['state']}")
        print(f"  Zone States: {result['zone_states']}")
        print(f"  Devices: ~{result['device_count']}")
        
        should_alert, reason = engine.should_alert()
        if should_alert:
            print(f"  ⚠️  ALERT: {reason}")
    
    # Progressive simulation
    print("\n" + "=" * 60)
    print("PROGRESSIVE SIMULATION (Crowd Building)")
    print("=" * 60 + "\n")
    
    engine.reset()
    
    import time as t
    
    for i in range(20):
        # Gradually decrease distances (crowd building)
        progress = i / 20
        base_dist = int(300 - (progress * 250))
        
        data = {
            "A": {"dist": base_dist + 20, "pir": 1 if progress > 0.2 else 0},
            "B": {"dist": base_dist + 10, "pir": 1 if progress > 0.3 else 0},
            "C": {"dist": base_dist, "pir": 1, "sound": int(40 + progress * 50)}
        }
        
        result = engine.process_sensor_data(data)
        
        # Visual bar
        risk_bar = "█" * int(result["risk_score"] * 20) + "░" * (20 - int(result["risk_score"] * 20))
        emoji = state_emoji.get(result["state"], "⚪")
        
        print(f"  [{i+1:2d}] [{risk_bar}] {result['risk_score']*100:5.1f}% {emoji} {result['state']}")
        
        t.sleep(0.1)  # Small delay for hysteresis to work
    
    print("\n" + "=" * 60)
    print("FINAL STATISTICS")
    print("=" * 60)
    
    stats = engine.get_statistics()
    print(f"""
  Peak Risk: {stats['peak_risk']*100:.1f}%
  State Changes: {stats['state_changes']}
  Final State: {stats['state']}
  Trend: {stats['trend']}
  
  Component Risks:
    Flow Imbalance: {stats['component_risks'].get('flow_imbalance', 0)*100:.1f}%
    Entry Velocity: {stats['component_risks'].get('entry_velocity', 0)*100:.1f}%
    Cluster Density: {stats['component_risks'].get('cluster_density', 0)*100:.1f}%
    Zone Blockage: {stats['component_risks'].get('zone_blockage', 0)*100:.1f}%
    Sound Level: {stats['component_risks'].get('sound_level', 0)*100:.1f}%
    """)
    
    print("✓ All tests complete!\n")


if __name__ == "__main__":
    main()