"""Task: Rally Niflung - FIXED Search Y=490"""

MAGNIFY_ICON = (155, 525)
NIFLUNG_CAT = (380, 655)
NIFLUNG_SEARCH = (380, 490)
LEVEL_UP_BTN = (510, 390)


class TaskRallyNiflung:
    name = "Rally Niflung"

    def __init__(self, bot):
        self.bot = bot

    def run(self):
        bot = self.bot
        bot.go_to_city()
        bot.wait(1)

        if not bot.go_to_world_map():
            bot.go_to_city()
            return False

        print("  [rally] Step 1: Opening search panel...")
        bot.tap(MAGNIFY_ICON[0], MAGNIFY_ICON[1], jitter=False)
        bot.wait(3)

        bot.tap(NIFLUNG_CAT[0], NIFLUNG_CAT[1], jitter=True)
        bot.wait(1)

        for _ in range(5):
            bot.tap(LEVEL_UP_BTN[0], LEVEL_UP_BTN[1], jitter=False)
            bot.wait(0.3)

        bot.tap(NIFLUNG_SEARCH[0], NIFLUNG_SEARCH[1], jitter=True)
        bot.wait(5)

        bot.tap(640, 300, jitter=True)
        bot.wait(2)

        img = bot.screenshot_b64()
        rally = bot.ask_ai(
            "Viking Rise (1280x720). Find RALLY button in popup. "
            '{"found": true, "x": 640, "y": 450}\nReply ONLY JSON.',
            img, 80)
        if rally and rally.get("found"):
            bot.tap(rally["x"], rally["y"])
            bot.wait(2)
            img = bot.screenshot_b64()
            create = bot.ask_ai(
                "Viking Rise (1280x720). Find Create/Start rally button. "
                '{"found": true, "x": 640, "y": 600}\nReply ONLY JSON.',
                img, 80)
            if create and create.get("found"):
                bot.tap(create["x"], create["y"])
                print("  [rally] ✓ Rally started!")

        bot.go_to_city()
        return True
