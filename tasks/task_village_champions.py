"""Task: Village Champions — Optimized, favoring mining villages with S tier first."""

from tasks.base_task import BaseTask


class TaskVillageChampions(BaseTask):
    name = "Village Champions"
    tag = "village_champions"
    cooldown_hours = 6

    # Priority: mining villages > others, S tier > A > B
    PRIORITY_ORDER = ["S", "A", "B", "C"]

    def run(self):
        if not self._cooldown_ok():
            return True

        bot = self.bot
        bot.go_to_city()
        bot.wait(2)

        # Open village champions panel
        self.log.info("Opening Village Champions...")
        found = self._find_and_tap(
            "Find the Village Champions icon or the Village management panel. "
            "Look for a village/champion icon on the right side or events area.",
            wait_after=4,
        )
        if not found:
            found = self._find_and_tap(
                "Find the Village Hall building or a village-related building.",
                wait_after=4,
            )
            if found:
                self._find_and_tap(
                    "Find a 'Champions' or 'Defend' tab.",
                    wait_after=3,
                )

        if not found:
            self.log.info("Village Champions not found.")
            return True

        # Deploy champions — prioritize mining villages, S tier first
        deployed = 0
        for _ in range(5):
            img = bot.screenshot_b64()
            result = bot.ask_ai(
                "Viking Rise Village Champions (1280x720). Find a village that "
                "needs a champion deployed. PRIORITY: 1) Mining villages first, "
                "2) S-tier heroes first, then A, B, C. Look for an empty slot "
                "or 'Deploy' button next to a mining/resource village. "
                '{"found": true, "x": 640, "y": 400} or {"found": false}\n'
                "Respond ONLY JSON.",
                img, 80,
            )
            if not result or not result.get("found"):
                break

            bot.tap(result["x"], result["y"])
            bot.wait(3)

            # Select best available champion
            ok = self._find_and_tap(
                "Find the highest tier champion available (S > A > B). "
                "Tap on them to select.",
                wait_after=3,
            )
            if ok:
                self._find_and_tap(
                    "Find a 'Deploy', 'Assign', or 'Confirm' button.",
                    wait_after=3,
                )
                deployed += 1
            else:
                bot.adb_back()
                bot.wait(2)

        if deployed:
            self.log.info(f"✔ Deployed {deployed} champion(s)!")
        else:
            self.log.info("No champions to deploy.")

        self._safe_close()
        self._save_cooldown()
        return True
