"""Task: Chapter Completion — Auto-complete chapters through 17.
Opens quest/chapter panel, claims completed steps, advances story."""

from tasks.base_task import BaseTask


class TaskChapter(BaseTask):
    name = "Chapter Completion"
    tag = "chapter"
    cooldown_hours = 2

    MAX_CHAPTER = 17

    def run(self):
        if not self._cooldown_ok():
            return True

        bot = self.bot
        bot.go_to_city()
        bot.wait(2)

        # Open chapter/quest panel — bottom-right quest icon
        self.log.info("Opening chapter panel...")
        found = self._find_and_tap(
            "Find the Chapter or Quest icon on the bottom toolbar or right side. "
            "It may look like a scroll, book, or checklist icon.",
            wait_after=4,
        )
        if not found:
            # Try fixed position for quest icon
            self._tap_ui(None, fallback_xy=(1230, 530), ai_prompt="Find quest/chapter icon on right side", jitter=True, wait_after=4)

        # Try to claim and advance multiple steps
        claimed = 0
        for step in range(15):
            # Look for a Go/Claim/Complete button
            ok = self._find_and_tap(
                "Find a green 'Go', 'Claim', 'Complete', or 'Collect' button "
                "in the chapter/quest panel. Ignore grayed-out buttons.",
                wait_after=3,
            )
            if not ok:
                break
            claimed += 1

            # Dismiss any reward popup
            self._dismiss_popup()
            bot.wait(2)

            # Check if story cutscene — skip it
            skip = self._find_and_tap(
                "Find a 'Skip' or 'X' button to skip cutscene or close dialog.",
                wait_after=2,
            )
            if skip:
                bot.wait(1)

        if claimed:
            self.log.info(f"✔ Completed {claimed} chapter step(s)!")
        else:
            self.log.info("No chapter steps available.")

        self._safe_close()
        self._save_cooldown()
        return True
