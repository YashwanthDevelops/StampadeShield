"""
╔═══════════════════════════════════════════════════════════╗
║              SURGE SHIELD - LIVE DASHBOARD                ║
║                  Day 4 Complete Version                   ║
║            With New Design System & All Features          ║
╚═══════════════════════════════════════════════════════════╝
"""

import sys
import os
import time
import random
from collections import deque
from datetime import datetime, timedelta

from dash import Dash, html, dcc
from dash.dependencies import Input, Output, State
import dash_bootstrap_components as dbc
import plotly.graph_objects as go

# Add parent path for imports
current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(current_dir)
sys.path.insert(0, parent_dir)

# Import UDP Receiver
try:
    from udp_receiver import UDPReceiver
    HAS_UDP = True
    print("✅ UDP Receiver module loaded")
except ImportError:
    HAS_UDP = False
    print("⚠️  UDP Receiver not found - Live mode disabled")

# Import Engine
try:
    from engine.surge_engine import SurgeEngine
    from engine.alert_manager import AlertManager, AlertLevel
    HAS_ENGINE = True
    print("✅ Engine modules loaded")
except ImportError:
    HAS_ENGINE = False
    print("⚠️  Engine not found - Using standalone mode")


# ═══════════════════════════════════════════════════════════
#                    DESIGN SYSTEM COLORS
# ═══════════════════════════════════════════════════════════

# Based on your CSS design tokens (dark mode)
COLORS = {
    # Base
    "background": "#1a1a1f",
    "foreground": "#c9c5be",
    "card": "#1f1f24",
    "card_foreground": "#f7f5f2",
    "border": "#2e2c28",
    
    # Primary
    "primary": "#c4753a",
    "primary_foreground": "#ffffff",
    
    # Muted
    "muted": "#151517",
    "muted_foreground": "#8a8680",
    
    # Accent
    "accent": "#141210",
    "accent_foreground": "#f3f1ed",
    
    # Charts
    "chart_1": "#c4753a",  # Orange/Rust
    "chart_2": "#9b6dd6",  # Purple
    "chart_3": "#22c55e",  # Green
    "chart_4": "#3b82f6",  # Blue
    "chart_5": "#f97316",  # Bright Orange
    
    # Destructive
    "destructive": "#dc2626",
    
    # Input
    "input": "#3a3835",
    "ring": "#c4753a",
}

# State colors
STATE_COLORS = {
    "CLEAR": "#22c55e",      # Green
    "NORMAL": "#3b82f6",     # Blue
    "ELEVATED": "#eab308",   # Yellow
    "CRITICAL": "#f97316",   # Orange
    "SURGE": "#ef4444",      # Red
    "OFFLINE": "#6b7280"     # Gray
}

# Zone colors
ZONE_COLORS = {
    "A": "#c4753a",  # Rust orange
    "B": "#9b6dd6",  # Purple
    "C": "#3b82f6"   # Blue
}

ZONE_LABELS = {
    "A": "ENTRY",
    "B": "CORRIDOR", 
    "C": "EXIT"
}

# Room configuration (meters)
ROOM_WIDTH = 10
ROOM_HEIGHT = 10
NODE_POSITIONS = {
    "A": (1, 9),     # Top-left (Entry)
    "B": (9, 9),     # Top-right (Corridor)
    "C": (5, 1)      # Bottom-center (Exit/Door)
}


# ═══════════════════════════════════════════════════════════
#                    SIMULATION ENGINE
# ═══════════════════════════════════════════════════════════

SCENARIOS = {
    "NORMAL": {
        "dist_range": (150, 300),
        "wifi_range": (3, 8),
        "pir_prob": 0.15,
        "sound_range": (30, 50),
    },
    "BUSY": {
        "dist_range": (80, 150),
        "wifi_range": (12, 20),
        "pir_prob": 0.5,
        "sound_range": (55, 70),
    },
    "SURGE": {
        "dist_range": (20, 60),
        "wifi_range": (25, 40),
        "pir_prob": 0.95,
        "sound_range": (75, 95),
    }
}


