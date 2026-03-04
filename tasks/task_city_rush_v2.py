"""
City Rush Task for Viking Rise - Automates Chief Hall upgrade from Level 1 to Level 17

This is the most critical automation for new farms. Every new account needs to reach
Chief Hall Level 17 to unlock all buildings and game features.

Phases:
  Phase 1 - Tutorial (Lv1-5): Read chapter quests, click Go, complete each quest
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


# ─── Upgrade Requirements Table ──────────────────────────────────────────────────
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

# Building name aliases
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
    cooldown_hours = 0
    max_steps = 500
    max_stuck = 15

    # ─── Lifecycle ────────────────────────────────────────────────────────────────

    def setup(self, bot):
        """Initialize task state"""
        self.phase = "tutorial"   # tutorial | growth | rush        self.target_level = 17
        self.current_level = 1
        self.stuck_count = 0
        self.last_action = None
        self.last_quest_text = None
        self.upgrade_queue = []
        self.resources = {"food": 0, "wood": 0, "stone": 0}
        self.upgrading_building = None
        self.step_counter = 0
        self.consecutive_same_action = 0

    def step(self, bot):
        """Main step - called repeatedly by the task scheduler"""
        self.step_counter += 1

        # ── Detect current level every 5 steps ──────────────────────────
        if self.step_counter % 5 == 1:
            detected = self._detect_chief_hall_level(bot)
            if detected and detected != self.current_level:
                old = self.current_level
                self.current_level = detected
                print(f"[CITY_RUSH] Chief Hall Level: {old} -> {detected}")
                self.stuck_count = 0

        # ── Done? ─────────────────────────────────────────────────────
        if self.current_level >= self.target_level:
            print(f"[CITY_RUSH] TARGET REACHED! Chief Hall Level {self.current_level}")
            return "done"

        # ── Handle popups first ────────────────────────────────────────
        if self._handle_popups(bot):
            return

        # ── Phase routing ──────────────────────────────────────────────
        if self.current_level < 5:
            self.phase = "tutorial"
            self._handle_tutorial(bot)
        elif self.current_level < 10:
            self.phase = "growth"
            self._handle_growth_phase(bot)
        else:
            self.phase = "rush"
            self._handle_rush_phase(bot)

    # ═══════════════════════════════════════════════════════════════════
    # Phase 1: Tutorial (Lv 1-5) - Read chapter quests & complete them
    # ═══════════════════════════════════════════════════════════════════

    def _handle_tutorial(self, bot):
        """
        Smart tutorial handler that reads chapter quests and completes them.

        Strategy:
        1. Check for tutorial arrows/highlights → tap them immediately
        2. Check for action buttons (confirm, upgrade, build) → tap them
        3. Read the chapter quest list to understand what to do next
        4. Click on the first INCOMPLETE quest → use its "Go" button
        5. After "Go", complete the specific quest type (build/gather/train)
        6. Use free speedups aggressively
        """
        screenshot = bot.screenshot_b64()

        # ──────────────────────────────────────────────────────────────
        # Priority 1: Tutorial arrows / glowing highlights (highest priority)
        # ──────────────────────────────────────────────────────────────
        arrows = bot.yolo_find("tutorial_arrow", screenshot)
        if arrows:
            print("[CITY_RUSH] Tutorial arrow found - tapping")
            bot.tap(arrows[0][0], arrows[0][1])
            time.sleep(1.5)
            self.stuck_count = 0
            return

        # ──────────────────────────────────────────────────────────────
        # Priority 2: Actionable buttons on screen
        # ──────────────────────────────────────────────────────────────
        for label in ["button_confirm", "button_agree", "button_next",
                       "button_ok", "button_claim", "button_collect"]:
            btns = bot.yolo_find(label, screenshot)
            if btns:
                print(f"[CITY_RUSH] Button '{label}' found - tapping")
                bot.tap(btns[0][0], btns[0][1])
                time.sleep(1.5)
                self.stuck_count = 0
                return

        # Check for upgrade/build buttons already visible
        upgrade_btns = bot.yolo_find("button_upgrade", screenshot)
        if upgrade_btns:
            print("[CITY_RUSH] Upgrade button found - tapping")
            bot.tap(upgrade_btns[0][0], upgrade_btns[0][1])
            time.sleep(2)
            self.stuck_count = 0
            return

        build_btns = bot.yolo_find("button_build", screenshot)
        if build_btns:
            print("[CITY_RUSH] Build button found - tapping")
            bot.tap(build_btns[0][0], build_btns[0][1])
            time.sleep(2)            self.stuck_count = 0
            return

        # Check for train buttons
        train_btns = bot.yolo_find("button_train", screenshot)
        if train_btns:
            print("[CITY_RUSH] Train button found - tapping")
            bot.tap(train_btns[0][0], train_btns[0][1])
            time.sleep(2)
            self.stuck_count = 0
            return

        # ──────────────────────────────────────────────────────────────
        # Priority 3: Free speedup for instant completion
        # ──────────────────────────────────────────────────────────────
        speedup_btns = bot.yolo_find("button_speedup", screenshot)
        if speedup_btns:
            bot.tap(speedup_btns[0][0], speedup_btns[0][1])
            time.sleep(1)
            screenshot2 = bot.screenshot_b64()
            free_btns = bot.yolo_find("button_free", screenshot2)
            if free_btns:
                print("[CITY_RUSH] Free speedup - using it")
                bot.tap(free_btns[0][0], free_btns[0][1])
                time.sleep(1)
                self.stuck_count = 0
            else:
                # Use any speedup available during tutorial
                use_btns = bot.yolo_find("button_use", screenshot2)
                if use_btns:
                    bot.tap(use_btns[0][0], use_btns[0][1])
                    time.sleep(1)
                else:
                    bot.key("back")
                    time.sleep(0.5)
            return

        # ──────────────────────────────────────────────────────────────
        # Priority 4: AI reads chapter quests & decides next action
        # ──────────────────────────────────────────────────────────────
        print("[CITY_RUSH] Reading chapter quests with AI...")
        prompt = (
            "You are automating Viking Rise. Analyze this screenshot carefully.\n\n"
            "LOOK AT THE LEFT SIDE of the screen for the Chapter quest list. "
            "Each quest shows a task like 'Gather 200 Lumber', 'Build Chief Hall', "
            "'Train 5 Infantry', 'Upgrade Walls', etc.\n"
            "Quests may show progress like '(100/200)' or '(0/1)'.\n"
            "A GREEN CHECK mark means the quest is COMPLETED.\n"
            "A BLUE/YELLOW dot means the quest is INCOMPLETE.\n\n"
            "Also look for:\n"
            "- Any glowing/highlighted building or UI element\n"
            "- A timer showing construction in progress\n"
            "- The world map vs city view\n"
            "- Any dialog or panel open\n\n"
            "What is the BEST next action? Reply with EXACTLY ONE:\n"
            "  quest_click: <x> <y>  (click on an INCOMPLETE quest to open it / get Go button)\n"
            "  tap: <x> <y>         (tap a specific element like a building or button)\n"
            "  gather_food           (need to gather food on world map)\n"
            "  gather_wood           (need to gather wood/lumber on world map)\n"
            "  build: <building>     (need to build/upgrade a specific building)\n"
            "  train_troops          (need to train troops at barracks)\n"
            "  go_to_city            (currently on map, need to return to city)\n"
            "  go_to_map             (need to go to world map)\n"
            "  use_speedup           (building in progress, use speedup)\n"
            "  wait                  (building in progress, nothing to do)\n"
            "  tutorial_done         (all chapter quests done, free play)\n"
            "  close_panel           (close an open panel/dialog first)\n\n"
            "IMPORTANT: If you see incomplete quests on the left side, "
            "click on the FIRST INCOMPLETE one to get its Go button."
        )
        ai_response = bot.ask_ai(prompt, screenshot)
        print(f"[CITY_RUSH] AI: {ai_response}")
        response_lower = ai_response.lower().strip()

        # Track if doing same thing repeatedly
        if response_lower == self.last_action:
            self.consecutive_same_action += 1
        else:
            self.consecutive_same_action = 0
        self.last_action = response_lower

        # ── Parse AI response ───────────────────────────────────────────

        # Click on a quest
        if "quest_click:" in response_lower:
            coords = re.findall(r'(\d+)', ai_response)
            if len(coords) >= 2:
                x, y = int(coords[0]), int(coords[1])
                print(f"[CITY_RUSH] Clicking quest at ({x}, {y})")
                bot.tap(x, y)
                time.sleep(1.5)
                # After clicking quest, look for "Go" button
                self._find_and_tap_go_button(bot)
                return

        # Direct tap
        if "tap:" in response_lower:
            coords = re.findall(r'(\d+)', ai_response)
            if len(coords) >= 2:
                x, y = int(coords[0]), int(coords[1])                print(f"[CITY_RUSH] Tapping ({x}, {y})")
                bot.tap(x, y)
                time.sleep(1.5)
                return

        # Gather food
        if "gather_food" in response_lower:
            print("[CITY_RUSH] Gathering food...")
            self._tutorial_gather(bot, "food")
            return

        # Gather wood
        if "gather_wood" in response_lower:
            print("[CITY_RUSH] Gathering wood...")
            self._tutorial_gather(bot, "wood")
            return

        # Build specific building
        if "build:" in response_lower:
            match = re.search(r'build:\s*(.+)', ai_response, re.IGNORECASE)
            if match:
                building = match.group(1).strip()
                print(f"[CITY_RUSH] Building: {building}")
                self._tutorial_build(bot, building)
                return

        # Train troops
        if "train_troops" in response_lower or "train" in response_lower:
            print("[CITY_RUSH] Training troops...")
            self._tutorial_train(bot)
            return

        # Go to city
        if "go_to_city" in response_lower:
            print("[CITY_RUSH] Going to city")
            bot.go_to_city()
            time.sleep(2)
            return

        # Go to map
        if "go_to_map" in response_lower:
            print("[CITY_RUSH] Going to world map")
            bot.tap(60, 600)
            time.sleep(2)
            return

        # Use speedup
        if "use_speedup" in response_lower or "speedup" in response_lower:
            print("[CITY_RUSH] Using speedup")
            self._use_speedups(bot)
            return

        # Wait for building
        if "wait" in response_lower:
            print("[CITY_RUSH] Waiting for construction...")
            self._use_speedups(bot)
            time.sleep(3)
            return

        # Tutorial done
        if "tutorial_done" in response_lower or "done" in response_lower:
            self.phase = "growth"
            print("[CITY_RUSH] Tutorial complete! Entering growth phase")
            return

        # Close panel
        if "close" in response_lower:
            print("[CITY_RUSH] Closing panel")
            bot.key("back")
            time.sleep(1)
            return

        # ──────────────────────────────────────────────────────────────
        # Fallback: Smart unstuck behavior
        # ──────────────────────────────────────────────────────────────
        self.stuck_count += 1
        print(f"[CITY_RUSH] Stuck count: {self.stuck_count}")

        if self.stuck_count % 5 == 1:
            # Click on the first incomplete chapter quest (left side)
            print("[CITY_RUSH] Fallback: clicking first quest on left")
            bot.tap(200, 320)
            time.sleep(1)
            self._find_and_tap_go_button(bot)
        elif self.stuck_count % 5 == 2:
            # Try clicking second quest
            print("[CITY_RUSH] Fallback: clicking second quest")
            bot.tap(200, 380)
            time.sleep(1)
            self._find_and_tap_go_button(bot)
        elif self.stuck_count % 5 == 3:
            # Tap Chief Hall center
            print("[CITY_RUSH] Fallback: tapping Chief Hall")
            bot.go_to_city()
            time.sleep(1)
            bot.tap(540, 700)
            time.sleep(1.5)
            self._tap_any_action_button(bot)
        elif self.stuck_count % 5 == 4:
            # Try going to map for gathering            print("[CITY_RUSH] Fallback: going to map to gather")
            self._tutorial_gather(bot, "any")
        else:
            # Go to city and try tapping around
            print("[CITY_RUSH] Fallback: exploring city")
            bot.go_to_city()
            time.sleep(2)

        if self.stuck_count > 30:
            print("[CITY_RUSH] Too many stuck, forcing growth phase")
            self.phase = "growth"

        # If doing same action 5+ times, try something different
        if self.consecutive_same_action >= 5:
            print("[CITY_RUSH] Same action repeated 5x - forcing different approach")
            self.consecutive_same_action = 0
            bot.key("back")
            time.sleep(1)
            bot.go_to_city()
            time.sleep(2)

    # ── Tutorial Helper Methods ────────────────────────────────────────

    def _find_and_tap_go_button(self, bot):
        """After clicking a quest, find and tap the 'Go' button"""
        screenshot = bot.screenshot_b64()

        # Look for Go button with YOLO
        go_btns = bot.yolo_find("button_go", screenshot)
        if go_btns:
            print("[CITY_RUSH] Go button found - tapping")
            bot.tap(go_btns[0][0], go_btns[0][1])
            time.sleep(2)
            # After Go, look for action buttons
            self._tap_any_action_button(bot)
            return True

        # AI fallback to find Go button
        prompt = (
            "I clicked on a chapter quest. Is there a 'Go' or arrow button "
            "next to it that I can tap to navigate to the quest objective? "
            "If yes, reply: tap: <x> <y>\n"
            "If no Go button visible, reply: none"
        )
        response = bot.ask_ai(prompt, screenshot)
        if "none" not in response.lower():
            coords = re.findall(r'(\d+)', response)
            if len(coords) >= 2:
                print(f"[CITY_RUSH] AI found Go button at ({coords[0]}, {coords[1]})")
                bot.tap(int(coords[0]), int(coords[1]))
                time.sleep(2)
                self._tap_any_action_button(bot)
                return True

        return False

    def _tap_any_action_button(self, bot):
        """After navigating to a quest target, tap any visible action button"""
        screenshot = bot.screenshot_b64()

        # Check for various action buttons in priority order
        for label in ["button_upgrade", "button_build", "button_train",
                       "button_gather", "button_march", "button_go",
                       "button_confirm", "button_ok", "button_claim",
                       "button_collect", "button_research"]:
            btns = bot.yolo_find(label, screenshot)
            if btns:
                print(f"[CITY_RUSH] Action button '{label}' found - tapping")
                bot.tap(btns[0][0], btns[0][1])
                time.sleep(2)

                # After first action, check for confirm/ok
                screenshot2 = bot.screenshot_b64()
                for confirm_label in ["button_confirm", "button_ok",
                                       "button_agree", "button_march"]:
                    c_btns = bot.yolo_find(confirm_label, screenshot2)
                    if c_btns:
                        bot.tap(c_btns[0][0], c_btns[0][1])
                        time.sleep(1)
                        break
                return True

        # AI fallback
        prompt = (
            "What button should I tap on this screen to progress? "
            "Look for Upgrade, Build, Train, Gather, March, Research, Go, OK, etc. "
            "Reply: tap: <x> <y> or none"
        )
        response = bot.ask_ai(prompt, screenshot)
        if "none" not in response.lower():
            coords = re.findall(r'(\d+)', response)
            if len(coords) >= 2:
                bot.tap(int(coords[0]), int(coords[1]))
                time.sleep(1.5)
                return True

        return False

    def _tutorial_build(self, bot, building_name):
        """Handle building/upgrading a specific building during tutorial"""        bot.go_to_city()
        time.sleep(1)

        # Ask AI to find the building
        screenshot = bot.screenshot_b64()
        prompt = (
            f"I need to find and tap on '{building_name}' in this Viking Rise city. "
            f"It could be a building to upgrade or an empty plot to build on. "
            f"Where should I tap? Reply: tap: <x> <y>"
        )
        response = bot.ask_ai(prompt, screenshot)
        coords = re.findall(r'(\d+)', response)
        if len(coords) >= 2:
            bot.tap(int(coords[0]), int(coords[1]))
            time.sleep(1.5)
            # Now tap the action button
            self._tap_any_action_button(bot)
        else:
            # Fallback: tap center for Chief Hall
            if "chief" in building_name.lower() or "hall" in building_name.lower():
                bot.tap(540, 700)
                time.sleep(1.5)
                self._tap_any_action_button(bot)

    def _tutorial_train(self, bot):
        """Handle training troops during tutorial"""
        bot.go_to_city()
        time.sleep(1)

        # Ask AI to find the barracks
        screenshot = bot.screenshot_b64()
        prompt = (
            "I need to train troops. Where is the Infantry Barracks or any "
            "military building in this Viking Rise city? Reply: tap: <x> <y>"
        )
        response = bot.ask_ai(prompt, screenshot)
        coords = re.findall(r'(\d+)', response)
        if len(coords) >= 2:
            bot.tap(int(coords[0]), int(coords[1]))
            time.sleep(1.5)

            # Look for train button
            screenshot2 = bot.screenshot_b64()
            train_btns = bot.yolo_find("button_train", screenshot2)
            if train_btns:
                bot.tap(train_btns[0][0], train_btns[0][1])
                time.sleep(1)
            else:
                self._tap_any_action_button(bot)

            # Confirm training
            time.sleep(1)
            screenshot3 = bot.screenshot_b64()
            for label in ["button_confirm", "button_ok", "button_train"]:
                btns = bot.yolo_find(label, screenshot3)
                if btns:
                    bot.tap(btns[0][0], btns[0][1])
                    time.sleep(1)
                    break

    def _tutorial_gather(self, bot, resource_type="any"):
        """Handle gathering resources during tutorial"""
        # Check if already on map
        screenshot = bot.screenshot_b64()
        prompt = (
            "Am I on the world map or in the city view? "
            "Reply: map or city"
        )
        response = bot.ask_ai(prompt, screenshot)

        if "city" in response.lower():
            # Go to world map
            bot.tap(60, 600)
            time.sleep(2)
            screenshot = bot.screenshot_b64()

        # Find resource tile
        if resource_type == "food":
            resource_desc = "farm or food resource tile (wheat/grain field)"
        elif resource_type == "wood":
            resource_desc = "lumber camp or wood resource tile (forest)"
        else:
            resource_desc = "any resource tile (farm, lumber camp, or stone quarry)"

        prompt = (
            f"I'm on the Viking Rise world map. I need to find a {resource_desc} "
            f"to gather from. Look for resource nodes near my city. "
            f"Reply: tap: <x> <y>"
        )
        response = bot.ask_ai(prompt, screenshot)
        coords = re.findall(r'(\d+)', response)
        if len(coords) >= 2:
            bot.tap(int(coords[0]), int(coords[1]))
            time.sleep(1.5)

            # Look for gather button
            screenshot2 = bot.screenshot_b64()
            for btn_label in ["button_gather", "button_march", "button_go"]:
                btns = bot.yolo_find(btn_label, screenshot2)
                if btns:                    print(f"[CITY_RUSH] Tapping {btn_label}")
                    bot.tap(btns[0][0], btns[0][1])
                    time.sleep(1)
                    break
            else:
                # AI fallback for gather button
                prompt2 = (
                    "I tapped on a resource tile. Where is the Gather or March button? "
                    "Reply: tap: <x> <y> or none"
                )
                response2 = bot.ask_ai(prompt2, screenshot2)
                if "none" not in response2.lower():
                    coords2 = re.findall(r'(\d+)', response2)
                    if len(coords2) >= 2:
                        bot.tap(int(coords2[0]), int(coords2[1]))
                        time.sleep(1)

            # Confirm march if needed
            time.sleep(1)
            screenshot3 = bot.screenshot_b64()
            for label in ["button_march", "button_confirm", "button_go"]:
                btns = bot.yolo_find(label, screenshot3)
                if btns:
                    bot.tap(btns[0][0], btns[0][1])
                    time.sleep(1)
                    break

        # Return to city
        time.sleep(2)
        bot.go_to_city()
        time.sleep(1)

    def _tap_chief_hall_and_upgrade(self, bot):
        """Tap Chief Hall building and try to upgrade it"""
        bot.go_to_city()
        time.sleep(1)
        bot.tap(540, 700)
        time.sleep(1.5)
        self._tap_any_action_button(bot)

    # ═══════════════════════════════════════════════════════════════════
    # Phase 2: Growth (Lv 5-10)
    # ═══════════════════════════════════════════════════════════════════

    def _handle_growth_phase(self, bot):
        """Auto-upgrade Chief Hall with prerequisite handling."""
        if self._is_building_upgrading(bot):
            print("[CITY_RUSH] A building is upgrading - using speedups...")
            self._use_speedups(bot)
            time.sleep(3)
            return

        next_level = self.current_level + 1
        if next_level in CHIEF_HALL_REQUIREMENTS:
            reqs = CHIEF_HALL_REQUIREMENTS[next_level]
            prereq_met = self._check_and_upgrade_prerequisites(bot, reqs)
            if not prereq_met:
                return

        if self._upgrade_chief_hall(bot):
            self.upgrading_building = "Chief Hall"
            print(f"[CITY_RUSH] Chief Hall Lv{next_level} upgrade started!")
            time.sleep(2)
            return

        if self._check_resources_low(bot, next_level):
            self._gather_resources(bot)
            return

        time.sleep(3)

    # ═══════════════════════════════════════════════════════════════════
    # Phase 3: Rush (Lv 10-17)
    # ═══════════════════════════════════════════════════════════════════

    def _handle_rush_phase(self, bot):
        """Rush phase with aggressive speedup usage."""
        if self._is_building_upgrading(bot):
            print("[CITY_RUSH] Building upgrading - using speedups")
            self._use_speedups(bot)
            time.sleep(2)
            return

        next_level = self.current_level + 1
        if next_level in CHIEF_HALL_REQUIREMENTS:
            reqs = CHIEF_HALL_REQUIREMENTS[next_level]
            prereq_met = self._check_and_upgrade_prerequisites(bot, reqs)
            if not prereq_met:
                return

        if self._upgrade_chief_hall(bot):
            self.upgrading_building = "Chief Hall"
            print(f"[CITY_RUSH] Chief Hall Lv{next_level} upgrade started! (Rush)")
            self._use_speedups(bot)
            time.sleep(2)
            return

        if self._check_resources_low(bot, next_level):
            self._use_resource_items(bot)
            self._gather_resources(bot)            return

        time.sleep(3)

    # ═══════════════════════════════════════════════════════════════════
    # Prerequisite System
    # ═══════════════════════════════════════════════════════════════════

    def _check_and_upgrade_prerequisites(self, bot, reqs):
        """Check and upgrade prerequisite buildings. Returns True if all met."""
        for building_name, required_level in reqs["buildings"]:
            current_bldg_level = self._get_building_level(bot, building_name)

            if current_bldg_level is not None and current_bldg_level < required_level:
                print(f"[CITY_RUSH] Prereq: {building_name} Lv{current_bldg_level} -> Lv{required_level}")

                if self._navigate_to_building(bot, building_name):
                    if self._tap_upgrade_building(bot, building_name):
                        self.upgrading_building = building_name
                        print(f"[CITY_RUSH] Upgrading {building_name}")
                        time.sleep(2)
                    else:
                        self._handle_sub_prerequisites(bot, building_name, required_level)
                return False

        print("[CITY_RUSH] All prerequisites met!")
        return True

    def _get_building_level(self, bot, building_name):
        """Get current level of a building using AI"""
        screenshot = bot.screenshot_b64()
        aliases = BUILDING_ALIASES.get(building_name, [building_name.lower()])
        alias_list = ", ".join(aliases)

        prompt = (
            f"Look at this Viking Rise city. Find '{building_name}' "
            f"(also known as: {alias_list}). "
            f"What level is it? Reply ONLY a number like: 5"
        )
        response = bot.ask_ai(prompt, screenshot)
        numbers = re.findall(r'\b(\d{1,2})\b', response)
        if numbers:
            level = int(numbers[0])
            if 0 <= level <= 30:
                return level
        return None

    def _navigate_to_building(self, bot, building_name):
        """Navigate to and tap on a specific building"""
        screenshot = bot.screenshot_b64()
        aliases = BUILDING_ALIASES.get(building_name, [building_name.lower()])
        alias_list = ", ".join(aliases)

        prompt = (
            f"Find '{building_name}' (also: {alias_list}) in this city. "
            f"Reply: tap: <x> <y>"
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
        """Tap upgrade button for a selected building"""
        screenshot = bot.screenshot_b64()

        upgrade_btns = bot.yolo_find("button_upgrade", screenshot)
        if upgrade_btns:
            print(f"[CITY_RUSH] Upgrading {building_name}")
            bot.tap(upgrade_btns[0][0], upgrade_btns[0][1])
            time.sleep(1)

            screenshot2 = bot.screenshot_b64()
            confirm_btns = bot.yolo_find("button_confirm", screenshot2)
            if confirm_btns:
                bot.tap(confirm_btns[0][0], confirm_btns[0][1])
                time.sleep(1)
            return True

        prompt = (
            f"Where is the Upgrade button for {building_name}? "
            f"Reply: tap: <x> <y> or blocked"
        )
        response = bot.ask_ai(prompt, screenshot)
        if "blocked" in response.lower():
            return False

        coords = re.findall(r'(\d+)', response)
        if len(coords) >= 2:
            bot.tap(int(coords[0]), int(coords[1]))
            time.sleep(1.5)
            return True
        return False

    def _handle_sub_prerequisites(self, bot, building_name, target_level):
        """Handle sub-prerequisites for a building"""
        screenshot = bot.screenshot_b64()
        prompt = (
            f"Upgrading {building_name} is blocked. What requirement is shown? "
            f"Reply: requirement: <building_name> <level>"
        )
        response = bot.ask_ai(prompt, screenshot)
        print(f"[CITY_RUSH] Sub-prereq: {response}")

        match = re.search(r'requirement:\s*(\w[\w\s\']*?)\s+(\d+)', response, re.IGNORECASE)
        if match:
            sub_building = match.group(1).strip()
            sub_level = int(match.group(2))
            print(f"[CITY_RUSH] Sub-prerequisite: {sub_building} Lv{sub_level}")
            bot.key("back")
            time.sleep(1)
            if self._navigate_to_building(bot, sub_building):
                self._tap_upgrade_building(bot, sub_building)

    # ═══════════════════════════════════════════════════════════════════
    # Chief Hall Upgrade
    # ═══════════════════════════════════════════════════════════════════

    def _detect_chief_hall_level(self, bot):
        """Detect current Chief Hall level"""
        screenshot = bot.screenshot_b64()
        prompt = (
            "What level is the Chief Hall in this Viking Rise screen? "
            "Look for 'Lv.' text on or near the main building. "
            "Reply ONLY a number like: 3"
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
        bot.tap(540, 700)
        time.sleep(1.5)

        screenshot = bot.screenshot_b64()
        upgrade_btns = bot.yolo_find("button_upgrade", screenshot)
        if upgrade_btns:
            print("[CITY_RUSH] Chief Hall upgrade button found")
            bot.tap(upgrade_btns[0][0], upgrade_btns[0][1])
            time.sleep(1)

            screenshot2 = bot.screenshot_b64()
            confirm_btns = bot.yolo_find("button_confirm", screenshot2)
            if confirm_btns:
                bot.tap(confirm_btns[0][0], confirm_btns[0][1])
                time.sleep(1)
            return True

        prompt = (
            "Chief Hall panel is open. Where is Upgrade button? "
            "If blocked/greyed: blocked. Otherwise: tap: <x> <y>"
        )
        response = bot.ask_ai(prompt, screenshot)
        if "blocked" in response.lower():
            return False

        coords = re.findall(r'(\d+)', response)
        if len(coords) >= 2:
            bot.tap(int(coords[0]), int(coords[1]))
            time.sleep(1.5)
            return True

        return False

    # ═══════════════════════════════════════════════════════════════════
    # Resource & Speedup Management
    # ═══════════════════════════════════════════════════════════════════

    def _check_resources_low(self, bot, next_level):
        """Check if resources are too low"""
        if next_level not in CHIEF_HALL_REQUIREMENTS:
            return False
        reqs = CHIEF_HALL_REQUIREMENTS[next_level]
        screenshot = bot.screenshot_b64()
        prompt = (
            f"Resource bar at top: do I have at least "
            f"Food {reqs['food']:,}, Wood {reqs['wood']:,}, Stone {reqs['stone']:,}? "
            f"Reply: yes or no"
        )
        response = bot.ask_ai(prompt, screenshot)
        return "no" in response.lower()

    def _gather_resources(self, bot):
        """Send troops to gather resources"""
        print("[CITY_RUSH] Gathering resources...")        bot.tap(60, 600)
        time.sleep(2)

        screenshot = bot.screenshot_b64()
        prompt = (
            "World map: find nearest resource tile to gather from. "
            "Reply: tap: <x> <y>"
        )
        response = bot.ask_ai(prompt, screenshot)
        coords = re.findall(r'(\d+)', response)
        if len(coords) >= 2:
            bot.tap(int(coords[0]), int(coords[1]))
            time.sleep(1.5)

            screenshot2 = bot.screenshot_b64()
            for label in ["button_gather", "button_march", "button_go"]:
                btns = bot.yolo_find(label, screenshot2)
                if btns:
                    bot.tap(btns[0][0], btns[0][1])
                    time.sleep(1)
                    break

        bot.go_to_city()
        time.sleep(1)

    def _use_resource_items(self, bot):
        """Use resource items from inventory"""
        print("[CITY_RUSH] Using resource items...")
        bot.tap(80, 780)
        time.sleep(1.5)

        screenshot = bot.screenshot_b64()
        prompt = "Find Resources tab in inventory. Reply: tap: <x> <y>"
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
        """Use speedup items"""
        print("[CITY_RUSH] Using speedups...")
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

            prompt = "Speedup dialog: where to tap to use speedup? Reply: tap: <x> <y>"
            response = bot.ask_ai(prompt, screenshot2)
            coords = re.findall(r'(\d+)', response)
            if len(coords) >= 2:
                bot.tap(int(coords[0]), int(coords[1]))
                time.sleep(1)

    def _is_building_upgrading(self, bot):
        """Check if any building is currently upgrading"""
        screenshot = bot.screenshot_b64()
        prompt = (
            "Is a building being upgraded? Look for timer/construction. "
            "Reply: yes or no"
        )
        response = bot.ask_ai(prompt, screenshot)
        return "yes" in response.lower()

    # ═══════════════════════════════════════════════════════════════════
    # Popup Handling
    # ═══════════════════════════════════════════════════════════════════

    def _handle_popups(self, bot):
        """Handle random popups. Returns True if handled."""
        screenshot = bot.screenshot_b64()

        close_buttons = bot.yolo_find("button_close", screenshot)
        if close_buttons:
            for btn in close_buttons:                x, y = btn[0], btn[1]
                if x > 400 and y < 400:
                    print("[CITY_RUSH] Popup - closing")
                    bot.tap(x, y)
                    time.sleep(1)
                    return True

        return False

