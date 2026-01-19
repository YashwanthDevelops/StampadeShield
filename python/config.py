"""
╔═══════════════════════════════════════════════════════════╗
║                    STAMPEDE SHIELD                        ║
║                   Configuration File                      ║
╚═══════════════════════════════════════════════════════════╝

All thresholds, constants, and settings in one place.
Edit this file to tune the system behavior.

Author: StampedeShield Team
Version: 2.0
"""

# ═══════════════════════════════════════════════════════════
#                     NODE CONFIGURATION
# ═══════════════════════════════════════════════════════════

# Node positions in the room (x, y) in meters
# Origin (0,0) is bottom-left corner
NODE_POSITIONS = {
    "A": (0, 10),      # Top-left corner
    "B": (10, 10),     # Top-right corner  
    "C": (5, 0)        # Bottom-center (door/entrance)
}

# Room dimensions in meters
ROOM_BOUNDS = (10, 10)  # (Width, Height)

# Node roles
NODE_ROLES = {
    "A": "corner",      # Corner monitoring
    "B": "corner",      # Corner monitoring
    "C": "door"         # Door/entrance monitoring (master node)
}

# Which node is the master (has LEDs, buzzer, microphone)
MASTER_NODE = "C"


# ═══════════════════════════════════════════════════════════
#                    NETWORK CONFIGURATION
# ═══════════════════════════════════════════════════════════

# WiFi Hotspot Settings
HOTSPOT_SSID = "Vijayalakshmi's iPhone"  # Your iPhone hotspot name
HOTSPOT_PASS = "12345678"                 # Your hotspot password

# Server Configuration (Your Mac)
SERVER_IP = "172.20.10.2"
SERVER_PORT = 8000
SERVER_URL = f"http://{SERVER_IP}:{SERVER_PORT}/update"

# UDP Configuration (for direct node communication)
UDP_PORT = 4444
UDP_BROADCAST_IP = "255.255.255.255"

# Node timeout - consider offline after this many seconds
NODE_TIMEOUT = 5


# ═══════════════════════════════════════════════════════════
#                   DISTANCE THRESHOLDS
# ═══════════════════════════════════════════════════════════

# Ultrasonic sensor thresholds (in centimeters)
DISTANCE_THRESHOLDS = {
    "danger": 50,       # < 50cm = DANGER (very close/crowded)
    "warning": 100,     # < 100cm = WARNING (getting crowded)
    "safe": 100         # >= 100cm = SAFE (clear space)
}

# Passage Detection (Node C - Door)
PASSAGE_THRESHOLD = 50       # cm - someone is passing through
PRESENCE_THRESHOLD = 150     # cm - someone is near the door
MIN_PASSAGE_DURATION = 200   # ms - minimum time to count as passage
PASSAGE_COOLDOWN = 800       # ms - cooldown between passage counts
BASELINE_DISTANCE = 300      # cm - distance when doorway is empty

# Zone Detection (Nodes A, B - Corners)
ZONE_CLEAR_DIST = 200        # cm - zone is empty
ZONE_OCCUPIED_DIST = 150     # cm - someone present in zone
ZONE_CROWDED_DIST = 80       # cm - zone is crowded


# ═══════════════════════════════════════════════════════════
#                   SOUND THRESHOLDS (Node C)
# ═══════════════════════════════════════════════════════════

# Microphone thresholds (in decibels)
SOUND_THRESHOLDS = {
    "danger": 85,       # > 85dB = DANGER (screaming/panic)
    "warning": 70,      # > 70dB = WARNING (loud crowd)
    "safe": 70          # <= 70dB = SAFE (normal noise)
}

# Sound floor (quiet room baseline)
SOUND_FLOOR = 35            # dB - minimum reading

# Baseline calibration
MIC_BASELINE_WINDOW = 30    # seconds to establish baseline
MIC_SPIKE_MULTIPLIER = 1.5  # Spike if > baseline × this


# ═══════════════════════════════════════════════════════════
#                   WIFI DEVICE TRACKING
# ═══════════════════════════════════════════════════════════

