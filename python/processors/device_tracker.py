#!/usr/bin/env python3
"""
╔═══════════════════════════════════════════════════════════╗
║                    STAMPEDE SHIELD                        ║
║          Device Tracker for WiFi Crowd Estimation         ║
╚═══════════════════════════════════════════════════════════╝

Tracks WiFi device counts from nodes and estimates:
- Total unique devices in area
- Device distribution across zones
- Approximate positions for heatmap visualization

Author: StampedeShield Team
Version: 2.0
"""

import time
import math
import random
from typing import Dict, List, Tuple, Optional
from collections import deque


class DeviceTracker:
    """
    Tracks WiFi devices across multiple nodes.
    
    Since nodes only report device count (not MAC addresses),
    we estimate positions for visualization using zone-based
    distribution and random placement within zones.
    """
    
    def __init__(self, node_positions: Optional[Dict] = None, 
                 config: Optional[Dict] = None):
        """
        Initialize the device tracker.
        
        Args:
            node_positions: Dict of node positions {"A": (x, y), ...}
            config: Configuration dictionary with:
                - WIFI_MULTIPLIER: Multiply count to estimate actual people (1.4)
                - DEVICE_TIMEOUT: Seconds before node data is stale (30)
                - TX_POWER: RSSI at 1 meter (-59 dBm)
                - PATH_LOSS: Environment factor (2.5)
                - DETECTION_RADIUS: Max detection range in meters (15)
        """
        # Default node positions (in meters)
        self.node_positions = node_positions or {
            "A": (0, 10),      # Top-left corner
            "B": (10, 10),     # Top-right corner
            "C": (5, 0)        # Bottom-center (door)
        }
        
        # Default configuration
        default_config = {
            "WIFI_MULTIPLIER": 1.4,
            "DEVICE_TIMEOUT": 30,
            "TX_POWER": -59,
            "PATH_LOSS": 2.5,
            "DETECTION_RADIUS": 15,
            "ROOM_WIDTH": 10,
            "ROOM_HEIGHT": 10
        }
        
        self.config = {**default_config, **(config or {})}
        
        # Node data storage
        self.node_data: Dict[str, Dict] = {}
        
        # History for trend analysis
        self.count_history: deque = deque(maxlen=300)  # ~5 min at 1/sec
        
        # Zone definitions (for distribution)
        self._define_zones()
        
        # Statistics
        self.peak_count = 0
        self.total_updates = 0
    
    def _define_zones(self):
        """Define zones based on node positions."""
        w = self.config["ROOM_WIDTH"]
        h = self.config["ROOM_HEIGHT"]
        
        # Zone boundaries: (x_min, y_min, x_max, y_max)
        self.zones = {
            "A": (0, h/2, w/2, h),           # Top-left quadrant
            "B": (w/2, h/2, w, h),           # Top-right quadrant
            "C": (w/4, 0, 3*w/4, h/2),       # Bottom-center (door area)
            "center": (w/4, h/4, 3*w/4, 3*h/4)  # Center of room
        }
    
    def update_scan(self, node_id: str, wifi_count: int, 
                    timestamp: Optional[float] = None,
                    rssi: Optional[int] = None):
        """
        Update device count from a node.
        
        Args:
            node_id: Node identifier ("A", "B", or "C")
            wifi_count: Number of WiFi devices detected
            timestamp: Unix timestamp (uses current time if None)
            rssi: Optional RSSI value for distance estimation
        """
        if timestamp is None:
            timestamp = time.time()
        
        self.node_data[node_id] = {
            "count": wifi_count,
            "timestamp": timestamp,
            "rssi": rssi,
            "age": 0.0
        }
        
        self.total_updates += 1
        
        # Update history
        total = self.get_device_count()
        self.count_history.append((timestamp, total))
        
        # Track peak
        if total > self.peak_count:
            self.peak_count = total
    
    def _get_active_nodes(self) -> Dict[str, Dict]:
        """Get nodes with recent data (not stale)."""
        now = time.time()
        timeout = self.config["DEVICE_TIMEOUT"]
        
        active = {}
        for node_id, data in self.node_data.items():
            age = now - data["timestamp"]
            if age < timeout:
                data["age"] = age
                active[node_id] = data
        
        return active
    
    def get_device_count(self) -> int:
        """
        Get estimated total unique devices.
        
        Since nodes may detect overlapping devices, we use:
        - Maximum count across nodes as base
        - Add fraction of other counts for non-overlap
        - Multiply by estimator for people without WiFi
        
        Returns:
            Estimated total device count
        """
        active_nodes = self._get_active_nodes()
        
        if not active_nodes:
            return 0
        
        counts = [data["count"] for data in active_nodes.values()]
        
        if not counts:
            return 0
        
        # Use max as base (devices detected by at least one node)
        max_count = max(counts)
        
        # Add weighted sum of others for potential non-overlap
        # This accounts for devices only seen by specific nodes
        total_others = sum(c for c in counts if c != max_count)
        overlap_factor = 0.3  # Assume 30% are unique to other nodes
        
        estimated = max_count + (total_others * overlap_factor)
        
        # Apply multiplier for people without WiFi on
        multiplier = self.config["WIFI_MULTIPLIER"]
        final_count = int(estimated * multiplier)
        
        return final_count
    
    def get_raw_counts(self) -> Dict[str, int]:
        """
        Get raw device counts from each node.
        
        Returns:
            Dictionary of node_id -> count
        """
        active_nodes = self._get_active_nodes()
        return {node_id: data["count"] for node_id, data in active_nodes.items()}
    
    def rssi_to_distance(self, rssi: int) -> float:
        """
        Convert RSSI to estimated distance in meters.
        
        Formula: distance = 10 ^ ((TX_POWER - RSSI) / (10 * n))
        
        Args:
            rssi: Signal strength in dBm (negative value)
            
        Returns:
            Estimated distance in meters
        """
        if rssi >= 0:
            return 0.0
        
        tx_power = self.config["TX_POWER"]
        path_loss = self.config["PATH_LOSS"]
        
        distance = 10 ** ((tx_power - rssi) / (10 * path_loss))
        
        return round(distance, 2)
    
    def triangulate_position(self, rssi_readings: Dict[str, int]) -> Tuple[float, float]:
        """
        Estimate position using inverse-distance weighted centroid.
        
        Args:
            rssi_readings: Dictionary of node_id -> RSSI value
            
        Returns:
            Tuple of (x, y) estimated position
        """
        if not rssi_readings:
            # Return center of room if no data
            w = self.config["ROOM_WIDTH"]
            h = self.config["ROOM_HEIGHT"]
            return (w / 2, h / 2)
        
        total_weight = 0.0
        weighted_x = 0.0
        weighted_y = 0.0
        
        for node_id, rssi in rssi_readings.items():
            if node_id not in self.node_positions:
                continue
            
            # Get distance from RSSI
            distance = self.rssi_to_distance(rssi)
            
            # Avoid division by zero
            if distance < 0.1:
                distance = 0.1
            
            # Weight is inverse of distance (closer = more weight)
            weight = 1.0 / distance
            
            # Get node position
            node_x, node_y = self.node_positions[node_id]
            
            # Accumulate weighted position
            weighted_x += node_x * weight
            weighted_y += node_y * weight
            total_weight += weight
        
        if total_weight == 0:
            w = self.config["ROOM_WIDTH"]
            h = self.config["ROOM_HEIGHT"]
            return (w / 2, h / 2)
        
        # Calculate weighted centroid
        x = weighted_x / total_weight
        y = weighted_y / total_weight
        
        # Clamp to room bounds
        w = self.config["ROOM_WIDTH"]
        h = self.config["ROOM_HEIGHT"]
        x = max(0, min(w, x))
        y = max(0, min(h, y))
        
        return (round(x, 2), round(y, 2))
    
    def get_zone_counts(self) -> Dict[str, int]:
        """
        Distribute devices across zones based on node readings.
        
        Uses relative counts from each node to estimate
        zone-specific populations.
        
        Returns:
            Dictionary of zone_id -> device count
        """
        active_nodes = self._get_active_nodes()
        total_devices = self.get_device_count()
        
        if not active_nodes or total_devices == 0:
            return {"A": 0, "B": 0, "C": 0, "center": 0}
        
        # Get counts and total
        counts = {node_id: data["count"] for node_id, data in active_nodes.items()}
        total_raw = sum(counts.values())
        
        if total_raw == 0:
            return {"A": 0, "B": 0, "C": 0, "center": 0}
        
        # Calculate zone proportions
        zone_counts = {}
        
        # Distribute to node zones based on their relative counts
        for node_id in ["A", "B", "C"]:
            if node_id in counts:
                proportion = counts[node_id] / total_raw
                zone_counts[node_id] = int(total_devices * proportion * 0.6)
            else:
                zone_counts[node_id] = 0
        
        # Remaining devices go to center (overlap area)
        assigned = sum(zone_counts.values())
        zone_counts["center"] = max(0, total_devices - assigned)
        
        return zone_counts
    
    def get_estimated_positions(self) -> List[Tuple[float, float, float]]:
        """
        Generate estimated positions for visualization.
        
        Since we only have counts (not individual device data),
        we distribute devices randomly within their estimated zones.
        
        Returns:
            List of (x, y, density_score) tuples for each estimated device
        """
        zone_counts = self.get_zone_counts()
        positions = []
        
        for zone_id, count in zone_counts.items():
            if count == 0 or zone_id not in self.zones:
                continue
            
            # Get zone boundaries
            x_min, y_min, x_max, y_max = self.zones[zone_id]
            
            # Generate random positions within zone
            for _ in range(count):
                x = random.uniform(x_min, x_max)
                y = random.uniform(y_min, y_max)
                
                # Calculate density score based on zone crowding
                zone_area = (x_max - x_min) * (y_max - y_min)
                density = count / zone_area if zone_area > 0 else 0
                density_score = min(1.0, density / 5.0)  # Normalize to 0-1
                
                positions.append((round(x, 2), round(y, 2), round(density_score, 3)))
        
        return positions
    
    def get_heatmap_grid(self, grid_size: int = 10) -> List[List[float]]:
        """
        Generate a heatmap grid for visualization.
        
        Args:
            grid_size: Number of cells in each dimension
            
        Returns:
            2D list of density values (0.0 to 1.0)
        """
        w = self.config["ROOM_WIDTH"]
        h = self.config["ROOM_HEIGHT"]
        
        cell_width = w / grid_size
        cell_height = h / grid_size
        
        # Initialize grid
        grid = [[0.0 for _ in range(grid_size)] for _ in range(grid_size)]
        
        # Get estimated positions
        positions = self.get_estimated_positions()
        
        # Count devices in each cell
        for x, y, density in positions:
            col = int(min(x / cell_width, grid_size - 1))
            row = int(min(y / cell_height, grid_size - 1))
            grid[row][col] += 1
        
        # Normalize to 0-1
        max_count = max(max(row) for row in grid) if positions else 1
        if max_count > 0:
            for row in range(grid_size):
                for col in range(grid_size):
                    grid[row][col] = min(1.0, grid[row][col] / max_count)
        
        return grid
    
    def get_flow_trend(self, window_seconds: int = 60) -> str:
        """
        Analyze device count trend over time.
        
        Returns:
            "increasing", "decreasing", "stable", or "unknown"
        """
        if len(self.count_history) < 10:
            return "unknown"
        
        now = time.time()
        cutoff = now - window_seconds
        
        recent = [(ts, count) for ts, count in self.count_history if ts >= cutoff]
        
        if len(recent) < 5:
            return "unknown"
        
        # Split into first half and second half
        mid = len(recent) // 2
        first_half_avg = sum(c for _, c in recent[:mid]) / mid
        second_half_avg = sum(c for _, c in recent[mid:]) / (len(recent) - mid)
        
        # Determine trend
        diff = second_half_avg - first_half_avg
        threshold = 2  # Minimum change to be significant
        
        if diff > threshold:
            return "increasing"
        elif diff < -threshold:
            return "decreasing"
        else:
            return "stable"
    
    def get_statistics(self) -> Dict:
        """
        Get comprehensive tracking statistics.
        
        Returns:
            Dictionary with various statistics
        """
        active_nodes = self._get_active_nodes()
        
        return {
            "total_devices": self.get_device_count(),
            "raw_counts": self.get_raw_counts(),
            "zone_distribution": self.get_zone_counts(),
            "active_nodes": len(active_nodes),
            "peak_count": self.peak_count,
            "trend": self.get_flow_trend(),
            "total_updates": self.total_updates
        }
    
    def reset(self):
        """Reset tracker state."""
        self.node_data.clear()
        self.count_history.clear()
        self.peak_count = 0
        self.total_updates = 0


