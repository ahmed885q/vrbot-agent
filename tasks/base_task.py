"""
VRBOT Base Task Classes
=======================
Shared utilities for all tasks: cooldown, safe_close, verification.

Classes:
    BaseTask      — cooldown + safe_close + verify helpers
    BuildingTask  — find building in city → action → confirm → close
    WorldMapTask  — go to world map → find target → action → march
    EventTask     — find event icon in city → claim rewards
"""

import os
import json
import time


# ── Cooldown helper (standalone, works without inheritance) ──────────

COOLDOWN_DIR = os.path.dirname(__file__)


def cooldown_ok(tag, hours):
    """Return True if enough time has passed since last run."""
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


# ══════════════════════════════════════════════════════════════════════
#  BaseTask
# ══════════════════════════════════════════════════════════════════════

class BaseTask:
    name = "Base"
    tag = "base"
    cooldown_hours = 0  # 0 = no cooldown

    def __init__(self, bot):
        self.bot = bot

    # ── Cooldown ─────────────────────────────────────────────────────

    def _cooldown_ok(self):
        return cooldown_ok(self.tag, self.cooldown_hours)

    def _save_cooldown(self):
        cooldown_save(self.tag)

    # ── Safe close (reliable return to city) ─────────────────────────

    def _safe_close(self, max_attempts=4):
        """Try multiple strategies to close current screen and return to city."""
        bot = self.bot
        for attempt in range(max_attempts):
            s = bot.detect_screen()
            screen = s.get("screen", "unknown").lower() if s else "unknown"
            if screen == "city":
                return True

            if attempt == 0:
                # Try X button at common positions
                bot.tap(35, 25, jitter=False)
                bot.wait(2)
            elif attempt == 1:
                bot.adb_back()
                bot.wait(2)
            elif attempt == 2:
                bot.adb_back()
                bot.wait(1)
                bot.adb_back()
                bot.wait(2)
            else:
                bot.go_to_city()
                return True
        return False

    # ── Verify screen ────────────────────────────────────────────────

    def _on_screen(self, expected):
        """Quick screen check without burning API calls unnecessarily."""
        s = self.bot.detect_screen()
        if not s:
            return False
        return expected in s.get("screen", "").lower()

    # ── Find and tap with retry ──────────────────────────────────────

    def _find_and_tap(self, prompt, wait_after=3, retries=1):
        """Use AI to locate element, tap it, return True if found."""
        bot = self.bot
        for attempt in range(retries):
            img = bot.screenshot_b64()
            result = bot.ask_ai(
                f"Viking Rise (1280x720). {prompt}\n"
                'Respond ONLY JSON: {"found": true, "x": 640, "y": 400} '
                'or {"found": false}',
                img, 80
            )
            if result and result.get("found"):
                bot.tap(result["x"], result["y"])
                bot.wait(wait_after)
                return True
            if attempt < retries - 1:
                bot.wait(1)
        return False

    def _find_and_tap_hybrid(self, yolo_classes, ai_prompt, wait_after=3):
        """Try YOLO first, then AI. Returns True if found and tapped."""
        bot = self.bot
        result = bot.hybrid_find(
            yolo_classes,
            f"Viking Rise (1280x720). {ai_prompt}\n"
            '{"found": true, "x": 640, "y": 400} or {"found": false}\nJSON ONLY.',
        )
        if result and result.get("found"):
            bot.tap(result["x"], result["y"])
            bot.wait(wait_after)
            return True
        return False


# ══════════════════════════════════════════════════════════════════════
#  BuildingTask — find building in city → action → confirm
# ══════════════════════════════════════════════════════════════════════

