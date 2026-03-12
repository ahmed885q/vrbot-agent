"""Task: Tribe Gifts — Open tribe → Gifts tab → claim all gifts
Cooldown: 4 hours
"""
from tasks.base_task import BaseTask

ALLIANCE_BTN = (1100, 685)
# Tab positions (bottom bar): Crystal Trove(~430) | Materials(~560) | Assist(~690) | Gifts(~810) | Shop(~930)
GIFTS_TAB = (810, 690)


class TaskTribeGifts(BaseTask):
    name = "Tribe Gifts"
    tag = "tribe_gifts"
    cooldown_hours = 4

    def run(self):
        if not self._cooldown_ok():
            return True

        bot = self.bot
        bot.go_to_city()
        bot.wait(2)

        # Open Alliance
        self.log.info("Opening tribe...")
        self._tap_ui(None, fallback_xy=ALLIANCE_BTN, ai_prompt="Find the Alliance/Tribe button on bottom-right toolbar", wait_after=4)

        # Verify
        s = bot.detect_screen()
        screen = s.get("screen", "").lower() if s else ""
        if "city" in screen:
            self._tap_ui(None, fallback_xy=ALLIANCE_BTN, ai_prompt="Find the Alliance/Tribe button on bottom-right toolbar", wait_after=4)

        # Tap Gifts tab
        self.log.info("Tapping Gifts tab...")
        self._tap_ui(None, fallback_xy=GIFTS_TAB, ai_prompt="Find the Gifts tab in the alliance menu", wait_after=3)

        # Claim gifts (try multiple times - there can be several)
        claimed = 0
        for i in range(5):
            found = self._find_and_tap(
                "This is the alliance Gifts screen. "
                "Find a gift chest/box with a 'Claim' or 'Open' button. "
                "If no gifts, reply found:false.",
                wait_after=3,
            )
            if found:
                claimed += 1
                # Dismiss reward popup
                self._dismiss_popup()
                bot.wait(2)
            else:
                break

        if claimed:
            self.log.info(f"✔ Claimed {claimed} gift(s)!")
        else:
            self.log.info("No gifts available.")

        bot.adb_back()
        bot.wait(2)
        self._safe_close()
        self._save_cooldown()
        return True
