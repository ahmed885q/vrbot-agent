"""Task: Errands — Complete and claim errands around the city."""

from tasks.base_task import BaseTask


class TaskErrands(BaseTask):
    name = "Errands"
    tag = "errands"
    cooldown_hours = 4

    def run(self):
        if not self._cooldown_ok():
            return True

        bot = self.bot
        bot.go_to_city()
        bot.wait(2)

        # Look for errand indicators (floating icons above buildings)
        self.log.info("Searching for errands...")
        completed = 0

        for attempt in range(8):
            img = bot.screenshot_b64()
            result = bot.ask_ai(
                "Viking Rise city (1280x720). Find an errand indicator — "
                "a floating chat bubble, exclamation mark (!), question mark (?), "
                "or green checkmark above a building or NPC. "
                '{"found": true, "x": 500, "y": 300} or {"found": false}\n'
                "Respond ONLY JSON.",
                img, 80,
            )
            if not result or not result.get("found"):
                if attempt < 4:
                    # Swipe to check other areas (dynamic pattern with fallback)
                    x2 = 300 + attempt * 100
                    self._swipe_ui(direction="explore_nw", fallback_coords=(640, 360, x2, 200))
                    bot.wait(2)
                    continue
                break

            bot.tap(result["x"], result["y"])
            bot.wait(3)

            # Complete the errand
            ok = self._find_and_tap(
                "Find a 'Complete', 'Collect', 'Claim', 'Go', or 'OK' button.",
                wait_after=3,
            )
            if ok:
                completed += 1
                self._dismiss_popup()  # dismiss
                bot.wait(2)
            else:
                self._safe_close()
                bot.wait(1)

        if completed:
            self.log.info(f"✔ Completed {completed} errand(s)!")
        else:
            self.log.info("No errands found.")

        self._safe_close()
        self._save_cooldown()
        return True
