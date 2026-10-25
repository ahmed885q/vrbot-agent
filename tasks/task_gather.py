"""Task: Auto Gather — Smart resource farming
v2.0 Rewrite:
  - March slot checking before sending: asks AI how many free slots exist
  - Configurable resource priority order (RESOURCE_PRIORITY list)
  - Non-blocking: uses file cooldown so other tasks run between rounds
  - Per-march retry (MAX_RETRIES=2) on failed march verification
  - Smarter world map navigation: only re-navigates if not already there
  - Tracks and logs sent/skipped/failed per round

Config:
  RESOURCE_PRIORITY  — ordered list of resources to send (repeats = multiple marches)
  MAX_MARCHES        — hard cap per round (never exceeds march slots available)
  MARCH_SLOT_CHECK   — if True, ask AI for free slots before sending (slower, safer)
  cooldown_hours     — gap between gather rounds (default 6h)
"""

import random
import time
from tasks.base_task import BaseTask

# ─── Fallback coordinates (calibrated to 1280x720) ──────────────────────────

FALLBACK = {
    "magnify_icon": (155, 525),
    "gather_btn":   (1075, 485),
    "create_btn":   (940, 170),
    "march_btn":    (960, 615),
}

# Category tap + search button per resource type (in the search panel)
RESOURCE_COORDS = {
    "farm":     {"cat": (555, 655),  "search": (555, 490)},
    "sawmill":  {"cat": (725, 655),  "search": (725, 490)},
    "quarry":   {"cat": (890, 655),  "search": (890, 490)},
    "goldmine": {"cat": (1060, 655), "search": (1060, 490)},
}

# ─── Configuration ────────────────────────────────────────────────────────────

# Resources to send, in priority order. Repeat an entry to send multiple marches.
# Example: prioritise gold then food: ["goldmine", "goldmine", "farm", "sawmill", "quarry"]
RESOURCE_PRIORITY = ["farm", "sawmill", "quarry", "goldmine", "goldmine"]

MAX_MARCHES        = 5     # never send more than this per round
MARCH_SLOT_CHECK   = True  # verify free march slots via AI before sending
MAX_RETRIES        = 2     # retries per march if verification fails
DELAY_BETWEEN_MARCHES = (8, 18)  # seconds, random between each march


