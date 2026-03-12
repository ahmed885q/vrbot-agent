"""
VRBOT State Machine Engine
==========================
Inspired by OSROKBOT's state machine architecture.
Provides a robust state-based task execution framework
with automatic error recovery and transition management.

Integration: Import and use in vrbot_core.py as the main task runner.
"""

import time
import logging
import traceback
from enum import Enum, auto
from typing import Callable, Dict, Optional, List, Any
from dataclasses import dataclass, field

logger = logging.getLogger("vrbot.state_machine")


# ─────────────────────────────────────────────
# State Definitions
# ─────────────────────────────────────────────

class TaskState(Enum):
    """Universal task states for any VRBOT task."""
    IDLE = auto()
    INITIALIZING = auto()
    NAVIGATING = auto()          # Going to the right screen/location
    DETECTING = auto()           # Using YOLO/Vision to detect game state
    EXECUTING = auto()           # Performing the main action
    WAITING = auto()             # Waiting for game response/animation
    VERIFYING = auto()           # Verifying action succeeded
    RECOVERING = auto()          # Handling unexpected state
    CAPTCHA_DETECTED = auto()    # Captcha/verification popup found
    COMPLETED = auto()
    FAILED = auto()
    PAUSED = auto()


class BotState(Enum):
    """Top-level bot states."""
    STOPPED = auto()
    STARTING = auto()
    RUNNING = auto()
    PAUSED = auto()
    CAPTCHA_WAIT = auto()
    RESTARTING_GAME = auto()
    ERROR_RECOVERY = auto()
    SHUTTING_DOWN = auto()
    FATAL_ERROR = auto()      # Unrecoverable error — needs manual intervention or restart
    DISCONNECTED = auto()     # Lost connection to hub / no heartbeat response


# ─────────────────────────────────────────────
# State Transition
# ─────────────────────────────────────────────

@dataclass
class StateTransition:
    """Defines a transition between states."""
    from_state: TaskState
    to_state: TaskState
    condition: Optional[Callable] = None    # Function that returns bool
    action: Optional[Callable] = None       # Action to perform on transition
    on_failure: Optional[TaskState] = None  # State to go to if action fails


@dataclass
class StateConfig:
    """Configuration for a state."""
    state: TaskState
    enter_action: Optional[Callable] = None     # Called when entering state
    execute_action: Optional[Callable] = None   # Called each tick in state
    exit_action: Optional[Callable] = None      # Called when leaving state
    timeout_seconds: float = 30.0               # Max time in state
    max_retries: int = 3                        # Retries before failure
    on_timeout: Optional[TaskState] = None      # State on timeout


# ─────────────────────────────────────────────
# State Machine Core
# ─────────────────────────────────────────────

