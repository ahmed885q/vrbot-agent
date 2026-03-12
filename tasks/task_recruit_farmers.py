"""Task: Recruit Farmers — Recruit new farmers for villages."""

from tasks.base_task import BaseTask


class TaskRecruitFarmers(BaseTask):
    name = "Recruit Farmers"
    tag = "recruit_farmers"
    cooldown_hours = 8

    def run(self):
        if not self._cooldown_ok():
            return True

        bot = self.bot
        bot.go_to_city()
        bot.wait(2)

        self.log.info("Looking for farmer recruitment...")
        found = self._find_and_tap(
            "Find the Village or Farm management panel. Look for a village icon, "
            "farmer icon, or house icon on the right side or toolbar.",
            wait_after=4,
        )
        if not found:
            found = self._find_and_tap(
                "Find the Farmstead, Village Hall, or Tavern building.",
                wait_after=4,
            )

        if not found:
            self.log.info("Recruitment panel not found.")
            return True

        # Navigate to recruit tab
        self._find_and_tap(
            "Find a 'Recruit', 'Hire', or 'New Farmer' tab or button.",
            wait_after=3,
        )

        recruited = 0
        for _ in range(3):
            ok = self._find_and_tap(
                "Find a 'Recruit', 'Hire', or 'Free Recruit' button (green).",
                wait_after=3,
            )
            if not ok:
                break
            self._find_and_tap("Find 'Confirm' or 'OK' button.", wait_after=2)
            recruited += 1
            self._dismiss_popup()
            bot.wait(2)

        if recruited:
            self.log.info(f"✔ Recruited {recruited} farmer(s)!")
        else:
            self.log.info("No recruitment available.")

        self._safe_close()
        self._save_cooldown()
        return True
