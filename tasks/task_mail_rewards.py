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
        self.log.info("Opening mail...")
        self._tap_ui(None, fallback_xy=MAIL_ICON, ai_prompt="Find the Mail/envelope icon on the right side", wait_after=3)

        # Verify mail opened
        s = self.bot.detect_screen()
        screen = s.get("screen", "").lower() if s else ""
        if screen == "city":
            self._tap_ui(None, fallback_xy=MAIL_ICON, ai_prompt="Find the Mail/envelope icon on the right side", wait_after=3)

        # Read & Claim All
        self.log.info("Tapping Read & Claim All...")
        self._tap_ui("claim", fallback_xy=READ_CLAIM_ALL, wait_after=3)
        self._dismiss_popup()
        self.bot.wait(2)

        self.bot.adb_back()
        self.bot.wait(2)
        self.log.info("✔ Mail claimed!")

    def _collect_quests(self):
        self.log.info("Opening Daily Quests...")
        self._tap_ui(None, fallback_xy=QUESTS_ICON, ai_prompt="Find the Quests/daily tasks icon on the left side", wait_after=4)

        claimed = 0
        for i in range(5):
            img = self.bot.screenshot_b64()
            result = self.bot.ask_ai(
                "Viking Rise Quests screen (1280x720). "
                "Find a GREEN 'Claim' button (completed quest). "
                "IGNORE blue 'Go' buttons. "
                '{"found": true, "x": 1080, "y": 300} or {"found": false}\n'
                "Respond ONLY JSON.",
                img, 80,
            )
            if result and result.get("found"):
                self.bot.tap(result["x"], result["y"])
                self.bot.wait(2)
                self._dismiss_popup()
                self.bot.wait(2)
                claimed += 1
            else:
                break

        self.bot.adb_back()
        self.bot.wait(2)

        # Check if still not on city
        s = self.bot.detect_screen()
        if s and "city" not in s.get("screen", "").lower():
            self.bot.adb_back()
            self.bot.wait(2)

        self.log.info(f"✔ Claimed {claimed} quest(s)!")

    def run(self):
        if not self._cooldown_ok():
            return True

        self.bot.go_to_city()
        self.bot.wait(2)

        self._collect_mail()
        self.bot.go_to_city()
        self.bot.wait(2)

        self._collect_quests()
        self.bot.go_to_city()

        self._save_cooldown()
        self.log.info("✔ All rewards collected!")
        return True
