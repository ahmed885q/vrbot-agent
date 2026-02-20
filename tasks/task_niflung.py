"""Task: Auto Kill Niflung - Continuous Loop
Runs every ~1 minute until manually stopped.
Anti-ban: random delays between actions.
"""

import random
import time

MAGNIFY_ICON = (155, 525)
NIFLUNG_CAT = (380, 655)
NIFLUNG_SEARCH = (380, 490)
ATTACK_BTN = (950, 462)
CREATE_BTN = (940, 170)
MARCH_BTN = (985, 640)

# ============ CONFIG ============
WAIT_BETWEEN_ATTACKS = 60        # 1 minute between each attack
WAIT_RANDOM_EXTRA = (-10, 15)    # ±random seconds for anti-ban
# ================================


class TaskNiflung:
    name = "Auto Kill Niflung"

    def __init__(self, bot):
        self.bot = bot
        self.total_kills = 0

    def _human_wait(self, base_min=2, base_max=4):
        delay = random.uniform(base_min, base_max)
        self.bot.wait(delay)

    def _ensure_world_map(self):
        """Reliably get to world map: city first, then world map."""
        bot = self.bot

        # Close any popups with single back
        bot.adb_back()
        bot.wait(1)

        # Go to city (clean state)
        bot.go_to_city()
        bot.wait(2)

        # Now go to world map
        if not bot.go_to_world_map():
            # Retry once
            print("  [niflung] Retry: go_to_world_map...")
            bot.go_to_city()
            bot.wait(2)
            if not bot.go_to_world_map():
                return False
        bot.wait(2)
        return True

    def _kill_one(self):
        """Send one Niflung attack march."""
        bot = self.bot
        self.total_kills += 1
        print(f"\n  [niflung] === Attack #{self.total_kills} ===")

        # Step 1: Open search panel
        print("  [niflung] Opening search panel...")
        bot.tap(MAGNIFY_ICON[0], MAGNIFY_ICON[1], jitter=False)
        self._human_wait(2.5, 4)

        # Step 2: Select Niflung category
        print("  [niflung] Selecting Niflung...")
        bot.tap(NIFLUNG_CAT[0], NIFLUNG_CAT[1], jitter=False)
        self._human_wait(1.5, 3)

        # Step 3: Search
        print("  [niflung] Tapping Search...")
        bot.tap(NIFLUNG_SEARCH[0], NIFLUNG_SEARCH[1], jitter=False)
        self._human_wait(5, 8)

        # Step 4: Attack
        print("  [niflung] Tapping Attack...")
        bot.tap(ATTACK_BTN[0], ATTACK_BTN[1], jitter=False)
        self._human_wait(2, 4)

        # Step 5: Create
        print("  [niflung] Tapping Create...")
        bot.tap(CREATE_BTN[0], CREATE_BTN[1], jitter=False)
        self._human_wait(2, 4)

        # Step 6: March
        print("  [niflung] Tapping March...")
        bot.tap(MARCH_BTN[0], MARCH_BTN[1], jitter=False)
        self._human_wait(3, 5)

        print(f"  [niflung] ✔ Attack #{self.total_kills} sent!")
        return True

    def run(self):
        bot = self.bot
        start_time = time.time()

        print(f"  [niflung] ╔══════════════════════════════════════╗")
        print(f"  [niflung] ║  Auto Niflung Killer Started         ║")
        print(f"  [niflung] ║  Interval: ~1 min | Stop: Ctrl+C    ║")
        print(f"  [niflung] ╚══════════════════════════════════════╝")

        while True:
            try:
                # Get to world map reliably
                if not self._ensure_world_map():
                    print("  [niflung] ✗ Failed to reach world map, retrying...")
                    bot.wait(5)
                    continue

                # Send attack
                self._kill_one()

                # Wait ~1 minute
                extra = random.randint(*WAIT_RANDOM_EXTRA)
                wait_time = WAIT_BETWEEN_ATTACKS + extra
                elapsed_h = (time.time() - start_time) / 3600

                print(f"\n  [niflung] ⏱ Total kills: {self.total_kills} | Running: {elapsed_h:.1f}h")
                print(f"  [niflung] 💤 Waiting {wait_time}s before next attack...")

                # Go to city during wait
                bot.go_to_city()
                bot.wait(wait_time)

            except KeyboardInterrupt:
                break
            except Exception as e:
                print(f"  [niflung] ✗ Error: {e}")
                bot.go_to_city()
                bot.wait(10)

        # Final stats
        elapsed = (time.time() - start_time) / 3600
        print(f"\n  [niflung] ╔══════════════════════════════════════╗")
        print(f"  [niflung] ║  Auto Niflung Stopped                ║")
        print(f"  [niflung] ║  Total kills: {self.total_kills:<24}║")
        print(f"  [niflung] ║  Duration: {elapsed:.1f}h{' '*(23-len(f'{elapsed:.1f}h'))}║")
        print(f"  [niflung] ╚══════════════════════════════════════╝")

        bot.go_to_city()
        return True
