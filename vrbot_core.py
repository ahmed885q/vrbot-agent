"""
VRBOT Core Engine v5.3 — 4-Layer Hybrid Detection
===================================================
Layer 1: Template Match (free, ~5ms)
Layer 2: YOLO ONNX (free, ~50-100ms)
Layer 3: GPT-4o mini (paid, ~2s)
Layer 4: Claude (paid, ~3s fallback)

Changelog v5.3:
  - Template Matching as Layer 1 (fastest, free)
  - 4-layer detection: Template → YOLO → OpenAI → Claude
  - All v5.2 improvements retained
"""
import subprocess, os, sys, time, json, base64, re, random, io, math
import numpy as np
from PIL import Image

from vrbot_config import (
    BACKEND, ADB_EXE, ADB_DEVICE, DEBUG_DIR,
    DOCKER_CONTAINER, DOCKER_SSH,
    TAP_DELAY_MIN, TAP_DELAY_MAX, COORDINATE_JITTER,
    TASK_DELAY_MIN, TASK_DELAY_MAX,
    SESSION_BREAK_INTERVAL, SESSION_BREAK_DURATION,
    AI_PROVIDER, OPENAI_MODEL, CLAUDE_MODEL,
    YOLO_ENABLED, YOLO_MODEL_PATH, YOLO_CONFIDENCE,
)

# --- Template Matcher ---
_template_matcher = None
def _init_templates():
    global _template_matcher
    if _template_matcher is None:
        try:
            from template_matcher import TemplateMatcher
            tm = TemplateMatcher("templates", confidence=0.75)
            tm.load_templates()
            if tm.available_templates:
                _template_matcher = tm
                print(f"  [init] Template matcher ready ({len(tm.available_templates)} templates)")
            else:
                print("  [init] No templates found — skipping template matching")
        except Exception as e:
            print(f"  [init] Template matcher not available: {e}")
    return _template_matcher

# --- AI Clients ---
_openai_client = None
_anthropic_client = None
_onnx_session = None
_onnx_tried = False
_onnx_labels = None

def _init_openai():
    global _openai_client
    if _openai_client is None:
        try:
            from openai import OpenAI
            _openai_client = OpenAI()
            print("  [init] OpenAI client ready")
        except Exception as e:
            print(f"  [init] OpenAI not available: {e}")
    return _openai_client

def _init_anthropic():
    global _anthropic_client
    if _anthropic_client is None:
        try:
            import anthropic
            _anthropic_client = anthropic.Anthropic()
            print("  [init] Anthropic client ready")
        except Exception as e:
            print(f"  [init] Anthropic not available: {e}")
    return _anthropic_client

def _init_yolo():
    """Initialize ONNX Runtime session for YOLO (no PyTorch needed)."""
    global _onnx_session, _onnx_tried, _onnx_labels
    if _onnx_tried:
        return _onnx_session
    _onnx_tried = True
    if not YOLO_ENABLED:
        return None

    onnx_path = YOLO_MODEL_PATH.replace(".pt", ".onnx")
    if not os.path.exists(onnx_path):
        print(f"  [init] ONNX model not found: {onnx_path}")
        return None

    try:
        import onnxruntime as ort
        _onnx_session = ort.InferenceSession(onnx_path, providers=["CPUExecutionProvider"])
        meta = _onnx_session.get_modelmeta()
        if meta.custom_metadata_map and "names" in meta.custom_metadata_map:
            import ast
            _onnx_labels = ast.literal_eval(meta.custom_metadata_map["names"])
        else:
            _onnx_labels = {}
        print(f"  [init] YOLO ONNX loaded: {onnx_path} ({len(_onnx_labels)} classes)")
    except Exception as e:
        print(f"  [init] ONNX not available: {e}")
        _onnx_session = None
    return _onnx_session


# ══════════════════════════════════════════════════════════════
# YOLO CLASS → SCREEN MAPPING (all 224 classes)
# ══════════════════════════════════════════════════════════════
# Each rule: (screen_name, [yolo_class_keywords], min_matches)
SCREEN_RULES = [
    ("city", [
        "resource_bar", "resource-bar_icon", "city_icon", "city location_icon",
        "manage city_icon", "manage_cite_popup", "worker_inf_icon",
        "chat_ box_icon", "chat_box",
    ], 1),
    ("world_map", [
        "compass_icon", "warld_btn", "world_botn", "farm", "farm_icon",
        "quarry", "quarry_icon", "sawmil", "sawmil_icon", "monster",
        "monster_icon", "niflungs", "niflungs_leader", "niflung_popup",
        "coordinates_btn", "search_btn_icon", "resume_search_btn",
        "resume_search_btn_icon", "boss_icon",
    ], 1),
    ("mail_screen", [
        "mail_popup", "mail_tab", "new_mail_btn",
        "delete_mail_botn", "system_botn", "report_botn",
    ], 1),
    ("alliance_screen", [
        "tribe_popup", "tribe_tab", "tribe_members_btn",
        "tribe_bank_btn", "tribe_assist_popup",
        "staging_post_popup", "donate_btn", "donate_gem_btn",
    ], 1),
    ("hero_screen", [
        "hero_list", "hero_avater", "hero_power",
        "hero_summon_popup", "hero_summon_btn", "skills_icon",
        "main_commander", "secondary_commander",
    ], 1),
    ("training", [
        "barracks_popup", "train_btn", "train_now_btn", "quick_train_btn",
        "infantry_btn", "archer_btn", "pikemen_btn", "porter_btn",
        "infantry_type", "archer_type", "pikemen_typy", "porter_type",
        "troop_list", "troop_slider", "troop_tier", "troop_type",
    ], 1),
    ("research_screen", [
        "research_arrow", "teck_node", "teck_tap",
    ], 1),
    ("building_info", [
        "building_upgrade_popup", "upgrade_popup",
    ], 1),
    ("event_screen", [
        "event_banner", "daily_quests", "dialy_quests_popup",
        "quest_detail_popup", "quest_reward_tap",
        "conquest_quests_btn",
    ], 1),
    ("march_screen", [
        "create_squad_popup", "create_troop_popup",
        "march_number", "depart_btn", "route_option",
    ], 1),
    ("shop", [
        "mall_botn", "purchase_btn", "prestige_shop_btn",
        "crystal_trove_btn",
    ], 1),
    ("inventory", [
        "item_popupo", "convert_items_btn",
        "item_smelting_btn", "materials_btn", "werehouse_btn",
    ], 1),
    ("profile", [
        "here-avatar_icon", "honor_wall_btn",
    ], 2),  # need 2 to avoid false positives
    ("settings", [
        "ceneral_sittings_popup",
    ], 1),
    ("divination", [
        "divination_shack_popup", "divination_shack_btn",
        "divination_result_popup", "one_divination_btn",
        "fast_divination_btn",
    ], 1),
    ("commission", [
        "commission_popup", "commissions_btn", "commission_item",
    ], 1),
    ("clan_camp", [
        "clan_camp_popup", "recruit_worker_popup", "hire_btn",
        "hired_btn", "recruitment_btn",
        "exploration_btn", "exploration_map_popup", "exploration_squad",
    ], 1),
    ("dragon", [
        "dragon_cave_btn", "dragon_cave_popup", "capture_mount_btn",
        "quick_tame_btn", "team_beast_btn",
    ], 1),
    ("infirmary", [
        "infirmary_popup", "heal_now_btn", "healing_btn",
    ], 1),
    ("smithy_screen", [
        "reflnement_previem_btn",
    ], 1),
    ("summon", [
        "hero_summon_popup", "summon_btn", "summon_tab",
        "summon_10x_btn", "energy_summon_btn",
        "free_summon_btn", "skill_summon_popup", "skill_summon_btn",
    ], 1),
    ("prosperity_screen", [
        "prosperity_popup", "prosperity_icon",
    ], 1),
    ("war_screen", [
        "war_popup",
    ], 1),
    ("mercenary", [
        "mercenary_guild_popup",
    ], 1),
    ("niflung_encounter", [
        "niflung_popup", "niflungs_popup",
    ], 1),
    ("obtainable_resources", [
        "obtainable_resources_popup", "obtainable resources_icon",
    ], 1),
    ("outdoor_meet", [
        "outdoor_meet_popup",
    ], 1),
    ("encounter", [
        "enconuter_popup",
    ], 1),
]