class BuildingTask(BaseTask):
    """
    Override these in subclass:
        building_desc  — what to tell AI to look for
        action_desc    — what button to press inside building
        confirm_desc   — optional confirm button description
    """
    building_desc = "a building with an upgrade icon"
    action_desc = "an Upgrade or Build button"
    confirm_desc = "a Confirm, OK, or Start button"

    def _find_building(self):
        """Search city for the building, swiping to look around."""
        bot = self.bot
        swipe_patterns = [
            None,                          # attempt 0: no swipe
            (640, 360, 400, 200),          # attempt 1: swipe up-left
            (400, 200, 800, 500),          # attempt 2: swipe down-right
        ]
        for attempt, swipe in enumerate(swipe_patterns):
            if swipe:
                bot.swipe(*swipe)
                bot.wait(2)
            print(f"  [{self.tag}] Searching (attempt {attempt + 1})...")
            img = bot.screenshot_b64()
            result = bot.ask_ai(
                f"Viking Rise city (1280x720). Find {self.building_desc}. "
                "Look for buildings, icons, or bubbles. "
                '{"found": true, "x": 500, "y": 350} or {"found": false}\n'
                "Respond ONLY JSON.",
                img, 80,
            )
            if result and result.get("found"):
                return result
        return None

    def run(self):
        tag = self.tag
        if not self._cooldown_ok():
            return True  # cooldown active, skip gracefully

        bot = self.bot
        bot.go_to_city()
        bot.wait(2)

        # Step 1: Find building
        result = self._find_building()
        if not result:
            print(f"  [{tag}] Building not found.")
            return False

        # Step 2: Tap building
        print(f"  [{tag}] Found at ({result['x']}, {result['y']}), tapping...")
        bot.tap(result["x"], result["y"])
        bot.wait(4)

        # Step 3: Verify we left city (building menu opened)
        s = bot.detect_screen()
        screen = s.get("screen", "").lower() if s else ""
        if screen == "city":
            print(f"  [{tag}] Building didn't open, retrying tap...")
            bot.tap(result["x"], result["y"])
            bot.wait(4)

        # Step 4: Find action button
        print(f"  [{tag}] Looking for action...")
        found_action = self._find_and_tap(
            f"You are in a building menu. Find {self.action_desc}.",
            wait_after=3,
        )

        if found_action:
            # Step 5: Confirm if needed
            found_confirm = self._find_and_tap(
                f"Find {self.confirm_desc} (green or blue button).",
                wait_after=3,
            )
            if found_confirm:
                print(f"  [{tag}] ✔ Action confirmed!")
            else:
                print(f"  [{tag}] ✔ Action done (no confirm needed).")
        else:
            print(f"  [{tag}] No action available.")

        # Step 6: Close and return
        self._safe_close()
        self._save_cooldown()
        return True


# ══════════════════════════════════════════════════════════════════════
#  WorldMapTask — go to world map → find → action → march
# ══════════════════════════════════════════════════════════════════════

class WorldMapTask(BaseTask):
    """
    Override these:
        target_desc  — what to find on world map
        action_desc  — what button after tapping target
    """
    target_desc = "a target"
    action_desc = "an Attack or Rally button"

    def _ensure_world_map(self):
        bot = self.bot
        bot.go_to_city()
        bot.wait(2)
        if bot.go_to_world_map():
            return True
        # Retry
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

        # Find target (try 2 angles)
        found = False
        for attempt in range(2):
            if attempt == 1:
                bot.swipe(640, 360, 200, 200)
                bot.wait(2)

            print(f"  [{tag}] Searching (attempt {attempt + 1})...")
            img = bot.screenshot_b64()
            result = bot.ask_ai(
                f"Viking Rise world map (1280x720). Find {self.target_desc}. "
                '{"found": true, "x": 500, "y": 300} or {"found": false}\n'
                "Respond ONLY JSON.",
                img, 80,
            )
            if result and result.get("found"):
                found = True
                break

        if not found:
            print(f"  [{tag}] Target not found.")
            bot.go_to_city()
            self._save_cooldown()
            return True  # not an error, just nothing to do

        # Tap target
        bot.tap(result["x"], result["y"])
        bot.wait(3)

        # Action button
        action_found = self._find_and_tap(
            f"Find {self.action_desc} in the popup.",
            wait_after=3,
        )
        if action_found:
            # March / confirm
            march_found = self._find_and_tap(
                "Find a March, Send, Create, or Confirm button.",
                wait_after=3,
            )
            if march_found:
                print(f"  [{tag}] ✔ March sent!")
            else:
                # Try fixed march position
                bot.tap(960, 615, jitter=False)
                bot.wait(2)
                print(f"  [{tag}] ✔ Attempted march.")
        else:
            print(f"  [{tag}] No action button.")

        bot.go_to_city()
        self._save_cooldown()
        return True


# ══════════════════════════════════════════════════════════════════════
#  EventTask — find event icon → claim rewards
# ══════════════════════════════════════════════════════════════════════

class EventTask(BaseTask):
    """
    Override:
        icon_desc   — what event icon to find
        claim_desc  — what buttons to press
        max_claims  — how many claim attempts
    """
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

        # Find icon
        print(f"  [{tag}] Looking for icon...")
        found = self._find_and_tap(
            f"Find {self.icon_desc} on the city screen. "
            "Look at the right side panel, top area, or floating icons.",
            wait_after=4,
        )
        if not found:
            print(f"  [{tag}] Icon not found.")
            return True  # event might not be active

        # Claim loop
        claimed = 0
        for i in range(self.max_claims):
            ok = self._find_and_tap(
                f"Find {self.claim_desc} (green or highlighted).",
                wait_after=3,
            )
            if ok:
                claimed += 1
                # Dismiss reward popup
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
