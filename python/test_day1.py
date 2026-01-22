"""
╔═══════════════════════════════════════════════════════════╗
║              DAY 1 INTEGRATION TEST                       ║
║         UDP Receiver + Sensor Simulator                   ║
╚═══════════════════════════════════════════════════════════╝
"""

import time
import sys
from udp_receiver import UDPReceiver
from sensor_simulator import SensorSimulator

def main():
    print("=" * 60)
    print("  🛡️  SURGE SHIELD - DAY 1 INTEGRATION TEST")
    print("=" * 60)
    print()
    
    # Start UDP Receiver
    print("[1/3] Starting UDP Receiver on port 5005...")
    receiver = UDPReceiver(port=5005)
    receiver.start()
    time.sleep(0.5)
    
    # Start Simulator
    print("[2/3] Starting Sensor Simulator...")
    simulator = SensorSimulator(target_ip="127.0.0.1", target_port=5005)
    simulator.start()
    time.sleep(0.5)
    
    print("[3/3] Running test sequence...")
    print()
    print("-" * 60)
    
    # Test each mode
    modes = ["NORMAL", "BUSY", "SURGE"]
    
    for mode in modes:
        print(f"\n📊 Testing {mode} mode...")
        simulator.set_mode(mode)
        time.sleep(1.5)  # Let values stabilize
        
        # Get data from all nodes
        data = receiver.get_all_latest()
        
        print(f"   Active nodes: {list(data.keys())}")
        
        for node_id in ["A", "B", "C"]:
            if node_id in data:
                d = data[node_id]
                dist = d.get("dist", "?")
                pir = d.get("pir", "?")
                wifi = d.get("wifi", "?")
                sound = d.get("sound", "?")
                
                # Status indicator
                if isinstance(dist, int):
                    if dist < 50:
                        status = "🔴"
                    elif dist < 150:
                        status = "🟡"
                    else:
                        status = "🟢"
                else:
                    status = "❓"
                
                print(f"   Node {node_id}: {status} dist={dist}cm, pir={pir}, wifi={wifi}, sound={sound}")
            else:
                print(f"   Node {node_id}: ❌ OFFLINE")
    
    print()
    print("-" * 60)
    
    # Verify all nodes received
    final_data = receiver.get_all_latest()
    all_nodes_ok = all(n in final_data for n in ["A", "B", "C"])
    
    if all_nodes_ok:
        print()
        print("  ✅ DAY 1 TEST PASSED!")
        print("     • UDP Receiver working")
        print("     • Simulator sending data")
        print("     • All 3 nodes received")
        print()
    else:
        print()
        print("  ❌ DAY 1 TEST FAILED!")
        print(f"     Missing nodes: {[n for n in ['A','B','C'] if n not in final_data]}")
        print()
    
    # Cleanup
    simulator.stop()
    receiver.stop()
    
    return 0 if all_nodes_ok else 1

if __name__ == "__main__":
    sys.exit(main())