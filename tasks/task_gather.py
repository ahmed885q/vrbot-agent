"""Task: Auto Gather — Smart Scheduled Farming
Features:
- Sends 5 marches (farm, sawmill, quarry, goldmine, goldmine)
- Waits 5.5 HOURS then re-sends automatically
- Random delays between all actions (anti-ban)
- Verifies world map before each march
"""

import random
import time
from tasks.base_task import BaseTask

# Fallback coordinates (used if hybrid_find_button fails)
FALLBACK = {
    "magnify_icon": (155, 525),
    "gather_btn": (1075, 485),
    "create_btn": (940, 170),
    "march_btn": (960, 615),
}

RESOURCES = {
    "farm":     {"cat": (555, 655), "search": (555, 490)},
    "sawmill":  {"cat": (725, 655), "search": (725, 490)},
    "quarry":   {"cat": (890, 655), "search": (890, 490)},
    "goldmine": {"cat": (1060, 655), "search": (1060, 490)},
}

# ============ CONFIG ============
MARCH_ORDER = ["farm", "sawmill", "quarry", "goldmine", "goldmine"]
MAX_MARCHES = 5
DELAY_BETWEEN_MARCHES = (8, 15)
DELAY_ACTION_MIN = 1.5
DELAY_ACTION_MAX = 4.0
WAIT_BETWEEN_ROUNDS_HOURS = 5.5
AUTO_FARM_HOURS = 24
# ================================


class TaskGather(BaseTask):
    name = "Auto Gather (Scheduled)"
    tag = "gather"
    cooldown_hours = 0  # self-managed loop

    def __init__(self, bot):
        super().__init__(bot)
        self.total_marches_sent = 0
        self.rounds_completed = 0

    def _human_wait(self, base_min=2, base_max=4):
        self.bot.wait(random.uniform(base_min, base_max))

    def _ensure_world_map(self):
        """Reliably get to world map."""
        bot = self.bot
        bot.go_to_city()
        bot.wait(2)
        if bot.go_to_world_map():
            return True
        bot.go_to_city()
        bot.wait(2)
        return bot.go_to_world_map()

    def _send_one_march(self, resource, march_num):
        bot = self.bot
        info = RESOURCES[resource]
        self.log.info(f"\n=== March {march_num}/{MAX_MARCHES}: {resource} ===")

        # Step 1: Open search panel
        self.log.info("Opening search panel...")
        self._tap_ui("search", fallback_xy=FALLBACK["magnify_icon"], wait_after=3)
        self._human_wait(2.5, 4)

        # Step 2: Select resource category
        cx, cy = info["cat"]
        self.log.info(f"Selecting {resource}...")
        self._tap_ui(None, fallback_xy=(cx, cy), ai_prompt=f"Tap the {resource} category tab", jitter=True, wait_after=1)
        self._human_wait(1.5, 3)

        # Step 3: Search
        sx, sy = info["search"]
        self.log.info(f"Tapping Search ({sx},{sy})...")
        self._tap_ui("search", fallback_xy=(sx, sy), wait_after=3)
        self._human_wait(5, 8)

        # Step 4: Gather
        self.log.info("Tapping Gather...")
        self._tap_ui("gather", fallback_xy=FALLBACK["gather_btn"], wait_after=3)
        self._human_wait(2, 4)

        # Step 5: Create
        self.log.info("Tapping Create...")
        self._tap_ui("create", fallback_xy=FALLBACK["create_btn"], wait_after=3)
        self._human_wait(2, 4)

        # Step 6: March
        self.log.info("Tapping March...")
        self._tap_ui("march", fallback_xy=FALLBACK["march_btn"], wait_after=3)
        self._human_wait(3, 5)

        # Step 7: Verify — check we're back on world map (march sent)
        s = bot.detect_screen()
        screen = s.get("screen", "").lower() if s else ""
        if "world" in screen or "city" in screen:
            self.total_marches_sent += 1
            self.log.info(f"✔ March #{march_num} sent! (total: {self.total_marches_sent})")
            return True
        else:
            self.log.warning(f"⚠ March might have failed (screen: {screen})")
            # Try dismissing any popup
            bot.adb_back()
            bot.wait(2)
            return False

    def _send_round(self):
        """Send all 5 marches."""
        bot = self.bot
        successful = 0
        for i, resource in enumerate(MARCH_ORDER, 1):
            if not self._ensure_world_map():
                self.log.error("✗ Failed to reach world map")
                bot.wait(5)
                continue

            if self._send_one_march(resource, i):
                successful += 1

            if i < len(MARCH_ORDER):
                wait = random.uniform(*DELAY_BETWEEN_MARCHES)
                self.log.info(f"Waiting {wait:.0f}s before next march...")
                bot.wait(wait)

        return successful

    def run(self):
        start_time = time.time()
        auto_farm_seconds = AUTO_FARM_HOURS * 3600
        wait_seconds = WAIT_BETWEEN_ROUNDS_HOURS * 3600

        self.log.info("╔══════════════════════════════════════╗")
        self.log.info("║  Auto Gather Started                 ║")
        self.log.info(f"║  {MAX_MARCHES} marches / {WAIT_BETWEEN_ROUNDS_HOURS}h cycle          ║")
        self.log.info("╚══════════════════════════════════════╝")

        while (time.time() - start_time) < auto_farm_seconds:
            try:
                self.rounds_completed += 1
                self.log.info(f"\n── Round #{self.rounds_completed} ──")

                successful = self._send_round()
                self.log.info(f"✔ Round done: {successful}/{MAX_MARCHES} marches sent")

                self.bot.go_to_city()

                elapsed_h = (time.time() - start_time) / 3600
                remaining_h = AUTO_FARM_HOURS - elapsed_h
                if remaining_h <= 0:
                    break

                wait_h = min(WAIT_BETWEEN_ROUNDS_HOURS, remaining_h)
                self.log.info(f"💤 Next round in {wait_h:.1f}h (total: {elapsed_h:.1f}h)")
                self.bot.wait(wait_h * 3600)

            except KeyboardInterrupt:
                break
            except Exception as e:
                self.log.error(f"✗ Error: {e}")
                self.bot.go_to_city()
                self.bot.wait(30)

        elapsed = (time.time() - start_time) / 3600
        self.log.info("\n╔══════════════════════════════════════╗")
        self.log.info("║  Auto Gather Complete                ║")
        self.log.info(f"║  Rounds: {self.rounds_completed:<29}║")
        self.log.info(f"║  Marches: {self.total_marches_sent:<28}║")
        self.log.info(f"║  Duration: {elapsed:.1f}h{' '*(23-len(f'{elapsed:.1f}h'))}║")
        self.log.info("╚══════════════════════════════════════╝")

        self.bot.go_to_city()
        return True
