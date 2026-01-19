#!/usr/bin/env python3
"""
╔═══════════════════════════════════════════════════════════╗
║                    STAMPEDE SHIELD                        ║
║              Integrated System Test Suite                 ║
╚═══════════════════════════════════════════════════════════╝

Tests all algorithms together with simulated data.
Demonstrates the complete data processing pipeline.

Usage:
    python test_integrated.py
    python test_integrated.py --scenario surge --duration 60

Author: StampedeShield Team
Version: 2.0
"""

import sys
import time
import threading
import argparse
from typing import Dict, Optional

# ═══════════════════════════════════════════════════════════
# IMPORTS - Adjust paths based on your project structure
# ═══════════════════════════════════════════════════════════

# Try different import styles based on project structure
try:
    # If running from project root with package structure
    from simulation.simulation import Simulator
    from ingestion.udp_receiver import UDPReceiver
    from processors.passage_detector import PassageDetector
    from processors.zone_detector import ZoneDetector
    from processors.device_tracker import DeviceTracker
    from processors.cluster_detector import ClusterDetector
    import config
except ImportError:
    # If all files are in same directory
    try:
        from simulator import Simulator
        from udp_receiver import UDPReceiver
        from passage_detector import PassageDetector
        from zone_detector import ZoneDetector
        from device_tracker import DeviceTracker
        from cluster_detector import ClusterDetector
        
        # Create a mock config if not available
        class MockConfig:
            PASSAGE_THRESHOLD = 50
            MIN_PASSAGE_DURATION = 200
            PASSAGE_COOLDOWN = 800
            BASELINE_DISTANCE = 300
            ZONE_CLEAR_DIST = 200
            ZONE_CROWDED_DIST = 80
            CLEAR_CONFIRM_TIME = 2.0
            CROWDED_CONFIRM_TIME = 1.0
            WIFI_MULTIPLIER = 1.4
            NODE_POSITIONS = {"A": (0, 10), "B": (10, 10), "C": (5, 0)}
            ROOM_BOUNDS = (10, 10)
        
        config = MockConfig()
        
    except ImportError as e:
        print(f"Error importing modules: {e}")
        print("\nPlease ensure all module files are in the same directory:")
        print("  - simulator.py")
        print("  - udp_receiver.py")
        print("  - passage_detector.py")
        print("  - zone_detector.py")
        print("  - device_tracker.py")
        print("  - cluster_detector.py")
        print("  - config.py (optional)")
        sys.exit(1)


