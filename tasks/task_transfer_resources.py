"""Task: Transfer Resources — نقل الموارد بين المزارع
=====================================================
Transfers resources from the current farm to a target castle.

Flow:
  1. Go to world map
  2. Find the target castle (ally) nearby
  3. Tap target castle → "Transfer" / "نقل الموارد"
  4. Select resource type & amount
  5. Send march
  6. Repeat for remaining resource types

Prerequisites:
  - Target castle MUST be in the same alliance
  - Target castle MUST be nearby (within march range)
  - Farm must have resources to send

Config (passed via bot.config):
  transfer_target_name:  str  — Target castle name to search for (e.g. "Ahmed")
  transfer_resources:    list — Resources to send: ["food", "wood", "stone", "gold"]
  transfer_amount:       str  — "all" or "half" or specific number
  transfer_max_marches:  int  — Max marches to send (default 1)
"""

import random
import time
from tasks.base_task import BaseTask

# ── Fallback coordinates (1280x720 resolution) ──
FALLBACK = {
    "world_map_btn": (1230, 640),    # World map button from city
    "transfer_btn": (640, 520),      # Transfer/Help button in castle popup
    "send_btn": (960, 615),          # Send/March button
    "max_btn": (850, 400),           # Max amount button
    "confirm_btn": (640, 550),       # Confirm button
    "close_btn": (1240, 60),         # Close popup X
}

# Resource tab positions in transfer panel (approximate)
RESOURCE_TABS = {
    "food":  (300, 350),
    "wood":  (480, 350),
    "stone": (660, 350),
    "gold":  (840, 350),
}

# Amount slider/input positions
AMOUNT_POSITIONS = {
    "slider_start": (350, 450),
    "slider_end":   (930, 450),
    "slider_max":   (930, 450),      # Drag to max
    "slider_half":  (640, 450),      # Drag to middle
}


