"""Task: Account Items — Use resource chests from inventory
Cooldown: 24 hours
"""
from tasks.base_task import BaseTask

ITEMS_BTN = (970, 665)


class TaskAccountItems(BaseTask):
    name = "Account Items"
    tag = "account_items"
    cooldown_hours = 24

    def run(self):
        if not self._cooldown_ok():
            return True

        self.bot.go_to_city()
        self.bot.wait(2)

        self.log.info("Opening items...")
        self._tap_ui(None, fallback_xy=ITEMS_BTN, ai_prompt="Find the Items/Inventory button on the bottom toolbar", wait_after=4)

        # Verify opened
        s = self.bot.detect_screen()
        if s and s.get("screen", "").lower() == "city":
            self.log.info("Items didn't open.")
            return False

        # Find and use resource items (up to 3)
        used = 0
        for i in range(3):
            self.log.info(f"Looking for usable item ({i + 1})...")
            found = self._find_and_tap(
                "You are on an inventory/items screen. "
                "Find a resource chest, speedup item, or usable item. "
                "Look for items with a green highlight or 'Use' label.",
                wait_after=2,
            )
            if found:
                use_ok = self._find_and_tap_hybrid(
                    ["use", "activate"],
                    "Find the Use or Open button.",
                    wait_after=2,
                )
                if use_ok:
                    used += 1
                    self._dismiss_popup()  # dismiss popup
                    bot.wait(2)
                else:
                    break
            else:
                break

        if used:
            self.log.info(f"✔ Used {used} item(s)!")
        else:
            self.log.info("No usable items.")

        self._safe_close()
        self._save_cooldown()
        return True
