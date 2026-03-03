"""
VRBOT Core Engine - Hybrid YOLO (ONNX) + AI Vision
Priority: YOLO ONNX (free, local) -> GPT-4o mini (cheap) -> Claude (fallback)

Usage:
    from vrbot_core import Bot
    bot = Bot()
    bot.tap(500, 300)
    screen = bot.detect_screen()
"""
import subprocess, os, sys, time, json, base64, re, random, io
import numpy as np
from PIL import Image

from vrbot_config import (
    ADB_EXE, ADB_DEVICE, DEBUG_DIR,
    TAP_DELAY_MIN, TAP_DELAY_MAX, COORDINATE_JITTER,
    TASK_DELAY_MIN, TASK_DELAY_MAX,
    SESSION_BREAK_INTERVAL, SESSION_BREAK_DURATION,
    AI_PROVIDER, OPENAI_MODEL, CLAUDE_MODEL,
    YOLO_ENABLED, YOLO_MODEL_PATH, YOLO_CONFIDENCE,
)

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

    # Find ONNX model
    onnx_path = YOLO_MODEL_PATH.replace(".pt", ".onnx")
    if not os.path.exists(onnx_path):
        print(f"  [init] ONNX model not found: {onnx_path}")
        return None

    try:
        import onnxruntime as ort
        _onnx_session = ort.InferenceSession(onnx_path, providers=["CPUExecutionProvider"])

        # Load class labels from metadata
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


