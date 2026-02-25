"""Task: Divination — Use divination for speed-up rewards only."""

from tasks.base_task import BaseTask


class TaskDivination(BaseTask):
    name = "Divination"
    tag = "divination"
    cooldown_hours = 12

    def run(self):
        if not self._cooldown_ok():
            return True

        bot = self.bot
        bot.go_to_city()
        bot.wait(2)

        # Find divination icon/building
        print(f"  [{self.tag}] Looking for Divination...")
        found = self._find_and_tap(
            "Find the Divination or Fortune icon — a crystal ball, oracle, "
            "or mystical icon. Usually on the right side panel or events area.",
            wait_after=4,
        )
        if not found:
            # Try the Seer building
            found = self._find_and_tap(
                "Find the Seer's Hut or Oracle building in the city.",
                wait_after=4,
            )

        if not found:
            print(f"  [{self.tag}] Divination not found.")
            return True

        # Perform divination draws
        draws = 0
        for _ in range(3):
            ok = self._find_and_tap(
                "Find a 'Divine', 'Draw', 'Free Draw', or 'Reveal' button.",
                wait_after=4,
            )
            if not ok:
                break
            draws += 1
            # Dismiss result
            bot.tap(640, 400, jitter=False)
            bot.wait(2)
            self._find_and_tap("Find 'OK' or 'Collect' button.", wait_after=2)

        if draws:
            print(f"  [{self.tag}] ✔ Completed {draws} divination(s)!")
        else:
            print(f"  [{self.tag}] No divination available.")

        self._safe_close()
        self._save_cooldown()
        return True
