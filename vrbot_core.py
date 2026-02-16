"""
VRBOT Core Engine — AI Vision
Shared by ALL task modules.

Usage:
    from vrbot_core import Bot
    bot = Bot()
    bot.tap(500, 300)
    screen = bot.detect_screen()
    result = bot.ask_ai("find the barracks", bot.screenshot_b64())
    bot.go_to_city()
"""
import subprocess, os, sys, time, json, base64, re, random

from vrbot_config import (
    ADB_EXE, ADB_DEVICE, CLAUDE_MODEL, DEBUG_DIR,
    TAP_DELAY_MIN, TAP_DELAY_MAX, COORDINATE_JITTER,
    TASK_DELAY_MIN, TASK_DELAY_MAX,
    SESSION_BREAK_INTERVAL, SESSION_BREAK_DURATION,
)

# --- Anthropic Client ---
try:
    import anthropic
    _client = anthropic.Anthropic()
except ImportError:
    print("ERROR: pip install anthropic"); sys.exit(1)
except Exception as e:
    print("ERROR:", e); sys.exit(1)


class Bot:
    """Main bot engine — ADB + AI Vision."""

    def __init__(self):
        os.makedirs(DEBUG_DIR, exist_ok=True)
        self._shot_counter = 0
        self._session_start = time.time()
        self._last_tap_time = 0

    # ═══════════════════════════════════════════════
    # ADB
    # ═══════════════════════════════════════════════

    def _adb(self, *args):
        cmd = [ADB_EXE, "-s", ADB_DEVICE] + list(args)
        return subprocess.run(cmd, capture_output=True, timeout=15)

    def tap(self, x, y, jitter=True):
        """Tap with optional coordinate jitter and human-like delay."""
        # Anti-ban: random delay since last tap
        elapsed = time.time() - self._last_tap_time
        min_wait = TAP_DELAY_MIN
        if elapsed < min_wait:
            time.sleep(min_wait - elapsed + random.uniform(0, 0.3))

        # Jitter
        if jitter and COORDINATE_JITTER > 0:
            x += random.randint(-COORDINATE_JITTER, COORDINATE_JITTER)
            y += random.randint(-COORDINATE_JITTER, COORDINATE_JITTER)
        x, y = max(0, min(1279, x)), max(0, min(719, y))

        self._adb("shell", "input", "tap", str(x), str(y))
        self._last_tap_time = time.time()
        print(f"    tap ({x},{y})")

    def swipe(self, x1, y1, x2, y2, duration=None):
        """Swipe with random duration for human-like behavior."""
        if duration is None:
            duration = random.randint(300, 700)
        self._adb("shell", "input", "swipe",
                   str(x1), str(y1), str(x2), str(y2), str(duration))
        print(f"    swipe ({x1},{y1})->({x2},{y2}) {duration}ms")

    def screenshot(self, name=None):
        """Take screenshot, save to debug dir, return file path."""
        if name is None:
            self._shot_counter += 1
            name = f"shot_{self._shot_counter:04d}"
        path = os.path.join(DEBUG_DIR, name + ".png")
        self._adb("shell", "screencap", "-p", "/sdcard/vrbot_screen.png")
        self._adb("pull", "/sdcard/vrbot_screen.png", path)
        return path

    def screenshot_b64(self, name=None):
        """Take screenshot and return as base64."""
        path = self.screenshot(name)
        with open(path, "rb") as f:
            return base64.standard_b64encode(f.read()).decode("utf-8")

    # ═══════════════════════════════════════════════
    # AI VISION
    # ═══════════════════════════════════════════════

    @staticmethod
    def _extract_json(text):
        """Robust JSON extraction from Claude response."""
        # Direct parse
        try:
            return json.loads(text.strip())
        except:
            pass
        # Code blocks
        for pat in [r'```json\s*(.*?)\s*```', r'```\s*(.*?)\s*```']:
            m = re.search(pat, text, re.DOTALL)
            if m:
                try:
                    return json.loads(m.group(1).strip())
                except:
                    pass
        # Find { ... } in text
        start = text.find('{')
        if start >= 0:
            depth = 0
            for i in range(start, len(text)):
                if text[i] == '{': depth += 1
                elif text[i] == '}': depth -= 1
                if depth == 0:
                    try:
                        return json.loads(text[start:i+1])
                    except:
                        break
        return None

    def ask_ai(self, prompt, image_b64=None, max_tokens=300):
        """Send prompt (with optional image) to Claude, return parsed JSON."""
        content = []
        if image_b64:
            content.append({
                "type": "image",
                "source": {"type": "base64", "media_type": "image/png", "data": image_b64}
            })
        content.append({"type": "text", "text": prompt})

        try:
            resp = _client.messages.create(
                model=CLAUDE_MODEL,
                max_tokens=max_tokens,
                messages=[{"role": "user", "content": content}],
            )
            text = resp.content[0].text
            result = self._extract_json(text)
            if result is None:
                print(f"  [AI] No JSON: {text[:120]}")
            return result
        except Exception as e:
            print(f"  [AI] Error: {e}")
            return None

    def ask_ai_text(self, prompt, image_b64=None, max_tokens=500):
        """Send prompt to Claude, return raw text (no JSON parsing)."""
        content = []
        if image_b64:
            content.append({
                "type": "image",
                "source": {"type": "base64", "media_type": "image/png", "data": image_b64}
            })
        content.append({"type": "text", "text": prompt})

        try:
            resp = _client.messages.create(
                model=CLAUDE_MODEL,
                max_tokens=max_tokens,
                messages=[{"role": "user", "content": content}],
            )
            return resp.content[0].text
        except Exception as e:
            print(f"  [AI] Error: {e}")
            return None

    # ═══════════════════════════════════════════════
    # SCREEN DETECTION
    # ═══════════════════════════════════════════════

    SCREEN_TYPES = (
        "city, training, action_menu, resource_popup, exit_popup, "
        "speedup_popup, queue_screen, building_info, profile, "
        "world_map, march_screen, research_screen, mail_screen, "
        "inventory, hero_screen, alliance_screen, event_screen, "
        "settings, chat, shop, unknown"
    )

    def detect_screen(self, image_b64=None):
        """Detect current screen type. Returns dict with 'screen' and 'details'."""
        if image_b64 is None:
            image_b64 = self.screenshot_b64()
        prompt = (
            "Viking Rise game screenshot (1280x720). What screen is this?\n"
            '{"screen": "city", "details": "main city view"}\n'
            "Reply ONLY JSON like above. Screen types: " + self.SCREEN_TYPES
        )
        return self.ask_ai(prompt, image_b64, 150)

    def find_and_tap(self, description, image_b64=None):
        """Ask AI to find something on screen and tap it.
        Returns True if found and tapped."""
        if image_b64 is None:
            image_b64 = self.screenshot_b64()
        prompt = (
            f"Viking Rise (1280x720). Find: {description}\n"
            '{"found": true, "x": 640, "y": 360}\n'
            "Reply ONLY JSON like above."
        )
        result = self.ask_ai(prompt, image_b64, 80)
        if result and result.get("found"):
            self.tap(result["x"], result["y"])
            return True
        return False

    def find_close_button(self, image_b64=None):
        """Find Cancel/Close/X button on current screen."""
        if image_b64 is None:
            image_b64 = self.screenshot_b64()
        prompt = (
            "Viking Rise screenshot (1280x720). Find the X or Close button.\n"
            "Look in top-right corner for X, or bottom for Cancel.\n"
            '{"found": true, "x": 1240, "y": 40}\n'
            "Reply with ONLY a JSON like above. No explanation."
        )
        return self.ask_ai(prompt, image_b64, 80)

    # ═══════════════════════════════════════════════
    # NAVIGATION
    # ═══════════════════════════════════════════════

    def go_to_city(self, max_attempts=8):
        """Navigate back to city view safely. No adb_back ever."""
        # Fallback X positions to try (top-right corners, common close spots)
        CLOSE_FALLBACKS = [(1245, 35), (1240, 45), (1220, 30), (1250, 50)]

        for attempt in range(max_attempts):
            img = self.screenshot_b64()
            r = self.detect_screen(img)
            if not r:
                self.tap(50, 50, jitter=False)
                time.sleep(2)
                continue

            s = r.get("screen", "unknown")
            print(f"  [nav] {s}")

            if s == "city":
                return True

            if s in ("exit_popup", "speedup_popup", "resource_popup"):
                close = self.find_close_button(img)
                if close and close.get("found"):
                    self.tap(close["x"], close["y"])
                else:
                    self.tap(350, 480, jitter=False)
                time.sleep(2)

            elif s == "world_map":
                # Tap city/home button — usually bottom center or minimap
                found = self.find_and_tap(
                    "the city/home button to return to my base (NOT alliance/tribe buttons)", img
                )
                if not found:
                    self.tap(640, 680, jitter=False)  # bottom center
                time.sleep(2)

            elif s in ("profile", "training", "building_info",
                       "queue_screen", "research_screen", "mail_screen",
                       "inventory", "hero_screen", "alliance_screen",
                       "event_screen", "settings", "shop", "chat"):
                # Try AI first, then cycle through fallback positions
                close = self.find_close_button(img)
                if close and close.get("found"):
                    self.tap(close["x"], close["y"])
                else:
                    fb = CLOSE_FALLBACKS[attempt % len(CLOSE_FALLBACKS)]
                    print(f"  [nav] Fallback close: {fb}")
                    self.tap(fb[0], fb[1], jitter=False)
                time.sleep(2)

            elif s == "action_menu":
                self.tap(50, 50, jitter=False)
                time.sleep(1.5)

            else:
                self.tap(50, 50, jitter=False)
                time.sleep(2)

        return False

    def close_popup(self):
        """Try to close whatever popup is on screen."""
        img = self.screenshot_b64()
        close = self.find_close_button(img)
        if close and close.get("found"):
            self.tap(close["x"], close["y"])
            time.sleep(1.5)
            return True
        return False

    # ═══════════════════════════════════════════════
    # ANTI-BAN
    # ═══════════════════════════════════════════════

    def random_delay(self, min_s=None, max_s=None):
        """Human-like random delay."""
        if min_s is None: min_s = TAP_DELAY_MIN
        if max_s is None: max_s = TAP_DELAY_MAX
        time.sleep(random.uniform(min_s, max_s))

    def task_delay(self):
        """Delay between tasks."""
        time.sleep(random.uniform(TASK_DELAY_MIN, TASK_DELAY_MAX))

    def check_session_break(self):
        """Take a break if session has been running too long."""
        elapsed = (time.time() - self._session_start) / 60
        if elapsed >= SESSION_BREAK_INTERVAL:
            print(f"\n  [anti-ban] Session break ({SESSION_BREAK_DURATION}s)...")
            time.sleep(SESSION_BREAK_DURATION)
            self._session_start = time.time()

    # ═══════════════════════════════════════════════
    # UTILITY
    # ═══════════════════════════════════════════════

    def wait(self, seconds):
        """Wait with slight randomization."""
        time.sleep(seconds + random.uniform(0, 0.5))

    def is_on_screen(self, screen_type):
        """Quick check if we're on a specific screen."""
        r = self.detect_screen()
        return r and r.get("screen") == screen_type
