"""Task: Intelligence Rewards — Collect intelligence/espionage rewards.
Opens the intelligence panel, claims available scout reports and spy rewards.
Inspired by competitor feature (fbots intelligence rewards)."""

import random
from tasks.base_task import BaseTask


class TaskIntelligenceRewards(BaseTask):
    name = "Intelligence Rewards"
    tag = "intelligence_rewards"
    cooldown_hours = 4

    def run(self):
        if not self._cooldown_ok():
            return True

        bot = self.bot
        bot.go_to_city()
        bot.wait(2)

        self.log.info("Opening intelligence/scout panel...")

        # Try to find the intelligence or scout report icon
        found = self._find_and_tap(
            "Find and tap the 'Intelligence', 'Scout Report', 'Spy', "
            "or reconnaissance icon. It may be an eye icon, telescope, "
            "or radar symbol on the toolbar or in a menu.",
            wait_after=3,
        )
        if not found:
            # Try through mail/reports
            found = self._find_and_tap(
                "Find and tap the 'Reports' or 'Mail' icon on the bottom toolbar.",
                wait_after=2,
            )
            if found:
                self._find_and_tap(
                    "Find and tap the 'Scout' or 'Intelligence' tab in the reports panel.",
                    wait_after=2,
                )

        # Collect all available rewards
        collected = 0
        for i in range(5):
            found_reward = self._find_and_tap(
                "Find and tap any unclaimed reward, red dot notification, "
                "or 'Claim' button in the intelligence/scout panel. "
                "Look for gold/resource icons or 'Collect' buttons.",
                wait_after=2,
            )
            if not found_reward:
                break

            # Confirm collection
            self._find_and_tap(
                "Find and tap 'Claim', 'Collect', 'OK', or 'Confirm' "
                "to collect the intelligence reward.",
                wait_after=2,
            )
            collected += 1
            bot.wait(random.uniform(0.5, 1.5))

        if collected == 0:
            self.log.info("No intelligence rewards to collect.")
        else:
            self.log.info(f"Collected {collected} intelligence reward(s)!")

        self._safe_close()
        self._save_cooldown()
        return True
