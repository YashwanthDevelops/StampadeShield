#!/usr/bin/env python3
"""
╔═══════════════════════════════════════════════════════════╗
║                    STAMPEDE SHIELD                        ║
║           Cluster Detector for Surge Prevention           ║
╚═══════════════════════════════════════════════════════════╝

Detects dangerous crowd clusters using grid-based density analysis.
Identifies when people are clustering together (surge risk).

Author: StampedeShield Team
Version: 2.0
"""

import time
from typing import Dict, List, Tuple, Optional, Set
from collections import deque


class ClusterDetector:
    """
    Detects crowd clusters using grid-based density analysis.
    
    Divides the room into cells and counts devices per cell.
    Identifies clusters when cell density exceeds thresholds.
    Adjacent high-density cells are merged into larger clusters.
    
    Risk Levels:
    - LOW: 3-4 devices in cluster
    - MEDIUM: 5-7 devices in cluster
    - HIGH: 8+ devices in cluster
    """
    
    def __init__(self, room_bounds: Tuple[float, float] = (10, 10),
                 cell_size: float = 2.0,
                 config: Optional[Dict] = None):
        """
        Initialize the cluster detector.
        
        Args:
            room_bounds: (width, height) of room in meters
            cell_size: Size of each grid cell in meters
            config: Optional configuration:
                - MIN_CLUSTER_SIZE: Minimum devices to form cluster (3)
                - MEDIUM_THRESHOLD: Devices for MEDIUM risk (5)
                - HIGH_THRESHOLD: Devices for HIGH risk (8)
                - DENSITY_THRESHOLD: Devices per cell to be "dense" (2)
        """
        self.room_width, self.room_height = room_bounds
        self.cell_size = cell_size
        
        # Calculate grid dimensions
        self.grid_cols = int(self.room_width / cell_size)
        self.grid_rows = int(self.room_height / cell_size)
        
        # Ensure at least 1x1 grid
        self.grid_cols = max(1, self.grid_cols)
        self.grid_rows = max(1, self.grid_rows)
        
        # Default configuration
        default_config = {
            "MIN_CLUSTER_SIZE": 3,
            "MEDIUM_THRESHOLD": 5,
            "HIGH_THRESHOLD": 8,
            "DENSITY_THRESHOLD": 2
        }
        
        self.config = {**default_config, **(config or {})}
        
        # Grid storage
        self.grid: List[List[int]] = []
        self.cell_positions: List[List[List[Tuple[float, float]]]] = []
        
        # Cluster data
        self.clusters: List[Dict] = []
        
        # History
        self.cluster_history: deque = deque(maxlen=100)
        self.max_cluster_ever = 0
        
        # Initialize grid
        self._reset_grid()
    
    def _reset_grid(self):
        """Reset grid to empty state."""
        self.grid = [[0 for _ in range(self.grid_cols)] 
                     for _ in range(self.grid_rows)]
        self.cell_positions = [[[] for _ in range(self.grid_cols)]
                               for _ in range(self.grid_rows)]
    
    def _position_to_cell(self, x: float, y: float) -> Tuple[int, int]:
        """
        Convert (x, y) position to grid cell (row, col).
        
        Args:
            x: X coordinate in meters
            y: Y coordinate in meters
            
        Returns:
            Tuple of (row, col)
        """
        col = int(x / self.cell_size)
        row = int(y / self.cell_size)
        
        # Clamp to grid bounds
        col = max(0, min(self.grid_cols - 1, col))
        row = max(0, min(self.grid_rows - 1, row))
        
        return (row, col)
    
    def _cell_to_position(self, row: int, col: int) -> Tuple[float, float]:
        """
        Convert grid cell to center position.
        
        Args:
            row: Grid row
            col: Grid column
            
        Returns:
            Tuple of (x, y) center position
        """
        x = (col + 0.5) * self.cell_size
        y = (row + 0.5) * self.cell_size
        return (x, y)
    
    def update(self, positions: List[Tuple[float, float]]):
        """
        Update detector with new device positions.
        
        Args:
            positions: List of (x, y) tuples from DeviceTracker
        """
        # Reset grid
        self._reset_grid()
        
        # Populate grid with positions
        for pos in positions:
            if len(pos) >= 2:
                x, y = pos[0], pos[1]
                row, col = self._position_to_cell(x, y)
                self.grid[row][col] += 1
                self.cell_positions[row][col].append((x, y))
        
        # Find clusters
        self.clusters = self._find_clusters()
        
        # Update history
        if self.clusters:
            max_size = self.get_max_cluster_size()
            self.cluster_history.append((time.time(), max_size))
            if max_size > self.max_cluster_ever:
                self.max_cluster_ever = max_size
    
    def _find_clusters(self) -> List[Dict]:
        """
        Find all clusters using connected component analysis.
        
        Returns:
            List of cluster dictionaries
        """
        clusters = []
        visited: Set[Tuple[int, int]] = set()
        density_threshold = self.config["DENSITY_THRESHOLD"]
        min_cluster_size = self.config["MIN_CLUSTER_SIZE"]
        
        # Find connected dense cells
        for row in range(self.grid_rows):
            for col in range(self.grid_cols):
                if (row, col) in visited:
                    continue
                
                if self.grid[row][col] >= density_threshold:
                    # Start BFS to find connected dense cells
                    cluster_cells = self._bfs_cluster(row, col, visited, 
                                                       density_threshold)
                    
                    if cluster_cells:
                        # Calculate cluster properties
                        cluster = self._build_cluster(cluster_cells)
                        
                        if cluster["count"] >= min_cluster_size:
                            clusters.append(cluster)
        
        # Also check individual high-density cells not connected
        for row in range(self.grid_rows):
            for col in range(self.grid_cols):
                count = self.grid[row][col]
                if count >= min_cluster_size:
                    # Check if this cell is already part of a cluster
                    cell_center = self._cell_to_position(row, col)
                    already_counted = False
                    
                    for cluster in clusters:
                        cx, cy = cluster["center"]
                        dist = ((cx - cell_center[0])**2 + 
                                (cy - cell_center[1])**2) ** 0.5
                        if dist < self.cell_size * 1.5:
                            already_counted = True
                            break
                    
                    if not already_counted:
                        cluster = {
                            "center": cell_center,
                            "count": count,
                            "cells": [(row, col)],
                            "risk": self._calculate_risk(count)
                        }
                        clusters.append(cluster)
        
        # Sort by count (largest first)
        clusters.sort(key=lambda c: c["count"], reverse=True)
        
        return clusters
    
    def _bfs_cluster(self, start_row: int, start_col: int,
                     visited: Set[Tuple[int, int]],
                     density_threshold: int) -> List[Tuple[int, int]]:
        """
        Find connected dense cells using BFS.
        
        Args:
            start_row: Starting row
            start_col: Starting column
            visited: Set of already visited cells
            density_threshold: Minimum devices to be "dense"
            
        Returns:
            List of (row, col) cells in cluster
        """
        if (start_row, start_col) in visited:
            return []
        
        if self.grid[start_row][start_col] < density_threshold:
            return []
        
        cluster_cells = []
        queue = deque([(start_row, start_col)])
        
        while queue:
            row, col = queue.popleft()
            
            if (row, col) in visited:
                continue
            
            if self.grid[row][col] < density_threshold:
                continue
            
            visited.add((row, col))
            cluster_cells.append((row, col))
            
            # Check 4 adjacent cells (up, down, left, right)
            neighbors = [
                (row - 1, col),  # Up
                (row + 1, col),  # Down
                (row, col - 1),  # Left
                (row, col + 1)   # Right
            ]
            
            for nr, nc in neighbors:
                if 0 <= nr < self.grid_rows and 0 <= nc < self.grid_cols:
                    if (nr, nc) not in visited:
                        queue.append((nr, nc))
        
        return cluster_cells
    
    def _build_cluster(self, cells: List[Tuple[int, int]]) -> Dict:
        """
        Build cluster dictionary from list of cells.
        
        Args:
            cells: List of (row, col) cells
            
        Returns:
            Cluster dictionary
        """
        if not cells:
            return {"center": (0, 0), "count": 0, "cells": [], "risk": "LOW"}
        
        # Calculate total count
        total_count = sum(self.grid[row][col] for row, col in cells)
        
        # Calculate centroid
        total_x = 0.0
        total_y = 0.0
        
        for row, col in cells:
            cx, cy = self._cell_to_position(row, col)
            weight = self.grid[row][col]
            total_x += cx * weight
            total_y += cy * weight
        
        if total_count > 0:
            center_x = total_x / total_count
            center_y = total_y / total_count
        else:
            center_x, center_y = self._cell_to_position(cells[0][0], cells[0][1])
        
        return {
            "center": (round(center_x, 2), round(center_y, 2)),
            "count": total_count,
            "cells": cells,
            "risk": self._calculate_risk(total_count)
        }
    
    def _calculate_risk(self, count: int) -> str:
        """
        Calculate risk level based on cluster size.
        
        Args:
            count: Number of devices in cluster
            
        Returns:
            "LOW", "MEDIUM", or "HIGH"
        """
        high_threshold = self.config["HIGH_THRESHOLD"]
        medium_threshold = self.config["MEDIUM_THRESHOLD"]
        
        if count >= high_threshold:
            return "HIGH"
        elif count >= medium_threshold:
            return "MEDIUM"
        else:
            return "LOW"
    
    def get_clusters(self) -> List[Dict]:
        """
        Get all detected clusters.
        
        Returns:
            List of cluster dictionaries with:
            - center: (x, y) position
            - count: Number of devices
            - risk: "LOW", "MEDIUM", or "HIGH"
        """
        # Return simplified cluster info (without cells)
        return [
            {
                "center": c["center"],
                "count": c["count"],
                "risk": c["risk"]
            }
            for c in self.clusters
        ]
    
    def get_max_cluster_size(self) -> int:
        """
        Get size of largest current cluster.
        
        Returns:
            Number of devices in largest cluster, or 0 if no clusters
        """
        if not self.clusters:
            return 0
        return max(c["count"] for c in self.clusters)
    
    def get_cluster_risk_score(self) -> float:
        """
        Calculate overall clustering risk score.
        
        Returns:
            Float from 0.0 (dispersed) to 1.0 (dangerous clustering)
        """
        if not self.clusters:
            return 0.0
        
        high_threshold = self.config["HIGH_THRESHOLD"]
        
        # Score based on largest cluster
        max_size = self.get_max_cluster_size()
        size_score = min(1.0, max_size / (high_threshold * 1.5))
        
        # Score based on number of clusters
        num_clusters = len(self.clusters)
        cluster_count_score = min(1.0, num_clusters / 5)
        
        # Score based on high-risk clusters
        high_risk_count = sum(1 for c in self.clusters if c["risk"] == "HIGH")
        high_risk_score = min(1.0, high_risk_count / 2)
        
        # Weighted combination
        total_score = (
            size_score * 0.5 +
            cluster_count_score * 0.2 +
            high_risk_score * 0.3
        )
        
        return round(min(1.0, total_score), 3)
    
    def get_high_risk_clusters(self) -> List[Dict]:
        """
        Get only HIGH risk clusters.
        
        Returns:
            List of high-risk cluster dictionaries
        """
        return [c for c in self.get_clusters() if c["risk"] == "HIGH"]
    
    def get_grid_density(self) -> List[List[int]]:
        """
        Get raw grid density values.
        
        Returns:
            2D list of device counts per cell
        """
        return [row[:] for row in self.grid]
    
    def get_density_heatmap(self) -> List[List[float]]:
        """
        Get normalized density heatmap (0.0 to 1.0).
        
        Returns:
            2D list of normalized density values
        """
        max_density = max(max(row) for row in self.grid) if self.grid else 1
        if max_density == 0:
            max_density = 1
        
        return [
            [min(1.0, cell / max_density) for cell in row]
            for row in self.grid
        ]
    
    def get_statistics(self) -> Dict:
        """
        Get clustering statistics.
        
        Returns:
            Dictionary with various statistics
        """
        return {
            "num_clusters": len(self.clusters),
            "max_cluster_size": self.get_max_cluster_size(),
            "max_cluster_ever": self.max_cluster_ever,
            "risk_score": self.get_cluster_risk_score(),
            "high_risk_count": len(self.get_high_risk_clusters()),
            "clusters": self.get_clusters()
        }
    
    def reset(self):
        """Reset detector state."""
        self._reset_grid()
        self.clusters = []
        self.cluster_history.clear()
        self.max_cluster_ever = 0


