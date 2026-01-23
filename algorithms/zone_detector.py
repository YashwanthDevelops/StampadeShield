"""
ZONE DETECTOR
Monitors Entry, Center, Exit zones
"""

from datetime import datetime
from collections import deque


class ZoneDetector:
    def __init__(self):
        self.zones = {
            "ENTRY": {
                "node": "NODE_A",
                "status": "GREEN",
                "density": 0,
                "risk": 0,
                "history": deque(maxlen=60)
            },
            "CENTER": {
                "node": "NODE_C",
                "status": "GREEN",
                "density": 0,
                "risk": 0,
                "history": deque(maxlen=60)
            },
            "EXIT": {
                "node": "NODE_B",
                "status": "GREEN",
                "density": 0,
                "risk": 0,
                "history": deque(maxlen=60)
            }
        }
    
    def distance_to_density(self, distance):
        """Convert distance to crowd density"""
        if distance <= 0 or distance > 400:
            return 0.5
        
        density = max(0.5, min(8.0, (400 - distance) / 50))
        return round(density, 1)
    
    def get_status(self, distance):
        """Get zone status from distance"""
        if distance > 100:
            return "GREEN"
        elif distance > 50:
            return "YELLOW"
        elif distance > 30:
            return "ORANGE"
        elif distance > 15:
            return "RED"
        else:
            return "BLACK"
    
    def update(self, node_id, distance, pir, mic=None):
        """Update zone with new sensor data"""
        
        zone_name = None
        for name, zone in self.zones.items():
            if zone["node"] == node_id:
                zone_name = name
                break
        
        if zone_name is None:
            return None
        
        zone = self.zones[zone_name]
        zone["density"] = self.distance_to_density(distance)
        zone["status"] = self.get_status(distance)
        zone["history"].append({
            "time": datetime.now(),
            "dist": distance,
            "pir": pir
        })
        zone["risk"] = self.calculate_risk(zone_name)
        
        return zone
    
    def calculate_risk(self, zone_name):
        """Calculate risk for a zone (0-100)"""
        zone = self.zones[zone_name]
        risk = 0
        
        # Density risk (0-50)
        d = zone["density"]
        if d > 6:
            risk += 50
        elif d > 4:
            risk += 35
        elif d > 2:
            risk += 20
        elif d > 1:
            risk += 10
        
        # Trend risk (0-30)
        if len(zone["history"]) >= 10:
            recent = [r["dist"] for r in list(zone["history"])[-5:]]
            older = [r["dist"] for r in list(zone["history"])[-10:-5]]
            
            recent_avg = sum(recent) / 5
            older_avg = sum(older) / 5
            
            if recent_avg < older_avg - 20:
                risk += 30
            elif recent_avg < older_avg - 10:
                risk += 20
            elif recent_avg < older_avg:
                risk += 10
        
        # Motion risk (0-20)
        if len(zone["history"]) >= 5:
            motion = sum(1 for r in list(zone["history"])[-5:] if r["pir"])
            risk += motion * 4
        
        return min(100, risk)
    
    def get_all_zones(self):
        """Get summary of all zones"""
        return {
            name: {
                "status": z["status"],
                "density": z["density"],
                "risk": z["risk"]
            }
            for name, z in self.zones.items()
        }
    
    def get_critical_zones(self):
        """Get zones in critical state"""
        critical = []
        for name, zone in self.zones.items():
            if zone["status"] in ["RED", "BLACK"]:
                critical.append(name)
        return critical