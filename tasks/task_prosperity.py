"""Task: Prosperity — Collect obtainable resources (green button in city)
Cooldown: 24 hours
"""
from tasks.base_task import BaseTask


class TaskProsperity(BaseTask):
    name = "Prosperity"
    tag = "prosperity"
    cooldown_hours = 24

    def run(self):
        if not self._cooldown_ok():
            return True

        bot = self.bot
        bot.go_to_city()
        bot.wait(2)

        # The Prosperity button is a GREEN floating button in the city
        # Position varies based on camera angle, so use AI
        self.log.info("Looking for Prosperity button...")
        found = self._find_and_tap(
            "Find the GREEN 'Prosperity' floating button in the city. "
            "It shows 'Obtainable Resources' or has a green glow. "
            "NOT a building — it's a floating UI button.",
            wait_after=3,
            retries=2,
        )

        if found:
            # Tap OK on the popup
            self.log.info("Tapping OK...")
            bot.tap(640, 450, jitter=False)
            bot.wait(2)
            self._dismiss_popup()  # dismiss reward
            bot.wait(2)
            self.log.info("✔ Prosperity collected!")
        else:
            self.log.info("Prosperity button not found (may not be available).")

        self._safe_close()
        self._save_cooldown()
        return True
