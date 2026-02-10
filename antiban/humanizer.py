"""
Anti-Ban Humanizer — Makes bot actions look human
- Random delays between actions
- Random tap position offsets
- Natural swipe curves
- Rest breaks and session management
"""

import asyncio
import random
import time
import math
import logging
from typing import Tuple

log = logging.getLogger("vrbot.antiban")


class Humanizer:
    def __init__(self, config):
        self.cfg = config
        self._session_start = time.time()
        self._last_rest = time.time()
        self._action_count = 0
        self._total_actions = 0

    # ─── Delays ─────────────────────────────────────

    async def delay(self, min_ms: int = None, max_ms: int = None):
        """Random delay between actions (human-like)"""
        if not self.cfg.enabled:
            await asyncio.sleep(0.1)
            return

        lo = min_ms or self.cfg.tap_delay_min
        hi = max_ms or self.cfg.tap_delay_max

        # Use gaussian distribution (more natural than uniform)
        mean = (lo + hi) / 2
        std = (hi - lo) / 4
        delay_ms = max(lo, min(hi, random.gauss(mean, std)))

        # Occasionally add extra "thinking" time (5% chance)
        if random.random() < 0.05:
            delay_ms += random.randint(1000, 3000)

        await asyncio.sleep(delay_ms / 1000)

    async def short_delay(self):
        """Short delay (UI transition)"""
        await self.delay(300, 800)

    async def medium_delay(self):
        """Medium delay (reading/deciding)"""
        await self.delay(1000, 2500)

    async def long_delay(self):
        """Long delay (complex decision)"""
        await self.delay(2500, 5000)

    # ─── Position Randomization ─────────────────────

    def randomize_pos(self, x: int, y: int, radius: int = None) -> Tuple[int, int]:
        """Add random offset to tap position (human inaccuracy)"""
        if not self.cfg.enabled:
            return x, y

        r = radius or random.randint(self.cfg.tap_offset_min, self.cfg.tap_offset_max)

        # Gaussian offset (most taps near center, few at edges)
        dx = int(random.gauss(0, r / 2))
        dy = int(random.gauss(0, r / 2))

        return x + dx, y + dy

    def randomize_region(self, x: int, y: int, w: int, h: int) -> Tuple[int, int]:
        """Random position within a region (for buttons)"""
        # Don't click edges (looks robotic), stay in center 70%
        margin_x = int(w * 0.15)
        margin_y = int(h * 0.15)
        rx = random.randint(x + margin_x, x + w - margin_x)
        ry = random.randint(y + margin_y, y + h - margin_y)
        return rx, ry

    # ─── Human-like Swipe ──────────────────────────

    def humanize_swipe(
        self, x1: int, y1: int, x2: int, y2: int
    ) -> Tuple[int, int, int, int, int]:
        """
        Humanize swipe: add curve, randomize start/end, duration
        Returns (x1, y1, x2, y2, duration_ms)
        """
        if not self.cfg.enabled:
            return x1, y1, x2, y2, 400

        # Randomize start and end positions
        x1, y1 = self.randomize_pos(x1, y1, 5)
        x2, y2 = self.randomize_pos(x2, y2, 5)

        # Random duration
        duration = random.randint(
            self.cfg.swipe_duration_min,
            self.cfg.swipe_duration_max
        )

        return x1, y1, x2, y2, duration

    # ─── Rest Breaks ───────────────────────────────

    async def maybe_rest(self) -> bool:
        """
        Check if it's time for a rest break.
        Returns True if rested.
        """
        if not self.cfg.enabled:
            return False

        self._action_count += 1
        self._total_actions += 1
        now = time.time()

        # Check session limit
        session_hours = (now - self._session_start) / 3600
        if session_hours >= self.cfg.session_max_hours:
            rest_min = random.randint(self.cfg.session_break_min, self.cfg.session_break_max)
            log.info(f"Session break: {rest_min} minutes (played {session_hours:.1f}h)")
            await asyncio.sleep(rest_min * 60)
            self._session_start = time.time()
            self._last_rest = time.time()
            self._action_count = 0
            return True

        # Check periodic rest
        minutes_since_rest = (now - self._last_rest) / 60
        rest_threshold = random.randint(self.cfg.rest_every_min, self.cfg.rest_every_max)

        if minutes_since_rest >= rest_threshold:
            rest_min = random.randint(self.cfg.rest_duration_min, self.cfg.rest_duration_max)
            log.info(f"Taking a break: {rest_min} minutes ({self._action_count} actions since last rest)")
            await asyncio.sleep(rest_min * 60)
            self._last_rest = time.time()
            self._action_count = 0
            return True

        return False

    # ─── Task Order Randomization ──────────────────

    def shuffle_tasks(self, tasks: list) -> list:
        """Shuffle task execution order (anti-pattern detection)"""
        if not self.cfg.enabled:
            return tasks

        # Fisher-Yates with bias (mostly same order, slight variation)
        shuffled = tasks.copy()
        for i in range(len(shuffled) - 1, 0, -1):
            # 30% chance to swap with a nearby task
            if random.random() < 0.3:
                j = max(0, i - random.randint(1, 3))
                shuffled[i], shuffled[j] = shuffled[j], shuffled[i]
        return shuffled

    # ─── Stats ─────────────────────────────────────

    def stats(self) -> dict:
        now = time.time()
        return {
            "total_actions": self._total_actions,
            "session_hours": round((now - self._session_start) / 3600, 2),
            "since_rest_min": round((now - self._last_rest) / 60, 1),
            "actions_since_rest": self._action_count,
            "enabled": self.cfg.enabled,
        }
