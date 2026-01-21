import socket
import json
import time
import threading
from udp_receiver import UDPReceiver

def test_callback(data):
    print(f"CALLBACK RECEIVED: {data}")

def run_test():
    receiver = UDPReceiver(port=5005)
    receiver.on_data(test_callback)
    receiver.start()
    
    # Give the thread a moment to start
    time.sleep(0.5)

    sender_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    dest = ("127.0.0.1", 5005) # Since we bound to 0.0.0.0, sending to localhost works
    
    # 1. Test sending data
    print("\n--- Test 1: Sending Data ---")
    data_packet = {"id": "NodeA", "dist": 100, "temp": 25}
    sender_sock.sendto(json.dumps(data_packet).encode('utf-8'), dest)
    time.sleep(0.5) # Wait for processing
    
    latest = receiver.get_latest("NodeA")
    print(f"Latest for NodeA: {latest}")
    assert latest == data_packet, "Data mismatch!"

    # 2. Test get_all_latest
    print("\n--- Test 2: Multiple Nodes ---")
    data_packet_b = {"id": "NodeB", "dist": 200}
    sender_sock.sendto(json.dumps(data_packet_b).encode('utf-8'), dest)
    time.sleep(0.5)
    
    all_latest = receiver.get_all_latest()
    print(f"All latest: {all_latest}")
    assert "NodeA" in all_latest and "NodeB" in all_latest, "Missing nodes in all_latest"

    # 3. Test timeout
    print("\n--- Test 3: Timeout ---")
    print("Waiting for 3.5 seconds...")
    time.sleep(3.5)
    
    latest_a = receiver.get_latest("NodeA")
    print(f"Latest for NodeA after timeout: {latest_a}")
    assert latest_a is None, "NodeA should be timed out!"
    
    all_latest_timeout = receiver.get_all_latest()
    print(f"All latest after timeout: {all_latest_timeout}")
    assert len(all_latest_timeout) == 0, "All nodes should be timed out!"
    
    # 4. Test re-connect
    print("\n--- Test 4: Re-connect ---")
    sender_sock.sendto(json.dumps(data_packet).encode('utf-8'), dest)
    time.sleep(0.5)
    latest_re = receiver.get_latest("NodeA")
    print(f"Latest for NodeA after reconnect: {latest_re}")
    assert latest_re == data_packet, "NodeA should be back!"

    receiver.stop()
    print("\n--- All Tests Passed ---")

if __name__ == "__main__":
    run_test()
