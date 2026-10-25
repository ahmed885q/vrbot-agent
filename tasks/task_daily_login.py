"""Task: Daily Login Reward — claim the 24h sign-in calendar reward
v1.0

Flow:
  City → Open Mail/Events or left-panel shortcuts → Find daily login
  button → Tap Claim → Dismiss reward popup → Close

The daily login reward UI in Viking Rise appears as a calendar with
day-by-day rewards. It becomes claimable once every 24h.

Strategy:
  1. Try the dedicated shortcut icon (left panel) first
  2. Fall back to the Events/Calendar icon (bottom toolbar)
  3. AI confirms whether it's claimable today
  4. Tap Claim → dismiss

Cooldown: 22h (claim early each day to avoid drift)
"""

from tasks.base_task import BaseTask

# Fallback coords (1280x720)
SIGN_IN_ICON   = (65, 200)   # left panel shortcut — may vary by UI layout
EVENTS_ICON    = (1220, 650)  # bottom-right events/calendar button
CLAIM_APPROX   = (640, 520)   # rough center — AI refines this


class TaskDailyLogin(BaseTask):
    name = "Daily Login Reward"
    tag = "daily_login"
    cooldown_hours = 22  # 22h so it drifts earlier each day, never misses

    def _open_login_calendar(self):
        """Try to open the daily login / sign-in reward panel."""
        bot = self.bot

        # Attempt 1: dedicated sign-in shortcut on left panel
        found = self._find_and_tap(
            "Find a 'Sign In', 'Daily Login', or calendar reward shortcut icon "
            "on the LEFT panel or quick-access bar. It may show a gift box or calendar.",
            wait_after=3,
        )
        if found:
            return True

        # Attempt 2: Events/Calendar in bottom toolbar
        found = self._tap_ui(
            "events",
            fallback_xy=EVENTS_ICON,
            wait_after=3,
            ai_prompt="Find the 'Events', 'Calendar', or 'Activity' icon in the bottom toolbar",
        )
        if found:
            # Inside events list, look for daily login entry
            self._find_and_tap(
                "Inside the Events panel, find and tap 'Daily Login', 'Sign-In Reward', "
                "or 'Daily Attendance' entry.",
                wait_after=3,
            )
            return True

        # Attempt 3: fallback tap at known icon position
        self._tap_ui(None, fallback_xy=SIGN_IN_ICON, wait_after=3,
                     ai_prompt="Tap the daily login or sign-in icon on the left panel")
        return True

    def _is_claimable(self):
        """Ask AI if there's an unclaimed reward on screen. Returns True if yes."""
        bot = self.bot
        img = bot.screenshot_b64()
        result = bot.ask_ai(
            "Viking Rise daily login / sign-in calendar screen (1280x720). "
            "Is there a 'Claim', 'Collect', or glowing reward button for TODAY that hasn't "
            "been claimed yet? A claimed day usually shows a check mark or is greyed out. "
            '{"claimable": true, "x": 640, "y": 500} or {"claimable": false}. JSON ONLY.',
            img, 80,
        )
        if not result:
            return None  # can't verify
        return result if result.get("claimable") else None

    def run(self):
        if not self._cooldown_ok():
            return True

        bot = self.bot
        bot.go_to_city()
        bot.wait(2)

        self.log.info("Opening daily login reward panel…")
        self._open_login_calendar()

        # Verify we can claim
        claim_info = self._is_claimable()
        if claim_info is False:
            # explicitly False means already claimed
            self.log.info("Daily login already claimed today — saving cooldown")
            self._safe_close()
            self._save_cooldown()
            return True

        # claim_info is either dict with coords or None (uncertain)
        if claim_info and isinstance(claim_info, dict):
            x, y = claim_info.get("x", CLAIM_APPROX[0]), claim_info.get("y", CLAIM_APPROX[1])
            self.log.info(f"Tapping Claim at ({x}, {y})…")
            bot.tap(x, y)
        else:
            # AI uncertain — try to tap the claim button directly
            self.log.info("Tapping Claim (AI uncertain, using hybrid detection)…")
            self._tap_ui(
                "claim",
                fallback_xy=CLAIM_APPROX,
                wait_after=3,
                ai_prompt="Find and tap the 'Claim' or 'Collect' button for today's daily login reward",
            )

        bot.wait(3)

        # Dismiss reward popup
        self._dismiss_popup()
        bot.wait(2)

        # Verify dismiss worked
        self._safe_close()

        self.log.info("✔ Daily login reward claimed!")
        self._save_cooldown()
        return True
