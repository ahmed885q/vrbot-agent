"""Task: Hall of Valor - Free Summon (Hero + Skill)

Strategy:
  1. Go to city -> zoom in -> tap buildings one by one
  2. After each tap: check if still on city (recovery if entered wrong building)
  3. If popup visible -> read name -> if Hall of Valor -> enter summon
  4. Dismiss popups by tapping grass, use back only for full screens
"""

import time
from tasks.base_task import BaseTask, cooldown_ok, cooldown_save


class TaskHallOfValor(BaseTask):
    name = 'Hall of Valor'
    tag = 'hall_of_valor'
    cooldown_hours = 24

    TOUCH_DEV = '/dev/input/event2'

    TAB_HERO          = (175, 148)
    TAB_SKILL         = (175, 245)
    FREE_SUMMON_BTN   = (645, 615)
    BACK_ARROW        = (30, 25)
    DISMISS_SPOT      = (200, 550)

    SUMMON_TABS = [
        ('Hero Summon',  TAB_HERO),
        ('Skill Summon', TAB_SKILL),
    ]

    def _zoom_in(self, times=3):
        d = self.TOUCH_DEV
        print(f'  [valor] Zooming in ({times}x)...')
        for t in range(times):
            cmds = []
            cmds.append(f'sendevent {d} 3 47 0; sendevent {d} 3 57 10{t}; sendevent {d} 3 53 590; sendevent {d} 3 54 360; sendevent {d} 3 58 1')
            cmds.append(f'sendevent {d} 3 47 1; sendevent {d} 3 57 20{t}; sendevent {d} 3 53 690; sendevent {d} 3 54 360; sendevent {d} 3 58 1')
            cmds.append(f'sendevent {d} 1 330 1; sendevent {d} 0 0 0')
            for s in range(1, 9):
                f = s / 8
                cmds.append(f'sendevent {d} 3 47 0; sendevent {d} 3 53 {int(590-200*f)}; sendevent {d} 3 54 {int(360-150*f)}')
                cmds.append(f'sendevent {d} 3 47 1; sendevent {d} 3 53 {int(690+200*f)}; sendevent {d} 3 54 {int(360+150*f)}')
                cmds.append(f'sendevent {d} 0 0 0; sleep 0.03')
            cmds.append(f'sendevent {d} 3 47 0; sendevent {d} 3 57 -1; sendevent {d} 3 47 1; sendevent {d} 3 57 -1')
            cmds.append(f'sendevent {d} 1 330 0; sendevent {d} 0 0 0')
            self.bot._adb('shell', '; '.join(cmds))
            time.sleep(0.5)

    def _ensure_city(self):
        for _ in range(5):
            img = self.bot.screenshot_b64()
            result = self.bot.ask_ai(
                'What screen is this? Respond JSON ONLY: '
                '{"screen": "city"} if main city view, '
                '{"screen": "popup"} if building popup with name, '
                '{"screen": "other"} if any other screen.',
                img
            )
            if result:
                screen = result.get('screen', '')
                if screen == 'city':
                    return 'city'
                elif screen == 'popup':
                    return 'popup'
                else:
                    self.bot._adb("shell", "input", "keyevent", "4")
                    self.bot.wait(2)
        return 'unknown'

    def _tap_and_check(self, x, y):
        self.bot.tap(x, y, jitter=False)
        self.bot.wait(2)

        img = self.bot.screenshot_b64()
        result = self.bot.ask_ai(
            'Viking Rise screenshot (1280x720). What do you see? JSON ONLY:\n'
            '1. {"screen": "city_popup", "name": "<building name>"} - building popup\n'
            '2. {"screen": "city"} - city with no popup\n'
            '3. {"screen": "building_interior"} - inside a building\n'
            '4. {"screen": "summon"} - Hall of Valor summon screen',
            img
        )

        if not result:
            return 'unknown', None

        screen = result.get('screen', '')

        if screen == 'city_popup':
            name = result.get('name', '').lower()
            if 'hall of valor' in name or 'valor' in name:
                print(f'  [valor] ✔ Found Hall of Valor!')
                return 'found', result
            else:
                print(f'  [valor] Found: {result.get("name")} - not it.')
                self.bot.tap(*self.DISMISS_SPOT, jitter=False)
                self.bot.wait(1)
                return 'wrong_building', result

        elif screen == 'summon':
            print(f'  [valor] ✔ Entered summon screen directly!')
            return 'summon', result

        elif screen == 'building_interior':
            print(f'  [valor] Wrong building interior, going back...')
            self.bot._adb("shell", "input", "keyevent", "4")
            self.bot.wait(2)
            self._ensure_city()
            return 'wrong_interior', result

        elif screen == 'city':
            return 'empty', result

        return 'unknown', result

    def _enter_summon(self, bx, by):
        img = self.bot.screenshot_b64()
        result = self.bot.ask_ai(
            'Viking Rise building popup (1280x720). '
            'Find the RIGHTMOST circular action button (Enter button). '
            'Respond JSON ONLY: {"x": <number>, "y": <number>}',
            img
        )

        if result and 'x' in result:
            ex, ey = result['x'], result['y']
            print(f'  [valor] AI found Enter at ({ex}, {ey})...')
            self.bot.tap(ex, ey, jitter=False)
            self.bot.wait(4)

            img2 = self.bot.screenshot_b64()
            r2 = self.bot.ask_ai(
                'Is this a SUMMON screen with Hero/Skill tabs? '
                'JSON ONLY: {"summon": true} or {"summon": false}',
                img2
            )
            if r2 and r2.get('summon'):
                return True

            self.bot.tap(bx, by, jitter=False)
            self.bot.wait(2)

        # Fallback positions
        for ex, ey in [(bx+200, 420), (bx+130, 420), (bx+260, 420),
                        (1140, 420), (1020, 420), (900, 420)]:
            if ex < 100 or ex > 1250:
                continue
            self.bot.tap(ex, ey, jitter=False)
            self.bot.wait(4)

            img = self.bot.screenshot_b64()
            r = self.bot.ask_ai(
                'Is this a SUMMON screen? JSON ONLY: '
                '{"summon": true} or {"summon": false}',
                img
            )
            if r and r.get('summon'):
                return True

            self.bot.tap(bx, by, jitter=False)
            self.bot.wait(2)

        return False

    def _is_free_available(self):
        img = self.bot.screenshot_b64()
        result = self.bot.ask_ai(
            'Bottom of summon screen: is there a "Free Summon" button? '
            'Or countdown/paid buttons? '
            'JSON ONLY: {"free": true} or {"free": false}',
            img
        )
        return result and result.get('free', False)

    def _do_free_summon(self, tab_name):
        print(f'  [valor] Free {tab_name}! Summoning...')
        self.bot.tap(*self.FREE_SUMMON_BTN)
        self.bot.wait(10)
        self.bot.tap(640, 360)
        self.bot.wait(3)

    def _find_building(self):
        self.bot.go_to_city()
        self.bot.wait(2)
        self._zoom_in(3)
        self.bot.wait(2)

        phase1 = [
            (640, 280), (780, 220), (500, 320),
            (880, 320), (420, 220), (740, 170),
            (1000, 280), (340, 360), (560, 180),
            (900, 180),
        ]

        print('  [valor] Phase 1: Checking current view...')
        for x, y in phase1:
            status, result = self._tap_and_check(x, y)
            if status in ('found', 'summon'):
                return x, y

        pans = [
            ('right', (640, 360, 200, 360)),
            ('left',  (640, 360, 1080, 360)),
            ('up',    (640, 360, 640, 600)),
            ('down',  (640, 360, 640, 120)),
        ]

        taps_per_pan = [
            (640, 280), (780, 220), (500, 320),
            (880, 320), (420, 220), (560, 180),
            (1000, 280),
        ]

        for direction, swipe_coords in pans:
            print(f'  [valor] Panning {direction}...')
            self.bot.swipe(*swipe_coords)
            self.bot.wait(2)

            for x, y in taps_per_pan:
                status, result = self._tap_and_check(x, y)
                if status in ('found', 'summon'):
                    return x, y

        return None, None

    def run(self):
        if not self._cooldown_ok():
            return True

        bx, by = self._find_building()

        if bx is None:
            print('  [valor] Building not found.')
            self.bot.go_to_city()
            return False

        # Check if already in summon screen
        img = self.bot.screenshot_b64()
        r = self.bot.ask_ai(
            'Is this a SUMMON screen with Hero/Skill tabs? '
            'JSON ONLY: {"summon": true} or {"summon": false}',
            img
        )
        already_in = r and r.get('summon')

        if not already_in:
            if not self._enter_summon(bx, by):
                print('  [valor] Could not enter summon screen.')
                self.bot.tap(*self.DISMISS_SPOT, jitter=False)
                self.bot.wait(1)
                self.bot.go_to_city()
                return False

        summoned = False
        for tab_name, tab_coords in self.SUMMON_TABS:
            print(f'  [valor] Checking {tab_name}...')
            self.bot.tap(*tab_coords)
            self.bot.wait(3)

            if self._is_free_available():
                self._do_free_summon(tab_name)
                summoned = True
            else:
                print(f'  [valor] {tab_name} - on cooldown.')

        self.bot.tap(*self.BACK_ARROW)
        self.bot.wait(2)
        self.bot._adb("shell", "input", "keyevent", "4")
        self.bot.wait(1)
        self.bot.go_to_city()

        self._save_cooldown()
        if summoned:
            print('  [valor] ✔ Free summons claimed!')
        else:
            print('  [valor] No free summons available.')
        return True