class StateMachine:
    """
    Generic state machine for VRBOT tasks.
    
    Usage:
        sm = StateMachine("GatherResource")
        sm.add_state(StateConfig(
            state=TaskState.NAVIGATING,
            execute_action=self._navigate_to_world_map,
            timeout_seconds=15
        ))
        sm.add_transition(StateTransition(
            from_state=TaskState.NAVIGATING,
            to_state=TaskState.DETECTING,
            condition=lambda: self.is_on_world_map()
        ))
        sm.start()
    """

    def __init__(self, name: str, initial_state: TaskState = TaskState.IDLE):
        self.name = name
        self.current_state = initial_state
        self.previous_state: Optional[TaskState] = None
        self.states: Dict[TaskState, StateConfig] = {}
        self.transitions: Dict[TaskState, List[StateTransition]] = {}
        self.context: Dict[str, Any] = {}  # Shared data between states
        
        # Timing
        self.state_enter_time: float = time.time()
        self.state_retry_count: int = 0
        self.total_ticks: int = 0
        
        # Callbacks
        self.on_state_change: Optional[Callable] = None
        self.on_error: Optional[Callable] = None
        self.on_captcha: Optional[Callable] = None
        self.on_complete: Optional[Callable] = None
        
        # Running flag
        self._running = False
        self._paused = False
        
        logger.info(f"[{self.name}] State machine created")

    def add_state(self, config: StateConfig):
        """Register a state configuration."""
        self.states[config.state] = config
        if config.state not in self.transitions:
            self.transitions[config.state] = []

    def add_transition(self, transition: StateTransition):
        """Register a state transition."""
        if transition.from_state not in self.transitions:
            self.transitions[transition.from_state] = []
        self.transitions[transition.from_state].append(transition)

    def set_state(self, new_state: TaskState, reason: str = ""):
        """Force a state change."""
        if new_state == self.current_state:
            return
            
        old_state = self.current_state
        
        # Exit old state
        if old_state in self.states and self.states[old_state].exit_action:
            try:
                self.states[old_state].exit_action()
            except Exception as e:
                logger.warning(f"[{self.name}] Exit action error for {old_state}: {e}")

        self.previous_state = old_state
        self.current_state = new_state
        self.state_enter_time = time.time()
        self.state_retry_count = 0
        
        reason_str = f" ({reason})" if reason else ""
        logger.info(f"[{self.name}] {old_state.name} → {new_state.name}{reason_str}")
        
        # Enter new state
        if new_state in self.states and self.states[new_state].enter_action:
            try:
                self.states[new_state].enter_action()
            except Exception as e:
                logger.error(f"[{self.name}] Enter action error for {new_state}: {e}")
        
        # Notify callback
        if self.on_state_change:
            self.on_state_change(old_state, new_state, reason)

    def tick(self) -> TaskState:
        """
        Execute one tick of the state machine.
        Returns current state after tick.
        Call this in your main loop.
        """
        if not self._running or self._paused:
            return self.current_state
            
        self.total_ticks += 1
        state = self.current_state
        
        # Terminal states
        if state in (TaskState.COMPLETED, TaskState.FAILED):
            return state
        
        # Check timeout
        config = self.states.get(state)
        if config and config.timeout_seconds > 0:
            elapsed = time.time() - self.state_enter_time
            if elapsed > config.timeout_seconds:
                self.state_retry_count += 1
                if self.state_retry_count >= (config.max_retries if config else 3):
                    timeout_target = config.on_timeout or TaskState.FAILED
                    self.set_state(timeout_target, 
                                   f"timeout after {elapsed:.1f}s, {self.state_retry_count} retries")
                    return self.current_state
                else:
                    logger.warning(
                        f"[{self.name}] {state.name} timeout ({elapsed:.1f}s), "
                        f"retry {self.state_retry_count}/{config.max_retries}"
                    )
                    self.state_enter_time = time.time()  # Reset timer for retry
        
        # Execute state action
        if config and config.execute_action:
            try:
                config.execute_action()
            except Exception as e:
                logger.error(f"[{self.name}] Execute error in {state.name}: {e}")
                logger.debug(traceback.format_exc())
                if self.on_error:
                    self.on_error(state, e)
                self.set_state(TaskState.RECOVERING, f"error: {e}")
                return self.current_state
        
        # Check transitions
        if state in self.transitions:
            for transition in self.transitions[state]:
                if transition.condition and transition.condition():
                    # Run transition action if any
                    if transition.action:
                        try:
                            transition.action()
                        except Exception as e:
                            logger.error(f"[{self.name}] Transition action error: {e}")
                            if transition.on_failure:
                                self.set_state(transition.on_failure, f"transition error: {e}")
                            continue
                    
                    self.set_state(transition.to_state, "transition condition met")
                    break
        
        return self.current_state

    def start(self, initial_state: Optional[TaskState] = None):
        """Start the state machine."""
        self._running = True
        self._paused = False
        if initial_state:
            self.set_state(initial_state, "start")
        elif self.current_state == TaskState.IDLE:
            self.set_state(TaskState.INITIALIZING, "start")
        logger.info(f"[{self.name}] Started")

    def pause(self):
        """Pause the state machine."""
        self._paused = True
        self.set_state(TaskState.PAUSED, "user pause")

    def resume(self):
        """Resume from pause."""
        self._paused = False
        if self.previous_state:
            self.set_state(self.previous_state, "resumed")

    def stop(self):
        """Stop the state machine."""
        self._running = False
        logger.info(f"[{self.name}] Stopped")

    def is_running(self) -> bool:
        return self._running and not self._paused

    def is_complete(self) -> bool:
        return self.current_state in (TaskState.COMPLETED, TaskState.FAILED)

    def get_elapsed_in_state(self) -> float:
        return time.time() - self.state_enter_time

    def get_status(self) -> dict:
        """Get current status for UI/logging."""
        return {
            "name": self.name,
            "state": self.current_state.name,
            "previous_state": self.previous_state.name if self.previous_state else None,
            "elapsed_in_state": round(self.get_elapsed_in_state(), 1),
            "retry_count": self.state_retry_count,
            "total_ticks": self.total_ticks,
            "running": self._running,
            "paused": self._paused,
        }


