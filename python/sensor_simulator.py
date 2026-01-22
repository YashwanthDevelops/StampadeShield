"""
╔═══════════════════════════════════════════════════════════╗
║              SURGE SHIELD - SENSOR SIMULATOR              ║
║                 Matches Firmware JSON Format              ║
╚═══════════════════════════════════════════════════════════╝
"""

import socket
import time
import threading
import random
import json

class SensorSimulator:
    """
    Simulates 3 ESP32 sensor nodes sending UDP data.
    Matches the exact JSON format of the real firmware.
    """
    
    MODES = {
        "NORMAL": {
            "dist": (150, 300),
            "pir_prob": 0.05,
            "wifi": (3, 8),
            "sound": (30, 50),
            "description": "Low traffic, normal conditions"
        },
        "BUSY": {
            "dist": (50, 150),
            "pir_prob": 0.4,
            "wifi": (10, 20),
            "sound": (55, 75),
            "description": "High traffic, crowded"
        },
        "SURGE": {
            "dist": (15, 50),
            "pir_prob": 0.95,
            "wifi": (25, 40),
            "sound": (80, 100),
            "description": "Dangerous crowding"
        }
    }
    
    NODES = {
        "A": {"zone": "ENTRY", "has_sound": False},
        "B": {"zone": "CORRIDOR", "has_sound": False},
        "C": {"zone": "EXIT", "has_sound": True}
    }

    def __init__(self, target_ip: str = "127.0.0.1", target_port: int = 5005):
        self.target = (target_ip, target_port)
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.running = False
        self.thread = None
        self.mode = "NORMAL"
        self.start_time = time.time()
        
        # Smooth state for each node
        self.state = {
            node_id: {
                "dist": 200.0,
                "wifi": 5.0,
                "sound": 40.0,
                "pir_cooldown": 0
            }
            for node_id in self.NODES
        }

    def set_mode(self, mode: str) -> bool:
        """Set simulation mode."""
        mode = mode.upper()
        if mode in self.MODES:
            self.mode = mode
            print(f"[SIM] Mode: {mode} - {self.MODES[mode]['description']}")
            return True
        return False

    def start(self):
        """Start the simulator thread."""
        if not self.running:
            self.running = True
            self.start_time = time.time()
            self.thread = threading.Thread(target=self._loop, daemon=True)
            self.thread.start()
            print(f"[SIM] Simulator started → {self.target[0]}:{self.target[1]}")

    def stop(self):
        """Stop the simulator."""
        self.running = False
        if self.thread:
            self.thread.join(timeout=2)
        self.sock.close()
        print("[SIM] Simulator stopped")

    def _get_state_from_dist(self, dist: float) -> str:
        """Determine state based on distance."""
        if dist < 50:
            return "SURGE"
        elif dist < 100:
            return "CRITICAL"
        elif dist < 150:
            return "ELEVATED"
        elif dist < 200:
            return "NORMAL"
        else:
            return "CLEAR"

    def _loop(self):
        """Main simulation loop."""
        while self.running:
            targets = self.MODES[self.mode]
            
            for node_id, node_config in self.NODES.items():
                s = self.state[node_id]
                
                # --- Distance: Smooth transition ---
                target_dist = random.uniform(*targets["dist"])
                # Faster changes in SURGE mode
                alpha = 0.3 if self.mode == "SURGE" else 0.1
                s["dist"] = s["dist"] * (1 - alpha) + target_dist * alpha
                
                # Add some noise
                dist_noise = random.gauss(0, 5)
                final_dist = max(10, min(400, int(s["dist"] + dist_noise)))
                
                # --- PIR: Probability-based with cooldown ---
                if s["pir_cooldown"] > 0:
                    s["pir_cooldown"] -= 1
                    pir = 1
                else:
                    if random.random() < targets["pir_prob"]:
                        pir = 1
                        s["pir_cooldown"] = random.randint(3, 10)  # Stay triggered
                    else:
                        pir = 0
                
                # --- WiFi: Smooth transition (simulated RSSI) ---
                target_wifi = random.uniform(*targets["wifi"])
                s["wifi"] = s["wifi"] * 0.9 + target_wifi * 0.1
                # Convert to fake RSSI (more devices = stronger signal for demo)
                wifi_rssi = int(-80 + s["wifi"] * 2)
                
                # --- Sound: Only for Node C ---
                if node_config["has_sound"]:
                    target_sound = random.uniform(*targets["sound"])
                    s["sound"] = s["sound"] * 0.9 + target_sound * 0.1
                    final_sound = int(s["sound"])
                else:
                    final_sound = 0
                
                # --- Build payload (matches firmware format) ---
                payload = {
                    "id": node_id,
                    "zone": node_config["zone"],
                    "dist": final_dist,
                    "pir": pir,
                    "wifi": wifi_rssi,
                    "ts": int((time.time() - self.start_time) * 1000)
                }
                
                # Add sound only for Node C
                if node_config["has_sound"]:
                    payload["sound"] = final_sound
                    payload["state"] = self._get_state_from_dist(final_dist)
                
                # --- Send UDP packet ---
                try:
                    msg = json.dumps(payload)
                    self.sock.sendto(msg.encode(), self.target)
                except Exception as e:
                    print(f"[SIM] Send error: {e}")
            
            time.sleep(0.1)  # 10Hz update rate

    def send_single(self, node_id: str, **kwargs) -> bool:
        """Send a single custom packet for testing."""
        if node_id not in self.NODES:
            return False
        
        payload = {
            "id": node_id,
            "zone": self.NODES[node_id]["zone"],
            "dist": kwargs.get("dist", 200),
            "pir": kwargs.get("pir", 0),
            "wifi": kwargs.get("wifi", -70),
            "ts": int((time.time() - self.start_time) * 1000)
        }
        
        if self.NODES[node_id]["has_sound"]:
            payload["sound"] = kwargs.get("sound", 40)
        
        try:
            self.sock.sendto(json.dumps(payload).encode(), self.target)
            return True
        except:
            return False


# ═══════════════════════════════════════════════════════════
#                    INTERACTIVE MODE
# ═══════════════════════════════════════════════════════════

if __name__ == "__main__":
    print()
    print("╔═══════════════════════════════════════════════════════════╗")
    print("║              SURGE SHIELD - SENSOR SIMULATOR              ║")
    print("╚═══════════════════════════════════════════════════════════╝")
    print()
    
    sim = SensorSimulator()
    sim.start()
    
    print()
    print("Commands:")
    print("  NORMAL  - Low traffic simulation")
    print("  BUSY    - High traffic simulation")
    print("  SURGE   - Emergency/stampede simulation")
    print("  q       - Quit")
    print()
    
    try:
        while True:
            cmd = input("Mode > ").strip().upper()
            
            if cmd == 'Q':
                break
            elif cmd in sim.MODES:
                sim.set_mode(cmd)
            elif cmd == '':
                continue
            else:
                print(f"Unknown command: {cmd}")
                print("Valid modes: NORMAL, BUSY, SURGE")
                
    except KeyboardInterrupt:
        print("\nInterrupted")
    finally:
        sim.stop()
        print("Done!")