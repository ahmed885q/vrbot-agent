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
        print("  [gifts] Opening tribe...")
        bot.tap(ALLIANCE_BTN[0], ALLIANCE_BTN[1], jitter=False)
        bot.wait(4)

        # Verify
        s = bot.detect_screen()
        screen = s.get("screen", "").lower() if s else ""
        if "city" in screen:
            bot.tap(ALLIANCE_BTN[0], ALLIANCE_BTN[1], jitter=False)
            bot.wait(4)

        # Tap Gifts tab
        print("  [gifts] Tapping Gifts tab...")
        bot.tap(GIFTS_TAB[0], GIFTS_TAB[1], jitter=False)
        bot.wait(3)

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
                bot.tap(640, 400, jitter=False)
                bot.wait(2)
            else:
                break

        if claimed:
            print(f"  [gifts] ✔ Claimed {claimed} gift(s)!")
        else:
            print("  [gifts] No gifts available.")

        bot.adb_back()
        bot.wait(2)
        self._safe_close()
        self._save_cooldown()
        return True