# WiFi scan settings
WIFI_SCAN_INTERVAL = 5      # seconds between scans

# Device tracking
DEVICE_TIMEOUT = 30         # seconds - device considered gone after this

# Crowd estimation
# Not everyone has WiFi on, so multiply count
WIFI_MULTIPLIER = 1.4       # Actual people ≈ WiFi count × this

# Crowd density thresholds (based on WiFi device count)
WIFI_CROWD_THRESHOLDS = {
    "low": 5,           # < 5 devices = low crowd
    "moderate": 15,     # 5-15 devices = moderate
    "high": 25,         # 15-25 devices = high crowd
    "critical": 35      # > 35 devices = critical
}


# ═══════════════════════════════════════════════════════════
#                   RSSI / TRIANGULATION
# ═══════════════════════════════════════════════════════════

# RSSI to distance conversion parameters
RSSI_TX_POWER = -59         # dBm at 1 meter (calibrate for your environment)
RSSI_PATH_LOSS = 2.5        # Path loss exponent (2.0=free space, 2.5-3.0=indoor)

# Distance calculation: distance = 10 ^ ((TX_POWER - RSSI) / (10 * PATH_LOSS))


# ═══════════════════════════════════════════════════════════
#                   CLUSTERING / DENSITY
# ═══════════════════════════════════════════════════════════

# DBSCAN clustering parameters
CLUSTER_EPSILON = 1.5       # meters - max distance to be neighbors
CLUSTER_MIN_SAMPLES = 3     # minimum points to form a cluster

# Density thresholds
DENSITY_THRESHOLDS = {
    "safe": 1.0,            # < 1 person per sq meter
    "moderate": 2.0,        # 1-2 people per sq meter
    "high": 3.0,            # 2-3 people per sq meter
    "critical": 4.0         # > 4 people per sq meter (dangerous)
}


# ═══════════════════════════════════════════════════════════
#                   SURGE / RISK ENGINE
# ═══════════════════════════════════════════════════════════

# Risk calculation weights (must sum to 1.0)
RISK_WEIGHTS = {
    "flow_imbalance": 0.25,     # Entry vs exit rate imbalance
    "entry_velocity": 0.25,     # How fast people are entering
    "cluster_density": 0.30,    # How densely packed are clusters
    "zone_blockage": 0.20       # Are zones blocked/crowded
}

# State thresholds (risk score 0.0 - 1.0)
STATE_THRESHOLDS = [0.15, 0.35, 0.55, 0.75]

# State names corresponding to thresholds
# Score: 0.00-0.15 = CLEAR
# Score: 0.15-0.35 = NORMAL  
# Score: 0.35-0.55 = ELEVATED
# Score: 0.55-0.75 = HIGH
# Score: 0.75-1.00 = CRITICAL
STATE_NAMES = ["CLEAR", "NORMAL", "ELEVATED", "HIGH", "CRITICAL"]

# State colors for dashboard
STATE_COLORS = {
    "CLEAR": "#00FF00",      # Green
    "NORMAL": "#0088FF",     # Blue
    "ELEVATED": "#FFFF00",   # Yellow
    "HIGH": "#FF8800",       # Orange
    "CRITICAL": "#FF0000"    # Red
}

# State transition delays (prevents rapid flickering)
ESCALATE_DELAY = 3.0        # seconds before going UP a level
DEESCALATE_DELAY = 10.0     # seconds before going DOWN a level


# ═══════════════════════════════════════════════════════════
#                   LED INDICATOR SETTINGS
# ═══════════════════════════════════════════════════════════

# LED behavior mapping
LED_STATES = {
    "safe": {
        "green": True,
        "yellow": False,
        "red": False,
        "blink": False
    },
    "warning": {
        "green": False,
        "yellow": True,
        "red": False,
        "blink": False
    },
    "danger": {
        "green": False,
        "yellow": False,
        "red": True,
        "blink": True  # Blink red for danger
    }
}

# LED pin mapping (for reference - defined in Arduino code)
LED_PINS = {
    "green": 2,
    "yellow": 4,
    "red": 15
}


