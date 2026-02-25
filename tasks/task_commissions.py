"""Task: Commissions — Complete available commissions, claim rewards."""

from tasks.base_task import BaseTask


class TaskCommissions(BaseTask):
    name = "Commissions"
    tag = "commissions"
    cooldown_hours = 4

    def run(self):
        if not self._cooldown_ok():
            return True

        bot = self.bot
        bot.go_to_city()
        bot.wait(2)

        # Open commissions panel — usually in event/quest area
        print(f"  [{self.tag}] Opening commissions...")
        found = self._find_and_tap(
            "Find the Commissions icon or board. It may be a notice board, "
            "bulletin board, or mission icon on the right side of the screen.",
            wait_after=4,
        )
        if not found:
            # Try tavern building
            found = self._find_and_tap(
                "Find the Tavern building in the city — it handles commissions.",
                wait_after=4,
            )
            if found:
                self._find_and_tap(
                    "Find a 'Commissions' or 'Missions' tab or button.",
                    wait_after=3,
                )

        if not found:
            print(f"  [{self.tag}] Commissions not found.")
            return True

        # Claim completed commissions
        claimed = 0
        for _ in range(5):
            ok = self._find_and_tap(
                "Find a green 'Claim', 'Complete', or 'Collect' button for a "
                "completed commission. Ignore locked or in-progress ones.",
                wait_after=3,
            )
            if not ok:
                break
            claimed += 1
            bot.tap(640, 400, jitter=False)
            bot.wait(2)

        # Start new commissions
        for _ in range(3):
            ok = self._find_and_tap(
                "Find a 'Start', 'Accept', or 'Dispatch' button for a new commission.",
                wait_after=3,
            )
            if not ok:
                break
            self._find_and_tap("Find a 'Confirm' button.", wait_after=2)

        if claimed:
            print(f"  [{self.tag}] ✔ Claimed {claimed} commission(s)!")
        else:
            print(f"  [{self.tag}] No commissions to claim.")

        self._safe_close()
        self._save_cooldown()
        return True
