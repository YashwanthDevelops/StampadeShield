import sys
import time
import random
from collections import deque
from datetime import datetime, timedelta
from dash import Dash, html, dcc
from dash.dependencies import Input, Output, State
import dash_bootstrap_components as dbc
import plotly.graph_objects as go

# Add parent path for imports
sys.path.insert(0, '..')

try:
    from engine.surge_engine import SurgeEngine
    from engine.alert_manager import AlertManager
    HAS_ENGINE = True
except ImportError:
    HAS_ENGINE = False
    print("Warning: Engine modules not found. Using standalone mode.")

# Initialize app
app = Dash(
    __name__,
    external_stylesheets=[dbc.themes.BOOTSTRAP],
    suppress_callback_exceptions=True
)

app.title = "StampedeShield Monitor"

# ═══════════════════════════════════════════════════════════
#                  COLOR SCHEME (from provided CSS)
# ═══════════════════════════════════════════════════════════

# Dark mode colors (oklch converted to hex)
COLORS = {
    # Backgrounds
    "background": "#1a1a1a",        # oklch(0.2046 0 0)
    "card": "#2b2b2b",              # oklch(0.2686 0 0)
    "sidebar": "#161616",           # oklch(0.1684 0 0)
    "muted": "#1f1f1f",             # oklch(0.2393 0 0)
    
    # Foregrounds
    "foreground": "#ebebeb",        # oklch(0.9219 0 0)
    "muted_foreground": "#a8a8a8",  # oklch(0.7155 0 0)
    
    # Borders
    "border": "#4a4a4a",            # oklch(0.3715 0 0)
    
    # Primary (warm orange)
    "primary": "#d4915c",           # oklch(0.7686 0.1647 70.0804)
    
    # Accent (brown)
    "accent": "#8b5a2b",            # oklch(0.4732 0.1247 46.2007)
    
    # Destructive (red)
    "destructive": "#dc2626",       # oklch(0.6368 0.2078 25.3313)
    
    # Chart colors
    "chart_1": "#d4a574",           # oklch(0.7686 0.1647 70.0804) - warm orange
    "chart_2": "#c4864a",           # oklch(0.6658 0.1574 58.3183) - darker orange
    "chart_3": "#a66832",           # oklch(0.5553 0.1455 48.9975) - brown-orange
    "chart_4": "#8b5a2b",           # oklch(0.4732 0.1247 46.2007) - brown
    "chart_5": "#704a24",           # oklch(0.4137 0.1054 45.9038) - dark brown
}

# Zone colors using chart palette
ZONE_COLORS = {
    "A": COLORS["chart_1"],  # #d4a574 warm orange
    "B": COLORS["chart_2"],  # #c4864a darker orange
    "C": COLORS["chart_3"],  # #a66832 brown-orange
}

# State colors
STATE_COLORS = {
    "CLEAR": "#22c55e",      # green
    "NORMAL": "#3b82f6",     # blue
    "ELEVATED": "#eab308",   # yellow
    "CRITICAL": "#f97316",   # orange
    "SURGE": "#ef4444"       # red
}

# Zone labels
ZONE_LABELS = {"A": "ENTRY", "B": "CORRIDOR", "C": "EXIT"}


# ═══════════════════════════════════════════════════════════
#                  SIMULATION DATA GENERATOR
# ═══════════════════════════════════════════════════════════

def generate_sim_data(scenario: str) -> dict:
    """Generate fake sensor data based on scenario."""
    data = {}
    for node_id in ["A", "B", "C"]:
        if scenario == "SURGE":
            data[node_id] = {
                "dist": random.randint(20, 60),
                "pir": 1,
                "wifi": random.randint(20, 35),
                "sound": random.randint(70, 90)
            }
        elif scenario == "BUSY":
            data[node_id] = {
                "dist": random.randint(50, 150),
                "pir": random.choice([0, 1]),
                "wifi": random.randint(8, 15),
                "sound": random.randint(50, 70)
            }
        else:  # NORMAL
            data[node_id] = {
                "dist": random.randint(150, 300),
                "pir": random.choice([0, 0, 0, 1]),
                "wifi": random.randint(2, 5),
                "sound": random.randint(20, 40)
            }
    return data