def generate_sim_data(scenario: str) -> dict:
    """Generate simulated sensor data."""
    params = SCENARIOS.get(scenario, SCENARIOS["NORMAL"])
    
    data = {}
    for node_id in ["A", "B", "C"]:
        dist_min, dist_max = params["dist_range"]
        wifi_min, wifi_max = params["wifi_range"]
        sound_min, sound_max = params["sound_range"]
        
        base_dist = random.randint(dist_min, dist_max)
        # Add node-specific variation
        if node_id == "C":
            base_dist = int(base_dist * 0.9)  # Door is usually busier
        
        data[node_id] = {
            "id": node_id,
            "zone": ZONE_LABELS[node_id],
            "dist": base_dist,
            "pir": 1 if random.random() < params["pir_prob"] else 0,
            "wifi": random.randint(wifi_min, wifi_max),
            "sound": random.randint(sound_min, sound_max) if node_id == "C" else 0,
            "online": True
        }
    
    return data


def calculate_state(sensor_data: dict) -> dict:
    """Calculate system state from sensor data."""
    if not sensor_data:
        return {
            "risk_score": 0,
            "state": "CLEAR",
            "zone_states": {"A": "CLEAR", "B": "CLEAR", "C": "CLEAR"},
            "device_count": 0,
            "passage_rate": 0
        }
    
    # Aggregate metrics
    distances = [d.get("dist", 300) for d in sensor_data.values()]
    avg_dist = sum(distances) / len(distances)
    min_dist = min(distances)
    
    total_wifi = sum(d.get("wifi", 0) for d in sensor_data.values())
    max_sound = max(d.get("sound", 0) for d in sensor_data.values())
    pir_active = sum(1 for d in sensor_data.values() if d.get("pir", 0))
    
    # Calculate risk components
    dist_risk = max(0, min(1, (300 - avg_dist) / 280))
    crowding_risk = max(0, min(1, (200 - min_dist) / 180)) if min_dist < 200 else 0
    sound_risk = max(0, min(1, (max_sound - 50) / 45)) if max_sound > 50 else 0
    motion_risk = pir_active / 3
    
    # Weighted combination
    risk_score = (
        0.35 * dist_risk +
        0.30 * crowding_risk +
        0.20 * sound_risk +
        0.15 * motion_risk
    )
    risk_score = max(0, min(1, risk_score))
    
    # Determine state
    if risk_score >= 0.75:
        state = "SURGE"
    elif risk_score >= 0.55:
        state = "CRITICAL"
    elif risk_score >= 0.35:
        state = "ELEVATED"
    elif risk_score >= 0.15:
        state = "NORMAL"
    else:
        state = "CLEAR"
    
    # Zone states
    zone_states = {}
    for zone_id, readings in sensor_data.items():
        dist = readings.get("dist", 300)
        if not readings.get("online", True):
            zone_states[zone_id] = "OFFLINE"
        elif dist < 50:
            zone_states[zone_id] = "SURGE"
        elif dist < 100:
            zone_states[zone_id] = "CRITICAL"
        elif dist < 150:
            zone_states[zone_id] = "ELEVATED"
        elif dist < 200:
            zone_states[zone_id] = "NORMAL"
        else:
            zone_states[zone_id] = "CLEAR"
    
    return {
        "risk_score": risk_score,
        "state": state,
        "zone_states": zone_states,
        "device_count": total_wifi,
        "passage_rate": max(0, int((300 - avg_dist) / 8))
    }


def generate_device_positions(sensor_data: dict) -> list:
    """Generate device positions for heatmap visualization."""
    devices = []
    
    for node_id, readings in sensor_data.items():
        if not readings.get("online", True):
            continue
            
        node_x, node_y = NODE_POSITIONS[node_id]
        dist = readings.get("dist", 300)
        wifi_count = readings.get("wifi", 0)
        
        # More devices when closer
        crowd_factor = max(0, (300 - dist) / 300)
        num_devices = int(wifi_count * crowd_factor * 0.5) + 1
        
        for _ in range(min(num_devices, 12)):
            spread = (dist / 150) + 0.3
            x = node_x + random.gauss(0, spread)
            y = node_y + random.gauss(0, spread)
            
            # Clamp to room
            x = max(0, min(ROOM_WIDTH, x))
            y = max(0, min(ROOM_HEIGHT, y))
            
            density = 1 - (dist / 300)
            devices.append({
                "x": round(x, 2),
                "y": round(y, 2),
                "zone": node_id,
                "density": round(density, 2)
            })
    
    return devices


