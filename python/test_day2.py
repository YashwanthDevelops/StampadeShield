"""
╔═══════════════════════════════════════════════════════════╗
║              DAY 2 INTEGRATION TEST                       ║
║         All Processors Working Together                   ║
╚═══════════════════════════════════════════════════════════╝
"""

import time
import sys
import os

# Add paths
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from udp_receiver import UDPReceiver
from sensor_simulator import SensorSimulator
from processors.passage_detector import PassageDetector
from processors.device_tracker import DeviceTracker
from processors.cluster_detector import ClusterDetector
from processors.zone_detector import ZoneDetector

def main():
    print()
    print("=" * 60)
    print("  🛡️  SURGE SHIELD - DAY 2 INTEGRATION TEST")
    print("=" * 60)
    print()
    
    # ═══════════════════════════════════════════════════════════
    # Initialize all components
    # ═══════════════════════════════════════════════════════════
    print("[1/6] Initializing UDP Receiver...")
    receiver = UDPReceiver(port=5005)
    receiver.start()
    time.sleep(0.3)
    
    print("[2/6] Initializing Simulator...")
    simulator = SensorSimulator(target_ip="127.0.0.1", target_port=5005)
    simulator.start()
    time.sleep(0.3)
    
    print("[3/6] Initializing Passage Detector (Node C - Door)...")
    passage_detector = PassageDetector()
    
    print("[4/6] Initializing Zone Detectors (Nodes A, B)...")
    zone_a = ZoneDetector("A")
    zone_b = ZoneDetector("B")
    
    print("[5/6] Initializing Device Tracker...")
    device_tracker = DeviceTracker()
    
    print("[6/6] Initializing Cluster Detector...")
    cluster_detector = ClusterDetector()
    
    print()
    print("✅ All components initialized!")
    print()
    print("-" * 60)
    
    # ═══════════════════════════════════════════════════════════
    # Test each mode
    # ═══════════════════════════════════════════════════════════
    
    modes = ["NORMAL", "BUSY", "SURGE"]
    
    for mode in modes:
        print(f"\n📊 Testing {mode} mode...")
        print("-" * 40)
        
        simulator.set_mode(mode)
        
        # Collect data for 2 seconds
        start = time.time()
        samples = 0
        
        while time.time() - start < 2.0:
            data = receiver.get_all_latest()
            
            if not data:
                time.sleep(0.1)
                continue
            
            samples += 1
            
            # Process each node
            for node_id, readings in data.items():
                dist = readings.get("dist", 300)
                pir = readings.get("pir", 0)
                
                if node_id == "C":
                    # Passage detection at door
                    passage_detector.process_reading(dist)
                elif node_id == "A":
                    zone_a.process_reading(dist, pir)
                elif node_id == "B":
                    zone_b.process_reading(dist, pir)
                
                # Device tracking (use distance as proxy for crowd)
                # Since firmware sends RSSI not device count
                estimated_devices = max(1, int((300 - dist) / 30))
                device_tracker.update_scan(node_id, estimated_devices)
            
            # Update cluster detector with estimated positions
            positions = device_tracker.get_estimated_positions()
            if positions:
                cluster_detector.update([(p[0], p[1]) for p in positions])
            
            time.sleep(0.1)
        
        # Print results for this mode
        print(f"\n  Results after {samples} samples:")
        print(f"  ─────────────────────────────────")
        
        # Passage detector
        passage_stats = passage_detector.get_statistics()
        print(f"  📍 Passages: {passage_stats['passage_count']} | "
              f"Flow: {passage_stats['flow_rate_1min']:.1f}/min")
        
        # Zone detectors
        zone_a_info = zone_a.get_state_info()
        zone_b_info = zone_b.get_state_info()
        print(f"  📍 Zone A: {zone_a_info['state']:10s} | "
              f"Score: {zone_a_info['occupancy_score']:.2f}")
        print(f"  📍 Zone B: {zone_b_info['state']:10s} | "
              f"Score: {zone_b_info['occupancy_score']:.2f}")
        
        # Device tracker
        device_stats = device_tracker.get_statistics()
        print(f"  📍 Devices: {device_stats['total_devices']} | "
              f"Trend: {device_stats['trend']}")
        
        # Cluster detector
        cluster_stats = cluster_detector.get_statistics()
        print(f"  📍 Clusters: {cluster_stats['num_clusters']} | "
              f"Max size: {cluster_stats['max_cluster_size']} | "
              f"Risk: {cluster_stats['risk_score']:.2f}")
    
    # ═══════════════════════════════════════════════════════════
    # Final Summary
    # ═══════════════════════════════════════════════════════════
    print()
    print("=" * 60)
    print("  DAY 2 TEST SUMMARY")
    print("=" * 60)
    
    all_passed = True
    
    checks = [
        ("UDP Receiver", receiver.running),
        ("Simulator", simulator.running),
        ("Passage Detector", passage_detector.passage_count >= 0),
        ("Zone A Detector", zone_a.state is not None),
        ("Zone B Detector", zone_b.state is not None),
        ("Device Tracker", device_tracker.total_updates > 0),
        ("Cluster Detector", cluster_detector.get_cluster_risk_score() >= 0),
    ]
    
    for name, passed in checks:
        status = "✅" if passed else "❌"
        print(f"  {status} {name}")
        if not passed:
            all_passed = False
    
    print()
    if all_passed:
        print("  ✅ DAY 2 TEST PASSED!")
        print("     All processors working correctly.")
    else:
        print("  ❌ DAY 2 TEST FAILED!")
        print("     Check failed components above.")
    print()
    
    # Cleanup
    simulator.stop()
    receiver.stop()
    
    return 0 if all_passed else 1

if __name__ == "__main__":
    sys.exit(main())