class TaskDailyGifts:
    name = 'Daily Gifts'

    def __init__(self, bot):
        self.bot = bot

    def run(self):
        # Daily Quests icon is under hero avatar, top-left
        print('  [daily] Opening Daily Quests...')
        self.bot.tap(65, 120)
        self.bot.wait(4)

        s = self.bot.detect_screen()
        screen = s.get('screen', '').lower() if s else ''
        print(f'  [daily] Screen: {screen}')

        # Claim completed quests (green Claim buttons)
        for i in range(5):
            print(f'  [daily] Looking for Claim button (attempt {i+1})...')
            img = self.bot.screenshot_b64()
            result = self.bot.ask_ai(
                'You are on a Daily Quests screen in Viking Rise. '
                'There are quest rows with green Claim buttons and blue Go buttons. '
                'Find a green Claim button (means quest is completed). '
                'Ignore blue Go buttons. '
                'Respond JSON ONLY. '
                'Example found: {"found": true, "x": 1080, "y": 240} '
                'Example not found: {"found": false}',
                img
            )

            if result and result.get('found'):
                x = result['x']
                y = result['y']
                print(f'  [daily] Claiming quest reward at ({x}, {y})...')
                self.bot.tap(x, y)
                self.bot.wait(3)
                # Dismiss reward popup
                self.bot.tap(640, 400)
                self.bot.wait(2)
            else:
                print('  [daily] No more Claim buttons.')
                break

        # Check treasure chests at top (quest point milestones)
        print('  [daily] Checking quest point chests...')
        img = self.bot.screenshot_b64()
        chest = self.bot.ask_ai(
            'Look at the top area with treasure chests at 20, 40, 60, 80, 100 points. '
            'Is any chest glowing, highlighted, or ready to open (claimable)? '
            'Respond JSON ONLY. '
            'Example found: {"found": true, "x": 500, "y": 100} '
            'Example not found: {"found": false}',
            img
        )

        if chest and chest.get('found'):
            print(f'  [daily] Claiming chest...')
            self.bot.tap(chest['x'], chest['y'])
            self.bot.wait(3)
            self.bot.tap(640, 400)
            self.bot.wait(2)

        # Close - back arrow top-left
        print('  [daily] Closing Daily Quests...')
        self.bot.tap(35, 25)
        self.bot.wait(4)
        s = self.bot.detect_screen()
        screen = s.get('screen', '').lower() if s else ''
        if 'city' in screen:
            return True
        self.bot.tap(35, 25)
        self.bot.wait(3)
        self.bot.go_to_city()
        return True
