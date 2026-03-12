"""Task: Gather Boost — Activate gathering speed boost items.
Opens items/inventory, finds gather speed boost items, and activates them.
Inspired by competitor feature (fbots collection acceleration)."""

import random
from tasks.base_task import BaseTask


class TaskGatherBoost(BaseTask):
    name = "Gather Speed Boost"
    tag = "gather_boost"
    cooldown_hours = 4

    def run(self):
        if not self._cooldown_ok():
            return True

        bot = self.bot
        bot.go_to_city()
        bot.wait(2)

        self.log.info("Opening items to find gather boosts...")

        # Open items/backpack/inventory
        found = self._find_and_tap(
            "Find and tap the 'Items', 'Backpack', or 'Inventory' icon. "
            "It is usually at the bottom toolbar or in the lord/profile menu.",
            wait_after=3,
        )
        if not found:
            # Try through lord profile
            found = self._find_and_tap(
                "Find and tap the Lord avatar or profile icon at the top-left "
                "to open the profile menu.",
                wait_after=2,
            )
            if found:
                self._find_and_tap(
                    "Find and tap 'Items' or 'Backpack' in the profile menu.",
                    wait_after=3,
                )

        # Navigate to boost category
        found_cat = self._find_and_tap(
            "Find and tap the 'Boosts', 'Speed Up', or 'Buffs' category tab. "
            "It may show a lightning bolt or arrow icon.",
            wait_after=2,
        )

        # Look for gathering boost specifically
        found_boost = self._find_and_tap(
            "Find and tap a 'Gathering Speed' boost, 'Resource Collection' boost, "
            "or any item that increases gathering/collection speed. "
            "It usually has a pickaxe or resource icon with a speed arrow.",
            wait_after=2,
        )
        if not found_boost:
            self.log.info("No gather speed boosts available.")
            self._safe_close()
            self._save_cooldown()
            return True

        # Use the boost
        found_use = self._find_and_tap(
            "Find and tap the 'Use' or 'Activate' button to activate the boost.",
            wait_after=2,
        )
        if found_use:
            # Confirm if needed
            self._find_and_tap(
                "Find and tap 'Confirm' or 'OK' to activate the boost.",
                wait_after=2,
            )
            self.log.info("Gather speed boost activated!")
        else:
            self.log.info("Could not activate boost.")

        bot.wait(random.uniform(1, 2))
        self._safe_close()
        self._save_cooldown()
        return True
