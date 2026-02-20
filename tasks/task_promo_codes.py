class TaskPromoCodes:
    name = 'Promo Codes'

    def __init__(self, bot):
        self.bot = bot

    def run(self):
        # Promo codes usually in Settings
        print('  [promo] Opening avatar/settings...')
        self.bot.tap(65, 45)
        self.bot.wait(4)

        print('  [promo] Looking for Settings or Promo Code...')
        img = self.bot.screenshot_b64()
        result = self.bot.ask_ai(
            'You are on a profile or settings screen. '
            'Find a Settings, Redeem Code, Gift Code, or Promo Code button. '
            'Respond JSON ONLY. '
            'Found: {"found": true, "x": 640, "y": 400} '
            'Not found: {"found": false}',
            img
        )

        if result and result.get('found'):
            self.bot.tap(result['x'], result['y'])
            self.bot.wait(3)
            print('  [promo] Found promo section.')
        else:
            print('  [promo] Promo code section not found.')

        self.bot.tap(35, 25)
        self.bot.wait(3)
        s = self.bot.detect_screen()
        if s and 'city' not in s.get('screen', '').lower():
            self.bot.tap(35, 25)
            self.bot.wait(2)
            self.bot.go_to_city()
        return True

