"""
VRBOT Agent — Anti-Ban Humanizer
Simulates human-like behavior patterns to avoid game detection.
Inspired by GnBots' safe botting practices.
"""
import random
import time
import math
import logging
from datetime import datetime, timedelta

log = logging.getLogger("vrbot.antiban")


class Humanizer:
    """Simulates human behavior to avoid bot detection."""

    def __init__(self, config=None):
        cfg = config or {}
        self.min_click_delay = cfg.get("min_click_delay", 800) / 1000.0
        self.max_click_delay = cfg.get("max_click_delay", 3500) / 1000.0
        self.pixel_offset = cfg.get("pixel_offset", 12)
        self.rest_interval_min = cfg.get("rest_interval_min", 30)
        self.rest_interval_max = cfg.get("rest_interval_max", 60)
        self.rest_duration_min = cfg.get("rest_duration_min", 5)
        self.rest_duration_max = cfg.get("rest_duration_max", 15)
        self.session_max_hours = cfg.get("session_max_hours", 8)
        self.sleep_start = cfg.get("sleep_hours_start", 23)
        self.sleep_end = cfg.get("sleep_hours_end", 7)
        self.shuffle_actions = cfg.get("action_order_shuffle", True)

        # Session tracking
        self._session_start = datetime.now()
        self._action_count = 0
        self._last_rest = datetime.now()
        self._total_actions = 0
        self._fatigue_level = 0.0  # 0.0 - 1.0

    # ─── Delays ───────────────────────────────────────────────

    def delay(self, context="normal"):
        """Human-like random delay between actions."""
        base = self._get_base_delay(context)
        # Add fatigue factor — tired humans are slower
        fatigue_bonus = self._fatigue_level * 1.5
        delay = base + fatigue_bonus
        # Add slight randomness using gaussian distribution
        delay = max(0.3, random.gauss(delay, delay * 0.2))
        time.sleep(delay)
        self._action_count += 1
        self._total_actions += 1
        self._update_fatigue()

    def _get_base_delay(self, context):
        """Get base delay based on action context."""
        delays = {
            "fast":    (0.3, 0.8),    # Quick taps (dismiss, close)
            "normal":  (0.8, 2.0),    # Regular actions
            "slow":    (1.5, 3.5),    # Careful actions (upgrades, trains)
            "reading": (2.0, 5.0),    # Simulating reading text
            "thinking": (3.0, 8.0),   # Simulating decision making
            "menu":    (0.5, 1.5),    # Menu navigation
        }
        lo, hi = delays.get(context, (self.min_click_delay, self.max_click_delay))
        return random.uniform(lo, hi)

    def micro_delay(self):
        """Very short delay between rapid sequential actions."""
        time.sleep(random.uniform(0.1, 0.4))

    # ─── Click Offset ─────────────────────────────────────────

    def offset(self, base_offset=None):
        """Get random pixel offset for click position."""
        off = base_offset or self.pixel_offset
        # Use gaussian distribution — clicks cluster around center
        return int(random.gauss(0, off / 2.5))

    def offset_xy(self, x, y, base_offset=None):
        """Apply random offset to coordinates."""
        return (
            x + self.offset(base_offset),
            y + self.offset(base_offset)
        )

    # ─── Rest / Break System ──────────────────────────────────

    def should_rest(self):
        """Check if it's time for a break."""
        elapsed = (datetime.now() - self._last_rest).total_seconds() / 60
        # Random rest interval
        rest_interval = random.uniform(self.rest_interval_min, self.rest_interval_max)
        return elapsed >= rest_interval

    def take_rest(self):
        """Simulate a natural break."""
        duration = random.uniform(self.rest_duration_min, self.rest_duration_max) * 60
        log.info(f"😴 Taking a rest for {duration/60:.1f} minutes (human simulation)")
        self._last_rest = datetime.now()
        self._fatigue_level = max(0, self._fatigue_level - 0.3)
        time.sleep(duration)
        log.info("☀️ Break finished, resuming...")

    def should_sleep(self):
        """Check if it's sleep hours (stop botting)."""
        hour = datetime.now().hour
        if self.sleep_start > self.sleep_end:
            return hour >= self.sleep_start or hour < self.sleep_end
        return self.sleep_start <= hour < self.sleep_end

    def session_expired(self):
        """Check if session exceeded max hours."""
        elapsed = (datetime.now() - self._session_start).total_seconds() / 3600
        return elapsed >= self.session_max_hours

    def reset_session(self):
        """Reset session timer."""
        self._session_start = datetime.now()
        self._action_count = 0
        self._fatigue_level = 0.0

    # ─── Action Randomization ─────────────────────────────────

    def shuffle_tasks(self, tasks):
        """Slightly shuffle task order to avoid patterns."""
        if not self.shuffle_actions or len(tasks) < 2:
            return tasks

        tasks = list(tasks)
        # Don't fully shuffle — just swap a few adjacent items
        swaps = random.randint(1, max(1, len(tasks) // 3))
        for _ in range(swaps):
            i = random.randint(0, len(tasks) - 2)
            # Only swap if priority allows
            if hasattr(tasks[i], 'priority') and hasattr(tasks[i+1], 'priority'):
                if abs(tasks[i].priority - tasks[i+1].priority) <= 2:
                    tasks[i], tasks[i+1] = tasks[i+1], tasks[i]
            else:
                tasks[i], tasks[i+1] = tasks[i+1], tasks[i]
        return tasks

    def random_idle_action(self, adb):
        """Perform random idle actions (scroll, zoom) to look human."""
        action = random.choice(["scroll", "zoom", "wait", "nothing", "nothing"])

        if action == "scroll":
            # Random map scroll
            x1 = random.randint(300, 900)
            y1 = random.randint(200, 500)
            dx = random.randint(-200, 200)
            dy = random.randint(-150, 150)
            adb.swipe(x1, y1, x1 + dx, y1 + dy,
                      duration_ms=random.randint(300, 800), human=True)
            log.debug("Idle: random scroll")

        elif action == "zoom":
            adb.pinch_zoom(640, 360, zoom_in=random.choice([True, False]))
            log.debug("Idle: random zoom")

        elif action == "wait":
            wait = random.uniform(2, 8)
            log.debug(f"Idle: waiting {wait:.1f}s")
            time.sleep(wait)

    # ─── Fatigue System ───────────────────────────────────────

    def _update_fatigue(self):
        """Update fatigue level based on actions performed."""
        # Fatigue increases with actions, decreases with time
        self._fatigue_level = min(1.0, self._action_count / 500)

    @property
    def stats(self):
        """Return humanizer stats."""
        elapsed = (datetime.now() - self._session_start).total_seconds() / 3600
        return {
            "session_hours": round(elapsed, 2),
            "total_actions": self._total_actions,
            "fatigue_level": round(self._fatigue_level, 2),
            "is_sleep_time": self.should_sleep(),
            "needs_rest": self.should_rest(),
        }

    # ─── Swipe Patterns ──────────────────────────────────────

    def human_swipe_duration(self, distance):
        """Calculate human-like swipe duration based on distance."""
        base = 200 + (distance * 0.8)
        return int(base + random.uniform(-80, 120))

    def bezier_points(self, start, end, control=None, steps=10):
        """Generate bezier curve points for smooth swipe path."""
        if control is None:
            mid_x = (start[0] + end[0]) // 2 + random.randint(-30, 30)
            mid_y = (start[1] + end[1]) // 2 + random.randint(-20, 20)
            control = (mid_x, mid_y)

        points = []
        for i in range(steps + 1):
            t = i / steps
            x = (1-t)**2 * start[0] + 2*(1-t)*t * control[0] + t**2 * end[0]
            y = (1-t)**2 * start[1] + 2*(1-t)*t * control[1] + t**2 * end[1]
            points.append((int(x), int(y)))
        return points

