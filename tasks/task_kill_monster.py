"""Task: Auto Kill Monster — uses hybrid detection

v5.3 Rewrite:
  - Uses hybrid_find_button for attack/create/march buttons
  - YOLO for monster_icon, search_btn
  - Verify each step before proceeding
  - No infinite loop (runs KILLS_PER_CYCLE then exits)

Flow: World Map → Magnify → Monster → Search → Attack → Create → March
"""

import random
import time
from tasks.base_task import BaseTask

# Fallback coordinates (used if detection fails)
MAGNIFY_ICON = (155, 525)
MONSTER_CAT = (210, 655)
MONSTER_SEARCH = (210, 477)
ATTACK_POS = (950, 510)
CREATE_POS = (933, 173)
MARCH_POS = (985, 640)

KILLS_PER_CYCLE = 5
WAIT_BETWEEN_ATTACKS = 60


class TaskKillMonster(BaseTask):
    name = "Auto Kill Monster"
    tag = "kill_monster"
    cooldown_hours = 24

    def _ensure_world_map(self):
        bot = self.bot
        bot.go_to_city()
        bot.wait(2)
        if bot.go_to_world_map():
            return True
        bot.go_to_city()
        bot.wait(2)
        return bot.go_to_world_map()

    def _open_monster_search(self):
        """Open the monster search dialog."""
        bot = self.bot

        # Try YOLO for search icon / magnify
        for cls in ["search_icon", "search_btn", "search_btn_icon"]:
            result = bot.yolo_find(cls)
            if result:
                print(f"  [monster] YOLO found {cls}")
                bot.tap(result["x"], result["y"])
                bot.wait(2)
                return True

        # Fallback: magnify icon at known position
        print("  [monster] Using magnify fallback...")
        bot.tap(*MAGNIFY_ICON, jitter=False)
        bot.wait(2)
        return True

    def _select_monster(self):
        """Select monster category and search."""
        bot = self.bot

        # Try YOLO for monster_icon
        result = bot.yolo_find("monster_icon")
        if result:
            print(f"  [monster] YOLO found monster_icon")
            bot.tap(result["x"], result["y"])
        else:
            bot.tap(*MONSTER_CAT, jitter=False)
        bot.wait(2)

        # Search button
        result = bot.hybrid_find_button("search")
        if result and result.get("found"):
            bot.tap(result["x"], result["y"])
        else:
            bot.tap(*MONSTER_SEARCH, jitter=False)
        bot.wait(5)

    def _attack_monster(self):
        """Execute attack sequence: Attack → Create → March."""
        bot = self.bot

        # Step 1: Attack button
        result = bot.hybrid_find_button("attack")
        if result and result.get("found"):
            print(f"  [monster] Found Attack at ({result['x']},{result['y']})")
            bot.tap(result["x"], result["y"])
        else:
            print("  [monster] Attack fallback position")
            bot.tap(*ATTACK_POS, jitter=False)
        bot.wait(3)

        # Step 2: Create squad
        result = bot.hybrid_find_button("create")
        if result and result.get("found"):
            print(f"  [monster] Found Create at ({result['x']},{result['y']})")
            bot.tap(result["x"], result["y"])
        else:
            bot.tap(*CREATE_POS, jitter=False)
        bot.wait(3)

        # Step 3: March
        result = bot.hybrid_find_button("march")
        if result and result.get("found"):
            print(f"  [monster] Found March at ({result['x']},{result['y']})")
            bot.tap(result["x"], result["y"])
        else:
            bot.tap(*MARCH_POS, jitter=False)
        bot.wait(3)

        return True

    def _kill_one(self, kill_num):
        """Execute one full kill sequence."""
        bot = self.bot
        print(f"\n  [monster] === Attack #{kill_num}/{KILLS_PER_CYCLE} ===")

        # Open search
        self._open_monster_search()

        # Select monster + search
        self._select_monster()

        # Attack sequence
        success = self._attack_monster()

        # Verify we're back on map
        s = bot.detect_screen()
        screen = s.get("screen", "").lower() if s else ""
        if "world" in screen or "city" in screen:
            print(f"  [monster] ✔ Attack #{kill_num} sent!")
            return True
        else:
            print(f"  [monster] ⚠ Attack may have failed (screen: {screen})")
            bot.adb_back()
            bot.wait(2)
            return False

    def run(self):
        if not self._cooldown_ok():
            return True

        print(f"  [monster] Starting {KILLS_PER_CYCLE} kill cycle")
        successful = 0

        for i in range(1, KILLS_PER_CYCLE + 1):
            if not self._ensure_world_map():
                print("  [monster] ✗ Failed world map, retrying...")
                self.bot.wait(5)
                continue

            if self._kill_one(i):
                successful += 1

            if i < KILLS_PER_CYCLE:
                extra = random.randint(-10, 15)
                wait_time = max(30, WAIT_BETWEEN_ATTACKS + extra)
                print(f"  [monster] Waiting {wait_time}s...")
                self.bot.go_to_city()
                self.bot.wait(wait_time)

        self.bot.go_to_city()
        self._save_cooldown()
        print(f"  [monster] ✔ Cycle done: {successful}/{KILLS_PER_CYCLE} kills")
        return True
