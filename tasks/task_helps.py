"""Task: Alliance Helps — Open tribe → Assist tab → Help All
Cooldown: 4 hours
"""
from tasks.base_task import BaseTask

ALLIANCE_BTN = (1100, 685)
ASSIST_TAB = (694, 690)


class TaskHelps(BaseTask):
    name = "Alliance Helps"
    tag = "helps"
    cooldown_hours = 4

    def run(self):
        if not self._cooldown_ok():
            return True

        self.bot.go_to_city()
        self.bot.wait(2)

        # Open Alliance
        self.log.info("Opening tribe...")
        self._tap_ui(None, fallback_xy=ALLIANCE_BTN, ai_prompt="Find the Alliance/Tribe button on bottom-right toolbar", wait_after=4)

        # Verify we're in alliance screen
        s = self.bot.detect_screen()
        screen = s.get("screen", "").lower() if s else ""
        if "city" in screen:
            self.log.info("Alliance didn't open, retrying...")
            self._tap_ui(None, fallback_xy=ALLIANCE_BTN, ai_prompt="Find the Alliance/Tribe button on bottom-right toolbar", wait_after=4)

        # Tap Assist tab
        self.log.info("Tapping Assist tab...")
        self._tap_ui("help_all", fallback_xy=ASSIST_TAB, ai_prompt="Find the Assist/Help tab in alliance menu", wait_after=3)

        # Look for Help All button (try twice)
        helped = False
        for attempt in range(2):
            found = self._find_and_tap_hybrid(
                ["help_all", "assist"],
                "Find a 'Help All' or 'Assist All' button (usually large, "
                "center/right area). Also look for individual Help buttons.",
                wait_after=2,
            )
            if found:
                helped = True
                self.log.info("✔ Helped alliance!")
                break
            self.bot.wait(1)

        if not helped:
            self.log.info("No pending helps.")

        self.bot.adb_back()
        self.bot.wait(2)
        self._safe_close()
        self._save_cooldown()
        return True
