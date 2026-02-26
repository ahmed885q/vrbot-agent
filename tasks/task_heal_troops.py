"""Task: Heal Troops — Heal injured troops in the Hospital building.
Opens hospital, selects all wounded, and starts healing.
Inspired by competitor feature (fbots hospital treatment)."""

import random
from tasks.base_task import BuildingTask


class TaskHealTroops(BuildingTask):
    name = "Heal Troops"
    tag = "heal_troops"
    cooldown_hours = 1

    def run(self):
        if not self._cooldown_ok():
            return True

        bot = self.bot
        bot.go_to_city()
        bot.wait(2)

        print(f"  [{self.tag}] Opening Hospital...")

        # Find and tap the Hospital building
        found = self._find_and_tap(
            "Find and tap the Hospital building in the city. "
            "It has a red cross or medical symbol on it.",
            wait_after=3,
        )
        if not found:
            print(f"  [{self.tag}] Hospital not found.")
            self._safe_close()
            return True

        # Look for Heal button
        found_heal = self._find_and_tap(
            "Find and tap the 'Heal' or 'Heal All' button to heal wounded troops. "
            "It is usually a green button at the bottom of the hospital panel.",
            wait_after=3,
        )
        if not found_heal:
            print(f"  [{self.tag}] No wounded troops or heal button not found.")
            self._safe_close()
            self._save_cooldown()
            return True

        # Confirm healing if needed
        self._find_and_tap(
            "Find and tap 'Confirm' or 'OK' to start healing troops.",
            wait_after=2,
        )

        print(f"  [{self.tag}] Troop healing started!")
        bot.wait(random.uniform(1, 2))
        self._safe_close()
        self._save_cooldown()
        return True
