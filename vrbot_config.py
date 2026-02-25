"""
VRBOT Config - 37 Tasks + Hybrid YOLO
"""
# --- ADB ---
ADB_EXE = r"C:\LDPlayer\LDPlayer9\adb.exe"
ADB_DEVICE = "emulator-5554"

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

# --- ALL 37 Tasks ---
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
}