# ─────────────────────────────────────────────
# Task Base Class with State Machine
# ─────────────────────────────────────────────

class VRBotTask:
    """
    Base class for all VRBOT tasks using state machine.
    Subclass this and implement the abstract methods.
    
    Example:
        class GatherResourceTask(VRBotTask):
            def __init__(self, bot):
                super().__init__("GatherResource", bot)
                self._setup_states()
            
            def _setup_states(self):
                self.sm.add_state(StateConfig(
                    state=TaskState.NAVIGATING,
                    execute_action=self._go_to_world_map,
                    timeout_seconds=20
                ))
                # ... add more states and transitions
    """

    def __init__(self, name: str, bot: Any):
        self.name = name
        self.bot = bot  # Reference to main bot (vrbot_core)
        self.sm = StateMachine(name)
        self.result: Dict[str, Any] = {}
        self.start_time: float = 0
        self.end_time: float = 0
        
        # Set up common states
        self._setup_common_states()

    def _setup_common_states(self):
        """Setup states common to all tasks."""
        # Recovery state - tries to get back to city view
        self.sm.add_state(StateConfig(
            state=TaskState.RECOVERING,
            execute_action=self._recover,
            timeout_seconds=30,
            on_timeout=TaskState.FAILED
        ))
        
        # Captcha state
        self.sm.add_state(StateConfig(
            state=TaskState.CAPTCHA_DETECTED,
            execute_action=self._handle_captcha,
            timeout_seconds=120,  # Wait up to 2 min for captcha
            on_timeout=TaskState.FAILED
        ))
        
        # Connect captcha callback
        self.sm.on_captcha = self._on_captcha_detected

    def _recover(self):
        """Default recovery: press back, try to get to city view."""
        logger.warning(f"[{self.name}] Attempting recovery...")
        try:
            # Press ESC/back to close popups
            if hasattr(self.bot, 'adb'):
                self.bot.adb.press_back()
                time.sleep(1)
                
                # Try to detect if we're in a known state
                if hasattr(self.bot, 'detect_game_state'):
                    state = self.bot.detect_game_state()
                    if state == 'city_view':
                        self.sm.set_state(TaskState.INITIALIZING, "recovered to city")
                        return
                    elif state == 'world_map':
                        self.sm.set_state(TaskState.INITIALIZING, "recovered to world map")
                        return
                
                # Press back again
                self.bot.adb.press_back()
                time.sleep(1)
                
        except Exception as e:
            logger.error(f"[{self.name}] Recovery failed: {e}")

    def _handle_captcha(self):
        """Default captcha handler - pause and notify."""
        logger.critical(f"[{self.name}] CAPTCHA DETECTED! Pausing bot...")
        if hasattr(self.bot, 'on_captcha_detected'):
            self.bot.on_captcha_detected()
        # Stay in this state until manual resolution or timeout

    def _on_captcha_detected(self):
        """Called when captcha is detected during any state."""
        self.sm.set_state(TaskState.CAPTCHA_DETECTED, "captcha popup")

    def run(self) -> Dict[str, Any]:
        """Execute the task using state machine. Returns result dict."""
        self.start_time = time.time()
        self.sm.start(TaskState.INITIALIZING)
        
        while not self.sm.is_complete():
            self.sm.tick()
            time.sleep(0.1)  # Prevent CPU spinning
            
            # Check for captcha on every tick
            if self._check_captcha():
                self.sm.set_state(TaskState.CAPTCHA_DETECTED, "captcha check")
        
        self.end_time = time.time()
        self.result['duration'] = round(self.end_time - self.start_time, 1)
        self.result['success'] = self.sm.current_state == TaskState.COMPLETED
        self.result['final_state'] = self.sm.current_state.name
        
        return self.result

    def _check_captcha(self) -> bool:
        """
        Override this to implement captcha detection.
        Called every tick. Return True if captcha detected.
        """
        return False

    def get_status(self) -> dict:
        """Get task status for UI."""
        status = self.sm.get_status()
        status['result'] = self.result
        return status
