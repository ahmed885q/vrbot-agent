"""Task: Transfer Resources — نقل الموارد بين المزارع (Supply Feature)
=====================================================================
Transfers resources from the current farm to a target castle using
Viking Rise's "Supply" (تموين) feature.

Two Methods Supported:
  METHOD A — Tribe Hall Supply (preferred):
    1. Go to city → open Tribe Hall building
    2. Tap "Supply" / "تموين" tab
    3. Select target ally from the list (or search by name)
    4. Select resource type & amount
    5. Send supply march
    6. Repeat for remaining resource types

  METHOD B — World Map Direct (fallback):
    1. Go to world map
    2. Find the target castle (ally) nearby
    3. Tap target castle → "Supply" / "تموين"
    4. Select resource type & amount
    5. Send supply march

Prerequisites:
  - Tribe Hall MUST be level 14+ (required for Supply feature)
  - Target castle MUST be in the same Tribe (alliance)
  - Target castle MUST be nearby (within march range)
  - Farm must have resources to send
  - 32% resource tax applies (e.g., sending 100k → target receives ~68k)

Config (passed via bot.config):
  transfer_target_name:  str  — Target castle name to search for (e.g. "Ahmed")
  transfer_resources:    list — Resources to send: ["food", "wood", "stone", "gold"]
  transfer_amount:       str  — "all" or "half" or specific number
  transfer_max_marches:  int  — Max marches to send (default 1)
  transfer_method:       str  — "tribe_hall" (default) or "world_map"
"""

import random
import time
from tasks.base_task import BaseTask

# ── Fallback coordinates (1280x720 resolution) ──
FALLBACK = {
    # City UI
    "world_map_btn": (1230, 640),    # World map button from city
    # Tribe Hall Supply screen
    "tribe_hall":    (640, 360),      # Tribe Hall building (center city area)
    "supply_tab":    (400, 100),      # Supply tab inside Tribe Hall
    "search_ally":   (1100, 160),     # Search button in ally list
    "first_ally":    (640, 300),      # First ally in supply list
    # Transfer panel
    "transfer_btn":  (640, 520),      # Supply button in castle popup (world map)
    "send_btn":      (960, 615),      # Send/March button
    "max_btn":       (850, 400),      # Max amount button
    "confirm_btn":   (640, 550),      # Confirm button
    "close_btn":     (1240, 60),      # Close popup X
}

# Resource tab positions in transfer/supply panel (approximate)
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

