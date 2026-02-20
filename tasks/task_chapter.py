class TaskChapter:
    name = 'Chapter'

    def __init__(self, bot):
        self.bot = bot

    def run(self):
        print('  [chapter] Looking for icon...')
        img = self.bot.screenshot_b64()
        result = self.bot.ask_ai(
            'You are looking at a Viking Rise city screen. '
            'Find the Chapter, Story, or Campaign icon on the screen. '
            'Respond JSON ONLY. '
            'Found: {"found": true, "x": 640, "y": 400} '
            'Not found: {"found": false}',
            img
        )

        if not result or not result.get('found'):
            print('  [chapter] Icon not found.')
            return False

        print(f'  [chapter] Tapping...')
        self.bot.tap(result['x'], result['y'])
        self.bot.wait(4)

        # Look for action
        print('  [chapter] Looking for action...')
        for i in range(3):
            img = self.bot.screenshot_b64()
            action = self.bot.ask_ai(
                'Find a Start, Continue, Claim, or Next button. '
                'Respond JSON ONLY. '
                'Found: {"found": true, "x": 640, "y": 500} '
                'Not found: {"found": false}',
                img
            )
            if action and action.get('found'):
                print(f'  [chapter] Action {i+1}...')
                self.bot.tap(action['x'], action['y'])
                self.bot.wait(3)
                self.bot.tap(640, 400)
                self.bot.wait(2)
            else:
                break

        print('  [chapter] Closing...')
        self.bot.tap(35, 25)
        self.bot.wait(3)
        s = self.bot.detect_screen()
        if s and 'city' not in s.get('screen', '').lower():
            self.bot.tap(35, 25)
            self.bot.wait(2)
            self.bot.go_to_city()
        return True