# Exact YOLO class names for hybrid_find_button
YOLO_BUTTON_MAP = {
    "claim":    ["claim_btn", "claim_all_botn", "claim_free_btn", "rewards_claimed_botn"],
    "close":    ["close_btn", "back_btn"],
    "confirm":  ["confirm_btn", "ok_btn"],
    "cancel":   ["cancel_btn"],
    "upgrade":  ["upgrade_btn", "upgrade_now_btn"],
    "attack":   ["attack_btn"],
    "rally":    ["rally_btn", "auto_rally_btn"],
    "gather":   ["gather_btn", "gather_btn_icon", "farm_btn", "sawmil_btn"],
    "march":    ["march_btn", "depart_btn"],
    "help_all": ["assist_btn", "complete_all_btn"],
    "train":    ["train_btn", "train_now_btn", "quick_train_btn"],
    "use":      ["use_btn"],
    "submit":   ["submit_btn", "submit_all_btn"],
    "donate":   ["donate_btn", "donate_gem_btn"],
    "heal":     ["heal_now_btn", "healing_btn"],
    "recruit":  ["recruit_btn", "recruitment_btn"],
    "search":   ["search_btn", "search_btn_icon", "resume_search_btn"],
    "create":   ["create_btn"],
    "go":       ["go_btn"],
    "speed_up": ["speed_up_btn"],
    "shop":     ["shop_btn", "mall_botn"],
    "info":     ["info_btn", "details_btn"],
    "refresh":  ["refresh_btn", "refresh_map_btn"],
    "recall":   ["recall_btn"],
    "maximum":  ["maximum_btn"],
    "appoint":  ["appoint_all_btn"],
    "converge": ["converge_btn"],
}


