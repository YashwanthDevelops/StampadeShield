"""
CLUSTER DETECTOR
Detects crowd clusters and their severity
"""

from datetime import datetime
from collections import deque


class ClusterDetector:
    def __init__(self):
        self.clusters = []
        self.history = deque(maxlen=120)
    
    def update(self, node_data):
        """
        Detect clusters from all nodes
        
        node_data format:
        {
            "NODE_A": {"dist": 25, "pir": 1},
            "NODE_B": {"dist": 80, "pir": 0},
            "NODE_C": {"dist": 40, "pir": 1}
        }
        """
        self.history.append({
            "time": datetime.now(),
            "data": node_data.copy()
        })
        
        self.clusters = self.detect_clusters(node_data)
        return self.clusters
    
    def detect_clusters(self, node_data):
        """Identify clusters based on sensor data"""
        clusters = []
        
        for node_id, data in node_data.items():
            dist = data.get("dist", 400)
            pir = data.get("pir", 0)
            
            if dist < 60:
                if dist < 15:
                    severity = "CRITICAL"
                    size = "LARGE"
                    people = int((60 - dist) / 5)
                elif dist < 30:
                    severity = "HIGH"
                    size = "MEDIUM"
                    people = int((60 - dist) / 7)
                elif dist < 45:
                    severity = "MODERATE"
                    size = "SMALL"
                    people = int((60 - dist) / 10)
                else:
                    severity = "LOW"
                    size = "FORMING"
                    people = 2
                
                clusters.append({
                    "node": node_id,
                    "zone": self.node_to_zone(node_id),
                    "severity": severity,
                    "size": size,
                    "distance": dist,
                    "people": max(1, people),
                    "moving": pir == 1
                })
        
        return clusters
    
    def node_to_zone(self, node_id):
        """Convert node ID to zone name"""
        mapping = {
            "NODE_A": "ENTRY",
            "NODE_B": "EXIT",
            "NODE_C": "CENTER"
        }
        return mapping.get(node_id, "UNKNOWN")
    
    def get_cluster_count(self):
        """Get number of active clusters"""
        return len(self.clusters)
    
    def get_worst_cluster(self):
        """Get most severe cluster"""
        if not self.clusters:
            return None
        
        order = {"CRITICAL": 4, "HIGH": 3, "MODERATE": 2, "LOW": 1}
        return max(self.clusters, key=lambda c: order.get(c["severity"], 0))
    
    def get_total_people(self):
        """Estimate total people in clusters"""
        return sum(c["people"] for c in self.clusters)
    
    def get_cluster_risk(self):
        """Calculate overall cluster risk (0-100)"""
        if not self.clusters:
            return 0
        
        risk = 0
        for c in self.clusters:
            if c["severity"] == "CRITICAL":
                risk += 40
            elif c["severity"] == "HIGH":
                risk += 25
            elif c["severity"] == "MODERATE":
                risk += 15
            else:
                risk += 5
        
        return min(100, risk)