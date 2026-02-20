class TaskHeroTraining:
    name = 'Hero Training'

    def __init__(self, bot):
        self.bot = bot

    def _find_building(self):
        '''Search for building, swipe if not found'''
        for attempt in range(3):
            print(f'  [hero_train] Searching for building (attempt {attempt+1})...')
            img = self.bot.screenshot_b64()
            result = self.bot.ask_ai(
                'You are looking at a Viking Rise city screen. '
                'Find the Hero Training ground or training facility for heroes. '
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
        print('  [hero_train] Starting...')
        result = self._find_building()
        if not result:
            print('  [hero_train] Building not found.')
            self.bot.go_to_city()
            return False

        print(f'  [hero_train] Found at ({result["x"]}, {result["y"]}), tapping...')
        self.bot.tap(result['x'], result['y'])
        self.bot.wait(4)

        # Look for action button
        print('  [hero_train] Looking for action...')
        img = self.bot.screenshot_b64()
        action = self.bot.ask_ai(
            'You are on a hero training screen. Find a Train or Start button. '
            'Respond JSON ONLY. '
            'Found: {"found": true, "x": 640, "y": 500} '
            'Not found: {"found": false}',
            img
        )

        if action and action.get('found'):
            print(f'  [hero_train] Tapping action...')
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
            print('  [hero_train] Done!')
        else:
            print('  [hero_train] No action available.')

        # Close
        print('  [hero_train] Closing...')
        self.bot.tap(35, 25)
        self.bot.wait(3)
        s = self.bot.detect_screen()
        if s and 'city' not in s.get('screen', '').lower():
            self.bot.tap(35, 25)
            self.bot.wait(2)
            self.bot.go_to_city()
        return True

