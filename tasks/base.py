"""
Base Task — All Viking Rise tasks inherit from this
Provides common helpers for tapping, finding UI, navigating
"""

import asyncio
import logging
import time
from typing import Optional, Tuple

log = logging.getLogger("vrbot.task")


class BaseTask:
    """Base class for all bot tasks"""

    id: str = "base"
    name: str = "Base Task"
    interval_sec: int = 300  # default: every 5 minutes

    def __init__(self, adb, vision, humanizer, ws, config):
        self.adb = adb
        self.vision = vision
        self.humanizer = humanizer
        self.ws = ws
        self.config = config
        self.log = logging.getLogger(f"vrbot.task.{self.id}")

    async def execute(self):
        """Override this in subclass"""
        raise NotImplementedError

    # ─── Helpers ────────────────────────────────────

    async def tap(self, x: int, y: int):
        """Human-like tap"""
        rx, ry = self.humanizer.randomize_pos(x, y)
        self.adb.tap(rx, ry)
        await self.humanizer.short_delay()

    async def tap_template(self, template: str, timeout: float = 5.0) -> bool:
        """Find and tap a template image"""
        match = self.vision.wait_for_template(template, timeout=timeout)
        if match:
            await self.tap(match.center_x, match.center_y)
            return True
        self.log.debug(f"Template not found: {template}")
        return False

    async def tap_match(self, match) -> bool:
        """Tap a MatchResult"""
        if match:
            rx, ry = self.humanizer.randomize_region(
                match.x, match.y, match.width, match.height
            )
            self.adb.tap(rx, ry)
            await self.humanizer.short_delay()
            return True
        return False

    async def swipe(self, x1: int, y1: int, x2: int, y2: int):
        """Human-like swipe"""
        sx1, sy1, sx2, sy2, dur = self.humanizer.humanize_swipe(x1, y1, x2, y2)
        self.adb.swipe(sx1, sy1, sx2, sy2, dur)
        await self.humanizer.short_delay()

    async def wait_and_tap(self, template: str, timeout: float = 10.0) -> bool:
        """Wait for template to appear then tap it"""
        match = self.vision.wait_for_template(template, timeout=timeout)
        if match:
            await self.tap(match.center_x, match.center_y)
            return True
        return False

    def on_screen(self, template: str, threshold: float = 0.85) -> bool:
        """Check if template is on screen"""
        return self.vision.template_exists(template, threshold)

    def find(self, template: str) -> Optional[object]:
        """Find template on screen"""
        return self.vision.find_template(template)

    async def back(self):
        """Press back button"""
        self.adb.back()
        await self.humanizer.short_delay()

    async def go_home(self):
        """Navigate to city/home screen"""
        # Tap city button (bottom nav)
        if not await self.tap_template("nav_city.png", timeout=3):
            # Fallback: press back multiple times
            for _ in range(3):
                await self.back()
                await asyncio.sleep(0.5)

    async def close_popups(self, max_attempts: int = 3):
        """Close any popups/dialogs"""
        for _ in range(max_attempts):
            closed = False
            for btn in ["btn_close.png", "btn_x.png", "btn_cancel.png", "popup_close.png"]:
                if await self.tap_template(btn, timeout=1):
                    closed = True
                    break
            if not closed:
                break
            await asyncio.sleep(0.5)

    async def wait(self, seconds: float):
        """Wait with human variance"""
        await asyncio.sleep(seconds)

    async def report(self, message: str):
        """Report log to dashboard"""
        self.log.info(message)
        if self.ws:
            await self.ws.report_log("info", f"[{self.name}] {message}")
