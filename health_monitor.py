"""
VRBOT Game Health Monitor & Auto-Restart
==========================================
Inspired by autoclient's NoxClientHandler and ROK Bot's auto-restart.
Monitors game health and automatically recovers from crashes/freezes.

Features:
- Detects game crashes, ANR (App Not Responding), freezes
- Auto-restarts game via ADB
- Monitors emulator health (LDPlayer/Redroid)
- Detects stuck states (same screen for too long)
- Auto-recovery from known problematic states
- Health metrics for dashboard

Integration: Runs as a background thread alongside task execution.
"""

import time
import logging
import threading
import subprocess
from enum import Enum, auto
from typing import Optional, Callable, Dict, List, Any
from dataclasses import dataclass, field

logger = logging.getLogger("vrbot.health_monitor")


class GameHealth(Enum):
    """Game health status."""
    HEALTHY = auto()
    SLOW = auto()           # Game responding but slow
    UNRESPONSIVE = auto()   # Game not responding to inputs
    CRASHED = auto()        # Game process died
    FROZEN = auto()         # Screen stuck (same frame)
    DISCONNECTED = auto()   # ADB connection lost
    EMULATOR_DOWN = auto()  # Emulator not running


class RecoveryAction(Enum):
    """Recovery actions in order of severity."""
    PRESS_BACK = auto()        # Close popup/dialog
    TAP_SCREEN = auto()        # Dismiss loading screen
    FORCE_STOP = auto()        # Force stop game app
    RESTART_GAME = auto()      # Restart the game
    CLEAR_CACHE = auto()       # Clear game cache and restart
    RESTART_EMULATOR = auto()  # Restart the emulator
    FULL_RESET = auto()        # Nuclear option: restart everything


@dataclass
class HealthEvent:
    """Record of a health event."""
    timestamp: float
    health: GameHealth
    recovery_action: Optional[RecoveryAction] = None
    details: str = ""
    recovered: bool = False
    recovery_time: float = 0


