"""
╔═══════════════════════════════════════════════════════════╗
║                    STAMPEDE SHIELD                        ║
║              Alert Manager - Notification System          ║
╚═══════════════════════════════════════════════════════════╝

Manages alert generation, cooldowns, and notification dispatch.
Supports: Console, Telegram, Node C buzzer commands.

Author: StampedeShield Team
Version: 2.0
"""

import time
import threading
import socket
import json
from typing import Dict, Optional, List, Callable
from collections import deque
from enum import Enum


class AlertLevel(Enum):
    """Alert severity levels."""
    INFO = 0
    WARNING = 1
    CRITICAL = 2
    EMERGENCY = 3


class AlertManager:
    """
    Manages alerts and notifications for the system.
    
    Features:
    - Cooldown between repeated alerts
    - Multiple notification channels
    - Alert history tracking
    - Rate limiting
    """
    
    def __init__(self, config: Optional[Dict] = None):
        """
        Initialize the alert manager.
        
        Args:
            config: Optional configuration:
                - COOLDOWN_SECONDS: Time between same-type alerts (30)
                - MAX_ALERTS_PER_MINUTE: Rate limit (10)
                - NODE_C_IP: IP for sending buzzer commands
                - NODE_C_PORT: Port for Node C commands (5006)
        """
        default_config = {
            "COOLDOWN_SECONDS": 30,
            "MAX_ALERTS_PER_MINUTE": 10,
            "NODE_C_IP": None,  # Will try to find from sensor data
            "NODE_C_PORT": 5006,
            "ENABLE_BUZZER": True,
            "ENABLE_CONSOLE": True,
        }
        
        self.config = {**default_config, **(config or {})}
        
        # Alert history
        self.alert_history: deque = deque(maxlen=100)
        
        # Cooldown tracking
        self.last_alert_time: Dict[str, float] = {}
        
        # Rate limiting
        self.alerts_this_minute: deque = deque(maxlen=100)
        
        # Callbacks for custom handlers
        self.handlers: List[Callable] = []
        
        # UDP socket for Node C commands
        self.udp_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        
        # Node C address (discovered from sensor data)
        self.node_c_address: Optional[tuple] = None
        
        # Statistics
        self.total_alerts = 0
        self.suppressed_alerts = 0
    
    def register_handler(self, handler: Callable):
        """
        Register a custom alert handler.
        
        Handler receives: (level, message, data)
        """
        self.handlers.append(handler)
    
    def trigger_alert(self, level: AlertLevel, message: str, 
                      data: Optional[Dict] = None,
                      alert_type: str = "general") -> bool:
        """
        Trigger an alert.
        
        Args:
            level: Alert severity level
            message: Alert message
            data: Optional additional data
            alert_type: Type for cooldown tracking
            
        Returns:
            True if alert was sent, False if suppressed
        """
        timestamp = time.time()
        
        # Check rate limit
        if not self._check_rate_limit(timestamp):
            self.suppressed_alerts += 1
            return False
        
        # Check cooldown
        if not self._check_cooldown(alert_type, timestamp):
            self.suppressed_alerts += 1
            return False
        
        # Create alert record
        alert = {
            "timestamp": timestamp,
            "level": level.name,
            "level_value": level.value,
            "message": message,
            "type": alert_type,
            "data": data or {}
        }
        
        # Store in history
        self.alert_history.append(alert)
        self.total_alerts += 1
        
        # Update cooldown
        self.last_alert_time[alert_type] = timestamp
        
        # Update rate tracking
        self.alerts_this_minute.append(timestamp)
        
        # Dispatch to handlers
        self._dispatch_alert(alert)
        
        return True
    
    def _check_rate_limit(self, timestamp: float) -> bool:
        """Check if we're within rate limit."""
        cutoff = timestamp - 60
        recent = sum(1 for t in self.alerts_this_minute if t >= cutoff)
        return recent < self.config["MAX_ALERTS_PER_MINUTE"]
    
    def _check_cooldown(self, alert_type: str, timestamp: float) -> bool:
        """Check if cooldown has passed for this alert type."""
        last_time = self.last_alert_time.get(alert_type, 0)
        cooldown = self.config["COOLDOWN_SECONDS"]
        return (timestamp - last_time) >= cooldown
    
    def _dispatch_alert(self, alert: Dict):
        """Dispatch alert to all channels."""
        level = AlertLevel[alert["level"]]
        
        # Console output
        if self.config["ENABLE_CONSOLE"]:
            self._console_alert(alert)
        
        # Buzzer for high severity
        if self.config["ENABLE_BUZZER"] and level.value >= AlertLevel.CRITICAL.value:
            self._trigger_buzzer(alert)
        
        # Custom handlers
        for handler in self.handlers:
            try:
                handler(level, alert["message"], alert["data"])
            except Exception as e:
                print(f"Alert handler error: {e}")
    
    def _console_alert(self, alert: Dict):
        """Print alert to console."""
        level = alert["level"]
        
        level_symbols = {
            "INFO": "ℹ️ ",
            "WARNING": "⚠️ ",
            "CRITICAL": "🔴",
            "EMERGENCY": "🚨"
        }
        
        symbol = level_symbols.get(level, "•")
        ts = time.strftime("%H:%M:%S", time.localtime(alert["timestamp"]))
        
        print(f"\n{symbol} [{ts}] {level}: {alert['message']}")
        
        if alert["data"]:
            for k, v in alert["data"].items():
                print(f"   {k}: {v}")
    
    def _trigger_buzzer(self, alert: Dict):
        """Send buzzer command to Node C."""
        if not self.node_c_address:
            return
        
        try:
            cmd = {
                "cmd": "BUZZ",
                "level": alert["level"]
            }
            msg = json.dumps(cmd).encode()
            self.udp_socket.sendto(msg, self.node_c_address)
        except Exception as e:
            print(f"Buzzer command failed: {e}")
    
    def set_node_c_address(self, ip: str, port: int = 5006):
        """Set Node C address for buzzer commands."""
        self.node_c_address = (ip, port)
    
    def process_state_change(self, old_state: str, new_state: str, 
                             risk_score: float, zone_states: Dict):
        """
        Process a system state change and generate appropriate alerts.
        
        Args:
            old_state: Previous state name
            new_state: New state name
            risk_score: Current risk score
            zone_states: Dictionary of zone states
        """
        state_levels = {
            "CLEAR": AlertLevel.INFO,
            "NORMAL": AlertLevel.INFO,
            "ELEVATED": AlertLevel.WARNING,
            "CRITICAL": AlertLevel.CRITICAL,
            "SURGE": AlertLevel.EMERGENCY
        }
        
        level = state_levels.get(new_state, AlertLevel.INFO)
        
        # Only alert for concerning states
        if level.value < AlertLevel.WARNING.value:
            return
        
        # Generate message
        if new_state == "SURGE":
            message = "⚠️ SURGE DETECTED! Immediate action required!"
        elif new_state == "CRITICAL":
            message = f"Critical crowd density - Risk at {risk_score*100:.0f}%"
        else:
            message = f"Elevated crowd levels - Risk at {risk_score*100:.0f}%"
        
        self.trigger_alert(
            level=level,
            message=message,
            data={
                "old_state": old_state,
                "new_state": new_state,
                "risk_score": f"{risk_score*100:.1f}%",
                "zones": zone_states
            },
            alert_type=f"state_{new_state}"
        )
    
    def send_state_to_node_c(self, state: str):
        """
        Send state update to Node C for LED control.
        
        Args:
            state: Current system state name
        """
        if not self.node_c_address:
            return
        
        try:
            cmd = {
                "cmd": "SET_STATE",
                "state": state
            }
            msg = json.dumps(cmd).encode()
            self.udp_socket.sendto(msg, self.node_c_address)
        except Exception as e:
            pass  # Silent fail for state updates
    
    def get_recent_alerts(self, count: int = 10) -> List[Dict]:
        """Get most recent alerts."""
        alerts = list(self.alert_history)
        return alerts[-count:]
    
    def get_alerts_by_level(self, level: AlertLevel) -> List[Dict]:
        """Get alerts of a specific level."""
        return [a for a in self.alert_history if a["level"] == level.name]
    
    def get_statistics(self) -> Dict:
        """Get alert statistics."""
        now = time.time()
        
        # Count by level
        level_counts = {}
        for level in AlertLevel:
            level_counts[level.name] = sum(
                1 for a in self.alert_history if a["level"] == level.name
            )
        
        # Recent alerts (last minute)
        recent = sum(1 for a in self.alert_history 
                    if now - a["timestamp"] < 60)
        
        return {
            "total_alerts": self.total_alerts,
            "suppressed_alerts": self.suppressed_alerts,
            "recent_alerts": recent,
            "by_level": level_counts,
            "cooldown_active": {
                k: (now - v) < self.config["COOLDOWN_SECONDS"]
                for k, v in self.last_alert_time.items()
            }
        }
    
    def clear_history(self):
        """Clear alert history."""
        self.alert_history.clear()
        self.last_alert_time.clear()
        self.alerts_this_minute.clear()
    
    def reset(self):
        """Full reset."""
        self.clear_history()
        self.total_alerts = 0
        self.suppressed_alerts = 0


