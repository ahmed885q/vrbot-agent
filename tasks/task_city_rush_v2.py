"""
City Rush Task for Viking Rise - Automates Chief Hall upgrade from Level 1 to Level 17

This is the most critical automation for new farms. Every new account needs to reach
Chief Hall Level 17 to unlock all buildings and game features.

Phases:
  Phase 1 - Tutorial (Lv1-5): Follow tutorial arrows, auto-click
  Phase 2 - Growth (Lv5-10):  Auto-upgrade with prerequisite handling
  Phase 3 - Rush (Lv10-17):   Resource management, speedups, prerequisites

Chief Hall Upgrade Requirements (verified from game data):
  Lv2:  Infantry Barracks Lv1                    | 1.8K F, 1.8K W
  Lv3:  Walls Lv2                                | 4K F, 4K W
  Lv4:  Walls Lv3                                | 12.7K F, 12.7K W
  Lv5:  Walls Lv4, Infirmary Lv5                 | 27.6K F, 27.6K W
  Lv6:  Walls Lv5, Warehouse Lv5                 | 48.8K F, 48.8K W, 25.1K S
  Lv7:  Walls Lv6, Eagle's Nest Lv6              | 72.2K F, 72.2K W, 37.2K S
  Lv8:  Walls Lv7, Infantry Barracks Lv7         | 108.3K F, 108.3K W, 55.8K S
  Lv9:  Walls Lv8, Tribe Hall Lv8                | 150.8K F, 150.8K W, 77.7K S
  Lv10: Walls Lv9, Academy Lv9                   | 212K F, 212K W, 109K S
  Lv11: Walls Lv10, Infirmary Lv10               | 297K F, 297K W, 153K S
  Lv12: Walls Lv11, Warehouse Lv11               | 416K F, 416K W, 214K S
  Lv13: Walls Lv12, Piker Barracks Lv12          | 582K F, 582K W, 300K S
  Lv14: Walls Lv13, Tribe Hall Lv13              | 815K F, 815K W, 420K S
  Lv15: Walls Lv14, Divination Lv14              | 1.1M F, 1.1M W, 589K S
  Lv16: Walls Lv15, Academy Lv15                 | 1.5M F, 1.5M W, 820K S
  Lv17: Walls Lv16, Infirmary Lv16               | 3.1M F, 3.1M W, 1.6M S
"""

import time
import re
from base_task import BaseTask


# -- Upgrade Requirements Table --
# Format: target_level -> { "buildings": [(name, level), ...], "food": int, "wood": int, "stone": int }
CHIEF_HALL_REQUIREMENTS = {
    2:  {"buildings": [("Infantry Barracks", 1)],
         "food": 1800, "wood": 1800, "stone": 0},
    3:  {"buildings": [("Walls", 2)],
         "food": 4000, "wood": 4000, "stone": 0},
    4:  {"buildings": [("Walls", 3)],
         "food": 12700, "wood": 12700, "stone": 0},
    5:  {"buildings": [("Walls", 4), ("Infirmary", 5)],
         "food": 27600, "wood": 27600, "stone": 0},
    6:  {"buildings": [("Walls", 5), ("Warehouse", 5)],
         "food": 48800, "wood": 48800, "stone": 25100},
    7:  {"buildings": [("Walls", 6), ("Eagle's Nest", 6)],
         "food": 72200, "wood": 72200, "stone": 37200},
    8:  {"buildings": [("Walls", 7), ("Infantry Barracks", 7)],
         "food": 108300, "wood": 108300, "stone": 55800},
    9:  {"buildings": [("Walls", 8), ("Tribe Hall", 8)],
         "food": 150800, "wood": 150800, "stone": 77700},
    10: {"buildings": [("Walls", 9), ("Academy", 9)],
         "food": 212000, "wood": 212000, "stone": 109000},
    11: {"buildings": [("Walls", 10), ("Infirmary", 10)],
         "food": 297000, "wood": 297000, "stone": 153000},
    12: {"buildings": [("Walls", 11), ("Warehouse", 11)],
         "food": 416000, "wood": 416000, "stone": 214000},
    13: {"buildings": [("Walls", 12), ("Piker Barracks", 12)],
         "food": 582000, "wood": 582000, "stone": 300000},
    14: {"buildings": [("Walls", 13), ("Tribe Hall", 13)],
         "food": 815000, "wood": 815000, "stone": 420000},
    15: {"buildings": [("Walls", 14), ("Divination", 14)],
         "food": 1100000, "wood": 1100000, "stone": 589000},
    16: {"buildings": [("Walls", 15), ("Academy", 15)],
         "food": 1500000, "wood": 1500000, "stone": 820000},
    17: {"buildings": [("Walls", 16), ("Infirmary", 16)],
         "food": 3100000, "wood": 3100000, "stone": 1600000},
}

