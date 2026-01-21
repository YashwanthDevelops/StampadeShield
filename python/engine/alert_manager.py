#!/usr/bin/env python3
"""
AlertManager - State-based alert system for StampedeShield.

Triggers alerts based on SurgeState transitions with cooldown logic.
"""

import time
from collections import deque
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any
from enum import Enum


class AlertLevel(Enum):
    INFO = "INFO"
    WARNING = "WARNING"
    CRITICAL = "CRITICAL"


@dataclass
class Alert:
    """Alert output structure."""
    timestamp: float
    level: str
    state: str
    message: str
    zone: str = ""
    telegram_flag: bool = False

    def to_dict(self) -> Dict[str, Any]:
        return {
            "timestamp": self.timestamp,
            "level": self.level,
            "state": self.state,
            "message": self.message,
            "zone": self.zone,
            "telegram_flag": self.telegram_flag
        }


class AlertManager:
    """
    Manages alerts based on SurgeState transitions.
    
    Args:
        cooldown_seconds: Minimum time between same-level alerts (default: 30).
    """
    
    # State severity ordering
    STATE_SEVERITY = {
        "CLEAR": 0,
        "NORMAL": 1,
        "ELEVATED": 2,
        "CRITICAL": 3,
        "SURGE": 4
    }

    def __init__(self, cooldown_seconds: float = 30.0):
        self.cooldown_seconds = cooldown_seconds
        self.last_state = "CLEAR"
        self.last_alert_time: Dict[str, float] = {}  # level -> timestamp
        self.alert_history: deque = deque(maxlen=100)

    def process(self, surge_state) -> Optional[Alert]:
        """
        Process a SurgeState and potentially generate an alert.
        
        Args:
            surge_state: SurgeState object from SurgeEngine.
            
        Returns:
            Alert object if triggered, None otherwise.
        """
        current_time = time.time()
        current_state = surge_state.state
        
        # Determine if state changed
        if current_state == self.last_state:
            return None  # No change, no alert
        
        old_severity = self.STATE_SEVERITY.get(self.last_state, 0)
        new_severity = self.STATE_SEVERITY.get(current_state, 0)
        
        alert = None
        
        if new_severity > old_severity:
            # State escalation
            alert = self._create_escalation_alert(current_state, surge_state, current_time)
        else:
            # State downgrade
            alert = self._create_downgrade_alert(current_state, surge_state, current_time)
        
        if alert and self._check_cooldown(alert.level, current_time):
            self.last_state = current_state
            self.last_alert_time[alert.level] = current_time
            self.alert_history.append(alert)
            self._log_alert(alert)
            return alert
        
        # Update state even if alert was suppressed
        self.last_state = current_state
        return None

    def _create_escalation_alert(self, state: str, surge_state, ts: float) -> Alert:
        """Create alert for escalating states."""
        if state == "ELEVATED":
            return Alert(
                timestamp=ts,
                level=AlertLevel.WARNING.value,
                state=state,
                message=f"Crowd density increasing. Risk: {surge_state.risk_score:.1%}",
                zone=self._get_hottest_zone(surge_state.zone_states)
            )
        elif state == "CRITICAL":
            return Alert(
                timestamp=ts,
                level=AlertLevel.CRITICAL.value,
                state=state,
                message=f"HIGH RISK! Crowd surge detected. Risk: {surge_state.risk_score:.1%}",
                zone=self._get_hottest_zone(surge_state.zone_states)
            )
        elif state == "SURGE":
            return Alert(
                timestamp=ts,
                level=AlertLevel.CRITICAL.value,
                state=state,
                message=f"⚠️ SURGE ALERT! Immediate action required. Risk: {surge_state.risk_score:.1%}",
                zone=self._get_hottest_zone(surge_state.zone_states),
                telegram_flag=True  # Special flag for Telegram
            )
        else:
            return Alert(
                timestamp=ts,
                level=AlertLevel.INFO.value,
                state=state,
                message=f"State changed to {state}. Risk: {surge_state.risk_score:.1%}",
                zone=""
            )

    def _create_downgrade_alert(self, state: str, surge_state, ts: float) -> Alert:
        """Create alert for de-escalating states."""
        return Alert(
            timestamp=ts,
            level=AlertLevel.INFO.value,
            state=state,
            message=f"Situation improving. State: {state}, Risk: {surge_state.risk_score:.1%}",
            zone=""
        )

    def _check_cooldown(self, level: str, current_time: float) -> bool:
        """Check if enough time has passed since last alert of this level."""
        last_time = self.last_alert_time.get(level, 0)
        return (current_time - last_time) >= self.cooldown_seconds

    def _get_hottest_zone(self, zone_states: Dict[str, str]) -> str:
        """Find the zone with highest severity."""
        hottest = ""
        max_severity = -1
        severity_map = {"CLEAR": 0, "OCCUPIED": 1, "CROWDED": 2}
        
        for zone, state in zone_states.items():
            sev = severity_map.get(state, 0)
            if sev > max_severity:
                max_severity = sev
                hottest = zone
        return hottest

    def _log_alert(self, alert: Alert):
        """Log alert to console."""
        prefix = {"INFO": "ℹ️", "WARNING": "⚠️", "CRITICAL": "🚨"}.get(alert.level, "")
        print(f"[ALERT] {prefix} [{alert.level}] {alert.message}")
        if alert.zone:
            print(f"        Zone: {alert.zone}")

    def get_recent_alerts(self, n: int = 10) -> List[Dict]:
        """Get the n most recent alerts."""
        alerts = list(self.alert_history)[-n:]
        return [a.to_dict() for a in alerts]

    def reset(self):
        """Reset alert manager state."""
        self.last_state = "CLEAR"
        self.last_alert_time.clear()
        self.alert_history.clear()


if __name__ == "__main__":
    # Quick test
    from dataclasses import dataclass
    
    @dataclass
    class MockState:
        state: str
        risk_score: float
        zone_states: dict
    
    am = AlertManager(cooldown_seconds=1)  # Short cooldown for testing
    
    states = [
        MockState("NORMAL", 0.25, {"A": "OCCUPIED"}),
        MockState("ELEVATED", 0.45, {"A": "CROWDED", "B": "OCCUPIED"}),
        MockState("CRITICAL", 0.75, {"A": "CROWDED", "B": "CROWDED"}),
        MockState("SURGE", 0.92, {"A": "CROWDED", "B": "CROWDED", "C": "CROWDED"}),
        MockState("ELEVATED", 0.55, {"A": "CROWDED"}),
        MockState("NORMAL", 0.30, {"A": "OCCUPIED"}),
    ]
    
    print("=== AlertManager Test ===\n")
    for s in states:
        print(f"\n>>> Processing state: {s.state}")
        time.sleep(0.2)
        alert = am.process(s)
    
    print(f"\nRecent alerts: {len(am.get_recent_alerts())}")
