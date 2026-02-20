"""Task: Collect All Rewards
1. Mail rewards: Open mail → Read & Claim All
2. Daily quests: Open quests → claim completed
"""


# Mail icon (bottom-right area of city screen)
MAIL_ICON = (1245, 580)
READ_CLAIM_ALL = (390, 645)

# Daily Quests icon (left side of city screen)  
QUESTS_ICON = (65, 120)
QUESTS_TAB = (790, 690)


class TaskRewards:
    name = "Collect Rewards"

    def __init__(self, bot):
        self.bot = bot

    def _collect_mail(self):
        """Open mail → Read & Claim All → close."""
        bot = self.bot
        print("  [rewards] === Mail Rewards ===")

        # Open mail
        print("  [rewards] Opening mail...")
        bot.tap(MAIL_ICON[0], MAIL_ICON[1], jitter=False)
        bot.wait(3)

        # Read & Claim All
        print("  [rewards] Tapping Read & Claim All...")
        bot.tap(READ_CLAIM_ALL[0], READ_CLAIM_ALL[1], jitter=False)
        bot.wait(3)

        # Tap again in case confirmation popup
        bot.tap(640, 400, jitter=False)
        bot.wait(2)

        # Close mail
        print("  [rewards] Closing mail...")
        bot.adb_back()
        bot.wait(2)

        print("  [rewards] ✔ Mail claimed!")

    def _collect_quests(self):
        """Open daily quests → claim green buttons → close."""
        bot = self.bot
        print("  [rewards] === Daily Quest Rewards ===")

        # Open quests
        print("  [rewards] Opening Daily Quests...")
        bot.tap(QUESTS_ICON[0], QUESTS_ICON[1], jitter=False)
        bot.wait(4)

        # Switch to Quests tab
        print("  [rewards] Switching to Quests tab...")
        bot.tap(QUESTS_TAB[0], QUESTS_TAB[1], jitter=False)
        bot.wait(3)

        # Look for green Claim buttons
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
                # Dismiss reward popup
                bot.tap(640, 400)
                bot.wait(2)
            else:
                print("  [rewards] No more Claim buttons.")
                break

        # Close quests
        print("  [rewards] Closing quests...")
        bot.adb_back()
        bot.wait(2)

        # Make sure we're back to city
        s = bot.detect_screen()
        screen = s.get("screen", "").lower() if s else ""
        if "city" not in screen:
            bot.adb_back()
            bot.wait(2)

        print("  [rewards] ✔ Quests claimed!")

    def run(self):
        bot = self.bot
        bot.go_to_city()
        bot.wait(2)

        # 1. Collect mail rewards
        self._collect_mail()
        bot.go_to_city()
        bot.wait(2)

        # 2. Collect daily quest rewards
        self._collect_quests()
        bot.go_to_city()

        print("  [rewards] ✔ All rewards collected!")
        return True