# ═══════════════════════════════════════════════════════════
#                       TEST SUITE
# ═══════════════════════════════════════════════════════════

def print_grid(grid: List[List[int]], title: str = "Grid"):
    """Print ASCII grid visualization."""
    print(f"\n  {title}:")
    print("  ┌" + "──" * len(grid[0]) + "┐")
    
    for row in reversed(grid):  # Reverse for correct Y orientation
        line = "  │"
        for val in row:
            if val == 0:
                line += "  "
            elif val < 10:
                line += f" {val}"
            else:
                line += f"{val}"
        line += "│"
        print(line)
    
    print("  └" + "──" * len(grid[0]) + "┘")


def print_clusters(clusters: List[Dict]):
    """Print cluster information."""
    if not clusters:
        print("  No clusters detected")
        return
    
    risk_emoji = {"LOW": "🟢", "MEDIUM": "🟡", "HIGH": "🔴"}
    
    for i, cluster in enumerate(clusters):
        emoji = risk_emoji.get(cluster["risk"], "⚪")
        cx, cy = cluster["center"]
        print(f"  [{i+1}] {emoji} {cluster['risk']:6s} | "
              f"Count: {cluster['count']:2d} | "
              f"Center: ({cx:.1f}, {cy:.1f})")


def main():
    """Run cluster detector tests."""
    print("\n")
    print("╔═══════════════════════════════════════════════════════════╗")
    print("║                    STAMPEDE SHIELD                        ║")
    print("║             Cluster Detector - Test Suite                 ║")
    print("╚═══════════════════════════════════════════════════════════╝")
    
    # Create detector
    detector = ClusterDetector(
        room_bounds=(10, 10),
        cell_size=2.0,
        config={
            "MIN_CLUSTER_SIZE": 3,
            "MEDIUM_THRESHOLD": 5,
            "HIGH_THRESHOLD": 8,
            "DENSITY_THRESHOLD": 2
        }
    )
    
    # ═══════════════════════════════════════════════════════════
    # TEST 1: No clusters (dispersed)
    # ═══════════════════════════════════════════════════════════
    print("\n" + "=" * 60)
    print("TEST 1: Dispersed Crowd (No Clusters)")
    print("=" * 60)
    
    dispersed_positions = [
        (1, 1), (3, 3), (5, 5), (7, 7), (9, 9),
        (1, 9), (9, 1), (5, 1), (1, 5)
    ]
    
    detector.update(dispersed_positions)
    
    print(f"\n  Positions: {len(dispersed_positions)} devices scattered")
    print_grid(detector.get_grid_density(), "Density Grid")
    
    print("\n  Clusters detected:")
    print_clusters(detector.get_clusters())
    
    print(f"\n  Risk Score: {detector.get_cluster_risk_score():.3f}")
    
    # ═══════════════════════════════════════════════════════════
    # TEST 2: Single cluster
    # ═══════════════════════════════════════════════════════════
    print("\n" + "=" * 60)
    print("TEST 2: Single Cluster")
    print("=" * 60)
    
    cluster_positions = [
        # Cluster near center
        (5.0, 5.0), (5.2, 5.1), (4.8, 5.2),
        (5.1, 4.9), (5.3, 5.0), (4.9, 5.1),
        # Some scattered
        (1, 1), (9, 9)
    ]
    
    detector.update(cluster_positions)
    
    print(f"\n  Positions: {len(cluster_positions)} devices (6 clustered)")
    print_grid(detector.get_grid_density(), "Density Grid")
    
    print("\n  Clusters detected:")
    print_clusters(detector.get_clusters())
    
    print(f"\n  Risk Score: {detector.get_cluster_risk_score():.3f}")
    print(f"  Max Cluster Size: {detector.get_max_cluster_size()}")
    
    # ═══════════════════════════════════════════════════════════
    # TEST 3: High-risk cluster (8+ devices)
    # ═══════════════════════════════════════════════════════════
    print("\n" + "=" * 60)
    print("TEST 3: HIGH Risk Cluster (8+ devices)")
    print("=" * 60)
    
    high_risk_positions = [
        # Large cluster near door (5, 0)
        (5.0, 0.5), (5.1, 0.6), (4.9, 0.4),
        (5.2, 0.5), (4.8, 0.6), (5.0, 0.7),
        (5.1, 0.4), (4.9, 0.5), (5.0, 0.6),
        (5.2, 0.7), (4.8, 0.4),
        # Scattered elsewhere
        (1, 8), (9, 8)
    ]
    
    detector.update(high_risk_positions)
    
    print(f"\n  Positions: {len(high_risk_positions)} devices (11 at door!)")
    print_grid(detector.get_grid_density(), "Density Grid")
    
    print("\n  Clusters detected:")
    print_clusters(detector.get_clusters())
    
    print(f"\n  Risk Score: {detector.get_cluster_risk_score():.3f}")
    print(f"  High Risk Clusters: {len(detector.get_high_risk_clusters())}")
    
    # ═══════════════════════════════════════════════════════════
    # TEST 4: Multiple clusters
    # ═══════════════════════════════════════════════════════════
    print("\n" + "=" * 60)
    print("TEST 4: Multiple Clusters")
    print("=" * 60)
    
    multi_cluster_positions = [
        # Cluster 1: Top-left (corner A)
        (0.5, 9.5), (0.6, 9.4), (0.4, 9.6),
        (0.5, 9.3), (0.7, 9.5),
        # Cluster 2: Bottom-center (door)
        (5.0, 0.5), (5.1, 0.4), (4.9, 0.6),
        (5.2, 0.5), (4.8, 0.5), (5.0, 0.4),
        (5.1, 0.6), (4.9, 0.5),
        # Cluster 3: Top-right (corner B)
        (9.5, 9.5), (9.4, 9.6), (9.6, 9.4),
        (9.5, 9.3),
        # Scattered
        (5, 5), (3, 3)
    ]
    
    detector.update(multi_cluster_positions)
    
    print(f"\n  Positions: {len(multi_cluster_positions)} devices in 3 clusters")
    print_grid(detector.get_grid_density(), "Density Grid")
    
    print("\n  Clusters detected:")
    print_clusters(detector.get_clusters())
    
    stats = detector.get_statistics()
    print(f"\n  Statistics:")
    print(f"    Total Clusters: {stats['num_clusters']}")
    print(f"    Max Cluster Size: {stats['max_cluster_size']}")
    print(f"    Risk Score: {stats['risk_score']:.3f}")
    print(f"    High Risk Count: {stats['high_risk_count']}")
    
    # ═══════════════════════════════════════════════════════════
    # TEST 5: Adjacent cells forming large cluster
    # ═══════════════════════════════════════════════════════════
    print("\n" + "=" * 60)
    print("TEST 5: Adjacent Cells (Large Cluster)")
    print("=" * 60)
    
    adjacent_positions = [
        # Spread across 2x2 cells but adjacent
        # Cell (2,2) - around (5,5)
        (5.0, 5.0), (5.1, 5.1), (5.2, 5.2),
        # Cell (2,3) - around (5,7)
        (5.0, 6.5), (5.1, 6.6), (5.2, 6.4),
        # Cell (3,2) - around (7,5)
        (6.5, 5.0), (6.6, 5.1), (6.4, 5.2),
        # Cell (3,3) - around (7,7)
        (6.5, 6.5), (6.6, 6.6), (6.4, 6.4),
    ]
    
    detector.update(adjacent_positions)
    
    print(f"\n  Positions: {len(adjacent_positions)} devices in 2x2 adjacent cells")
    print_grid(detector.get_grid_density(), "Density Grid")
    
    print("\n  Clusters detected:")
    print_clusters(detector.get_clusters())
    
    print(f"\n  Risk Score: {detector.get_cluster_risk_score():.3f}")
    
    # ═══════════════════════════════════════════════════════════
    # VISUAL: Heatmap
    # ═══════════════════════════════════════════════════════════
    print("\n" + "=" * 60)
    print("VISUAL: Density Heatmap")
    print("=" * 60)
    
    # Use the multi-cluster scenario
    detector.update(multi_cluster_positions)
    
    heatmap = detector.get_density_heatmap()
    chars = " ░▒▓█"
    
    print("\n  Heatmap (normalized density):")
    print("  ┌" + "──" * len(heatmap[0]) + "┐")
    
    for row in reversed(heatmap):
        line = "  │"
        for val in row:
            idx = int(val * (len(chars) - 1))
            line += chars[idx] * 2
        line += "│"
        print(line)
    
    print("  └" + "──" * len(heatmap[0]) + "┘")
    print("\n  Legend: ' '=empty  ░=low  ▒=medium  ▓=high  █=cluster")
    
    # ═══════════════════════════════════════════════════════════
    # RISK PROGRESSION
    # ═══════════════════════════════════════════════════════════
    print("\n" + "=" * 60)
    print("DEMO: Risk Progression")
    print("=" * 60)
    
    print("\n  Simulating crowd building up at door...\n")
    
    import random
    
    base_positions = [(1, 8), (9, 8), (3, 5), (7, 5)]  # Scattered
    
    for stage in range(5):
        # Add more people at door (5, 0) each stage
        door_crowd = [
            (5 + random.uniform(-0.5, 0.5), 
             0.5 + random.uniform(-0.3, 0.3))
            for _ in range(stage * 3 + 2)
        ]
        
        all_positions = base_positions + door_crowd
        detector.update(all_positions)
        
        risk_score = detector.get_cluster_risk_score()
        max_size = detector.get_max_cluster_size()
        
        # Visual bar
        bar_len = int(risk_score * 20)
        bar = "█" * bar_len + "░" * (20 - bar_len)
        
        risk_color = "🟢" if risk_score < 0.3 else "🟡" if risk_score < 0.6 else "🔴"
        
        print(f"  Stage {stage + 1}: {len(door_crowd):2d} at door | "
              f"Max cluster: {max_size:2d} | "
              f"Risk: [{bar}] {risk_color} {risk_score:.2f}")
    
    # ═══════════════════════════════════════════════════════════
    # FINAL SUMMARY
    # ═══════════════════════════════════════════════════════════
    print("\n" + "=" * 60)
    print("SUMMARY")
    print("=" * 60)
    
    print("""
  Risk Levels:
    🟢 LOW    : 3-4 devices clustered
    🟡 MEDIUM : 5-7 devices clustered  
    🔴 HIGH   : 8+  devices clustered
    
  Risk Score:
    0.0 - 0.3 : Safe (dispersed crowd)
    0.3 - 0.6 : Warning (clustering forming)
    0.6 - 1.0 : Danger (dangerous clusters)
    """)
    
    print("✓ All tests complete!\n")


if __name__ == "__main__":
    main()