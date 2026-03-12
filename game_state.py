"""
VRBOT Game State Machine v1.0
================================
Vision-based game state detection and handling.

Uses the 4-layer detection (Template → YOLO → Claude → OpenAI) to determine
the current game state, then dispatches to the appropriate handler.

Usage:
    from game_state import GameStateMachine
    gsm = GameStateMachine(bot)
    state = gsm.get_state()           # → GameScreen.CITY
    gsm.navigate_to(GameScreen.CITY)  # smart navigation
"""

import time
import logging
from enum import Enum
from typing import Optional, Dict, Callable, List, Tuple

log = logging.getLogger("vrbot.gamestate")


# ═══════════════════════════════════════════════════════════════════
# Game Screen Enum — all possible screens the bot can be on
# ═══════════════════════════════════════════════════════════════════

class GameScreen(Enum):
    """All identifiable game screens."""

    # ── Core ──
    CITY = "city"
    WORLD_MAP = "world_map"

    # ── Menus ──
    MAIL_SCREEN = "mail_screen"
    ALLIANCE_SCREEN = "alliance_screen"
    HERO_SCREEN = "hero_screen"
    EVENT_SCREEN = "event_screen"
    SHOP = "shop"
    INVENTORY = "inventory"
    PROFILE = "profile"
    SETTINGS = "settings"
    CHAT = "chat"

    # ── Buildings / Actions ──
    TRAINING = "training"
    BUILDING_INFO = "building_info"
    RESEARCH_SCREEN = "research_screen"
    MARCH_SCREEN = "march_screen"
    INFIRMARY = "infirmary"

    # ── Special ──
    POPUP = "popup"
    CAPTCHA = "captcha"
    LOADING = "loading"
    LOGIN_SCREEN = "login_screen"

    # ── Game-specific ──
    DIVINATION = "divination"
    PROSPERITY_SCREEN = "prosperity_screen"
    WAR_SCREEN = "war_screen"
    NIFLUNG_ENCOUNTER = "niflung_encounter"

    # ── Fallback ──
    UNKNOWN = "unknown"


# ═══════════════════════════════════════════════════════════════════
# Screen → Action Rules: what buttons/actions are expected on each screen
# ═══════════════════════════════════════════════════════════════════

# Expected recovery actions for each screen to get back to CITY
SCREEN_RECOVERY: Dict[str, List[str]] = {
    "world_map":         ["tap_home_btn"],        # tap home/castle button
    "popup":             ["close_popup"],          # close/X button
    "mail_screen":       ["press_back"],           # back button
    "alliance_screen":   ["press_back"],
    "hero_screen":       ["press_back"],
    "event_screen":      ["press_back"],
    "shop":              ["press_back"],
    "inventory":         ["press_back"],
    "profile":           ["press_back"],
    "settings":          ["press_back"],
    "chat":              ["press_back"],
    "training":          ["press_back"],
    "building_info":     ["press_back"],
    "research_screen":   ["press_back"],
    "march_screen":      ["press_back"],
    "infirmary":         ["press_back"],
    "divination":        ["press_back"],
    "prosperity_screen": ["press_back"],
    "war_screen":        ["press_back"],
    "loading":           ["wait"],                 # just wait
    "captcha":           ["wait"],                 # captcha handler deals with this
    "login_screen":      ["wait"],
    "unknown":           ["press_back", "tap_center"],
}


# ═══════════════════════════════════════════════════════════════════
# GameStateMachine — core class
# ═══════════════════════════════════════════════════════════════════

