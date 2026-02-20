"""Task: Clear Forest - Clear fog/forest on world map"""


class TaskClearForest:
    name = "Clear Forest"

    def __init__(self, bot):
        self.bot = bot

    def run(self):
        bot = self.bot
        bot.go_to_city()
        bot.wait(1)

        if not bot.go_to_world_map():
            bot.go_to_city()
            return False

        print("  [forest] Looking for dark fog area...")
        img = bot.screenshot_b64()
        result = bot.ask_ai(
            "Viking Rise world map (1280x720). "
            "Find a DARK/BLACK FOG area at the edges of explored territory. "
            "This is where the map is not yet explored - looks dark/shadowy. "
            '{"found": true, "x": 500, "y": 300}\nReply ONLY JSON.',
            img, 80)

        if not result or not result.get("found"):
            # Swipe to find fog
            bot.swipe(640, 360, 200, 200)
            bot.wait(2)
            img = bot.screenshot_b64()
            result = bot.ask_ai(
                "Viking Rise world map (1280x720). "
                "Find any DARK/BLACK FOG area to explore. "
                '{"found": true, "x": 500, "y": 300}\nReply ONLY JSON.',
                img, 80)

        if result and result.get("found"):
            bot.tap(result["x"], result["y"])
            bot.wait(2)

            img = bot.screenshot_b64()
            btn = bot.ask_ai(
                "Viking Rise (1280x720). Find Explore/Scout/Clear button in popup. "
                '{"found": true, "x": 640, "y": 500}\nReply ONLY JSON.',
                img, 80)
            if btn and btn.get("found"):
                bot.tap(btn["x"], btn["y"])
                bot.wait(2)
                # March screen
                march = bot.ask_ai(
                    "Viking Rise (1280x720). Find March/Send button. "
                    '{"found": true, "x": 640, "y": 600}\nReply ONLY JSON.',
                    None, 80)
                if march and march.get("found"):
                    bot.tap(march["x"], march["y"])
                else:
                    bot.tap(640, 600, jitter=True)
                bot.wait(2)
                print("  [forest] Explore started!")
            else:
                print("  [forest] No explore button.")
        else:
            print("  [forest] No fog found.")

        bot.go_to_city()
        return True
