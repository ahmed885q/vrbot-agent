"""Task: Shield — Check and activate peace shield
Cooldown: 8 hours
"""
from tasks.base_task import BaseTask

ITEMS_BTN = (970, 665)


class TaskShield(BaseTask):
    name = "Shield"
    tag = "shield"
    cooldown_hours = 8

    def run(self):
        if not self._cooldown_ok():
            return True

        bot = self.bot
        bot.go_to_city()
        bot.wait(2)

        # Check if shield already active
        print("  [shield] Checking shield status...")
        img = bot.screenshot_b64()
        result = bot.ask_ai(
            "Viking Rise city (1280x720). "
            "Is there a peace shield dome/bubble over the city or a shield timer? "
            '{"shield_active": true} or {"shield_active": false}\n'
            "Respond ONLY JSON.",
            img, 60,
        )
        if result and result.get("shield_active"):
            print("  [shield] ✔ Shield already active!")
            self._save_cooldown()
            return True

        # Open Items bag
        print("  [shield] Opening items...")
        bot.tap(ITEMS_BTN[0], ITEMS_BTN[1], jitter=False)
        bot.wait(4)

        # Verify items opened
        s = bot.detect_screen()
        if s and s.get("screen", "").lower() == "city":
            print("  [shield] Items didn't open.")
            return False

        # Find shield item
        print("  [shield] Looking for shield item...")
        shield_found = self._find_and_tap(
            "You are on an inventory screen. "
            "Find a Peace Shield or Protection Shield item. "
            "Look in the items/resources list.",
            wait_after=3,
        )

        if shield_found:
            # Tap Use button
            use_found = self._find_and_tap_hybrid(
                ["use", "activate"],
                "Find the Use or Activate button.",
                wait_after=3,
            )
            if use_found:
                # Confirm if needed
                bot.tap(640, 400, jitter=False)
                bot.wait(2)
                print("  [shield] ✔ Shield activated!")
            else:
                print("  [shield] Use button not found.")
        else:
            print("  [shield] No shield items available.")

        self._safe_close()
        self._save_cooldown()
        return True
