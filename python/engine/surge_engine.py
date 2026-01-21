#!/usr/bin/env python3
"""
SurgeEngine - Unified crowd risk assessment engine.

Combines PassageDetector, DeviceTracker, ClusterDetector, and ZoneDetector
to produce a unified risk score and state.
"""

import sys
import time
from collections import deque
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any

# Add parent directory to path to import processors
sys.path.insert(0, '..')
from processors.passage_detector import PassageDetector
from processors.device_tracker import DeviceTracker
from processors.cluster_detector import ClusterDetector
from processors.zone_detector import ZoneDetector


@dataclass
class SurgeState:
    """Output state from SurgeEngine."""
    risk_score: float = 0.0
    state: str = "CLEAR"
    zone_states: Dict[str, str] = field(default_factory=dict)
    passage_rate: float = 0.0
    cluster_count: int = 0
    device_count: int = 0
    velocity: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "risk_score": self.risk_score,
            "state": self.state,
            "zone_states": self.zone_states,
            "passage_rate": self.passage_rate,
            "cluster_count": self.cluster_count,
            "device_count": self.device_count,
            "velocity": self.velocity
        }


class SurgeEngine:
    """
    Unified engine for stampede risk detection.
    
    Args:
        node_positions: Dict of node positions for DeviceTracker.
        config: Optional configuration overrides.
    """
    
    # State thresholds
    THRESHOLDS = [
        (0.2, "CLEAR"),
        (0.4, "NORMAL"),
        (0.6, "ELEVATED"),
        (0.8, "CRITICAL"),
        (float('inf'), "SURGE")
    ]
    
    # Risk formula weights
    WEIGHT_PASSAGE = 0.30
    WEIGHT_DENSITY = 0.25
    WEIGHT_CLUSTER = 0.25
    WEIGHT_VELOCITY = 0.20
    
    # Normalization caps
    MAX_FLOW_RATE = 60.0      # passages/min for max score
    MAX_DEVICE_COUNT = 50.0   # devices for max score
    MAX_VELOCITY = 0.1        # risk change per second for max score

    def __init__(self, node_positions: Optional[Dict] = None, config: Optional[Dict] = None):
        config = config or {}
        
        # Default node positions (triangle layout)
        if node_positions is None:
            node_positions = {"A": (5, 0), "B": (0, 10), "C": (10, 10)}
        
        # Initialize processors
        self.passage_detector = PassageDetector(config.get("passage", {}))
        self.device_tracker = DeviceTracker(node_positions, config.get("device", {}))
        self.cluster_detector = ClusterDetector(
            room_bounds=(10, 10),
            cell_size=2.0,
            config=config.get("cluster", {})
        )
        self.zone_detectors = {
            node_id: ZoneDetector(node_id, config.get("zone", {}))
            for node_id in node_positions.keys()
        }
        
        # Risk history for velocity calculation
        self.risk_history: deque = deque(maxlen=20)  # Store (timestamp, risk) tuples
        self.last_risk = 0.0

    def process(self, sensor_data: Dict[str, Dict]) -> SurgeState:
        """
        Process sensor data from all nodes.
        
        Args:
            sensor_data: Dict like {"A": {"dist": 100, "pir": 1, "wifi": 5, "sound": 45}, ...}
            
        Returns:
            SurgeState with risk assessment.
        """
        current_time = time.time()
        
        # 1. Process each node's data
        zone_states = {}
        for node_id, data in sensor_data.items():
            dist = data.get("dist", 300)
            pir = data.get("pir", 0)
            wifi = data.get("wifi", 0)
            
            # Update device tracker
            self.device_tracker.update_scan(node_id, wifi)
            
            # Update zone detector
            if node_id in self.zone_detectors:
                result = self.zone_detectors[node_id].process_reading(dist, pir)
                zone_states[node_id] = result.get("state", "CLEAR")
        
        # 2. Use node "A" for passage detection (assumed to be at doorway)
        if "A" in sensor_data:
            self.passage_detector.process_reading(sensor_data["A"].get("dist", 300))
        
        # 3. Get estimated device positions and update cluster detector
        positions = self.device_tracker.get_estimated_positions()
        # ClusterDetector expects (x, y) tuples only
        position_tuples = [(p[0], p[1]) for p in positions] if positions else []
        self.cluster_detector.update(position_tuples)
        
        # 4. Calculate individual scores
        passage_rate = self.passage_detector.get_flow_rate()
        passage_score = min(1.0, passage_rate / self.MAX_FLOW_RATE)
        
        device_count = self.device_tracker.get_device_count()
        density_score = min(1.0, device_count / self.MAX_DEVICE_COUNT)
        
        cluster_score = self.cluster_detector.get_cluster_risk_score()
        cluster_count = len(self.cluster_detector.get_clusters())
        
        # Velocity calculation (rate of change of risk)
        velocity = self._calculate_velocity(current_time)
        velocity_score = min(1.0, abs(velocity) / self.MAX_VELOCITY)
        
        # 5. Calculate weighted risk
        risk_score = (
            self.WEIGHT_PASSAGE * passage_score +
            self.WEIGHT_DENSITY * density_score +
            self.WEIGHT_CLUSTER * cluster_score +
            self.WEIGHT_VELOCITY * velocity_score
        )
        risk_score = min(1.0, max(0.0, risk_score))
        
        # 6. Determine state from thresholds
        state = "SURGE"
        for threshold, state_name in self.THRESHOLDS:
            if risk_score < threshold:
                state = state_name
                break
        
        # 7. Store risk for velocity calculation
        self.risk_history.append((current_time, risk_score))
        self.last_risk = risk_score
        
        return SurgeState(
            risk_score=round(risk_score, 3),
            state=state,
            zone_states=zone_states,
            passage_rate=round(passage_rate, 2),
            cluster_count=cluster_count,
            device_count=int(device_count),
            velocity=round(velocity, 4)
        )

    def _calculate_velocity(self, current_time: float) -> float:
        """Calculate rate of change of risk score per second."""
        if len(self.risk_history) < 2:
            return 0.0
        
        # Get oldest and newest readings
        oldest_time, oldest_risk = self.risk_history[0]
        newest_time, newest_risk = self.risk_history[-1]
        
        time_delta = newest_time - oldest_time
        if time_delta < 0.1:  # Less than 100ms
            return 0.0
        
        return (newest_risk - oldest_risk) / time_delta

    def reset(self):
        """Reset all processors and history."""
        self.passage_detector.reset()
        self.device_tracker.reset()
        self.cluster_detector.reset()
        for zd in self.zone_detectors.values():
            zd.reset()
        self.risk_history.clear()
        self.last_risk = 0.0


if __name__ == "__main__":
    # Quick standalone test
    engine = SurgeEngine()
    
    test_data = {
        "A": {"dist": 100, "pir": 1, "wifi": 10, "sound": 60},
        "B": {"dist": 150, "pir": 0, "wifi": 8, "sound": 55},
        "C": {"dist": 200, "pir": 0, "wifi": 5, "sound": 50}
    }
    
    result = engine.process(test_data)
    print(f"Risk: {result.risk_score}, State: {result.state}")
    print(f"Zones: {result.zone_states}")
    print(f"Passage Rate: {result.passage_rate}/min, Devices: {result.device_count}")
