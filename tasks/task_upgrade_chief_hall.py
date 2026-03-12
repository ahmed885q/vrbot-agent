"""Task: Upgrade Chief Hall — Find and upgrade the Chief Hall (main building)."""
from tasks.base_task import BuildingTask


class TaskUpgradeChiefHall(BuildingTask):
    name = "Upgrade Chief Hall"
    tag = "upgrade_chief_hall"
    cooldown_hours = 0  # Check every run — upgrade takes hours
    building_desc = (
        "the Chief Hall — the LARGEST central building in the city. "
        "It is the main building, usually in the center with a crown or chief icon. "
        "It may have an upgrade arrow icon above it if ready."
    )
    action_desc = "an Upgrade button (green arrow icon)"
    confirm_desc = "a Confirm or Upgrade button"

    def run(self):
        """Override to handle prerequisite requirements."""
        tag = self.tag
        if not self._cooldown_ok():
            return True

        bot = self.bot
        bot.go_to_city()
        bot.wait(2)

        # Chief Hall is usually center — try tapping center first
        print(f"  [{tag}] Looking for Chief Hall...")
        bot.tap(640, 350)
        bot.wait(3)

        # Check if we got a building popup
        img = bot.screenshot_b64()
        result = bot.ask_ai(
            "Viking Rise (1280x720). Is this a building information popup? "
            "Does it say 'Chief Hall' or show an Upgrade button? "
            '{"found": true, "is_chief_hall": true, "upgrade_x": 640, "upgrade_y": 500} '
            'or {"found": false}. JSON ONLY.',
            img, 80,
        )

        if not result or not result.get("found"):
            # Try AI search for Chief Hall
            result2 = self._find_building()
            if result2:
                bot.tap(result2["x"], result2["y"])
                bot.wait(4)
            else:
                print(f"  [{tag}] Chief Hall not found.")
                return False

        # Look for upgrade button
        found = self._find_and_tap(
            "Find the green Upgrade button in this building menu. "
            "If it says 'Requirements not met', report found=false.",
            wait_after=3,
        )

        if found:
            # Check for requirements popup
            img = bot.screenshot_b64()
            req_check = bot.ask_ai(
                "Viking Rise (1280x720). Is there a requirements/prerequisites popup? "
                "Or is there a Confirm/Upgrade button to proceed? "
                '{"has_requirements": false, "confirm_x": 640, "confirm_y": 500} '
                'or {"has_requirements": true}. JSON ONLY.',
                img, 80,
            )

            if req_check and not req_check.get("has_requirements"):
                if "confirm_x" in req_check:
                    bot.tap(req_check["confirm_x"], req_check["confirm_y"])
                    bot.wait(3)
                    print(f"  [{tag}] ✓ Chief Hall upgrade started!")
                else:
                    self._tap_button("confirm", wait_after=3)
                    print(f"  [{tag}] ✓ Upgrade initiated!")
            else:
                print(f"  [{tag}] Requirements not met yet.")
        else:
            print(f"  [{tag}] No upgrade available (builder busy or max level).")

        self._safe_close()
        self._save_cooldown()
        return True
