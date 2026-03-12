"""Task: Promo Codes — Open settings → redeem codes
Cooldown: 168 hours (weekly)
"""
from tasks.base_task import BaseTask


class TaskPromoCodes(BaseTask):
    name = "Promo Codes"
    tag = "promo_codes"
    cooldown_hours = 168  # weekly

    def run(self):
        if not self._cooldown_ok():
            return True

        bot = self.bot
        bot.go_to_city()
        bot.wait(2)

        # Open avatar/profile
        print("  [promo] Opening profile...")
        bot.tap(65, 45, jitter=False)
        bot.wait(4)

        # Find settings or promo code section
        found = self._find_and_tap(
            "You are on a profile/settings screen. "
            "Find a Settings, Redeem Code, Gift Code, or Promo Code button.",
            wait_after=3,
        )
        if found:
            # Look for code input field
            code_found = self._find_and_tap(
                "Find a text input field or 'Enter Code' area for promo codes.",
                wait_after=2,
            )
            if code_found:
                print("  [promo] ✔ Found promo section (no codes to enter).")
            else:
                print("  [promo] Promo code input not found.")
        else:
            print("  [promo] Promo section not found.")

        self._safe_close()
        self._save_cooldown()
        return True
