import os
import sys
import json
from datetime import datetime

import paho.mqtt.client as mqtt
from telegram_alert import TelegramAlert

# Telegram Configuration - Load from environment variables
TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN", "")
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID", "")

if not TELEGRAM_TOKEN or not TELEGRAM_CHAT_ID:
    print("=" * 65)
    print("  ⚠️  WARNING: Telegram credentials not configured!")
    print("  Set TELEGRAM_TOKEN and TELEGRAM_CHAT_ID environment variables")
    print("  Alerts will be disabled until credentials are provided.")
    print("=" * 65)
    telegram = None
else:
    telegram = TelegramAlert(TELEGRAM_TOKEN, TELEGRAM_CHAT_ID)

# Add algorithms to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'algorithms'))

from zone_detector import ZoneDetector
from cluster_detector import ClusterDetector
from stampede_predictor import StampedePredictor

# MQTT Settings
BROKER = "broker.hivemq.com"
PORT = 1883
TOPIC = "stampede/data"

# Initialize algorithms
zone_detector = ZoneDetector()
cluster_detector = ClusterDetector()
predictor = StampedePredictor(zone_detector, cluster_detector)

# Node data storage
nodes = {
    "NODE_A": {"dist": 400, "pir": 0, "mic": 0},
    "NODE_B": {"dist": 400, "pir": 0, "mic": 0},
    "NODE_C": {"dist": 400, "pir": 0, "mic": 0}
}

message_count = 0
mqtt_client = None  # Global reference for publishing commands


def print_dashboard():
    """Print the full dashboard"""
    
    # Get prediction
    mic = nodes["NODE_C"].get("mic", 0)
    result = predictor.predict(mic)
    
    # Level emoji
    level_emoji = {
        "SAFE": "🟢",
        "LOW": "🟡", 
        "MODERATE": "🟠",
        "HIGH": "🔴",
        "CRITICAL": "🚨"
    }
    
    print()
    print("=" * 65)
    print("           🚨 STAMPEDE PREVENTION SYSTEM 🚨")
    print("=" * 65)
    
    # Risk display
    emoji = level_emoji.get(result["level"], "⚪")
    print(f"\n  RISK: {emoji} {result['level']} ({result['risk']}%)")
    
    # CPI Display (NEW!)
    print(f"  CROWD PRESSURE INDEX (CPI): {result['cpi']}")
    
    # CPI Breakdown (NEW!)
    breakdown = result.get("cpi_breakdown")
    if breakdown:
        print(f"    ├─ Density:  {breakdown['density']:5.1f}%")
        print(f"    ├─ Motion:   {breakdown['motion']:5.1f}%")
        print(f"    ├─ Audio:    {breakdown['audio']:5.1f}%")
        print(f"    └─ Trend:    {breakdown['trend']:5.1f}%")
    
    if result["time_to_danger"] is not None:
        print(f"\n  ⏱️  Time to critical: {result['time_to_danger']} seconds")
    
    # Zones
    print("\n  " + "-" * 61)
    print("  ZONES:")
    print("  " + "-" * 61)
    
    zones = zone_detector.get_all_zones()
    zone_emoji = {"GREEN": "🟢", "YELLOW": "🟡", "ORANGE": "🟠", "RED": "🔴", "BLACK": "⚫"}
    
    node_map = {"ENTRY": "NODE_A", "CENTER": "NODE_C", "EXIT": "NODE_B"}
    
    for name in ["ENTRY", "CENTER", "EXIT"]:
        z = zones[name]
        node = nodes[node_map[name]]
        e = zone_emoji.get(z["status"], "⚪")
        print(f"  {e} {name:7} | Dist: {node['dist']:5.1f}cm | Density: {z['density']:.1f}/m² | Risk: {z['risk']}%")
    
    # Clusters
    clusters = cluster_detector.clusters
    if clusters:
        print("\n  " + "-" * 61)
        print("  CLUSTERS:")
        print("  " + "-" * 61)
        for c in clusters:
            print(f"  📍 {c['zone']}: {c['severity']} - ~{c['people']} people")
    
    # Audio
    print("\n  " + "-" * 61)
    print("  AUDIO:")
    print("  " + "-" * 61)
    
    mic = nodes["NODE_C"].get("mic", 0)
    if mic > 700:
        print(f"  🔊 Level: {mic} (SCREAM DETECTED!)")
    elif mic > 400:
        print(f"  🔊 Level: {mic} (LOUD)")
    else:
        print(f"  🎤 Level: {mic} (Normal)")
    
    # Factors
    print("\n  " + "-" * 61)
    print("  RISK FACTORS:")
    print("  " + "-" * 61)
    for factor in result["factors"]:
        print(f"  {factor}")
    
    # Recommendation
    print("\n  " + "-" * 61)
    print(f"  {result['recommendation']}")
    print("=" * 65)

    # Publish alert level to Node C LEDs
    if mqtt_client:
        mqtt_client.publish("stampede/commands", result["level"])
    
    # Send Telegram alert if HIGH or CRITICAL
    if result["level"] in ["HIGH", "CRITICAL"] and telegram:
        telegram.send_alert(
            result["level"],
            result["risk"],
            result["cpi"],
            result["recommendation"],
            result["factors"]
        )


