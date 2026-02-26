"""Task: Map Explore — Explore fog-of-war areas on the world map.
Sends scouts to explore unknown territories, revealing resources and enemies.
Inspired by competitor feature (fbots map research)."""

import random
from tasks.base_task import BaseTask


class TaskMapExplore(BaseTask):
    name = "Map Exploration"
    tag = "map_explore"
    cooldown_hours = 3

    MAX_EXPLORES = 3

    def run(self):
        if not self._cooldown_ok():
            return True

        bot = self.bot
        bot.go_to_city()
        bot.wait(2)

        print(f"  [{self.tag}] Heading to world map for exploration...")

        # Go to world map
        found = self._find_and_tap(
            "Find and tap the 'World Map' button or the map/globe icon "
            "to leave the city and go to the kingdom map.",
            wait_after=3,
        )
        if not found:
            print(f"  [{self.tag}] Could not open world map.")
            self._safe_close()
            return True

        explored = 0
        for i in range(self.MAX_EXPLORES):
            print(f"  [{self.tag}] Exploration attempt {i+1}/{self.MAX_EXPLORES}...")

            # Find fog/unexplored area
            found_fog = self._find_and_tap(
                "Find and tap a dark, foggy, or unexplored area on the map. "
                "These are greyed out or covered with fog of war. "
                "Tap on the edge of the explored territory.",
                wait_after=3,
            )
            if not found_fog:
                print(f"  [{self.tag}] No unexplored areas found nearby.")
                break

            # Look for explore/scout button
            found_explore = self._find_and_tap(
                "Find and tap the 'Explore', 'Scout', or 'Investigate' button "
                "to send scouts to this area.",
                wait_after=2,
            )
            if not found_explore:
                continue

            # Confirm
            self._find_and_tap(
                "Find and tap 'Confirm', 'Send', or 'March' to dispatch scouts.",
                wait_after=2,
            )
            explored += 1
            print(f"  [{self.tag}] Scout sent to explore area {i+1}!")
            bot.wait(random.uniform(2, 4))

        if explored == 0:
            print(f"  [{self.tag}] No areas explored.")
        else:
            print(f"  [{self.tag}] {explored} area(s) being explored!")

        # Return to city
        bot.go_to_city()
        bot.wait(1)
        self._safe_close()
        self._save_cooldown()
        return True