# Tax rate for resource supply in Viking Rise
SUPPLY_TAX_RATE = 0.32  # 32% tax


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
            "method": cfg.get("transfer_method", "tribe_hall"),
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

    # ══════════════════════════════════════════════
    #  METHOD A: Tribe Hall Supply (preferred)
    # ══════════════════════════════════════════════

    def _open_tribe_hall(self):
        """Find and open the Tribe Hall building in city view."""
        bot = self.bot
        bot.go_to_city()
        self._human_wait(2, 3)

        # Try AI vision to find Tribe Hall
        found = self._find_and_tap(
            "Find the 'Tribe Hall' or 'قاعة القبيلة' building in the city. "
            "It's usually a large decorated building, might have tribal/Viking "
            "decorations. It could also be called 'Alliance Hall'.",
            wait_after=4, retries=2
        )
        if found:
            self.log.info("Tribe Hall opened via AI detection")
            return True

        # Fallback: tap center area where Tribe Hall typically is
        self.log.info("Trying fallback Tribe Hall position...")
        self._tap_ui(None, fallback_xy=FALLBACK["tribe_hall"], wait_after=4)

        # Verify we opened a building menu
        img = bot.screenshot_b64()
        result = bot.ask_ai(
            "Viking Rise (1280x720). Am I inside a building menu? "
            "Look for building name at top, tabs/options, upgrade button. "
            '{"found": true, "building": "tribe_hall"} or {"found": false}. JSON ONLY.',
            img, 60
        )
        return result and result.get("found", False)

    def _navigate_to_supply_tab(self):
        """Inside Tribe Hall, find and tap the Supply tab."""
        bot = self.bot

        # Look for Supply/تموين tab
        found = self._find_and_tap(
            "Inside the Tribe Hall menu, find the 'Supply' or 'تموين' or "
            "'Resource Supply' tab/button. It might show a cart/truck icon "
            "or resource transfer icon. Check tabs at the top of the menu.",
            wait_after=3, retries=2
        )
        if found:
            self.log.info("Supply tab found")
            return True

        # Fallback
        self._tap_ui(None, fallback_xy=FALLBACK["supply_tab"], wait_after=3)

        # Verify
        img = bot.screenshot_b64()
        result = bot.ask_ai(
            "Viking Rise (1280x720). Am I on a Supply/resource transfer screen? "
            "Look for: list of tribe members/allies, resource icons, "
            "send/supply button, or ally search. "
            '{"found": true} or {"found": false}. JSON ONLY.',
            img, 60
        )
        return result and result.get("found", False)

    def _select_target_from_list(self, target_name):
        """In the Supply screen, find and select the target ally."""
        bot = self.bot

        # First try: look for the target name directly on screen
        found = self._find_and_tap(
            f"In the ally/tribe member list, find the player named '{target_name}'. "
            f"Tap on their name or avatar. Look for text matching '{target_name}'.",
            wait_after=3, retries=1
        )
        if found:
            self.log.info(f"Found target '{target_name}' in list")
            return True

        # Scroll down to find more allies
        self.log.info("Scrolling ally list to find target...")
        for scroll_attempt in range(3):
            self._swipe_ui("up", duration=random.randint(400, 700))
            self._human_wait(1.5, 2.5)

            found = self._find_and_tap(
                f"Find player named '{target_name}' in the list. "
                f"Tap on their name/row.",
                wait_after=3, retries=1
            )
            if found:
                self.log.info(f"Found target '{target_name}' after scrolling")
                return True

        # Try search functionality if available
        self.log.info("Trying search for target ally...")
        search_found = self._find_and_tap(
            "Find a search icon or search bar in the supply/ally screen. "
            "It might be a magnifying glass icon at the top.",
            wait_after=2, retries=1
        )
        if search_found:
            self._human_wait(1, 2)
            # Type the target name
            bot.type_text(target_name)
            self._human_wait(2, 3)
            # Tap the first result
            self._find_and_tap(
                f"Find and tap the search result for '{target_name}'.",
                wait_after=3, retries=1
            )
            return True

        self.log.warning(f"Could not find '{target_name}' in Supply list")
        return False

    def _supply_via_tribe_hall(self, resource, target_name, amount):
        """Transfer resources using Tribe Hall → Supply method."""
        bot = self.bot

        # Step 1: Open Tribe Hall
        if not self._open_tribe_hall():
            self.log.warning("Could not open Tribe Hall")
            return False

        self._human_wait(1.5, 3)

        # Step 2: Navigate to Supply tab
        if not self._navigate_to_supply_tab():
            self.log.warning("Could not find Supply tab — Tribe Hall may be < level 14")
            self._safe_close()
            return False

        self._human_wait(1.5, 3)

        # Step 3: Select target ally
        if not self._select_target_from_list(target_name):
            self.log.warning(f"Target '{target_name}' not found in Supply list")
            self._safe_close()
            return False

        self._human_wait(1.5, 3)

        # Step 4: Select resource and amount
        self._select_resource_and_amount(resource, amount)

        # Step 5: Send
        self.log.info(f"Sending {resource} supply ({amount}) — 32% tax applies...")
        self._send_march()

        # Step 6: Verify
        self._human_wait(3, 5)
        s = bot.detect_screen()
        screen = s.get("screen", "").lower() if s else ""

        if any(k in screen for k in ("tribe", "supply", "city", "world")):
            self.marches_sent += 1
            self.total_transferred[resource] = self.total_transferred.get(resource, 0) + 1
            self.log.info(f"✔ {resource} supply sent! (total: {self.marches_sent})")
            return True
        else:
            self.log.warning(f"Supply might have failed (screen: {screen})")
            self._dismiss_popup()
            bot.adb_back()
            bot.wait(2)
            return False

    # ══════════════════════════════════════════════
    #  METHOD B: World Map Direct (fallback)
    # ══════════════════════════════════════════════

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

    def _tap_castle_and_open_supply(self):
        """Tap on the target castle and find the Supply option."""
        bot = self.bot

        # After tapping castle, a popup should appear with options
        self._human_wait(2, 3)

        # Look for "Supply" / "تموين" option (updated from old "Transfer")
        found = self._find_and_tap(
            "In the castle popup menu, find the 'Supply' or 'تموين' or "
            "'Send Resources' or 'Transfer' or 'نقل الموارد' button. "
            "It might show a cart/truck icon or resource icon.",
            wait_after=3, retries=2
        )
        if found:
            self.log.info("Supply menu opened from world map")
            return True

        # Fallback: try tapping common position
        self.log.info("Trying fallback supply button position...")
        self._tap_ui(None, fallback_xy=FALLBACK["transfer_btn"], wait_after=3)

        # Verify we're in supply/transfer screen
        img = bot.screenshot_b64()
        result = bot.ask_ai(
            "Viking Rise (1280x720). Am I on a resource supply/transfer screen? "
            "Look for resource icons (food/wood/stone/gold), amount slider, "
            "and send/march button. "
            '{"found": true, "screen": "supply"} or {"found": false}. JSON ONLY.',
            img, 60
        )
        return result and result.get("found", False)

    def _supply_via_world_map(self, resource, target_name, amount):
        """Transfer resources using world map → castle tap → Supply."""
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

        # Step 4: Open supply menu
        if not self._tap_castle_and_open_supply():
            self.log.warning("Could not open supply menu")
            bot.adb_back()
            bot.wait(2)
            return False

        # Step 5: Select resource and amount
        self._select_resource_and_amount(resource, amount)

        # Step 6: Send march
        self.log.info(f"Sending {resource} supply ({amount}) — 32% tax applies...")
        self._send_march()

        # Step 7: Verify — check screen state
        self._human_wait(3, 5)
        s = bot.detect_screen()
        screen = s.get("screen", "").lower() if s else ""

        if "world" in screen or "city" in screen:
            self.marches_sent += 1
            self.total_transferred[resource] = self.total_transferred.get(resource, 0) + 1
            self.log.info(f"✔ {resource} supply sent! (total marches: {self.marches_sent})")
            return True
        else:
            # Try to dismiss any popup and go back
            self.log.warning(f"Supply might have failed (screen: {screen})")
            self._dismiss_popup()
            bot.adb_back()
            bot.wait(2)
            return False

    # ══════════════════════════════════════════════
    #  Shared helpers
    # ══════════════════════════════════════════════

    def _select_resource_and_amount(self, resource, amount):
        """Select a resource type and set the supply amount."""
        bot = self.bot

        # Step 1: Tap the resource tab
        if resource in RESOURCE_TABS:
            rx, ry = RESOURCE_TABS[resource]
            self.log.info(f"Selecting resource: {resource}")

            # Try AI detection first
            found = self._find_and_tap(
                f"Find the '{resource}' tab or icon in the resource supply/transfer panel. "
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
                "Find the 'Max' or 'أقصى' or maximum amount button in the supply panel.",
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
        """Tap the Send/March button to dispatch the supply."""
        bot = self.bot

        # Try hybrid detection
        found = self._tap_button("march", wait_after=3)
        if found:
            return True

        # Try AI — look for Supply/Send/March
        found = self._find_and_tap(
            "Find the 'March' or 'Send' or 'Supply' or 'تموين' or "
            "'إرسال' or 'مسيرة' button. "
            "Usually at the bottom of the screen, large green/orange button.",
            wait_after=3, retries=2
        )
        if found:
            return True

        # Fallback
        self._tap_ui(None, fallback_xy=FALLBACK["send_btn"], wait_after=3)
        return True

    def _transfer_one_resource(self, resource, target_name, amount, method):
        """Route to the appropriate transfer method."""
        if method == "tribe_hall":
            success = self._supply_via_tribe_hall(resource, target_name, amount)
            if not success:
                # Fallback to world map method
                self.log.info("Tribe Hall method failed, trying world map fallback...")
                success = self._supply_via_world_map(resource, target_name, amount)
            return success
        else:
            return self._supply_via_world_map(resource, target_name, amount)

    # ══════════════════════════════════════════════
    #  Main entry point
    # ══════════════════════════════════════════════

    def run(self):
        """Main transfer flow."""
        cfg = self._get_config()
        target_name = cfg["target_name"]
        resources = cfg["resources"]
        amount = cfg["amount"]
        max_marches = cfg["max_marches"]
        method = cfg["method"]

        if not target_name:
            self.log.error("No transfer_target_name configured! Set it in bot config.")
            return False

        self.log.info("╔══════════════════════════════════════╗")
        self.log.info("║  Resource Supply Started              ║")
        self.log.info(f"║  Target: {target_name:<29}║")
        self.log.info(f"║  Resources: {', '.join(resources):<26}║")
        self.log.info(f"║  Amount: {amount:<29}║")
        self.log.info(f"║  Method: {method:<29}║")
        self.log.info(f"║  Max marches: {max_marches:<24}║")
        self.log.info(f"║  Tax rate: {SUPPLY_TAX_RATE*100:.0f}%{' '*24}║")
        self.log.info("╚══════════════════════════════════════╝")

        self._set_state("running")

        for resource in resources:
            if self.marches_sent >= max_marches:
                self.log.info(f"Max marches ({max_marches}) reached. Stopping.")
                break

            self.log.info(f"\n── Supplying {resource} ──")

            success = self._transfer_one_resource(resource, target_name, amount, method)
            if not success:
                self.log.warning(f"Failed to supply {resource}, continuing...")

            # Wait between transfers (anti-detection)
            if resource != resources[-1]:
                wait = random.uniform(8, 15)
                self.log.info(f"Waiting {wait:.0f}s before next supply...")
                self.bot.wait(wait)

        # Return to city
        self.bot.go_to_city()

        self.log.info("\n╔══════════════════════════════════════╗")
        self.log.info("║  Resource Supply Complete             ║")
        self.log.info(f"║  Marches sent: {self.marches_sent:<23}║")
        for res, count in self.total_transferred.items():
            self.log.info(f"║  {res}: {count} supply(s){' '*(21-len(res))}║")
        if self.total_transferred:
            self.log.info(f"║  Note: 32% tax deducted on arrival   ║")
        self.log.info("╚══════════════════════════════════════╝")

        self._set_state("completed")
        return True
