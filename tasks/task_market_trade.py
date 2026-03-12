"""Task: Market Trade — Trade resources at the Market (unlocked 8-12 days)."""

from tasks.base_task import BaseTask


class TaskMarketTrade(BaseTask):
    name = "Market Trade"
    tag = "market_trade"
    cooldown_hours = 8

    def run(self):
        if not self._cooldown_ok():
            return True

        bot = self.bot
        bot.go_to_city()
        bot.wait(2)

        # Find Market building
        self.log.info("Looking for Market...")
        found = self._find_and_tap(
            "Find the Market or Trading Post building in the city. "
            "It looks like a merchant stall, market tent, or shop building.",
            wait_after=4,
        )
        if not found:
            self.log.info("Market not found (may not be unlocked yet).")
            return True

        # Look for trade opportunities
        trades = 0
        for _ in range(3):
            ok = self._find_and_tap(
                "Find a 'Trade', 'Exchange', or 'Buy' button for a resource trade. "
                "Look for favorable exchange rates.",
                wait_after=3,
            )
            if not ok:
                break
            self._find_and_tap("Find 'Confirm' or 'Trade' button.", wait_after=3)
            trades += 1
            bot.wait(2)

        if trades:
            self.log.info(f"✔ Completed {trades} trade(s)!")
        else:
            self.log.info("No trades available.")

        self._safe_close()
        self._save_cooldown()
        return True
