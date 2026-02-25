"""Task: Auto Kill Monster — 5 kills every 24 hours
Flow: Magnify → Monster → Search → Attack → Create → March
Cooldown: 24 hours after 5 kills.
"""

import random
import time
from tasks.base_task import BaseTask

MAGNIFY_ICON = (155, 525)
MONSTER_CAT = (210, 655)
MONSTER_SEARCH = (210, 477)
ATTACK_BTN = (950, 510)
CREATE_BTN = (933, 173)
MARCH_BTN = (985, 640)

KILLS_PER_CYCLE = 5
COOLDOWN_HOURS = 24
WAIT_BETWEEN_ATTACKS = 60
WAIT_RANDOM_EXTRA = (-10, 15)


class TaskKillMonster(BaseTask):
    name = "Auto Kill Monster"
    tag = "kill_monster"
    cooldown_hours = 0  # self-managed

    def __init__(self, bot):
        super().__init__(bot)
        self.total_kills = 0
        self.cycles = 0

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
        print(f"\n  [monster] === Attack #{kill_num}/{KILLS_PER_CYCLE} (total: {self.total_kills}) ===")

        bot.tap(MAGNIFY_ICON[0], MAGNIFY_ICON[1], jitter=False)
        self._human_wait(2.5, 4)

        bot.tap(MONSTER_CAT[0], MONSTER_CAT[1], jitter=False)
        self._human_wait(1.5, 3)

        bot.tap(MONSTER_SEARCH[0], MONSTER_SEARCH[1], jitter=False)
        self._human_wait(5, 8)

        bot.tap(ATTACK_BTN[0], ATTACK_BTN[1], jitter=False)
        self._human_wait(2, 4)

        bot.tap(CREATE_BTN[0], CREATE_BTN[1], jitter=False)
        self._human_wait(2, 4)

        bot.tap(MARCH_BTN[0], MARCH_BTN[1], jitter=False)
        self._human_wait(3, 5)

        # Verify
        s = bot.detect_screen()
        screen = s.get("screen", "").lower() if s else ""
        if "world" in screen or "city" in screen:
            print(f"  [monster] ✔ Attack #{kill_num} sent!")
            return True
        else:
            print(f"  [monster] ⚠ Attack might have failed (screen: {screen})")
            bot.adb_back()
            bot.wait(2)
            return False

    def run(self):
        start_time = time.time()

        print(f"  [monster] ╔══════════════════════════════════════╗")
        print(f"  [monster] ║  Auto Monster Killer Started         ║")
        print(f"  [monster] ║  {KILLS_PER_CYCLE} kills / {COOLDOWN_HOURS}h cycle                 ║")
        print(f"  [monster] ╚══════════════════════════════════════╝")

        while True:
            try:
                self.cycles += 1
                print(f"\n  [monster] ── Cycle #{self.cycles} ──")
                successful = 0

                for i in range(1, KILLS_PER_CYCLE + 1):
                    if not self._ensure_world_map():
                        print("  [monster] ✗ Failed world map, retrying...")
                        self.bot.wait(5)
                        continue

                    if self._kill_one(i):
                        successful += 1

                    if i < KILLS_PER_CYCLE:
                        extra = random.randint(*WAIT_RANDOM_EXTRA)
                        wait_time = max(30, WAIT_BETWEEN_ATTACKS + extra)
                        print(f"  [monster] 💤 Waiting {wait_time}s...")
                        self.bot.go_to_city()
                        self.bot.wait(wait_time)

                elapsed_h = (time.time() - start_time) / 3600
                print(f"\n  [monster] ✔ Cycle #{self.cycles}: {successful}/{KILLS_PER_CYCLE} kills")
                print(f"  [monster] 💤 Cooldown: {COOLDOWN_HOURS}h...")

                self.bot.go_to_city()
                self.bot.wait(COOLDOWN_HOURS * 3600)

            except KeyboardInterrupt:
                break
            except Exception as e:
                print(f"  [monster] ✗ Error: {e}")
                self.bot.go_to_city()
                self.bot.wait(10)

        elapsed = (time.time() - start_time) / 3600
        print(f"\n  [monster] Stopped: {self.total_kills} kills, {self.cycles} cycles, {elapsed:.1f}h")
        self.bot.go_to_city()
        return True
