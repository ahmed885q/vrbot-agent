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

MAGNIFY_ICON = (155, 525)

RESOURCES = {
    "farm":     {"cat": (555, 655), "search": (555, 490)},
    "sawmill":  {"cat": (725, 655), "search": (725, 490)},
    "quarry":   {"cat": (890, 655), "search": (890, 490)},
    "goldmine": {"cat": (1060, 655), "search": (1060, 490)},
}

GATHER_BTN = (1075, 485)
CREATE_BTN = (940, 170)
MARCH_BTN  = (960, 615)

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
        print(f"\n  [gather] === March {march_num}/{MAX_MARCHES}: {resource} ===")

        # Step 1: Open search panel
        print("  [gather] Opening search panel...")
        bot.tap(MAGNIFY_ICON[0], MAGNIFY_ICON[1], jitter=False)
        self._human_wait(2.5, 4)

        # Step 2: Select resource category
        cx, cy = info["cat"]
        print(f"  [gather] Selecting {resource}...")
        bot.tap(cx, cy, jitter=True)
        self._human_wait(1.5, 3)

        # Step 3: Search
        sx, sy = info["search"]
        print(f"  [gather] Tapping Search ({sx},{sy})...")
        bot.tap(sx, sy, jitter=False)
        self._human_wait(5, 8)

        # Step 4: Gather
        print("  [gather] Tapping Gather...")
        bot.tap(GATHER_BTN[0], GATHER_BTN[1], jitter=False)
        self._human_wait(2, 4)

        # Step 5: Create
        print("  [gather] Tapping Create...")
        bot.tap(CREATE_BTN[0], CREATE_BTN[1], jitter=False)
        self._human_wait(2, 4)

        # Step 6: March
        print("  [gather] Tapping March...")
        bot.tap(MARCH_BTN[0], MARCH_BTN[1], jitter=False)
        self._human_wait(3, 5)

        # Step 7: Verify — check we're back on world map (march sent)
        s = bot.detect_screen()
        screen = s.get("screen", "").lower() if s else ""
        if "world" in screen or "city" in screen:
            self.total_marches_sent += 1
            print(f"  [gather] ✔ March #{march_num} sent! (total: {self.total_marches_sent})")
            return True
        else:
            print(f"  [gather] ⚠ March might have failed (screen: {screen})")
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
                print("  [gather] ✗ Failed to reach world map")
                bot.wait(5)
                continue

            if self._send_one_march(resource, i):
                successful += 1

            if i < len(MARCH_ORDER):
                wait = random.uniform(*DELAY_BETWEEN_MARCHES)
                print(f"  [gather] Waiting {wait:.0f}s before next march...")
                bot.wait(wait)

        return successful

    def run(self):
        start_time = time.time()
        auto_farm_seconds = AUTO_FARM_HOURS * 3600
        wait_seconds = WAIT_BETWEEN_ROUNDS_HOURS * 3600

        print(f"  [gather] ╔══════════════════════════════════════╗")
        print(f"  [gather] ║  Auto Gather Started                 ║")
        print(f"  [gather] ║  {MAX_MARCHES} marches / {WAIT_BETWEEN_ROUNDS_HOURS}h cycle          ║")
        print(f"  [gather] ╚══════════════════════════════════════╝")

        while (time.time() - start_time) < auto_farm_seconds:
            try:
                self.rounds_completed += 1
                print(f"\n  [gather] ── Round #{self.rounds_completed} ──")

                successful = self._send_round()
                print(f"  [gather] ✔ Round done: {successful}/{MAX_MARCHES} marches sent")

                self.bot.go_to_city()

                elapsed_h = (time.time() - start_time) / 3600
                remaining_h = AUTO_FARM_HOURS - elapsed_h
                if remaining_h <= 0:
                    break

                wait_h = min(WAIT_BETWEEN_ROUNDS_HOURS, remaining_h)
                print(f"  [gather] 💤 Next round in {wait_h:.1f}h (total: {elapsed_h:.1f}h)")
                self.bot.wait(wait_h * 3600)

            except KeyboardInterrupt:
                break
            except Exception as e:
                print(f"  [gather] ✗ Error: {e}")
                self.bot.go_to_city()
                self.bot.wait(30)

        elapsed = (time.time() - start_time) / 3600
        print(f"\n  [gather] ╔══════════════════════════════════════╗")
        print(f"  [gather] ║  Auto Gather Complete                ║")
        print(f"  [gather] ║  Rounds: {self.rounds_completed:<29}║")
        print(f"  [gather] ║  Marches: {self.total_marches_sent:<28}║")
        print(f"  [gather] ║  Duration: {elapsed:.1f}h{' '*(23-len(f'{elapsed:.1f}h'))}║")
        print(f"  [gather] ╚══════════════════════════════════════╝")

        self.bot.go_to_city()
        return True
