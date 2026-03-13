"""
VRBOT Config v5.4 — Dual Backend (LDPlayer + Docker/Redroid)
"""
import os
import sys

# --- .env file loader ---
_env_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env")
if os.path.exists(_env_path):
    with open(_env_path) as _f:
        for _line in _f:
            _line = _line.strip()
            if _line and not _line.startswith("#") and "=" in _line:
                _k, _v = _line.split("=", 1)
                os.environ.setdefault(_k.strip(), _v.strip())

# --- Backend ---
# "ldplayer"  = Local LDPlayer emulator via ADB (Windows)
# "docker"    = Redroid containers via docker exec (Server)
# Auto-detect: Linux defaults to "docker", Windows to "ldplayer"
_default_backend = "docker" if sys.platform.startswith("linux") else "ldplayer"
BACKEND = os.environ.get("VRBOT_BACKEND", _default_backend)

# --- ADB (LDPlayer backend or direct ADB on Linux) ---
if sys.platform.startswith("linux"):
    ADB_EXE = "adb"
    ADB_DEVICE = os.environ.get("ADB_SERIAL", "emulator-5554")
else:
    ADB_EXE = r"C:\LDPlayer\LDPlayer9\adb.exe"
    ADB_DEVICE = os.environ.get("ADB_SERIAL", "emulator-5554")

# --- Docker (Redroid backend) ---
DOCKER_CONTAINER = os.environ.get("VRBOT_CONTAINER", "farm_001")
# SSH to remote server (None = local docker, "root@88.99.64.19" = remote)
DOCKER_SSH = os.environ.get("VRBOT_DOCKER_SSH", None)

# --- AI Provider ---
AI_PROVIDER = "anthropic"  # "openai" or "anthropic"
OPENAI_MODEL = "gpt-4o-mini"
CLAUDE_MODEL = "claude-sonnet-4-20250514"

# --- API Keys (already loaded from .env at top of file) ---

# --- YOLO ONNX (FREE - runs locally, no PyTorch needed) ---
YOLO_ENABLED = True
YOLO_MODEL_PATH = "models/best.onnx"
YOLO_CONFIDENCE = 0.40  # lowered from 0.45 → catches more buttons

# --- Paths ---
DEBUG_DIR = "debug_screenshots"

# --- Anti-Ban (tuned for safety) ---
TAP_DELAY_MIN = 0.5
TAP_DELAY_MAX = 2.0
TASK_DELAY_MIN = 5
TASK_DELAY_MAX = 15
COORDINATE_JITTER = 3
SESSION_BREAK_INTERVAL = 40   # minutes
SESSION_BREAK_DURATION = 60   # seconds

# --- Navigation ---
NAV_MAX_RETRIES = 15

# --- Task Settings ---
TROOP_ROTATION = ['infantry', 'lancer', 'archer']

# --- ALL Tasks ---
TASKS_ENABLED = {
    # ── Quick Collections ──
    "daily_gifts": True,
    "rewards": True,
    "mail_rewards": True,
    "helps": True,
    "tribe_gifts": True,
    "prosperity": True,

    # ── Buildings ──
    "construction": True,
    "research": True,
    "train_troops": True,
    "hall_of_valor": True,
    "divination": True,
    "smithy": True,
    "upgrade_chief_hall": True,
    "chief_hall": True,
    "expansion": True,

    # ── Economy ──
    "errands": True,
    "commissions": True,
    "farmer_appointments": True,
    "recruit_farmers": True,
    "village_champions": True,

    # ── Heroes ──
    "hero_xp": True,
    "hero_training": True,
    "account_items": True,

    # ── World Map ──
    "gather": True,
    "niflung": True,
    "kill_monster": True,
    "rally_niflung": True,
    "clear_forest": True,
    "cinderbone": True,
    "staging_post": True,
    "reclaim_midgard": True,

    # ── Events ──
    "leidolf": True,
    "festival_flames": True,
    "chapter": True,
    "promo_codes": True,

    # ── Defense ──
    "shield": True,

    # ── Alliance ──
    "tribe_tech": True,
    "city_rush": False,
    "community_events": False,
    "conquer_island": False,
    "gather_supplies": False,
    "market_trade": False,
    "rebate_pack": False,
    "surprise_gift": False,
    "toy_shop": False,
    "tribe_gold_tile": False,

    # ── Maintenance ──
    "wall_repair": True,
    "heal_troops": True,
    "troop_upgrade": True,
    "gather_boost": True,
    "map_explore": False,
    "intelligence_rewards": True,
}
