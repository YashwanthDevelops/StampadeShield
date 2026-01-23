"""
STAMPEDE PREVENTION SYSTEM - COORDINATOR WITH ALGORITHMS
"""

import paho.mqtt.client as mqtt
import json
from datetime import datetime

# MQTT Settings
BROKER = "broker.hivemq.com"
PORT = 1883
TOPIC = "stampede/data"

# Store data from nodes
nodes = {
    "NODE_A": {"dist": 400, "pir": 0, "time": None},
    "NODE_B": {"dist": 400, "pir": 0, "time": None},
    "NODE_C": {"dist": 400, "pir": 0, "mic": 0, "time": None}
}

# Thresholds
DIST_SAFE = 100       # cm - above this is safe
DIST_WARNING = 50     # cm - below this is warning
DIST_DANGER = 30      # cm - below this is danger
MIC_LOUD = 400        # above this is loud
MIC_SCREAM = 700      # above this is scream

def calculate_density(distance):
    """Convert distance to density level"""
    if distance > DIST_SAFE:
        return "LOW"
    elif distance > DIST_WARNING:
        return "MEDIUM"
    elif distance > DIST_DANGER:
        return "HIGH"
    else:
        return "CRITICAL"

def calculate_risk():
    """Calculate overall risk from all nodes"""
    risk_score = 0
    
    # Distance risk (0-40 points per node)
    for node_id, data in nodes.items():
        dist = data["dist"]
        if dist < DIST_DANGER:
            risk_score += 40
        elif dist < DIST_WARNING:
            risk_score += 25
        elif dist < DIST_SAFE:
            risk_score += 10
    
    # PIR risk (0-10 points per node)
    motion_count = sum(1 for n in nodes.values() if n["pir"] == 1)
    risk_score += motion_count * 10
    
    # Mic risk (0-30 points)
    mic = nodes["NODE_C"].get("mic", 0)
    if mic > MIC_SCREAM:
        risk_score += 30
    elif mic > MIC_LOUD:
        risk_score += 15
    
    return min(100, risk_score)

def get_risk_level(score):
    """Convert score to level"""
    if score >= 80:
        return "🚨 CRITICAL"
    elif score >= 60:
        return "🔴 HIGH"
    elif score >= 40:
        return "🟠 MEDIUM"
    elif score >= 20:
        return "🟡 LOW"
    else:
        return "🟢 SAFE"

def print_status():
    """Print dashboard"""
    risk = calculate_risk()
    level = get_risk_level(risk)
    
    print()
    print("=" * 60)
    print(f"  RISK LEVEL: {level} ({risk}%)")
    print("=" * 60)
    print()
    print("  NODE      DISTANCE    DENSITY     MOTION")
    print("  ----      --------    -------     ------")
    
    for node_id in ["NODE_A", "NODE_B", "NODE_C"]:
        data = nodes[node_id]
        dist = data["dist"]
        density = calculate_density(dist)
        motion = "YES" if data["pir"] == 1 else "No"
        
        print(f"  {node_id}    {dist:6.1f} cm    {density:8}    {motion}")
    
    # Mic status
    mic = nodes["NODE_C"].get("mic", 0)
    mic_status = "🔊 SCREAM!" if mic > MIC_SCREAM else ("🔊 LOUD" if mic > MIC_LOUD else "Normal")
    print()
    print(f"  Audio Level: {mic} ({mic_status})")
    print()
    
    # Warnings
    if risk >= 60:
        print("  ⚠️  WARNING: High crowd density detected!")
    if mic > MIC_SCREAM:
        print("  ⚠️  WARNING: Possible panic/screaming!")
    
    print("=" * 60)

def on_connect(client, userdata, flags, rc):
    print("✅ Connected to MQTT Broker")
    print("📡 Waiting for data...")
    print()
    client.subscribe(TOPIC)

message_count = 0

def on_message(client, userdata, msg):
    global message_count
    
    try:
        payload = msg.payload.decode()
        data = json.loads(payload)
        
        node_id = data.get("id", "UNKNOWN")
        
        if node_id in nodes:
            nodes[node_id]["dist"] = data.get("dist", 400)
            nodes[node_id]["pir"] = data.get("pir", 0)
            nodes[node_id]["time"] = datetime.now()
            
            if "mic" in data:
                nodes[node_id]["mic"] = data["mic"]
        
        message_count += 1
        
        # Print full status every 5 messages
        if message_count % 5 == 0:
            print_status()
        else:
            # Print simple line
            dist = data.get("dist", 0)
            pir = "MOTION" if data.get("pir", 0) == 1 else "Clear"
            mic = data.get("mic", None)
            
            line = f"[{node_id}] D:{dist:5.1f}cm | {pir}"
            if mic is not None:
                line += f" | Mic:{mic}"
            print(line)
        
    except Exception as e:
        print(f"Error: {e}")

def main():
    print()
    print("=" * 60)
    print("       STAMPEDE PREVENTION SYSTEM")
    print("       Coordinator with Risk Analysis")
    print("=" * 60)
    print()
    
    client = mqtt.Client()
    client.on_connect = on_connect
    client.on_message = on_message
    
    try:
        client.connect(BROKER, PORT, 60)
        client.loop_forever()
    except KeyboardInterrupt:
        print("\n🛑 Stopped")

if __name__ == "__main__":
    main()