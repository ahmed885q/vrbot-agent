import json
import os
import time


class TaskHallOfValor:
    """
    Hall of Valor — Free Summon (Hero + Skill)

    Strategy:
      1. Zoom in → tap buildings → check popup name via AI (text reading)
      2. Once found, try enter buttons from rightmost to left (NO AI for coordinates)
      3. Inside summon screen: fixed coordinates for everything
    """
    name = 'Hall of Valor'

    TOUCH_DEV = '/dev/input/event2'

    # ── Summon screen coordinates (FIXED — 1280×720) ────────────────────
    TAB_HERO          = (175, 148)
    TAB_SKILL         = (175, 245)
    FREE_SUMMON_BTN   = (645, 615)
    RETURN_BTN        = (100, 25)
    BACK_ARROW        = (30, 25)

    COOLDOWN_HOURS    = 24
    COOLDOWN_FILE     = '.hall_of_valor_last_run.json'

    SUMMON_TABS = [
        ('Hero Summon',  TAB_HERO),
        ('Skill Summon', TAB_SKILL),
    ]

    def __init__(self, bot):
        self.bot = bot

    # ── Cooldown ────────────────────────────────────────────────────────
    def _cooldown_ok(self):
        path = self.COOLDOWN_FILE
        if not os.path.exists(path):
            return True
        try:
            with open(path, 'r') as f:
                data = json.load(f)
            last = data.get('last_run', 0)
            elapsed = time.time() - last
            hours_left = self.COOLDOWN_HOURS - (elapsed / 3600)
            if hours_left > 0:
                print(f'  [valor] Cooldown active — {hours_left:.1f}h remaining.')
                return False
            return True
        except Exception:
            return True

    def _save_cooldown(self):
        with open(self.COOLDOWN_FILE, 'w') as f:
            json.dump({'last_run': time.time()}, f)

    # ── Pinch-to-Zoom via sendevent ─────────────────────────────────────
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
        print(f'  [valor] Zoom done.')

    # ── Check if we're on summon screen ─────────────────────────────────
    def _is_summon_screen(self):
        img = self.bot.screenshot_b64()
        result = self.bot.ask_ai(
            'Is this a SUMMON screen? It should show tabs on the left side '
            '(like "Hero Summon", "Skill Summon") and summon cards/buttons. '
            'Respond JSON ONLY: {"summon": true} or {"summon": false}',
            img
        )
        return result and result.get('summon', False)

    # ── Tap and check if popup says "Hall of Valor" ─────────────────────
    def _tap_and_check(self, x, y):
        """Tap location, check if popup name = Hall of Valor. Returns True/False."""
        self.bot.tap(x, y, jitter=False)
        self.bot.wait(2)

        img = self.bot.screenshot_b64()
        result = self.bot.ask_ai(
            'Look at this Viking Rise screenshot (1280x720). '
            'Is there a building popup showing the name "Hall of Valor"? '
            'A building popup has the building name in a banner at the top '
            'and circular action buttons in a row below. '
            'Respond JSON ONLY: '
            '{"match": true} if popup says "Hall of Valor", '
            '{"match": false} if no popup or different building name.',
            img
        )
        if result and result.get('match'):
            return True

        # Dismiss wrong popup
        self.bot.tap(50, 50, jitter=False)
        self.bot.wait(1)
        return False

    # ── Enter summon screen by trying button positions ──────────────────
    def _enter_summon_from_popup(self, building_x):
        """
        After Hall of Valor popup is confirmed, try tapping the Enter/Summon
        button. Buttons are in a row at y≈420, spaced ~130px apart.
        The rightmost button is the Enter button.

        We calculate candidate positions based on building_x and try from
        rightmost to leftmost until summon screen appears.
        """
        # Button row Y is approximately 120px below center of popup area
        btn_y = 420

        # The 4 buttons are roughly centered around building_x+50,
        # spanning ~390px total. Try candidates from rightmost inward.
        # Also include absolute positions that cover most scenarios.
        candidates = []

        # Calculated from building position (4 buttons, ~130px spacing)
        for offset in [390, 260, 130]:
            cx = building_x + offset
            if 100 < cx < 1250:
                candidates.append((cx, btn_y))

        # Absolute fallback positions (cover common button locations)
        for abs_x in [1140, 1020, 900, 780]:
            if (abs_x, btn_y) not in candidates:
                candidates.append((abs_x, btn_y))

        for bx, by in candidates:
            print(f'  [valor] Trying enter button at ({bx}, {by})...')
            self.bot.tap(bx, by, jitter=False)
            self.bot.wait(4)

            if self._is_summon_screen():
                print('  [valor] Entered summon screen!')
                return True

            # Check if popup is still there or dismissed
            # If on city screen, re-tap building
            img = self.bot.screenshot_b64()
            result = self.bot.ask_ai(
                'Is there still a "Hall of Valor" building popup with circular buttons visible? '
                'Respond JSON ONLY: {"popup": true} or {"popup": false}',
                img
            )
            if not (result and result.get('popup')):
                # Popup gone — either entered summon or dismissed
                # Quick check if summon loaded
                if self._is_summon_screen():
                    return True
                print('  [valor] Popup dismissed, trying to re-tap building...')
                self.bot.tap(building_x, 300, jitter=False)
                self.bot.wait(2)

        return False

    # ── Step 1: Find building ───────────────────────────────────────────
    def _find_building(self):
        self.bot.go_to_city()
        self.bot.wait(2)

        self._zoom_in(3)
        self.bot.wait(2)

        # Phase 1: Current view
        phase1_taps = [
            (950, 180), (1050, 250), (850, 150),
            (1100, 350), (750, 200),
        ]

        print('  [valor] Phase 1: Checking current view...')
        for x, y in phase1_taps:
            print(f'  [valor] Tapping ({x}, {y})...')
            if self._tap_and_check(x, y):
                return x  # return building x for button calculation

        # Phase 2: Pan and check
        pan_and_taps = [
            ((640, 360, 400, 200), [(640, 350), (750, 300), (500, 400), (850, 250), (900, 350)]),
            ((640, 360, 850, 500), [(640, 350), (500, 250), (750, 400), (400, 300), (640, 200)]),
            ((640, 360, 300, 360), [(640, 350), (500, 300), (800, 250), (640, 200), (750, 400)]),
            ((640, 360, 980, 360), [(640, 350), (500, 300), (800, 400), (640, 200), (400, 350)]),
        ]

        for i, (swipe, taps) in enumerate(pan_and_taps):
            print(f'  [valor] Phase 2.{i+1}: Panning...')
            self.bot.swipe(*swipe)
            self.bot.wait(2)

            for x, y in taps:
                print(f'  [valor] Tapping ({x}, {y})...')
                if self._tap_and_check(x, y):
                    return x

        return None

    # ── Check if Free Summon available ──────────────────────────────────
    def _is_free_available(self):
        img = self.bot.screenshot_b64()
        result = self.bot.ask_ai(
            'Look at the BOTTOM CENTER of this summon screen. '
            'Is there a button that says exactly "Free Summon"? '
            'Or does it show "Next Free:" with a countdown timer, '
            'or paid buttons like "Summon x1" with gem icon? '
            'Respond JSON ONLY: '
            '{"free": true} if "Free Summon" visible, '
            '{"free": false} if timer or paid only.',
            img
        )
        return result and result.get('free', False)

    # ── Do free summon ──────────────────────────────────────────────────
    def _do_free_summon(self, tab_name):
        print(f'  [valor] Free {tab_name} available! Summoning...')
        self.bot.tap(*self.FREE_SUMMON_BTN)
        self.bot.wait(10)
        self.bot.tap(640, 360)
        self.bot.wait(3)
        self.bot.tap(*self.RETURN_BTN)
        self.bot.wait(3)

    # ── Main run ────────────────────────────────────────────────────────
    def run(self):
        print('  [valor] Starting...')

        if not self._cooldown_ok():
            return False

        # Step 1 — Find building
        building_x = self._find_building()
        if building_x is None:
            print('  [valor] Building not found after all attempts.')
            self.bot.go_to_city()
            return False

        print(f'  [valor] Found Hall of Valor! (building_x={building_x})')

        # Step 2 — Enter summon screen (try buttons from right to left)
        if not self._enter_summon_from_popup(building_x):
            print('  [valor] Could not enter summon screen.')
            self.bot._adb("shell", "input", "keyevent", "4")
            self.bot.wait(1)
            self.bot.go_to_city()
            return False

        # Step 3 — Free Summon on each tab
        summoned = False
        for tab_name, tab_coords in self.SUMMON_TABS:
            print(f'  [valor] Checking {tab_name}...')
            self.bot.tap(*tab_coords)
            self.bot.wait(3)

            if self._is_free_available():
                self._do_free_summon(tab_name)
                summoned = True
            else:
                print(f'  [valor] {tab_name} — on cooldown, skipping.')

        # Step 4 — Exit
        print('  [valor] Closing...')
        self.bot.tap(*self.BACK_ARROW)
        self.bot.wait(2)
        self.bot._adb("shell", "input", "keyevent", "4")
        self.bot.wait(2)
        self.bot.go_to_city()

        self._save_cooldown()
        if summoned:
            print('  [valor] Done! Free summons claimed.')
        else:
            print('  [valor] No free summons available right now.')

        return True