class TaskTransferResources(BaseTask):
    name = "Transfer Resources"
    tag = "transfer_resources"
    cooldown_hours = 0  # No cooldown — manual trigger

    def __init__(self, bot):
        super().__init__(bot)
        self.marches_sent = 0
        self.total_transferred = {}

    def _get_config(self):
        """Read transfer config from bot.config."""
        cfg = getattr(self.bot, 'config', {}) or {}
        return {
            "target_name": cfg.get("transfer_target_name", ""),
            "resources": cfg.get("transfer_resources", ["food", "wood", "stone", "gold"]),
            "amount": cfg.get("transfer_amount", "all"),
            "max_marches": cfg.get("transfer_max_marches", 1),
        }

    def _ensure_world_map(self):
        """Navigate to world map reliably."""
        bot = self.bot
        bot.go_to_city()
        bot.wait(2)
        if bot.go_to_world_map():
            return True
        # Retry
        bot.go_to_city()
        bot.wait(2)
        return bot.go_to_world_map()

    def _find_target_castle(self, target_name):
        """Find the target castle on the world map.

        The target castle should already be nearby (user moved farms close).
        Uses AI vision to locate the castle by name.
        """
        bot = self.bot

        # Search nearby area — try current view first, then scan around
        search_patterns = [
            None,                          # Current view
            "left",                        # Swipe left
            "right",                       # Swipe right (back + further)
            "up",                          # Swipe up
            "down",                        # Swipe down
        ]

        for i, direction in enumerate(search_patterns):
            if direction:
                self._swipe_ui(direction)
                self._human_wait(1.5, 2.5)

            self.log.info(f"Scanning for target castle (attempt {i + 1})...")
            img = bot.screenshot_b64()
            result = bot.ask_ai(
                f"Viking Rise world map (1280x720). "
                f"Find a castle/city belonging to a player named '{target_name}' or "
                f"any allied castle (green nameplate) nearby. "
                f"Look for castle icon with name text above it. "
                '{"found": true, "x": 640, "y": 360} or {"found": false}. JSON ONLY.',
                img, 100
            )
            if result and result.get("found"):
                self.log.info(f"Found target castle at ({result['x']}, {result['y']})")
                return result

        return None

    def _tap_castle_and_open_transfer(self):
        """Tap on the target castle and find the Transfer option."""
        bot = self.bot

        # After tapping castle, a popup should appear with options
        self._human_wait(2, 3)

        # Look for "Transfer" / "نقل" / "Help" option
        found = self._find_and_tap(
            "In the castle popup menu, find the 'Transfer' or 'نقل الموارد' or "
            "'Send Resources' or 'Help' button. It might show a truck/cart icon.",
            wait_after=3, retries=2
        )
        if found:
            self.log.info("Transfer menu opened")
            return True

        # Fallback: try tapping common position
        self.log.info("Trying fallback transfer button position...")
        self._tap_ui(None, fallback_xy=FALLBACK["transfer_btn"], wait_after=3)

        # Verify we're in transfer screen
        img = bot.screenshot_b64()
        result = bot.ask_ai(
            "Viking Rise (1280x720). Am I on a resource transfer screen? "
            "Look for resource icons (food/wood/stone/gold), amount slider, "
            "and send/march button. "
            '{"found": true, "screen": "transfer"} or {"found": false}. JSON ONLY.',
            img, 60
        )
        return result and result.get("found", False)

    def _select_resource_and_amount(self, resource, amount):
        """Select a resource type and set the transfer amount."""
        bot = self.bot

        # Step 1: Tap the resource tab
        if resource in RESOURCE_TABS:
            rx, ry = RESOURCE_TABS[resource]
            self.log.info(f"Selecting resource: {resource}")

            # Try AI detection first
            found = self._find_and_tap(
                f"Find the '{resource}' tab or icon in the resource transfer panel. "
                f"Food=grain/wheat icon, Wood=log icon, Stone=rock icon, Gold=coin icon.",
                wait_after=2, retries=1
            )
            if not found:
                self._tap_ui(None, fallback_xy=(rx, ry), wait_after=2, jitter=True)

            self._human_wait(1, 2)

        # Step 2: Set amount
        if amount == "all" or amount == "max":
            # Try to find and tap "Max" button
            found = self._find_and_tap(
                "Find the 'Max' or 'أقصى' or maximum amount button in the transfer panel.",
                wait_after=2, retries=1
            )
            if not found:
                # Drag slider to max
                self.log.info("Dragging slider to max...")
                sx, sy = AMOUNT_POSITIONS["slider_start"]
                ex, ey = AMOUNT_POSITIONS["slider_max"]
                bot.swipe(sx, sy, ex, ey, duration=random.randint(400, 700))
                bot.wait(2)
        elif amount == "half":
            # Drag slider to middle
            sx, sy = AMOUNT_POSITIONS["slider_start"]
            ex, ey = AMOUNT_POSITIONS["slider_half"]
            bot.swipe(sx, sy, ex, ey, duration=random.randint(400, 700))
            bot.wait(2)

        self._human_wait(1, 2)
        return True

    def _send_march(self):
        """Tap the Send/March button to dispatch the transfer."""
        bot = self.bot

        # Try hybrid detection
        found = self._tap_button("march", wait_after=3)
        if found:
            return True

        # Try AI
        found = self._find_and_tap(
            "Find the 'March' or 'Send' or 'إرسال' or 'مسيرة' button. "
            "Usually at the bottom of the screen, large green/orange button.",
            wait_after=3, retries=2
        )
        if found:
            return True

        # Fallback
        self._tap_ui(None, fallback_xy=FALLBACK["send_btn"], wait_after=3)
        return True

    def _transfer_one_resource(self, resource, target_name, amount):
        """Complete flow: find castle → open transfer → select → send."""
        bot = self.bot

        # Step 1: Ensure we're on world map
        if not self._ensure_world_map():
            self.log.error("Cannot reach world map")
            return False

        self._human_wait(2, 4)

        # Step 2: Find the target castle
        target = self._find_target_castle(target_name)
        if not target:
            self.log.warning(f"Target castle '{target_name}' not found on map")
            return False

        # Step 3: Tap on the castle
        bot.tap(target["x"], target["y"])
        self._human_wait(2, 3)

        # Step 4: Open transfer menu
        if not self._tap_castle_and_open_transfer():
            self.log.warning("Could not open transfer menu")
            bot.adb_back()
            bot.wait(2)
            return False

        # Step 5: Select resource and amount
        self._select_resource_and_amount(resource, amount)

        # Step 6: Send march
        self.log.info(f"Sending {resource} ({amount})...")
        self._send_march()

        # Step 7: Verify — check screen state
        self._human_wait(3, 5)
        s = bot.detect_screen()
        screen = s.get("screen", "").lower() if s else ""

        if "world" in screen or "city" in screen:
            self.marches_sent += 1
            self.total_transferred[resource] = self.total_transferred.get(resource, 0) + 1
            self.log.info(f"✔ {resource} transfer sent! (total marches: {self.marches_sent})")
            return True
        else:
            # Try to dismiss any popup and go back
            self.log.warning(f"Transfer might have failed (screen: {screen})")
            self._dismiss_popup()
            bot.adb_back()
            bot.wait(2)
            return False

    def run(self):
        """Main transfer flow."""
        cfg = self._get_config()
        target_name = cfg["target_name"]
        resources = cfg["resources"]
        amount = cfg["amount"]
        max_marches = cfg["max_marches"]

        if not target_name:
            self.log.error("No transfer_target_name configured! Set it in bot config.")
            return False

        self.log.info("╔══════════════════════════════════════╗")
        self.log.info("║  Resource Transfer Started            ║")
        self.log.info(f"║  Target: {target_name:<29}║")
        self.log.info(f"║  Resources: {', '.join(resources):<26}║")
        self.log.info(f"║  Amount: {amount:<29}║")
        self.log.info(f"║  Max marches: {max_marches:<24}║")
        self.log.info("╚══════════════════════════════════════╝")

        self._set_state("running")

        for resource in resources:
            if self.marches_sent >= max_marches:
                self.log.info(f"Max marches ({max_marches}) reached. Stopping.")
                break

            self.log.info(f"\n── Transferring {resource} ──")

            success = self._transfer_one_resource(resource, target_name, amount)
            if not success:
                self.log.warning(f"Failed to transfer {resource}, continuing...")

            # Wait between transfers (anti-detection)
            if resource != resources[-1]:
                wait = random.uniform(8, 15)
                self.log.info(f"Waiting {wait:.0f}s before next transfer...")
                self.bot.wait(wait)

        # Return to city
        self.bot.go_to_city()

        self.log.info("\n╔══════════════════════════════════════╗")
        self.log.info("║  Resource Transfer Complete           ║")
        self.log.info(f"║  Marches sent: {self.marches_sent:<23}║")
        for res, count in self.total_transferred.items():
            self.log.info(f"║  {res}: {count} transfer(s){' '*(20-len(res))}║")
        self.log.info("╚══════════════════════════════════════╝")

        self._set_state("completed")
        return True