class IntegratedTester:
    """
    Integrated test runner for all StampedeShield algorithms.
    
    Orchestrates:
    - Simulator (generates fake sensor data)
    - UDPReceiver (receives and parses data)
    - PassageDetector (counts people through door)
    - ZoneDetector (monitors corner zones)
    - DeviceTracker (tracks WiFi devices)
    - ClusterDetector (detects dangerous clusters)
    """
    
    def __init__(self, scenario: str = "surge", use_udp: bool = True):
        """
        Initialize the integrated tester.
        
        Args:
            scenario: Simulation scenario ("normal", "busy", "surge")
            use_udp: Whether to use UDP (True) or direct simulation (False)
        """
        self.scenario = scenario
        self.use_udp = use_udp
        self.running = False
        
        # Get config values
        self.config = self._build_config()
        
        # Initialize components
        self.simulator: Optional[Simulator] = None
        self.receiver: Optional[UDPReceiver] = None
        
        # Initialize processors
        self.passage_detector = PassageDetector({
            "PASSAGE_THRESHOLD": self.config.get("PASSAGE_THRESHOLD", 50),
            "MIN_PASSAGE_DURATION": self.config.get("MIN_PASSAGE_DURATION", 200),
            "PASSAGE_COOLDOWN": self.config.get("PASSAGE_COOLDOWN", 800),
            "BASELINE_DISTANCE": self.config.get("BASELINE_DISTANCE", 300)
        })
        
        self.zone_detector_a = ZoneDetector("A", {
            "ZONE_CLEAR_DIST": self.config.get("ZONE_CLEAR_DIST", 200),
            "ZONE_CROWDED_DIST": self.config.get("ZONE_CROWDED_DIST", 80),
            "CLEAR_CONFIRM_TIME": self.config.get("CLEAR_CONFIRM_TIME", 2.0),
            "CROWDED_CONFIRM_TIME": self.config.get("CROWDED_CONFIRM_TIME", 1.0)
        })
        
        self.zone_detector_b = ZoneDetector("B", {
            "ZONE_CLEAR_DIST": self.config.get("ZONE_CLEAR_DIST", 200),
            "ZONE_CROWDED_DIST": self.config.get("ZONE_CROWDED_DIST", 80),
            "CLEAR_CONFIRM_TIME": self.config.get("CLEAR_CONFIRM_TIME", 2.0),
            "CROWDED_CONFIRM_TIME": self.config.get("CROWDED_CONFIRM_TIME", 1.0)
        })
        
        self.device_tracker = DeviceTracker(
            node_positions=self.config.get("NODE_POSITIONS", {
                "A": (0, 10), "B": (10, 10), "C": (5, 0)
            }),
            config={"WIFI_MULTIPLIER": self.config.get("WIFI_MULTIPLIER", 1.4)}
        )
        
        self.cluster_detector = ClusterDetector(
            room_bounds=self.config.get("ROOM_BOUNDS", (10, 10)),
            cell_size=2.0
        )
        
        # Statistics
        self.start_time = 0
        self.updates_processed = 0
    
    def _build_config(self) -> Dict:
        """Build configuration dictionary from config module."""
        cfg = {}
        
        # Try to get values from config module
        config_attrs = [
            "PASSAGE_THRESHOLD", "MIN_PASSAGE_DURATION", "PASSAGE_COOLDOWN",
            "BASELINE_DISTANCE", "ZONE_CLEAR_DIST", "ZONE_CROWDED_DIST",
            "CLEAR_CONFIRM_TIME", "CROWDED_CONFIRM_TIME", "WIFI_MULTIPLIER",
            "NODE_POSITIONS", "ROOM_BOUNDS"
        ]
        
        for attr in config_attrs:
            if hasattr(config, attr):
                cfg[attr] = getattr(config, attr)
        
        return cfg
    
    def start(self):
        """Start all components."""
        print("\n[TEST] Starting integrated test...")
        
        self.running = True
        self.start_time = time.time()
        
        if self.use_udp:
            # Start UDP receiver
            print("[TEST] Starting UDP receiver...")
            self.receiver = UDPReceiver(port=4444)
            self.receiver.start()
            
            # Start simulator
            print(f"[TEST] Starting simulator (scenario: {self.scenario})...")
            self.simulator = Simulator(target_host="127.0.0.1", target_port=4444)
            self.simulator.start(self.scenario)
        else:
            # Create simulator for direct data generation
            print(f"[TEST] Creating direct simulator (scenario: {self.scenario})...")
            self.simulator = Simulator()
        
        print("[TEST] ✓ All components started\n")
    
    def stop(self):
        """Stop all components."""
        print("\n[TEST] Stopping all components...")
        
        self.running = False
        
        if self.simulator:
            self.simulator.stop()
        
        if self.receiver:
            self.receiver.stop()
        
        print("[TEST] ✓ All components stopped")
    
    def process_data(self, node_data: Dict) -> Dict:
        """
        Process data from a single node through all processors.
        
        Args:
            node_data: Dictionary with node sensor data
            
        Returns:
            Dictionary with all processor results
        """
        node_id = node_data.get("id") or node_data.get("node", "?")
        distance = node_data.get("dist") or node_data.get("distance", 400)
        pir = node_data.get("pir", 0)
        wifi_count = node_data.get("wifi_count", 0)
        db = node_data.get("db", 0)
        timestamp = time.time()
        
        results = {"node": node_id}
        
        # Process based on node type
        if node_id == "C":
            # Door node - passage detection
            passage_result = self.passage_detector.process_reading(distance, timestamp)
            results["passage"] = passage_result
        
        if node_id == "A":
            zone_result = self.zone_detector_a.process_reading(distance, pir, timestamp)
            results["zone"] = zone_result
        
        if node_id == "B":
            zone_result = self.zone_detector_b.process_reading(distance, pir, timestamp)
            results["zone"] = zone_result
        
        # Update device tracker for all nodes
        self.device_tracker.update_scan(node_id, wifi_count, timestamp)
        
        self.updates_processed += 1
        
        return results
    
    def get_system_status(self) -> Dict:
        """
        Get complete system status from all processors.
        
        Returns:
            Dictionary with all status information
        """
        # Get passage info
        passage_count = self.passage_detector.passage_count
        flow_rate = self.passage_detector.get_flow_rate()
        
        # Get zone states
        zone_a_state = self.zone_detector_a.state.value
        zone_b_state = self.zone_detector_b.state.value
        
        # Get device count and positions
        device_count = self.device_tracker.get_device_count()
        positions = self.device_tracker.get_estimated_positions()
        
        # Update cluster detector with positions
        self.cluster_detector.update([(x, y) for x, y, _ in positions])
        cluster_risk = self.cluster_detector.get_cluster_risk_score()
        max_cluster = self.cluster_detector.get_max_cluster_size()
        
        # Calculate elapsed time
        elapsed = time.time() - self.start_time if self.start_time else 0
        
        return {
            "elapsed": elapsed,
            "passages": passage_count,
            "flow_rate": flow_rate,
            "zone_a": zone_a_state,
            "zone_b": zone_b_state,
            "devices": device_count,
            "cluster_risk": cluster_risk,
            "max_cluster": max_cluster,
            "updates": self.updates_processed
        }
    
    def print_status(self, status: Dict):
        """Print formatted status line."""
        elapsed = status["elapsed"]
        minutes = int(elapsed // 60)
        seconds = int(elapsed % 60)
        
        # Determine overall risk level
        risk = status["cluster_risk"]
        if risk > 0.6:
            risk_indicator = "🔴"
        elif risk > 0.3:
            risk_indicator = "🟡"
        else:
            risk_indicator = "🟢"
        
        # Zone state emojis
        zone_emoji = {"CLEAR": "🟢", "OCCUPIED": "🟡", "CROWDED": "🔴"}
        zone_a_emoji = zone_emoji.get(status["zone_a"], "⚪")
        zone_b_emoji = zone_emoji.get(status["zone_b"], "⚪")
        
        print(
            f"[{minutes:02d}:{seconds:02d}] "
            f"Passages: {status['passages']:3d} | "
            f"Flow: {status['flow_rate']:5.1f}/min | "
            f"ZoneA: {zone_a_emoji}{status['zone_a']:8s} | "
            f"ZoneB: {zone_b_emoji}{status['zone_b']:8s} | "
            f"Devices: {status['devices']:3d} | "
            f"Cluster: {risk_indicator} {status['cluster_risk']:.2f}"
        )
    
    def run(self, duration: int = 60, update_interval: float = 1.0):
        """
        Run the integrated test.
        
        Args:
            duration: Test duration in seconds
            update_interval: Seconds between status updates
        """
        self.start()
        
        print("=" * 100)
        print(f"{'INTEGRATED TEST':^100}")
        print(f"{'Scenario: ' + self.scenario.upper() + ' | Duration: ' + str(duration) + 's':^100}")
        print("=" * 100)
        print()
        
        # Header
        print(
            f"{'[TIME]':8s} "
            f"{'Passages':10s} | "
            f"{'Flow':11s} | "
            f"{'ZoneA':14s} | "
            f"{'ZoneB':14s} | "
            f"{'Devices':9s} | "
            f"{'Cluster':12s}"
        )
        print("-" * 100)
        
        try:
            last_update = 0
            
            while self.running and (time.time() - self.start_time) < duration:
                current_time = time.time()
                
                # Get data from receiver or simulator
                if self.use_udp and self.receiver:
                    # Get all node data
                    all_data = self.receiver.get_all_data()
                    
                    for node_id, node_data in all_data.items():
                        self.process_data({"node": node_id, **node_data})
                
                else:
                    # Direct simulation mode (without UDP)
                    # Generate fake data directly
                    pass
                
                # Print status at intervals
                if current_time - last_update >= update_interval:
                    status = self.get_system_status()
                    self.print_status(status)
                    last_update = current_time
                
                # Small sleep to prevent CPU spinning
                time.sleep(0.1)
        
        except KeyboardInterrupt:
            print("\n\n[TEST] Interrupted by user")
        
        finally:
            self.stop()
        
        # Print final summary
        self._print_summary()
    
    def _print_summary(self):
        """Print test summary."""
        status = self.get_system_status()
        
        print("\n")
        print("=" * 100)
        print(f"{'TEST SUMMARY':^100}")
        print("=" * 100)
        
        print(f"""
  Duration:          {status['elapsed']:.1f} seconds
  Updates Processed: {status['updates']}
  
  📊 PASSAGE DETECTION (Node C):
     Total Passages: {status['passages']}
     Flow Rate:      {status['flow_rate']:.1f} passages/min
     
  📊 ZONE STATUS:
     Zone A: {status['zone_a']}
     Zone B: {status['zone_b']}
     
  📊 DEVICE TRACKING:
     Current Count:  {status['devices']}
     Peak Count:     {self.device_tracker.peak_count}
     
  📊 CLUSTER ANALYSIS:
     Risk Score:     {status['cluster_risk']:.3f}
     Max Cluster:    {status['max_cluster']} devices
     High Risk:      {len(self.cluster_detector.get_high_risk_clusters())} clusters
""")
        
        # Final risk assessment
        risk = status['cluster_risk']
        if risk > 0.7:
            print("  ⚠️  FINAL ASSESSMENT: 🔴 CRITICAL - Immediate intervention needed!")
        elif risk > 0.5:
            print("  ⚠️  FINAL ASSESSMENT: 🟠 HIGH - Close monitoring required")
        elif risk > 0.3:
            print("  ⚠️  FINAL ASSESSMENT: 🟡 ELEVATED - Situation developing")
        else:
            print("  ✓  FINAL ASSESSMENT: 🟢 SAFE - Normal crowd conditions")
        
        print()
        print("=" * 100)


def run_quick_test():
    """Run a quick test without UDP (direct simulation)."""
    print("\n")
    print("╔═══════════════════════════════════════════════════════════╗")
    print("║                    STAMPEDE SHIELD                        ║")
    print("║              Quick Integration Test (No UDP)              ║")
    print("╚═══════════════════════════════════════════════════════════╝")
    
    # Create processors
    passage_detector = PassageDetector({"PASSAGE_THRESHOLD": 50})
    zone_detector_a = ZoneDetector("A", {})
    zone_detector_b = ZoneDetector("B", {})
    device_tracker = DeviceTracker()
    cluster_detector = ClusterDetector(room_bounds=(10, 10))
    
    # Simulate surge scenario
    print("\n[TEST] Simulating SURGE scenario (30 seconds)...\n")
    print("-" * 90)
    print(f"{'[Time]':8s} {'Pass':5s} {'Flow':8s} {'ZoneA':10s} {'ZoneB':10s} {'Devices':8s} {'Risk':8s}")
    print("-" * 90)
    
    import random
    
    start_time = time.time()
    
    # Surge parameters (escalating over 30 seconds)
    for i in range(60):  # 30 seconds at 0.5s intervals
        current_time = start_time + (i * 0.5)
        progress = i / 60.0  # 0.0 to 1.0
        
        # Escalating values
        base_distance = 300 - (progress * 250)  # 300 -> 50
        wifi_count = int(5 + (progress * 30))   # 5 -> 35
        pir_prob = 0.2 + (progress * 0.7)       # 0.2 -> 0.9
        
        # Generate node data
        dist_a = max(30, base_distance + random.uniform(-30, 30))
        dist_b = max(30, base_distance + random.uniform(-20, 40))
        dist_c = max(20, base_distance * 0.5 + random.uniform(-20, 20))
        
        pir_a = 1 if random.random() < pir_prob else 0
        pir_b = 1 if random.random() < pir_prob else 0
        
        # Process readings
        passage_detector.process_reading(dist_c, current_time)
        zone_detector_a.process_reading(dist_a, pir_a, current_time)
        zone_detector_b.process_reading(dist_b, pir_b, current_time)
        
        device_tracker.update_scan("A", wifi_count + random.randint(-3, 3), current_time)
        device_tracker.update_scan("B", wifi_count + random.randint(-2, 2), current_time)
        device_tracker.update_scan("C", wifi_count + random.randint(-1, 5), current_time)
        
        # Update cluster detector
        positions = device_tracker.get_estimated_positions()
        cluster_detector.update([(x, y) for x, y, _ in positions])
        
        # Print every second
        if i % 2 == 0:
            elapsed = i * 0.5
            passages = passage_detector.passage_count
            flow = passage_detector.get_flow_rate()
            zone_a = zone_detector_a.state.value
            zone_b = zone_detector_b.state.value
            devices = device_tracker.get_device_count()
            risk = cluster_detector.get_cluster_risk_score()
            
            # Risk indicator
            risk_icon = "🟢" if risk < 0.3 else "🟡" if risk < 0.6 else "🔴"
            
            print(f"[{elapsed:5.1f}s] {passages:4d} {flow:6.1f}/m "
                  f"{zone_a:10s} {zone_b:10s} {devices:7d} {risk_icon} {risk:.2f}")
    
    print("-" * 90)
    
    # Final summary
    print(f"""
  ═══════════════════════════════════════════════════════════
  RESULTS:
  ═══════════════════════════════════════════════════════════
  
  Passages:      {passage_detector.passage_count}
  Flow Rate:     {passage_detector.get_flow_rate():.1f}/min
  Zone A:        {zone_detector_a.state.value}
  Zone B:        {zone_detector_b.state.value}
  Devices:       {device_tracker.get_device_count()}
  Cluster Risk:  {cluster_detector.get_cluster_risk_score():.3f}
  Max Cluster:   {cluster_detector.get_max_cluster_size()}
    """)
    
    print("✓ Quick test complete!\n")


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="StampedeShield Integrated Test Suite"
    )
    parser.add_argument(
        "--scenario", "-s",
        choices=["normal", "busy", "surge"],
        default="surge",
        help="Simulation scenario (default: surge)"
    )
    parser.add_argument(
        "--duration", "-d",
        type=int,
        default=60,
        help="Test duration in seconds (default: 60)"
    )
    parser.add_argument(
        "--quick", "-q",
        action="store_true",
        help="Run quick test without UDP"
    )
    parser.add_argument(
        "--no-udp",
        action="store_true",
        help="Disable UDP, use direct simulation"
    )
    
    args = parser.parse_args()
    
    print("\n")
    print("╔═══════════════════════════════════════════════════════════╗")
    print("║                    STAMPEDE SHIELD                        ║")
    print("║              Integrated System Test Suite                 ║")
    print("╚═══════════════════════════════════════════════════════════╝")
    
    if args.quick:
        run_quick_test()
    else:
        tester = IntegratedTester(
            scenario=args.scenario,
            use_udp=not args.no_udp
        )
        tester.run(duration=args.duration)


if __name__ == "__main__":
    main()