class GameStateMachine:
    """Vision-based game state detection and navigation.

    Wraps the bot's detect_screen() into a formal state machine with:
    - get_state(): determine current GameScreen from vision
    - navigate_to(): smart navigation to target screen
    - verify_state(): confirm we're on expected screen
    - recover_to_city(): robust recovery to city from any screen
    """

    def __init__(self, bot):
        """
        Args:
            bot: VRBot core Bot instance (vrbot_core.py)
        """
        self.bot = bot
        self._current_state: GameScreen = GameScreen.UNKNOWN
        self._state_history: List[Tuple[GameScreen, float]] = []
        self._stuck_threshold = 3  # same screen N times = stuck
        self._max_history = 50

        # Stats
        self.detections = 0
        self.navigation_attempts = 0
        self.recovery_attempts = 0

    # ─── Core: Get Current Game State ───────────────────────

    def get_state(self, force: bool = False) -> GameScreen:
        """Determine current game screen using computer vision.

        Uses bot's 4-layer detection:
          1. Template matching (free, ~5ms)
          2. YOLO ONNX (free, ~50-100ms)
          3. Claude API (paid, ~2s)
          4. OpenAI API (paid, ~2s)

        Args:
            force: bypass 2-second cache

        Returns:
            GameScreen enum value
        """
        self.detections += 1

        result = self.bot.detect_screen(force=force)

        if not result:
            screen = GameScreen.UNKNOWN
        else:
            screen_str = result.get("screen", "unknown").lower()
            try:
                screen = GameScreen(screen_str)
            except ValueError:
                # Map unrecognized screen names
                screen = self._map_screen_name(screen_str)

        # Update state + history
        old_state = self._current_state
        self._current_state = screen
        self._state_history.append((screen, time.time()))
        if len(self._state_history) > self._max_history:
            self._state_history = self._state_history[-self._max_history:]

        if old_state != screen:
            log.info(f"GameState: {old_state.value} → {screen.value}")

        return screen

    def _map_screen_name(self, name: str) -> GameScreen:
        """Map unrecognized screen names to GameScreen enum."""
        ALIASES = {
            "home": GameScreen.CITY,
            "base": GameScreen.CITY,
            "main": GameScreen.CITY,
            "town": GameScreen.CITY,
            "overworld": GameScreen.WORLD_MAP,
            "kingdom": GameScreen.WORLD_MAP,
            "tribe": GameScreen.ALLIANCE_SCREEN,
            "guild": GameScreen.ALLIANCE_SCREEN,
            "quest": GameScreen.EVENT_SCREEN,
            "mission": GameScreen.EVENT_SCREEN,
            "barracks": GameScreen.TRAINING,
            "store": GameScreen.SHOP,
            "mall": GameScreen.SHOP,
            "dialog": GameScreen.POPUP,
            "modal": GameScreen.POPUP,
            "confirm": GameScreen.POPUP,
        }
        for key, val in ALIASES.items():
            if key in name:
                return val
        return GameScreen.UNKNOWN

    # ─── Verify: confirm we're on expected screen ───────────

    def verify_state(self, expected: GameScreen, retries: int = 2) -> bool:
        """Verify current screen matches expected.

        Args:
            expected: Expected GameScreen
            retries: Number of re-checks if first doesn't match

        Returns:
            True if on expected screen
        """
        for i in range(retries + 1):
            state = self.get_state(force=True)
            if state == expected:
                return True
            if i < retries:
                time.sleep(1)
        return False

    # ─── Stuck Detection ────────────────────────────────────

    def is_stuck(self) -> bool:
        """Check if bot is stuck (same screen N+ times in a row)."""
        if len(self._state_history) < self._stuck_threshold:
            return False
        recent = [s for s, _ in self._state_history[-self._stuck_threshold:]]
        return len(set(recent)) == 1 and recent[0] != GameScreen.CITY

    def last_n_states(self, n: int = 5) -> List[GameScreen]:
        """Get last N detected states."""
        return [s for s, _ in self._state_history[-n:]]

    # ─── Navigate To Target ─────────────────────────────────

    def navigate_to(self, target: GameScreen, max_attempts: int = 10) -> bool:
        """Navigate from current screen to target screen.

        Strategy:
          1. Check current state
          2. If already on target → done
          3. If on different screen → use recovery actions to get to city first
          4. From city → navigate to target

        Args:
            target: Desired GameScreen
            max_attempts: Max navigation attempts

        Returns:
            True if successfully navigated to target
        """
        self.navigation_attempts += 1

        for attempt in range(max_attempts):
            current = self.get_state(force=True)

            # Already there!
            if current == target:
                log.info(f"Navigate: already on {target.value}")
                return True

            # Special: navigate to city
            if target == GameScreen.CITY:
                return self.recover_to_city(max_attempts - attempt)

            # Special: navigate to world_map
            if target == GameScreen.WORLD_MAP:
                if current == GameScreen.CITY:
                    self.bot.go_to_world_map()
                    time.sleep(2)
                    if self.verify_state(GameScreen.WORLD_MAP):
                        return True
                else:
                    # Go to city first, then world map
                    if self.recover_to_city(5):
                        self.bot.go_to_world_map()
                        time.sleep(2)
                        if self.verify_state(GameScreen.WORLD_MAP):
                            return True

            # For other screens: must go to city first
            if current != GameScreen.CITY:
                if not self.recover_to_city(5):
                    continue

            # From city, navigation depends on target
            # (Tasks handle their own navigation from city)
            log.info(f"Navigate: at city, target={target.value} (task should handle)")
            return True  # City is the base, tasks navigate from here

        log.warning(f"Navigate: failed to reach {target.value} after {max_attempts} attempts")
        return False

    # ─── Recovery: Get Back to City ─────────────────────────

    def recover_to_city(self, max_attempts: int = 10) -> bool:
        """Robust recovery to city screen from any screen.

        Uses vision-based state detection at each step to decide
        the optimal recovery action (not blind button pressing).

        Returns:
            True if successfully returned to city
        """
        self.recovery_attempts += 1
        log.info("Recovery: attempting to return to city")

        for attempt in range(max_attempts):
            current = self.get_state(force=True)

            if current == GameScreen.CITY:
                log.info(f"Recovery: at city (attempt {attempt + 1})")
                return True

            # Get recovery actions for this screen
            actions = SCREEN_RECOVERY.get(current.value, ["press_back"])

            for action in actions:
                self._execute_action(action)
                time.sleep(1.5)

            # Check if stuck
            if self.is_stuck():
                log.warning(f"Recovery: stuck on {current.value}, trying go_to_city()")
                try:
                    return self.bot.go_to_city(max_attempts=5)
                except Exception as e:
                    log.error(f"Recovery: go_to_city failed: {e}")

        log.error(f"Recovery: FAILED after {max_attempts} attempts")
        return False

    def _execute_action(self, action: str):
        """Execute a recovery action."""
        if action == "close_popup":
            self.bot.close_popup()
        elif action == "press_back":
            self.bot.adb_back()
        elif action == "tap_home_btn":
            self.bot._tap_nav("go", (72, 636),
                              "Find the Home/Castle button (bottom-left)")
        elif action == "tap_center":
            self.bot.tap(640, 360, jitter=False)
        elif action == "wait":
            time.sleep(3)

    # ─── Context: what's available on current screen ────────

    def get_context(self) -> dict:
        """Get rich context about the current game state.

        Returns dict with:
            - screen: GameScreen value
            - buttons: list of detected buttons (from YOLO)
            - is_stuck: bool
            - history: recent state transitions
            - since: seconds since entering this state
        """
        current = self._current_state

        # Get YOLO detections for button context
        buttons = []
        try:
            detections = self.bot.yolo_detect()
            if detections:
                buttons = [d["class"] for d in detections
                           if "btn" in d["class"] or "button" in d["class"]]
        except Exception:
            pass

        # Calculate time on this screen
        since = 0
        for state, ts in reversed(self._state_history):
            if state == current:
                since = time.time() - ts
                break

        return {
            "screen": current.value,
            "buttons": buttons,
            "is_stuck": self.is_stuck(),
            "history": [s.value for s in self.last_n_states(5)],
            "since_seconds": round(since, 1),
            "detections_total": self.detections,
            "recovery_attempts": self.recovery_attempts,
        }

    # ─── Pre-task Check ─────────────────────────────────────

    def ensure_ready_for_task(self, task_name: str) -> bool:
        """Ensure the bot is in the correct state before running a task.

        Most tasks start from city. This method:
          1. Detects current state
          2. If not city → recovers to city
          3. Verifies city screen

        Returns:
            True if ready (at city screen)
        """
        state = self.get_state(force=True)

        if state == GameScreen.CITY:
            return True

        log.info(f"Pre-task [{task_name}]: on {state.value}, recovering to city")
        return self.recover_to_city(max_attempts=8)

    def post_task_check(self, task_name: str) -> GameScreen:
        """Check state after a task completes.

        Returns the current screen. Caller can decide recovery.
        """
        return self.get_state(force=True)

    # ─── Stats ──────────────────────────────────────────────

    def get_stats(self) -> dict:
        return {
            "detections": self.detections,
            "navigation_attempts": self.navigation_attempts,
            "recovery_attempts": self.recovery_attempts,
            "current_state": self._current_state.value,
            "history_size": len(self._state_history),
        }
