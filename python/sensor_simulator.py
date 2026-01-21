import socket
import time
import threading
import random
import json

class SensorSimulator:
    MODES = {
        "NORMAL": {"dist": (150, 300), "pir_prob": 0.05, "wifi": (2, 5), "sound": (30, 50)},
        "BUSY":   {"dist": (50, 150),  "pir_prob": 0.3,  "wifi": (8, 15), "sound": (50, 70)},
        "SURGE":  {"dist": (20, 60),   "pir_prob": 1.0,  "wifi": (20, 30), "sound": (80, 100)}
    }

    def __init__(self, target_ip="127.0.0.1", target_port=5005):
        self.target = (target_ip, target_port)
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.running = False
        self.thread = None
        self.mode = "NORMAL"
        self.nodes = ["A", "B", "C"]
        # Current simulated values for smooth transitions
        self.state = {n: {"dist": 200.0, "wifi": 3.0, "sound": 40.0} for n in self.nodes}

    def set_mode(self, mode):
        if mode in self.MODES:
            self.mode = mode
            print(f"Switched to {mode} mode")

    def start(self):
        if not self.running:
            self.running = True
            self.thread = threading.Thread(target=self._loop, daemon=True)
            self.thread.start()
            print("Simulator started")

    def stop(self):
        self.running = False
        if self.thread:
            self.thread.join()

    def _loop(self):
        while self.running:
            targets = self.MODES[self.mode]
            for node_id in self.nodes:
                # Interpolate values towards target midpoints (smoothing)
                s = self.state[node_id]
                
                # Distance: fast changes in SURGE, slower otherwise
                tgt_dist = random.uniform(*targets["dist"])
                alpha = 0.3 if self.mode == "SURGE" else 0.1
                s["dist"] = s["dist"] * (1 - alpha) + tgt_dist * alpha

                # Wifi & Sound: gradual drift
                tgt_wifi = random.uniform(*targets["wifi"])
                tgt_sound = random.uniform(*targets["sound"])
                s["wifi"] = s["wifi"] * 0.95 + tgt_wifi * 0.05
                s["sound"] = s["sound"] * 0.95 + tgt_sound * 0.05

                # PIR: Binary trigger based on probability
                pir = 1 if random.random() < targets["pir_prob"] else 0

                payload = {
                    "id": node_id,
                    "dist": int(s["dist"]),
                    "pir": pir,
                    "wifi": int(s["wifi"]),
                    "sound": int(s["sound"])
                }
                
                try:
                    self.sock.sendto(json.dumps(payload).encode(), self.target)
                except Exception as e:
                    print(f"Send error: {e}")

            time.sleep(0.1)  # 10Hz

if __name__ == "__main__":
    sim = SensorSimulator()
    sim.start()
    try:
        while True:
            cmd = input("Enter mode (NORMAL, BUSY, SURGE) or 'q' to quit: ").strip().upper()
            if cmd == 'Q': break
            if cmd in sim.MODES: sim.set_mode(cmd)
            else: print("Invalid mode")
    finally:
        sim.stop()
