"""Task: Tribe Gifts - Collect alliance gifts"""

# From alliance screenshot: Crystal Trove | Materials for War | Assist | Gifts | Shop | Warehouse | Settings
# Gifts is the 4th tab at bottom bar
GIFTS_TAB = (810, 690)


class TaskTribeGifts:
    name = "Tribe Gifts"

    def __init__(self, bot):
        self.bot = bot

    def run(self):
        bot = self.bot
        bot.go_to_city()
        bot.wait(2)

        print("  [tribe_gifts] Opening tribe...")
        bot.tap(1100, 685, jitter=False)
        bot.wait(4)

        # From alliance screenshot: Gifts tab is 4th from left
        # Crystal Trove(~430) | Materials(~560) | Assist(~690) | Gifts(~810) | Shop(~930)
        print("  [tribe_gifts] Tapping Gifts tab...")
        bot.tap(810, 690, jitter=False)
        bot.wait(3)

        img = bot.screenshot_b64()
        result = bot.ask_ai(
            "Viking Rise (1280x720). This should be the alliance Gifts screen. "
            "Look for gift chests/boxes with 'Claim' or 'Open' or 'Collect' buttons. "
            "If you see gifts, find the claim button. "
            "If this is NOT the gifts screen, reply {\"found\": false}. "
            '{"found": true, "x": 640, "y": 400}\nReply ONLY JSON.',
            img, 80)
        if result and result.get("found"):
            bot.tap(result["x"], result["y"])
            bot.wait(2)
            print("  [tribe_gifts] Claimed!")
        else:
            print("  [tribe_gifts] No gifts available.")

        bot.adb_back()
        bot.wait(1)
        bot.go_to_city()
        return True
