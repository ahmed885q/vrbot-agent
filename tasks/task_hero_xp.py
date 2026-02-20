class TaskHeroXp:
    name = 'Hero XP'

    def __init__(self, bot):
        self.bot = bot

    def run(self):
        # Open hero list (bottom right toolbar)
        print('  [hero_xp] Opening hero list...')
        self.bot.tap(1060, 665)
        self.bot.wait(4)

        print('  [hero_xp] Looking for XP/level up options...')
        img = self.bot.screenshot_b64()
        result = self.bot.ask_ai(
            'You are on a hero list or hero details screen. '
            'Find a Level Up, Add XP, or Train hero button. '
            'Respond JSON ONLY. '
            'Found: {"found": true, "x": 640, "y": 500} '
            'Not found: {"found": false}',
            img
        )

        if result and result.get('found'):
            self.bot.tap(result['x'], result['y'])
            self.bot.wait(3)
            print('  [hero_xp] Applied XP!')
        else:
            print('  [hero_xp] No XP action available.')

        self.bot.tap(35, 25)
        self.bot.wait(3)
        s = self.bot.detect_screen()
        if s and 'city' not in s.get('screen', '').lower():
            self.bot.tap(35, 25)
            self.bot.wait(2)
            self.bot.go_to_city()
        return True