def calculate_state_from_data(sensor_data: dict) -> dict:
    """Calculate surge state from sensor data (standalone mode)."""
    total_wifi = sum(d.get("wifi", 0) for d in sensor_data.values())
    avg_dist = sum(d.get("dist", 300) for d in sensor_data.values()) / 3
    
    dist_score = max(0, min(1, (300 - avg_dist) / 250))
    wifi_score = max(0, min(1, total_wifi / 60))
    risk_score = 0.6 * dist_score + 0.4 * wifi_score
    
    if risk_score >= 0.8:
        state = "SURGE"
    elif risk_score >= 0.6:
        state = "CRITICAL"
    elif risk_score >= 0.4:
        state = "ELEVATED"
    elif risk_score >= 0.2:
        state = "NORMAL"
    else:
        state = "CLEAR"
    
    zone_states = {}
    for zone_id, data in sensor_data.items():
        dist = data.get("dist", 300)
        if dist < 50:
            zone_states[zone_id] = "SURGE"
        elif dist < 100:
            zone_states[zone_id] = "CRITICAL"
        elif dist < 150:
            zone_states[zone_id] = "ELEVATED"
        elif dist < 200:
            zone_states[zone_id] = "NORMAL"
        else:
            zone_states[zone_id] = "CLEAR"
    
    passage_rate = max(0, int((300 - avg_dist) / 5))
    
    return {
        "risk_score": risk_score,
        "state": state,
        "zone_states": zone_states,
        "device_count": total_wifi,
        "passage_rate": passage_rate
    }


# ═══════════════════════════════════════════════════════════
#                  DASHBOARD STATE
# ═══════════════════════════════════════════════════════════

class DashboardState:
    def __init__(self):
        self.last_readings = {}
        self.last_update = {}
        
        # Flow rate history (120 samples = 2 min at 1Hz)
        self.flow_history = {
            "A": deque(maxlen=120),
            "B": deque(maxlen=120),
            "C": deque(maxlen=120)
        }
        self.flow_time = deque(maxlen=120)
        
        # PRE-POPULATE with 120 baseline values for full graph from start
        now = datetime.now()
        for i in range(120):
            past_time = now - timedelta(seconds=(119 - i))
            self.flow_time.append(past_time)
            for zone_id in ["A", "B", "C"]:
                self.flow_history[zone_id].append(0)
        
        # Surge tracking
        self.surge_periods = []
        self._surge_start = None
        
        # Alert history
        self.alerts = deque(maxlen=50)
        self.last_alert_time = {}
        
        # Engine
        if HAS_ENGINE:
            self.engine = SurgeEngine()
            self.alert_manager = AlertManager(cooldown_seconds=10)
        else:
            self.engine = None
            self.alert_manager = None
    
    def get_data(self, scenario: str = "NORMAL"):
        """Get current sensor data and process."""
        sensor_data = generate_sim_data(scenario)
        current_time = time.time()
        
        for node_id in ["A", "B", "C"]:
            self.last_readings[node_id] = sensor_data[node_id]
            self.last_update[node_id] = current_time
        
        if self.engine:
            surge_state = self.engine.process(sensor_data)
            surge_dict = {
                "risk_score": surge_state.risk_score,
                "state": surge_state.state,
                "zone_states": surge_state.zone_states,
                "device_count": surge_state.device_count,
                "passage_rate": surge_state.passage_rate
            }
        else:
            surge_dict = calculate_state_from_data(sensor_data)
        
        # Update flow history
        now = datetime.now()
        self.flow_time.append(now)
        
        for zone_id in ["A", "B", "C"]:
            dist = sensor_data[zone_id]["dist"]
            flow = max(0, int((300 - dist) / 5))
            self.flow_history[zone_id].append(flow)
        
        # Track surge periods
        if surge_dict["state"] == "SURGE":
            if self._surge_start is None:
                self._surge_start = now
        else:
            if self._surge_start is not None:
                self.surge_periods.append((self._surge_start, now))
                self._surge_start = None
        
        self._process_alerts(surge_dict)
        
        return sensor_data, surge_dict
    
    def _process_alerts(self, surge_dict):
        """Generate alerts based on state."""
        state = surge_dict["state"]
        current_time = time.time()
        
        last_time = self.last_alert_time.get(state, 0)
        if current_time - last_time < 10:
            return
        
        alert = None
        if state == "SURGE":
            alert = {"level": "CRITICAL", "message": "SURGE DETECTED - Immediate action required", "zone": None}
        elif state == "CRITICAL":
            alert = {"level": "CRITICAL", "message": "Critical density reached", "zone": None}
        elif state == "ELEVATED":
            alert = {"level": "WARNING", "message": "Elevated crowd density", "zone": None}
        
        if alert:
            alert["timestamp"] = current_time
            self.alerts.append(alert)
            self.last_alert_time[state] = current_time
    
    def get_recent_alerts(self, n=10):
        return list(self.alerts)[-n:]


