"""Task: Train Troops — Recruit troops from the Barracks building."""
from tasks.base_task import BuildingTask


class TaskTrainTroops(BuildingTask):
    name = "Train Troops"
    tag = "train_troops"
    cooldown_hours = 1
    building_desc = (
        "the Barracks building — a military building where troops are trained. "
        "It has soldiers or shield icons."
    )
    action_desc = "a Train or Recruit button"
    confirm_desc = "a Confirm, Train, or Start button"

    def run(self):
        """Override to handle troop type selection."""
        tag = self.tag
        if not self._cooldown_ok():
            return True

        bot = self.bot
        bot.go_to_city()
        bot.wait(2)

        # Find Barracks
        result = self._find_building()
        if not result:
            print(f"  [{tag}] Barracks not found.")
            return False

        bot.tap(result["x"], result["y"])
        bot.wait(4)

        # Check if we entered the building
        s = bot.detect_screen()
        screen = s.get("screen", "").lower() if s else ""
        if screen == "city":
            bot.tap(result["x"], result["y"])
            bot.wait(4)

        # Find Train button — pick highest tier available
        print(f"  [{tag}] Looking for Train button...")
        found = self._find_and_tap(
            "You are inside the Barracks. Find the Train or Recruit button. "
            "If there are multiple troop tiers, pick the HIGHEST tier available. "
            "Look for a green Train button.",
            wait_after=3,
        )

        if found:
            # Set max troops and confirm
            self._find_and_tap(
                "Find the MAX button to set maximum troop count, or a slider to max.",
                wait_after=2,
            )
            confirm = self._tap_button("confirm", wait_after=3)
            if not confirm:
                confirm = self._tap_button("train", wait_after=3)
            if confirm:
                print(f"  [{tag}] ✓ Troops training started!")
            else:
                print(f"  [{tag}] ✓ Train initiated (no confirm needed).")
        else:
            print(f"  [{tag}] No Train button available (queue full?).")

        self._safe_close()
        self._save_cooldown()
        return True
