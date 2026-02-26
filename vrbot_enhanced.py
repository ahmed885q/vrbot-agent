"""
VRBOT Enhanced Engine - Integration Module
============================================
Connects all 4 improvements into vrbot_core.py:
1. State Machine Architecture
2. Captcha Detection & Handling
3. Auto-Restart & Health Monitor
4. Random Task Scheduling (Anti-Ban)

Drop-in replacement for the main bot loop in vrbot_core.py

Usage:
    from vrbot_enhanced import VRBotEnhanced
    
    bot = VRBotEnhanced(
        adb_controller=adb,
        device_serial="emulator-5554",
        farm_id="farm_001",
        config={...}
    )
    bot.start()
"""

import time
import logging
import threading
from typing import Dict, Optional, Any, Callable

from state_machine import StateMachine, TaskState, BotState, VRBotTask, StateConfig, StateTransition
from captcha_detector import CaptchaDetector, CaptchaEvent, ScreenGuard
from health_monitor import GameHealthMonitor, GameHealth
from task_scheduler import (
    TaskScheduler, ScheduledTask, TaskPriority, 
    TaskScheduleType, HumanBehaviorConfig, create_default_scheduler
)

logger = logging.getLogger("vrbot.enhanced")


class VRBotEnhanced:
    """
    Enhanced VRBOT engine with all 4 improvements integrated.
    
    Architecture:
    ┌─────────────────────────────────────────┐
    │           VRBotEnhanced                 │
    │  ┌──────────────────────────────────┐   │
    │  │      TaskScheduler               │   │
    │  │  (Random order, anti-ban)        │   │
    │  │  ┌────────────────────────────┐  │   │
    │  │  │  VRBotTask (StateMachine)  │  │   │
    │  │  │  States → Transitions      │  │   │
    │  │  └────────────────────────────┘  │   │
    │  └──────────────────────────────────┘   │
    │  ┌──────────────┐ ┌─────────────────┐   │
    │  │ CaptchaDetect│ │ HealthMonitor   │   │
    │  │ (Screen scan)│ │ (Auto-restart)  │   │
    │  └──────────────┘ └─────────────────┘   │
    └─────────────────────────────────────────┘
    """

    def __init__(self, adb_controller=None, vision_engine=None,
                 device_serial: str = None, farm_id: str = "default",
                 config: Dict = None):
        
        self.adb = adb_controller
        self.vision = vision_engine
        self.device_serial = device_serial
        self.farm_id = farm_id
        self.config = config or {}
        
        # Bot state
        self.state = BotState.STOPPED
        self._running = False
        
        # ─── Initialize Components ───
        
        # 1. Captcha Detector
        self.captcha = CaptchaDetector(
            adb_controller=self.adb,
            vision_engine=self.vision,
            config=self.config.get('captcha', {})
        )
        self.captcha.on_captcha = self._on_captcha
        self.captcha.on_resolved = self._on_captcha_resolved
        
        # 2. Health Monitor
        self.health = GameHealthMonitor(
            adb_controller=self.adb,
            device_serial=self.device_serial,
            config=self.config.get('health', {})
        )
        self.health.on_health_change = self._on_health_change
        self.health.on_game_restarted = self._on_game_restarted
        
        # 3. Screen Guard (combines captcha + popup detection)
        self.guard = ScreenGuard(self.captcha)
        
        # 4. Task Scheduler (will be configured via register_tasks)
        self.scheduler: Optional[TaskScheduler] = None
        
        # Callbacks for external integration (GUI, WebSocket)
        self.on_state_change: Optional[Callable] = None
        self.on_task_update: Optional[Callable] = None
        self.on_error: Optional[Callable] = None
        self.on_stats_update: Optional[Callable] = None
        
        logger.info(f"VRBotEnhanced initialized for farm {farm_id}")

    # ─────────────────────────────────────────
    # Setup & Configuration
    # ─────────────────────────────────────────

    def register_tasks(self, tasks: Dict[str, Callable]):
        """
        Register task callables with the scheduler.
        
        Args:
            tasks: Dict mapping task names to their run() methods.
                   e.g., {"GatherResource": gather_task.run, ...}
        """
        self.scheduler = create_default_scheduler(tasks)
        
        # Wire up callbacks
        self.scheduler.on_task_start = self._on_task_start
        self.scheduler.on_task_complete = self._on_task_complete
        self.scheduler.on_cycle_start = self._on_cycle_start
        self.scheduler.on_cycle_complete = self._on_cycle_complete
        self.scheduler.on_break = self._on_break
        
        logger.info(f"Registered {len(tasks)} tasks")

    def configure_behavior(self, **kwargs):
        """
        Configure human behavior simulation.
        
        Args:
            min_task_delay, max_task_delay, long_pause_probability,
            break_after_cycles, randomize_within_priority, etc.
        """
        if self.scheduler:
            for key, value in kwargs.items():
                if hasattr(self.scheduler.behavior, key):
                    setattr(self.scheduler.behavior, key, value)
                    logger.info(f"Behavior config: {key} = {value}")

    def configure_captcha(self, **kwargs):
        """Configure captcha detection (webhook_url, notify_email, etc.)."""
        for key, value in kwargs.items():
            if hasattr(self.captcha, key):
                setattr(self.captcha, key, value)

    # ─────────────────────────────────────────
    # Main Control
    # ─────────────────────────────────────────

    def start(self, max_cycles: int = 0):
        """
        Start the enhanced bot.
        
        Args:
            max_cycles: 0 = infinite, N = run N cycles then stop
        """
        if not self.scheduler:
            raise RuntimeError("No tasks registered! Call register_tasks() first.")
        
        logger.info(f"═══════ VRBOT Enhanced Starting (Farm: {self.farm_id}) ═══════")
        
        self._running = True
        self._set_state(BotState.STARTING)
        
        # Start health monitor in background
        self.health.start()
        
        # Wait for initial health check
        initial_health = self.health.check_health()
        if initial_health == GameHealth.CRASHED:
            logger.info("Game not running, starting it...")
            self.health.recover()
            time.sleep(10)
        
        self._set_state(BotState.RUNNING)
        
        try:
            # Main loop
            self.scheduler.run_continuous(max_cycles=max_cycles)
        except KeyboardInterrupt:
            logger.info("Keyboard interrupt received")
        except Exception as e:
            logger.error(f"Bot crashed: {e}")
            if self.on_error:
                self.on_error(str(e))
        finally:
            self.stop()

    def start_async(self, max_cycles: int = 0):
        """Start the bot in a background thread."""
        thread = threading.Thread(
            target=self.start,
            args=(max_cycles,),
            daemon=True,
            name=f"vrbot-{self.farm_id}"
        )
        thread.start()
        return thread

    def stop(self):
        """Stop the bot gracefully."""
        logger.info(f"═══════ VRBOT Enhanced Stopping (Farm: {self.farm_id}) ═══════")
        self._running = False
        self._set_state(BotState.SHUTTING_DOWN)
        
        if self.scheduler:
            self.scheduler.stop()
        
        self.health.stop()
        self._set_state(BotState.STOPPED)

    def pause(self):
        """Pause the bot."""
        self._set_state(BotState.PAUSED)
        if self.scheduler:
            self.scheduler.pause()
        self.health.pause()

    def resume(self):
        """Resume the bot."""
        self._set_state(BotState.RUNNING)
        if self.scheduler:
            self.scheduler.resume()
        self.health.resume()

    # ─────────────────────────────────────────
    # Event Handlers
    # ─────────────────────────────────────────

    def _on_captcha(self, event: CaptchaEvent):
        """Handle captcha detection."""
        logger.critical(f"🚨 CAPTCHA on farm {self.farm_id}!")
        self._set_state(BotState.CAPTCHA_WAIT)
        
        if self.scheduler:
            self.scheduler.pause()
        
        # Notify external systems
        if self.on_error:
            self.on_error(f"Captcha detected: {event.captcha_type.name}")

    def _on_captcha_resolved(self, event: CaptchaEvent):
        """Handle captcha resolution."""
        logger.info(f"✅ Captcha resolved on farm {self.farm_id}")
        self._set_state(BotState.RUNNING)
        
        if self.scheduler:
            self.scheduler.resume()

    def _on_health_change(self, health: GameHealth, details: str):
        """Handle game health changes."""
        if health in (GameHealth.CRASHED, GameHealth.FROZEN, GameHealth.UNRESPONSIVE):
            self._set_state(BotState.RESTARTING_GAME)
            if self.scheduler:
                self.scheduler.pause()
        
        elif health == GameHealth.HEALTHY and self.state == BotState.RESTARTING_GAME:
            self._set_state(BotState.RUNNING)
            if self.scheduler:
                self.scheduler.resume()

    def _on_game_restarted(self):
        """Called when game has been restarted by health monitor."""
        logger.info(f"Game restarted on farm {self.farm_id}")
        # Wait for game to fully load before resuming
        time.sleep(30)
        self.health.resume()
        self._set_state(BotState.RUNNING)

    def _on_task_start(self, task_name: str):
        """Task started."""
        if self.on_task_update:
            self.on_task_update({
                'event': 'task_start',
                'task': task_name,
                'farm_id': self.farm_id,
                'timestamp': time.time(),
            })

    def _on_task_complete(self, task_name: str, success: bool, duration: float):
        """Task completed."""
        if self.on_task_update:
            self.on_task_update({
                'event': 'task_complete',
                'task': task_name,
                'success': success,
                'duration': duration,
                'farm_id': self.farm_id,
                'timestamp': time.time(),
            })

    def _on_cycle_start(self, cycle: int):
        """Cycle started."""
        logger.info(f"Farm {self.farm_id}: Cycle {cycle} started")

    def _on_cycle_complete(self, cycle: int, summary: Dict):
        """Cycle completed."""
        logger.info(
            f"Farm {self.farm_id}: Cycle {cycle} complete - "
            f"{summary['successful']}/{summary['total_tasks']} tasks"
        )
        if self.on_stats_update:
            self.on_stats_update(self.get_full_stats())

    def _on_break(self, duration: float):
        """Break started."""
        logger.info(f"Farm {self.farm_id}: Taking break for {duration:.0f}s")

    def _set_state(self, new_state: BotState):
        """Update bot state."""
        old = self.state
        self.state = new_state
        if old != new_state:
            logger.info(f"Bot state: {old.name} → {new_state.name}")
            if self.on_state_change:
                self.on_state_change(old.name, new_state.name)

    # ─────────────────────────────────────────
    # Stats & Dashboard
    # ─────────────────────────────────────────

    def get_full_stats(self) -> Dict:
        """Get comprehensive stats for dashboard/WebSocket."""
        return {
            'farm_id': self.farm_id,
            'bot_state': self.state.name,
            'scheduler': self.scheduler.get_stats() if self.scheduler else {},
            'captcha': self.captcha.get_stats(),
            'captcha_risk': self.captcha.get_risk_level(),
            'health': self.health.get_stats(),
            'timestamp': time.time(),
        }

    def resolve_captcha(self, method: str = "manual"):
        """Manually resolve a captcha (called from GUI/dashboard)."""
        self.captcha.resolve(method)


