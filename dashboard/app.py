"""
STAMPEDE SHIELD - Web Dashboard
Flask Server
"""

from flask import Flask, render_template, jsonify
import paho.mqtt.client as mqtt
import json
import threading
from datetime import datetime
from collections import deque
import sys
import os

# Add parent folder to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'algorithms'))

from zone_detector import ZoneDetector
from cluster_detector import ClusterDetector
from stampede_predictor import StampedePredictor

app = Flask(__name__)

# Initialize algorithms
zone_detector = ZoneDetector()
cluster_detector = ClusterDetector()
predictor = StampedePredictor(zone_detector, cluster_detector)

CALIBRATION_FILE = 'calibration.json'

def load_calibration():
    try:
        if os.path.exists(CALIBRATION_FILE):
            with open(CALIBRATION_FILE, 'r') as f:
                data = json.load(f)
                for zone, dist in data.items():
                    zone_detector.set_baseline(zone, dist)
            print("Reverted to saved calibration")
    except Exception as e:
        print(f"Calibration load error: {e}")

load_calibration()

# Store node data
nodes = {
    "NODE_A": {"dist": 400, "pir": 0, "mic": 0, "online": False, "last_seen": None, "uptime": 0, "last_heartbeat": None},
    "NODE_B": {"dist": 400, "pir": 0, "mic": 0, "online": False, "last_seen": None, "uptime": 0, "last_heartbeat": None},
    "NODE_C": {"dist": 400, "pir": 0, "mic": 0, "online": False, "last_seen": None, "uptime": 0, "last_heartbeat": None}
}

# Risk history for prediction
risk_history = deque(maxlen=30)

# MQTT Settings
BROKER = "broker.hivemq.com"
TOPIC = "stampede/data"
COMMAND_TOPIC = "stampede/commands"

# Global MQTT client for publishing commands
mqtt_client = None
mqtt_client_lock = threading.Lock()

def calculate_confidence():
    """Calculate system confidence based on node availability and data quality"""
    online_count = sum(1 for n in nodes.values() if n["online"])
    base_confidence = (online_count / 3) * 100
    
    # Reduce confidence if data is old
    for node in nodes.values():
        if node["last_seen"]:
            age = (datetime.now() - node["last_seen"]).total_seconds()
            if age > 5:
                base_confidence -= 10
    
    return max(0, min(100, int(base_confidence)))

def predict_timeline():
    """Predict risk levels for next 2 minutes"""
    if len(risk_history) < 5:
        current = predictor.current_risk
        return {
            "now": get_level_from_risk(current),
            "30s": get_level_from_risk(current),
            "60s": get_level_from_risk(current),
            "120s": get_level_from_risk(current)
        }
    
    # Calculate trend
    recent = list(risk_history)[-5:]
    trend = (recent[-1] - recent[0]) / 5  # Risk change per reading
    
    current = predictor.current_risk
    
    # Predict future (each reading is ~2 seconds, so 15 readings = 30s)
    pred_30s = min(100, max(0, current + (trend * 15)))
    pred_60s = min(100, max(0, current + (trend * 30)))
    pred_120s = min(100, max(0, current + (trend * 60)))
    
    return {
        "now": get_level_from_risk(current),
        "30s": get_level_from_risk(pred_30s),
        "60s": get_level_from_risk(pred_60s),
        "120s": get_level_from_risk(pred_120s)
    }

def get_level_from_risk(risk):
    """Convert risk score to level"""
    if risk >= 80:
        return "CRITICAL"
    elif risk >= 60:
        return "HIGH"
    elif risk >= 40:
        return "MODERATE"
    elif risk >= 20:
        return "LOW"
    else:
        return "SAFE"

