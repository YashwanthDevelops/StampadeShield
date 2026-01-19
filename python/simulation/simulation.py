#!/usr/bin/env python3
"""
╔═══════════════════════════════════════════════════════════╗
║                    STAMPEDE SHIELD                        ║
║              Simulator for Testing (No Hardware)          ║
╚═══════════════════════════════════════════════════════════╝

Generates fake sensor data that mimics real ESP32 nodes.
Sends via UDP to test the receiver/dashboard without hardware.

Usage:
    python simulator.py

Author: StampedeShield Team
"""

import socket
import json
import threading
import time
import random
import math
from datetime import datetime


class NodeSimulator:
    """Simulates a single ESP32 node with realistic sensor behavior."""
    
    def __init__(self, node_id, has_microphone=False):
        """
        Initialize a node simulator.
        
        Args:
            node_id: Node identifier ('A', 'B', or 'C')
            has_microphone: Whether this node has a microphone (Node C)
        """
        self.node_id = node_id
        self.has_microphone = has_microphone
        
        # Current sensor values
        self.distance = 200.0
        self.pir = 0
        self.wifi_count = 5
        self.db = 40 if has_microphone else None
        
        # Target values (for smooth transitions)
        self.target_distance = 200.0
        self.target_wifi = 5
        self.target_db = 40
        
        # Simulation parameters
        self.pir_probability = 0.2
        self.uptime = 0
        
        # Add some personality to each node
        self.distance_offset = random.uniform(-20, 20)
        self.wifi_offset = random.randint(-2, 2)
    
    def update(self, scenario_params):
        """
        Update sensor values based on scenario parameters.
        
        Args:
            scenario_params: Dictionary with scenario configuration
        """
        # Extract parameters
        dist_min = scenario_params.get('dist_min', 100)
        dist_max = scenario_params.get('dist_max', 300)
        wifi_min = scenario_params.get('wifi_min', 5)
        wifi_max = scenario_params.get('wifi_max', 10)
        pir_prob = scenario_params.get('pir_probability', 0.2)
        db_min = scenario_params.get('db_min', 35)
        db_max = scenario_params.get('db_max', 60)
        
        # Occasionally change targets (creates natural variation)
        if random.random() < 0.1:  # 10% chance each update
            self.target_distance = random.uniform(dist_min, dist_max) + self.distance_offset
            self.target_wifi = random.randint(wifi_min, wifi_max) + self.wifi_offset
            if self.has_microphone:
                self.target_db = random.uniform(db_min, db_max)
        
        # Smooth transition towards targets
        self.distance += (self.target_distance - self.distance) * 0.1
        self.wifi_count += int((self.target_wifi - self.wifi_count) * 0.2)
        if self.has_microphone:
            self.db += (self.target_db - self.db) * 0.15
        
        # Add noise
        self.distance += random.uniform(-5, 5)
        self.distance = max(10, min(400, self.distance))  # Clamp 10-400
        
        self.wifi_count = max(0, min(50, self.wifi_count + random.randint(-1, 1)))
        
        if self.has_microphone:
            self.db += random.uniform(-3, 3)
            self.db = max(35, min(120, self.db))
        
        # PIR trigger based on probability
        self.pir = 1 if random.random() < pir_prob else 0
        
        # Increment uptime
        self.uptime += 1
    
    def get_status(self):
        """Calculate status based on current values."""
        if self.distance < 50:
            return "danger"
        if self.has_microphone and self.db and self.db > 85:
            return "danger"
        if self.distance < 100:
            return "warning"
        if self.has_microphone and self.db and self.db > 70:
            return "warning"
        if self.pir == 1:
            return "warning"
        return "safe"
    
    def get_data(self):
        """
        Get current node data as dictionary.
        
        Returns:
            dict: Node data ready for JSON serialization
        """
        data = {
            "node": self.node_id,
            "distance": round(self.distance, 1),
            "dist": round(self.distance, 1),  # Alias for compatibility
            "pir": self.pir,
            "wifi_count": self.wifi_count,
            "status": self.get_status(),
            "rssi": random.randint(-70, -40),
            "uptime": self.uptime,
            "timestamp": int(time.time())
        }
        
        if self.has_microphone:
            data["db"] = int(self.db)
        
        return data