# ─────────────────────────────────────────────
# Example: How to integrate into existing vrbot_core.py
# ─────────────────────────────────────────────

INTEGRATION_GUIDE = """
╔══════════════════════════════════════════════════════════════╗
║  VRBOT Enhanced Integration Guide                           ║
╠══════════════════════════════════════════════════════════════╣
║                                                              ║
║  Step 1: Copy these files to your vrbot-agent/ folder:       ║
║    - state_machine.py                                        ║
║    - captcha_detector.py                                     ║
║    - health_monitor.py                                       ║
║    - task_scheduler.py                                       ║
║    - vrbot_enhanced.py  (this file)                          ║
║                                                              ║
║  Step 2: In vrbot_core.py, replace the main loop:            ║
║                                                              ║
║    from vrbot_enhanced import VRBotEnhanced                  ║
║                                                              ║
║    # Create enhanced bot                                     ║
║    bot = VRBotEnhanced(                                      ║
║        adb_controller=self.adb,                              ║
║        vision_engine=self.vision,                            ║
║        device_serial=self.device_serial,                     ║
║        farm_id=self.farm_id,                                 ║
║        config={                                              ║
║            'captcha': {                                      ║
║                'captcha_webhook_url': 'https://...',         ║
║            },                                                ║
║            'health': {                                       ║
║                'freeze_threshold': 30,                       ║
║                'ldplayer_path': r'C:\LDPlayer\...',          ║
║            },                                                ║
║        }                                                     ║
║    )                                                         ║
║                                                              ║
║    # Register your existing tasks                            ║
║    bot.register_tasks({                                      ║
║        'GatherResource': self.gather_task.run,               ║
║        'HuntMonster': self.hunt_task.run,                    ║
║        'KillMonster': self.kill_monster_task.run,            ║
║        'TrainTroops': self.train_task.run,                   ║
║        'UpgradeBuilding': self.upgrade_task.run,             ║
║        'DailyQuests': self.daily_task.run,                   ║
║        'AllianceHelp': self.alliance_task.run,               ║
║        'CollectRewards': self.collect_task.run,              ║
║        'NiflungBoss': self.niflung_task.run,                 ║
║    })                                                        ║
║                                                              ║
║    # Start the enhanced engine                               ║
║    bot.start()  # Blocking                                   ║
║    # OR                                                      ║
║    bot.start_async()  # Non-blocking                         ║
║                                                              ║
║  Step 3: Connect to WebSocket hub for dashboard:             ║
║    bot.on_stats_update = ws_hub.send_stats                   ║
║    bot.on_task_update = ws_hub.send_task_update              ║
║    bot.on_state_change = ws_hub.send_state_change            ║
║                                                              ║
║  Step 4 (Optional): Create captcha templates:                ║
║    Place screenshots of captcha UI elements in:              ║
║    templates/captcha/                                        ║
║      - verify_popup.png                                      ║
║      - slider_track.png                                      ║
║      - captcha_title.png                                     ║
║                                                              ║
╚══════════════════════════════════════════════════════════════╝
"""

if __name__ == "__main__":
    print(INTEGRATION_GUIDE)