def get_recommended_actions():
    """Generate priority-ordered actions with reasons"""
    actions = []
    zones = zone_detector.get_all_zones()
    
    # Check EXIT zone
    if zones["EXIT"]["status"] in ["RED", "BLACK"]:
        actions.append({
            "priority": 1,
            "action": "Stop Entry",
            "reason": f"EXIT density {zones['EXIT']['density']}/m²"
        })
    
    # Check for bottleneck
    worst = cluster_detector.get_worst_cluster()
    if worst and worst["severity"] == "CRITICAL":
        actions.append({
            "priority": 2,
            "action": "Open Secondary Exit",
            "reason": f"Bottleneck at {worst['zone']}"
        })
    
    # Check audio trend
    mic = nodes["NODE_C"].get("mic", 0)
    if mic > 400:
        actions.append({
            "priority": 3,
            "action": "Activate PA System",
            "reason": "Elevated noise levels"
        })
    
    # Check entry zone
    if zones["ENTRY"]["status"] in ["ORANGE", "RED", "BLACK"]:
        actions.append({
            "priority": 4,
            "action": "Deploy Crowd Control",
            "reason": f"ENTRY density rising"
        })
    
    if not actions:
        actions.append({
            "priority": 1,
            "action": "Continue Monitoring",
            "reason": "No immediate action required"
        })
    
    return sorted(actions, key=lambda x: x["priority"])

def on_connect(client, userdata, flags, rc, properties):
    print(f"Dashboard connected to MQTT (rc={rc})")
    client.subscribe(TOPIC)
    client.subscribe("stampede/health")  # Subscribe to health heartbeats

def on_message(client, userdata, msg):
    try:
        data = json.loads(msg.payload.decode())
        
        # Handle heartbeat messages
        if msg.topic == "stampede/health":
            node_id = data.get("id", "UNKNOWN")
            if node_id in nodes:
                nodes[node_id]["uptime"] = data.get("uptime", 0)
                nodes[node_id]["last_heartbeat"] = datetime.now()
                print(f"💓 Heartbeat from {node_id} (uptime: {data.get('uptime', 0)}s)")
            return
        
        # Handle sensor data messages
        node_id = data.get("id", "UNKNOWN")
        
        if node_id in nodes:
            nodes[node_id]["dist"] = data.get("dist", 400)
            nodes[node_id]["pir"] = data.get("pir", 0)
            nodes[node_id]["online"] = True
            nodes[node_id]["last_seen"] = datetime.now()
            
            if "mic" in data:
                nodes[node_id]["mic"] = data["mic"]
            
            # Update algorithms
            zone_detector.update(
                node_id,
                data.get("dist", 400),
                data.get("pir", 0),
                data.get("mic", None)
            )
            
            node_data = {
                "NODE_A": {"dist": nodes["NODE_A"]["dist"], "pir": nodes["NODE_A"]["pir"]},
                "NODE_B": {"dist": nodes["NODE_B"]["dist"], "pir": nodes["NODE_B"]["pir"]},
                "NODE_C": {"dist": nodes["NODE_C"]["dist"], "pir": nodes["NODE_C"]["pir"]}
            }
            
            cluster_detector.update(node_data)
            
            # Run prediction
            mic = nodes["NODE_C"].get("mic", 0)
            predictor.predict(mic)
            
            # Publish alert level to Node C LEDs
            with mqtt_client_lock:
                if mqtt_client and mqtt_client.is_connected():
                    mqtt_client.publish(COMMAND_TOPIC, predictor.risk_level)
            
            # Store risk history
            risk_history.append(predictor.current_risk)
            
    except Exception as e:
        print(f"Error: {e}")

# Start MQTT in background
def start_mqtt():
    global mqtt_client
    client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)
    client.on_connect = on_connect
    client.on_message = on_message
    
    while True:
        try:
            client.connect(BROKER, 1883, 60)
            with mqtt_client_lock:
                mqtt_client = client 
            break
        except Exception as e:
            print(f"MQTT Connection Failed: {e}. Retrying in 5s...")
            import time
            time.sleep(5)
            
    try:
        client.loop_forever()
    except Exception as e:
        print(f"MQTT Loop Error: {e}")