# ═══════════════════════════════════════════════════════════
#                    DASHBOARD STATE
# ═══════════════════════════════════════════════════════════

class DashboardState:
    """Manages all dashboard state and data."""
    
    def __init__(self):
        # UDP Receiver
        self.udp_receiver = None
        if HAS_UDP:
            try:
                self.udp_receiver = UDPReceiver(port=5005)
                self.udp_receiver.start()
                print("✅ UDP Receiver started on port 5005")
            except Exception as e:
                print(f"❌ UDP start failed: {e}")
        
        # Surge Engine
        self.surge_engine = None
        if HAS_ENGINE:
            try:
                self.surge_engine = SurgeEngine()
                print("✅ Surge Engine initialized")
            except Exception as e:
                print(f"❌ Engine init failed: {e}")
        
        # History for graphs
        self.flow_history = {z: deque(maxlen=120) for z in ["A", "B", "C"]}
        self.risk_history = deque(maxlen=120)
        self.flow_time = deque(maxlen=120)
        
        # Pre-populate
        now = datetime.now()
        for i in range(120):
            t = now - timedelta(seconds=(119 - i))
            self.flow_time.append(t)
            self.risk_history.append(0)
            for z in ["A", "B", "C"]:
                self.flow_history[z].append(0)
        
        # Alerts
        self.alerts = deque(maxlen=50)
        self.last_alert_time = {}
        
        # Surge tracking
        self._surge_start = None
        self.surge_periods = []
    
    def get_data(self, mode: str, scenario: str):
        """Get current sensor data and calculated state."""
        
        # Get raw data
        if mode == 'SIM':
            raw_data = generate_sim_data(scenario)
        else:
            if self.udp_receiver:
                raw_data = self.udp_receiver.get_all_latest()
                for node in ["A", "B", "C"]:
                    if node not in raw_data:
                        raw_data[node] = {
                            "id": node,
                            "zone": ZONE_LABELS[node],
                            "dist": 400,
                            "pir": 0,
                            "wifi": 0,
                            "sound": 0,
                            "online": False
                        }
                    else:
                        raw_data[node]["online"] = True
            else:
                raw_data = generate_sim_data("NORMAL")
        
        # Calculate state
        if self.surge_engine and mode != 'SIM':
            state_data = self.surge_engine.process_sensor_data(raw_data)
        else:
            state_data = calculate_state(raw_data)
        
        # Generate positions
        devices = generate_device_positions(raw_data)
        
        # Update history
        now = datetime.now()
        self.flow_time.append(now)
        self.risk_history.append(state_data["risk_score"])
        
        for z in ["A", "B", "C"]:
            if z in raw_data:
                dist = raw_data[z].get("dist", 300)
                flow = max(0, int((300 - dist) / 6))
            else:
                flow = 0
            self.flow_history[z].append(flow)
        
        # Track surge
        if state_data["state"] == "SURGE":
            if self._surge_start is None:
                self._surge_start = now
        else:
            if self._surge_start:
                self.surge_periods.append((self._surge_start, now))
                self._surge_start = None
        
        # Alerts
        self._process_alerts(state_data)
        
        return raw_data, state_data, devices
    
    def _process_alerts(self, state_data: dict):
        """Generate alerts for concerning states."""
        state = state_data.get("state", "CLEAR")
        current_time = time.time()
        
        if state in ["ELEVATED", "CRITICAL", "SURGE"]:
            last = self.last_alert_time.get(state, 0)
            if current_time - last > 15:  # 15 second cooldown
                level = "CRITICAL" if state == "SURGE" else "WARNING"
                risk_pct = state_data.get("risk_score", 0) * 100
                msg = f"{state} - Risk at {risk_pct:.0f}%"
                
                self.alerts.append({
                    "level": level,
                    "message": msg,
                    "timestamp": current_time,
                    "state": state
                })
                self.last_alert_time[state] = current_time


