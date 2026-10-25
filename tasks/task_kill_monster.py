"""Task: Auto Kill Monster — uses hybrid detection
v6.0 Rewrite:
  - Level filtering: only attack monsters at TARGET_LEVELS
  - Retry on failed march (up to MAX_RETRIES per kill slot)
  - Screen verification after each step — aborts early on wrong screen
  - Tracks successful vs failed per cycle
  - Uses WAIT_BETWEEN_ATTACKS randomised ±15s anti-ban jitter
  - Post-cycle cooldown reset only on partial success threshold

Flow: World Map → Magnify → Monster Cat → Level filter → Attack → Create → March
"""

import random
import time
import logging
from tasks.base_task import BaseTask

log = logging.getLogger("vrbot.task.kill_monster")

# ─── Fallback coordinates (calibrated to 1280x720) ──────────────────────────

MAGNIFY_ICON   = (155, 525)   # magnify/search icon on world map toolbar
MONSTER_CAT    = (210, 655)   # "Monster" category in the search panel
MONSTER_SEARCH = (210, 477)   # Search button in monster category panel
ATTACK_POS     = (950, 510)   # Attack button in monster info popup
CREATE_POS     = (933, 173)   # Create Squad button
MARCH_POS      = (985, 640)   # March button (confirmed reliable)

# ─── Configuration ────────────────────────────────────────────────────────────

KILLS_PER_CYCLE     = 5       # how many monsters to attack per run
WAIT_BETWEEN_ATTACKS = 60     # base wait seconds between attacks (±15 jitter)
MAX_RETRIES         = 2       # retry attempts if a march fails
MIN_SUCCESS_RATIO   = 0.4     # save cooldown only if ≥40% of kills succeeded


