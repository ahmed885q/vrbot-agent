"""Task: Auto VIP — Claim VIP points, daily VIP rewards, and VIP chest
v1.0 — GnBot Parity Feature

Flow:
  City → VIP panel (avatar icon or VIP icon) → Claim daily VIP reward
  → Claim VIP chest if tier full → Check VIP points → Close

GnBot Logic Replicated:
  1. Open VIP panel via avatar or dedicated VIP button
  2. Claim the free daily VIP reward (24h cooldown reward)
  3. If VIP level chest is available — claim it
  4. Log current VIP level and points for tracking

Viking Rise VIP Notes:
  - VIP is earned through spending diamonds/crystals
  - Daily free VIP reward is available regardless of VIP level
  - VIP chests unlock at VIP 3, 5, 8, 10, 12, 14, 16
  - VIP points decay over time if not refreshed
"""

import random
from tasks.base_task import BaseTask

# ── Fallback coords (1280x720) ──────────────────────────────────────
AVATAR_ICON    = (50, 50)     # player avatar icon (top left)
VIP_ICON       = (200, 50)    # VIP badge/icon near avatar
VIP_DAILY_BTN  = (640, 450)   # daily VIP reward claim button
VIP_CHEST_BTN  = (640, 350)   # VIP level chest claim button
CLOSE_BTN      = (1220, 60)   # close/X button


class TaskAutoVip(BaseTask):
    name = "Auto VIP Claim"
    tag = "auto_vip"
    cooldown_hours = 22   # slightly under 24h to avoid drift

    def _open_vip_panel(self):
        """Open the VIP panel via avatar or VIP icon."""
        bot = self.bot

        # Try VIP icon first (may show as VIP badge near avatar)
        found = self._find_and_tap(
            "Find the VIP icon, VIP badge, or player level badge near the top-left "
            "avatar area. It may say 'VIP' or show a crown/star icon.",
            wait_after=3,
        )
        if found:
            return True

        # Try avatar → VIP tab
        self._tap_ui(None, fallback_xy=AVATAR_ICON, wait_after=2,
                     ai_prompt="Tap the player avatar icon in the top-left corner")
        bot.wait(2)

        found = self._find_and_tap(
            "Find and tap a 'VIP' tab or 'VIP' button inside the player profile panel.",
            wait_after=3,
        )
        return found

    def _claim_daily_vip(self):
        """Claim the daily VIP reward if available. Returns True if claimed."""
        bot = self.bot
        img = bot.screenshot_b64()
        result = bot.ask_ai(
            "Viking Rise VIP panel (1280x720). Is there a daily VIP reward "
            "that can be claimed? It usually shows as a 'Claim', 'Collect', or highlighted "
            "reward button with a 24h timer that is ready (timer at 00:00 or green/glowing). "
            '{"claimable": true, "x": 640, "y": 450} or {"claimable": false}. JSON ONLY.',
            img, 80,
        )

        if result and result.get("claimable"):
            x = result.get("x", VIP_DAILY_BTN[0])
            y = result.get("y", VIP_DAILY_BTN[1])
            bot.tap(x, y)
            bot.wait(2)
            self._dismiss_popup()
            self.log.info(f"  ✔ Daily VIP reward claimed at ({x}, {y})")
            return True

        self.log.info("  Daily VIP reward not ready")
        return False

    def _claim_vip_chest(self):
        """Claim VIP level chest if available. Returns True if claimed."""
        bot = self.bot
        img = bot.screenshot_b64()
        result = bot.ask_ai(
            "Viking Rise VIP panel (1280x720). Is there a VIP level chest or "
            "milestone reward that is ready to open/claim? It usually appears as "
            "a glowing chest icon when the VIP progress bar is full. "
            '{"ready": true, "x": 640, "y": 350} or {"ready": false}. JSON ONLY.',
            img, 80,
        )

        if result and result.get("ready"):
            x = result.get("x", VIP_CHEST_BTN[0])
            y = result.get("y", VIP_CHEST_BTN[1])
            bot.tap(x, y)
            bot.wait(2)
            self._dismiss_popup()
            self.log.info(f"  ✔ VIP chest claimed at ({x}, {y})")
            return True

        self.log.info("  No VIP chest available")
        return False

    def _log_vip_status(self):
        """Read and log current VIP level for monitoring."""
        bot = self.bot
        img = bot.screenshot_b64()
        result = bot.ask_ai(
            "Viking Rise VIP panel (1280x720). What is the current VIP level shown? "
            'Return {"vip_level": 5} or {"vip_level": null} if not visible. JSON ONLY.',
            img, 50,
        )
        if result and result.get("vip_level") is not None:
            self.log.info(f"  VIP Level: {result['vip_level']}")

    def run(self):
        if not self._cooldown_ok():
            return True

        bot = self.bot
        bot.go_to_city()
        bot.wait(2)

        self.log.info("Opening VIP panel…")
        opened = self._open_vip_panel()
        if not opened:
            self.log.warning("Could not open VIP panel — skipping")
            self._save_cooldown()
            return True

        # Log VIP status for monitoring
        self._log_vip_status()

        daily = self._claim_daily_vip()
        chest = self._claim_vip_chest()

        self._safe_close()
        bot.go_to_city()

        self.log.info(
            f"✔ VIP done — daily={'✔' if daily else '✗'} "
            f"chest={'✔' if chest else '✗'}"
        )

        self._save_cooldown()
        return True