class GameHealthMonitor:
    """
    Monitors game health and handles auto-recovery.
    
    Usage:
        monitor = GameHealthMonitor(
            adb_controller=adb,
            game_package="com.igg.android.vikingriseglobal",
            device_serial="emulator-5554"
        )
        monitor.on_health_change = my_callback
        monitor.start()
        
        # Later:
        monitor.stop()
    """

    # Viking Rise package name
    DEFAULT_PACKAGE = "com.igg.android.vikingriseglobal"
    
    # LDPlayer related
    LDPLAYER_PACKAGE = "com.ldplayer"
    
    # Timings
    GAME_START_TIMEOUT = 120      # Max seconds to wait for game to load
    FREEZE_THRESHOLD = 30         # Seconds of same screen = frozen
    ANR_THRESHOLD = 10            # Seconds of no response = ANR
    HEALTH_CHECK_INTERVAL = 5    # Seconds between health checks
    MAX_RECOVERY_ATTEMPTS = 5     # Max recovery attempts before giving up

    def __init__(self, adb_controller=None, game_package: str = None, 
                 device_serial: str = None, config: Dict = None):
        self.adb = adb_controller
        self.game_package = game_package or self.DEFAULT_PACKAGE
        self.device_serial = device_serial
        self.config = config or {}
        
        # State
        self.current_health = GameHealth.HEALTHY
        self.last_screenshot_hash: Optional[str] = None
        self.same_screen_since: float = time.time()
        self.recovery_attempts = 0
        self.last_health_check: float = 0
        
        # History
        self.events: List[HealthEvent] = []
        self.total_restarts = 0
        self.uptime_start: float = time.time()
        
        # Thread control
        self._monitor_thread: Optional[threading.Thread] = None
        self._running = False
        self._paused = False
        
        # Callbacks
        self.on_health_change: Optional[Callable[[GameHealth, str], None]] = None
        self.on_recovery_start: Optional[Callable[[RecoveryAction], None]] = None
        self.on_recovery_complete: Optional[Callable[[bool], None]] = None
        self.on_game_restarted: Optional[Callable[[], None]] = None
        
        # Configure
        self.freeze_threshold = self.config.get('freeze_threshold', self.FREEZE_THRESHOLD)
        self.check_interval = self.config.get('health_check_interval', self.HEALTH_CHECK_INTERVAL)
        self.max_recovery = self.config.get('max_recovery_attempts', self.MAX_RECOVERY_ATTEMPTS)
        
        logger.info(f"GameHealthMonitor initialized for {self.game_package}")

    # ─────────────────────────────────────────
    # Core Health Checks
    # ─────────────────────────────────────────

    def check_health(self) -> GameHealth:
        """Perform a comprehensive health check. Returns current health status."""
        try:
            # 1. Check ADB connection
            if not self._check_adb_connection():
                return self._set_health(GameHealth.DISCONNECTED, "ADB connection lost")
            
            # 2. Check if game is running
            if not self._is_game_running():
                return self._set_health(GameHealth.CRASHED, "Game process not found")
            
            # 3. Check for ANR (App Not Responding)
            if self._check_anr():
                return self._set_health(GameHealth.UNRESPONSIVE, "ANR detected")
            
            # 4. Check for frozen screen
            if self._check_frozen():
                return self._set_health(GameHealth.FROZEN, 
                    f"Screen unchanged for {time.time() - self.same_screen_since:.0f}s")
            
            # 5. All good
            if self.current_health != GameHealth.HEALTHY:
                self._set_health(GameHealth.HEALTHY, "recovered")
            
            return GameHealth.HEALTHY
            
        except Exception as e:
            logger.error(f"Health check error: {e}")
            return self._set_health(GameHealth.DISCONNECTED, f"check error: {e}")

    def _check_adb_connection(self) -> bool:
        """Check if ADB connection to device is alive."""
        try:
            if self.adb and hasattr(self.adb, 'is_connected'):
                return self.adb.is_connected()
            
            # Fallback: try adb shell command
            serial_arg = f"-s {self.device_serial}" if self.device_serial else ""
            result = self._run_adb(f"shell echo ok")
            return result.strip() == "ok"
            
        except Exception:
            return False

    def _is_game_running(self) -> bool:
        """Check if the game process is running on device."""
        try:
            result = self._run_adb(f"shell pidof {self.game_package}")
            return bool(result.strip())
        except Exception:
            return False

    def _check_anr(self) -> bool:
        """Check for Android ANR (App Not Responding) state."""
        try:
            result = self._run_adb("shell dumpsys activity | grep 'ANR in'")
            if self.game_package in result:
                return True
            return False
        except Exception:
            return False

    def _check_frozen(self) -> bool:
        """Check if game screen is frozen (same frame for too long)."""
        try:
            screenshot = None
            if self.adb and hasattr(self.adb, 'screenshot'):
                screenshot = self.adb.screenshot()
            
            if screenshot is None:
                return False
            
            # Quick hash of screenshot
            import hashlib
            import numpy as np
            
            if hasattr(screenshot, 'tobytes'):
                # numpy array
                small = screenshot[::10, ::10]  # Downsample for speed
                current_hash = hashlib.md5(small.tobytes()).hexdigest()
            else:
                # PIL Image
                small = screenshot.resize((64, 64))
                current_hash = hashlib.md5(small.tobytes()).hexdigest()
            
            if current_hash == self.last_screenshot_hash:
                # Same screen
                elapsed = time.time() - self.same_screen_since
                if elapsed > self.freeze_threshold:
                    return True
            else:
                # Screen changed
                self.last_screenshot_hash = current_hash
                self.same_screen_since = time.time()
            
            return False
            
        except Exception as e:
            logger.debug(f"Freeze check error: {e}")
            return False

    def _set_health(self, health: GameHealth, details: str) -> GameHealth:
        """Update health status and fire callbacks."""
        if health != self.current_health:
            old_health = self.current_health
            self.current_health = health
            
            event = HealthEvent(
                timestamp=time.time(),
                health=health,
                details=details
            )
            self.events.append(event)
            
            level = logging.WARNING if health != GameHealth.HEALTHY else logging.INFO
            logger.log(level, f"Health: {old_health.name} → {health.name} ({details})")
            
            if self.on_health_change:
                self.on_health_change(health, details)
        
        return health

    # ─────────────────────────────────────────
    # Recovery Actions
    # ─────────────────────────────────────────

    def recover(self) -> bool:
        """
        Attempt to recover from unhealthy state.
        Escalates through recovery actions based on severity.
        Returns True if recovered.
        """
        if self.current_health == GameHealth.HEALTHY:
            return True
        
        if self.recovery_attempts >= self.max_recovery:
            logger.error(f"Max recovery attempts ({self.max_recovery}) reached. Giving up.")
            return False
        
        self.recovery_attempts += 1
        health = self.current_health
        
        logger.info(f"Recovery attempt {self.recovery_attempts}/{self.max_recovery} for {health.name}")
        
        # Choose recovery action based on health status
        if health == GameHealth.FROZEN:
            actions = [
                RecoveryAction.TAP_SCREEN,
                RecoveryAction.PRESS_BACK,
                RecoveryAction.FORCE_STOP,
                RecoveryAction.RESTART_GAME,
            ]
        elif health == GameHealth.UNRESPONSIVE:
            actions = [
                RecoveryAction.PRESS_BACK,
                RecoveryAction.FORCE_STOP,
                RecoveryAction.RESTART_GAME,
            ]
        elif health == GameHealth.CRASHED:
            actions = [
                RecoveryAction.RESTART_GAME,
                RecoveryAction.CLEAR_CACHE,
                RecoveryAction.RESTART_EMULATOR,
            ]
        elif health == GameHealth.DISCONNECTED:
            actions = [
                RecoveryAction.RESTART_EMULATOR,
                RecoveryAction.FULL_RESET,
            ]
        else:
            actions = [RecoveryAction.PRESS_BACK]
        
        # Try actions in order until one works
        action_index = min(self.recovery_attempts - 1, len(actions) - 1)
        action = actions[action_index]
        
        if self.on_recovery_start:
            self.on_recovery_start(action)
        
        success = self._execute_recovery(action)
        
        if self.on_recovery_complete:
            self.on_recovery_complete(success)
        
        if success:
            self.recovery_attempts = 0
            self._set_health(GameHealth.HEALTHY, f"recovered via {action.name}")
            
        return success

    def _execute_recovery(self, action: RecoveryAction) -> bool:
        """Execute a specific recovery action."""
        logger.info(f"Executing recovery: {action.name}")
        
        try:
            if action == RecoveryAction.TAP_SCREEN:
                return self._recovery_tap_screen()
            elif action == RecoveryAction.PRESS_BACK:
                return self._recovery_press_back()
            elif action == RecoveryAction.FORCE_STOP:
                return self._recovery_force_stop()
            elif action == RecoveryAction.RESTART_GAME:
                return self._recovery_restart_game()
            elif action == RecoveryAction.CLEAR_CACHE:
                return self._recovery_clear_cache()
            elif action == RecoveryAction.RESTART_EMULATOR:
                return self._recovery_restart_emulator()
            elif action == RecoveryAction.FULL_RESET:
                return self._recovery_full_reset()
            return False
        except Exception as e:
            logger.error(f"Recovery action {action.name} failed: {e}")
            return False

    def _recovery_tap_screen(self) -> bool:
        """Tap center of screen to dismiss loading/popup."""
        self._run_adb("shell input tap 640 360")  # Center of 1280x720
        time.sleep(2)
        return self._is_game_running()

    def _recovery_press_back(self) -> bool:
        """Press back button."""
        self._run_adb("shell input keyevent 4")  # KEYCODE_BACK
        time.sleep(2)
        self._run_adb("shell input keyevent 4")
        time.sleep(2)
        return self._is_game_running()

    def _recovery_force_stop(self) -> bool:
        """Force stop the game."""
        self._run_adb(f"shell am force-stop {self.game_package}")
        time.sleep(3)
        return self._start_game()

    def _recovery_restart_game(self) -> bool:
        """Restart the game from scratch."""
        logger.info("Restarting game...")
        self.total_restarts += 1
        
        # Force stop
        self._run_adb(f"shell am force-stop {self.game_package}")
        time.sleep(3)
        
        # Start game
        success = self._start_game()
        
        if success and self.on_game_restarted:
            self.on_game_restarted()
        
        return success

    def _recovery_clear_cache(self) -> bool:
        """Clear game cache and restart."""
        logger.info("Clearing game cache...")
        self._run_adb(f"shell am force-stop {self.game_package}")
        time.sleep(2)
        self._run_adb(f"shell pm clear-cache {self.game_package}")
        time.sleep(3)
        return self._start_game()

    def _recovery_restart_emulator(self) -> bool:
        """Restart the emulator (LDPlayer specific for local, Redroid for cloud)."""
        logger.warning("Restarting emulator...")
        
        # For Redroid (cloud)
        if self.config.get('is_cloud', False):
            container_name = self.config.get('container_name', 'redroid')
            try:
                subprocess.run(['docker', 'restart', container_name], 
                             timeout=60, capture_output=True)
                time.sleep(30)  # Wait for emulator to boot
                return self._start_game()
            except Exception as e:
                logger.error(f"Docker restart failed: {e}")
                return False
        
        # For LDPlayer (local)
        ldplayer_path = self.config.get('ldplayer_path', 
            r'C:\LDPlayer\LDPlayer9\ldconsole.exe')
        instance_index = self.config.get('instance_index', 0)
        
        try:
            # Quit instance
            subprocess.run([ldplayer_path, 'quit', '--index', str(instance_index)],
                         timeout=30, capture_output=True)
            time.sleep(10)
            
            # Launch instance
            subprocess.run([ldplayer_path, 'launch', '--index', str(instance_index)],
                         timeout=30, capture_output=True)
            time.sleep(30)  # Wait for emulator to boot
            
            # Start game
            return self._start_game()
            
        except Exception as e:
            logger.error(f"LDPlayer restart failed: {e}")
            return False

    def _recovery_full_reset(self) -> bool:
        """Full reset - restart emulator and reconnect everything."""
        logger.critical("FULL RESET - restarting everything...")
        success = self._recovery_restart_emulator()
        if success:
            time.sleep(10)
            return self._start_game()
        return False

    def _start_game(self) -> bool:
        """Start the game and wait for it to load."""
        logger.info(f"Starting {self.game_package}...")
        
        # Launch game activity
        self._run_adb(
            f"shell am start -n {self.game_package}/"
            f"com.gpc.sdk.unity.GPCSDKMainActivity"
        )
        
        # Wait for game to start
        start_time = time.time()
        while time.time() - start_time < self.GAME_START_TIMEOUT:
            time.sleep(5)
            if self._is_game_running():
                logger.info(f"Game started in {time.time() - start_time:.0f}s")
                # Wait extra time for game to fully load (splash screen, etc.)
                time.sleep(30)
                return True
        
        logger.error(f"Game failed to start within {self.GAME_START_TIMEOUT}s")
        return False

    # ─────────────────────────────────────────
    # Background Monitor Thread
    # ─────────────────────────────────────────

    def start(self):
        """Start background health monitoring."""
        self._running = True
        self.uptime_start = time.time()
        self._monitor_thread = threading.Thread(target=self._monitor_loop, daemon=True)
        self._monitor_thread.start()
        logger.info("Health monitor started")

    def stop(self):
        """Stop background health monitoring."""
        self._running = False
        if self._monitor_thread:
            self._monitor_thread.join(timeout=10)
        logger.info("Health monitor stopped")

    def pause(self):
        """Pause monitoring (e.g., during intentional game restart)."""
        self._paused = True

    def resume(self):
        """Resume monitoring."""
        self._paused = False
        self.same_screen_since = time.time()  # Reset freeze timer

    def _monitor_loop(self):
        """Background monitoring loop."""
        while self._running:
            try:
                if not self._paused:
                    health = self.check_health()
                    
                    if health != GameHealth.HEALTHY:
                        logger.warning(f"Unhealthy state detected: {health.name}")
                        self.recover()
                
                time.sleep(self.check_interval)
                
            except Exception as e:
                logger.error(f"Monitor loop error: {e}")
                time.sleep(10)

    # ─────────────────────────────────────────
    # ADB Helper
    # ─────────────────────────────────────────

    def _run_adb(self, command: str) -> str:
        """Run an ADB command and return output."""
        try:
            serial_arg = f"-s {self.device_serial} " if self.device_serial else ""
            full_cmd = f"adb {serial_arg}{command}"
            result = subprocess.run(
                full_cmd, shell=True, capture_output=True, 
                text=True, timeout=15
            )
            return result.stdout
        except subprocess.TimeoutExpired:
            logger.warning(f"ADB command timed out: {command}")
            return ""
        except Exception as e:
            logger.error(f"ADB command failed: {command} - {e}")
            return ""

    # ─────────────────────────────────────────
    # Stats & Metrics
    # ─────────────────────────────────────────

    def get_stats(self) -> Dict:
        """Get health monitor statistics."""
        uptime = time.time() - self.uptime_start
        
        # Calculate uptime percentage
        unhealthy_time = sum(
            e.recovery_time for e in self.events if e.recovered
        )
        uptime_pct = ((uptime - unhealthy_time) / max(uptime, 1)) * 100
        
        return {
            "current_health": self.current_health.name,
            "uptime_seconds": round(uptime),
            "uptime_percentage": round(uptime_pct, 1),
            "total_restarts": self.total_restarts,
            "recovery_attempts": self.recovery_attempts,
            "total_events": len(self.events),
            "events_last_hour": len([
                e for e in self.events 
                if time.time() - e.timestamp < 3600
            ]),
        }
