class TaskShield:
    name = 'Shield'

    def __init__(self, bot):
        self.bot = bot

    def run(self):
        print('  [shield] Checking shield status...')
        img = self.bot.screenshot_b64()
        result = self.bot.ask_ai(
            'You are looking at a Viking Rise city screen. '
            'Is there a peace shield dome/bubble over the city or a shield timer? '
            'Respond JSON ONLY. '
            'Active: {"shield_active": true} '
            'Not active: {"shield_active": false}',
            img
        )

        if result and result.get('shield_active'):
            print('  [shield] Shield already active!')
            return True

        # Open Items bag at (970, 665)
        print('  [shield] Opening items...')
        self.bot.tap(970, 665)
        self.bot.wait(4)

        s = self.bot.detect_screen()
        screen = s.get('screen', '').lower() if s else ''
        print(f'  [shield] Screen: {screen}')

        if 'city' in screen:
            print('  [shield] Items did not open.')
            return False

        # Find shield item using AI
        print('  [shield] Looking for shield item...')
        img = self.bot.screenshot_b64()
        shield_item = self.bot.ask_ai(
            'You are looking at an inventory/items screen. '
            'Find a Peace Shield, Protection Shield, or any Shield item. '
            'Respond JSON ONLY. '
            'Found: {"found": true, "x": 400, "y": 300} '
            'Not found: {"found": false}',
            img
        )

        if shield_item and shield_item.get('found'):
            print('  [shield] Found shield, tapping...')
            self.bot.tap(shield_item['x'], shield_item['y'])
            self.bot.wait(3)

            img = self.bot.screenshot_b64()
            use_btn = self.bot.ask_ai(
                'Is there a Use or Activate button? '
                'Respond JSON ONLY. '
                'Found: {"found": true, "x": 640, "y": 500} '
                'Not found: {"found": false}',
                img
            )
            if use_btn and use_btn.get('found'):
                self.bot.tap(use_btn['x'], use_btn['y'])
                self.bot.wait(3)
                print('  [shield] Shield activated!')
            else:
                print('  [shield] Use button not found.')
        else:
            print('  [shield] No shield items available.')

        # Close - AI find X button
        print('  [shield] Closing...')
        img = self.bot.screenshot_b64()
        close = self.bot.ask_ai(
            'Find the X or Close button. '
            'Respond JSON ONLY. '
            'Example: {"found": true, "x": 1200, "y": 50} '
            'Not found: {"found": false}',
            img
        )
        if close and close.get('found'):
            self.bot.tap(close['x'], close['y'])
            self.bot.wait(3)

        s = self.bot.detect_screen()
        if s and 'city' not in s.get('screen', '').lower():
            self.bot.go_to_city()
        return True
