"""Task: Daily Quest — Claim daily quest rewards automatically
v1.0 — GnBot Parity Feature

Flow:
  City → Quest/Mission icon → Claim all completed daily quests
  → Claim chest if bar is full → Close

GnBot Logic Replicated:
  1. Open Daily Quest / Mission panel (bottom toolbar or left panel)
  2. Scroll through quests and claim all completed ones (green checkmark)
  3. If daily progress bar is full → claim the daily chest reward
  4. Cooldown: 4h (quests refresh through the day as you play)

Config:
  CLAIM_DAILY_CHEST — claim the full-bar daily reward chest
  MAX_CLAIMS        — max quest claims per run
"""

import random
from tasks.base_task import BaseTask

# ── Fallback coords (1280x720) ──────────────────────────────────────
QUEST_ICON     = (1175, 645)   # quest/mission icon (bottom right toolbar)
CLAIM_BTN      = (1050, 400)   # claim button on quest row
DAILY_CHEST    = (640, 300)    # daily chest reward position
SCROLL_DOWN    = (640, 400)    # scroll point for quest list

# ── Config ───────────────────────────────────────────────────────────
CLAIM_DAILY_CHEST = True
MAX_CLAIMS        = 10   # max quests to claim per run (safety cap)


class TaskDailyQuest(BaseTask):
    name = "Daily Quest"
    tag = "daily_quest"
    cooldown_hours = 4

    def _open_quest_panel(self):
        """Open the daily quest / mission panel."""
        bot = self.bot
        found = self._tap_ui(
            "quest",
            fallback_xy=QUEST_ICON,
            wait_after=3,
            ai_prompt="Find the 'Quest', 'Mission', or 'Daily Quest' icon — "
                      "usually a scroll, sword, or checklist icon in the bottom right toolbar",
        )
        if not found:
            # Try left panel shortcut
            self._find_and_tap(
                "Find the Quest, Mission, or Daily Quest shortcut on the left-side quick panel "
                "or city sidebar. May show as a scroll icon or checklist icon.",
                wait_after=3,
            )

        # Make sure we're on Daily tab (not Main/Alliance)
        bot.wait(1)
        self._find_and_tap(
            "Find a 'Daily' tab or 'Daily Quests' tab inside the quest panel. "
            "Tap it to switch to the daily quests view if not already there.",
            wait_after=2,
        )
        return True

    def _claim_completed_quests(self):
        """Scan and claim all completed (green) quests. Returns count claimed."""
        bot = self.bot
        claimed = 0

        for i in range(MAX_CLAIMS):
            img = bot.screenshot_b64()
            result = bot.ask_ai(
                "Viking Rise daily quest panel (1280x720). "
                "Is there a completed quest with a green 'Claim' or 'Collect' button visible? "
                "If yes, give coordinates. "
                '{"claimable": true, "x": 1050, "y": 400} or {"claimable": false}. JSON ONLY.',
                img, 80,
            )

            if not result or not result.get("claimable"):
                self.log.info(f"  No more claimable quests (claimed {claimed} so far)")
                break

            x = result.get("x", CLAIM_BTN[0])
            y = result.get("y", CLAIM_BTN[1])
            bot.tap(x, y)
            bot.wait(random.uniform(1.5, 3))
            claimed += 1
            self.log.info(f"  ✔ Claimed quest #{claimed} at ({x}, {y})")

            # Dismiss reward popup if appeared
            self._dismiss_popup()
            bot.wait(1)

        # Scroll down and try again if we hit the cap
        if claimed >= MAX_CLAIMS:
            self.log.info("  Hit MAX_CLAIMS — scrolling for more")
            bot.swipe(SCROLL_DOWN[0], SCROLL_DOWN[1]+150, SCROLL_DOWN[0], SCROLL_DOWN[1]-150, duration=500)
            bot.wait(2)

        return claimed

    def _claim_daily_chest(self):
        """Claim the daily reward chest if progress bar is full."""
        if not CLAIM_DAILY_CHEST:
            return False

        bot = self.bot
        img = bot.screenshot_b64()
        result = bot.ask_ai(
            "Viking Rise quest panel (1280x720). Is there a daily progress chest or reward box "
            "at the top that is ready to claim? It usually appears as a glowing chest icon when "
            "the daily progress bar is full. "
            '{"ready": true, "x": 640, "y": 300} or {"ready": false}. JSON ONLY.',
            img, 80,
        )

        if result and result.get("ready"):
            x = result.get("x", DAILY_CHEST[0])
            y = result.get("y", DAILY_CHEST[1])
            bot.tap(x, y)
            bot.wait(2)
            self._dismiss_popup()
            self.log.info(f"  ✔ Daily chest claimed at ({x}, {y})")
            return True

        self.log.info("  Daily chest not ready yet")
        return False

    def run(self):
        if not self._cooldown_ok():
            return True

        bot = self.bot
        bot.go_to_city()
        bot.wait(2)

        self.log.info("Opening Daily Quest panel…")
        self._open_quest_panel()

        # Claim completed quests
        claimed = self._claim_completed_quests()

        # Try daily chest
        chest = self._claim_daily_chest()

        self._safe_close()
        bot.go_to_city()

        self.log.info(
            f"✔ Daily Quest done — {claimed} quests claimed"
            + (" + daily chest!" if chest else "")
        )

        if claimed > 0 or chest:
            self._save_cooldown()
        else:
            # Nothing to claim yet — save cooldown anyway (will retry in cooldown_hours)
            self._save_cooldown()

        return True
