"""
VRBOT Config - 16 Tasks + Hybrid YOLO
"""
# --- ADB ---
ADB_EXE = r"C:\LDPlayer\LDPlayer9\adb.exe"
ADB_DEVICE = "127.0.0.1:5555"

# --- AI Provider ---
AI_PROVIDER = "openai"  # "openai" or "anthropic"
OPENAI_MODEL = "gpt-4o-mini"
CLAUDE_MODEL = "claude-sonnet-4-20250514"

# --- YOLO ONNX (FREE - runs locally, no PyTorch needed) ---
YOLO_ENABLED = True
YOLO_MODEL_PATH = "models/best.onnx"
YOLO_CONFIDENCE = 0.45

# --- Paths ---
DEBUG_DIR = "debug_screenshots"

# --- Anti-Ban ---
TAP_DELAY_MIN = 0.5
TAP_DELAY_MAX = 2.0
TASK_DELAY_MIN = 5
TASK_DELAY_MAX = 15
COORDINATE_JITTER = 3
SESSION_BREAK_INTERVAL = 40
SESSION_BREAK_DURATION = 60

# --- Navigation ---
NAV_MAX_RETRIES = 15

# --- Task Settings ---
TROOP_ROTATION = ['infantry', 'lancer', 'archer']

# --- 16 Tasks ONLY ---
TASKS_ENABLED = {
    # Quick Collections
    "daily_gifts": True,
    "rewards": True,
    "mail_rewards": True,
    "helps": True,
    "tribe_gifts": True,
    "prosperity": True,

    # Buildings
    "construction": True,       # Upgrade
    "research": True,
    "hall_of_valor": True,
    "clear_forest": True,

    # World Map
    "gather": True,             # Farming / Gather resources
    "niflung": True,            # Kill Niflung
    "kill_monster": True,       # Kill Monster
    "rally_niflung": True,      # Rally Niflung Leader

    # Alliance
    "tribe_tech": True,
}
