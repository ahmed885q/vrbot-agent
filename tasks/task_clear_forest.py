"""Task: Clear Forest & Monster Caves — Remove obstacles in city and clear caves."""

from tasks.base_task import BaseTask


class TaskClearForest(BaseTask):
    name = "Clear Forest & Caves"
    tag = "clear_forest"
    cooldown_hours = 2

    def _clear_obstacles(self):
        """Find and clear trees, rocks, or caves in city."""
        bot = self.bot
        cleared = 0

        for attempt in range(6):
            # Search for clearable obstacles
            img = bot.screenshot_b64()
            result = bot.ask_ai(
                "Viking Rise city (1280x720). Find a tree, rock, bush, fog, or "
                "monster cave that can be cleared/removed. These are obstacles with "
                "a tap indicator or glow. Look at edges of the city. "
                '{"found": true, "x": 500, "y": 400} or {"found": false}\n'
                "Respond ONLY JSON.",
                img, 80,
            )
            if not result or not result.get("found"):
                break

            bot.tap(result["x"], result["y"])
            bot.wait(3)

            # Look for Clear/Remove button
            ok = self._find_and_tap(
                "Find a 'Clear', 'Remove', 'Explore', or 'Enter' button.",
                wait_after=3,
            )
            if ok:
                # Confirm if needed
                self._find_and_tap(
                    "Find a 'Confirm' or 'OK' button (green).",
                    wait_after=3,
                )
                cleared += 1
                bot.tap(640, 400, jitter=False)  # dismiss reward
                bot.wait(2)
            else:
                bot.adb_back()
                bot.wait(2)

            # Swipe to reveal more areas
            if attempt in (2, 4):
                bot.swipe(640, 360, 300, 200)
                bot.wait(2)

        return cleared

    def run(self):
        if not self._cooldown_ok():
            return True

        bot = self.bot
        bot.go_to_city()
        bot.wait(2)

        cleared = self._clear_obstacles()
        if cleared:
            print(f"  [{self.tag}] ✔ Cleared {cleared} obstacle(s)!")
        else:
            print(f"  [{self.tag}] No obstacles to clear.")

        self._safe_close()
        self._save_cooldown()
        return True
