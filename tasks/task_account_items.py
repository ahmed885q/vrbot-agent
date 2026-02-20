class TaskAccountItems:
    name = 'Account Items'

    def __init__(self, bot):
        self.bot = bot

    def run(self):
        print('  [items] Opening items...')
        self.bot.tap(970, 665)
        self.bot.wait(4)

        # Check Resources tab for usable items
        print('  [items] Checking for usable resource items...')
        img = self.bot.screenshot_b64()
        result = self.bot.ask_ai(
            'You are on an inventory/items screen. '
            'Look at the Resources tab. Are there any resource chests or items to open/use? '
            'Find any item with a Use button. '
            'Respond JSON ONLY. '
            'Found: {"found": true, "x": 400, "y": 300} '
            'Not found: {"found": false}',
            img
        )

        if result and result.get('found'):
            self.bot.tap(result['x'], result['y'])
            self.bot.wait(2)
            # Look for Use button
            img2 = self.bot.screenshot_b64()
            use = self.bot.ask_ai(
                'Is there a Use or Open button? Respond JSON ONLY. '
                'Found: {"found": true, "x": 1050, "y": 590} '
                'Not found: {"found": false}',
                img2
            )
            if use and use.get('found'):
                self.bot.tap(use['x'], use['y'])
                self.bot.wait(2)
                print('  [items] Used item!')
        else:
            print('  [items] No usable items.')

        # Close
        img = self.bot.screenshot_b64()
        close = self.bot.ask_ai(
            'Find the X or Close button. Respond JSON ONLY. '
            'Example: {"found": true, "x": 1230, "y": 77} '
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