# Initialize global state
dashboard_state = DashboardState()


# ═══════════════════════════════════════════════════════════
#                      DASH APP
# ═══════════════════════════════════════════════════════════

app = Dash(
    __name__,
    external_stylesheets=[dbc.themes.BOOTSTRAP],
    suppress_callback_exceptions=True,
    assets_folder='assets'
)
app.title = "SURGE SHIELD"


# ═══════════════════════════════════════════════════════════
#                    LAYOUT COMPONENTS
# ═══════════════════════════════════════════════════════════

def create_zone_card(zone_id: str):
    """Create a zone monitoring card."""
    return html.Div(
        id=f"card-{zone_id}",
        className="zone-card",
        style={
            "background": COLORS["card"],
            "border": f"1px solid {COLORS['border']}",
            "borderRadius": "8px",
            "padding": "1.25rem",
            "flex": "1",
            "minWidth": "200px",
            "borderLeft": f"3px solid {ZONE_COLORS[zone_id]}"
        },
        children=[
            # Header
            html.Div(style={
                "display": "flex",
                "justifyContent": "space-between",
                "alignItems": "center",
                "marginBottom": "0.75rem"
            }, children=[
                html.Div(style={"display": "flex", "alignItems": "center", "gap": "0.5rem"}, children=[
                    html.Div(style={
                        "width": "10px",
                        "height": "10px",
                        "borderRadius": "50%",
                        "background": ZONE_COLORS[zone_id]
                    }),
                    html.Span(f"ZONE {zone_id}", style={
                        "color": COLORS["foreground"],
                        "fontWeight": "600",
                        "fontSize": "0.9rem"
                    })
                ]),
                html.Span(ZONE_LABELS[zone_id], style={
                    "color": COLORS["muted_foreground"],
                    "fontSize": "0.75rem",
                    "textTransform": "uppercase",
                    "letterSpacing": "0.05em"
                })
            ]),
            
            # Status
            html.Div(id=f"status-{zone_id}", style={
                "fontSize": "1.25rem",
                "fontWeight": "700",
                "marginBottom": "0.5rem"
            }),
            
            # Details
            html.Div(id=f"details-{zone_id}", style={
                "color": COLORS["muted_foreground"],
                "fontSize": "0.8rem",
                "fontFamily": "ui-monospace, monospace"
            })
        ]
    )


def create_metric_card(metric_id: str, label: str, icon: str):
    """Create a metric display card."""
    return html.Div(style={
        "background": COLORS["card"],
        "border": f"1px solid {COLORS['border']}",
        "borderRadius": "8px",
        "padding": "1.25rem",
        "textAlign": "center",
        "minWidth": "130px"
    }, children=[
        html.Div(icon, style={"fontSize": "1.25rem", "marginBottom": "0.25rem"}),
        html.Div(label, style={
            "color": COLORS["muted_foreground"],
            "fontSize": "0.7rem",
            "textTransform": "uppercase",
            "letterSpacing": "0.05em",
            "marginBottom": "0.25rem"
        }),
        html.Div(id=metric_id, style={
            "fontSize": "1.75rem",
            "fontWeight": "700",
            "color": COLORS["foreground"]
        })
    ])


# ═══════════════════════════════════════════════════════════
#                       MAIN LAYOUT
# ═══════════════════════════════════════════════════════════

