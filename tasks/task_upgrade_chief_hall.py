class TaskUpgradeChiefHall:
    name = 'Upgrade Chief Hall'

    def __init__(self, bot):
        self.bot = bot

    def _find_building(self):
        '''Search for building, swipe if not found'''
        for attempt in range(3):
            print(f'  [upgrade_ch] Searching for building (attempt {attempt+1})...')
            img = self.bot.screenshot_b64()
            result = self.bot.ask_ai(
                'You are looking at a Viking Rise city screen. '
                'Find the Chief Hall or main castle/palace building (the largest building). '
                'Look for buildings with icons or labels. '
                'Respond JSON ONLY. '
                'Found: {"found": true, "x": 500, "y": 350} '
                'Not found: {"found": false}',
                img
            )
            if result and result.get('found'):
                return result
            # Swipe to look around
            if attempt == 0:
                self.bot.swipe(640, 360, 400, 200)
            elif attempt == 1:
                self.bot.swipe(400, 200, 800, 500)
            self.bot.wait(2)
        return None

    def run(self):
        print('  [upgrade_ch] Starting...')
        result = self._find_building()
        if not result:
            print('  [upgrade_ch] Building not found.')
            self.bot.go_to_city()
            return False

        print(f'  [upgrade_ch] Found at ({result["x"]}, {result["y"]}), tapping...')
        self.bot.tap(result['x'], result['y'])
        self.bot.wait(4)

        # Look for action button
        print('  [upgrade_ch] Looking for action...')
        img = self.bot.screenshot_b64()
        action = self.bot.ask_ai(
            'You are in the Chief Hall menu. Find an Upgrade button to upgrade the hall. '
            'Respond JSON ONLY. '
            'Found: {"found": true, "x": 640, "y": 500} '
            'Not found: {"found": false}',
            img
        )

        if action and action.get('found'):
            print(f'  [upgrade_ch] Tapping action...')
            self.bot.tap(action['x'], action['y'])
            self.bot.wait(3)

            # Confirm if needed
            img2 = self.bot.screenshot_b64()
            confirm = self.bot.ask_ai(
                'Is there a Confirm, OK, Train, Upgrade, or Start button? '
                'Respond JSON ONLY. '
                'Found: {"found": true, "x": 640, "y": 500} '
                'Not found: {"found": false}',
                img2
            )
            if confirm and confirm.get('found'):
                self.bot.tap(confirm['x'], confirm['y'])
                self.bot.wait(3)
            print('  [upgrade_ch] Done!')
        else:
            print('  [upgrade_ch] No action available.')

        # Close
        print('  [upgrade_ch] Closing...')
        self.bot.tap(35, 25)
        self.bot.wait(3)
        s = self.bot.detect_screen()
        if s and 'city' not in s.get('screen', '').lower():
            self.bot.tap(35, 25)
            self.bot.wait(2)
            self.bot.go_to_city()
        return True