# ═══════════════════════════════════════════════════════════
#                   BUZZER SETTINGS
# ═══════════════════════════════════════════════════════════

# Buzzer behavior
BUZZER_PIN = 19
BUZZER_FREQUENCY = 2000     # Hz

# Auto-off timeout
BUZZER_TIMEOUT = 10         # seconds - auto-off after this

# Buzzer patterns (on_ms, off_ms)
BUZZER_PATTERNS = {
    "warning": (500, 500),      # Slow beep
    "danger": (150, 150),       # Fast beep
    "critical": (100, 50)       # Rapid beep
}


# ═══════════════════════════════════════════════════════════
#                   ALERTS / NOTIFICATIONS
# ═══════════════════════════════════════════════════════════

# Telegram Bot (optional)
TELEGRAM_ENABLED = False
TELEGRAM_BOT_TOKEN = "YOUR_BOT_TOKEN_HERE"
TELEGRAM_CHAT_ID = "YOUR_CHAT_ID_HERE"
TELEGRAM_COOLDOWN = 30      # seconds between alerts

# Alert triggers
ALERT_MIN_STATE = 3         # Minimum state index to trigger alert (3 = HIGH)
ALERT_STATES = ["HIGH", "CRITICAL"]  # States that trigger alerts


# ═══════════════════════════════════════════════════════════
#                   DASHBOARD SETTINGS
# ═══════════════════════════════════════════════════════════

# Dashboard refresh rate
DASHBOARD_REFRESH_MS = 200  # milliseconds

# History settings
HISTORY_MAX_POINTS = 300    # Max data points to keep (5 minutes at 1/sec)
HISTORY_INTERVAL = 1.0      # seconds between history saves

# Dashboard display
SHOW_DEBUG_INFO = True      # Show debug information
SHOW_RAW_DATA = False       # Show raw sensor values


# ═══════════════════════════════════════════════════════════
#                   SIMULATION SETTINGS
# ═══════════════════════════════════════════════════════════

# Simulator scenarios
SIMULATION_SCENARIOS = {
    "normal": {
        "dist_min": 150,
        "dist_max": 300,
        "wifi_min": 5,
        "wifi_max": 8,
        "pir_probability": 0.2,
        "db_min": 35,
        "db_max": 55
    },
    "busy": {
        "dist_min": 80,
        "dist_max": 150,
        "wifi_min": 15,
        "wifi_max": 25,
        "pir_probability": 0.6,
        "db_min": 55,
        "db_max": 75
    },
    "surge": {
        "dist_min": 30,
        "dist_max": 80,
        "wifi_min": 25,
        "wifi_max": 40,
        "pir_probability": 0.95,
        "db_min": 75,
        "db_max": 100
    }
}

# Surge escalation time
SURGE_DURATION = 30  # seconds


# ═══════════════════════════════════════════════════════════
#                   LOGGING SETTINGS
# ═══════════════════════════════════════════════════════════

# Logging
LOG_ENABLED = True
LOG_FILE = "stampedeshield.log"
LOG_LEVEL = "INFO"  # DEBUG, INFO, WARNING, ERROR
LOG_MAX_SIZE_MB = 10
LOG_BACKUP_COUNT = 3

# Console output
CONSOLE_VERBOSE = True      # Print detailed info to console
CONSOLE_COLORS = True       # Use colored output


# ═══════════════════════════════════════════════════════════
#                   HELPER FUNCTIONS
# ═══════════════════════════════════════════════════════════

def get_status_from_distance(distance_cm):
    """
    Determine status based on distance reading.
    
    Args:
        distance_cm: Distance in centimeters
        
    Returns:
        str: 'danger', 'warning', or 'safe'
    """
    if distance_cm < DISTANCE_THRESHOLDS["danger"]:
        return "danger"
    elif distance_cm < DISTANCE_THRESHOLDS["warning"]:
        return "warning"
    else:
        return "safe"


def get_status_from_sound(db):
    """
    Determine status based on sound level.
    
    Args:
        db: Sound level in decibels
        
    Returns:
        str: 'danger', 'warning', or 'safe'
    """
    if db > SOUND_THRESHOLDS["danger"]:
        return "danger"
    elif db > SOUND_THRESHOLDS["warning"]:
        return "warning"
    else:
        return "safe"


