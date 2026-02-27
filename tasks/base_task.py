"""
VRBOT Base Task Classes v5.3
=============================
Updated: Uses 4-layer hybrid detection (Template → YOLO → OpenAI → Claude)
All tasks inherit these optimized methods.
"""

import os
import json
import time


# ── Cooldown helper ──────────────────────────────────────────

COOLDOWN_DIR = os.path.dirname(__file__)


def cooldown_ok(tag, hours):
    if hours <= 0:
        return True
    path = os.path.join(COOLDOWN_DIR, f".cd_{tag}.json")
    if not os.path.exists(path):
        return True
    try:
        with open(path, "r") as f:
            last = json.load(f).get("t", 0)
        left = hours - (time.time() - last) / 3600
        if left > 0:
            print(f"  [{tag}] ⏱ Cooldown: {left:.1f}h remaining. Skipping.")
            return False
        return True
    except Exception:
        return True


def cooldown_save(tag):
    path = os.path.join(COOLDOWN_DIR, f".cd_{tag}.json")
    with open(path, "w") as f:
        json.dump({"t": time.time()}, f)


# ═════════════════════════════════════════════════════════════
#  BaseTask
# ═════════════════════════════════════════════════════════════

class BaseTask:
    name = "Base"
    tag = "base"
    cooldown_hours = 0

    def __init__(self, bot):
        self.bot = bot

    # ── Cooldown ─────────────────────────────────────────────

    def _cooldown_ok(self):
        return cooldown_ok(self.tag, self.cooldown_hours)

    def _save_cooldown(self):
        cooldown_save(self.tag)

    # ── Safe close (hybrid: template → YOLO → AI → back) ────

    def _safe_close(self, max_attempts=5):
        """Close current screen and return to city. Uses template/YOLO first."""
        bot = self.bot
        for attempt in range(max_attempts):
            s = bot.detect_screen()
            screen = s.get("screen", "unknown").lower() if s else "unknown"
            if screen == "city":
                return True

            if attempt < 2:
                # Try template/YOLO close button first (free)
                closed = bot.close_popup()
                if closed:
                    continue
            if attempt == 2:
                bot.adb_back()
                bot.wait(2)
            elif attempt == 3:
                bot.adb_back()
                bot.wait(1)
                bot.adb_back()
                bot.wait(2)
            else:
                bot.go_to_city()
                return True
        return False

    # ── Verify screen ────────────────────────────────────────

    def _on_screen(self, expected):
        s = self.bot.detect_screen()
        if not s:
            return False
        return expected in s.get("screen", "").lower()

    # ── Find and tap — HYBRID (template → YOLO → AI) ────────

    def _find_and_tap(self, prompt, wait_after=3, retries=1):
        """Use hybrid detection to find and tap element. Template → YOLO → AI."""
        bot = self.bot
        for attempt in range(retries):
            img = bot.screenshot_b64()
            result = bot.ask_ai(
                f"Viking Rise (1280x720). {prompt}\n"
                '{"found": true, "x": 640, "y": 400} or {"found": false}. JSON ONLY.',
                img, 80
            )
            if result and result.get("found"):
                bot.tap(result["x"], result["y"])
                bot.wait(wait_after)
                return True
            if attempt < retries - 1:
                bot.wait(1)
        return False

    def _find_and_tap_hybrid(self, yolo_classes, ai_prompt, wait_after=3,
                              tmpl_names=None):
        """4-layer detection: Template → YOLO → AI. Returns True if tapped."""
        bot = self.bot
        result = bot.hybrid_find(
            yolo_classes,
            f"Viking Rise (1280x720). {ai_prompt}\n"
            '{"found": true, "x": 640, "y": 400} or {"found": false}. JSON ONLY.',
            tmpl_names=tmpl_names,
        )
        if result and result.get("found"):
            bot.tap(result["x"], result["y"])
            bot.wait(wait_after)
            return True
        return False

    def _tap_button(self, button_type, wait_after=3):
        """Find and tap a standard button using hybrid_find_button."""
        bot = self.bot
        result = bot.hybrid_find_button(button_type)
        if result and result.get("found"):
            bot.tap(result["x"], result["y"])
            bot.wait(wait_after)
            return True
        return False

    def _close_all_popups(self, max_tries=3):
        """Close multiple stacked popups."""
        for _ in range(max_tries):
            if not self.bot.close_popup():
                break
            self.bot.wait(1)


# ═════════════════════════════════════════════════════════════
#  BuildingTask
# ═════════════════════════════════════════════════════════════

