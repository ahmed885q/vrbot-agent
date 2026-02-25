"""Task: Research — Start research and use speed-up items."""

from tasks.base_task import BuildingTask


class TaskResearch(BuildingTask):
    name = "Research"
    tag = "research"
    cooldown_hours = 1
    building_desc = (
        "the Academy or Research building — it looks like a large hall or library "
        "building, often with a book or scroll icon. May have a green arrow if "
        "research is available."
    )
    action_desc = "a 'Research' or 'Study' button on an available tech (green/blue)"
    confirm_desc = "a 'Confirm' or 'Research' button"

    def run(self):
        result = super().run()

        # After starting research, use speedups
        bot = self.bot
        bot.go_to_city()
        bot.wait(2)

        # Check for active research with speedup option
        found = self._find_and_tap(
            "Find the Academy building or a research timer icon.",
            wait_after=3,
        )
        if found:
            ok = self._find_and_tap(
                "Find a 'Speed Up' or hourglass button for research.",
                wait_after=3,
            )
            if ok:
                # Use research speed items
                for _ in range(3):
                    used = self._find_and_tap(
                        "Find a 'Use' button next to a research speed-up item.",
                        wait_after=2,
                    )
                    if not used:
                        break
                    self._find_and_tap("Find 'Confirm' button.", wait_after=2)

            self._safe_close()

        return result
