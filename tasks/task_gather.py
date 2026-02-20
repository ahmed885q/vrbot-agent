"""Task: Auto Gather - Smart Scheduled Farming
Features:
- Sends 5 marches (farm, sawmill, quarry, goldmine, goldmine)
- Waits 2 HOURS then re-sends automatically
- Random delays between all actions (anti-ban)
- Human-like behavior patterns
- Configurable duration
"""

import random
import time

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

# Anti-ban delays (seconds)
DELAY_BETWEEN_MARCHES = (8, 15)     # between each march send
DELAY_ACTION_MIN = 1.5              # min delay between taps
DELAY_ACTION_MAX = 4.0              # max delay between taps

# Wait 5.5 hours between rounds (anti-detection)
WAIT_BETWEEN_ROUNDS_HOURS = 5.5

# Total auto-farm duration (hours)
AUTO_FARM_HOURS = 24
# ================================


def human_delay(min_s=DELAY_ACTION_MIN, max_s=DELAY_ACTION_MAX):
    return random.uniform(min_s, max_s)


class TaskGather:
    name = "Auto Gather (Scheduled)"

    def __init__(self, bot):
        self.bot = bot
        self.total_marches_sent = 0
        self.rounds_completed = 0

    def _random_tap(self, x, y, jitter=False):
        if jitter:
            x += random.randint(-3, 3)
            y += random.randint(-3, 3)
        self.bot.tap(x, y, jitter=False)

    def _human_wait(self, base_min=2, base_max=4):
        delay = random.uniform(base_min, base_max)
        self.bot.wait(delay)

    def _send_one_march(self, resource, march_num):
        bot = self.bot
        info = RESOURCES[resource]
        print(f"\n  [auto-gather] === March {march_num}/{MAX_MARCHES}: {resource} ===")

        # Step 1: Open search panel
        print("  [auto-gather] Opening search panel...")
        self._random_tap(MAGNIFY_ICON[0], MAGNIFY_ICON[1])
        self._human_wait(2.5, 4)

        # Step 2: Select resource category
        cx, cy = info["cat"]
        print(f"  [auto-gather] Selecting {resource}...")
        self._random_tap(cx, cy, jitter=True)
        self._human_wait(1.5, 3)

        # Step 3: Search — NO jitter
        sx, sy = info["search"]
        print(f"  [auto-gather] Tapping Search ({sx},{sy})...")
        self._random_tap(sx, sy)
        self._human_wait(5, 8)

        # Step 4: Gather
        print(f"  [auto-gather] Tapping Gather...")
        self._random_tap(GATHER_BTN[0], GATHER_BTN[1])
        self._human_wait(2, 4)

        # Step 5: Create
        print(f"  [auto-gather] Tapping Create...")
        self._random_tap(CREATE_BTN[0], CREATE_BTN[1])
        self._human_wait(2, 4)

        # Step 6: March
        print(f"  [auto-gather] Tapping March...")
        self._random_tap(MARCH_BTN[0], MARCH_BTN[1])
        self._human_wait(3, 5)

        self.total_marches_sent += 1
        print(f"  [auto-gather] ✔ March {march_num} sent! (Total: {self.total_marches_sent})")
        return True

    def _send_all_marches(self):
        bot = self.bot
        sent = 0

        for i, resource in enumerate(MARCH_ORDER):
            march_num = i + 1
            try:
                self._send_one_march(resource, march_num)
                sent += 1
            except Exception as e:
                print(f"  [auto-gather] ✗ March {march_num} failed: {e}")
                bot.adb_back()
                self._human_wait(2, 4)

            if i < len(MARCH_ORDER) - 1:
                delay = random.uniform(*DELAY_BETWEEN_MARCHES)
                print(f"  [auto-gather] Waiting {delay:.0f}s before next march...")
                bot.wait(delay)

        self.rounds_completed += 1
        print(f"\n  [auto-gather] === Round {self.rounds_completed}: {sent}/{MAX_MARCHES} marches sent ===")
        return sent

    def _long_wait(self):
        """Wait ~2 hours with periodic human-like activity."""
        bot = self.bot
        wait_seconds = WAIT_BETWEEN_ROUNDS_HOURS * 3600
        # Add random ±10 minutes for unpredictability
        wait_seconds += random.randint(-600, 600)

        print(f"  [auto-gather] 💤 Sleeping ~{WAIT_BETWEEN_ROUNDS_HOURS}h ({wait_seconds//60} min) until next round...")

        bot.go_to_city()
        start = time.time()

        while (time.time() - start) < wait_seconds:
            remaining = wait_seconds - (time.time() - start)
            remaining_min = remaining / 60
            print(f"  [auto-gather] ⏱ {remaining_min:.0f} min remaining...")

            # Sleep in chunks of 10-15 minutes
            chunk = random.uniform(600, 900)
            chunk = min(chunk, remaining)
            bot.wait(chunk)

            # Every ~12 min: random human activity (anti-AFK detection)
            if remaining > 120 and random.random() < 0.4:
                print("  [auto-gather] 👆 Anti-AFK: random activity...")
                bot.tap(random.randint(400, 800), random.randint(200, 400), jitter=False)
                bot.wait(random.uniform(2, 5))

        print(f"  [auto-gather] ✔ Wait complete, starting new round!")

    def run(self):
        bot = self.bot
        start_time = time.time()
        max_duration = AUTO_FARM_HOURS * 3600

        print(f"  [auto-gather] ╔══════════════════════════════════════╗")
        print(f"  [auto-gather] ║  Auto Gather Started ({AUTO_FARM_HOURS}h)          ║")
        print(f"  [auto-gather] ║  Order: farm→sawmill→quarry→gold×2  ║")
        print(f"  [auto-gather] ║  Wait: {WAIT_BETWEEN_ROUNDS_HOURS}h between rounds            ║")
        print(f"  [auto-gather] ╚══════════════════════════════════════╝")

        bot.go_to_city()
        bot.wait(1)

        if not bot.go_to_world_map():
            bot.go_to_city()
            return False

        # === Round 1: Send initial 5 marches ===
        self._send_all_marches()

        # === Auto loop: wait 2h → re-send ===
        while (time.time() - start_time) < max_duration:
            elapsed_h = (time.time() - start_time) / 3600
            remaining_h = AUTO_FARM_HOURS - elapsed_h
            print(f"\n  [auto-gather] ⏱ Elapsed: {elapsed_h:.1f}h | Remaining: {remaining_h:.1f}h | Total sent: {self.total_marches_sent}")

            if remaining_h < 0.1:
                break

            # Wait 2 hours
            self._long_wait()

            # Check time
            if (time.time() - start_time) >= max_duration:
                break

            # Re-send all marches
            print("  [auto-gather] 🔄 Starting new gather round...")
            if not bot.go_to_world_map():
                bot.go_to_city()
                self._human_wait(5, 10)
                continue

            self._send_all_marches()

        # === Done ===
        elapsed = (time.time() - start_time) / 3600
        print(f"\n  [auto-gather] ╔══════════════════════════════════════╗")
        print(f"  [auto-gather] ║  Auto Gather Complete!               ║")
        print(f"  [auto-gather] ║  Duration: {elapsed:.1f}h                      ║")
        print(f"  [auto-gather] ║  Rounds: {self.rounds_completed}                           ║")
        print(f"  [auto-gather] ║  Total marches: {self.total_marches_sent}                    ║")
        print(f"  [auto-gather] ╚══════════════════════════════════════╝")

        bot.go_to_city()
        return True
