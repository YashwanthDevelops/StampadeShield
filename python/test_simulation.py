import time
import threading
from udp_receiver import UDPReceiver
from sensor_simulator import SensorSimulator

def run_integration_test():
    print("--- Starting Integration Test ---")
    
    # 1. Start Receiver
    receiver = UDPReceiver(port=5005)
    receiver.start()
    
    # 2. Start Simulator
    sim = SensorSimulator(target_port=5005)
    sim.start()
    
    try:
        # Monitor Loop
        for i in range(3):
            print(f"\n[Seconds: {i}] Latest Data:")
            print(receiver.get_all_latest())
            time.sleep(1)

        # Switch Mode
        print("\n>>> Switching to BUSY mode")
        sim.set_mode("BUSY")
        time.sleep(2)
        print(f"Latest Data (BUSY): {receiver.get_all_latest()}")

        print("\n>>> Switching to SURGE mode")
        sim.set_mode("SURGE")
        time.sleep(2)
        print(f"Latest Data (SURGE): {receiver.get_all_latest()}")

    finally:
        sim.stop()
        receiver.stop()
        print("\n--- Test Complete ---")

if __name__ == "__main__":
    run_integration_test()
