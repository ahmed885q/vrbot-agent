"""Task: Construction — Find upgradable building → upgrade, use speedups."""

from tasks.base_task import BuildingTask


class TaskConstruction(BuildingTask):
    name = "Construction"
    tag = "construction"
    cooldown_hours = 1
    building_desc = (
        "a building with a GREEN ARROW ↑ icon or hammer/construction icon above it. "
        "This means it is ready to upgrade. Ignore buildings without icons."
    )
    action_desc = "an Upgrade or Build button (green or blue)"
    confirm_desc = "a Confirm or Upgrade button"

    def run(self):
        """Override to add speedup usage after construction starts."""
        result = super().run()

        # After construction starts, try to use regular speedups
        bot = self.bot
        bot.go_to_city()
        bot.wait(2)

        # Check for active construction with speedup option
        found = self._find_and_tap(
            "Find a building under construction with a timer/hourglass icon. "
            "Tap the building to see speedup options.",
            wait_after=3,
        )
        if found:
            self._find_and_tap(
                "Find a 'Speed Up' or 'Free' speedup button.",
                wait_after=2,
            )
            self._find_and_tap(
                "Find a 'Use' button to apply construction speed-up items.",
                wait_after=2,
            )
            self._find_and_tap("Find 'Confirm' button.", wait_after=2)
            self._safe_close()

        return result
