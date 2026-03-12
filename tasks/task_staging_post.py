"""Task: Staging Post — Claim rewards except the red battle icon."""

from tasks.base_task import BaseTask


class TaskStagingPost(BaseTask):
    name = "Staging Post"
    tag = "staging_post"
    cooldown_hours = 6

    def run(self):
        if not self._cooldown_ok():
            return True

        bot = self.bot
        bot.go_to_city()
        bot.wait(2)

        # Find staging post
        print(f"  [{self.tag}] Looking for Staging Post...")
        found = self._find_and_tap(
            "Find the Staging Post building — it looks like a military tent, "
            "outpost, or campfire structure. May be near the city edge.",
            wait_after=4,
        )
        if not found:
            print(f"  [{self.tag}] Staging Post not found.")
            return True

        # Claim available rewards (skip red battle icons)
        claimed = 0
        for _ in range(5):
            img = bot.screenshot_b64()
            result = bot.ask_ai(
                "Viking Rise Staging Post (1280x720). Find a claimable reward "
                "button (green 'Claim' or 'Collect'). IMPORTANT: Do NOT tap "
                "any RED battle/attack icons — skip those completely. "
                '{"found": true, "x": 640, "y": 400} or {"found": false}\n'
                "Respond ONLY JSON.",
                img, 80,
            )
            if not result or not result.get("found"):
                break

            bot.tap(result["x"], result["y"])
            bot.wait(3)
            claimed += 1
            bot.tap(640, 400, jitter=False)
            bot.wait(2)

        if claimed:
            print(f"  [{self.tag}] ✔ Claimed {claimed} staging post reward(s)!")
        else:
            print(f"  [{self.tag}] No rewards available.")

        self._safe_close()
        self._save_cooldown()
        return True
