"""Task: Tribe Technology - Donate 20 times (once per 24h)
Flow: City → Alliance → Technology → select tech → Donate x20
Cooldown: Runs once then skips until 24 hours pass
"""

import random
import time
import os
import json

# City → Alliance button
ALLIANCE_BTN = (1100, 685)

# Tribe screen → Technology icon (partially visible at right edge)
TECH_ICON = (1255, 400)

# Technology tree → select a tech (Stone Gathering II - not 10/10)
TECH_SELECT = (900, 470)

# Donate button (blue "Donate 6,000" resources - RIGHT button)
# LEFT button (855,640) = GEMS! Don't use it!
DONATE_BTN = (1100, 640)

# Cancel button if gem popup appears
CANCEL_BTN = (610, 462)

# Total donation chances per day
MAX_DONATIONS = 20


# Cooldown file path
COOLDOWN_FILE = os.path.join(os.path.dirname(__file__), ".tribe_tech_last_run.json")

# Cooldown: 24 hours
COOLDOWN_HOURS = 24


class TaskTribeTech:
    name = "Tribe Technology"

    def __init__(self, bot):
        self.bot = bot

    def _check_cooldown(self):
        """Return True if cooldown passed (can run), False if still cooling down."""
        if not os.path.exists(COOLDOWN_FILE):
            return True
        try:
            with open(COOLDOWN_FILE, "r") as f:
                data = json.load(f)
            last_run = data.get("last_run", 0)
            elapsed_h = (time.time() - last_run) / 3600
            if elapsed_h < COOLDOWN_HOURS:
                remaining_h = COOLDOWN_HOURS - elapsed_h
                print(f"  [tribe_tech] ⏱ Cooldown: {remaining_h:.1f}h remaining. Skipping.")
                return False
            return True
        except:
            return True

    def _save_cooldown(self):
        """Save current time as last run."""
        with open(COOLDOWN_FILE, "w") as f:
            json.dump({"last_run": time.time()}, f)

    def run(self):
        # Check 24h cooldown
        if not self._check_cooldown():
            return True

        bot = self.bot
        bot.go_to_city()
        bot.wait(2)

        # Step 1: Open Alliance/Tribe
        print("  [tribe_tech] Opening tribe...")
        bot.tap(ALLIANCE_BTN[0], ALLIANCE_BTN[1], jitter=False)
        bot.wait(4)

        # Step 2: Swipe left to reveal Technology icon
        print("  [tribe_tech] Swiping to reveal Technology...")
        bot.swipe(1100, 400, 600, 400, duration=500)
        bot.wait(2)

        # Step 3: Tap Technology
        print("  [tribe_tech] Tapping Technology...")
        bot.tap(1050, 400, jitter=False)
        bot.wait(4)

        # Step 3: Select a tech to donate to
        print("  [tribe_tech] Selecting tech...")
        bot.tap(TECH_SELECT[0], TECH_SELECT[1], jitter=False)
        bot.wait(3)

        # Step 4: Donate 20 times
        print(f"  [tribe_tech] Donating {MAX_DONATIONS} times...")
        for i in range(MAX_DONATIONS):
            bot.tap(DONATE_BTN[0], DONATE_BTN[1], jitter=False)
            delay = random.uniform(0.8, 1.5)
            bot.wait(delay)
            if (i + 1) % 5 == 0:
                print(f"  [tribe_tech] Donated {i+1}/{MAX_DONATIONS}")

        print(f"  [tribe_tech] ✔ All {MAX_DONATIONS} donations complete!")

        # Save cooldown - won't run again for 24h
        self._save_cooldown()
        print(f"  [tribe_tech] ⏱ Next run in {COOLDOWN_HOURS}h")

        # Close
        bot.adb_back()
        bot.wait(1)
        bot.adb_back()
        bot.wait(1)
        bot.go_to_city()
        return True
