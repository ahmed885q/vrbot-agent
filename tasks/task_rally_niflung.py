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
        print("  [rally] Opening search panel...")
        bot.tap(MAGNIFY_ICON[0], MAGNIFY_ICON[1], jitter=False)
        bot.wait(3)

        # Select Niflung category
        print("  [rally] Selecting Niflung category...")
        bot.tap(NIFLUNG_CAT[0], NIFLUNG_CAT[1], jitter=True)
        bot.wait(2)

        # Level up to find Niflung Leader (tap 5 times)
        print("  [rally] Leveling up to find leader...")
        for _ in range(5):
            bot.tap(LEVEL_UP_BTN[0], LEVEL_UP_BTN[1], jitter=False)
            bot.wait(0.3)

        # Search
        print("  [rally] Searching...")
        bot.tap(NIFLUNG_SEARCH[0], NIFLUNG_SEARCH[1], jitter=True)
        bot.wait(5)

        # Tap the Niflung on map
        bot.tap(640, 300, jitter=True)
        bot.wait(3)

        # Find Rally button
        print("  [rally] Looking for Rally button...")
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
                print("  [rally] ✔ Rally started!")
            else:
                print("  [rally] Create button not found.")
        else:
            print("  [rally] Rally button not found.")

        bot.go_to_city()
        self._save_cooldown()
        return True