state = DashboardState()


# ═══════════════════════════════════════════════════════════
#                       COMPONENTS
# ═══════════════════════════════════════════════════════════

def create_header():
    """Create dashboard header."""
    return html.Div(
        style={
            "display": "flex",
            "justifyContent": "space-between",
            "alignItems": "center",
            "padding": "1rem 2rem",
            "background": COLORS["card"],
            "borderBottom": f"1px solid {COLORS['border']}"
        },
        children=[
            html.H1(
                "🛡️ STAMPEDE SHIELD v1.0",
                style={
                    "color": COLORS["foreground"],
                    "margin": 0,
                    "fontSize": "1.5rem",
                    "fontFamily": "Inter, sans-serif"
                }
            ),
            html.Div(
                style={"display": "flex", "alignItems": "center", "gap": "1.5rem"},
                children=[
                    # Scenario dropdown
                    html.Div([
                        html.Label(
                            "Scenario:",
                            style={
                                "color": COLORS["muted_foreground"],
                                "marginRight": "0.5rem",
                                "fontSize": "0.8rem"
                            }
                        ),
                        dcc.Dropdown(
                            id="scenario-dropdown",
                            options=[
                                {"label": "NORMAL", "value": "NORMAL"},
                                {"label": "BUSY", "value": "BUSY"},
                                {"label": "SURGE", "value": "SURGE"}
                            ],
                            value="NORMAL",
                            clearable=False,
                            style={"width": "120px"}
                        )
                    ], id="scenario-container", style={"display": "flex", "alignItems": "center"}),
                    
                    # Mode toggle
                    html.Div([
                        dbc.Switch(
                            id="mode-toggle",
                            value=True,
                            style={"marginRight": "0.5rem"}
                        ),
                        html.Span(
                            "SIM",
                            id="mode-label",
                            style={"color": COLORS["primary"], "fontWeight": "bold"}
                        )
                    ], style={"display": "flex", "alignItems": "center"}),
                    
                    # Live indicator
                    html.Div([
                        html.Div(
                            id="live-dot",
                            style={
                                "width": "10px",
                                "height": "10px",
                                "borderRadius": "50%",
                                "backgroundColor": COLORS["primary"],
                                "marginRight": "0.5rem"
                            }
                        ),
                        html.Span(
                            "SIM",
                            id="live-text",
                            style={"color": COLORS["primary"], "fontSize": "0.9rem"}
                        )
                    ], style={"display": "flex", "alignItems": "center"})
                ]
            )
        ]
    )