class Bot:
    """Main bot engine - YOLO + GPT-4o mini + Claude hybrid."""

    def __init__(self):
        os.makedirs(DEBUG_DIR, exist_ok=True)
        self._shot_counter = 0
        self._session_start = time.time()
        self._last_tap_time = 0
        self._ai_calls = 0
        self._yolo_hits = 0
        self._api_calls = 0
        self._nav_fails = 0
        _init_yolo()

    # ================================================
    # ADB
    # ================================================

    def _adb(self, *args):
        cmd = [ADB_EXE, "-s", ADB_DEVICE] + list(args)
        return subprocess.run(cmd, capture_output=True, timeout=15)

    def tap(self, x, y, jitter=True):
        elapsed = time.time() - self._last_tap_time
        min_wait = TAP_DELAY_MIN
        if elapsed < min_wait:
            time.sleep(min_wait - elapsed + random.uniform(0, 0.3))
        if jitter and COORDINATE_JITTER > 0:
            x += random.randint(-COORDINATE_JITTER, COORDINATE_JITTER)
            y += random.randint(-COORDINATE_JITTER, COORDINATE_JITTER)
        x, y = max(0, min(1279, x)), max(0, min(719, y))
        self._adb("shell", "input", "swipe", str(x), str(y), str(x), str(y), "50")
        self._last_tap_time = time.time()
        print(f"    tap ({x},{y})")

    def swipe(self, x1, y1, x2, y2, duration=None):
        if duration is None:
            duration = random.randint(300, 700)
        self._adb("shell", "input", "swipe",
                   str(x1), str(y1), str(x2), str(y2), str(duration))
        print(f"    swipe ({x1},{y1})->({x2},{y2}) {duration}ms")

    def adb_back(self):
        """Press Android back button."""
        self._adb("shell", "input", "keyevent", "4")
        print("    [adb] back")

    def dismiss_chat(self):
        """Brief pause before tapping toolbar buttons."""
        time.sleep(0.3)

    def is_world_map(self, image_b64=None):
        """Check if on world map. Uses AI for accuracy (YOLO unreliable here)."""
        if image_b64 is None:
            image_b64 = self.screenshot_b64()
        result = self.ask_ai(
            "Viking Rise (1280x720). Is this the WORLD MAP or the CITY?\n"
            "WORLD MAP = open terrain/grass, other player castles, "
            "coordinate bar '#30 X:390 Y:808' at top, magnifying glass icons on left.\n"
            "CITY = your OWN base with buildings inside walls, construction bubbles, "
            "toolbar icons at bottom-right (sword, shield, helm).\n"
            '{"screen": "world_map"} or {"screen": "city"}\nReply ONLY JSON.',
            image_b64, 60
        )
        if result:
            return result.get("screen") == "world_map"
        return False

    def go_to_world_map(self, max_attempts=3):
        """Navigate to world map. Tap button then verify."""
        # First check if already on world map
        if self.is_world_map():
            print("  [world] Already on world map")
            return True

        # Tap world map button and verify
        for attempt in range(max_attempts):
            print(f"  [world] Tapping world map button (attempt {attempt+1})...")
            self.tap(47, 643, jitter=False)
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
            self._adb("pull", "/sdcard/vrbot_debug.png", path)
            print(f"  [debug] Saved: {path}")
        except:
            pass

    def screenshot(self, name=None):
        if name is None:
            self._shot_counter += 1
            name = f"shot_{self._shot_counter:04d}"
        path = os.path.join(DEBUG_DIR, name + ".png")
        self._adb("shell", "screencap", "-p", "/sdcard/vrbot_screen.png")
        self._adb("pull", "/sdcard/vrbot_screen.png", path)
        return path

    def screenshot_b64(self, name=None):
        path = self.screenshot(name)
        with open(path, "rb") as f:
            return base64.standard_b64encode(f.read()).decode("utf-8")

    # ================================================
    # YOLO ONNX DETECTION (FREE - LOCAL, NO PYTORCH)
    # ================================================

    def _preprocess_image(self, image_path, input_size=720):
        """Preprocess image for ONNX YOLO inference."""
        img = Image.open(image_path).convert("RGB")
        orig_w, orig_h = img.size

        # Resize to square with letterbox
        scale = min(input_size / orig_w, input_size / orig_h)
        new_w, new_h = int(orig_w * scale), int(orig_h * scale)
        img_resized = img.resize((new_w, new_h), Image.BILINEAR)

        # Pad to square
        canvas = Image.new("RGB", (input_size, input_size), (114, 114, 114))
        pad_x = (input_size - new_w) // 2
        pad_y = (input_size - new_h) // 2
        canvas.paste(img_resized, (pad_x, pad_y))

        # Normalize to [0, 1] and convert to NCHW float32
        arr = np.array(canvas, dtype=np.float32) / 255.0
        arr = arr.transpose(2, 0, 1)  # HWC -> CHW
        arr = np.expand_dims(arr, 0)  # Add batch dim

        return arr, orig_w, orig_h, scale, pad_x, pad_y

    def yolo_detect(self, image_path=None, image_b64=None):
        """Run YOLO ONNX on screenshot. Returns list of detections."""
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
            # Get input size from model
            input_shape = session.get_inputs()[0].shape
            input_size = input_shape[2] if len(input_shape) >= 3 else 720

            arr, orig_w, orig_h, scale, pad_x, pad_y = self._preprocess_image(image_path, input_size)

            # Run inference
            input_name = session.get_inputs()[0].name
            outputs = session.run(None, {input_name: arr})
            preds = outputs[0]  # Shape: [1, num_classes+4, num_boxes] or [1, num_boxes, num_classes+4]

            # Parse predictions (YOLOv8 format: [1, 4+nc, N] -> transpose to [N, 4+nc])
            if preds.shape[1] < preds.shape[2]:
                preds = preds[0].T  # [N, 4+nc]
            else:
                preds = preds[0]

            detections = []
            for pred in preds:
                # First 4 values = cx, cy, w, h (center format)
                cx, cy, w, h = pred[:4]
                class_scores = pred[4:]
                cls_id = int(np.argmax(class_scores))
                conf = float(class_scores[cls_id])

                if conf < YOLO_CONFIDENCE:
                    continue

                # Convert from letterbox coords to original image coords
                x1 = (cx - w / 2 - pad_x) / scale
                y1 = (cy - h / 2 - pad_y) / scale
                x2 = (cx + w / 2 - pad_x) / scale
                y2 = (cy + h / 2 - pad_y) / scale

                # Clamp to image bounds
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

            if detections:
                self._yolo_hits += 1

            return sorted(detections, key=lambda d: -d["confidence"])

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
        """Find any of the given classes."""
        detections = self.yolo_detect(image_b64=image_b64)
        for d in detections:
            for name in class_names:
                if name.lower() in d["class"] or d["class"] in name.lower():
                    print(f"  [yolo] Found {d['class']} ({d['confidence']}) at ({d['x']}, {d['y']})")
                    return {"found": True, "x": d["x"], "y": d["y"], "class": d["class"]}
        return None

    def yolo_detect_screen(self, image_path=None):
        """Try to guess screen type from YOLO detections (FREE)."""
        detections = self.yolo_detect(image_path=image_path)
        if not detections:
            return None

        classes = [d["class"] for d in detections]
        classes_str = " ".join(classes)

        # Heuristics based on what YOLO detects
        # These keywords depend on your trained YOLO model classes
        if any(k in classes_str for k in ["resource_bar", "toolbar", "build_btn"]):
            return {"screen": "city", "details": "yolo: city elements detected"}
        if any(k in classes_str for k in ["compass", "magnify", "world"]):
            return {"screen": "world_map", "details": "yolo: map elements detected"}
        if any(k in classes_str for k in ["mail", "inbox"]):
            return {"screen": "mail_screen", "details": "yolo: mail detected"}
        if any(k in classes_str for k in ["alliance", "tribe", "guild"]):
            return {"screen": "alliance_screen", "details": "yolo: alliance detected"}

        return None

    # ================================================
    # AI VISION (API - paid)
    # ================================================

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
            print(f"  [claude] Error: {e}")
            return None

    def ask_ai(self, prompt, image_b64=None, max_tokens=300):
        self._ai_calls += 1
        if AI_PROVIDER == "openai":
            result = self._ask_openai(prompt, image_b64, max_tokens)
            if result is None:
                result = self._ask_anthropic(prompt, image_b64, max_tokens)
            return result
        else:
            result = self._ask_anthropic(prompt, image_b64, max_tokens)
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

    # ================================================
    # HYBRID DETECTION (YOLO first, then API)
    # ================================================

    def hybrid_find(self, yolo_classes, ai_prompt, image_b64=None):
        if image_b64 is None:
            image_b64 = self.screenshot_b64()
        if YOLO_ENABLED and yolo_classes:
            result = self.yolo_find_any(yolo_classes, image_b64)
            if result:
                return result
        return self.ask_ai(ai_prompt, image_b64)

    def hybrid_find_button(self, button_type, image_b64=None):
        BUTTON_MAP = {
            "claim": (["claim", "collect", "claim_all"],
                'Find green Claim/Collect button. JSON ONLY: {"found": true, "x": 640, "y": 500} or {"found": false}'),
            "close": (["close", "x_button", "back"],
                'Find X/Close button. JSON ONLY: {"found": true, "x": 1230, "y": 50} or {"found": false}'),
            "confirm": (["confirm", "ok", "yes"],
                'Find Confirm/OK/Yes button. JSON ONLY: {"found": true, "x": 640, "y": 400} or {"found": false}'),
            "upgrade": (["upgrade", "build"],
                'Find Upgrade/Build button. JSON ONLY: {"found": true, "x": 640, "y": 500} or {"found": false}'),
            "attack": (["attack", "march"],
                'Find Attack/March button. JSON ONLY: {"found": true, "x": 640, "y": 500} or {"found": false}'),
            "gather": (["gather"],
                'Find Gather button. JSON ONLY: {"found": true, "x": 640, "y": 500} or {"found": false}'),
            "help_all": (["help_all", "assist"],
                'Find Help All/Assist All button. JSON ONLY: {"found": true, "x": 640, "y": 500} or {"found": false}'),
            "train": (["train", "recruit"],
                'Find Train/Recruit button. JSON ONLY: {"found": true, "x": 640, "y": 500} or {"found": false}'),
            "use": (["use", "activate"],
                'Find Use/Activate button. JSON ONLY: {"found": true, "x": 640, "y": 500} or {"found": false}'),
        }
        if button_type not in BUTTON_MAP:
            return None
        yolo_classes, ai_prompt = BUTTON_MAP[button_type]
        return self.hybrid_find(yolo_classes, ai_prompt, image_b64)

    # ================================================
    # SCREEN DETECTION (YOLO first → API fallback)
    # ================================================

    def detect_screen(self, image_b64=None):
        """Detect screen type. YOLO first (free), then API."""
        # Step 1: Try YOLO (FREE)
        if YOLO_ENABLED:
            yolo_result = self.yolo_detect_screen()
            if yolo_result:
                print(f"  [yolo] Screen: {yolo_result['screen']}")
                return yolo_result

        # Step 2: Fall back to API (PAID)
        if image_b64 is None:
            image_b64 = self.screenshot_b64()
        prompt = (
            "Viking Rise game screenshot (1280x720). Identify screen type.\n"
            "Pick from this list ONLY:\n"
            "city, training, action_menu, resource_popup, exit_popup, "
            "speedup_popup, queue_screen, building_info, profile, "
            "world_map, march_screen, research_screen, mail_screen, "
            "inventory, hero_screen, alliance_screen, event_screen, "
            "settings, chat, shop, unknown\n\n"
            "CRITICAL RULES:\n"
            "- city = BUILDINGS visible (houses, towers, walls) + BOTTOM TOOLBAR with small icons + "
            "resource bar (food/wood/stone/gold) at top.\n"
            "- world_map = TERRAIN (grass, forests, mountains, fog) with resource tiles, "
            "monster camps, other cities. NO building toolbar. Compass/magnify on left.\n"
            "- If you see buildings with toolbar at bottom = city (NOT world_map).\n"
            '{"screen": "city", "details": "main city with buildings"}\n'
            "Reply ONLY JSON."
        )
        result = self.ask_ai(prompt, image_b64, 150)
        if result:
            result = self._normalize_screen(result)
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
        # YOLO first
        if YOLO_ENABLED:
            result = self.yolo_find_any(["close", "x_button", "back"], image_b64)
            if result:
                return result
        if image_b64 is None:
            image_b64 = self.screenshot_b64()
        prompt = (
            "Viking Rise (1280x720). Find X/Close button.\n"
            '{"found": true, "x": 1240, "y": 40}\n'
            "Reply ONLY JSON."
        )
        return self.ask_ai(prompt, image_b64, 80)

    # ================================================
    # NAVIGATION (FIXED COORDS - minimal API usage)
    # ================================================

    def go_to_city(self, max_attempts=15):
        """
        Navigate back to city. Uses FIXED COORDINATES to minimize API calls.
        Only calls detect_screen (API) when needed.
        """
        last_screen = None
        same_screen_count = 0

        for attempt in range(max_attempts):
            img = self.screenshot_b64()
            r = self.detect_screen(img)

            if not r:
                print("  [nav] detect failed, trying back")
                self.adb_back()
                time.sleep(2)
                continue

            s = r.get("screen", "unknown")
            print(f"  [nav] {s}")

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
                    for hx, hy in [(72, 636), (97, 654), (47, 643), (60, 654)]:
                        self.tap(hx, hy, jitter=False)
                        time.sleep(2)
                        check = self.detect_screen()
                        if check and check.get("screen") == "city":
                            self._nav_fails = 0
                            return True
                    self.adb_back()
                    time.sleep(1)
                elif s == "exit_popup":
                    # Press Back to dismiss, then tap outside
                    self._adb("shell", "input", "keyevent", "4")
                    time.sleep(1.5)
                    self.tap(640, 360, jitter=False)
                    time.sleep(1)
                else:
                    self.adb_back()
                    time.sleep(2)
                same_screen_count = 0
                continue

            # === SCREEN HANDLERS (FIXED COORDS - NO API) ===

            if s == "exit_popup":
                # Just press Back to dismiss exit dialog
                self._adb("shell", "input", "keyevent", "4")
                time.sleep(1.5)

            elif s in ("speedup_popup", "resource_popup"):
                self.tap(50, 50, jitter=False)
                time.sleep(1.5)

            elif s == "world_map":
                # Home button = bottom-left (same as world map toggle)
                print("  [nav] Tapping home button...")
                self.tap(72, 636, jitter=False)
                time.sleep(2)

            elif s == "action_menu":
                self.tap(50, 50, jitter=False)
                time.sleep(1.5)

            elif s == "profile":
                if attempt % 2 == 0:
                    self.tap(33, 25, jitter=False)
                else:
                    self.adb_back()
                time.sleep(2)

            elif s == "shop":
                self.adb_back()
                time.sleep(2)

            elif s in ("alliance_screen", "event_screen", "mail_screen",
                       "hero_screen", "inventory", "settings", "chat"):
                if attempt % 2 == 0:
                    self.tap(33, 25, jitter=False)
                else:
                    self.adb_back()
                time.sleep(2)

            elif s in ("training", "building_info", "queue_screen",
                       "research_screen", "march_screen"):
                self.adb_back()
                time.sleep(2)

            else:
                if attempt % 2 == 0:
                    self.tap(50, 50, jitter=False)
                else:
                    self.adb_back()
                time.sleep(2)

        self._nav_fails += 1
        print(f"  [nav] FAILED after {max_attempts} attempts (fails: {self._nav_fails})")
        return False

    def close_popup(self):
        img = self.screenshot_b64()
        close = self.find_close_button(img)
        if close and close.get("found"):
            self.tap(close["x"], close["y"])
            time.sleep(1.5)
            return True
        return False

    # ================================================
    # ANTI-BAN
    # ================================================

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

    # ================================================
    # UTILITY
    # ================================================

    def wait(self, seconds):
        time.sleep(seconds + random.uniform(0, 0.5))

    def is_on_screen(self, screen_type):
        r = self.detect_screen()
        return r and r.get("screen") == screen_type

    def print_stats(self):
        print(f"\n  [stats] AI calls: {self._ai_calls}")
        print(f"  [stats] YOLO hits: {self._yolo_hits} (free)")
        print(f"  [stats] API calls: {self._api_calls} (paid)")
        print(f"  [stats] Nav failures: {self._nav_fails}")
        saved = self._yolo_hits
        total = self._yolo_hits + self._api_calls
        if total > 0:
            pct = (saved / total) * 100
            print(f"  [stats] Cost saved: {pct:.0f}% by YOLO")