# ═══════════════════════════════════════════════════════════
#                       TEST SUITE
# ═══════════════════════════════════════════════════════════

def main():
    """Run alert manager tests."""
    print("\n")
    print("╔═══════════════════════════════════════════════════════════╗")
    print("║                    STAMPEDE SHIELD                        ║")
    print("║             Alert Manager - Test Suite                    ║")
    print("╚═══════════════════════════════════════════════════════════╝")
    
    # Create manager with short cooldown for testing
    manager = AlertManager({
        "COOLDOWN_SECONDS": 2,
        "MAX_ALERTS_PER_MINUTE": 20,
        "ENABLE_BUZZER": False,  # No actual hardware
        "ENABLE_CONSOLE": True
    })
    
    # ═══════════════════════════════════════════════════════════
    # TEST 1: Basic alerts
    # ═══════════════════════════════════════════════════════════
    print("\n" + "=" * 60)
    print("TEST 1: Basic Alerts")
    print("=" * 60)
    
    manager.trigger_alert(AlertLevel.INFO, "System started", alert_type="system")
    manager.trigger_alert(AlertLevel.WARNING, "Crowd building", {"zone": "A"}, "crowd")
    manager.trigger_alert(AlertLevel.CRITICAL, "High density!", {"risk": 0.7}, "density")
    manager.trigger_alert(AlertLevel.EMERGENCY, "SURGE!", {"risk": 0.9}, "surge")
    
    # ═══════════════════════════════════════════════════════════
    # TEST 2: Cooldown
    # ═══════════════════════════════════════════════════════════
    print("\n" + "=" * 60)
    print("TEST 2: Cooldown (same alert type)")
    print("=" * 60)
    
    result1 = manager.trigger_alert(AlertLevel.WARNING, "First warning", alert_type="test")
    print(f"  First alert sent: {result1}")
    
    result2 = manager.trigger_alert(AlertLevel.WARNING, "Second warning", alert_type="test")
    print(f"  Second alert (should be suppressed): {result2}")
    
    print("  Waiting for cooldown...")
    time.sleep(2.5)
    
    result3 = manager.trigger_alert(AlertLevel.WARNING, "Third warning", alert_type="test")
    print(f"  Third alert (after cooldown): {result3}")
    
    # ═══════════════════════════════════════════════════════════
    # TEST 3: State change processing
    # ═══════════════════════════════════════════════════════════
    print("\n" + "=" * 60)
    print("TEST 3: State Change Processing")
    print("=" * 60)
    
    time.sleep(2.5)  # Wait for cooldown
    
    manager.process_state_change(
        old_state="NORMAL",
        new_state="ELEVATED",
        risk_score=0.4,
        zone_states={"A": "ELEVATED", "B": "NORMAL", "C": "ELEVATED"}
    )
    
    time.sleep(2.5)
    
    manager.process_state_change(
        old_state="ELEVATED",
        new_state="CRITICAL",
        risk_score=0.65,
        zone_states={"A": "CRITICAL", "B": "ELEVATED", "C": "CRITICAL"}
    )
    
    # ═══════════════════════════════════════════════════════════
    # TEST 4: Custom handler
    # ═══════════════════════════════════════════════════════════
    print("\n" + "=" * 60)
    print("TEST 4: Custom Handler")
    print("=" * 60)
    
    custom_alerts = []
    
    def custom_handler(level, message, data):
        custom_alerts.append((level.name, message))
        print(f"  [CUSTOM] Received: {level.name} - {message}")
    
    manager.register_handler(custom_handler)
    
    time.sleep(2.5)
    manager.trigger_alert(AlertLevel.WARNING, "Handler test", alert_type="handler_test")
    
    print(f"  Custom handler received {len(custom_alerts)} alert(s)")
    
    # ═══════════════════════════════════════════════════════════
    # TEST 5: Statistics
    # ═══════════════════════════════════════════════════════════
    print("\n" + "=" * 60)
    print("TEST 5: Statistics")
    print("=" * 60)
    
    stats = manager.get_statistics()
    
    print(f"""
  Total Alerts: {stats['total_alerts']}
  Suppressed: {stats['suppressed_alerts']}
  Recent (1 min): {stats['recent_alerts']}
  
  By Level:
    INFO: {stats['by_level']['INFO']}
    WARNING: {stats['by_level']['WARNING']}
    CRITICAL: {stats['by_level']['CRITICAL']}
    EMERGENCY: {stats['by_level']['EMERGENCY']}
    """)
    
    # ═══════════════════════════════════════════════════════════
    # TEST 6: Recent alerts
    # ═══════════════════════════════════════════════════════════
    print("=" * 60)
    print("TEST 6: Recent Alerts")
    print("=" * 60)
    
    recent = manager.get_recent_alerts(5)
    print(f"\n  Last {len(recent)} alerts:")
    for alert in recent:
        ts = time.strftime("%H:%M:%S", time.localtime(alert["timestamp"]))
        print(f"    [{ts}] {alert['level']}: {alert['message']}")
    
    print("\n✓ All tests complete!\n")


if __name__ == "__main__":
    main()