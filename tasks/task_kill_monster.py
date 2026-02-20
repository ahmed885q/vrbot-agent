"""Task: Auto Kill Monster - 5 kills every 24 hours
Flow: Magnify → Monster → Search → Attack → Create → March
No level selector needed - just Search directly.
Cooldown: 24 hours after 5 kills.
"""

import random
import time

MAGNIFY_ICON = (155, 525)
MONSTER_CAT = (210, 655)
MONSTER_SEARCH = (210, 477)
ATTACK_BTN = (950, 510)
CREATE_BTN = (933, 173)
MARCH_BTN = (985, 640)

# ============ CONFIG ============
KILLS_PER_CYCLE = 5              # 5 kills per daily cycle
COOLDOWN_HOURS = 24              # Wait 24h after completing 5 kills
WAIT_BETWEEN_ATTACKS = 60        # 1 minute between each attack
WAIT_RANDOM_EXTRA = (-10, 15)    # ±random seconds for anti-ban
# ================================


class TaskKillMonster:
    name = "Auto Kill Monster"

    def __init__(self, bot):
        self.bot = bot
        self.total_kills = 0
        self.cycles = 0

    def _human_wait(self, base_min=2, base_max=4):
        delay = random.uniform(base_min, base_max)
        self.bot.wait(delay)

    def _ensure_world_map(self):
        """Reliably get to world map: city first, then world map."""
        bot = self.bot
        bot.adb_back()
        bot.wait(1)
        bot.go_to_city()
        bot.wait(2)
        if not bot.go_to_world_map():
            print("  [monster] Retry: go_to_world_map...")
            bot.go_to_city()
            bot.wait(2)
            if not bot.go_to_world_map():
                return False
        bot.wait(2)
        return True

    def _kill_one(self, kill_num):
        """Send one Monster attack march."""
        bot = self.bot
        self.total_kills += 1
        print(f"\n  [monster] === Attack #{kill_num}/{KILLS_PER_CYCLE} (total: {self.total_kills}) ===")

        # Step 1: Open search panel
        print("  [monster] Opening search panel...")
        bot.tap(MAGNIFY_ICON[0], MAGNIFY_ICON[1], jitter=False)
        self._human_wait(2.5, 4)

        # Step 2: Select Monster category
        print("  [monster] Selecting Monster...")
        bot.tap(MONSTER_CAT[0], MONSTER_CAT[1], jitter=False)
        self._human_wait(1.5, 3)

        # Step 3: Search
        print("  [monster] Tapping Search...")
        bot.tap(MONSTER_SEARCH[0], MONSTER_SEARCH[1], jitter=False)
        self._human_wait(5, 8)

        # Step 4: Attack
        print("  [monster] Tapping Attack...")
        bot.tap(ATTACK_BTN[0], ATTACK_BTN[1], jitter=False)
        self._human_wait(2, 4)

        # Step 5: Create
        print("  [monster] Tapping Create...")
        bot.tap(CREATE_BTN[0], CREATE_BTN[1], jitter=False)
        self._human_wait(2, 4)

        # Step 6: March
        print("  [monster] Tapping March...")
        bot.tap(MARCH_BTN[0], MARCH_BTN[1], jitter=False)
        self._human_wait(3, 5)

        print(f"  [monster] ✔ Attack #{kill_num} sent!")
        return True

    def run(self):
        bot = self.bot
        start_time = time.time()

        print(f"  [monster] ╔══════════════════════════════════════╗")
        print(f"  [monster] ║  Auto Monster Killer Started         ║")
        print(f"  [monster] ║  {KILLS_PER_CYCLE} kills / 24h cycle | Stop: Ctrl+C  ║")
        print(f"  [monster] ╚══════════════════════════════════════╝")

        while True:
            try:
                self.cycles += 1
                print(f"\n  [monster] ── Cycle #{self.cycles} ──")

                # Do 5 kills
                for i in range(1, KILLS_PER_CYCLE + 1):
                    if not self._ensure_world_map():
                        print("  [monster] ✗ Failed to reach world map, retrying...")
                        bot.wait(5)
                        continue

                    self._kill_one(i)

                    # Wait between attacks (except after last kill)
                    if i < KILLS_PER_CYCLE:
                        extra = random.randint(*WAIT_RANDOM_EXTRA)
                        wait_time = WAIT_BETWEEN_ATTACKS + extra
                        print(f"  [monster] 💤 Waiting {wait_time}s before next attack...")
                        bot.go_to_city()
                        bot.wait(wait_time)

                # Cycle done — wait 24 hours
                elapsed_h = (time.time() - start_time) / 3600
                cooldown_s = COOLDOWN_HOURS * 3600
                print(f"\n  [monster] ✅ Cycle #{self.cycles} done! {KILLS_PER_CYCLE} kills sent")
                print(f"  [monster] ⏱ Total kills: {self.total_kills} | Running: {elapsed_h:.1f}h")
                print(f"  [monster] 💤 Cooldown: {COOLDOWN_HOURS}h until next cycle...")

                bot.go_to_city()
                bot.wait(cooldown_s)

            except KeyboardInterrupt:
                break
            except Exception as e:
                print(f"  [monster] ✗ Error: {e}")
                bot.go_to_city()
                bot.wait(10)

        # Final stats
        elapsed = (time.time() - start_time) / 3600
        print(f"\n  [monster] ╔══════════════════════════════════════╗")
        print(f"  [monster] ║  Auto Monster Killer Stopped         ║")
        print(f"  [monster] ║  Cycles: {self.cycles:<29}║")
        print(f"  [monster] ║  Total kills: {self.total_kills:<24}║")
        print(f"  [monster] ║  Duration: {elapsed:.1f}h{' '*(23-len(f'{elapsed:.1f}h'))}║")
        print(f"  [monster] ╚══════════════════════════════════════╝")

        bot.go_to_city()
        return True