class TaskGather(BaseTask):
    name = "Auto Gather"
    tag = "gather"
    cooldown_hours = 6   # scheduler handles the gap; no busy-wait loop

    def __init__(self, bot):
        super().__init__(bot)
        self.total_marches_sent = 0
        self.rounds_completed = 0

    # ── helpers ──────────────────────────────────────────────────────────────

    def _ensure_world_map(self):
        """Go to world map; retry once from city on failure."""
        bot = self.bot
        s = bot.detect_screen()
        screen = (s.get("screen", "") if s else "").lower()
        if "world" in screen or "map" in screen:
            return True  # already there

        bot.go_to_city()
        bot.wait(2)
        if bot.go_to_world_map():
            return True
        self.log.warning("World map attempt 1 failed — retrying")
        bot.go_to_city()
        bot.wait(3)
        return bot.go_to_world_map()

    def _free_march_slots(self):
        """Ask AI how many free march slots are visible. Returns int (0–5) or 99 on error."""
        if not MARCH_SLOT_CHECK:
            return 99  # skip check, send up to MAX_MARCHES

        bot = self.bot
        img = bot.screenshot_b64()
        result = bot.ask_ai(
            "Viking Rise city or world map screen. Look at the march queue icons at the "
            "bottom of the screen. Count how many slots are EMPTY/available (greyed out, "
            "no troop icon). "
            '{"free_slots": 3} or {"free_slots": 0}. JSON ONLY.',
            img, 80,
        )
        if not result:
            self.log.debug("March slot check failed — assuming 2 free")
            return 2

        slots = result.get("free_slots", 2)
        self.log.info(f"March slots available: {slots}")
        return int(slots)

    def _send_one_march(self, resource, march_num, total):
        """Open world map search, pick resource, gather, create, march. Returns True on success."""
        bot = self.bot
        info = RESOURCE_COORDS[resource]
        self.log.info(f"\n=== March {march_num}/{total}: {resource} ===")

        for attempt in range(1, MAX_RETRIES + 1):
            if attempt > 1:
                self.log.info(f"  Retry {attempt}/{MAX_RETRIES}…")
                if not self._ensure_world_map():
                    self.log.error("  Cannot reach world map for retry")
                    return False

            # ① Open search panel
            self._tap_ui("search", fallback_xy=FALLBACK["magnify_icon"], wait_after=2,
                         ai_prompt="Find the magnify/search icon on the world map toolbar")
            bot.wait(random.uniform(2, 3.5))

            # ② Select resource category
            cx, cy = info["cat"]
            self._tap_ui(
                None,
                fallback_xy=(cx, cy),
                ai_prompt=f"Tap the '{resource}' or resource category tab in the search panel",
                jitter=True,
                wait_after=1,
            )
            bot.wait(random.uniform(1.5, 3))

            # ③ Search
            sx, sy = info["search"]
            self._tap_ui("search", fallback_xy=(sx, sy), wait_after=5,
                         ai_prompt="Find the Search or Find button in the resource search panel")
            bot.wait(random.uniform(4, 7))

            # ④ Gather
            tapped = self._tap_ui(
                "gather",
                fallback_xy=FALLBACK["gather_btn"],
                wait_after=3,
                ai_prompt="Find and tap the 'Gather' button on the resource tile",
            )
            if not tapped:
                self.log.warning("  Gather button not found — resource may be full/contested")
                bot.adb_back()
                bot.wait(2)
                continue

            bot.wait(random.uniform(2, 4))

            # ⑤ Create squad
            self._tap_ui("create", fallback_xy=FALLBACK["create_btn"], wait_after=3,
                         ai_prompt="Find the 'Create' or squad selection button in march setup")
            bot.wait(random.uniform(2, 3.5))

            # ⑥ March
            marched = self._tap_ui(
                "march",
                fallback_xy=FALLBACK["march_btn"],
                wait_after=4,
                ai_prompt="Find the green 'March' button to dispatch the squad",
            )

            # ⑦ Verify
            bot.wait(2)
            s = bot.detect_screen()
            screen = (s.get("screen", "") if s else "").lower()

            if "world" in screen or "city" in screen or "map" in screen:
                self.total_marches_sent += 1
                self.log.info(f"  ✔ March #{march_num} sent! (total this session: {self.total_marches_sent})")
                return True
            elif "error" in screen or "fail" in screen or "full" in screen:
                self.log.warning(f"  ✗ March failed — screen={screen!r} (attempt {attempt})")
                bot.adb_back()
                bot.wait(3)
            elif marched:
                # march button was tapped, screen just ambiguous — treat as success
                self.total_marches_sent += 1
                self.log.info(f"  ✔ March #{march_num} — screen={screen!r}, treating as sent")
                return True
            else:
                self.log.warning(f"  ✗ March not confirmed (attempt {attempt})")
                bot.adb_back()
                bot.wait(2)

        self.log.warning(f"  ✗ All {MAX_RETRIES} retries failed for march #{march_num}")
        return False

    def _send_round(self):
        """Send up to MAX_MARCHES for this round, respecting slot availability."""
        bot = self.bot

        # Check available march slots from city screen
        bot.go_to_city()
        bot.wait(2)
        free = self._free_march_slots()

        if free == 0:
            self.log.info("No free march slots — skipping round")
            return 0, 0  # (sent, attempted)

        to_send = min(MAX_MARCHES, free, len(RESOURCE_PRIORITY))
        self.log.info(f"Sending {to_send} marches (free slots: {free})")

        sent = 0
        failed = 0

        for i, resource in enumerate(RESOURCE_PRIORITY[:to_send], 1):
            if not self._ensure_world_map():
                self.log.error(f"✗ Cannot reach world map for march #{i}")
                failed += 1
                bot.wait(5)
                continue

            if self._send_one_march(resource, i, to_send):
                sent += 1
            else:
                failed += 1

            if i < to_send:
                wait = random.uniform(*DELAY_BETWEEN_MARCHES)
                self.log.info(f"Waiting {wait:.0f}s before next march…")
                bot.go_to_city()
                bot.wait(wait)

        return sent, failed

    # ── main entry ────────────────────────────────────────────────────────────

    def run(self):
        if not self._cooldown_ok():
            return True

        self.rounds_completed += 1
        self.log.info(
            f"\n╔══════════════════════════════════════╗\n"
            f"║  Auto Gather — Round #{self.rounds_completed:<15}║\n"
            f"╚══════════════════════════════════════╝"
        )

        sent, failed = self._send_round()

        self.bot.go_to_city()

        self.log.info(
            f"✔ Round #{self.rounds_completed} done: "
            f"{sent} sent, {failed} failed — "
            f"next in {self.cooldown_hours}h"
        )

        # Save cooldown so other tasks run; we'll re-queue in cooldown_hours
        if sent > 0 or failed == 0:
            self._save_cooldown()
        else:
            self.log.warning("All marches failed — NOT saving cooldown, will retry sooner")

        return True