mqtt_thread = threading.Thread(target=start_mqtt, daemon=True)
mqtt_thread.start()

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/api/calibrate', methods=['POST'])
def calibrate():
    """
    Saves current distances as the 'empty room' baseline.
    In a real scenario, this would save to a file/database.
    For now, we update the zone detector thresholds.
    """
    try:
        # Get current distances
        dist_a = nodes["NODE_A"]["dist"]
        dist_b = nodes["NODE_B"]["dist"]
        dist_c = nodes["NODE_C"]["dist"]
        
        # Update zone detector thresholds dynamically
        zone_detector.set_baseline("ENTRY", dist_a)
        zone_detector.set_baseline("EXIT", dist_b)
        zone_detector.set_baseline("CENTER", dist_c)
        
        print(f"CALIBRATION: Baseline set to A:{dist_a}, B:{dist_b}, C:{dist_c}")
        
        # Save to file for persistence
        new_baselines = {
            "ENTRY": dist_a,
            "EXIT": dist_b,
            "CENTER": dist_c
        }
        with open(CALIBRATION_FILE, 'w') as f:
            json.dump(new_baselines, f)
            
        return jsonify({"status": "success", "message": "Baseline updated"})
    except Exception as e:
        print(f"Calibration error: {e}")
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route('/api/data')
def get_data():
    """API endpoint for live data"""
    
    mic = nodes["NODE_C"].get("mic", 0)
    result = predictor.predict(mic)
    zones = zone_detector.get_all_zones()
    
    # Check node online status
    for node_id, node in nodes.items():
        if node["last_seen"]:
            age = (datetime.now() - node["last_seen"]).total_seconds()
            node["online"] = age < 10
        else:
            node["online"] = False
    
    return jsonify({
        "timestamp": datetime.now().strftime("%H:%M:%S"),
        "risk": {
            "level": result["level"],
            "score": result["risk"],
            "confidence": calculate_confidence()
        },
        "cpi": {
            "value": result["cpi"],
            "confidence": calculate_confidence(),
            "breakdown": result.get("cpi_breakdown", {})
        },
        "zones": {
            "ENTRY": {
                "status": zones["ENTRY"]["status"],
                "distance": nodes["NODE_A"]["dist"],
                "density": zones["ENTRY"]["density"],
                "risk": zones["ENTRY"]["risk"],
                "detection_type": zones["ENTRY"]["detection_type"]
            },
            "CENTER": {
                "status": zones["CENTER"]["status"],
                "distance": nodes["NODE_C"]["dist"],
                "density": zones["CENTER"]["density"],
                "risk": zones["CENTER"]["risk"],
                "detection_type": zones["CENTER"]["detection_type"]
            },
            "EXIT": {
                "status": zones["EXIT"]["status"],
                "distance": nodes["NODE_B"]["dist"],
                "density": zones["EXIT"]["density"],
                "risk": zones["EXIT"]["risk"],
                "detection_type": zones["EXIT"]["detection_type"]
            }
        },
        "audio": {
            "level": mic,
            "state": "SCREAM" if mic > 700 else ("LOUD" if mic > 400 else "NORMAL")
        },
        "timeline": predict_timeline(),
        "time_to_critical": result.get("time_to_danger"),
        "actions": get_recommended_actions(),
        "factors": result.get("factors", []),
        "recommendation": result.get("recommendation", ""),
        "nodes": {
            "NODE_A": {"online": nodes["NODE_A"]["online"], "uptime": nodes["NODE_A"]["uptime"]},
            "NODE_B": {"online": nodes["NODE_B"]["online"], "uptime": nodes["NODE_B"]["uptime"]},
            "NODE_C": {"online": nodes["NODE_C"]["online"], "uptime": nodes["NODE_C"]["uptime"]}
        }
    })

if __name__ == '__main__':
    print("="*50)
    print("  STAMPEDE SHIELD - Dashboard Server")
    print("="*50)
    print()
    print("  Open browser: http://localhost:5000")
    print()
    print("="*50)
    app.run(debug=False, host='0.0.0.0', port=5000)