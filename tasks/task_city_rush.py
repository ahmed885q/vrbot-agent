"""
Task: City Rush — Auto-develop city from Level 1 to Level 17.
================================================================
This is a meta-task that orchestrates the full city progression:
  1. Detect current Chief Hall level
  2. Upgrade prerequisite buildings
  3. Upgrade Chief Hall
  4. Use all available speedups
  5. Gather resources if needed
  6. Repeat until Level 17

Viking Rise building requirements per Chief Hall level:
  CH 2:  Any building Lv1
  CH 3:  Wall Lv2
  CH 4:  Wall Lv3, Barracks Lv3
  CH 5:  Wall Lv4, Academy Lv4
  CH 6:  Wall Lv5, Hospital Lv5
  CH 7:  Wall Lv6, Barracks Lv6
  CH 8:  Wall Lv7, Academy Lv7
  CH 9:  Wall Lv8, Storehouse Lv8
  CH 10: Wall Lv9, Barracks Lv9
  CH 11: Wall Lv10, Academy Lv10
  CH 12: Wall Lv11, Hospital Lv11
  CH 13: Wall Lv12, Barracks Lv12
  CH 14: Wall Lv13, Academy Lv13
  CH 15: Wall Lv14, Storehouse Lv14
  CH 16: Wall Lv15, Barracks Lv15
  CH 17: Wall Lv16, Academy Lv16

Usage:
  This task runs as part of the bot task system.
  Enable "city_rush" in your task config.
"""

from tasks.base_task import BaseTask
import time

# ── Fixed coordinates (1280x720) ──
CHIEF_HALL_CENTER = (640, 360)   # Center of city (Chief Hall)
UPGRADE_BTN_AREA = (640, 500)    # Upgrade button typical location
CONFIRM_BTN_AREA = (640, 520)    # Confirm button
SPEEDUP_BTN_AREA = (900, 400)    # Speed up button
USE_BTN_AREA = (640, 480)        # Use speedup item button
MAX_BTN_AREA = (800, 400)        # Max quantity button
INFO_AREA = (640, 200)           # Info/requirements area

# Building search descriptions for AI Vision
BUILDINGS = {
    "chief_hall": (
        "the Chief Hall / Town Center — the main, largest building "
        "in the center of the city"
    ),
    "wall": (
        "the City Wall or Gate — the fortification wall around the city, "
        "usually at the entrance/gate area"
    ),
    "barracks": (
        "the Barracks building — where troops are trained, "
        "has a sword/shield or military icon"
    ),
    "academy": (
        "the Academy or Research building — looks like a library or hall "
        "with a book/scroll icon"
    ),
    "hospital": (
        "the Hospital building — has a medical/cross/healing icon, "
        "where wounded troops recover"
    ),
    "storehouse": (
        "the Storehouse or Warehouse building — where resources are "
        "protected, looks like a storage barn"
    ),
}

# Requirements per Chief Hall level: {ch_level: [(building, required_level), ...]}
CH_REQUIREMENTS = {
    2:  [],
    3:  [("wall", 2)],
    4:  [("wall", 3), ("barracks", 3)],
    5:  [("wall", 4), ("academy", 4)],
    6:  [("wall", 5), ("hospital", 5)],
    7:  [("wall", 6), ("barracks", 6)],
    8:  [("wall", 7), ("academy", 7)],
    9:  [("wall", 8), ("storehouse", 8)],
    10: [("wall", 9), ("barracks", 9)],
    11: [("wall", 10), ("academy", 10)],
    12: [("wall", 11), ("hospital", 11)],
    13: [("wall", 12), ("barracks", 12)],
    14: [("wall", 13), ("academy", 13)],
    15: [("wall", 14), ("storehouse", 14)],
    16: [("wall", 15), ("barracks", 15)],
    17: [("wall", 16), ("academy", 16)],
}


