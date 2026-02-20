"""Task: Prosperity — Collect Obtainable Resources

A green Prosperity button appears in the city screen once every 24 hours.
Its position varies based on camera angle, so we use AI to locate it.
Tap it → "Obtainable Resources" popup → tap OK.

Cooldown: 24 hours (only saved when successful).
"""

import json
import os
import time


# OK button on "Obtainable Resources" popup
OK_BTN = (640, 610)


class TaskProsperity:
    name = "Prosperity"

    COOLDOWN_HOURS = 24
    COOLDOWN_FILE  = '.prosperity_last_run.json'

    def __init__(self, bot):
        self.bot = bot

    # ── Cooldown ────────────────────────────────────────────────────────
    def _cooldown_ok(self):
        if not os.path.exists(self.COOLDOWN_FILE):
            return True
        try:
            with open(self.COOLDOWN_FILE, 'r') as f:
                data = json.load(f)
            last = data.get('last_run', 0)
            hours_left = self.COOLDOWN_HOURS - ((time.time() - last) / 3600)
            if hours_left > 0:
                print(f'  [prosperity] Cooldown active — {hours_left:.1f}h remaining.')
                return False
            return True
        except Exception:
            return True

    def _save_cooldown(self):
        with open(self.COOLDOWN_FILE, 'w') as f:
            json.dump({'last_run': time.time()}, f)

    # ── Find and tap the green Prosperity button ────────────────────────
    def _find_prosperity_button(self):
        """
        Look for the green Prosperity button on screen.
        It's a GREEN diamond-shaped icon with a hand/fist symbol,
        located in the bottom-right area among other action buttons.
        """
        img = self.bot.screenshot_b64()
        result = self.bot.ask_ai(
            'Viking Rise city screen (1280x720). '
            'Find the GREEN diamond-shaped button with a HAND/FIST icon. '
            'It is the PROSPERITY button, located in the bottom-right area '
            'among other diamond-shaped action buttons (sword, shield, helm icons). '
            'The Prosperity button is GREEN colored — the others are dark/grey. '
            'Give its CENTER coordinates. '
            'Respond JSON ONLY: {"found": true, "x": 1100, "y": 600} '
            'or {"found": false}',
            img
        )
        if result and result.get('found'):
            return result
        return None

    # ── Main ────────────────────────────────────────────────────────────
    def run(self):
        print('  [prosperity] Starting...')

        if not self._cooldown_ok():
            return False

        bot = self.bot
        bot.go_to_city()
        bot.wait(2)

        # Try to find green Prosperity button
        print('  [prosperity] Looking for Prosperity button...')
        found = self._find_prosperity_button()

        if not found:
            print('  [prosperity] Button not found, trying alternate view...')
            # Swipe to show more of the city
            bot.swipe(640, 360, 400, 200)
            bot.wait(2)
            found = self._find_prosperity_button()

        if not found:
            print('  [prosperity] Prosperity button not available right now.')
            bot.go_to_city()
            return False

        # Tap the green button
        bx, by = found['x'], found['y']
        print(f'  [prosperity] Tapping Prosperity at ({bx}, {by})...')
        bot.tap(bx, by, jitter=False)
        bot.wait(3)

        # Check if Obtainable Resources popup appeared
        img = bot.screenshot_b64()
        result = bot.ask_ai(
            'Is there a popup titled "OBTAINABLE RESOURCES" on screen? '
            'It shows Decor Items with an OK button at the bottom. '
            'Respond JSON ONLY: {"popup": true} or {"popup": false}',
            img
        )

        if result and result.get('popup'):
            print('  [prosperity] Tapping OK...')
            bot.tap(OK_BTN[0], OK_BTN[1], jitter=False)
            bot.wait(2)
            bot.tap(640, 400, jitter=False)
            bot.wait(2)
            bot.go_to_city()
            self._save_cooldown()
            print('  [prosperity] ✔ Prosperity collected!')
            return True
        else:
            print('  [prosperity] Popup did not appear — button may have missed.')
            bot.go_to_city()
            return False
