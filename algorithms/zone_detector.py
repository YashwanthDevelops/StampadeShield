"""
ZONE DETECTOR
Monitors Entry, Center, Exit zones
"""

from datetime import datetime
from collections import deque


class ZoneDetector:
    def __init__(self):
        self.baselines = {
            "ENTRY": 400,
            "CENTER": 400,
            "EXIT": 400
        }
        self.zones = {
            "ENTRY": {
                "node": "NODE_A",
                "status": "GREEN",
                "density": 0,
                "risk": 0,
                "detection_type": "UNKNOWN",
                "history": deque(maxlen=60)
            },
            "CENTER": {
                "node": "NODE_C",
                "status": "GREEN",
                "density": 0,
                "risk": 0,
                "detection_type": "UNKNOWN",
                "history": deque(maxlen=60)
            },
            "EXIT": {
                "node": "NODE_B",
                "status": "GREEN",
                "density": 0,
                "risk": 0,
                "detection_type": "UNKNOWN",
                "history": deque(maxlen=60)
            }
        }
    
    def set_baseline(self, zone_name, distance):
        """Update baseline distance for a zone"""
        if zone_name in self.baselines:
            self.baselines[zone_name] = distance
    
    def distance_to_density(self, distance, baseline=400):
        """Convert distance to crowd density"""
        if distance <= 0 or distance > baseline:
            return 0.5
        
        # Calculate density based on baseline
        # 50cm reduction = 1.0 increase in density roughly
        density = max(0.5, min(8.0, (baseline - distance) / 50))
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
        zone["density"] = self.distance_to_density(distance, self.baselines[zone_name])
        zone["status"] = self.get_status(distance)
        zone["history"].append({
            "time": datetime.now(),
            "dist": distance,
            "pir": pir
        })
        zone["risk"] = self.calculate_risk(zone_name)
        zone["detection_type"] = self.get_detection_type(zone_name)
        
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
        
        # VARIANCE CHECK: Real crowds cause fluctuating readings
        # Single person = stable distance = LOW variance = reduce risk
        variance_factor = 1.0
        if len(zone["history"]) >= 10:
            recent_dists = [r["dist"] for r in list(zone["history"])[-10:]]
            avg_dist = sum(recent_dists) / len(recent_dists)
            variance = sum((d - avg_dist) ** 2 for d in recent_dists) / len(recent_dists)
            
            # Low variance (< 25) = likely single person or stationary object
            # High variance (> 100) = crowd movement
            if variance < 25:
                variance_factor = 0.3  # Reduce risk by 70%
            elif variance < 50:
                variance_factor = 0.6  # Reduce risk by 40%
            elif variance > 100:
                variance_factor = 1.2  # Increase risk by 20%
        
        # Apply variance factor to density risk
        risk = int(risk * variance_factor)
        
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
        
        # Motion risk (0-20) - but REQUIRE motion for high risk
        if len(zone["history"]) >= 5:
            motion_count = sum(1 for r in list(zone["history"])[-5:] if r["pir"])
            risk += motion_count * 4
            
            # NO motion + close distance = NOT a crowd, reduce risk
            if motion_count == 0 and zone["density"] > 2:
                risk = int(risk * 0.5)
        
        return min(100, risk)
    
    def get_detection_type(self, zone_name):
        """
        Classify what was detected based on variance and PIR motion.
        
        Returns:
            WALL: Very low variance (< 5), no motion - wall/fixed obstruction
            STATIC_OBJECT: Low variance (< 25), no motion - stationary object
            SINGLE_PERSON: Low variance (< 25), with motion - one person
            CROWD: Higher variance (>= 25), with motion - crowd movement
            UNKNOWN: Insufficient data to classify
        """
        zone = self.zones[zone_name]
        
        if len(zone["history"]) < 10:
            return "UNKNOWN"
        
        recent = list(zone["history"])[-10:]
        recent_dists = [r["dist"] for r in recent]
        
        # Calculate variance
        avg_dist = sum(recent_dists) / len(recent_dists)
        variance = sum((d - avg_dist) ** 2 for d in recent_dists) / len(recent_dists)
        
        # Check PIR motion in recent history
        motion_count = sum(1 for r in recent if r["pir"])
        has_motion = motion_count >= 3  # At least 30% motion detection
        
        # Distance must indicate something is there
        if avg_dist > 200:
            return "CLEAR"  # Nothing detected
        
        # Classification logic
        if variance < 5:
            return "WALL"  # Near-zero variance = fixed obstruction
        elif variance < 25:
            if has_motion:
                return "SINGLE_PERSON"
            else:
                return "STATIC_OBJECT"
        else:
            if has_motion:
                return "CROWD"
            else:
                return "STATIC_OBJECT"  # High variance but no motion is unusual
    
    def get_all_zones(self):
        """Get summary of all zones"""
        return {
            name: {
                "status": z["status"],
                "density": z["density"],
                "risk": z["risk"],
                "detection_type": z["detection_type"]
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