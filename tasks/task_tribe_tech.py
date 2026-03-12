"""Task: Tribe Technology — Donate 20 times (once per 24h)
Flow: City → Alliance → Technology → select tech → Donate x20
GEM SAFETY: Only taps RIGHT donate button (resources). LEFT = GEMS!
Cooldown: 24 hours
"""

import random
import time
from tasks.base_task import BaseTask

ALLIANCE_BTN = (1100, 685)
TECH_SELECT = (900, 470)

# CRITICAL: RIGHT button = resources. LEFT button (855,640) = GEMS!
DONATE_BTN = (1100, 640)

MAX_DONATIONS = 20
COOLDOWN_HOURS = 24


class TaskTribeTech(BaseTask):
    name = "Tribe Technology"
    tag = "tribe_tech"
    cooldown_hours = COOLDOWN_HOURS

    def run(self):
        if not self._cooldown_ok():
            return True

        bot = self.bot
        bot.go_to_city()
        bot.wait(2)

        # Step 1: Open Alliance/Tribe
        print("  [tribe_tech] Opening tribe...")
        bot.tap(ALLIANCE_BTN[0], ALLIANCE_BTN[1], jitter=False)
        bot.wait(4)

        # Verify alliance opened
        s = bot.detect_screen()
        screen = s.get("screen", "").lower() if s else ""
        if "city" in screen:
            print("  [tribe_tech] Alliance didn't open, retrying...")
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

        # Step 4: Select a tech to donate to
        print("  [tribe_tech] Selecting tech...")
        bot.tap(TECH_SELECT[0], TECH_SELECT[1], jitter=False)
        bot.wait(3)

        # Step 5: SAFETY CHECK — verify donate button is resource, not gems
        print("  [tribe_tech] Verifying donate button...")
        img = bot.screenshot_b64()
        check = bot.ask_ai(
            "Viking Rise Technology donate screen (1280x720). "
            "Look at the bottom area. There should be TWO buttons: "
            "LEFT = gem donation (costs gems/diamonds), "
            "RIGHT = resource donation (costs food/wood/stone). "
            "Is the RIGHT button at approximately x=1100 y=640 a RESOURCE donate "
            "(NOT gem)? "
            '{"safe": true, "details": "resource button"} or '
            '{"safe": false, "details": "gem button or wrong screen"}\n'
            "Respond ONLY JSON.",
            img, 100,
        )

        if check and check.get("safe") is False:
            print("  [tribe_tech] ⚠ GEM SAFETY: Donate button looks unsafe! Aborting.")
            bot.adb_back()
            bot.wait(1)
            bot.adb_back()
            bot.wait(1)
            bot.go_to_city()
            return False

        # Step 6: Donate 20 times
        print(f"  [tribe_tech] Donating {MAX_DONATIONS} times (resource button ONLY)...")
        for i in range(MAX_DONATIONS):
            bot.tap(DONATE_BTN[0], DONATE_BTN[1], jitter=False)
            delay = random.uniform(0.8, 1.5)
            bot.wait(delay)
            if (i + 1) % 5 == 0:
                print(f"  [tribe_tech] Donated {i + 1}/{MAX_DONATIONS}")

        print(f"  [tribe_tech] ✔ All {MAX_DONATIONS} donations complete!")

        # Save cooldown
        self._save_cooldown()
        print(f"  [tribe_tech] ⏱ Next run in {COOLDOWN_HOURS}h")

        # Close
        bot.adb_back()
        bot.wait(1)
        bot.adb_back()
        bot.wait(1)
        bot.go_to_city()
        return True
