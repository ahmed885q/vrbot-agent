"""Task: Auto Speedup — استخدم مسرّعات البناء والبحث تلقائياً
v1.0 — GnBot Parity Feature

Flow:
  City → Construction Queue → Apply speedup to active builds
  City → Research → Apply speedup to active research
  Repeats until no more speedups or nothing is building.

GnBot Logic Replicated:
  1. Open construction queue (top left timer icon)
  2. Check if active build exists
  3. Apply ALL available speedups (tap "Use All" or apply one by one)
  4. Repeat for research queue
  5. Done — cooldown 30min (re-check often since builds finish fast)

Config:
  SPEEDUP_CONSTRUCTION — True = speedup buildings
  SPEEDUP_RESEARCH     — True = speedup research
  SPEEDUP_TRAINING     — True = speedup troop training
  USE_ALL_SPEEDUPS     — True = tap "Use All" button (dump all speedups)
"""

import random
import time
from tasks.base_task import BaseTask

# ── Fallback coords (1280x720) ──────────────────────────────────────
BUILD_QUEUE_ICON  = (60, 160)   # construction/build timer icon (top left)
RESEARCH_ICON     = (60, 220)   # research timer icon (top left, below build)
TRAINING_ICON     = (60, 280)   # troop training timer icon
SPEEDUP_BTN       = (640, 520)  # speedup button inside queue panel
USE_ALL_BTN       = (850, 600)  # "Use All" speedup button
CONFIRM_BTN       = (640, 500)  # confirm dialog button

# ── Config ───────────────────────────────────────────────────────────
SPEEDUP_CONSTRUCTION = True
SPEEDUP_RESEARCH     = True
SPEEDUP_TRAINING     = False    # training speedups are expensive — off by default
USE_ALL_SPEEDUPS     = True     # dump all available speedups into active queue
MAX_APPLY_ATTEMPTS   = 3        # per queue type


class TaskAutoSpeedup(BaseTask):
    name = "Auto Speedup"
    tag = "auto_speedup"
    cooldown_hours = 0.5   # 30 min — check frequently

    def _open_build_queue(self):
        """Open construction/build queue via the timer icon or building."""
        bot = self.bot
        found = self._find_and_tap(
            "Find the construction queue icon — usually a timer/clock icon or hammer icon "
            "in the top-left corner of the city screen showing an active build timer.",
            wait_after=3,
        )
        if not found:
            # Fallback: tap known position
            self._tap_ui(None, fallback_xy=BUILD_QUEUE_ICON, wait_after=3,
                         ai_prompt="Tap the build/construction timer in the top-left corner")
        return True

    def _open_research_queue(self):
        """Open research queue via the timer icon or Library building."""
        bot = self.bot
        found = self._find_and_tap(
            "Find the research queue icon — a timer/clock icon near the top-left "
            "of the city screen showing an active research timer. It may be below "
            "the construction timer.",
            wait_after=3,
        )
        if not found:
            self._tap_ui(None, fallback_xy=RESEARCH_ICON, wait_after=3,
                         ai_prompt="Tap the research timer icon in the top-left corner")
        return True

    def _apply_speedups(self, queue_name):
        """Apply speedups to the currently open queue. Returns True if speedups were used."""
        bot = self.bot
        self.log.info(f"  Applying speedups to: {queue_name}")

        # Check if there's an active queue (timer visible)
        img = bot.screenshot_b64()
        status = bot.ask_ai(
            f"Viking Rise city screen (1280x720). Is there an active {queue_name} "
            f"in progress with a countdown timer? "
            '{"active": true, "has_speedup_btn": true} or {"active": false}. JSON ONLY.',
            img, 60,
        )

        if not status or not status.get("active"):
            self.log.info(f"  No active {queue_name} — skipping")
            bot.adb_back()
            bot.wait(1)
            return False

        applied = False
        for attempt in range(MAX_APPLY_ATTEMPTS):
            # Look for "Use All" button first
            if USE_ALL_SPEEDUPS:
                found = self._tap_ui(
                    "use_all",
                    fallback_xy=USE_ALL_BTN,
                    wait_after=2,
                    ai_prompt="Find a 'Use All', 'Apply All', or 'Use All Speedups' button "
                              "to apply all available speedup items at once",
                )
                if found:
                    # Confirm dialog if appears
                    bot.wait(1)
                    self._tap_ui(
                        "confirm",
                        fallback_xy=CONFIRM_BTN,
                        wait_after=2,
                        ai_prompt="Find a 'Confirm', 'OK', or 'Yes' button in the speedup confirmation dialog",
                    )
                    self.log.info(f"  ✔ 'Use All' applied for {queue_name}")
                    applied = True
                    break

            # Fallback: tap speedup button directly
            found = self._tap_ui(
                "speedup",
                fallback_xy=SPEEDUP_BTN,
                wait_after=2,
                ai_prompt="Find the 'Speed Up' or clock/speedup button on the active queue card",
            )
            if found:
                bot.wait(1)
                self._tap_ui(
                    "confirm",
                    fallback_xy=CONFIRM_BTN,
                    wait_after=2,
                    ai_prompt="Find a 'Confirm', 'OK', or 'Use' button in the speedup dialog",
                )
                applied = True
                break

            self.log.debug(f"  Speedup button not found (attempt {attempt+1})")
            bot.wait(random.uniform(1, 2))

        bot.adb_back()
        bot.wait(2)
        return applied

    def run(self):
        if not self._cooldown_ok():
            return True

        bot = self.bot
        bot.go_to_city()
        bot.wait(2)

        total_applied = 0

        # 1. Construction speedup
        if SPEEDUP_CONSTRUCTION:
            self.log.info("=== Construction Speedup ===")
            self._open_build_queue()
            if self._apply_speedups("construction"):
                total_applied += 1

        # Small delay between queues
        bot.go_to_city()
        bot.wait(random.uniform(2, 4))

        # 2. Research speedup
        if SPEEDUP_RESEARCH:
            self.log.info("=== Research Speedup ===")
            self._open_research_queue()
            if self._apply_speedups("research"):
                total_applied += 1

        # 3. Training speedup (optional)
        if SPEEDUP_TRAINING:
            bot.go_to_city()
            bot.wait(random.uniform(1, 3))
            self.log.info("=== Training Speedup ===")
            self._tap_ui(None, fallback_xy=TRAINING_ICON, wait_after=3,
                         ai_prompt="Tap the troop training timer icon in the top-left corner")
            if self._apply_speedups("training"):
                total_applied += 1

        bot.go_to_city()
        self.log.info(f"✔ Auto Speedup done — applied to {total_applied} queue(s)")
        self._save_cooldown()
        return True