# ═══════════════════════════════════════════════════════════
#                       TEST SUITE
# ═══════════════════════════════════════════════════════════

def print_heatmap(grid: List[List[float]]):
    """Print ASCII heatmap."""
    chars = " ░▒▓█"
    
    print("\n  Heatmap (density):")
    print("  ┌" + "─" * (len(grid[0]) * 2) + "┐")
    
    for row in reversed(grid):  # Reverse to match coordinate system
        line = "  │"
        for val in row:
            idx = int(val * (len(chars) - 1))
            line += chars[idx] * 2
        line += "│"
        print(line)
    
    print("  └" + "─" * (len(grid[0]) * 2) + "┘")


def main():
    """Run device tracker tests."""
    print("\n")
    print("╔═══════════════════════════════════════════════════════════╗")
    print("║                    STAMPEDE SHIELD                        ║")
    print("║              Device Tracker - Test Suite                  ║")
    print("╚═══════════════════════════════════════════════════════════╝")
    
    # Create tracker
    node_positions = {
        "A": (0, 10),
        "B": (10, 10),
        "C": (5, 0)
    }
    
    config = {
        "WIFI_MULTIPLIER": 1.4,
        "DEVICE_TIMEOUT": 30,
        "TX_POWER": -59,
        "PATH_LOSS": 2.5,
        "ROOM_WIDTH": 10,
        "ROOM_HEIGHT": 10
    }
    
    tracker = DeviceTracker(node_positions, config)
    
    # ═══════════════════════════════════════════════════════════
    # TEST 1: Basic device counting
    # ═══════════════════════════════════════════════════════════
    print("\n" + "=" * 60)
    print("TEST 1: Basic Device Counting")
    print("=" * 60)
    
    print("\n  Simulating node reports...")
    
    # Simulate node scans
    now = time.time()
    tracker.update_scan("A", wifi_count=8, timestamp=now)
    tracker.update_scan("B", wifi_count=5, timestamp=now)
    tracker.update_scan("C", wifi_count=12, timestamp=now)
    
    print(f"\n  Raw counts:")
    for node_id, count in tracker.get_raw_counts().items():
        print(f"    Node {node_id}: {count} devices")
    
    total = tracker.get_device_count()
    print(f"\n  Estimated total: {total} devices")
    print(f"  (Using max + overlap estimation + {config['WIFI_MULTIPLIER']}x multiplier)")
    
    # ═══════════════════════════════════════════════════════════
    # TEST 2: Zone distribution
    # ═══════════════════════════════════════════════════════════
    print("\n" + "=" * 60)
    print("TEST 2: Zone Distribution")
    print("=" * 60)
    
    zones = tracker.get_zone_counts()
    print("\n  Device distribution by zone:")
    for zone_id, count in zones.items():
        bar = "█" * count + "░" * (20 - count)
        print(f"    Zone {zone_id:6s}: [{bar}] {count}")
    
    # ═══════════════════════════════════════════════════════════
    # TEST 3: Position estimation
    # ═══════════════════════════════════════════════════════════
    print("\n" + "=" * 60)
    print("TEST 3: Position Estimation")
    print("=" * 60)
    
    positions = tracker.get_estimated_positions()
    print(f"\n  Generated {len(positions)} estimated positions")
    print("  First 5 positions (x, y, density):")
    for i, (x, y, density) in enumerate(positions[:5]):
        print(f"    [{i+1}] ({x:5.2f}, {y:5.2f}) density: {density:.3f}")
    
    # ═══════════════════════════════════════════════════════════
    # TEST 4: Heatmap generation
    # ═══════════════════════════════════════════════════════════
    print("\n" + "=" * 60)
    print("TEST 4: Heatmap Generation")
    print("=" * 60)
    
    grid = tracker.get_heatmap_grid(grid_size=10)
    print_heatmap(grid)
    
    print("\n  Legend: ' '=empty  ░=low  ▒=medium  ▓=high  █=crowded")
    
    # ═══════════════════════════════════════════════════════════
    # TEST 5: RSSI to distance conversion
    # ═══════════════════════════════════════════════════════════
    print("\n" + "=" * 60)
    print("TEST 5: RSSI to Distance Conversion")
    print("=" * 60)
    
    test_rssi = [-40, -50, -60, -70, -80, -90]
    print("\n  RSSI → Distance mapping:")
    print("  " + "-" * 35)
    
    for rssi in test_rssi:
        distance = tracker.rssi_to_distance(rssi)
        bar_len = int(min(distance, 20))
        bar = "─" * bar_len + "●"
        print(f"    {rssi:4d} dBm → {distance:6.2f}m  {bar}")
    
    # ═══════════════════════════════════════════════════════════
    # TEST 6: Triangulation
    # ═══════════════════════════════════════════════════════════
    print("\n" + "=" * 60)
    print("TEST 6: Position Triangulation")
    print("=" * 60)
    
    test_cases = [
        {"A": -50, "B": -70, "C": -60},  # Closer to A
        {"A": -70, "B": -50, "C": -60},  # Closer to B
        {"A": -65, "B": -65, "C": -45},  # Closer to C (door)
        {"A": -60, "B": -60, "C": -60},  # Center (equal distance)
    ]
    
    print("\n  RSSI readings → Estimated position:")
    print("  " + "-" * 50)
    
    for i, readings in enumerate(test_cases):
        x, y = tracker.triangulate_position(readings)
        print(f"    Case {i+1}: A={readings['A']}dBm, B={readings['B']}dBm, C={readings['C']}dBm")
        print(f"           → Position: ({x:.2f}, {y:.2f})")
    
    # ═══════════════════════════════════════════════════════════
    # TEST 7: Trend analysis
    # ═══════════════════════════════════════════════════════════
    print("\n" + "=" * 60)
    print("TEST 7: Flow Trend Analysis")
    print("=" * 60)
    
    # Reset and simulate increasing trend
    tracker.reset()
    
    print("\n  Simulating increasing crowd...")
    base_time = time.time()
    
    for i in range(30):
        # Gradually increase counts
        count_a = 5 + i // 3
        count_b = 3 + i // 4
        count_c = 8 + i // 2
        
        ts = base_time + i * 0.5
        tracker.update_scan("A", count_a, ts)
        tracker.update_scan("B", count_b, ts)
        tracker.update_scan("C", count_c, ts)
    
    trend = tracker.get_flow_trend()
    print(f"  Trend: {trend}")
    
    # ═══════════════════════════════════════════════════════════
    # TEST 8: Full statistics
    # ═══════════════════════════════════════════════════════════
    print("\n" + "=" * 60)
    print("TEST 8: Full Statistics")
    print("=" * 60)
    
    stats = tracker.get_statistics()
    
    print("\n  📊 Tracker Statistics:")
    print(f"     Total Devices: {stats['total_devices']}")
    print(f"     Peak Count: {stats['peak_count']}")
    print(f"     Active Nodes: {stats['active_nodes']}")
    print(f"     Trend: {stats['trend']}")
    print(f"     Total Updates: {stats['total_updates']}")
    print(f"\n     Raw Counts: {stats['raw_counts']}")
    print(f"     Zone Distribution: {stats['zone_distribution']}")
    
    # ═══════════════════════════════════════════════════════════
    # VISUAL DEMO
    # ═══════════════════════════════════════════════════════════
    print("\n" + "=" * 60)
    print("VISUAL: Room Layout with Devices")
    print("=" * 60)
    
    # Create a simple ASCII visualization
    room_width = 20
    room_height = 10
    room = [[' ' for _ in range(room_width)] for _ in range(room_height)]
    
    # Mark node positions
    room[9][0] = 'A'   # Top-left (y=10 → row 9)
    room[9][19] = 'B'  # Top-right
    room[0][10] = 'C'  # Bottom-center (door)
    
    # Place some devices
    positions = tracker.get_estimated_positions()
    for x, y, density in positions[:15]:  # Limit for visibility
        col = int(x / 10 * (room_width - 1))
        row = int(y / 10 * (room_height - 1))
        col = max(0, min(room_width - 1, col))
        row = max(0, min(room_height - 1, row))
        if room[row][col] == ' ':
            room[row][col] = '•'
    
    print("\n  Room Layout (A, B = corners, C = door, • = device):")
    print("  ┌" + "─" * room_width + "┐")
    for row in reversed(room):
        print("  │" + ''.join(row) + "│")
    print("  └" + "─" * room_width + "┘")
    print("         ↑ Door (Node C)")
    
    print("\n✓ All tests complete!\n")


if __name__ == "__main__":
    main()