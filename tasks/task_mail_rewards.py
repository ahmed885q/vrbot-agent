"""Task: Collect All Rewards
1. Mail rewards: Open mail → Read & Claim All
2. Daily quests: Open quests → claim completed

Cooldown: 24 hours
"""

import json
import os
import time

# Mail icon (bottom-right area of city screen)
MAIL_ICON = (1245, 580)
READ_CLAIM_ALL = (390, 645)

# Daily Quests icon (left side of city screen)  
QUESTS_ICON = (65, 120)
QUESTS_TAB = (790, 690)


class TaskMailRewards:
    name = "Collect Rewards"

    COOLDOWN_HOURS = 24
    COOLDOWN_FILE  = '.mail_rewards_last_run.json'

    def __init__(self, bot):
        self.bot = bot

    # ── Cooldown ────────────────────────────────────────────────────────
    def _cooldown_ok(self):
        if not os.path.exists(self.COOLDOWN_FILE):
            return True
        try:
            with open(self.COOLDOWN_FILE, 'r') as f:
                data = json.load(f)
            last = data.get('last_run', 0)
            hours_left = self.COOLDOWN_HOURS - ((time.time() - last) / 3600)
            if hours_left > 0:
                print(f'  [rewards] Cooldown active — {hours_left:.1f}h remaining.')
                return False
            return True
        except Exception:
            return True

    def _save_cooldown(self):
        with open(self.COOLDOWN_FILE, 'w') as f:
            json.dump({'last_run': time.time()}, f)

    # ── Mail ────────────────────────────────────────────────────────────
    def _collect_mail(self):
        """Open mail → Read & Claim All → close."""
        bot = self.bot
        print("  [rewards] === Mail Rewards ===")

        print("  [rewards] Opening mail...")
        bot.tap(MAIL_ICON[0], MAIL_ICON[1], jitter=False)
        bot.wait(3)

        print("  [rewards] Tapping Read & Claim All...")
        bot.tap(READ_CLAIM_ALL[0], READ_CLAIM_ALL[1], jitter=False)
        bot.wait(3)

        bot.tap(640, 400, jitter=False)
        bot.wait(2)

        print("  [rewards] Closing mail...")
        bot.adb_back()
        bot.wait(2)

        print("  [rewards] ✔ Mail claimed!")

    # ── Quests ──────────────────────────────────────────────────────────
    def _collect_quests(self):
        """Open daily quests → claim green buttons → close."""
        bot = self.bot
        print("  [rewards] === Daily Quest Rewards ===")

        print("  [rewards] Opening Daily Quests...")
        bot.tap(QUESTS_ICON[0], QUESTS_ICON[1], jitter=False)
        bot.wait(4)

        print("  [rewards] Switching to Quests tab...")
        bot.tap(QUESTS_TAB[0], QUESTS_TAB[1], jitter=False)
        bot.wait(3)

        for i in range(5):
            print(f"  [rewards] Looking for Claim button (attempt {i+1})...")
            img = bot.screenshot_b64()
            result = bot.ask_ai(
                "You are on a Quests screen in Viking Rise. "
                "Find a green Claim button (completed quest). "
                "Ignore blue Go buttons. "
                "Respond JSON ONLY. "
                'Found: {"found": true, "x": 1080, "y": 300} '
                'Not found: {"found": false}',
                img
            )

            if result and result.get("found"):
                x = result["x"]
                y = result["y"]
                print(f"  [rewards] Claiming at ({x}, {y})...")
                bot.tap(x, y)
                bot.wait(3)
                bot.tap(640, 400)
                bot.wait(2)
            else:
                print("  [rewards] No more Claim buttons.")
                break

        print("  [rewards] Closing quests...")
        bot.adb_back()
        bot.wait(2)

        s = bot.detect_screen()
        screen = s.get("screen", "").lower() if s else ""
        if "city" not in screen:
            bot.adb_back()
            bot.wait(2)

        print("  [rewards] ✔ Quests claimed!")

    # ── Main ────────────────────────────────────────────────────────────
    def run(self):
        if not self._cooldown_ok():
            return False

        bot = self.bot
        bot.go_to_city()
        bot.wait(2)

        self._collect_mail()
        bot.go_to_city()
        bot.wait(2)

        self._collect_quests()
        bot.go_to_city()

        self._save_cooldown()
        print("  [rewards] ✔ All rewards collected!")
        return True
