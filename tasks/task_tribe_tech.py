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
        self.log.info("Opening tribe...")
        self._tap_ui(None, fallback_xy=ALLIANCE_BTN, ai_prompt="Find the Alliance/Tribe button on bottom-right toolbar", wait_after=4)

        # Verify alliance opened
        s = bot.detect_screen()
        screen = s.get("screen", "").lower() if s else ""
        if "city" in screen:
            self.log.info("Alliance didn't open, retrying...")
            self._tap_ui(None, fallback_xy=ALLIANCE_BTN, ai_prompt="Find the Alliance/Tribe button on bottom-right toolbar", wait_after=4)

        # Step 2: Swipe left to reveal Technology icon
        self.log.info("Swiping to reveal Technology...")
        self._swipe_ui("left", fallback_coords=(1100, 400, 600, 400))
        bot.wait(2)

        # Step 3: Tap Technology
        self.log.info("Tapping Technology...")
        self._tap_ui(None, fallback_xy=(1050, 400), ai_prompt="Find Technology icon in alliance menu", wait_after=4)

        # Step 4: Select a tech to donate to
        self.log.info("Selecting tech...")
        self._tap_ui(None, fallback_xy=TECH_SELECT, ai_prompt="Find the Technology button in alliance menu", wait_after=3)

        # Step 5: SAFETY CHECK — verify donate button is resource, not gems
        self.log.info("Verifying donate button...")
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
            self.log.warning("⚠ GEM SAFETY: Donate button looks unsafe! Aborting.")
            bot.adb_back()
            bot.wait(1)
            bot.adb_back()
            bot.wait(1)
            bot.go_to_city()
            return False

        # Step 6: Donate 20 times
        self.log.info(f"Donating {MAX_DONATIONS} times (resource button ONLY)...")
        for i in range(MAX_DONATIONS):
            self._tap_ui("donate", fallback_xy=DONATE_BTN, wait_after=0)
            delay = random.uniform(0.8, 1.5)
            bot.wait(delay)
            if (i + 1) % 5 == 0:
                self.log.info(f"Donated {i + 1}/{MAX_DONATIONS}")

        self.log.info(f"✔ All {MAX_DONATIONS} donations complete!")

        # Save cooldown
        self._save_cooldown()
        self.log.info(f"⏱ Next run in {COOLDOWN_HOURS}h")

        # Close
        bot.adb_back()
        bot.wait(1)
        bot.adb_back()
        bot.wait(1)
        bot.go_to_city()
        return True