class Simulator:
    """
    StampedeShield Hardware Simulator.
    
    Generates fake sensor data for testing without real ESP32 hardware.
    Sends data via UDP to the receiver/dashboard.
    """
    
    # Scenario configurations
    SCENARIOS = {
        "normal": {
            "name": "Normal",
            "description": "Low crowd, occasional movement",
            "dist_min": 150,
            "dist_max": 300,
            "wifi_min": 5,
            "wifi_max": 8,
            "pir_probability": 0.2,
            "db_min": 35,
            "db_max": 55,
            "color": "🟢"
        },
        "busy": {
            "name": "Busy",
            "description": "Moderate crowd, frequent movement",
            "dist_min": 80,
            "dist_max": 150,
            "wifi_min": 15,
            "wifi_max": 25,
            "pir_probability": 0.6,
            "db_min": 55,
            "db_max": 75,
            "color": "🟡"
        },
        "surge": {
            "name": "Surge",
            "description": "Escalating crowd - DANGER",
            "dist_min": 30,
            "dist_max": 80,
            "wifi_min": 25,
            "wifi_max": 40,
            "pir_probability": 0.95,
            "db_min": 75,
            "db_max": 100,
            "color": "🔴"
        }
    }
    
    def __init__(self, target_host="127.0.0.1", target_port=4444):
        """
        Initialize the simulator.
        
        Args:
            target_host: IP address to send UDP packets to
            target_port: UDP port to send packets to
        """
        self.target_host = target_host
        self.target_port = target_port
        
        # Create nodes
        self.nodes = {
            'A': NodeSimulator('A', has_microphone=False),
            'B': NodeSimulator('B', has_microphone=False),
            'C': NodeSimulator('C', has_microphone=True)
        }
        
        # Current scenario
        self.current_scenario = "normal"
        self.scenario_params = self.SCENARIOS["normal"].copy()
        
        # Control flags
        self.running = False
        self.sim_thread = None
        
        # UDP socket
        self.socket = None
        
        # Surge mode variables
        self.surge_mode = False
        self.surge_start_time = 0
        self.surge_duration = 30  # seconds
        
        # Statistics
        self.packets_sent = 0
        self.start_time = 0
    
    def start(self, scenario="normal"):
        """
        Start the simulation.
        
        Args:
            scenario: Initial scenario ('normal', 'busy', or 'surge')
        """
        if self.running:
            print("[SIM] Already running!")
            return
        
        # Set scenario
        self.set_scenario(scenario)
        
        # Create UDP socket
        self.socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
        
        # Start simulation
        self.running = True
        self.start_time = time.time()
        self.packets_sent = 0
        
        self.sim_thread = threading.Thread(target=self._simulation_loop, daemon=True)
        self.sim_thread.start()
        
        print(f"[SIM] ✓ Started simulation")
        print(f"[SIM]   Target: {self.target_host}:{self.target_port}")
        print(f"[SIM]   Scenario: {self.SCENARIOS[scenario]['name']}")
    
    def stop(self):
        """Stop the simulation."""
        if not self.running:
            print("[SIM] Not running!")
            return
        
        self.running = False
        
        if self.sim_thread:
            self.sim_thread.join(timeout=2.0)
        
        if self.socket:
            self.socket.close()
            self.socket = None
        
        print(f"[SIM] ✓ Stopped (sent {self.packets_sent} packets)")
    
    def set_scenario(self, scenario):
        """
        Switch to a different scenario.
        
        Args:
            scenario: Scenario name ('normal', 'busy', or 'surge')
        """
        if scenario not in self.SCENARIOS:
            print(f"[SIM] ⚠ Unknown scenario: {scenario}")
            print(f"[SIM]   Available: {', '.join(self.SCENARIOS.keys())}")
            return
        
        self.current_scenario = scenario
        self.scenario_params = self.SCENARIOS[scenario].copy()
        
        # Special handling for surge mode
        if scenario == "surge":
            self.surge_mode = True
            self.surge_start_time = time.time()
            print(f"[SIM] ⚠ SURGE MODE ACTIVATED - Escalating over {self.surge_duration} seconds!")
        else:
            self.surge_mode = False
        
        info = self.SCENARIOS[scenario]
        print(f"[SIM] Scenario: {info['color']} {info['name']} - {info['description']}")
    
    def _simulation_loop(self):
        """Main simulation loop (runs in background thread)."""
        print("[SIM] Simulation loop started\n")
        
        send_interval = 0.2  # 200ms between sends
        last_status_time = 0
        
        while self.running:
            loop_start = time.time()
            
            # Update surge progression if in surge mode
            if self.surge_mode:
                self._update_surge_progression()
            
            # Update and send data for each node
            for node_id, node in self.nodes.items():
                node.update(self.scenario_params)
                self._send_node_data(node)
            
            self.packets_sent += 3  # 3 nodes
            
            # Print status every 2 seconds
            if time.time() - last_status_time >= 2.0:
                last_status_time = time.time()
                self._print_status()
            
            # Wait for next interval
            elapsed = time.time() - loop_start
            sleep_time = max(0, send_interval - elapsed)
            time.sleep(sleep_time)
    
    def _update_surge_progression(self):
        """Update scenario parameters during surge escalation."""
        elapsed = time.time() - self.surge_start_time
        progress = min(1.0, elapsed / self.surge_duration)
        
        # Interpolate from normal to surge
        normal = self.SCENARIOS["normal"]
        surge = self.SCENARIOS["surge"]
        
        def lerp(a, b, t):
            return a + (b - a) * t
        
        # Apply easing (slow start, fast end)
        eased_progress = progress * progress  # Quadratic easing
        
        self.scenario_params = {
            "dist_min": lerp(normal["dist_min"], surge["dist_min"], eased_progress),
            "dist_max": lerp(normal["dist_max"], surge["dist_max"], eased_progress),
            "wifi_min": int(lerp(normal["wifi_min"], surge["wifi_min"], eased_progress)),
            "wifi_max": int(lerp(normal["wifi_max"], surge["wifi_max"], eased_progress)),
            "pir_probability": lerp(normal["pir_probability"], surge["pir_probability"], eased_progress),
            "db_min": lerp(normal["db_min"], surge["db_min"], eased_progress),
            "db_max": lerp(normal["db_max"], surge["db_max"], eased_progress),
        }
        
        # Print surge progress
        if int(elapsed) % 5 == 0 and elapsed > 0:
            bar_length = 20
            filled = int(bar_length * progress)
            bar = "█" * filled + "░" * (bar_length - filled)
            print(f"[SURGE] [{bar}] {int(progress * 100)}% - {int(self.surge_duration - elapsed)}s remaining")
    
    def _send_node_data(self, node):
        """
        Send node data via UDP.
        
        Args:
            node: NodeSimulator instance
        """
        if not self.socket:
            return
        
        try:
            data = node.get_data()
            json_str = json.dumps(data)
            self.socket.sendto(json_str.encode('utf-8'), (self.target_host, self.target_port))
        except Exception as e:
            print(f"[SIM] ⚠ Send error: {e}")
    
    def _print_status(self):
        """Print current simulation status."""
        print("-" * 65)
        print(f"[SIM] {datetime.now().strftime('%H:%M:%S')} | Scenario: {self.current_scenario.upper()} | Packets: {self.packets_sent}")
        
        for node_id, node in self.nodes.items():
            data = node.get_data()
            status = data['status']
            
            if status == 'danger':
                emoji = '🔴'
            elif status == 'warning':
                emoji = '🟡'
            else:
                emoji = '🟢'
            
            line = f"  [{node_id}] {emoji} Dist: {data['distance']:6.1f}cm | PIR: {data['pir']} | WiFi: {data['wifi_count']:2d}"
            
            if 'db' in data:
                line += f" | dB: {data['db']:3d}"
            
            print(line)
        
        print("-" * 65)
    
    def get_statistics(self):
        """
        Get simulation statistics.
        
        Returns:
            dict: Statistics dictionary
        """
        runtime = time.time() - self.start_time if self.start_time else 0
        return {
            "running": self.running,
            "scenario": self.current_scenario,
            "packets_sent": self.packets_sent,
            "runtime_seconds": int(runtime),
            "packets_per_second": round(self.packets_sent / runtime, 1) if runtime > 0 else 0
        }


