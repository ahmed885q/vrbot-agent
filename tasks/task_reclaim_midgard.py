"""Task: Reclaim Midgard — Battle monsters, unlock sentry towers,
sacrificial stones, villages, and Odin statue."""

from tasks.base_task import BaseTask


class TaskReclaimMidgard(BaseTask):
    name = "Reclaim Midgard"
    tag = "reclaim_midgard"
    cooldown_hours = 4

    def run(self):
        if not self._cooldown_ok():
            return True

        bot = self.bot
        bot.go_to_city()
        bot.wait(2)

        # Open Reclaim Midgard panel
        print(f"  [{self.tag}] Opening Reclaim Midgard...")
        found = self._find_and_tap(
            "Find the 'Reclaim Midgard' or world exploration icon. "
            "It may be a map icon, compass, or globe on the right side panel.",
            wait_after=4,
        )
        if not found:
            # Try world map approach
            if not bot.go_to_world_map():
                print(f"  [{self.tag}] Cannot access Reclaim Midgard.")
                return True
            found = self._find_and_tap(
                "Find a fog area, locked zone, or 'Explore' icon on the world map.",
                wait_after=4,
            )

        if not found:
            print(f"  [{self.tag}] No Reclaim Midgard content found.")
            bot.go_to_city()
            return True

        # Process available actions
        actions = 0
        targets = [
            "a monster or enemy camp that can be attacked",
            "a sentry tower that can be unlocked or activated",
            "a sacrificial stone that can be unlocked",
            "a village that can be unlocked or liberated",
            "an Odin statue or shrine that can be activated",
        ]

        for target in targets:
            ok = self._find_and_tap(
                f"Find {target}. Look for glowing or actionable elements.",
                wait_after=3,
            )
            if ok:
                # Try to complete action
                self._find_and_tap(
                    "Find an 'Attack', 'Unlock', 'Activate', 'Explore', or 'March' button.",
                    wait_after=3,
                )
                self._find_and_tap(
                    "Find a 'Confirm', 'March', or 'Send' button.",
                    wait_after=3,
                )
                actions += 1
                bot.wait(2)

        if actions:
            print(f"  [{self.tag}] ✔ Completed {actions} Midgard action(s)!")
        else:
            print(f"  [{self.tag}] No Midgard actions available.")

        bot.go_to_city()
        self._save_cooldown()
        return True