app.layout = html.Div(style={
    "background": COLORS["background"],
    "minHeight": "100vh",
    "padding": "1.5rem",
    "fontFamily": "ui-sans-serif, system-ui, -apple-system, sans-serif"
}, children=[
    
    # Intervals and stores
    dcc.Interval(id='interval', interval=500, n_intervals=0),
    dcc.Store(id='store', data={'mode': 'SIM', 'scenario': 'NORMAL'}),
    
    # ─────────────────── HEADER ───────────────────
    html.Div(style={
        "display": "flex",
        "justifyContent": "space-between",
        "alignItems": "center",
        "marginBottom": "1.5rem",
        "paddingBottom": "1rem",
        "borderBottom": f"1px solid {COLORS['border']}"
    }, children=[
        # Logo
        html.Div(style={"display": "flex", "alignItems": "center", "gap": "0.75rem"}, children=[
            html.Span("🛡️", style={"fontSize": "1.75rem"}),
            html.H1("SURGE SHIELD", style={
                "color": COLORS["foreground"],
                "margin": 0,
                "fontSize": "1.5rem",
                "fontWeight": "700"
            }),
            html.Span(id="mode-indicator", style={
                "padding": "0.25rem 0.75rem",
                "borderRadius": "9999px",
                "fontSize": "0.7rem",
                "fontWeight": "600"
            })
        ]),
        
        # Controls
        html.Div(style={"display": "flex", "gap": "1rem", "alignItems": "center"}, children=[
            dcc.Dropdown(
                id='scenario',
                options=[
                    {"label": "🟢 NORMAL", "value": "NORMAL"},
                    {"label": "🟡 BUSY", "value": "BUSY"},
                    {"label": "🔴 SURGE", "value": "SURGE"}
                ],
                value="NORMAL",
                clearable=False,
                style={"width": "140px", "fontSize": "0.85rem"}
            ),
            html.Div(style={"display": "flex", "alignItems": "center", "gap": "0.5rem"}, children=[
                dbc.Switch(id='mode-switch', value=True),
                html.Span(id="mode-label", style={
                    "color": COLORS["primary"],
                    "fontWeight": "600",
                    "fontSize": "0.85rem"
                })
            ])
        ])
    ]),
    
    # ─────────────────── ZONE CARDS ───────────────────
    html.Div(style={
        "display": "grid",
        "gridTemplateColumns": "repeat(3, 1fr)",
        "gap": "1rem",
        "marginBottom": "1.5rem"
    }, children=[
        create_zone_card("A"),
        create_zone_card("B"),
        create_zone_card("C")
    ]),
    
    # ─────────────────── METRICS ROW ───────────────────
    html.Div(style={
        "display": "flex",
        "justifyContent": "center",
        "gap": "1rem",
        "marginBottom": "1.5rem",
        "flexWrap": "wrap"
    }, children=[
        create_metric_card("risk-value", "Risk Score", "📊"),
        create_metric_card("state-value", "System State", "🎯"),
        create_metric_card("device-value", "Devices", "📱"),
        create_metric_card("flow-value", "Flow Rate", "🚶")
    ]),
    
    # ─────────────────── MAIN PANELS ───────────────────
    html.Div(style={
        "display": "grid",
        "gridTemplateColumns": "1fr 1fr",
        "gap": "1rem",
        "marginBottom": "1rem"
    }, children=[
        
        # HEATMAP PANEL
        html.Div(style={
            "background": COLORS["card"],
            "border": f"1px solid {COLORS['border']}",
            "borderRadius": "8px",
            "padding": "1rem"
        }, children=[
            html.Div(style={
                "display": "flex",
                "alignItems": "center",
                "gap": "0.5rem",
                "marginBottom": "0.75rem"
            }, children=[
                html.Span("🗺️", style={"fontSize": "1rem"}),
                html.Span("Zone Heatmap", style={
                    "color": COLORS["foreground"],
                    "fontWeight": "600",
                    "fontSize": "0.875rem"
                })
            ]),
            dcc.Graph(id="heatmap", style={"height": "320px"}, config={"displayModeBar": False})
        ]),
        
        # FLOW GRAPH PANEL
        html.Div(style={
            "background": COLORS["card"],
            "border": f"1px solid {COLORS['border']}",
            "borderRadius": "8px",
            "padding": "1rem"
        }, children=[
            html.Div(style={
                "display": "flex",
                "alignItems": "center",
                "gap": "0.5rem",
                "marginBottom": "0.75rem"
            }, children=[
                html.Span("📈", style={"fontSize": "1rem"}),
                html.Span("Flow Rate", style={
                    "color": COLORS["foreground"],
                    "fontWeight": "600",
                    "fontSize": "0.875rem"
                })
            ]),
            dcc.Graph(id="flow-graph", style={"height": "320px"}, config={"displayModeBar": False})
        ])
    ]),
    
    # ─────────────────── ALERTS PANEL ───────────────────
    html.Div(style={
        "background": COLORS["card"],
        "border": f"1px solid {COLORS['border']}",
        "borderRadius": "8px",
        "padding": "1rem"
    }, children=[
        html.Div(style={
            "display": "flex",
            "alignItems": "center",
            "gap": "0.5rem",
            "marginBottom": "0.75rem"
        }, children=[
            html.Span("🚨", style={"fontSize": "1rem"}),
            html.Span("Alert Log", style={
                "color": COLORS["foreground"],
                "fontWeight": "600",
                "fontSize": "0.875rem"
            })
        ]),
        html.Div(id="alerts-panel", style={
            "maxHeight": "180px",
            "overflowY": "auto"
        })
    ])
])