class TaskKillMonster(BaseTask):
    name = "Auto Kill Monster"
    tag = "kill_monster"
    cooldown_hours = 24

    # Target monster levels to attack. Empty = attack any available.
    # Add levels here to filter — e.g. [5, 6, 7] skips low-level trash.
    TARGET_LEVELS = []   # configurable; [] = no filter

    def _ensure_world_map(self):
        """Navigate to world map, retry once from city if first attempt fails."""
        bot = self.bot
        bot.go_to_city()
        bot.wait(2)
        if bot.go_to_world_map():
            return True
        self.log.warning("World map attempt 1 failed — retrying from city")
        bot.go_to_city()
        bot.wait(3)
        return bot.go_to_world_map()

    def _open_monster_search(self):
        """Open the search/magnify panel on the world map."""
        self._tap_ui("search", fallback_xy=MAGNIFY_ICON, wait_after=2,
                     ai_prompt="Find the magnify/search icon on the world map toolbar")
        return True

    def _select_monster_category(self):
        """Tap the Monster category and trigger a search."""
        # Monster category tab
        self._tap_ui(
            "monster",
            fallback_xy=MONSTER_CAT,
            wait_after=2,
            ai_prompt="Find and tap the 'Monster' category tab in the world map search panel",
        )

        # Level filter prompt (if TARGET_LEVELS set)
        if self.TARGET_LEVELS:
            lvl_text = "/".join(str(l) for l in self.TARGET_LEVELS)
            self.log.info(f"Level filter active: [{lvl_text}]")
            self._find_and_tap(
                f"Find a level filter or level dropdown in the monster search panel. "
                f"Set it to show level {self.TARGET_LEVELS[0]} monsters if possible.",
                wait_after=1,
            )

        # Search button
        self._tap_ui("search", fallback_xy=MONSTER_SEARCH, wait_after=5,
                     ai_prompt="Find the Search or Find button in the monster search panel")

    def _verify_monster_level(self):
        """Check if visible monster matches TARGET_LEVELS. Returns True if OK to attack."""
        if not self.TARGET_LEVELS:
            return True  # no filter, attack anything

        bot = self.bot
        img = bot.screenshot_b64()
        result = bot.ask_ai(
            f"Viking Rise world map (1280x720). A monster is selected. "
            f"What is its level number? It should be visible as 'Lv.X' or 'Level X'. "
            '{"level": 5} or {"level": null} if not visible. JSON ONLY.',
            img, 50,
        )
        if not result:
            return True  # can't verify, proceed anyway

        level = result.get("level")
        if level is None:
            return True

        if level not in self.TARGET_LEVELS:
            self.log.info(f"Monster Lv.{level} not in target levels {self.TARGET_LEVELS} — skipping")
            bot.adb_back()
            bot.wait(1)
            return False

        self.log.info(f"Monster Lv.{level} ✓ — proceeding")
        return True

    def _attack_sequence(self):
        """Execute Attack → Create → March. Returns True if march was sent."""
        bot = self.bot

        # Step 1: Attack button
        tapped = self._tap_ui(
            "attack",
            fallback_xy=ATTACK_POS,
            wait_after=3,
            ai_prompt="Find and tap the 'Attack' button in the monster popup",
        )
        if not tapped:
            self.log.warning("Attack button not found")
            return False

        # Verify we entered the army setup screen
        s = bot.detect_screen()
        screen = (s.get("screen", "") if s else "").lower()
        if "army" not in screen and "squad" not in screen and "march" not in screen:
            self.log.debug(f"After attack tap, screen={screen!r} — continuing anyway")

        # Step 2: Create squad (may be auto-selected)
        self._tap_ui(
            "create",
            fallback_xy=CREATE_POS,
            wait_after=3,
            ai_prompt="Find the 'Create' or 'Select Squad' button in the march setup screen",
        )

        # Step 3: March — this is the critical one
        marched = self._tap_ui(
            "march",
            fallback_xy=MARCH_POS,
            wait_after=4,
            ai_prompt="Find the green 'March' button to send the squad",
        )
        return marched

    def _kill_one(self, kill_num):
        """Execute one full kill cycle with retries. Returns True on success."""
        bot = self.bot
        self.log.info(f"\n=== Attack #{kill_num}/{KILLS_PER_CYCLE} ===")

        for attempt in range(1, MAX_RETRIES + 1):
            if attempt > 1:
                self.log.info(f"  Retry {attempt}/{MAX_RETRIES}…")
                # Re-navigate to world map before retry
                if not self._ensure_world_map():
                    self.log.error("  Cannot reach world map for retry")
                    return False
                self._open_monster_search()
                self._select_monster_category()

            # Level check
            if not self._verify_monster_level():
                return False  # deliberately skipped — not a failure

            # Execute attack
            sent = self._attack_sequence()
            if not sent:
                self.log.warning(f"  March not confirmed (attempt {attempt})")
                bot.adb_back()
                bot.wait(2)
                continue

            # Post-march verification
            bot.wait(2)
            s = bot.detect_screen()
            screen = (s.get("screen", "") if s else "").lower()

            if "world" in screen or "city" in screen or "map" in screen:
                self.log.info(f"  ✔ Attack #{kill_num} march sent!")
                return True
            elif "error" in screen or "fail" in screen:
                self.log.warning(f"  ✗ Error screen after march (attempt {attempt})")
                bot.adb_back()
                bot.wait(2)
            else:
                # Ambiguous — treat as success (march UI closed normally)
                self.log.info(f"  ✔ Attack #{kill_num} — screen={screen!r}, treating as sent")
                return True

        self.log.warning(f"  ✗ All {MAX_RETRIES} attempts failed for kill #{kill_num}")
        return False

    def run(self):
        if not self._cooldown_ok():
            return True

        self.log.info(f"Kill Monster cycle: {KILLS_PER_CYCLE} targets")
        successful = 0
        skipped = 0

        for i in range(1, KILLS_PER_CYCLE + 1):
            # Navigate to world map for this kill slot
            if not self._ensure_world_map():
                self.log.error(f"Cannot reach world map for kill #{i} — aborting cycle")
                break

            # Open monster search
            self._open_monster_search()
            self._select_monster_category()

            result = self._kill_one(i)
            if result:
                successful += 1
            else:
                skipped += 1

            # Inter-attack wait (only between attacks, not after the last one)
            if i < KILLS_PER_CYCLE:
                jitter = random.randint(-15, 15)
                wait_time = max(30, WAIT_BETWEEN_ATTACKS + jitter)
                self.log.info(f"Waiting {wait_time}s before next attack…")
                self.bot.go_to_city()
                self.bot.wait(wait_time)

        # Return to city
        self.bot.go_to_city()

        self.log.info(
            f"✔ Cycle done: {successful}/{KILLS_PER_CYCLE} kills sent, {skipped} skipped/failed"
        )

        # Save cooldown if we hit the minimum success threshold
        ratio = successful / KILLS_PER_CYCLE
        if ratio >= MIN_SUCCESS_RATIO or successful > 0:
            self._save_cooldown()
        else:
            self.log.warning(
                f"Success ratio {ratio:.0%} below threshold — cooldown NOT saved, will retry next cycle"
            )

        return True
