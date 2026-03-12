"""Task: Daily Gifts — Claim daily quest rewards + milestone chests
Flow: Open quests → claim green buttons → claim chests → close
Cooldown: 6 hours
"""
from tasks.base_task import BaseTask

QUESTS_ICON = (65, 120)


class TaskDailyGifts(BaseTask):
    name = "Daily Gifts"
    tag = "daily_gifts"
    cooldown_hours = 6

    def run(self):
        if not self._cooldown_ok():
            return True

        self.bot.go_to_city()
        self.bot.wait(2)

        # Open Daily Quests
        self.log.info("Opening Daily Quests...")
        self._tap_ui(None, fallback_xy=QUESTS_ICON, ai_prompt="Find the Quests/daily tasks icon on the left side", wait_after=4)

        # Claim completed quests (max 5 attempts to avoid infinite AI calls)
        claimed = 0
        for i in range(5):
            self.log.info(f"Looking for Claim button ({i + 1})...")
            img = self.bot.screenshot_b64()
            result = self.bot.ask_ai(
                "Viking Rise Quests screen (1280x720). "
                "Find a GREEN 'Claim' button (completed quest). "
                "IGNORE blue 'Go' buttons (incomplete). "
                '{"found": true, "x": 1080, "y": 300} or {"found": false}\n'
                "Respond ONLY JSON.",
                img, 80,
            )
            if result and result.get("found"):
                self.bot.tap(result["x"], result["y"])
                self.bot.wait(2)
                # Dismiss reward popup
                self._dismiss_popup()
                self.bot.wait(2)
                claimed += 1
            else:
                break

        # Check milestone chests at top
        self.log.info("Checking milestone chests...")
        img = self.bot.screenshot_b64()
        chest = self.bot.ask_ai(
            "Viking Rise (1280x720). Look at the TOP area with treasure chests "
            "at quest point milestones (20, 40, 60, 80, 100). "
            "Is any chest GLOWING, highlighted, or ready to open? "
            '{"found": true, "x": 500, "y": 100} or {"found": false}\n'
            "Respond ONLY JSON.",
            img, 80,
        )
        if chest and chest.get("found"):
            self.bot.tap(chest["x"], chest["y"])
            self.bot.wait(3)
            self._dismiss_popup()
            self.bot.wait(2)
            claimed += 1

        self.log.info(f"✔ Claimed {claimed} reward(s).")

        # Close
        self._safe_close()
        self._save_cooldown()
        return True
