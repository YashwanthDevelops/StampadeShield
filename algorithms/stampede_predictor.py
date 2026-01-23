"""
STAMPEDE PREDICTOR
Main algorithm that combines all data to predict risk
THIS IS THE CORE OF YOUR PROJECT
"""

from datetime import datetime
from collections import deque


class StampedePredictor:
    def __init__(self, zone_detector, cluster_detector):
        self.zone = zone_detector
        self.cluster = cluster_detector
        
        self.risk_history = deque(maxlen=120)
        self.current_risk = 0
        self.risk_level = "SAFE"
        self.time_to_danger = None
    
    def predict(self, mic_level=0):
        """
        Main prediction function
        Call this after updating zone and cluster detectors
        """
        
        # Get component risks
        zone_risk = self.calculate_zone_risk()
        cluster_risk = self.cluster.get_cluster_risk()
        audio_risk = self.calculate_audio_risk(mic_level)
        trend_risk = self.calculate_trend_risk()
        
        # Weighted combination
        total_risk = (
            zone_risk * 0.35 +
            cluster_risk * 0.30 +
            audio_risk * 0.20 +
            trend_risk * 0.15
        )
        
        # Danger multipliers
        critical_zones = self.zone.get_critical_zones()
        worst_cluster = self.cluster.get_worst_cluster()
        
        if len(critical_zones) >= 2:
            total_risk *= 1.3
        
        if worst_cluster and worst_cluster["severity"] == "CRITICAL":
            total_risk *= 1.2
        
        if mic_level > 700:
            total_risk *= 1.4
        
        # Final risk
        self.current_risk = min(100, int(total_risk))
        self.risk_level = self.get_level(self.current_risk)
        
        # Store history
        self.risk_history.append({
            "time": datetime.now(),
            "risk": self.current_risk
        })
        
        # Predict time to danger
        self.predict_time()
        
        return self.get_result()
    
    def calculate_zone_risk(self):
        """Average risk from all zones"""
        zones = self.zone.get_all_zones()
        total = sum(z["risk"] for z in zones.values())
        return total / 3
    
    def calculate_audio_risk(self, mic_level):
        """Risk from audio level"""
        if mic_level > 800:
            return 100
        elif mic_level > 600:
            return 70
        elif mic_level > 400:
            return 40
        elif mic_level > 200:
            return 20
        else:
            return 0
    
    def calculate_trend_risk(self):
        """Risk from worsening trend"""
        if len(self.risk_history) < 10:
            return 0
        
        recent = [r["risk"] for r in list(self.risk_history)[-5:]]
        older = [r["risk"] for r in list(self.risk_history)[-10:-5]]
        
        recent_avg = sum(recent) / 5
        older_avg = sum(older) / 5
        
        increase = recent_avg - older_avg
        
        if increase > 20:
            return 100
        elif increase > 10:
            return 60
        elif increase > 5:
            return 30
        elif increase > 0:
            return 10
        else:
            return 0
    
    def get_level(self, risk):
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
    
    def predict_time(self):
        """Predict seconds until critical"""
        if len(self.risk_history) < 10:
            self.time_to_danger = None
            return
        
        recent = [r["risk"] for r in list(self.risk_history)[-10:]]
        
        first = sum(recent[:5]) / 5
        second = sum(recent[5:]) / 5
        
        trend = second - first
        
        if trend <= 0:
            self.time_to_danger = None
            return
        
        remaining = 80 - self.current_risk
        if remaining <= 0:
            self.time_to_danger = 0
        else:
            readings = remaining / trend
            self.time_to_danger = max(0, int(readings * 0.5))
    
    def get_factors(self):
        """Get list of risk factors"""
        factors = []
        
        # Zone factors
        zones = self.zone.get_all_zones()
        for name, z in zones.items():
            if z["status"] == "BLACK":
                factors.append(f"🚨 {name} zone CRITICAL")
            elif z["status"] == "RED":
                factors.append(f"🔴 {name} zone HIGH density")
            elif z["status"] == "ORANGE":
                factors.append(f"🟠 {name} zone elevated")
        
        # Cluster factors
        worst = self.cluster.get_worst_cluster()
        if worst:
            factors.append(f"📍 {worst['severity']} cluster at {worst['zone']}")
        
        total_people = self.cluster.get_total_people()
        if total_people > 10:
            factors.append(f"👥 ~{total_people} people in clusters")
        
        # Trend factor
        if len(self.risk_history) >= 10:
            recent = [r["risk"] for r in list(self.risk_history)[-5:]]
            older = [r["risk"] for r in list(self.risk_history)[-10:-5]]
            if sum(recent)/5 > sum(older)/5 + 10:
                factors.append("📈 Risk increasing rapidly")
        
        if not factors:
            factors.append("✅ No major risk factors")
        
        return factors
    
    def get_recommendation(self):
        """Get action recommendation"""
        if self.risk_level == "CRITICAL":
            return "🚨 EVACUATE NOW! Open all exits!"
        elif self.risk_level == "HIGH":
            return "⚠️ Stop entry! Begin evacuation!"
        elif self.risk_level == "MODERATE":
            return "⚡ Reduce entry. Deploy crowd control."
        elif self.risk_level == "LOW":
            return "👀 Monitor closely. Prepare response."
        else:
            return "✅ Normal. Continue monitoring."
    
    def get_result(self):
        """Get complete prediction result"""
        return {
            "risk": self.current_risk,
            "level": self.risk_level,
            "time_to_danger": self.time_to_danger,
            "factors": self.get_factors(),
            "recommendation": self.get_recommendation()
        }