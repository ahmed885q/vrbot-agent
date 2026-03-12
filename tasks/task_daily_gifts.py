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

        bot = self.bot
        bot.go_to_city()
        bot.wait(2)

        # Open Daily Quests
        print("  [daily] Opening Daily Quests...")
        bot.tap(QUESTS_ICON[0], QUESTS_ICON[1], jitter=False)
        bot.wait(4)

        # Claim completed quests (max 5 attempts to avoid infinite AI calls)
        claimed = 0
        for i in range(5):
            print(f"  [daily] Looking for Claim button ({i + 1})...")
            img = bot.screenshot_b64()
            result = bot.ask_ai(
                "Viking Rise Quests screen (1280x720). "
                "Find a GREEN 'Claim' button (completed quest). "
                "IGNORE blue 'Go' buttons (incomplete). "
                '{"found": true, "x": 1080, "y": 300} or {"found": false}\n'
                "Respond ONLY JSON.",
                img, 80,
            )
            if result and result.get("found"):
                bot.tap(result["x"], result["y"])
                bot.wait(2)
                # Dismiss reward popup
                bot.tap(640, 400, jitter=False)
                bot.wait(2)
                claimed += 1
            else:
                break

        # Check milestone chests at top
        print("  [daily] Checking milestone chests...")
        img = bot.screenshot_b64()
        chest = bot.ask_ai(
            "Viking Rise (1280x720). Look at the TOP area with treasure chests "
            "at quest point milestones (20, 40, 60, 80, 100). "
            "Is any chest GLOWING, highlighted, or ready to open? "
            '{"found": true, "x": 500, "y": 100} or {"found": false}\n'
            "Respond ONLY JSON.",
            img, 80,
        )
        if chest and chest.get("found"):
            bot.tap(chest["x"], chest["y"])
            bot.wait(3)
            bot.tap(640, 400, jitter=False)
            bot.wait(2)
            claimed += 1

        print(f"  [daily] ✔ Claimed {claimed} reward(s).")

        # Close
        self._safe_close()
        self._save_cooldown()
        return True
