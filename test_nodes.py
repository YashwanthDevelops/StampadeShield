# test_nodes.py - Simple UDP listener for all nodes
import socket
import json

sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
sock.bind(("0.0.0.0", 5005))

print("=" * 50)
print("  STAMPEDE SHIELD - NODE TEST")
print("=" * 50)
print("Waiting for nodes...\n")

nodes_seen = set()

while True:
    data, addr = sock.recvfrom(1024)
    try:
        msg = json.loads(data.decode())
        node = msg.get("id", "?")
        zone = msg.get("zone", "?")
        dist = msg.get("dist", 0)
        pir = msg.get("pir", 0)
        
        nodes_seen.add(node)
        
        print(f"[Node {node}] {zone:8} | dist={dist:3}cm | pir={pir} | online: {sorted(nodes_seen)}")
        
        if len(nodes_seen) == 3:
            print("\n✅ ALL 3 NODES CONNECTED!\n")
            
    except Exception as e:
        print(f"Error: {e}")