def create_zone_card(zone_id: str):
    """Create a zone monitoring card."""
    label = ZONE_LABELS.get(zone_id, "ZONE")
    return html.Div(
        id=f"zone-card-{zone_id}",
        style={
            "background": COLORS["card"],
            "borderRadius": "0.375rem",
            "padding": "1.25rem",
            "flex": "1",
            "minWidth": "200px",
            "border": f"1px solid {COLORS['border']}"
        },
        children=[
            html.Div(
                style={
                    "display": "flex",
                    "justifyContent": "space-between",
                    "alignItems": "center",
                    "marginBottom": "1rem"
                },
                children=[
                    html.Div([
                        html.Span(
                            f"ZONE {zone_id}",
                            style={
                                "color": COLORS["foreground"],
                                "fontWeight": "bold",
                                "fontSize": "1.1rem"
                            }
                        ),
                        html.Span(
                            f" · {label}",
                            style={
                                "color": COLORS["muted_foreground"],
                                "fontSize": "0.9rem"
                            }
                        )
                    ]),
                    html.Span(
                        "CLEAR",
                        id=f"zone-status-{zone_id}",
                        style={
                            "padding": "0.25rem 0.75rem",
                            "borderRadius": "0.375rem",
                            "fontSize": "0.75rem",
                            "fontWeight": "bold",
                            "backgroundColor": STATE_COLORS["CLEAR"],
                            "color": "#fff"
                        }
                    )
                ]
            ),
            html.Div(
                style={"display": "grid", "gridTemplateColumns": "1fr 1fr", "gap": "0.75rem"},
                children=[
                    html.Div([
                        html.Div("STATE", style={"color": COLORS["muted_foreground"], "fontSize": "0.7rem"}),
                        html.Div("--", id=f"zone-state-{zone_id}", style={"color": COLORS["foreground"], "fontSize": "1rem", "fontWeight": "bold"})
                    ]),
                    html.Div([
                        html.Div("FLOW", style={"color": COLORS["muted_foreground"], "fontSize": "0.7rem"}),
                        html.Div("--/min", id=f"zone-flow-{zone_id}", style={"color": COLORS["foreground"], "fontSize": "1rem"})
                    ]),
                    html.Div([
                        html.Div("DEVICES", style={"color": COLORS["muted_foreground"], "fontSize": "0.7rem"}),
                        html.Div("--", id=f"zone-devices-{zone_id}", style={"color": COLORS["foreground"], "fontSize": "1rem"})
                    ]),
                    html.Div([
                        html.Div("UPDATED", style={"color": COLORS["muted_foreground"], "fontSize": "0.7rem"}),
                        html.Div("--:--:--", id=f"zone-time-{zone_id}", style={"color": COLORS["muted_foreground"], "fontSize": "0.85rem", "fontFamily": "JetBrains Mono, monospace"})
                    ])
                ]
            )
        ]
    )


def create_metrics_panel():
    """Create metrics panel with 4 items."""
    return html.Div(
        style={
            "display": "flex",
            "justifyContent": "center",
            "gap": "3rem",
            "padding": "1.5rem",
            "background": COLORS["card"],
            "borderRadius": "0.375rem",
            "margin": "1rem 0",
            "border": f"1px solid {COLORS['border']}"
        },
        children=[
            html.Div([
                html.Div("RISK", style={"color": COLORS["muted_foreground"], "fontSize": "0.75rem", "textAlign": "center"}),
                html.Div("0%", id="metric-risk", style={"color": STATE_COLORS["CLEAR"], "fontSize": "1.75rem", "fontWeight": "bold", "textAlign": "center"})
            ]),
            html.Div([
                html.Div("STATE", style={"color": COLORS["muted_foreground"], "fontSize": "0.75rem", "textAlign": "center"}),
                html.Div("CLEAR", id="metric-state", style={"color": STATE_COLORS["CLEAR"], "fontSize": "1.25rem", "fontWeight": "bold", "textAlign": "center"})
            ]),
            html.Div([
                html.Div("DEVICES", style={"color": COLORS["muted_foreground"], "fontSize": "0.75rem", "textAlign": "center"}),
                html.Div("0", id="metric-devices", style={"color": COLORS["foreground"], "fontSize": "1.75rem", "fontWeight": "bold", "textAlign": "center"})
            ]),
            html.Div([
                html.Div("RATE", style={"color": COLORS["muted_foreground"], "fontSize": "0.75rem", "textAlign": "center"}),
                html.Div("0/min", id="metric-passage", style={"color": COLORS["foreground"], "fontSize": "1.5rem", "fontWeight": "bold", "textAlign": "center"})
            ])
        ]
    )


def create_flow_graph():
    """Create large flow rate graph."""
    return html.Div(
        style={
            "background": COLORS["card"],
            "borderRadius": "0.375rem",
            "padding": "1rem",
            "margin": "1rem 0",
            "border": f"1px solid {COLORS['border']}",
            "width": "100%",
            "boxSizing": "border-box"
        },
        children=[
            html.Div(
                "📈 FLOW RATE MONITOR (Last 2 minutes)",
                style={
                    "color": COLORS["muted_foreground"],
                    "fontSize": "0.85rem",
                    "marginBottom": "0.5rem",
                    "fontWeight": "bold",
                    "fontFamily": "Inter, sans-serif"
                }
            ),
            dcc.Graph(
                id="flow-graph",
                config={"displayModeBar": False, "responsive": True},
                style={"height": "400px", "width": "100%"}
            )
        ]
    )


