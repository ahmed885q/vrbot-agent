class TaskCinderbone:
    name = 'Cinderbone'

    def __init__(self, bot):
        self.bot = bot

    def run(self):
        print('  [cinder] Switching to world map...')
        # Tap world map button (compass bottom-left)
        self.bot.tap(100, 655)
        self.bot.wait(4)

        s = self.bot.detect_screen()
        screen = s.get('screen', '').lower() if s else ''
        if 'world' not in screen and 'map' not in screen:
            print('  [cinder] Not on world map.')
            self.bot.go_to_city()
            return False

        print('  [cinder] Searching...')
        img = self.bot.screenshot_b64()
        result = self.bot.ask_ai(
            'You are on the Viking Rise world map. '
            'Find a Cinderbone boss or special monster on the map. '
            'Respond JSON ONLY. '
            'Found: {"found": true, "x": 640, "y": 360} '
            'Not found: {"found": false}',
            img
        )

        if result and result.get('found'):
            print(f'  [cinder] Found, tapping...')
            self.bot.tap(result['x'], result['y'])
            self.bot.wait(4)

            img = self.bot.screenshot_b64()
            action = self.bot.ask_ai(
                'Find an Attack or Challenge button. '
                'Respond JSON ONLY. '
                'Found: {"found": true, "x": 640, "y": 500} '
                'Not found: {"found": false}',
                img
            )
            if action and action.get('found'):
                self.bot.tap(action['x'], action['y'])
                self.bot.wait(4)

                # Confirm march
                img2 = self.bot.screenshot_b64()
                march = self.bot.ask_ai(
                    'Is there a March, Attack, Gather, or Confirm button? '
                    'Respond JSON ONLY. '
                    'Found: {"found": true, "x": 640, "y": 600} '
                    'Not found: {"found": false}',
                    img2
                )
                if march and march.get('found'):
                    self.bot.tap(march['x'], march['y'])
                    self.bot.wait(3)
                    print('  [cinder] Marching!')
        else:
            print('  [cinder] Target not found on map.')

        self.bot.go_to_city()
        return True

