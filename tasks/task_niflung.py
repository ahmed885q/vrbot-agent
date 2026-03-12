"""Task: Auto Kill Niflung — Continuous Loop
Runs every ~2 minutes until manually stopped.
Anti-ban: random delays between actions.
"""

import random
import time
from tasks.base_task import BaseTask

MAGNIFY_ICON = (155, 525)
NIFLUNG_CAT = (380, 655)
NIFLUNG_SEARCH = (380, 490)
ATTACK_BTN = (950, 510)
CREATE_BTN = (933, 173)
MARCH_BTN = (985, 640)

WAIT_BETWEEN_ATTACKS = 120  # 2 min
WAIT_RANDOM_EXTRA = (-15, 20)


class TaskNiflung(BaseTask):
    name = "Auto Kill Niflung"
    tag = "niflung"
    cooldown_hours = 0  # self-managed loop

    def __init__(self, bot):
        super().__init__(bot)
        self.total_kills = 0

    def _human_wait(self, base_min=2, base_max=4):
        self.bot.wait(random.uniform(base_min, base_max))

    def _ensure_world_map(self):
        bot = self.bot
        bot.adb_back()
        bot.wait(1)
        bot.go_to_city()
        bot.wait(2)
        if bot.go_to_world_map():
            return True
        bot.go_to_city()
        bot.wait(2)
        return bot.go_to_world_map()

    def _kill_one(self, kill_num):
        bot = self.bot
        self.total_kills += 1
        self.log.info(f"\n=== Attack #{kill_num} (total: {self.total_kills}) ===")

        # Open search panel
        bot.tap(MAGNIFY_ICON[0], MAGNIFY_ICON[1], jitter=False)
        self._human_wait(2.5, 4)

        # Select Niflung category
        bot.tap(NIFLUNG_CAT[0], NIFLUNG_CAT[1], jitter=False)
        self._human_wait(1.5, 3)

        # Search
        bot.tap(NIFLUNG_SEARCH[0], NIFLUNG_SEARCH[1], jitter=False)
        self._human_wait(5, 8)

        # Attack
        bot.tap(ATTACK_BTN[0], ATTACK_BTN[1], jitter=False)
        self._human_wait(2, 4)

        # Create
        bot.tap(CREATE_BTN[0], CREATE_BTN[1], jitter=False)
        self._human_wait(2, 4)

        # March
        bot.tap(MARCH_BTN[0], MARCH_BTN[1], jitter=False)
        self._human_wait(3, 5)

        # Verify
        s = bot.detect_screen()
        screen = s.get("screen", "").lower() if s else ""
        if "world" in screen or "city" in screen:
            self.log.info(f"✔ Attack #{kill_num} sent!")
            return True
        else:
            self.log.warning(f"⚠ Attack might have failed (screen: {screen})")
            bot.adb_back()
            bot.wait(2)
            return False

    def run(self):
        start_time = time.time()

        self.log.info("╔══════════════════════════════════════╗")
        self.log.info("║  Auto Niflung Killer Started         ║")
        self.log.info(f"║  Loop ~{WAIT_BETWEEN_ATTACKS}s | Stop: Ctrl+C        ║")
        self.log.info("╚══════════════════════════════════════╝")

        kill_num = 0
        while True:
            try:
                kill_num += 1

                if not self._ensure_world_map():
                    self.log.error("✗ Failed to reach world map, retrying...")
                    self.bot.wait(5)
                    continue

                self._kill_one(kill_num)

                # Wait between attacks
                extra = random.randint(*WAIT_RANDOM_EXTRA)
                wait_time = max(30, WAIT_BETWEEN_ATTACKS + extra)
                self.log.info(f"💤 Waiting {wait_time}s...")
                self.bot.go_to_city()
                self.bot.wait(wait_time)

            except KeyboardInterrupt:
                break
            except Exception as e:
                self.log.error(f"✗ Error: {e}")
                self.bot.go_to_city()
                self.bot.wait(10)

        elapsed = (time.time() - start_time) / 3600
        self.log.info(f"\n║  Stopped: {self.total_kills} kills in {elapsed:.1f}h  ║")
        self.bot.go_to_city()
        return True