# Building name aliases for matching game screen text
BUILDING_ALIASES = {
    "Infantry Barracks": ["infantry barracks", "infantry", "barracks"],
    "Walls": ["walls", "wall", "city wall", "city walls"],
    "Infirmary": ["infirmary", "hospital"],
    "Warehouse": ["warehouse", "storehouse"],
    "Eagle's Nest": ["eagle's nest", "eagle nest", "eagles nest", "watchtower"],
    "Tribe Hall": ["tribe hall", "alliance hall", "embassy"],
    "Academy": ["academy", "research", "college"],
    "Piker Barracks": ["piker barracks", "pikemen barracks", "pikemen", "piker"],
    "Divination": ["divination", "divination shack", "oracle"],
}


class TaskCityRush(BaseTask):
    """Automate Chief Hall upgrade from Level 1 to Level 17 in Viking Rise"""

    name = "City Rush"
    tag = "city_rush"
    description = "Upgrade Chief Hall from Level 1 to Level 17 automatically"
    cooldown_hours = 0      # continuous until done
    max_steps = 500
    max_stuck = 15

    # -- Lifecycle --

    def setup(self, bot):
        """Initialize task state"""
        self.phase = "tutorial"   # tutorial | growth | rush
        self.target_level = 17
        self.current_level = 1
        self.stuck_count = 0
        self.last_action = None
        self.upgrade_queue = []   # prerequisite buildings waiting to upgrade
        self.resources = {"food": 0, "wood": 0, "stone": 0}
        self.upgrading_building = None  # currently upgrading building name
        self.step_counter = 0

    def step(self, bot):
        """Main step - called repeatedly by the task scheduler"""
        self.step_counter += 1

        # -- Detect current level --
        if self.step_counter % 5 == 1:
            detected = self._detect_chief_hall_level(bot)
            if detected and detected != self.current_level:
                old = self.current_level
                self.current_level = detected
                print(f"[CITY_RUSH] Chief Hall Level: {old} -> {detected}")
                self.stuck_count = 0

        # -- Done? --
        if self.current_level >= self.target_level:
            print(f"[CITY_RUSH] TARGET REACHED! Chief Hall Level {self.current_level}")
            return "done"

        # -- Handle popups first --
        if self._handle_popups(bot):
            return

        # -- Phase routing --
        if self.current_level < 5:
            self.phase = "tutorial"
            self._handle_tutorial(bot)
        elif self.current_level < 10:
            self.phase = "growth"
            self._handle_growth_phase(bot)
        else:
            self.phase = "rush"
            self._handle_rush_phase(bot)

    # -- Phase 1: Tutorial (Lv 1-5) --

    def _handle_tutorial(self, bot):
        """Follow tutorial arrows and prompts"""
        screenshot = bot.screenshot_b64()

        # Look for highlighted / glowing tutorial elements
        arrows = bot.yolo_find("tutorial_arrow", screenshot)
        if arrows:
            print("[CITY_RUSH] Tutorial arrow found - tapping")
            bot.tap(arrows[0][0], arrows[0][1])
            time.sleep(1)
            return

        # Look for "agree" / "confirm" / "next" buttons
        for label in ["button_confirm", "button_agree", "button_next"]:
            btns = bot.yolo_find(label, screenshot)
            if btns:
                print(f"[CITY_RUSH] Tutorial button '{label}' found - tapping")
                bot.tap(btns[0][0], btns[0][1])
                time.sleep(1)
                return

        # Look for upgrade button in tutorial
        upgrade_btns = bot.yolo_find("button_upgrade", screenshot)
        if upgrade_btns:
            print("[CITY_RUSH] Upgrade button found - tapping for tutorial")
            bot.tap(upgrade_btns[0][0], upgrade_btns[0][1])
            time.sleep(1.5)
            return

        # Ask AI to understand the tutorial state
        print("[CITY_RUSH] Asking AI about tutorial state")
        prompt = (
            "Analyze this Viking Rise game screen. What does the tutorial want me to do? "
            "Look for: arrows, highlighted areas, tutorial text, buttons. "
            "Respond with ONE of:\n"
            "  tutorial_tap: <x> <y>   (coordinates to tap)\n"
            "  tutorial_done           (tutorial is finished)\n"
            "  city_view               (we are in city, no tutorial)"
        )
        ai_response = bot.ask_ai(prompt, screenshot)
        print(f"[CITY_RUSH] AI: {ai_response}")

        if "tutorial_tap" in ai_response.lower():
            coords = re.findall(r'(\d+)', ai_response)
            if len(coords) >= 2:
                bot.tap(int(coords[0]), int(coords[1]))
                time.sleep(1)
                return

        if "tutorial_done" in ai_response.lower() or "city_view" in ai_response.lower():
            self.phase = "growth"
            print("[CITY_RUSH] Tutorial complete, entering growth phase")
            return

        # Fallback: tap center
        print("[CITY_RUSH] No tutorial element found - tapping center")
        bot.tap(540, 960)
        time.sleep(1)

    # -- Phase 2: Growth (Lv 5-10) --

    def _handle_growth_phase(self, bot):
        """
        Auto-upgrade Chief Hall with prerequisite handling.
        Each step: check prereqs -> upgrade prereqs -> upgrade Chief Hall.
        """
        # Check if something is currently upgrading
        if self._is_building_upgrading(bot):
            print("[CITY_RUSH] A building is upgrading - waiting...")
            # Try to use speedups if Chief Hall is upgrading
            if self.upgrading_building == "Chief Hall":
                self._use_speedups(bot)
            time.sleep(3)
            return

        # Check & handle prerequisites for next level
        next_level = self.current_level + 1
        if next_level in CHIEF_HALL_REQUIREMENTS:
            reqs = CHIEF_HALL_REQUIREMENTS[next_level]
            prereq_met = self._check_and_upgrade_prerequisites(bot, reqs)
            if not prereq_met:
                return  # still working on prerequisites

        # Prerequisites met - try to upgrade Chief Hall
        if self._upgrade_chief_hall(bot):
            self.upgrading_building = "Chief Hall"
            print(f"[CITY_RUSH] Chief Hall Lv{next_level} upgrade started!")
            time.sleep(2)
            return

        # If resources are low, try gathering
        if self._check_resources_low(bot, next_level):
            self._gather_resources(bot)
            return

        time.sleep(3)

    # -- Phase 3: Rush (Lv 10-17) --

    def _handle_rush_phase(self, bot):
        """
        Rush phase uses speedups aggressively and manages resources.
        Same logic as growth but with speedup usage.
        """
        # Check if something is currently upgrading
        if self._is_building_upgrading(bot):
            print("[CITY_RUSH] Building upgrading - using speedups")
            self._use_speedups(bot)
            time.sleep(2)
            return

        # Handle prerequisites
        next_level = self.current_level + 1
        if next_level in CHIEF_HALL_REQUIREMENTS:
            reqs = CHIEF_HALL_REQUIREMENTS[next_level]
            prereq_met = self._check_and_upgrade_prerequisites(bot, reqs)
            if not prereq_met:
                return

        # Upgrade Chief Hall
        if self._upgrade_chief_hall(bot):
            self.upgrading_building = "Chief Hall"
            print(f"[CITY_RUSH] Chief Hall Lv{next_level} upgrade started! (Rush phase)")
            self._use_speedups(bot)
            time.sleep(2)
            return

        # Resource management
        if self._check_resources_low(bot, next_level):
            self._use_resource_items(bot)
            self._gather_resources(bot)
            return

        time.sleep(3)

    # -- Prerequisite System --

    def _check_and_upgrade_prerequisites(self, bot, reqs):
        """
        Check if all prerequisite buildings meet the required levels.
        If not, navigate to them and start upgrading.
        Returns True if all prerequisites are met.
        """
        for building_name, required_level in reqs["buildings"]:
            # Ask AI to check the building level
            current_bldg_level = self._get_building_level(bot, building_name)

            if current_bldg_level is not None and current_bldg_level < required_level:
                print(f"[CITY_RUSH] Prerequisite needed: {building_name} Lv{current_bldg_level} -> Lv{required_level}")

                # Navigate to and upgrade the prerequisite building
                if self._navigate_to_building(bot, building_name):
                    if self._tap_upgrade_building(bot, building_name):
                        self.upgrading_building = building_name
                        print(f"[CITY_RUSH] Upgrading {building_name} to Lv{current_bldg_level + 1}")
                        time.sleep(2)
                    else:
                        print(f"[CITY_RUSH] Cannot upgrade {building_name} yet - checking sub-prerequisites")
                        self._handle_sub_prerequisites(bot, building_name, required_level)
                return False

        print("[CITY_RUSH] All prerequisites met!")
        return True

    def _get_building_level(self, bot, building_name):
        """Get the current level of a specific building using AI"""
        screenshot = bot.screenshot_b64()

        aliases = BUILDING_ALIASES.get(building_name, [building_name.lower()])
        alias_list = ", ".join(aliases)

        prompt = (
            f"Look at this Viking Rise city screen. Find the building '{building_name}' "
            f"(also known as: {alias_list}). "
            f"What level is it? Reply with ONLY a number like: 5"
        )
        response = bot.ask_ai(prompt, screenshot)

        # Extract number from response
        numbers = re.findall(r'\b(\d{1,2})\b', response)
        if numbers:
            level = int(numbers[0])
            if 0 <= level <= 30:
                return level

        return None

    def _navigate_to_building(self, bot, building_name):
        """Navigate camera to focus on a specific building"""
        screenshot = bot.screenshot_b64()

        aliases = BUILDING_ALIASES.get(building_name, [building_name.lower()])
        alias_list = ", ".join(aliases)

        prompt = (
            f"I need to find and tap on the '{building_name}' building "
            f"(also known as: {alias_list}) in this Viking Rise city view. "
            f"Where is it? Give me the x, y coordinates to tap. "
            f"Reply format: tap: <x> <y>"
        )
        response = bot.ask_ai(prompt, screenshot)

        coords = re.findall(r'(\d+)', response)
        if len(coords) >= 2:
            x, y = int(coords[0]), int(coords[1])
            print(f"[CITY_RUSH] Navigating to {building_name} at ({x}, {y})")
            bot.tap(x, y)
            time.sleep(1.5)
            return True

        print(f"[CITY_RUSH] Could not find {building_name}")
        return False

    def _tap_upgrade_building(self, bot, building_name):
        """Tap the upgrade button for a building that is already selected"""
        screenshot = bot.screenshot_b64()

        # Look for upgrade button
        upgrade_btns = bot.yolo_find("button_upgrade", screenshot)
        if upgrade_btns:
            print(f"[CITY_RUSH] Tapping upgrade button for {building_name}")
            bot.tap(upgrade_btns[0][0], upgrade_btns[0][1])
            time.sleep(1)

            # Confirm if there is a confirm button
            screenshot2 = bot.screenshot_b64()
            confirm_btns = bot.yolo_find("button_confirm", screenshot2)
            if confirm_btns:
                bot.tap(confirm_btns[0][0], confirm_btns[0][1])
                time.sleep(1)

            return True

        # Try asking AI for the upgrade button location
        prompt = (
            f"I have the {building_name} building info panel open. "
            f"Where is the Upgrade button? Reply: tap: <x> <y>"
        )
        response = bot.ask_ai(prompt, screenshot)
        coords = re.findall(r'(\d+)', response)
        if len(coords) >= 2:
            bot.tap(int(coords[0]), int(coords[1]))
            time.sleep(1.5)
            return True

        return False

    def _handle_sub_prerequisites(self, bot, building_name, target_level):
        """
        Handle sub-prerequisites: e.g. Walls needs resources,
        Infirmary might need lower-level buildings first.
        """
        screenshot = bot.screenshot_b64()
        prompt = (
            f"I'm trying to upgrade {building_name} but it's blocked. "
            f"What does the upgrade screen say I need? "
            f"Look for requirement text (e.g. 'Requires: Walls Lv.X'). "
            f"Reply: requirement: <building_name> <level>"
        )
        response = bot.ask_ai(prompt, screenshot)
        print(f"[CITY_RUSH] Sub-prereq check: {response}")

        match = re.search(r'requirement:\s*(\w[\w\s\']*?)\s+(\d+)', response, re.IGNORECASE)
        if match:
            sub_building = match.group(1).strip()
            sub_level = int(match.group(2))
            print(f"[CITY_RUSH] Sub-prerequisite: {sub_building} Lv{sub_level}")
            bot.key("back")
            time.sleep(1)
            if self._navigate_to_building(bot, sub_building):
                self._tap_upgrade_building(bot, sub_building)

    # -- Chief Hall Upgrade --

    def _detect_chief_hall_level(self, bot):
        """Detect current Chief Hall level using multiple methods"""
        screenshot = bot.screenshot_b64()

        # Method 1: OCR on the Chief Hall building
        prompt = (
            "Look at the Chief Hall / Chief's Hall building (the main/largest building "
            "in the center of the Viking Rise city). What level is it? "
            "Look for 'Lv.' or 'Level' text near or on the building. "
            "Reply with ONLY the number, e.g.: 7"
        )
        response = bot.ask_ai(prompt, screenshot)
        numbers = re.findall(r'\b(\d{1,2})\b', response)
        if numbers:
            level = int(numbers[0])
            if 1 <= level <= 25:
                return level

        # Method 2: Check top-left power/level indicator
        prompt = (
            "Look at the top area of the screen. Is there a Chief Hall level indicator? "
            "Reply with ONLY the number."
        )
        response = bot.ask_ai(prompt, screenshot)
        numbers = re.findall(r'\b(\d{1,2})\b', response)
        if numbers:
            level = int(numbers[0])
            if 1 <= level <= 25:
                return level

        return None

    def _upgrade_chief_hall(self, bot):
        """Navigate to Chief Hall and start upgrade"""
        bot.go_to_city()
        time.sleep(1)

        # Tap on Chief Hall (center of city)
        bot.tap(540, 700)
        time.sleep(1.5)

        screenshot = bot.screenshot_b64()

        # Look for upgrade button
        upgrade_btns = bot.yolo_find("button_upgrade", screenshot)
        if upgrade_btns:
            print("[CITY_RUSH] Chief Hall upgrade button found")
            bot.tap(upgrade_btns[0][0], upgrade_btns[0][1])
            time.sleep(1)

            # Check for confirm dialog
            screenshot2 = bot.screenshot_b64()
            confirm_btns = bot.yolo_find("button_confirm", screenshot2)
            if confirm_btns:
                bot.tap(confirm_btns[0][0], confirm_btns[0][1])
                time.sleep(1)
            return True

        # AI fallback
        prompt = (
            "I have the Chief Hall building panel open. Where is the Upgrade button? "
            "If upgrade is greyed out or says 'requirements not met', say: blocked. "
            "Otherwise reply: tap: <x> <y>"
        )
        response = bot.ask_ai(prompt, screenshot)

        if "blocked" in response.lower():
            print("[CITY_RUSH] Chief Hall upgrade is blocked - need prerequisites")
            return False

        coords = re.findall(r'(\d+)', response)
        if len(coords) >= 2:
            bot.tap(int(coords[0]), int(coords[1]))
            time.sleep(1.5)
            return True

        print("[CITY_RUSH] Could not find Chief Hall upgrade button")
        return False

    # -- Resource & Speedup Management --

    def _check_resources_low(self, bot, next_level):
        """Check if resources are too low for the next upgrade"""
        if next_level not in CHIEF_HALL_REQUIREMENTS:
            return False

        reqs = CHIEF_HALL_REQUIREMENTS[next_level]
        screenshot = bot.screenshot_b64()

        prompt = (
            f"Look at the resource bar at the top of the screen. "
            f"What are the current Food, Wood, and Stone amounts? "
            f"I need at least: Food {reqs['food']:,}, Wood {reqs['wood']:,}, Stone {reqs['stone']:,}. "
            f"Do I have enough? Reply: yes or no"
        )
        response = bot.ask_ai(prompt, screenshot)
        return "no" in response.lower()

    def _gather_resources(self, bot):
        """Send troops to gather resources on the world map"""
        print("[CITY_RUSH] Gathering resources...")
        bot.tap(60, 600)  # Map button
        time.sleep(2)

        screenshot = bot.screenshot_b64()
        prompt = (
            "I'm on the world map. Find the nearest resource tile (farm, lumber camp, "
            "or stone quarry) to gather from. Reply: tap: <x> <y>"
        )
        response = bot.ask_ai(prompt, screenshot)
        coords = re.findall(r'(\d+)', response)
        if len(coords) >= 2:
            bot.tap(int(coords[0]), int(coords[1]))
            time.sleep(1.5)

            screenshot2 = bot.screenshot_b64()
            gather_btns = bot.yolo_find("button_gather", screenshot2)
            if gather_btns:
                bot.tap(gather_btns[0][0], gather_btns[0][1])
                time.sleep(1)

        bot.go_to_city()
        time.sleep(1)

    def _use_resource_items(self, bot):
        """Use resource items from inventory"""
        print("[CITY_RUSH] Using resource items from inventory...")
        bot.tap(80, 780)  # Items button
        time.sleep(1.5)

        screenshot = bot.screenshot_b64()
        prompt = (
            "I need to use resource items (food/wood/stone packs) from my inventory. "
            "Is there a Resources tab? Reply: tap: <x> <y>"
        )
        response = bot.ask_ai(prompt, screenshot)
        coords = re.findall(r'(\d+)', response)
        if len(coords) >= 2:
            bot.tap(int(coords[0]), int(coords[1]))
            time.sleep(1)

            screenshot2 = bot.screenshot_b64()
            use_btns = bot.yolo_find("button_use", screenshot2)
            if use_btns:
                for btn in use_btns[:5]:
                    bot.tap(btn[0], btn[1])
                    time.sleep(0.5)

        bot.key("back")
        time.sleep(1)

    def _use_speedups(self, bot):
        """Use speedup items to finish building faster"""
        print("[CITY_RUSH] Attempting to use speedups...")
        screenshot = bot.screenshot_b64()

        speedup_btns = bot.yolo_find("button_speedup", screenshot)
        if speedup_btns:
            bot.tap(speedup_btns[0][0], speedup_btns[0][1])
            time.sleep(1)

            screenshot2 = bot.screenshot_b64()
            free_btns = bot.yolo_find("button_free", screenshot2)
            if free_btns:
                bot.tap(free_btns[0][0], free_btns[0][1])
                time.sleep(1)
                return

            use_btns = bot.yolo_find("button_use", screenshot2)
            if use_btns:
                bot.tap(use_btns[0][0], use_btns[0][1])
                time.sleep(1)
                return

            prompt = (
                "I see a speedup dialog. Where do I tap to use a speedup? "
                "Reply: tap: <x> <y>"
            )
            response = bot.ask_ai(prompt, screenshot2)
            coords = re.findall(r'(\d+)', response)
            if len(coords) >= 2:
                bot.tap(int(coords[0]), int(coords[1]))
                time.sleep(1)

    def _is_building_upgrading(self, bot):
        """Check if any building is currently upgrading"""
        screenshot = bot.screenshot_b64()
        prompt = (
            "Is there a building currently being upgraded in this Viking Rise city? "
            "Look for a timer or construction animation. Reply: yes or no"
        )
        response = bot.ask_ai(prompt, screenshot)
        return "yes" in response.lower()

    # -- Popup Handling --

    def _handle_popups(self, bot):
        """Handle random popups. Returns True if handled."""
        screenshot = bot.screenshot_b64()

        close_buttons = bot.yolo_find("button_close", screenshot)
        if close_buttons:
            for btn in close_buttons:
                x, y = btn[0], btn[1]
                if x > 400 and y < 400:
                    print("[CITY_RUSH] Popup detected - closing")
                    bot.tap(x, y)
                    time.sleep(1)
                    return True

        prompt = (
            "Is there a popup or overlay on screen that I should close? "
            "Reply: yes or no"
        )
        response = bot.ask_ai(prompt, screenshot)
        if "yes" in response.lower():
            prompt2 = "Where is the close/X button for this popup? Reply: tap: <x> <y>"
            response2 = bot.ask_ai(prompt2, screenshot)
            coords = re.findall(r'(\d+)', response2)
            if len(coords) >= 2:
                bot.tap(int(coords[0]), int(coords[1]))
                time.sleep(1)
                return True

        return False

