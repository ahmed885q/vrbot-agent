"""Task: Tribe Gold Tile — Auto farm tribe gold resource tiles if built."""

from tasks.base_task import BaseTask

MAGNIFY_ICON = (155, 525)
GATHER_BTN = (1075, 485)
CREATE_BTN = (940, 170)
MARCH_BTN = (960, 615)


class TaskTribeGoldTile(BaseTask):
    name = "Tribe Gold Tile Farm"
    tag = "tribe_gold_tile"
    cooldown_hours = 6

    def _ensure_world_map(self):
        bot = self.bot
        bot.go_to_city()
        bot.wait(2)
        if bot.go_to_world_map():
            return True
        bot.go_to_city()
        bot.wait(2)
        return bot.go_to_world_map()

    def run(self):
        if not self._cooldown_ok():
            return True

        bot = self.bot

        if not self._ensure_world_map():
            print(f"  [{self.tag}] Cannot reach world map.")
            return False

        # Navigate to tribe territory / gold tile
        print(f"  [{self.tag}] Searching for Tribe Gold Tile...")

        # Use magnify search for tribe territory
        bot.tap(MAGNIFY_ICON[0], MAGNIFY_ICON[1], jitter=False)
        bot.wait(3)

        # Look for tribe/alliance resource tile tab
        found = self._find_and_tap(
            "Find a 'Tribe', 'Alliance', or 'Territory' tab in the search panel.",
            wait_after=3,
        )
        if not found:
            # Try finding gold tile directly
            bot.adb_back()
            bot.wait(2)

            found = self._find_and_tap(
                "Find a golden/gold resource tile on the world map. "
                "It should be in your tribe's territory with a gold icon.",
                wait_after=3,
            )

        if not found:
            print(f"  [{self.tag}] Gold tile not found.")
            bot.go_to_city()
            return True

        # Search for gold tile
        self._find_and_tap(
            "Find 'Search' or 'Go' button to locate the gold tile.",
            wait_after=5,
        )

        # Gather from gold tile
        bot.tap(GATHER_BTN[0], GATHER_BTN[1], jitter=False)
        bot.wait(3)

        # Create march
        bot.tap(CREATE_BTN[0], CREATE_BTN[1], jitter=False)
        bot.wait(3)

        # Send march
        bot.tap(MARCH_BTN[0], MARCH_BTN[1], jitter=False)
        bot.wait(3)

        print(f"  [{self.tag}] ✔ Sent march to tribe gold tile!")

        bot.go_to_city()
        self._save_cooldown()
        return True
