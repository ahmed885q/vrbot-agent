"""Task: Alliance Helps - Help alliance members"""


class TaskHelps:
    name = "Alliance Helps"

    def __init__(self, bot):
        self.bot = bot

    def run(self):
        bot = self.bot
        bot.go_to_city()
        bot.wait(2)

        print("  [helps] Opening tribe...")
        bot.tap(1100, 685, jitter=False)
        bot.wait(3)

        # Tap Assist tab (3rd from left in bottom bar)
        print("  [helps] Tapping Assist tab...")
        bot.tap(694, 690, jitter=True)
        bot.wait(3)

        img = bot.screenshot_b64()
        result = bot.ask_ai(
            "Viking Rise alliance screen (1280x720). "
            "Look for a button that says 'Help All' or 'Assist All' or a hand icon. "
            "It could be a large button in the center/right of the screen. "
            "Also look for individual 'Help' buttons next to member requests. "
            '{"found": true, "x": 640, "y": 400}\nReply ONLY JSON.',
            img, 80
        )
        if result and result.get("found"):
            bot.tap(result["x"], result["y"])
            bot.wait(2)
            print("  [helps] Helped!")
        else:
            print("  [helps] No pending helps found.")

        bot.adb_back()
        bot.wait(1)
        bot.go_to_city()
        return True