def get_crowd_level(wifi_count):
    """
    Determine crowd level based on WiFi device count.
    
    Args:
        wifi_count: Number of WiFi devices detected
        
    Returns:
        str: 'low', 'moderate', 'high', or 'critical'
    """
    if wifi_count >= WIFI_CROWD_THRESHOLDS["critical"]:
        return "critical"
    elif wifi_count >= WIFI_CROWD_THRESHOLDS["high"]:
        return "high"
    elif wifi_count >= WIFI_CROWD_THRESHOLDS["moderate"]:
        return "moderate"
    else:
        return "low"


def estimate_people_count(wifi_count):
    """
    Estimate actual number of people from WiFi count.
    
    Args:
        wifi_count: Number of WiFi devices detected
        
    Returns:
        int: Estimated number of people
    """
    return int(wifi_count * WIFI_MULTIPLIER)


def get_state_from_risk(risk_score):
    """
    Determine state from risk score.
    
    Args:
        risk_score: Float between 0.0 and 1.0
        
    Returns:
        tuple: (state_index, state_name, state_color)
    """
    state_index = 0
    for i, threshold in enumerate(STATE_THRESHOLDS):
        if risk_score >= threshold:
            state_index = i + 1
    
    state_name = STATE_NAMES[state_index]
    state_color = STATE_COLORS[state_name]
    
    return (state_index, state_name, state_color)


def rssi_to_distance(rssi):
    """
    Convert RSSI to approximate distance in meters.
    
    Args:
        rssi: Signal strength in dBm
        
    Returns:
        float: Estimated distance in meters
    """
    if rssi >= 0:
        return 0.0
    
    distance = 10 ** ((RSSI_TX_POWER - rssi) / (10 * RSSI_PATH_LOSS))
    return round(distance, 2)


# ═══════════════════════════════════════════════════════════
#                   VALIDATION
# ═══════════════════════════════════════════════════════════

def validate_config():
    """
    Validate configuration values.
    
    Returns:
        tuple: (is_valid, list of errors)
    """
    errors = []
    
    # Check risk weights sum to 1.0
    weight_sum = sum(RISK_WEIGHTS.values())
    if abs(weight_sum - 1.0) > 0.01:
        errors.append(f"RISK_WEIGHTS must sum to 1.0 (currently {weight_sum})")
    
    # Check state thresholds are ascending
    for i in range(len(STATE_THRESHOLDS) - 1):
        if STATE_THRESHOLDS[i] >= STATE_THRESHOLDS[i + 1]:
            errors.append("STATE_THRESHOLDS must be in ascending order")
            break
    
    # Check threshold values are reasonable
    if DISTANCE_THRESHOLDS["danger"] >= DISTANCE_THRESHOLDS["warning"]:
        errors.append("DISTANCE_THRESHOLDS danger should be less than warning")
    
    if SOUND_THRESHOLDS["warning"] >= SOUND_THRESHOLDS["danger"]:
        errors.append("SOUND_THRESHOLDS warning should be less than danger")
    
    return (len(errors) == 0, errors)


# Run validation when module is imported
if __name__ == "__main__":
    print("╔═══════════════════════════════════════════════════════════╗")
    print("║              STAMPEDE SHIELD CONFIGURATION                ║")
    print("╚═══════════════════════════════════════════════════════════╝")
    print()
    
    is_valid, errors = validate_config()
    
    if is_valid:
        print("✓ Configuration is valid!")
    else:
        print("✗ Configuration errors found:")
        for error in errors:
            print(f"  - {error}")
    
    print()
    print("Current Settings:")
    print(f"  WiFi: {HOTSPOT_SSID}")
    print(f"  Server: {SERVER_URL}")
    print(f"  Distance Thresholds: {DISTANCE_THRESHOLDS}")
    print(f"  Sound Thresholds: {SOUND_THRESHOLDS}")
    print(f"  State Names: {STATE_NAMES}")