def create_alert_panel():
    """Create alert log panel."""
    return html.Div(
        style={
            "background": COLORS["card"],
            "borderRadius": "0.375rem",
            "padding": "1rem",
            "maxHeight": "180px",
            "border": f"1px solid {COLORS['border']}"
        },
        children=[
            html.Div(
                "🔔 RECENT ALERTS",
                style={
                    "color": COLORS["muted_foreground"],
                    "fontSize": "0.85rem",
                    "marginBottom": "0.5rem",
                    "fontWeight": "bold"
                }
            ),
            html.Div(
                id="alert-list",
                style={"height": "130px", "overflowY": "auto"}
            )
        ]
    )


# ═══════════════════════════════════════════════════════════
#                       LAYOUT
# ═══════════════════════════════════════════════════════════

app.layout = html.Div(
    style={"backgroundColor": COLORS["background"], "minHeight": "100vh"},
    children=[
        dcc.Interval(id='update-interval', interval=500, n_intervals=0),
        dcc.Store(id='mode-store', data={'mode': 'SIM', 'scenario': 'NORMAL'}),
        
        create_header(),
        
        html.Div(
            style={"padding": "1rem 2rem"},
            children=[
                html.Div(
                    style={"display": "flex", "gap": "1rem", "marginBottom": "1rem"},
                    children=[
                        create_zone_card("A"),
                        create_zone_card("B"),
                        create_zone_card("C")
                    ]
                ),
                create_metrics_panel(),
                create_flow_graph(),
                create_alert_panel()
            ]
        )
    ]
)


# ═══════════════════════════════════════════════════════════
#                       CALLBACKS
# ═══════════════════════════════════════════════════════════

@app.callback(
    [
        Output('mode-store', 'data'),
        Output('mode-label', 'children'),
        Output('mode-label', 'style'),
        Output('scenario-container', 'style')
    ],
    [Input('mode-toggle', 'value'), Input('scenario-dropdown', 'value')],
    State('mode-store', 'data')
)
def update_mode(is_sim, scenario, current_data):
    mode = 'SIM' if is_sim else 'LIVE'
    new_data = {'mode': mode, 'scenario': scenario or 'NORMAL'}
    
    if is_sim:
        label = "SIM"
        label_style = {"color": COLORS["primary"], "fontWeight": "bold"}
        scenario_style = {"display": "flex", "alignItems": "center"}
    else:
        label = "LIVE"
        label_style = {"color": STATE_COLORS["CLEAR"], "fontWeight": "bold"}
        scenario_style = {"display": "none"}
    
    return new_data, label, label_style, scenario_style


