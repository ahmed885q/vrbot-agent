"""Task: Hall of Valor - Free Summon (Hero + Skill)

Strategy v4 (Template Match):
  1. Go to city → zoom in
  2. Tap grid positions across the city
  3. After each tap: template match "text_hall_of_valor" (FREE, ~5ms)
  4. If found → enter summon → claim free summons
  0 API calls to find building, ~3-4 total for summon flow
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

    # Grid positions to tap (1280x720 coords, avoid edges)
    GRID_POSITIONS = [
        (640, 300), (640, 380), (640, 250),
        (520, 300), (760, 300), (520, 380), (760, 380),
        (420, 280), (860, 280), (420, 360), (860, 360),
        (380, 320), (900, 320), (560, 220), (720, 220),
        (640, 200), (520, 430), (760, 430),
    ]

    SCAN_AFTER_PAN = [
        (640, 300), (520, 300), (760, 300),
        (420, 340), (860, 340), (640, 220),
        (560, 380), (720, 380),
    ]

    def _zoom_in(self, times=3):
        d = self.TOUCH_DEV
        self.log.info(f"Zooming in ({times}x)...")
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

    def _check_hall_of_valor(self):
        """Template match for 'Hall of Valor' text (FREE, ~5ms)."""
        from vrbot_core import _init_templates
        tm = _init_templates()
        if tm:
            img = self.bot.screenshot_b64()
            result = tm.find_any(["text_hall_of_valor"], screenshot_b64=img)
            if result:
                self.log.info(f"✔ Template matched \"Hall of Valor\"!")
                return True
        return False

    def _dismiss_popup(self):
        self._tap_ui(None, fallback_xy=self.DISMISS_SPOT, wait_after=1)

    def _recover_to_city(self):
        for _ in range(3):
            r = self.bot.detect_screen(force=True)
            if r and r.get('screen') == 'city':
                return True
            self.bot.adb_back()
            self.bot.wait(2)
        return self.bot.go_to_city()

    def _is_in_summon(self):
        """Check if we're in summon screen using YOLO (FREE)."""
        summon = self.bot.yolo_find_any([
            "free_summon_btn", "hero_summon_btn", "skill_summon_btn",
            "summon_tab", "summon_btn", "energy_summon_btn", "summon_10x_btn"
        ])
        return summon is not None

    def _scan_grid(self, positions):
        """Tap positions, template match after each tap."""
        for x, y in positions:
            self._tap_ui(None, fallback_xy=(x, y), wait_after=1.5)

            # Template match: "Hall of Valor" text (FREE)
            if self._check_hall_of_valor():
                self.log.info(f"✔ Found at grid ({x},{y})!")
                return x, y

            # Check if we entered summon screen directly (YOLO - FREE)
            if self._is_in_summon():
                self.log.info(f"✔ Entered summon directly from ({x},{y})!")
                return x, y

            # Quick check: did we leave city?
            r = self.bot.detect_screen(force=True)
            if r:
                screen = r.get('screen', '')
                if screen == 'city':
                    continue
                elif screen in ('summon', 'hero_summon_popup', 'skill_summon_popup'):
                    self.log.info(f"✔ Entered summon from ({x},{y})!")
                    return x, y
                elif screen != 'city':
                    self.log.info(f"({x},{y}): entered {screen}, recovering...")
                    self._recover_to_city()
                    self.bot.wait(1)

        return None, None

    def _enter_summon(self, bx, by):
        """Enter summon screen from building popup."""
        img = self.bot.screenshot_b64()
        result = self.bot.ask_ai(
            'Viking Rise building popup (1280x720). '
            'Find the RIGHTMOST circular action button (Enter button). '
            'JSON ONLY: {"x": <number>, "y": <number>}',
            img
        )

        if result and 'x' in result:
            ex, ey = int(result['x']), int(result['y'])
            self.log.info(f"Entering at ({ex}, {ey})...")
            self.bot.tap(ex, ey, jitter=False)
            self.bot.wait(4)

            r = self.bot.detect_screen(force=True)
            if r and r.get('screen') in ('summon', 'hero_summon_popup', 'skill_summon_popup'):
                return True

            img2 = self.bot.screenshot_b64()
            r2 = self.bot.ask_ai(
                'Is this a SUMMON screen with Hero/Skill tabs? '
                'JSON ONLY: {"summon": true} or {"summon": false}',
                img2
            )
            if r2 and r2.get('summon'):
                return True

        # Fallback
        for ox in [200, 130, 260]:
            ex = bx + ox
            if ex < 100 or ex > 1250:
                continue
            self.bot.tap(ex, 420, jitter=False)
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
        free_btn = self.bot.yolo_find_any(["free_summon_btn"])
        if free_btn:
            return True

        img = self.bot.screenshot_b64()
        result = self.bot.ask_ai(
            'Bottom of summon screen: is there a "Free Summon" button? '
            'Or countdown/paid buttons? '
            'JSON ONLY: {"free": true} or {"free": false}',
            img
        )
        return result and result.get('free', False)

    def _do_free_summon(self, tab_name):
        self.log.info(f"Free {tab_name}! Summoning...")
        free_btn = self.bot.yolo_find_any(["free_summon_btn"])
        if free_btn:
            self._tap_ui(None, fallback_xy=(free_btn['x'], free_btn['y']), wait_after=10)
        else:
            self._tap_ui(None, fallback_xy=self.FREE_SUMMON_BTN, wait_after=10)
        self._tap_center()

    def _find_building(self):
        """Find Hall of Valor using grid-tap + template matching."""
        self.bot.go_to_city()
        self.bot.wait(2)
        self._zoom_in(3)
        self.bot.wait(2)

        # Phase 1: Scan current view
        self.log.info("Phase 1: Scanning current view...")
        bx, by = self._scan_grid(self.GRID_POSITIONS)
        if bx is not None:
            return bx, by

        # Phase 2: Pan and scan
        pans = [
            ('right', (640, 360, 300, 360)),
            ('left',  (640, 360, 980, 360)),
            ('up',    (640, 360, 640, 550)),
            ('down',  (640, 360, 640, 170)),
        ]

        for direction, swipe_coords in pans:
            self.log.info(f"Panning {direction}...")
            self._swipe_ui(direction=direction, fallback_coords=swipe_coords)
            self.bot.wait(2)

            bx, by = self._scan_grid(self.SCAN_AFTER_PAN)
            if bx is not None:
                return bx, by

        return None, None

    def run(self):
        if not self._cooldown_ok():
            return True

        bx, by = self._find_building()

        if bx is None:
            self.log.info("❌ Building not found.")
            self.bot.go_to_city()
            return False

        # Check if already in summon screen (YOLO first - FREE)
        already_in = self._is_in_summon()

        if not already_in:
            r = self.bot.detect_screen(force=True)
            already_in = r and r.get('screen') in ('summon', 'hero_summon_popup', 'skill_summon_popup')

        if not already_in:
            img = self.bot.screenshot_b64()
            r2 = self.bot.ask_ai(
                'Is this a SUMMON screen with Hero/Skill tabs? '
                'JSON ONLY: {"summon": true} or {"summon": false}',
                img
            )
            already_in = r2 and r2.get('summon')

        if not already_in:
            if not self._enter_summon(bx, by):
                self.log.info("❌ Could not enter summon screen.")
                self._dismiss_popup()
                self.bot.go_to_city()
                return False

        summoned = False
        for tab_name, tab_coords in self.SUMMON_TABS:
            self.log.info(f"Checking {tab_name}...")
            self._tap_ui(None, fallback_xy=tab_coords, wait_after=3)

            if self._is_free_available():
                self._do_free_summon(tab_name)
                summoned = True
            else:
                self.log.info(f"{tab_name} - on cooldown.")

        self._tap_ui(None, fallback_xy=self.BACK_ARROW, wait_after=2)
        self.bot.adb_back()
        self.bot.wait(1)
        self.bot.go_to_city()

        self._save_cooldown()
        if summoned:
            self.log.info("✔ Free summons claimed!")
        else:
            self.log.info("No free summons available.")
        return True