class TaskCityRush(BaseTask):
    name = "City Rush to 17"
    tag = "city_rush"
    cooldown_hours = 0  # Run continuously

    TARGET_LEVEL = 17
    MAX_RETRIES = 3

    # ──────────────────────────────────────────────
    #  DETECT CURRENT CHIEF HALL LEVEL
    # ──────────────────────────────────────────────
    def _detect_ch_level(self):
        """Use AI Vision to detect current Chief Hall level."""
        bot = self.bot
        bot.go_to_city()
        bot.wait(2)

        # Tap Chief Hall
        self._find_and_tap(BUILDINGS["chief_hall"], wait_after=4)

        # Read level from building info panel
        img = bot.screenshot_b64()
        result = bot.ask_ai(
            "Viking Rise building info panel (1280x720). "
            "Read the Chief Hall / Town Center level number. "
            "Look for 'Lv' or 'Level' followed by a number. "
            '{"level": 5} — Respond ONLY with JSON.',
            img, 50,
        )

        self._safe_close()

        if result and isinstance(result.get("level"), (int, float)):
            return int(result["level"])
        return None

    # ──────────────────────────────────────────────
    #  USE ALL SPEEDUPS
    # ──────────────────────────────────────────────
    def _use_all_speedups(self):
        """Find active construction and use all available speedups."""
        bot = self.bot
        bot.go_to_city()
        bot.wait(2)

        # Find building under construction (timer icon)
        found = self._find_and_tap(
            "Find a building that is currently under construction — "
            "it will have a timer, hourglass, or progress bar above it. "
            "Tap the building to open its panel.",
            wait_after=4,
        )
        if not found:
            return False

        # Tap Speed Up button
        ok = self._find_and_tap(
            "Find a 'Speed Up' or 'Boost' button (often blue or green). "
            "It may show a clock/hourglass icon.",
            wait_after=3,
        )
        if not ok:
            return False

        # Try Free speedup first
        self._find_and_tap(
            "Find a 'Free' speed up button or 'Help' button.",
            wait_after=2,
        )

        # Use speedup items (5m, 10m, 30m, 1h, 3h, 8h)
        used = 0
        for _ in range(20):  # Max 20 speedup uses
            ok = self._find_and_tap(
                "Find a 'Use' button next to a construction speed-up item. "
                "Prefer larger speedups (8h > 3h > 1h > 30m > 10m > 5m).",
                wait_after=2,
            )
            if not ok:
                break

            # Try to increase quantity to max
            self._find_and_tap(
                "Find a 'Max' button or '+' button to use maximum quantity.",
                wait_after=1,
            )

            # Confirm use
            self._find_and_tap(
                "Find a green 'Confirm' or 'Use' confirmation button.",
                wait_after=2,
            )
            used += 1

            # Check if construction finished
            img = bot.screenshot_b64()
            check = bot.ask_ai(
                "Viking Rise speedup panel (1280x720). "
                "Is the construction/upgrade already complete? "
                "Look for 'Completed' text or if the timer shows 00:00:00. "
                '{"completed": true} or {"completed": false}',
                img, 50,
            )
            if check and check.get("completed"):
                break

        if used:
            print(f"  [{self.tag}] Used {used} speedup(s)")

        self._safe_close()
        return used > 0

    # ──────────────────────────────────────────────
    #  UPGRADE A BUILDING
    # ──────────────────────────────────────────────
    def _upgrade_building(self, building_key, target_level=None):
        """Find and upgrade a specific building."""
        bot = self.bot
        bot.go_to_city()
        bot.wait(2)

        desc = BUILDINGS.get(building_key, building_key)
        label = building_key.replace("_", " ").title()
        target_str = f" to Lv{target_level}" if target_level else ""

        print(f"  [{self.tag}] Upgrading {label}{target_str}...")

        # Find the building
        found = self._find_and_tap(
            f"Find {desc}. It may have a green upgrade arrow above it.",
            wait_after=4,
        )
        if not found:
            # Swipe around to find it
            bot.swipe(640, 360, 300, 200)
            bot.wait(2)
            found = self._find_and_tap(
                f"Find {desc}.",
                wait_after=4,
            )

        if not found:
            print(f"  [{self.tag}] {label} not found!")
            return False

        # Check current level if target specified
        if target_level:
            img = bot.screenshot_b64()
            level_info = bot.ask_ai(
                f"Viking Rise building panel (1280x720). "
                f"What is the current level of this {label}? "
                f'Look for "Lv" or "Level" number. '
                '{"level": 5} — Respond ONLY JSON.',
                img, 50,
            )
            if level_info and isinstance(level_info.get("level"), (int, float)):
                current = int(level_info["level"])
                if current >= target_level:
                    print(f"  [{self.tag}] {label} already Lv{current} (need {target_level}) ✔")
                    self._safe_close()
                    return True

        # Press Upgrade button
        ok = self._find_and_tap(
            "Find an 'Upgrade' button (green or blue). "
            "If grayed out, look for requirements text.",
            wait_after=4,
        )
        if not ok:
            # Maybe need to scroll or find upgrade tab
            self._find_and_tap(
                "Find an 'Upgrade' or 'Build' tab in the building menu.",
                wait_after=3,
            )
            ok = self._find_and_tap(
                "Find an 'Upgrade' button (green or blue).",
                wait_after=4,
            )

        if not ok:
            print(f"  [{self.tag}] Cannot upgrade {label} — may need resources or prerequisites")
            self._safe_close()
            return False

        # Confirm upgrade
        self._find_and_tap(
            "Find a 'Confirm' or 'Upgrade' confirmation button (green).",
            wait_after=3,
        )

        # Dismiss any popup
        bot.tap(640, 400, jitter=False)
        bot.wait(2)

        print(f"  [{self.tag}] ✔ {label} upgrade started!")
        self._safe_close()

        # Use speedups immediately
        self._use_all_speedups()

        return True

    # ──────────────────────────────────────────────
    #  UPGRADE RESOURCE BUILDINGS
    # ──────────────────────────────────────────────
    def _upgrade_resource_buildings(self):
        """Upgrade farms, lumber mills, quarries, mines for more resources."""
        bot = self.bot
        bot.go_to_city()
        bot.wait(2)

        resource_buildings = [
            "a Farm or Food production building with a green upgrade arrow",
            "a Lumber Mill or Wood production building with a green upgrade arrow",
            "a Quarry or Stone production building with a green upgrade arrow",
            "an Iron Mine or Metal production building with a green upgrade arrow",
        ]

        upgraded = 0
        for desc in resource_buildings:
            found = self._find_and_tap(desc, wait_after=4)
            if found:
                ok = self._find_and_tap(
                    "Find an 'Upgrade' button (green or blue).",
                    wait_after=3,
                )
                if ok:
                    self._find_and_tap("Find 'Confirm' button.", wait_after=3)
                    upgraded += 1
                    bot.tap(640, 400, jitter=False)
                    bot.wait(2)
                self._safe_close()
                bot.wait(1)

        if upgraded:
            print(f"  [{self.tag}] Upgraded {upgraded} resource building(s)")
            self._use_all_speedups()

        return upgraded

    # ──────────────────────────────────────────────
    #  COLLECT RESOURCES
    # ──────────────────────────────────────────────
    def _collect_resources(self):
        """Collect any available resources from buildings."""
        bot = self.bot
        bot.go_to_city()
        bot.wait(2)

        collected = 0
        for _ in range(5):
            img = bot.screenshot_b64()
            result = bot.ask_ai(
                "Viking Rise city (1280x720). Find a resource bubble or "
                "collectible icon floating above a building — food, wood, "
                "stone, or gold icons that can be tapped to collect. "
                '{"found": true, "x": 500, "y": 300} or {"found": false}',
                img, 80,
            )
            if not result or not result.get("found"):
                break
            bot.tap(result["x"], result["y"])
            bot.wait(1)
            collected += 1

        if collected:
            print(f"  [{self.tag}] Collected {collected} resource(s)")
        return collected

    # ──────────────────────────────────────────────
    #  USE RESOURCE ITEMS FROM INVENTORY
    # ──────────────────────────────────────────────
    def _use_resource_items(self):
        """Open inventory and use resource items if available."""
        bot = self.bot
        bot.go_to_city()
        bot.wait(2)

        # Open items/inventory
        found = self._find_and_tap(
            "Find the Items, Inventory, or Backpack icon — usually on "
            "the bottom toolbar or accessible from the profile menu.",
            wait_after=4,
        )
        if not found:
            return False

        # Look for Resource tab
        self._find_and_tap(
            "Find a 'Resources' or 'Items' tab in the inventory.",
            wait_after=3,
        )

        # Use resource items
        used = 0
        for _ in range(5):
            ok = self._find_and_tap(
                "Find a resource chest, resource pack, or food/wood/stone/gold "
                "item that can be used. Tap on it.",
                wait_after=3,
            )
            if not ok:
                break
            self._find_and_tap(
                "Find a 'Use' or 'Open' button.",
                wait_after=2,
            )
            self._find_and_tap("Find 'Confirm' or 'Use All' button.", wait_after=2)
            used += 1
            bot.tap(640, 400, jitter=False)
            bot.wait(1)

        if used:
            print(f"  [{self.tag}] Used {used} resource item(s)")
        self._safe_close()
        return used > 0

    # ──────────────────────────────────────────────
    #  CLAIM ALL REWARDS
    # ──────────────────────────────────────────────
    def _claim_rewards(self):
        """Claim any available quest/chapter/mail rewards."""
        bot = self.bot
        bot.go_to_city()
        bot.wait(2)

        # Claim quest rewards
        found = self._find_and_tap(
            "Find a quest/chapter notification icon with a red dot or "
            "reward indicator on the right side or bottom toolbar.",
            wait_after=4,
        )
        if found:
            for _ in range(5):
                ok = self._find_and_tap(
                    "Find a green 'Claim', 'Collect', or 'Complete' button.",
                    wait_after=3,
                )
                if not ok:
                    break
                bot.tap(640, 400, jitter=False)
                bot.wait(2)
            self._safe_close()

    # ──────────────────────────────────────────────
    #  WAIT FOR CONSTRUCTION
    # ──────────────────────────────────────────────
    def _wait_for_construction(self, max_wait=30):
        """Wait for current construction to finish (with speedup attempts)."""
        bot = self.bot

        for check in range(max_wait):
            bot.go_to_city()
            bot.wait(2)

            # Check if any building is under construction
            img = bot.screenshot_b64()
            result = bot.ask_ai(
                "Viking Rise city (1280x720). Is there any building currently "
                "under construction? Look for a timer, progress bar, or "
                "construction crane icon above any building. "
                '{"building": true} or {"building": false}',
                img, 50,
            )
            if not result or not result.get("building"):
                return True  # No construction = ready

            # Try speedups again
            self._use_all_speedups()

            # Wait 30 seconds before checking again
            print(f"  [{self.tag}] Construction in progress... waiting ({check+1}/{max_wait})")
            bot.wait(30)

        return False

    # ──────────────────────────────────────────────
    #  MAIN RUSH LOOP
    # ──────────────────────────────────────────────
    def run(self):
        bot = self.bot
        bot.go_to_city()
        bot.wait(3)

        # Detect current level
        current_level = self._detect_ch_level()
        if current_level is None:
            print(f"  [{self.tag}] Cannot detect Chief Hall level!")
            current_level = 1  # Assume level 1

        print(f"  [{self.tag}] ═══════════════════════════════════")
        print(f"  [{self.tag}]  CITY RUSH: Level {current_level} → {self.TARGET_LEVEL}")
        print(f"  [{self.tag}] ═══════════════════════════════════")

        if current_level >= self.TARGET_LEVEL:
            print(f"  [{self.tag}] ✔ Already at Level {current_level}! Done.")
            return True

        # Main progression loop
        for target_ch in range(current_level + 1, self.TARGET_LEVEL + 1):
            print(f"\n  [{self.tag}] ───── Upgrading to Chief Hall Lv{target_ch} ─────")

            # 1. Collect resources
            self._collect_resources()
            self._claim_rewards()

            # 2. Upgrade prerequisite buildings
            requirements = CH_REQUIREMENTS.get(target_ch, [])
            for building_key, req_level in requirements:
                label = building_key.replace("_", " ").title()
                print(f"  [{self.tag}] Prerequisite: {label} Lv{req_level}")

                # May need multiple upgrades to reach required level
                for attempt in range(req_level):
                    success = self._upgrade_building(building_key, req_level)
                    if success:
                        break
                    # Wait for construction to finish
                    self._wait_for_construction(max_wait=10)
                    # Try resource items if upgrade failed
                    self._use_resource_items()

            # 3. Wait for any active construction
            self._wait_for_construction(max_wait=15)

            # 4. Upgrade Chief Hall
            for attempt in range(self.MAX_RETRIES):
                success = self._upgrade_building("chief_hall")
                if success:
                    break
                print(f"  [{self.tag}] CH upgrade failed, retry {attempt+1}/{self.MAX_RETRIES}")
                self._collect_resources()
                self._use_resource_items()
                self._upgrade_resource_buildings()
                self._wait_for_construction(max_wait=10)

            # 5. Wait for CH upgrade to complete
            self._wait_for_construction(max_wait=20)

            # 6. Verify level
            new_level = self._detect_ch_level()
            if new_level and new_level >= target_ch:
                print(f"  [{self.tag}] ✔ Chief Hall Level {target_ch} reached!")
            else:
                print(f"  [{self.tag}] ⚠ Level verification: detected Lv{new_level}")

            # 7. Upgrade resource buildings between CH levels
            self._upgrade_resource_buildings()

        # Final check
        final_level = self._detect_ch_level()
        print(f"\n  [{self.tag}] ═══════════════════════════════════")
        print(f"  [{self.tag}]  CITY RUSH COMPLETE!")
        print(f"  [{self.tag}]  Final Level: {final_level or '?'}")
        print(f"  [{self.tag}] ═══════════════════════════════════")

        return True
