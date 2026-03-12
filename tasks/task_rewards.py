"""Task: Collect Rewards — Mail rewards + Daily quest rewards
Flow: Open mail → Read & Claim All → Open quests → claim
Cooldown: 6 hours
"""
from tasks.base_task import BaseTask

MAIL_ICON = (1245, 580)
READ_CLAIM_ALL = (390, 645)
QUESTS_ICON = (65, 120)


class TaskRewards(BaseTask):
    name = "Collect Rewards"
    tag = "rewards"
    cooldown_hours = 6

    def _collect_mail(self):
        """Open mail → Read & Claim All → close."""
        bot = self.bot
        self.log.info("=== Mail ===")
        bot.tap(MAIL_ICON[0], MAIL_ICON[1], jitter=False)
        bot.wait(3)

        # Verify mail opened (not still on city)
        s = bot.detect_screen()
        screen = s.get("screen", "").lower() if s else ""
        if screen == "city":
            self.log.info("Mail didn't open, retrying...")
            bot.tap(MAIL_ICON[0], MAIL_ICON[1], jitter=False)
            bot.wait(3)

        # Read & Claim All
        bot.tap(READ_CLAIM_ALL[0], READ_CLAIM_ALL[1], jitter=False)
        bot.wait(3)
        self._dismiss_popup()  # dismiss popup
        bot.wait(2)

        # Close mail
        bot.adb_back()
        bot.wait(2)
        self.log.info("✔ Mail claimed!")

    def _collect_quests(self):
        """Open daily quests → claim green buttons → close."""
        bot = self.bot
        self.log.info("=== Quests ===")
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
                self._dismiss_popup()
                bot.wait(2)
                claimed += 1
            else:
                break

        bot.adb_back()
        bot.wait(2)
        self.log.info(f"✔ Claimed {claimed} quest(s).")

    def run(self):
        if not self._cooldown_ok():
            return True

        bot = self.bot
        bot.go_to_city()
        bot.wait(2)

        self._collect_mail()

        # Return to city between sub-tasks
        s = bot.detect_screen()
        if not s or s.get("screen", "").lower() != "city":
            bot.go_to_city()
            bot.wait(2)

        self._collect_quests()

        self._safe_close()
        self._save_cooldown()
        return True
