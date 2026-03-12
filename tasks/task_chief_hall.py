"""Task: Chief Hall — Fast construction to level 22.
Only builds what is needed. Elite tier costs extra."""

from tasks.base_task import BaseTask


class TaskChiefHall(BaseTask):
    name = "Chief Hall Rush"
    tag = "chief_hall"
    cooldown_hours = 1

    TARGET_LEVEL = 22

    def _use_speedups(self):
        """Look for and use construction speedups."""
        bot = self.bot
        # Look for speedup button in construction queue
        found = self._find_and_tap(
            "Find a 'Speed Up' or hourglass/clock button for construction.",
            wait_after=3,
        )
        if not found:
            return False

        # Use free speedup first
        self._find_and_tap(
            "Find 'Free' speed up button or 'Use' button for construction speedups.",
            wait_after=2,
        )
        # Use item speedups
        for _ in range(3):
            ok = self._find_and_tap(
                "Find a 'Use' button next to a construction speed-up item.",
                wait_after=2,
            )
            if not ok:
                break
            # Confirm
            self._find_and_tap(
                "Find a green 'Confirm' or 'Use' button.",
                wait_after=2,
            )
        return True

    def run(self):
        if not self._cooldown_ok():
            return True

        bot = self.bot
        bot.go_to_city()
        bot.wait(2)

        # Find Chief Hall building
        print(f"  [{self.tag}] Looking for Chief Hall...")
        found = self._find_and_tap(
            "Find the Chief Hall / Town Center / main large building in the center "
            "of the city. It is usually the biggest building.",
            wait_after=4,
        )
        if not found:
            print(f"  [{self.tag}] Chief Hall not found.")
            return False

        # Check if upgrade available
        upgraded = self._find_and_tap(
            "Find an 'Upgrade' button (green or blue) for the Chief Hall.",
            wait_after=4,
        )
        if upgraded:
            # Confirm upgrade
            self._find_and_tap(
                "Find a 'Confirm' or 'Upgrade' confirmation button (green).",
                wait_after=3,
            )
            print(f"  [{self.tag}] ✔ Chief Hall upgrade started!")

            # Use speedups
            self._use_speedups()
        else:
            # Maybe prerequisites needed
            print(f"  [{self.tag}] Upgrade not available — may need prerequisites.")
            # Check info to see what's needed
            self._find_and_tap(
                "Find an 'Info' or 'Requirements' tab to see what buildings are needed.",
                wait_after=3,
            )

        self._safe_close()
        self._save_cooldown()
        return True