class Bot:
    """Main bot engine v5.2 — YOLO + GPT-4o mini + Claude hybrid."""

    def __init__(self):
        os.makedirs(DEBUG_DIR, exist_ok=True)
        self._shot_counter = 0
        self._session_start = time.time()
        self._last_tap_time = 0
        self._ai_calls = 0
        self._yolo_hits = 0
        self._api_calls = 0
        self._nav_fails = 0
        self._claude_disabled = False
        self._screen_cache = None
        self._screen_cache_time = 0
        self._last_screenshot_path = None
        self._last_screenshot_b64 = None
        self._last_screenshot_time = 0
        self._tmpl_hits = 0
        _init_yolo()
        _init_templates()

    # ════════════════════════════════════════════════════
    # ADB COMMANDS
    # ════════════════════════════════════════════════════

    def _adb(self, *args):
        """Execute ADB command — routes to LDPlayer ADB or Docker backend."""
        if BACKEND == "docker":
            return self._docker_exec(*args)
        cmd = [ADB_EXE, "-s", ADB_DEVICE] + list(args)
        return subprocess.run(cmd, capture_output=True, timeout=15)

    def _docker_exec(self, *args):
        """Execute command inside a Docker/Redroid container.

        Translates ADB commands to docker exec equivalents:
          adb shell <cmd>      → docker exec <container> <cmd>
          adb exec-out <cmd>   → docker exec <container> <cmd>
          adb pull <src> <dst> → docker cp <container>:<src> <dst>
        """
        args = list(args)
        docker_cmd = None

        if args[0] == "shell":
            # adb shell <cmd> → docker exec <container> <cmd>
            shell_cmd = " ".join(args[1:])
            docker_cmd = ["docker", "exec", DOCKER_CONTAINER, "sh", "-c", shell_cmd]
        elif args[0] == "exec-out":
            # adb exec-out <cmd> → docker exec <container> <cmd>
            shell_cmd = " ".join(args[1:])
            docker_cmd = ["docker", "exec", DOCKER_CONTAINER, "sh", "-c", shell_cmd]
        elif args[0] == "pull":
            # adb pull <remote> <local> → docker cp <container>:<remote> <local>
            if len(args) >= 3:
                remote_path, local_path = args[1], args[2]
                docker_cmd = ["docker", "cp", f"{DOCKER_CONTAINER}:{remote_path}", local_path]
            else:
                return subprocess.CompletedProcess(args, 1, b"", b"pull needs 2 args")
        else:
            # Unknown — treat as shell command
            shell_cmd = " ".join(args)
            docker_cmd = ["docker", "exec", DOCKER_CONTAINER, "sh", "-c", shell_cmd]

        # Wrap with SSH if running remotely
        if DOCKER_SSH:
            remote_str = " ".join(f'"{a}"' if " " in a else a for a in docker_cmd)
            docker_cmd = ["ssh", "-o", "StrictHostKeyChecking=no", DOCKER_SSH, remote_str]

        return subprocess.run(docker_cmd, capture_output=True, timeout=30)

    def _invalidate_cache(self):
        """Invalidate screen cache after any interaction."""
        self._screen_cache = None

    # Probability of using natural touch (short swipe-to-tap) instead of instant tap
    _NATURAL_TOUCH_PROB = 0.25  # 25% of taps use natural approach

    def tap(self, x, y, jitter=True):
        elapsed = time.time() - self._last_tap_time
        min_wait = TAP_DELAY_MIN
        if elapsed < min_wait:
            time.sleep(min_wait - elapsed + random.uniform(0, 0.3))
        if jitter and COORDINATE_JITTER > 0:
            x += random.randint(-COORDINATE_JITTER, COORDINATE_JITTER)
            y += random.randint(-COORDINATE_JITTER, COORDINATE_JITTER)
        x, y = max(0, min(1279, x)), max(0, min(719, y))

        # Natural touch: ~25% of taps simulate finger approach (short swipe ending at target)
        if random.random() < self._NATURAL_TOUCH_PROB:
            self._natural_tap(x, y)
        else:
            self._adb("shell", "input", "tap", str(x), str(y))

        self._last_tap_time = time.time()
        self._invalidate_cache()
        print(f"    tap ({x},{y})")

    def _natural_tap(self, x, y):
        """Simulate natural finger touch with Bezier-like curved approach.

        Human fingers don't teleport — they approach from a slight offset
        with a curved trajectory (not perfectly straight).
        Uses quadratic Bezier interpolation for more natural movement.
        """
        # Start point: 10-35px away in a random direction
        offset = random.randint(10, 35)
        angle = random.uniform(0, 6.283)  # Random direction (2*pi radians)
        start_x = int(x + offset * math.cos(angle))
        start_y = int(y + offset * math.sin(angle))
        start_x = max(0, min(1279, start_x))
        start_y = max(0, min(719, start_y))

        # Control point for Bezier curve (perpendicular offset for natural arc)
        perp_angle = angle + random.choice([-1.57, 1.57])  # ±90 degrees
        ctrl_offset = random.randint(3, 12)
        mid_x = (start_x + x) // 2 + int(ctrl_offset * math.cos(perp_angle))
        mid_y = (start_y + y) // 2 + int(ctrl_offset * math.sin(perp_angle))

        # Generate 3-5 intermediate points along the Bezier curve
        n_points = random.randint(3, 5)
        points = []
        for i in range(n_points + 1):
            t = i / n_points
            # Quadratic Bezier: B(t) = (1-t)²·P0 + 2(1-t)t·P1 + t²·P2
            bx = int((1 - t) ** 2 * start_x + 2 * (1 - t) * t * mid_x + t ** 2 * x)
            by = int((1 - t) ** 2 * start_y + 2 * (1 - t) * t * mid_y + t ** 2 * y)
            bx = max(0, min(1279, bx))
            by = max(0, min(719, by))
            points.append((bx, by))

        # Execute as chained short swipes (total 80-200ms)
        total_dur = random.randint(80, 200)
        seg_dur = max(20, total_dur // len(points))
        for i in range(len(points) - 1):
            self._adb("shell", "input", "swipe",
                       str(points[i][0]), str(points[i][1]),
                       str(points[i + 1][0]), str(points[i + 1][1]),
                       str(seg_dur))

    def swipe(self, x1, y1, x2, y2, duration=None):
        if duration is None:
            duration = random.randint(300, 700)
        self._adb("shell", "input", "swipe",
                   str(x1), str(y1), str(x2), str(y2), str(duration))
        self._invalidate_cache()
        print(f"    swipe ({x1},{y1})->({x2},{y2}) {duration}ms")

    def adb_back(self):
        """Press Android back button."""
        self._adb("shell", "input", "keyevent", "4")
        self._invalidate_cache()
        print("    [adb] back")

    def dismiss_chat(self):
        """Brief pause before tapping toolbar buttons."""
        time.sleep(0.3)

    # ════════════════════════════════════════════════════
    # SCREENSHOT (exec-out = faster, fewer corrupt PNGs)
    # ════════════════════════════════════════════════════

    def screenshot(self, name=None):
        if name is None:
            self._shot_counter += 1
            name = f"shot_{self._shot_counter:04d}"
        path = os.path.join(DEBUG_DIR, name + ".png")

        if BACKEND == "docker":
            return self._screenshot_docker(path)

        # Method 1: exec-out (fast, fewer corrupt PNGs on real devices)
        try:
            result = subprocess.run(
                [ADB_EXE, "-s", ADB_DEVICE, "exec-out", "screencap", "-p"],
                capture_output=True, timeout=10
            )
            if result.returncode == 0 and len(result.stdout) > 5000:
                with open(path, "wb") as f:
                    f.write(result.stdout)
                img = Image.open(path)
                img.verify()
                self._last_screenshot_path = path
                self._last_screenshot_time = time.time()
                return path
        except:
            pass

        # Method 2: shell + pull (reliable on LDPlayer)
        for attempt in range(3):
            self._adb("shell", "screencap", "-p", "/sdcard/vrbot_screen.png")
            time.sleep(0.3)
            self._adb("pull", "/sdcard/vrbot_screen.png", path)
            if os.path.exists(path) and os.path.getsize(path) > 5000:
                try:
                    img = Image.open(path)
                    img.verify()
                    self._last_screenshot_path = path
                    self._last_screenshot_time = time.time()
                    return path
                except Exception:
                    print(f"  [screenshot] Corrupt PNG (attempt {attempt+1}/3)")
            else:
                print(f"  [screenshot] Empty/missing (attempt {attempt+1}/3)")
            time.sleep(0.5)

        print("  [screenshot] WARNING: All attempts failed, using last file")

    def _screenshot_docker(self, path):
        """Screenshot via Docker exec — fast pipe method."""
        os.makedirs(os.path.dirname(path) if os.path.dirname(path) else DEBUG_DIR, exist_ok=True)

        # Method 1: exec-out pipe (fastest — no temp file on device)
        try:
            result = self._adb("exec-out", "screencap", "-p")
            if result.returncode == 0 and len(result.stdout) > 5000:
                with open(path, "wb") as f:
                    f.write(result.stdout)
                img = Image.open(path)
                img.verify()
                self._last_screenshot_path = path
                self._last_screenshot_time = time.time()
                return path
        except Exception:
            pass

        # Method 2: screencap + docker cp (reliable fallback)
        for attempt in range(3):
            self._adb("shell", "screencap", "-p", "/data/vrbot_screen.png")
            time.sleep(0.3)
            self._adb("pull", "/data/vrbot_screen.png", path)
            if os.path.exists(path) and os.path.getsize(path) > 5000:
                try:
                    img = Image.open(path)
                    img.verify()
                    self._last_screenshot_path = path
                    self._last_screenshot_time = time.time()
                    return path
                except Exception:
                    print(f"  [screenshot] Corrupt PNG (attempt {attempt+1}/3)")
            else:
                print(f"  [screenshot] Empty/missing (attempt {attempt+1}/3)")
            time.sleep(0.5)

        print("  [screenshot] WARNING: Docker screenshot failed")
        self._last_screenshot_path = path
        self._last_screenshot_time = time.time()
        return path

    def screenshot_b64(self, name=None):
        # Reuse if < 0.5s old (avoids double-capture in same call chain)
        if (self._last_screenshot_b64
            and (time.time() - self._last_screenshot_time) < 0.5
            and self._last_screenshot_path
            and os.path.exists(self._last_screenshot_path)):
            return self._last_screenshot_b64

        path = self.screenshot(name)
        with open(path, "rb") as f:
            b64 = base64.standard_b64encode(f.read()).decode("utf-8")
        self._last_screenshot_b64 = b64
        return b64

    # ════════════════════════════════════════════════════
    # WORLD MAP DETECTION & NAVIGATION
    # ════════════════════════════════════════════════════

    def is_world_map(self, image_b64=None):
        """Check if on world map. YOLO first (free), then AI."""
        # Try YOLO first
        if YOLO_ENABLED:
            detections = self.yolo_detect(image_b64=image_b64)
            classes = set(d["class"] for d in detections)
            world_indicators = {"compass_icon", "warld_btn", "world_botn",
                                "farm", "farm_icon", "quarry", "quarry_icon",
                                "sawmil", "monster", "monster_icon",
                                "coordinates_btn", "search_btn_icon",
                                "niflungs", "boss_icon"}
            city_indicators = {"resource_bar", "resource-bar_icon", "city_icon",
                               "manage city_icon", "worker_inf_icon",
                               "chat_ box_icon", "chat_box"}
            world_hits = len(classes & world_indicators)
            city_hits = len(classes & city_indicators)
            if world_hits > 0 and world_hits > city_hits:
                print(f"  [yolo] World map confirmed ({world_hits} indicators)")
                return True
            if city_hits > 0 and city_hits > world_hits:
                print(f"  [yolo] City confirmed ({city_hits} indicators)")
                return False

        # Fallback to AI
        if image_b64 is None:
            image_b64 = self.screenshot_b64()
        result = self.ask_ai(
            "Viking Rise (1280x720). WORLD MAP or CITY?\n"
            "WORLD MAP = open terrain, other castles, coordinate bar, compass on left.\n"
            "CITY = your buildings inside walls, toolbar bottom-right.\n"
            '{"screen": "world_map"} or {"screen": "city"}\nJSON ONLY.',
            image_b64, 50
        )
        if result:
            return result.get("screen") == "world_map"
        return False

    # -- Fallback coordinates for core navigation --
    _NAV_WORLD_MAP_BTN = (47, 643)   # World map button (city bottom-left)
    _NAV_HOME_BTN = (72, 636)        # Home/city button (world map bottom-left)
    _NAV_HOME_ALTS = [(72, 636), (47, 643), (60, 654), (130, 654)]

    def _tap_nav(self, button_type, fallback_xy, ai_prompt=None):
        """Hybrid tap for core navigation: YOLO/Template → fallback."""
        result = self.hybrid_find_button(button_type)
        if result and result.get("found"):
            self.tap(result["x"], result["y"])
            return True
        if ai_prompt:
            result = self.hybrid_find(
                [], f"Viking Rise (1280x720). {ai_prompt}\n"
                '{"found": true, "x": 640, "y": 400} or {"found": false}. JSON ONLY.')
            if result and result.get("found"):
                self.tap(result["x"], result["y"])
                return True
        self.tap(fallback_xy[0], fallback_xy[1], jitter=False)
        return True

    def go_to_world_map(self, max_attempts=3):
        """Navigate to world map. Hybrid detection + fallback."""
        if self.is_world_map():
            print("  [world] Already on world map")
            return True
        for attempt in range(max_attempts):
            print(f"  [world] Tapping world map button (attempt {attempt+1})...")
            self._tap_nav("go", self._NAV_WORLD_MAP_BTN,
                          "Find the World Map button on bottom-left toolbar")
            time.sleep(3)
            if self.is_world_map():
                print("  [world] World map confirmed!")
                return True
            print("  [world] Not on world map yet...")
            time.sleep(1)
        print("  [world] Could not reach world map.")
        return False

    def _save_debug(self, name):
        """Save current screenshot for debugging."""
        try:
            path = os.path.join(DEBUG_DIR, f"{name}.png")
            self._adb("shell", "screencap", "-p", "/sdcard/vrbot_debug.png")
            time.sleep(0.3)
            self._adb("pull", "/sdcard/vrbot_debug.png", path)
            print(f"  [debug] Saved: {path}")
        except:
            pass

    # ════════════════════════════════════════════════════
    # YOLO ONNX DETECTION (FREE - LOCAL, NO PYTORCH)
    # ════════════════════════════════════════════════════

    def _preprocess_image(self, image_path, input_size=720):
        """Preprocess image for ONNX YOLO inference."""
        img = Image.open(image_path).convert("RGB")
        orig_w, orig_h = img.size
        scale = min(input_size / orig_w, input_size / orig_h)
        new_w, new_h = int(orig_w * scale), int(orig_h * scale)
        img_resized = img.resize((new_w, new_h), Image.BILINEAR)
        canvas = Image.new("RGB", (input_size, input_size), (114, 114, 114))
        pad_x = (input_size - new_w) // 2
        pad_y = (input_size - new_h) // 2
        canvas.paste(img_resized, (pad_x, pad_y))
        arr = np.array(canvas, dtype=np.float32) / 255.0
        arr = arr.transpose(2, 0, 1)
        arr = np.expand_dims(arr, 0)
        return arr, orig_w, orig_h, scale, pad_x, pad_y

    @staticmethod
    def _nms(detections, iou_threshold=0.5):
        """Non-Maximum Suppression to remove overlapping boxes."""
        if not detections:
            return detections
        # Sort by confidence descending
        dets = sorted(detections, key=lambda d: -d["confidence"])
        keep = []
        while dets:
            best = dets.pop(0)
            keep.append(best)
            remaining = []
            for d in dets:
                # Calculate IoU
                x1 = max(best["x1"], d["x1"])
                y1 = max(best["y1"], d["y1"])
                x2 = min(best["x2"], d["x2"])
                y2 = min(best["y2"], d["y2"])
                inter = max(0, x2 - x1) * max(0, y2 - y1)
                area_a = (best["x2"] - best["x1"]) * (best["y2"] - best["y1"])
                area_b = (d["x2"] - d["x1"]) * (d["y2"] - d["y1"])
                union = area_a + area_b - inter
                iou = inter / union if union > 0 else 0
                if iou < iou_threshold:
                    remaining.append(d)
            dets = remaining
        return keep

    def yolo_detect(self, image_path=None, image_b64=None):
        """Run YOLO ONNX on screenshot. Returns list of detections with NMS."""
        session = _init_yolo()
        if session is None:
            return []

        if image_path is None and image_b64:
            tmp = os.path.join(DEBUG_DIR, "_yolo_tmp.png")
            with open(tmp, "wb") as f:
                f.write(base64.b64decode(image_b64))
            image_path = tmp
        elif image_path is None:
            image_path = self.screenshot()

        try:
            input_shape = session.get_inputs()[0].shape
            input_size = input_shape[2] if len(input_shape) >= 3 else 720
            arr, orig_w, orig_h, scale, pad_x, pad_y = self._preprocess_image(image_path, input_size)

            input_name = session.get_inputs()[0].name
            outputs = session.run(None, {input_name: arr})
            preds = outputs[0]

            if preds.shape[1] < preds.shape[2]:
                preds = preds[0].T
            else:
                preds = preds[0]

            detections = []
            for pred in preds:
                cx, cy, w, h = pred[:4]
                class_scores = pred[4:]
                cls_id = int(np.argmax(class_scores))
                conf = float(class_scores[cls_id])

                if conf < YOLO_CONFIDENCE:
                    continue

                x1 = (cx - w / 2 - pad_x) / scale
                y1 = (cy - h / 2 - pad_y) / scale
                x2 = (cx + w / 2 - pad_x) / scale
                y2 = (cy + h / 2 - pad_y) / scale

                x1 = max(0, min(orig_w, x1))
                y1 = max(0, min(orig_h, y1))
                x2 = max(0, min(orig_w, x2))
                y2 = max(0, min(orig_h, y2))

                center_x = int((x1 + x2) / 2)
                center_y = int((y1 + y2) / 2)
                cls_name = _onnx_labels.get(cls_id, f"class_{cls_id}").lower()

                detections.append({
                    "class": cls_name,
                    "confidence": round(conf, 3),
                    "x": center_x, "y": center_y,
                    "x1": int(x1), "y1": int(y1),
                    "x2": int(x2), "y2": int(y2),
                })

            # Apply NMS to remove duplicates
            detections = self._nms(detections, iou_threshold=0.5)

            if detections:
                self._yolo_hits += 1
            return detections

        except Exception as e:
            print(f"  [yolo] Error: {e}")
            return []

    def yolo_find(self, class_name, image_b64=None):
        """Find specific class using YOLO."""
        detections = self.yolo_detect(image_b64=image_b64)
        class_name = class_name.lower()
        for d in detections:
            if class_name in d["class"] or d["class"] in class_name:
                print(f"  [yolo] Found {d['class']} ({d['confidence']}) at ({d['x']}, {d['y']})")
                return {"found": True, "x": d["x"], "y": d["y"]}
        return None

    def yolo_find_any(self, class_names, image_b64=None):
        """Find any of the given classes. Uses exact YOLO class names."""
        detections = self.yolo_detect(image_b64=image_b64)
        for d in detections:
            for name in class_names:
                if name.lower() in d["class"] or d["class"] in name.lower():
                    print(f"  [yolo] Found {d['class']} ({d['confidence']}) at ({d['x']}, {d['y']})")
                    return {"found": True, "x": d["x"], "y": d["y"], "class": d["class"]}
        return None

    def yolo_find_all(self, class_names, image_b64=None):
        """Find ALL instances of given classes. Returns list."""
        detections = self.yolo_detect(image_b64=image_b64)
        results = []
        for d in detections:
            for name in class_names:
                if name.lower() in d["class"] or d["class"] in name.lower():
                    results.append({"found": True, "x": d["x"], "y": d["y"],
                                    "class": d["class"], "confidence": d["confidence"]})
        return results

    def yolo_detect_screen(self, image_path=None, image_b64=None):
        """Detect screen from YOLO classes. Maps ALL 224 classes → 22+ screens."""
        detections = self.yolo_detect(image_path=image_path, image_b64=image_b64)
        if not detections:
            return None

        classes = set(d["class"] for d in detections)

        # Check each screen rule
        best_screen = None
        best_matches = 0
        for screen_name, keywords, min_matches in SCREEN_RULES:
            matches = sum(1 for kw in keywords if any(kw in c for c in classes))
            if matches >= min_matches and matches > best_matches:
                best_screen = screen_name
                best_matches = matches

        if best_screen:
            det_names = [d["class"] for d in detections[:5]]
            return {"screen": best_screen,
                    "details": f"yolo({best_matches}): {', '.join(det_names)}"}

        # Generic popup detection
        if any("popup" in c or "btn" in c for c in classes):
            popup_classes = [c for c in classes if "popup" in c or "btn" in c]
            return {"screen": "popup",
                    "details": f"yolo: {', '.join(list(popup_classes)[:5])}"}

        return None

    # ════════════════════════════════════════════════════
    # AI VISION (API — paid)
    # ════════════════════════════════════════════════════

    @staticmethod
    def _extract_json(text):
        try:
            return json.loads(text.strip())
        except:
            pass
        for pat in [r'```json\s*(.*?)\s*```', r'```\s*(.*?)\s*```']:
            m = re.search(pat, text, re.DOTALL)
            if m:
                try:
                    return json.loads(m.group(1).strip())
                except:
                    pass
        start = text.find("{")
        if start >= 0:
            depth = 0
            for i in range(start, len(text)):
                if text[i] == "{": depth += 1
                elif text[i] == "}": depth -= 1
                if depth == 0:
                    try:
                        return json.loads(text[start:i+1])
                    except:
                        break
        return None

    def _ask_openai(self, prompt, image_b64=None, max_tokens=300):
        client = _init_openai()
        if client is None:
            return None
        content = []
        if image_b64:
            content.append({
                "type": "image_url",
                "image_url": {"url": f"data:image/png;base64,{image_b64}", "detail": "low"}
            })
        content.append({"type": "text", "text": prompt})
        try:
            resp = client.chat.completions.create(
                model=OPENAI_MODEL, max_tokens=max_tokens,
                messages=[{"role": "user", "content": content}],
            )
            text = resp.choices[0].message.content
            self._api_calls += 1
            return self._extract_json(text)
        except Exception as e:
            print(f"  [openai] Error: {e}")
            return None

    def _ask_anthropic(self, prompt, image_b64=None, max_tokens=300):
        if self._claude_disabled:
            return None
        client = _init_anthropic()
        if client is None:
            return None
        content = []
        if image_b64:
            content.append({
                "type": "image",
                "source": {"type": "base64", "media_type": "image/png", "data": image_b64}
            })
        content.append({"type": "text", "text": prompt})
        try:
            resp = client.messages.create(
                model=CLAUDE_MODEL, max_tokens=max_tokens,
                messages=[{"role": "user", "content": content}],
            )
            text = resp.content[0].text
            self._api_calls += 1
            return self._extract_json(text)
        except Exception as e:
            err_str = str(e)
            print(f"  [claude] Error: {err_str}")
            if "401" in err_str or "authentication" in err_str.lower():
                self._claude_disabled = True
                print("  [claude] API key invalid — disabling Claude for this session")
            return None

    def ask_ai(self, prompt, image_b64=None, max_tokens=300):
        self._ai_calls += 1
        if AI_PROVIDER == "openai":
            result = self._ask_openai(prompt, image_b64, max_tokens)
            if result is None and not self._claude_disabled:
                result = self._ask_anthropic(prompt, image_b64, max_tokens)
            return result
        else:
            if not self._claude_disabled:
                result = self._ask_anthropic(prompt, image_b64, max_tokens)
            else:
                result = None
            if result is None:
                result = self._ask_openai(prompt, image_b64, max_tokens)
            return result

    def ask_ai_text(self, prompt, image_b64=None, max_tokens=500):
        if AI_PROVIDER == "openai":
            client = _init_openai()
            if client:
                content = []
                if image_b64:
                    content.append({"type": "image_url", "image_url": {"url": f"data:image/png;base64,{image_b64}", "detail": "low"}})
                content.append({"type": "text", "text": prompt})
                try:
                    resp = client.chat.completions.create(model=OPENAI_MODEL, max_tokens=max_tokens, messages=[{"role": "user", "content": content}])
                    return resp.choices[0].message.content
                except Exception as e:
                    print(f"  [openai] Error: {e}")
        if not self._claude_disabled:
            client = _init_anthropic()
            if client:
                content = []
                if image_b64:
                    content.append({"type": "image", "source": {"type": "base64", "media_type": "image/png", "data": image_b64}})
                content.append({"type": "text", "text": prompt})
                try:
                    resp = client.messages.create(model=CLAUDE_MODEL, max_tokens=max_tokens, messages=[{"role": "user", "content": content}])
                    return resp.content[0].text
                except Exception as e:
                    print(f"  [claude] Error: {e}")
        return None

    # ════════════════════════════════════════════════════
    # HYBRID DETECTION (YOLO first → API fallback)
    # ════════════════════════════════════════════════════

    def hybrid_find(self, yolo_classes, ai_prompt, image_b64=None, tmpl_names=None):
        """4-layer detection: Template → YOLO → AI."""
        if image_b64 is None:
            image_b64 = self.screenshot_b64()

        # Layer 1: Template matching (free, ~5ms)
        tm = _init_templates()
        if tm and tmpl_names:
            result = tm.find_any(tmpl_names, screenshot_b64=image_b64)
            if result:
                self._tmpl_hits += 1
                return result

        # Layer 2: YOLO (free, ~50-100ms)
        if YOLO_ENABLED and yolo_classes:
            result = self.yolo_find_any(yolo_classes, image_b64)
            if result:
                return result

        # Layer 3+4: AI (paid)
        return self.ask_ai(ai_prompt, image_b64)

    def hybrid_find_button(self, button_type, image_b64=None):
        """Find button using 4-layer detection: Template → YOLO → AI."""
        # Use exact YOLO class names from the model
        yolo_classes = YOLO_BUTTON_MAP.get(button_type, [])

        # Template names to search for (auto-captured + reference)
        TMPL_NAMES = {
            "claim":    ["claim_btn", "claim_all_botn", "claim_free_btn", "ref_claim", "ref_daily_claim", "ref_alliance_claim"],
            "close":    ["close_btn", "back_btn", "ref_vr_close", "ref_vr_back"],
            "confirm":  ["confirm_btn", "ok_btn", "ref_vr_confirm", "ref_confirm"],
            "cancel":   ["cancel_btn", "ref_vr_cancel"],
            "upgrade":  ["upgrade_btn", "upgrade_now_btn"],
            "attack":   ["attack_btn", "ref_attack"],
            "gather":   ["gather_btn", "gather_btn_icon", "ref_gather"],
            "march":    ["march_btn", "depart_btn"],
            "help_all": ["assist_btn", "complete_all_btn"],
            "train":    ["train_btn", "train_now_btn", "quick_train_btn", "ref_train"],
            "use":      ["use_btn"],
            "submit":   ["submit_btn", "submit_all_btn"],
            "donate":   ["donate_btn", "donate_gem_btn", "ref_donate"],
            "heal":     ["heal_now_btn", "healing_btn"],
            "recruit":  ["recruit_btn", "recruitment_btn"],
            "search":   ["search_btn", "resume_search_btn", "ref_search"],
            "create":   ["create_btn"],
            "go":       ["go_btn"],
            "speed_up": ["speed_up_btn", "ref_speedup"],
            "rally":    ["rally_btn", "auto_rally_btn"],
            "recall":   ["recall_btn"],
            "maximum":  ["maximum_btn"],
            "appoint":  ["appoint_all_btn"],
            "converge": ["converge_btn"],
        }
        tmpl_names = TMPL_NAMES.get(button_type, [])

        AI_PROMPTS = {
            "claim":    'Viking Rise (1280x720). Find green Claim/Collect button. {"found":true,"x":640,"y":500} or {"found":false}. JSON ONLY.',
            "close":    'Viking Rise (1280x720). Find X/Close button (top-right corner). {"found":true,"x":1230,"y":50} or {"found":false}. JSON ONLY.',
            "confirm":  'Viking Rise (1280x720). Find Confirm/OK/Yes button. {"found":true,"x":640,"y":400} or {"found":false}. JSON ONLY.',
            "cancel":   'Viking Rise (1280x720). Find Cancel button. {"found":true,"x":640,"y":400} or {"found":false}. JSON ONLY.',
            "upgrade":  'Viking Rise (1280x720). Find Upgrade/Build button. {"found":true,"x":640,"y":500} or {"found":false}. JSON ONLY.',
            "attack":   'Viking Rise (1280x720). Find Attack button. {"found":true,"x":640,"y":500} or {"found":false}. JSON ONLY.',
            "gather":   'Viking Rise (1280x720). Find Gather button. {"found":true,"x":640,"y":500} or {"found":false}. JSON ONLY.',
            "march":    'Viking Rise (1280x720). Find March/Depart button. {"found":true,"x":640,"y":500} or {"found":false}. JSON ONLY.',
            "help_all": 'Viking Rise (1280x720). Find Help All/Assist button. {"found":true,"x":640,"y":500} or {"found":false}. JSON ONLY.',
            "train":    'Viking Rise (1280x720). Find Train/Recruit button. {"found":true,"x":640,"y":500} or {"found":false}. JSON ONLY.',
            "use":      'Viking Rise (1280x720). Find Use/Activate button. {"found":true,"x":640,"y":500} or {"found":false}. JSON ONLY.',
            "submit":   'Viking Rise (1280x720). Find Submit button. {"found":true,"x":640,"y":500} or {"found":false}. JSON ONLY.',
            "donate":   'Viking Rise (1280x720). Find Donate button. {"found":true,"x":640,"y":500} or {"found":false}. JSON ONLY.',
            "heal":     'Viking Rise (1280x720). Find Heal button. {"found":true,"x":640,"y":500} or {"found":false}. JSON ONLY.',
            "recruit":  'Viking Rise (1280x720). Find Recruit button. {"found":true,"x":640,"y":500} or {"found":false}. JSON ONLY.',
            "search":   'Viking Rise (1280x720). Find Search button. {"found":true,"x":640,"y":500} or {"found":false}. JSON ONLY.',
            "create":   'Viking Rise (1280x720). Find Create button. {"found":true,"x":640,"y":500} or {"found":false}. JSON ONLY.',
            "go":       'Viking Rise (1280x720). Find Go button. {"found":true,"x":640,"y":500} or {"found":false}. JSON ONLY.',
            "speed_up": 'Viking Rise (1280x720). Find Speed Up button. {"found":true,"x":640,"y":500} or {"found":false}. JSON ONLY.',
            "rally":    'Viking Rise (1280x720). Find Rally button. {"found":true,"x":640,"y":500} or {"found":false}. JSON ONLY.',
            "recall":   'Viking Rise (1280x720). Find Recall button. {"found":true,"x":640,"y":500} or {"found":false}. JSON ONLY.',
            "maximum":  'Viking Rise (1280x720). Find Maximum button. {"found":true,"x":640,"y":500} or {"found":false}. JSON ONLY.',
            "appoint":  'Viking Rise (1280x720). Find Appoint All button. {"found":true,"x":640,"y":500} or {"found":false}. JSON ONLY.',
        }
        ai_prompt = AI_PROMPTS.get(button_type,
            f'Viking Rise (1280x720). Find {button_type} button. '
            '{"found":true,"x":640,"y":500} or {"found":false}. JSON ONLY.')

        return self.hybrid_find(yolo_classes, ai_prompt, image_b64, tmpl_names=tmpl_names)

    def hybrid_tap(self, button_type, fallback_xy=None, timeout=5.0, retries=2):
        """Convenience: detect button via 4-layer cascade → tap it → return success.

        This is the recommended way to interact with any game UI element.
        Flow: Template → YOLO → AI → fallback_xy (if provided).

        Args:
            button_type: Key from YOLO_BUTTON_MAP (e.g. "claim", "close", "confirm")
            fallback_xy: Optional (x, y) tuple as last resort if all detection fails
            timeout: Max seconds to wait for detection across retries
            retries: Number of detection attempts before using fallback
        Returns:
            dict: {"tapped": True/False, "method": "template|yolo|ai|fallback", "x": x, "y": y}
        """
        for attempt in range(retries):
            result = self.hybrid_find_button(button_type)
            if result and result.get("found"):
                method = result.get("method", result.get("template", "ai"))
                if isinstance(method, str) and "/" in method:
                    method = "template"
                elif not isinstance(method, str):
                    method = "detection"
                self.tap(result["x"], result["y"])
                print(f"    [hybrid_tap] {button_type} found via {method} at ({result['x']},{result['y']})")
                return {"tapped": True, "method": method, "x": result["x"], "y": result["y"]}
            if attempt < retries - 1:
                time.sleep(min(timeout / retries, 2.0))

        # Fallback to hardcoded coordinates
        if fallback_xy:
            self.tap(fallback_xy[0], fallback_xy[1], jitter=True)
            print(f"    [hybrid_tap] {button_type} FALLBACK at {fallback_xy}")
            return {"tapped": True, "method": "fallback", "x": fallback_xy[0], "y": fallback_xy[1]}

        print(f"    [hybrid_tap] {button_type} NOT FOUND (no fallback)")
        return {"tapped": False, "method": "none", "x": 0, "y": 0}

    def hybrid_tap_center(self, fallback_xy=(640, 400)):
        """Tap center of screen to dismiss popups. Tries close button first."""
        result = self.hybrid_tap("close", fallback_xy=fallback_xy, retries=1, timeout=2.0)
        if not result["tapped"] or result["method"] == "fallback":
            # Also try confirm/ok
            result2 = self.hybrid_tap("confirm", fallback_xy=fallback_xy, retries=1, timeout=2.0)
            if result2["tapped"] and result2["method"] != "fallback":
                return result2
        return result

    # ════════════════════════════════════════════════════
    # SCREEN DETECTION (cached, YOLO → API)
    # ════════════════════════════════════════════════════

    def detect_screen(self, image_b64=None, force=False):
        """Detect screen type. Cached 2s. YOLO first (free), then API."""
        # Cache: reuse if < 2 seconds old
        if not force and self._screen_cache and (time.time() - self._screen_cache_time) < 2.0:
            return self._screen_cache

        # Step 1: Try YOLO (FREE)
        if YOLO_ENABLED:
            yolo_result = self.yolo_detect_screen(image_b64=image_b64)
            if yolo_result:
                print(f"  [yolo] Screen: {yolo_result['screen']}")
                self._screen_cache = yolo_result
                self._screen_cache_time = time.time()
                return yolo_result

        # Step 2: Fall back to API (PAID)
        if image_b64 is None:
            image_b64 = self.screenshot_b64()
        prompt = (
            "Viking Rise mobile game (1280x720). Identify screen type.\n"
            "SCREENS:\n"
            "city = buildings inside walls, resource bar top, toolbar bottom-right\n"
            "world_map = open terrain, other castles, coordinates top, compass left\n"
            "mail_screen = mail inbox with tabs\n"
            "alliance_screen = tribe/alliance panel\n"
            "hero_screen = hero list or detail\n"
            "event_screen = events/quests panel\n"
            "training = barracks with troop types\n"
            "building_info = building detail with upgrade button\n"
            "research_screen = tech tree\n"
            "march_screen = troop deployment\n"
            "shop = store/mall\n"
            "inventory = items/backpack\n"
            "popup = dialog with OK/Confirm/Close\n"
            "profile = player profile\n"
            "settings = settings menu\n"
            "chat = chat window\n"
            "unknown = cannot determine\n\n"
            "KEY: buildings + toolbar = city. terrain + compass = world_map.\n"
            '{"screen":"city","details":"buildings with toolbar"}\nJSON ONLY.'
        )
        result = self.ask_ai(prompt, image_b64, 100)
        if result:
            result = self._normalize_screen(result)
            self._screen_cache = result
            self._screen_cache_time = time.time()
        return result

    @staticmethod
    def _normalize_screen(result):
        screen = result.get('screen', 'unknown').lower()
        details = result.get('details', '').lower()

        KEYWORD_MAP = {
            'alliance_screen': ['tribe', 'alliance', 'guild', 'clan'],
            'event_screen': ['quest', 'daily', 'event', 'mission', 'chapter'],
            'mail_screen': ['mail', 'inbox', 'message'],
            'inventory': ['item', 'bag', 'backpack', 'inventory', 'equip'],
            'hero_screen': ['hero', 'champion', 'warrior', 'character'],
            'world_map': ['world', 'map', 'overworld', 'kingdom'],
            'shop': ['shop', 'store', 'mall', 'market', 'purchase'],
            'city': ['city', 'base', 'town', 'home', 'village', 'main view'],
            'research_screen': ['research', 'academy', 'study', 'tech'],
            'training': ['train', 'barracks', 'recruit', 'troop'],
            'settings': ['setting', 'option', 'config'],
            'chat': ['chat', 'message board', 'group chat'],
            'profile': ['profile', 'avatar', 'account', 'lord info', 'commander'],
            'march_screen': ['march', 'deploy', 'dispatch'],
        }

        if screen == 'unknown':
            for correct_screen, keywords in KEYWORD_MAP.items():
                for kw in keywords:
                    if kw in details:
                        result['screen'] = correct_screen
                        return result

        for correct_screen, keywords in KEYWORD_MAP.items():
            for kw in keywords:
                if kw in screen:
                    result['screen'] = correct_screen
                    return result

        return result

    def find_and_tap(self, description, image_b64=None):
        if image_b64 is None:
            image_b64 = self.screenshot_b64()
        prompt = (
            f"Viking Rise (1280x720). Find: {description}\n"
            '{"found": true, "x": 640, "y": 360}\n'
            "Reply ONLY JSON."
        )
        result = self.ask_ai(prompt, image_b64, 80)
        if result and result.get("found"):
            self.tap(result["x"], result["y"])
            return True
        return False

    def find_close_button(self, image_b64=None):
        """Find close/X button. Template → YOLO → AI."""
        # Layer 1: Template
        tm = _init_templates()
        if tm:
            result = tm.find_any(
                ["close_btn", "back_btn", "ref_vr_close", "ref_vr_back"],
                screenshot_b64=image_b64 or self.screenshot_b64()
            )
            if result:
                self._tmpl_hits += 1
                return result
        # Layer 2: YOLO
        if YOLO_ENABLED:
            result = self.yolo_find_any(["close_btn", "back_btn"], image_b64)
            if result:
                return result
        # Layer 3: AI
        if image_b64 is None:
            image_b64 = self.screenshot_b64()
        prompt = (
            "Viking Rise (1280x720). Find X/Close button (usually top-right).\n"
            '{"found": true, "x": 1230, "y": 50}\nJSON ONLY.'
        )
        return self.ask_ai(prompt, image_b64, 60)

    # ════════════════════════════════════════════════════
    # NAVIGATION (smart, minimal API usage)
    # ════════════════════════════════════════════════════

    def go_to_city(self, max_attempts=15):
        """Navigate back to city. YOLO-first, smart popup handling."""
        last_screen = None
        same_screen_count = 0

        for attempt in range(max_attempts):
            img = self.screenshot_b64()
            r = self.detect_screen(img, force=True)

            if not r:
                print("  [nav] detect failed, trying back")
                self.adb_back()
                time.sleep(2)
                continue

            s = r.get("screen", "unknown")
            print(f"  [nav] attempt {attempt+1}: {s}")

            # === SUCCESS ===
            if s == "city":
                self._nav_fails = 0
                return True

            # === STUCK DETECTION ===
            if s == last_screen:
                same_screen_count += 1
            else:
                same_screen_count = 0
                last_screen = s

            if same_screen_count >= 3:
                print(f"  [nav] STUCK on {s} ({same_screen_count}x)")
                if s == "world_map":
                    print("  [nav] Trying home button positions...")
                    # Try hybrid first, then fallback positions
                    home = self.hybrid_find_button("go")
                    if home and home.get("found"):
                        self.tap(home["x"], home["y"])
                        time.sleep(2)
                        check = self.detect_screen(force=True)
                        if check and check.get("screen") == "city":
                            self._nav_fails = 0
                            return True
                    for hx, hy in self._NAV_HOME_ALTS:
                        self.tap(hx, hy, jitter=False)
                        time.sleep(2)
                        check = self.detect_screen(force=True)
                        if check and check.get("screen") == "city":
                            self._nav_fails = 0
                            return True
                    self.adb_back()
                    time.sleep(1)
                elif s == "exit_popup":
                    self.adb_back()
                    time.sleep(1.5)
                    self.tap(640, 360, jitter=False)  # center dismiss
                    time.sleep(1)
                else:
                    # Try YOLO close button before back
                    close = self.yolo_find_any(["close_btn", "back_btn", "confirm_btn"])
                    if close:
                        self.tap(close["x"], close["y"])
                    else:
                        self.adb_back()
                    time.sleep(2)
                same_screen_count = 0
                continue

            # === SCREEN HANDLERS ===

            if s == "exit_popup":
                self.adb_back()
                time.sleep(1.5)

            elif s in ("speedup_popup", "resource_popup"):
                self.adb_back()
                time.sleep(1.5)

            elif s == "world_map":
                print("  [nav] Tapping home button (world_botn)...")
                self._tap_nav("go", self._NAV_HOME_BTN,
                              "Find the Home/City button on bottom-left toolbar")
                time.sleep(2)

            elif s in ("action_menu", "popup", "encounter",
                       "niflung_encounter", "obtainable_resources",
                       "outdoor_meet", "war_screen"):
                # Try YOLO close/ok/back first, then adb_back
                close = self.yolo_find_any(["close_btn", "back_btn", "cancel_btn"])
                if close:
                    self.tap(close["x"], close["y"])
                else:
                    self.adb_back()
                time.sleep(1.5)

            elif s == "shop":
                self.adb_back()
                time.sleep(2)

            elif s in ("profile", "alliance_screen", "event_screen",
                       "mail_screen", "hero_screen", "inventory",
                       "settings", "chat", "divination", "commission",
                       "clan_camp", "dragon", "infirmary",
                       "smithy_screen", "summon", "prosperity_screen",
                       "mercenary"):
                self.adb_back()
                time.sleep(2)

            elif s in ("training", "building_info", "queue_screen",
                       "research_screen", "march_screen"):
                self.adb_back()
                time.sleep(2)

            else:
                # Unknown: alternate back and center-tap
                if attempt % 2 == 0:
                    self.adb_back()
                else:
                    self.tap(640, 360, jitter=False)
                time.sleep(2)

        self._nav_fails += 1
        print(f"  [nav] FAILED after {max_attempts} attempts (fails: {self._nav_fails})")
        return False

    def close_popup(self):
        """Close any popup. Template → YOLO → AI."""
        # Layer 1: Template (free, instant)
        tm = _init_templates()
        if tm:
            result = tm.find_any(
                ["close_btn", "back_btn", "ref_vr_close", "ok_btn", "confirm_btn"],
                screenshot_b64=self.screenshot_b64()
            )
            if result:
                self._tmpl_hits += 1
                self.tap(result["x"], result["y"])
                time.sleep(1.5)
                return True
        # Layer 2: YOLO (free)
        if YOLO_ENABLED:
            close = self.yolo_find_any(["close_btn", "back_btn"])
            if close:
                self.tap(close["x"], close["y"])
                time.sleep(1.5)
                return True
        # Layer 3: AI (paid)
        img = self.screenshot_b64()
        close = self.find_close_button(img)
        if close and close.get("found"):
            self.tap(close["x"], close["y"])
            time.sleep(1.5)
            return True
        return False

    # ════════════════════════════════════════════════════
    # ANTI-BAN
    # ════════════════════════════════════════════════════

    def random_delay(self, min_s=None, max_s=None):
        if min_s is None: min_s = TAP_DELAY_MIN
        if max_s is None: max_s = TAP_DELAY_MAX
        time.sleep(random.uniform(min_s, max_s))

    def task_delay(self):
        time.sleep(random.uniform(TASK_DELAY_MIN, TASK_DELAY_MAX))

    def check_session_break(self):
        elapsed = (time.time() - self._session_start) / 60
        if elapsed >= SESSION_BREAK_INTERVAL:
            print(f"\n  [anti-ban] Session break ({SESSION_BREAK_DURATION}s)...")
            time.sleep(SESSION_BREAK_DURATION)
            self._session_start = time.time()

    # ════════════════════════════════════════════════════
    # UTILITY
    # ════════════════════════════════════════════════════

    def wait(self, seconds):
        time.sleep(seconds + random.uniform(0, 0.5))

    def is_on_screen(self, screen_type):
        r = self.detect_screen()
        return r and r.get("screen") == screen_type

    def print_stats(self):
        print(f"\n  [stats] AI calls: {self._ai_calls}")
        print(f"  [stats] Template hits: {self._tmpl_hits} (free, instant)")
        print(f"  [stats] YOLO hits: {self._yolo_hits} (free)")
        print(f"  [stats] API calls: {self._api_calls} (paid)")
        print(f"  [stats] Nav failures: {self._nav_fails}")
        saved = self._tmpl_hits + self._yolo_hits
        total = saved + self._api_calls
        if total > 0:
            pct = (saved / total) * 100
            print(f"  [stats] Cost saved: {pct:.0f}% by Template+YOLO")
        tm = _init_templates()
        if tm:
            tm.print_stats()