def on_connect(client, userdata, flags, rc):
    print()
    print("=" * 65)
    print("  ✅ Connected to MQTT Broker")
    print("  📡 Waiting for sensor data...")
    print("=" * 65)
    client.subscribe(TOPIC)


def on_message(client, userdata, msg):
    global message_count
    
    try:
        data = json.loads(msg.payload.decode())
        node_id = data.get("id", "UNKNOWN")
        
        if node_id not in nodes:
            return
        
        # Update node data
        nodes[node_id]["dist"] = data.get("dist", 400)
        nodes[node_id]["pir"] = data.get("pir", 0)
        if "mic" in data:
            nodes[node_id]["mic"] = data["mic"]
        
        # Update zone detector
        zone_detector.update(
            node_id,
            data.get("dist", 400),
            data.get("pir", 0),
            data.get("mic", None)
        )
        
        # Update cluster detector
        node_data = {
            "NODE_A": {"dist": nodes["NODE_A"]["dist"], "pir": nodes["NODE_A"]["pir"]},
            "NODE_B": {"dist": nodes["NODE_B"]["dist"], "pir": nodes["NODE_B"]["pir"]},
            "NODE_C": {"dist": nodes["NODE_C"]["dist"], "pir": nodes["NODE_C"]["pir"]}
        }
        cluster_detector.update(node_data)
        
        message_count += 1
        
        # Dashboard every 8 messages
        if message_count % 8 == 0:
            print_dashboard()
        else:
            # Simple line
            dist = data.get("dist", 0)
            pir = "MOV" if data.get("pir", 0) else "---"
            mic_str = f" | Mic:{data['mic']}" if "mic" in data else ""
            print(f"  [{node_id}] D:{dist:5.1f}cm | {pir}{mic_str}")
    
    except Exception as e:
        print(f"  Error: {e}")


def main():
    global mqtt_client
    
    print()
    print("=" * 65)
    print("         🚨 STAMPEDE PREVENTION SYSTEM 🚨")
    print("              Algorithm Edition v1.0")
    print("=" * 65)
    
    client = mqtt.Client()
    client.on_connect = on_connect
    client.on_message = on_message
    mqtt_client = client  # Store reference for publishing
    
    try:
        print("\n  Connecting to broker...")
        client.connect(BROKER, PORT, 60)
        client.loop_forever()
    except KeyboardInterrupt:
        print("\n  🛑 System stopped")
    except Exception as e:
        print(f"\n  ❌ Error: {e}")


if __name__ == "__main__":
    main()