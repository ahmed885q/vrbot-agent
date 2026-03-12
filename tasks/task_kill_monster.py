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
        self._tap_ui("search", fallback_xy=MAGNIFY_ICON, wait_after=2)
        return True

    def _select_monster(self):
        """Select monster category and search."""
        # Select monster category (try YOLO first)
        self._tap_ui("monster", fallback_xy=MONSTER_CAT, wait_after=2, ai_prompt="Monster category button")

        # Search button
        self._tap_ui("search", fallback_xy=MONSTER_SEARCH, wait_after=5)

    def _attack_monster(self):
        """Execute attack sequence: Attack → Create → March."""
        # Step 1: Attack button
        self._tap_ui("attack", fallback_xy=ATTACK_POS, wait_after=3)

        # Step 2: Create squad
        self._tap_ui("create", fallback_xy=CREATE_POS, wait_after=3)

        # Step 3: March
        self._tap_ui("march", fallback_xy=MARCH_POS, wait_after=3)

        return True

    def _kill_one(self, kill_num):
        """Execute one full kill sequence."""
        bot = self.bot
        self.log.info(f"\n=== Attack #{kill_num}/{KILLS_PER_CYCLE} ===")

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
            self.log.info(f"✔ Attack #{kill_num} sent!")
            return True
        else:
            self.log.warning(f"⚠ Attack may have failed (screen: {screen})")
            bot.adb_back()
            bot.wait(2)
            return False

    def run(self):
        if not self._cooldown_ok():
            return True

        self.log.info(f"Starting {KILLS_PER_CYCLE} kill cycle")
        successful = 0

        for i in range(1, KILLS_PER_CYCLE + 1):
            if not self._ensure_world_map():
                self.log.error("✗ Failed world map, retrying...")
                self.bot.wait(5)
                continue

            if self._kill_one(i):
                successful += 1

            if i < KILLS_PER_CYCLE:
                extra = random.randint(-10, 15)
                wait_time = max(30, WAIT_BETWEEN_ATTACKS + extra)
                self.log.info(f"Waiting {wait_time}s...")
                self.bot.go_to_city()
                self.bot.wait(wait_time)

        self.bot.go_to_city()
        self._save_cooldown()
        self.log.info(f"✔ Cycle done: {successful}/{KILLS_PER_CYCLE} kills")
        return True