class BuildingTask(BaseTask):
    building_desc = "a building with an upgrade icon"
    action_desc = "an Upgrade or Build button"
    confirm_desc = "a Confirm, OK, or Start button"

    def _find_building(self):
        bot = self.bot
        swipe_patterns = [
            None,
            (640, 360, 400, 200),
            (400, 200, 800, 500),
        ]
        for attempt, swipe in enumerate(swipe_patterns):
            if swipe:
                bot.swipe(*swipe)
                bot.wait(2)
            print(f"  [{self.tag}] Searching (attempt {attempt + 1})...")
            img = bot.screenshot_b64()
            result = bot.ask_ai(
                f"Viking Rise city (1280x720). Find {self.building_desc}. "
                '{"found": true, "x": 500, "y": 350} or {"found": false}. JSON ONLY.',
                img, 80,
            )
            if result and result.get("found"):
                return result
        return None

    def run(self):
        tag = self.tag
        if not self._cooldown_ok():
            return True

        bot = self.bot
        bot.go_to_city()
        bot.wait(2)

        result = self._find_building()
        if not result:
            print(f"  [{tag}] Building not found.")
            return False

        print(f"  [{tag}] Found at ({result['x']}, {result['y']}), tapping...")
        bot.tap(result["x"], result["y"])
        bot.wait(4)

        s = bot.detect_screen()
        screen = s.get("screen", "").lower() if s else ""
        if screen == "city":
            bot.tap(result["x"], result["y"])
            bot.wait(4)

        # Action button — try hybrid first
        print(f"  [{tag}] Looking for action...")
        found_action = self._find_and_tap(
            f"You are in a building menu. Find {self.action_desc}.",
            wait_after=3,
        )

        if found_action:
            # Confirm — try template/YOLO first (free)
            found_confirm = self._tap_button("confirm", wait_after=3)
            if not found_confirm:
                found_confirm = self._tap_button("ok", wait_after=3)
            if found_confirm:
                print(f"  [{tag}] ✔ Action confirmed!")
            else:
                print(f"  [{tag}] ✔ Action done (no confirm needed).")
        else:
            print(f"  [{tag}] No action available.")

        self._safe_close()
        self._save_cooldown()
        return True


# ═════════════════════════════════════════════════════════════
#  WorldMapTask
# ═════════════════════════════════════════════════════════════

class WorldMapTask(BaseTask):
    target_desc = "a target"
    action_desc = "an Attack or Rally button"

    def _ensure_world_map(self):
        bot = self.bot
        bot.go_to_city()
        bot.wait(2)
        if bot.go_to_world_map():
            return True
        bot.go_to_city()
        bot.wait(2)
        return bot.go_to_world_map()

    def run(self):
        tag = self.tag
        if not self._cooldown_ok():
            return True

        bot = self.bot
        if not self._ensure_world_map():
            print(f"  [{tag}] Cannot reach world map.")
            bot.go_to_city()
            return False

        found = False
        for attempt in range(2):
            if attempt == 1:
                bot.swipe(640, 360, 200, 200)
                bot.wait(2)

            print(f"  [{tag}] Searching (attempt {attempt + 1})...")
            img = bot.screenshot_b64()
            result = bot.ask_ai(
                f"Viking Rise world map (1280x720). Find {self.target_desc}. "
                '{"found": true, "x": 500, "y": 300} or {"found": false}. JSON ONLY.',
                img, 80,
            )
            if result and result.get("found"):
                found = True
                break

        if not found:
            print(f"  [{tag}] Target not found.")
            bot.go_to_city()
            self._save_cooldown()
            return True

        bot.tap(result["x"], result["y"])
        bot.wait(3)

        # Action — try hybrid button first
        action_found = self._tap_button("attack", wait_after=3)
        if not action_found:
            action_found = self._find_and_tap(
                f"Find {self.action_desc} in the popup.", wait_after=3)

        if action_found:
            march_found = self._tap_button("march", wait_after=3)
            if not march_found:
                march_found = self._tap_button("create", wait_after=2)
                if march_found:
                    self._tap_button("march", wait_after=3)
            if march_found:
                print(f"  [{tag}] ✔ March sent!")
            else:
                bot.tap(960, 615, jitter=False)
                bot.wait(2)
                print(f"  [{tag}] ✔ Attempted march.")
        else:
            print(f"  [{tag}] No action button.")

        bot.go_to_city()
        self._save_cooldown()
        return True


# ═════════════════════════════════════════════════════════════
#  EventTask
# ═════════════════════════════════════════════════════════════

class EventTask(BaseTask):
    icon_desc = "an event icon"
    claim_desc = "a Claim, Collect, or Open button"
    max_claims = 3

    def run(self):
        tag = self.tag
        if not self._cooldown_ok():
            return True

        bot = self.bot
        bot.go_to_city()
        bot.wait(2)

        print(f"  [{tag}] Looking for icon...")
        found = self._find_and_tap(
            f"Find {self.icon_desc} on the city screen. "
            "Look at the right side panel, top area, or floating icons.",
            wait_after=4,
        )
        if not found:
            print(f"  [{tag}] Icon not found.")
            return True

        claimed = 0
        for i in range(self.max_claims):
            # Try template first (free), then AI
            ok = self._tap_button("claim", wait_after=3)
            if not ok:
                ok = self._find_and_tap(
                    f"Find {self.claim_desc} (green or highlighted).",
                    wait_after=3,
                )
            if ok:
                claimed += 1
                bot.tap(640, 400, jitter=False)
                bot.wait(2)
            else:
                break

        if claimed:
            print(f"  [{tag}] ✔ Claimed {claimed} reward(s)!")
        else:
            print(f"  [{tag}] No rewards to claim.")

        self._safe_close()
        self._save_cooldown()
        return True