def print_menu():
    """Print the interactive menu."""
    print("\n" + "=" * 50)
    print("           STAMPEDE SHIELD SIMULATOR")
    print("=" * 50)
    print("  1. 🟢 Start NORMAL scenario")
    print("  2. 🟡 Start BUSY scenario")
    print("  3. 🔴 Start SURGE scenario (escalating)")
    print("  4. ⏹  Stop simulation")
    print("  5. 📊 Show statistics")
    print("  6. 🚪 Exit")
    print("=" * 50)


def main():
    """Main entry point with interactive menu."""
    print("\n")
    print("╔═══════════════════════════════════════════════════════════╗")
    print("║                    STAMPEDE SHIELD                        ║")
    print("║              Hardware Simulator for Testing               ║")
    print("╚═══════════════════════════════════════════════════════════╝")
    print()
    print("This simulator generates fake sensor data for testing")
    print("the dashboard without real ESP32 hardware.")
    print()
    print("Target: UDP localhost:4444")
    print()
    
    # Create simulator
    sim = Simulator(target_host="127.0.0.1", target_port=4444)
    
    try:
        while True:
            print_menu()
            choice = input("\nEnter choice (1-6): ").strip()
            
            if choice == "1":
                if sim.running:
                    sim.stop()
                sim.start("normal")
                
            elif choice == "2":
                if sim.running:
                    sim.stop()
                sim.start("busy")
                
            elif choice == "3":
                if sim.running:
                    sim.stop()
                sim.start("surge")
                
            elif choice == "4":
                if sim.running:
                    sim.stop()
                else:
                    print("[SIM] Not running!")
                    
            elif choice == "5":
                stats = sim.get_statistics()
                print("\n📊 STATISTICS:")
                print(f"   Running: {'Yes' if stats['running'] else 'No'}")
                print(f"   Scenario: {stats['scenario']}")
                print(f"   Packets Sent: {stats['packets_sent']}")
                print(f"   Runtime: {stats['runtime_seconds']} seconds")
                print(f"   Rate: {stats['packets_per_second']} packets/sec")
                
            elif choice == "6":
                print("\n[SIM] Exiting...")
                break
                
            else:
                print("[SIM] ⚠ Invalid choice. Enter 1-6.")
            
            # Small delay to let output print
            time.sleep(0.5)
    
    except KeyboardInterrupt:
        print("\n\n[SIM] Caught Ctrl+C")
    
    finally:
        if sim.running:
            sim.stop()
        print("[SIM] Goodbye!\n")


# ==================== QUICK START MODE ====================
def quick_start(scenario="normal", duration=None):
    """
    Quick start simulation without menu.
    
    Args:
        scenario: Scenario to run ('normal', 'busy', 'surge')
        duration: How long to run in seconds (None = forever)
    
    Usage:
        python simulator.py normal 60    # Run normal for 60 seconds
        python simulator.py surge        # Run surge until Ctrl+C
    """
    print(f"\n[QUICK] Starting {scenario} simulation...")
    
    sim = Simulator()
    sim.start(scenario)
    
    try:
        if duration:
            print(f"[QUICK] Running for {duration} seconds...")
            time.sleep(duration)
        else:
            print("[QUICK] Running until Ctrl+C...")
            while True:
                time.sleep(1)
    except KeyboardInterrupt:
        print("\n[QUICK] Stopped by user")
    finally:
        sim.stop()


# ==================== ENTRY POINT ====================
if __name__ == "__main__":
    import sys
    
    # Check for command line arguments
    if len(sys.argv) > 1:
        scenario = sys.argv[1].lower()
        duration = int(sys.argv[2]) if len(sys.argv) > 2 else None
        quick_start(scenario, duration)
    else:
        main()