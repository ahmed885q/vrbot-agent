"""Task: Rally Niflung — Find and rally Niflung Leader
Flow: World map → Magnify → Niflung tab → level up → Search → tap → Rally → Create
Cooldown: 12 hours
"""
from tasks.base_task import BaseTask

MAGNIFY_ICON = (155, 525)
NIFLUNG_CAT = (380, 655)
NIFLUNG_SEARCH = (380, 490)
LEVEL_UP_BTN = (510, 390)


class TaskRallyNiflung(BaseTask):
    name = "Rally Niflung"
    tag = "rally_niflung"
    cooldown_hours = 12

    def run(self):
        if not self._cooldown_ok():
            return True

        bot = self.bot
        bot.go_to_city()
        bot.wait(2)

        if not bot.go_to_world_map():
            bot.go_to_city()
            return False

        # Open search panel
        self.log.info("Opening search panel...")
        self._tap_ui("search", fallback_xy=MAGNIFY_ICON, wait_after=3)

        # Select Niflung category
        self.log.info("Selecting Niflung category...")
        self._tap_ui(None, fallback_xy=NIFLUNG_CAT, ai_prompt="Find Niflung category tab", jitter=True)
        bot.wait(2)

        # Level up to find Niflung Leader (tap 5 times)
        self.log.info("Leveling up to find leader...")
        for _ in range(5):
            self._tap_ui(None, fallback_xy=LEVEL_UP_BTN, ai_prompt="Find level up or increase level button", wait_after=0.3)

        # Search
        self.log.info("Searching...")
        self._tap_ui("search", fallback_xy=NIFLUNG_SEARCH, wait_after=5, jitter=True)

        # Tap the Niflung on map
        bot.tap(640, 300, jitter=True)
        bot.wait(3)

        # Find Rally button
        self.log.info("Looking for Rally button...")
        rally_found = self._find_and_tap(
            "Find a RALLY button (not Attack). "
            "Rally starts a group attack that others can join.",
            wait_after=3,
        )

        if rally_found:
            # Create rally
            create_found = self._find_and_tap(
                "Find a Create or Start Rally button to confirm.",
                wait_after=3,
            )
            if create_found:
                self.log.info("✔ Rally started!")
            else:
                self.log.info("Create button not found.")
        else:
            self.log.info("Rally button not found.")

        bot.go_to_city()
        self._save_cooldown()
        return True