@app.callback(
    [
        # Zone A
        Output('zone-status-A', 'children'),
        Output('zone-status-A', 'style'),
        Output('zone-state-A', 'children'),
        Output('zone-flow-A', 'children'),
        Output('zone-devices-A', 'children'),
        Output('zone-time-A', 'children'),
        # Zone B
        Output('zone-status-B', 'children'),
        Output('zone-status-B', 'style'),
        Output('zone-state-B', 'children'),
        Output('zone-flow-B', 'children'),
        Output('zone-devices-B', 'children'),
        Output('zone-time-B', 'children'),
        # Zone C
        Output('zone-status-C', 'children'),
        Output('zone-status-C', 'style'),
        Output('zone-state-C', 'children'),
        Output('zone-flow-C', 'children'),
        Output('zone-devices-C', 'children'),
        Output('zone-time-C', 'children'),
        # Metrics
        Output('metric-risk', 'children'),
        Output('metric-risk', 'style'),
        Output('metric-state', 'children'),
        Output('metric-state', 'style'),
        Output('metric-devices', 'children'),
        Output('metric-passage', 'children'),
        # Graph
        Output('flow-graph', 'figure'),
        # Live indicator
        Output('live-dot', 'style'),
        Output('live-text', 'children'),
        Output('live-text', 'style'),
        # Alerts
        Output('alert-list', 'children')
    ],
    [Input('update-interval', 'n_intervals')],
    [State('mode-store', 'data')]
)
def update_dashboard(n, mode_data):
    mode_data = mode_data or {'mode': 'SIM', 'scenario': 'NORMAL'}
    is_sim = mode_data.get('mode', 'SIM') == 'SIM'
    scenario = mode_data.get('scenario', 'NORMAL')
    
    sensor_data, surge_dict = state.get_data(scenario)
    
    results = []
    
    # Zone cards
    for zone_id in ["A", "B", "C"]:
        zone_state = surge_dict["zone_states"].get(zone_id, "CLEAR")
        dist = sensor_data[zone_id]["dist"]
        flow = max(0, int((300 - dist) / 5))
        wifi = sensor_data[zone_id]["wifi"]
        time_str = datetime.now().strftime("%H:%M:%S")
        
        badge_style = {
            "padding": "0.25rem 0.75rem",
            "borderRadius": "0.375rem",
            "fontSize": "0.75rem",
            "fontWeight": "bold",
            "backgroundColor": STATE_COLORS.get(zone_state, STATE_COLORS["CLEAR"]),
            "color": "#fff"
        }
        
        results.extend([
            zone_state,
            badge_style,
            zone_state,
            f"{flow}/min",
            str(wifi),
            time_str
        ])
    
    # Metrics
    risk_val = surge_dict["risk_score"] * 100
    system_state = surge_dict["state"]
    
    if risk_val >= 80:
        risk_color = STATE_COLORS["SURGE"]
    elif risk_val >= 60:
        risk_color = STATE_COLORS["CRITICAL"]
    elif risk_val >= 40:
        risk_color = STATE_COLORS["ELEVATED"]
    elif risk_val >= 20:
        risk_color = STATE_COLORS["NORMAL"]
    else:
        risk_color = STATE_COLORS["CLEAR"]
    
    risk_style = {"color": risk_color, "fontSize": "1.75rem", "fontWeight": "bold", "textAlign": "center"}
    state_style = {"color": STATE_COLORS.get(system_state, STATE_COLORS["CLEAR"]), "fontSize": "1.25rem", "fontWeight": "bold", "textAlign": "center"}
    
    results.extend([
        f"{risk_val:.0f}%",
        risk_style,
        system_state,
        state_style,
        str(surge_dict["device_count"]),
        f"{surge_dict['passage_rate']}/min"
    ])
    
    # ═══════════════════════════════════════════════════════
    #                  FLOW GRAPH (FIXED)
    # ═══════════════════════════════════════════════════════
    
    fig = go.Figure()
    
    now = datetime.now()
    two_min_ago = now - timedelta(seconds=120)
    
    # Surge shading
    for start, end in state.surge_periods[-5:]:
        if end > two_min_ago:
            fig.add_vrect(
                x0=max(start, two_min_ago),
                x1=end,
                fillcolor="rgba(239,68,68,0.15)",
                line_width=0
            )
    
    if state._surge_start and state._surge_start > two_min_ago:
        fig.add_vrect(
            x0=state._surge_start,
            x1=now,
            fillcolor="rgba(239,68,68,0.15)",
            line_width=0
        )
    
    # Zone lines with chart colors
    times = list(state.flow_time)
    for zone_id in ["A", "B", "C"]:
        fig.add_trace(go.Scatter(
            x=times,
            y=list(state.flow_history[zone_id]),
            mode='lines',
            name=f"Zone {zone_id}",
            line=dict(
                color=ZONE_COLORS[zone_id],
                width=2,
                shape='spline'
            ),
            hovertemplate=f"Zone {zone_id}: %{{y}}/min<extra></extra>"
        ))
    
    # Critical threshold
    fig.add_hline(
        y=30,
        line_dash="dash",
        line_color="rgba(239,68,68,0.4)",
        line_width=1,
        annotation_text="CRITICAL",
        annotation_position="right",
        annotation_font_color=COLORS["muted_foreground"],
        annotation_font_size=10
    )
    
    # Layout with correct colors
    fig.update_layout(
        paper_bgcolor=COLORS["card"],
        plot_bgcolor=COLORS["card"],
        font=dict(family="Inter, sans-serif"),
        xaxis=dict(
            showgrid=False,
            zeroline=False,
            showline=False,
            range=[two_min_ago, now],
            tickformat="%H:%M:%S",
            tickfont=dict(color=COLORS["muted_foreground"], size=10),
            dtick=30000,
            fixedrange=True
        ),
        yaxis=dict(
            showgrid=False,
            zeroline=False,
            showline=False,
            range=[0, 60],
            tickfont=dict(color=COLORS["muted_foreground"], size=10),
            fixedrange=True
        ),
        margin=dict(l=50, r=20, t=20, b=50),
        height=400,
        autosize=True,
        legend=dict(
            orientation="h",
            yanchor="bottom",
            y=1.02,
            xanchor="right",
            x=1,
            font=dict(color=COLORS["muted_foreground"], size=11)
        ),
        hovermode="x unified",
        hoverlabel=dict(
            bgcolor=COLORS["card"],
            font_color=COLORS["foreground"],
            bordercolor=COLORS["border"]
        )
    )
    
    results.append(fig)
    
    # Live indicator
    if is_sim:
        dot_style = {
            "width": "10px",
            "height": "10px",
            "borderRadius": "50%",
            "backgroundColor": COLORS["primary"],
            "marginRight": "0.5rem"
        }
        live_text = "SIM"
        live_style = {"color": COLORS["primary"], "fontSize": "0.9rem"}
    else:
        dot_style = {
            "width": "10px",
            "height": "10px",
            "borderRadius": "50%",
            "backgroundColor": STATE_COLORS["CLEAR"],
            "marginRight": "0.5rem"
        }
        live_text = "LIVE"
        live_style = {"color": STATE_COLORS["CLEAR"], "fontSize": "0.9rem"}
    
    results.extend([dot_style, live_text, live_style])
    
    # Alerts
    alerts = state.get_recent_alerts(10)
    if not alerts:
        alert_rows = [
            html.Div(
                "No alerts yet.",
                style={
                    "color": COLORS["muted_foreground"],
                    "fontStyle": "italic",
                    "padding": "0.5rem"
                }
            )
        ]
    else:
        LEVEL_ICONS = {"INFO": "ℹ️", "WARNING": "⚠️", "CRITICAL": "🚨"}
        LEVEL_BORDERS = {"INFO": "#3b82f6", "WARNING": "#eab308", "CRITICAL": "#ef4444"}
        
        alert_rows = []
        for i, alert in enumerate(reversed(alerts)):
            ts = datetime.fromtimestamp(alert["timestamp"]).strftime("%H:%M:%S")
            level = alert["level"]
            icon = LEVEL_ICONS.get(level, "")
            border_color = LEVEL_BORDERS.get(level, COLORS["border"])
            bg = COLORS["muted"] if i % 2 == 0 else COLORS["card"]
            
            alert_rows.append(html.Div(
                style={
                    "display": "flex",
                    "justifyContent": "space-between",
                    "alignItems": "center",
                    "padding": "0.4rem 0.6rem",
                    "borderLeft": f"3px solid {border_color}",
                    "background": bg,
                    "marginBottom": "2px",
                    "borderRadius": "2px"
                },
                children=[
                    html.Span(
                        f"{icon} {alert['message']}",
                        style={"color": COLORS["foreground"], "fontSize": "0.8rem"}
                    ),
                    html.Span(
                        ts,
                        style={
                            "color": COLORS["muted_foreground"],
                            "fontSize": "0.7rem",
                            "fontFamily": "JetBrains Mono, monospace"
                        }
                    )
                ]
            ))
    
    results.append(alert_rows)
    
    return results


# ═══════════════════════════════════════════════════════════
#                       RUN
# ═══════════════════════════════════════════════════════════

if __name__ == "__main__":
    print("=" * 50)
    print("  STAMPEDE SHIELD DASHBOARD")
    print("=" * 50)
    print(f"Open: http://127.0.0.1:8050")
    print(f"Mode: Simulation (toggle in header)")
    print(f"Scenarios: NORMAL, BUSY, SURGE")
    print("=" * 50)
    app.run(debug=True, host='0.0.0.0', port=8050)