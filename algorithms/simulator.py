"""
STAMPEDE SHIELD - Crowd Simulator
Generates realistic simulated sensor data for testing and demos.
"""

import random
import math
import time


class CrowdSimulator:
    """
    Modular crowd simulation with three intensity modes.
    Data flows through existing processing pipeline - alerts arise naturally.
    """
    
    # Mode configurations: (audio_range, distance_range, pir_probability, spike_probability)
    MODES = {
        "normal": {
            "audio": (30, 150),      # Low, stable audio
            "distance": (280, 400),  # Far from sensors
            "pir_prob": 0.1,         # 10% chance of motion
            "spike_prob": 0.02,      # 2% chance of small spike
            "spike_mult": 1.3        # Spike multiplier
        },
        "medium": {
            "audio": (200, 450),     # Moderate audio levels
            "distance": (120, 280),  # Medium proximity
            "pir_prob": 0.5,         # 50% motion
            "spike_prob": 0.15,      # 15% occasional spikes
            "spike_mult": 1.6        # Moderate spike
        },
        "surge": {
            "audio": (550, 850),     # Sustained high audio
            "distance": (30, 150),   # Very close to sensors
            "pir_prob": 0.95,        # Almost constant motion
            "spike_prob": 0.35,      # 35% frequent sharp spikes
            "spike_mult": 1.4        # Scream-like spikes
        }
    }
    
    def __init__(self):
        self._time_offset = time.time()
        self._last_values = {}  # For smooth transitions
    
    def _get_time_factor(self):
        """Time-based variation for realistic data patterns"""
        elapsed = time.time() - self._time_offset
        # Combine multiple sine waves for organic variation
        return (
            math.sin(elapsed * 0.5) * 0.3 +
            math.sin(elapsed * 1.2) * 0.2 +
            math.sin(elapsed * 2.1) * 0.1
        )
    
    def _smooth_value(self, node_id, key, new_value, smoothing=0.3):
        """Smooth transitions between values to avoid jarring jumps"""
        cache_key = f"{node_id}_{key}"
        if cache_key in self._last_values:
            old_value = self._last_values[cache_key]
            new_value = old_value + (new_value - old_value) * smoothing
        self._last_values[cache_key] = new_value
        return new_value
    
    def generate_node_data(self, mode: str, node_id: str) -> dict:
        """
        Generate realistic sensor data for a single node.
        
        Returns:
            dict with keys: dist, pir, mic
        """
        if mode not in self.MODES:
            mode = "normal"
        
        config = self.MODES[mode]
        time_factor = self._get_time_factor()
        
        # Add node-specific variation (nodes behave slightly differently)
        node_offset = hash(node_id) % 100 / 100.0
        
        # Generate audio with time-based variation
        audio_min, audio_max = config["audio"]
        audio_base = random.uniform(audio_min, audio_max)
        audio_variation = (audio_max - audio_min) * 0.2 * time_factor
        audio = audio_base + audio_variation + (node_offset * 20)
        
        # Apply spike if triggered
        if random.random() < config["spike_prob"]:
            audio *= config["spike_mult"]
        
        audio = self._smooth_value(node_id, "mic", audio)
        audio = max(0, min(1000, int(audio)))  # Clamp to sensor range
        
        # Generate distance with variation
        dist_min, dist_max = config["distance"]
        dist_base = random.uniform(dist_min, dist_max)
        dist_variation = (dist_max - dist_min) * 0.15 * time_factor
        dist = dist_base + dist_variation - (node_offset * 15)
        dist = self._smooth_value(node_id, "dist", dist)
        dist = max(10, min(400, int(dist)))  # Clamp to sensor range
        
        # Generate PIR (binary with probability)
        pir = 1 if random.random() < config["pir_prob"] else 0
        
        return {
            "dist": dist,
            "pir": pir,
            "mic": audio
        }
    
    def generate_all_nodes(self, mode: str) -> dict:
        """
        Generate data for all three nodes.
        
        Returns:
            dict: {"NODE_A": {...}, "NODE_B": {...}, "NODE_C": {...}}
        """
        return {
            "NODE_A": self.generate_node_data(mode, "NODE_A"),
            "NODE_B": self.generate_node_data(mode, "NODE_B"),
            "NODE_C": self.generate_node_data(mode, "NODE_C")
        }
    
    def reset(self):
        """Reset simulator state for fresh start"""
        self._time_offset = time.time()
        self._last_values.clear()


# Singleton instance for use across the application
simulator = CrowdSimulator()
