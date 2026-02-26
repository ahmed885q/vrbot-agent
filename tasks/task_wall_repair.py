"""Task: Wall Repair — Auto-repair damaged castle wall.
Finds the wall, checks for damage indicator, and initiates repair.
Inspired by competitor feature (fbots wall auto-repair)."""

import random
from tasks.base_task import BuildingTask


class TaskWallRepair(BuildingTask):
    name = "Wall Auto-Repair"
    tag = "wall_repair"
    cooldown_hours = 1

    def run(self):
        if not self._cooldown_ok():
            return True

        bot = self.bot
        bot.go_to_city()
        bot.wait(2)

        print(f"  [{self.tag}] Checking wall for damage...")

        # Find and tap the wall structure
        found = self._find_and_tap(
            "Find the castle Wall or Fortification on the outer edge of the city. "
            "It may show a repair icon, hammer icon, or damage indicator.",
            wait_after=3,
        )
        if not found:
            print(f"  [{self.tag}] Wall not found or no damage.")
            self._safe_close()
            return True

        # Look for repair button
        found_repair = self._find_and_tap(
            "Find and tap the 'Repair' or 'Fix' button. "
            "It may be a green button with a hammer or wrench icon.",
            wait_after=3,
        )
        if not found_repair:
            print(f"  [{self.tag}] No repair needed — wall is intact.")
            self._safe_close()
            self._save_cooldown()
            return True

        # Confirm repair if dialog appears
        self._find_and_tap(
            "Find and tap 'Confirm' or 'OK' button to start the wall repair.",
            wait_after=2,
        )

        print(f"  [{self.tag}] Wall repair initiated!")
        bot.wait(random.uniform(1, 2))
        self._safe_close()
        self._save_cooldown()
        return True
