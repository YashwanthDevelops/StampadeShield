#!/usr/bin/env python3
"""
StampedeShield Dashboard - Skeleton Layout

A Dash-based monitoring dashboard with dark theme.
"""

from dash import Dash, html, dcc
from dash.dependencies import Input, Output
import dash_bootstrap_components as dbc

# Initialize app
app = Dash(
    __name__,
    external_stylesheets=[dbc.themes.BOOTSTRAP],
    assets_folder='assets',
    suppress_callback_exceptions=True
)

app.title = "StampedeShield Monitor"

# ═══════════════════════════════════════════════════════════
#                       COMPONENTS
# ═══════════════════════════════════════════════════════════

def create_header():
    """Create dashboard header with title and live indicator."""
    return html.Div(
        className="dashboard-header",
        children=[
            html.H1("STAMPEDE SHIELD v1.0", className="dashboard-title"),
            html.Div(
                className="live-indicator",
                children=[
                    html.Div(className="live-dot", id="live-dot"),
                    html.Span("LIVE", id="live-text")
                ]
            )
        ]
    )


def create_zone_card(zone_id: str):
    """Create a zone monitoring card."""
    return html.Div(
        className="zone-card",
        id=f"zone-card-{zone_id}",
        children=[
            html.Div(
                className="zone-card-header",
                children=[
                    html.Span(f"Zone {zone_id}", className="zone-name"),
                    html.Span(
                        "CLEAR",
                        className="zone-status-badge clear",
                        id=f"zone-status-{zone_id}"
                    )
                ]
            ),
            html.Div(
                className="zone-metrics",
                children=[
                    html.Div([
                        html.Span("Distance: "),
                        html.Span("--", className="zone-metric-value", id=f"zone-dist-{zone_id}")
                    ]),
                    html.Div([
                        html.Span("PIR: "),
                        html.Span("--", className="zone-metric-value", id=f"zone-pir-{zone_id}")
                    ]),
                    html.Div([
                        html.Span("WiFi: "),
                        html.Span("--", className="zone-metric-value", id=f"zone-wifi-{zone_id}")
                    ]),
                    html.Div([
                        html.Span("Sound: "),
                        html.Span("--", className="zone-metric-value", id=f"zone-sound-{zone_id}")
                    ])
                ]
            )
        ]
    )


def create_metrics_panel():
    """Create the main metrics panel."""
    return html.Div(
        className="metrics-panel",
        children=[
            html.Div(
                className="metrics-grid",
                children=[
                    html.Div(
                        className="metric-item",
                        children=[
                            html.Div("RISK SCORE", className="metric-label"),
                            html.Div("0.00", className="metric-value", id="metric-risk")
                        ]
                    ),
                    html.Div(
                        className="metric-item",
                        children=[
                            html.Div("DEVICE COUNT", className="metric-label"),
                            html.Div("0", className="metric-value", id="metric-devices")
                        ]
                    ),
                    html.Div(
                        className="metric-item",
                        children=[
                            html.Div("PASSAGE RATE", className="metric-label"),
                            html.Div("0/min", className="metric-value", id="metric-passage")
                        ]
                    ),
                    html.Div(
                        className="metric-item",
                        children=[
                            html.Div("SYSTEM STATE", className="metric-label"),
                            html.Div(
                                "CLEAR",
                                className="metric-value state clear",
                                id="metric-state"
                            )
                        ]
                    )
                ]
            )
        ]
    )


def create_graph_placeholder():
    """Create graph placeholder."""
    return html.Div(
        className="graph-panel",
        id="graph-container",
        children=[
            dcc.Graph(
                id="risk-graph",
                config={"displayModeBar": False},
                figure={
                    "data": [],
                    "layout": {
                        "paper_bgcolor": "rgba(0,0,0,0)",
                        "plot_bgcolor": "rgba(0,0,0,0)",
                        "font": {"color": "#e0d4c8"},
                        "xaxis": {"showgrid": False, "visible": False},
                        "yaxis": {"showgrid": False, "visible": False},
                        "annotations": [{
                            "text": "Risk Score Timeline (Placeholder)",
                            "xref": "paper",
                            "yref": "paper",
                            "showarrow": False,
                            "font": {"size": 14, "color": "#888"}
                        }],
                        "height": 250,
                        "margin": {"l": 20, "r": 20, "t": 20, "b": 20}
                    }
                }
            )
        ]
    )


def create_alert_panel():
    """Create alert log panel."""
    return html.Div(
        className="alert-panel",
        children=[
            html.Div(
                className="alert-panel-header",
                children=[
                    html.Span("🔔"),
                    html.Span("Recent Alerts")
                ]
            ),
            html.Div(
                className="alert-list",
                id="alert-list",
                children=[
                    html.Div(
                        className="alert-item info",
                        children=[
                            html.Span("System initialized. Monitoring active."),
                            html.Span("--:--:--", className="alert-time")
                        ]
                    )
                ]
            )
        ]
    )


# ═══════════════════════════════════════════════════════════
#                       LAYOUT
# ═══════════════════════════════════════════════════════════

app.layout = html.Div([
    # Interval for updates (500ms)
    dcc.Interval(
        id='update-interval',
        interval=500,
        n_intervals=0
    ),
    
    # Header
    create_header(),
    
    # Main Container
    html.Div(
        className="dashboard-container",
        children=[
            # Row 1: Zone Cards
            html.Div(
                className="zone-row",
                children=[
                    create_zone_card("A"),
                    create_zone_card("B"),
                    create_zone_card("C")
                ]
            ),
            
            # Row 2: Metrics Panel
            create_metrics_panel(),
            
            # Row 3: Graph Placeholder
            create_graph_placeholder(),
            
            # Row 4: Alert Log
            create_alert_panel()
        ]
    )
])


# ═══════════════════════════════════════════════════════════
#                       CALLBACKS (Skeleton)
# ═══════════════════════════════════════════════════════════

@app.callback(
    Output('live-text', 'children'),
    Input('update-interval', 'n_intervals')
)
def update_live_indicator(n):
    """Update live indicator text."""
    return "LIVE" if n % 2 == 0 else "LIVE •"


# Placeholder callback - will be connected to real data later
@app.callback(
    [Output('metric-risk', 'children'),
     Output('metric-devices', 'children'),
     Output('metric-passage', 'children'),
     Output('metric-state', 'children'),
     Output('metric-state', 'className')],
    Input('update-interval', 'n_intervals')
)
def update_metrics(n):
    """Placeholder metrics update."""
    # This will be replaced with real data connection
    return "0.00", "0", "0/min", "CLEAR", "metric-value state clear"


if __name__ == "__main__":
    print("Starting StampedeShield Dashboard...")
    print("Open http://127.0.0.1:8050 in your browser")
    app.run(debug=True, host='0.0.0.0', port=8050)
