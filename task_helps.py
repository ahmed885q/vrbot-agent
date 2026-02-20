"""
Task: Alliance Helps
Sends help to all tribe members.

Flow:
  1. From city, find and tap the handshake icon (top-left area)
  2. Check for "assisted" confirmation message
  3. If no handshake icon found, open Tribe screen -> Assist tab
  4. Return to city
"""


class TaskHelps:
    name = "Alliance Helps"

    def __init__(self, bot):
        self.bot = bot

    def run(self):
        print("  [helps] Looking for handshake icon...")

        # Method 1: Quick tap handshake icon on city screen
        img = self.bot.screenshot_b64()
        result = self.bot.ask_ai(
            "Viking Rise city view (1280x720).\n"
            "Find the HANDSHAKE icon - two hands shaking,\n"
            "usually on the left side near buildings. May have a number badge.\n"
            '{"found": true, "x": 60, "y": 200}\n'
            "Reply ONLY JSON like above.",
            img, 80
        )

        if result and result.get("found"):
            print(f"  [helps] Handshake icon at ({result['x']},{result['y']})")
            self.bot.tap(result["x"], result["y"])
            self.bot.wait(3)

            # Check result
            img2 = self.bot.screenshot_b64()
            check = self.bot.ask_ai(
                "Viking Rise screenshot (1280x720).\n"
                "Do you see 'assisted every Tribe member' or an assist list?\n"
                '{"success": true, "message": "assisted all"}\n'
                "Reply ONLY JSON.",
                img2, 80
            )

            if check and check.get("success"):
                print(f"  [helps] {check.get('message', 'Done')}")
                self._help_all_if_list(img2)
                self.bot.go_to_city()
                return True

            screen = self.bot.detect_screen(img2)
            if screen and screen.get("screen") != "city":
                self._help_all_if_list(img2)
                self.bot.go_to_city()
                return True

        # Method 2: Through Tribe screen
        print("  [helps] Trying through Tribe screen...")
        return self._helps_via_tribe()

    def _help_all_if_list(self, image_b64):
        result = self.bot.ask_ai(
            "Viking Rise screenshot (1280x720).\n"
            "Is there a Help All button or individual Help buttons?\n"
            '{"has_help_all": true, "x": 640, "y": 600}\n'
            "Reply ONLY JSON.",
            image_b64, 80
        )
        if result and result.get("has_help_all"):
            self.bot.tap(result["x"], result["y"])
            self.bot.wait(2)

    def _helps_via_tribe(self):
        img = self.bot.screenshot_b64()
        found = self.bot.find_and_tap(
            "the tribe/alliance button in bottom toolbar (wolf/flag icon)", img
        )
        if not found:
            print("  [helps] Tribe button not found")
            return False

        self.bot.wait(3)

        img2 = self.bot.screenshot_b64()
        found2 = self.bot.find_and_tap(
            "the Assist button/tab at bottom of tribe screen (handshake icon)", img2
        )
        if not found2:
            print("  [helps] Assist button not found")
            self.bot.go_to_city()
            return False

        self.bot.wait(3)
        img3 = self.bot.screenshot_b64()
        self._help_all_if_list(img3)

        print("  [helps] Done via tribe screen")
        self.bot.go_to_city()
        return True