# ═══════════════════════════════════════════════════════════
#                      CALLBACKS
# ═══════════════════════════════════════════════════════════

@app.callback(
    [Output('store', 'data'),
     Output('mode-indicator', 'children'),
     Output('mode-indicator', 'style'),
     Output('mode-label', 'children')],
    [Input('mode-switch', 'value'),
     Input('scenario', 'value')]
)
def update_mode(is_sim, scenario):
    mode = 'SIM' if is_sim else 'LIVE'
    
    base_style = {
        "padding": "0.25rem 0.75rem",
        "borderRadius": "9999px",
        "fontSize": "0.7rem",
        "fontWeight": "600"
    }
    
    if mode == 'SIM':
        return (
            {'mode': mode, 'scenario': scenario},
            "SIMULATION",
            {**base_style, "background": COLORS["primary"], "color": "#fff"},
            "SIM"
        )
    else:
        return (
            {'mode': mode, 'scenario': scenario},
            "LIVE",
            {**base_style, "background": STATE_COLORS["CLEAR"], "color": "#000"},
            "LIVE"
        )


@app.callback(
    [
        # Zone outputs (status, style, details) × 3
        Output("status-A", "children"), Output("status-A", "style"), Output("details-A", "children"),
        Output("status-B", "children"), Output("status-B", "style"), Output("details-B", "children"),
        Output("status-C", "children"), Output("status-C", "style"), Output("details-C", "children"),
        # Metrics
        Output("risk-value", "children"), Output("risk-value", "style"),
        Output("state-value", "children"), Output("state-value", "style"),
        Output("device-value", "children"),
        Output("flow-value", "children"),
        # Graphs
        Output("heatmap", "figure"),
        Output("flow-graph", "figure"),
        # Alerts
        Output("alerts-panel", "children")
    ],
    [Input('interval', 'n_intervals')],
    [State('store', 'data')]
)
def update_dashboard(n, store):
    """Main dashboard update - runs every 500ms."""
    
    mode = store.get('mode', 'SIM')
    scenario = store.get('scenario', 'NORMAL')
    
    # Get data
    raw_data, state_data, devices = dashboard_state.get_data(mode, scenario)
    
    outputs = []
    
    # ─────────────────── ZONE CARDS ───────────────────
    for zone in ["A", "B", "C"]:
        zone_state = state_data.get("zone_states", {}).get(zone, "CLEAR")
        color = STATE_COLORS.get(zone_state, "#888")
        readings = raw_data.get(zone, {})
        
        online = readings.get("online", True)
        
        if not online:
            outputs.append("OFFLINE")
            outputs.append({"color": STATE_COLORS["OFFLINE"], "fontSize": "1.25rem", "fontWeight": "700"})
            outputs.append("No data")
        else:
            outputs.append(zone_state)
            outputs.append({"color": color, "fontSize": "1.25rem", "fontWeight": "700"})
            
            dist = readings.get("dist", "?")
            pir = "🟢" if readings.get("pir") else "⚫"
            wifi = readings.get("wifi", "?")
            
            if zone == "C":
                sound = readings.get("sound", 0)
                outputs.append(f"📏 {dist}cm  {pir}  📶 {wifi}  🔊 {sound}dB")
            else:
                outputs.append(f"📏 {dist}cm  {pir}  📶 {wifi}")
    
    # ─────────────────── METRICS ───────────────────
    risk_pct = state_data.get("risk_score", 0) * 100
    sys_state = state_data.get("state", "CLEAR")
    state_color = STATE_COLORS.get(sys_state, "#888")
    
    # Risk
    outputs.append(f"{risk_pct:.0f}%")
    risk_color = STATE_COLORS["CLEAR"] if risk_pct < 35 else (STATE_COLORS["ELEVATED"] if risk_pct < 60 else STATE_COLORS["SURGE"])
    outputs.append({"fontSize": "1.75rem", "fontWeight": "700", "color": risk_color})
    
    # State
    outputs.append(sys_state)
    outputs.append({"fontSize": "1.75rem", "fontWeight": "700", "color": state_color})
    
    # Devices
    outputs.append(str(state_data.get("device_count", 0)))
    
    # Flow
    outputs.append(f"{state_data.get('passage_rate', 0)}/min")
    
    # ─────────────────── HEATMAP ───────────────────
    heatmap_fig = go.Figure()
    
    # Room background
    heatmap_fig.add_shape(
        type="rect",
        x0=0, y0=0, x1=ROOM_WIDTH, y1=ROOM_HEIGHT,
        fillcolor=COLORS["muted"],
        line=dict(color=COLORS["border"], width=1)
    )
    
    # Grid
    for i in range(1, ROOM_WIDTH):
        heatmap_fig.add_shape(
            type="line", x0=i, y0=0, x1=i, y1=ROOM_HEIGHT,
            line=dict(color=COLORS["border"], width=0.5, dash="dot")
        )
    for i in range(1, ROOM_HEIGHT):
        heatmap_fig.add_shape(
            type="line", x0=0, y0=i, x1=ROOM_WIDTH, y1=i,
            line=dict(color=COLORS["border"], width=0.5, dash="dot")
        )
    
    # Zone labels
    zone_label_pos = {"A": (1, 8), "B": (9, 8), "C": (5, 2)}
    for zone, (lx, ly) in zone_label_pos.items():
        zone_state = state_data.get("zone_states", {}).get(zone, "CLEAR")
        heatmap_fig.add_annotation(
            x=lx, y=ly,
            text=f"<b>{zone}</b><br>{ZONE_LABELS[zone]}",
            font=dict(color=ZONE_COLORS[zone], size=10),
            showarrow=False
        )
    
    # Node markers
    for node_id, (nx, ny) in NODE_POSITIONS.items():
        zone_state = state_data.get("zone_states", {}).get(node_id, "CLEAR")
        color = STATE_COLORS.get(zone_state, "#888")
        
        heatmap_fig.add_trace(go.Scatter(
            x=[nx], y=[ny],
            mode="markers",
            marker=dict(
                size=18,
                color=color,
                symbol="diamond",
                line=dict(width=2, color=COLORS["foreground"])
            ),
            name=f"Node {node_id}",
            hoverinfo="name"
        ))
    
    # Device dots
    for device in devices:
        density = device.get("density", 0.5)
        if density > 0.6:
            dot_color = "rgba(239, 68, 68, 0.6)"  # Red
        elif density > 0.3:
            dot_color = "rgba(234, 179, 8, 0.6)"  # Yellow
        else:
            dot_color = "rgba(34, 197, 94, 0.6)"  # Green
        
        heatmap_fig.add_trace(go.Scatter(
            x=[device["x"]],
            y=[device["y"]],
            mode="markers",
            marker=dict(size=7, color=dot_color),
            showlegend=False,
            hoverinfo="skip"
        ))
    
    heatmap_fig.update_layout(
        paper_bgcolor=COLORS["card"],
        plot_bgcolor=COLORS["card"],
        margin=dict(l=10, r=10, t=10, b=10),
        xaxis=dict(range=[-0.5, ROOM_WIDTH + 0.5], showgrid=False, zeroline=False, showticklabels=False),
        yaxis=dict(range=[-0.5, ROOM_HEIGHT + 0.5], showgrid=False, zeroline=False, showticklabels=False, scaleanchor="x"),
        showlegend=False
    )
    
    outputs.append(heatmap_fig)
    
    # ─────────────────── FLOW GRAPH ───────────────────
    flow_fig = go.Figure()
    
    now = datetime.now()
    time_list = list(dashboard_state.flow_time)
    
    for zone in ["A", "B", "C"]:
        flow_fig.add_trace(go.Scatter(
            x=time_list,
            y=list(dashboard_state.flow_history[zone]),
            name=f"Zone {zone}",
            line=dict(color=ZONE_COLORS[zone], width=2),
            fill='tozeroy',
            fillcolor=f"rgba({int(ZONE_COLORS[zone][1:3], 16)}, {int(ZONE_COLORS[zone][3:5], 16)}, {int(ZONE_COLORS[zone][5:7], 16)}, 0.1)"
        ))
    
    # Surge periods
    for start, end in dashboard_state.surge_periods[-3:]:
        flow_fig.add_vrect(
            x0=start, x1=end,
            fillcolor="rgba(239, 68, 68, 0.15)",
            layer="below",
            line_width=0
        )
    
    flow_fig.update_layout(
        paper_bgcolor=COLORS["card"],
        plot_bgcolor=COLORS["card"],
        margin=dict(l=35, r=10, t=10, b=35),
        xaxis=dict(
            range=[now - timedelta(seconds=120), now],
            showgrid=False,
            tickfont=dict(color=COLORS["muted_foreground"], size=10),
            tickformat="%H:%M:%S"
        ),
        yaxis=dict(
            range=[0, 50],
            showgrid=True,
            gridcolor=COLORS["border"],
            tickfont=dict(color=COLORS["muted_foreground"], size=10)
        ),
        legend=dict(
            orientation="h",
            yanchor="bottom",
            y=1.02,
            xanchor="center",
            x=0.5,
            font=dict(color=COLORS["muted_foreground"], size=10)
        ),
        hovermode="x unified"
    )
    
    outputs.append(flow_fig)
    
    # ─────────────────── ALERTS ───────────────────
    alert_items = []
    for alert in reversed(list(dashboard_state.alerts)[-8:]):
        level = alert.get("level", "INFO")
        level_color = STATE_COLORS["SURGE"] if level == "CRITICAL" else STATE_COLORS["ELEVATED"]
        
        alert_items.append(
            html.Div(style={
                "display": "flex",
                "alignItems": "center",
                "padding": "0.6rem",
                "borderLeft": f"3px solid {level_color}",
                "background": COLORS["accent"],
                "marginBottom": "0.4rem",
                "borderRadius": "0 4px 4px 0"
            }, children=[
                html.Span(
                    datetime.fromtimestamp(alert["timestamp"]).strftime("%H:%M:%S"),
                    style={
                        "color": COLORS["muted_foreground"],
                        "marginRight": "0.75rem",
                        "fontSize": "0.75rem",
                        "fontFamily": "ui-monospace, monospace"
                    }
                ),
                html.Span(
                    f"[{level}]",
                    style={
                        "color": level_color,
                        "fontWeight": "600",
                        "marginRight": "0.5rem",
                        "fontSize": "0.75rem"
                    }
                ),
                html.Span(alert["message"], style={
                    "color": COLORS["foreground"],
                    "fontSize": "0.8rem"
                })
            ])
        )
    
    if not alert_items:
        alert_items = [
            html.Div("No alerts", style={
                "color": COLORS["muted_foreground"],
                "textAlign": "center",
                "padding": "2rem",
                "fontStyle": "italic"
            })
        ]
    
    outputs.append(alert_items)
    
    return outputs


# ═══════════════════════════════════════════════════════════
#                        RUN
# ═══════════════════════════════════════════════════════════

if __name__ == "__main__":
    print()
    print("╔═══════════════════════════════════════════════════════════╗")
    print("║              🛡️  SURGE SHIELD DASHBOARD                   ║")
    print("╠═══════════════════════════════════════════════════════════╣")
    print(f"║  UDP Receiver: {'✅ Active' if HAS_UDP else '❌ Disabled':^40} ║")
    print(f"║  Surge Engine: {'✅ Active' if HAS_ENGINE else '⚠️  Standalone':^40} ║")
    print("╠═══════════════════════════════════════════════════════════╣")
    print("║  Starting on http://localhost:8050                        ║")
    print("╚═══════════════════════════════════════════════════════════╝")
    print()
    
    app.run(debug=True, host="0.0.0.0", port=8050)