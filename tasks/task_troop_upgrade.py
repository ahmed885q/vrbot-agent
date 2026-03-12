"""Task: Troop Upgrade — Upgrade existing troops to higher tiers.
Opens the training ground, finds upgrade tab, and upgrades available troops.
Inspired by competitor feature (fbots troop improvement)."""

import random
from tasks.base_task import BuildingTask


class TaskTroopUpgrade(BuildingTask):
    name = "Troop Upgrade"
    tag = "troop_upgrade"
    cooldown_hours = 2

    TROOP_TYPES = ["Infantry", "Pikemen", "Archers", "Movers"]

    def run(self):
        if not self._cooldown_ok():
            return True

        bot = self.bot
        bot.go_to_city()
        bot.wait(2)

        self.log.info("Opening training ground for upgrades...")

        # Find and tap training ground / barracks
        found = self._find_and_tap(
            "Find and tap the Training Ground, Barracks, or Military building "
            "in the city where troops are trained and upgraded.",
            wait_after=3,
        )
        if not found:
            self.log.info("Training ground not found.")
            self._safe_close()
            return True

        # Switch to upgrade tab
        found_tab = self._find_and_tap(
            "Find and tap the 'Upgrade' or 'Improve' tab in the training panel. "
            "It may be a tab at the top showing an arrow-up icon or 'Upgrade' text.",
            wait_after=3,
        )
        if not found_tab:
            self.log.info("Upgrade tab not found — may not be available.")
            self._safe_close()
            self._save_cooldown()
            return True

        upgraded = 0
        for troop in self.TROOP_TYPES:
            self.log.info(f"Checking {troop} upgrade...")

            found_troop = self._find_and_tap(
                f"Find and tap the '{troop}' or similar troop type button "
                f"that is available for upgrade (not greyed out).",
                wait_after=2,
            )
            if not found_troop:
                continue

            # Tap upgrade button
            found_upgrade = self._find_and_tap(
                "Find and tap the 'Upgrade' or 'Improve' button to upgrade these troops. "
                "It should be a green or blue action button.",
                wait_after=2,
            )
            if found_upgrade:
                # Confirm
                self._find_and_tap(
                    "Find and tap 'Confirm' or 'OK' to start the troop upgrade.",
                    wait_after=2,
                )
                upgraded += 1
                self.log.info(f"{troop} upgrade started!")

            bot.wait(random.uniform(1, 2))

        if upgraded == 0:
            self.log.info("No troops available for upgrade.")
        else:
            self.log.info(f"{upgraded} troop type(s) upgraded!")

        self._safe_close()
        self._save_cooldown()
        return True
