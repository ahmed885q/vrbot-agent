"""Task: Mail Rewards — Open mail → Read & Claim All
Cooldown: 6 hours (shared with Rewards task)
"""
import json
import os
import time
from tasks.base_task import BaseTask, cooldown_ok, cooldown_save

MAIL_ICON = (1245, 580)
READ_CLAIM_ALL = (390, 645)
QUESTS_ICON = (65, 120)


class TaskMailRewards(BaseTask):
    name = "Collect Rewards"
    tag = "mail_rewards"
    cooldown_hours = 6

    def _collect_mail(self):
        bot = self.bot
        print("  [mail] Opening mail...")
        bot.tap(MAIL_ICON[0], MAIL_ICON[1], jitter=False)
        bot.wait(3)

        # Verify mail opened
        s = bot.detect_screen()
        screen = s.get("screen", "").lower() if s else ""
        if screen == "city":
            bot.tap(MAIL_ICON[0], MAIL_ICON[1], jitter=False)
            bot.wait(3)

        # Read & Claim All
        print("  [mail] Tapping Read & Claim All...")
        bot.tap(READ_CLAIM_ALL[0], READ_CLAIM_ALL[1], jitter=False)
        bot.wait(3)
        bot.tap(640, 400, jitter=False)
        bot.wait(2)

        bot.adb_back()
        bot.wait(2)
        print("  [mail] ✔ Mail claimed!")

    def _collect_quests(self):
        bot = self.bot
        print("  [mail] Opening Daily Quests...")
        bot.tap(QUESTS_ICON[0], QUESTS_ICON[1], jitter=False)
        bot.wait(4)

        claimed = 0
        for i in range(5):
            img = bot.screenshot_b64()
            result = bot.ask_ai(
                "Viking Rise Quests screen (1280x720). "
                "Find a GREEN 'Claim' button (completed quest). "
                "IGNORE blue 'Go' buttons. "
                '{"found": true, "x": 1080, "y": 300} or {"found": false}\n'
                "Respond ONLY JSON.",
                img, 80,
            )
            if result and result.get("found"):
                bot.tap(result["x"], result["y"])
                bot.wait(2)
                bot.tap(640, 400, jitter=False)
                bot.wait(2)
                claimed += 1
            else:
                break

        bot.adb_back()
        bot.wait(2)

        # Check if still not on city
        s = bot.detect_screen()
        if s and "city" not in s.get("screen", "").lower():
            bot.adb_back()
            bot.wait(2)

        print(f"  [mail] ✔ Claimed {claimed} quest(s)!")

    def run(self):
        if not self._cooldown_ok():
            return True

        bot = self.bot
        bot.go_to_city()
        bot.wait(2)

        self._collect_mail()
        bot.go_to_city()
        bot.wait(2)

        self._collect_quests()
        bot.go_to_city()

        self._save_cooldown()
        print("  [mail] ✔ All rewards collected!")
        return True
