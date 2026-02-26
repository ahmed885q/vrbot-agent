"""
VRBOT Task Scheduler with Anti-Ban Randomization
==================================================
Inspired by ROK Bot's random tasks order and OSROKBOT's action sets.
Manages task execution with intelligent randomization and scheduling.

Features:
- Random task execution order (anti-ban)
- Priority-based task scheduling
- Cooldown management per task
- Human-like timing with randomized delays
- Task dependency chains
- Cycle management (gather cycle, daily cycle, etc.)
- Performance metrics per task

Integration: Replaces the sequential task execution in vrbot_core.py
"""

import time
import random
import logging
import json
from enum import Enum, auto
from typing import Optional, Callable, Dict, List, Any, Tuple
from dataclasses import dataclass, field
from pathlib import Path
from collections import defaultdict

logger = logging.getLogger("vrbot.scheduler")


class TaskPriority(Enum):
    """Task priority levels."""
    CRITICAL = 1    # Must run ASAP (e.g., shield renewal)
    HIGH = 2        # Important (e.g., gather, hunt)
    NORMAL = 3      # Regular tasks (e.g., daily quests)
    LOW = 4         # Nice to have (e.g., collect free stuff)
    BACKGROUND = 5  # Run when nothing else to do


class TaskScheduleType(Enum):
    """How often a task should run."""
    ONCE = auto()           # Run once per session
    EVERY_CYCLE = auto()    # Run every gather/hunt cycle
    PERIODIC = auto()       # Run every N minutes
    DAILY = auto()          # Run once per day
    ON_DEMAND = auto()      # Run only when requested


@dataclass
class ScheduledTask:
    """Configuration for a scheduled task."""
    name: str
    task_callable: Callable
    priority: TaskPriority = TaskPriority.NORMAL
    schedule_type: TaskScheduleType = TaskScheduleType.EVERY_CYCLE
    cooldown_seconds: float = 0         # Min time between runs
    period_seconds: float = 0           # For PERIODIC type
    max_duration_seconds: float = 300   # Max time for single execution
    dependencies: List[str] = field(default_factory=list)  # Task names that must run first
    enabled: bool = True
    randomize_order: bool = True        # Can this task be reordered?
    
    # Runtime state (managed by scheduler)
    last_run_time: float = 0
    last_success: bool = True
    run_count: int = 0
    fail_count: int = 0
    total_duration: float = 0
    consecutive_fails: int = 0


@dataclass
class HumanBehaviorConfig:
    """Configuration for human-like behavior simulation."""
    # Delay between tasks (seconds)
    min_task_delay: float = 2.0
    max_task_delay: float = 8.0
    
    # Extra long pause probability
    long_pause_probability: float = 0.05    # 5% chance of long pause
    long_pause_min: float = 15.0
    long_pause_max: float = 45.0
    
    # Break simulation
    break_after_cycles: int = 8             # Take a break every N cycles
    break_duration_min: float = 60.0        # 1 min
    break_duration_max: float = 180.0       # 3 min
    
    # Task order randomization
    randomize_within_priority: bool = True
    swap_adjacent_probability: float = 0.3   # 30% chance to swap adjacent tasks
    
    # Click timing variation
    click_delay_min: float = 0.05
    click_delay_max: float = 0.3
    
    # Session variation
    vary_cycle_duration: bool = True
    cycle_duration_variation: float = 0.15   # ±15% variation


class TaskScheduler:
    """
    Intelligent task scheduler with anti-ban randomization.
    
    Usage:
        scheduler = TaskScheduler()
        scheduler.add_task(ScheduledTask(
            name="GatherResource",
            task_callable=gather_task.run,
            priority=TaskPriority.HIGH,
            schedule_type=TaskScheduleType.EVERY_CYCLE,
            cooldown_seconds=300
        ))
        scheduler.add_task(ScheduledTask(
            name="CollectDailyReward",
            task_callable=daily_task.run,
            priority=TaskPriority.NORMAL,
            schedule_type=TaskScheduleType.DAILY
        ))
        
        # Run the scheduler
        while scheduler.has_pending_tasks():
            task_result = scheduler.execute_next()
    """

    def __init__(self, behavior_config: HumanBehaviorConfig = None):
        self.tasks: Dict[str, ScheduledTask] = {}
        self.behavior = behavior_config or HumanBehaviorConfig()
        
        # Execution state
        self.current_cycle: int = 0
        self.cycle_start_time: float = 0
        self.total_tasks_executed: int = 0
        self.session_start_time: float = time.time()
        
        # Queue management
        self._execution_queue: List[str] = []
        self._completed_this_cycle: set = set()
        
        # History for metrics
        self._execution_history: List[Dict] = []
        
        # Callbacks
        self.on_task_start: Optional[Callable[[str], None]] = None
        self.on_task_complete: Optional[Callable[[str, bool, float], None]] = None
        self.on_cycle_start: Optional[Callable[[int], None]] = None
        self.on_cycle_complete: Optional[Callable[[int, Dict], None]] = None
        self.on_break: Optional[Callable[[float], None]] = None
        
        # Pause control
        self._paused = False
        self._stopped = False
        
        logger.info("TaskScheduler initialized")

    # ─────────────────────────────────────────
    # Task Management
    # ─────────────────────────────────────────

    def add_task(self, task: ScheduledTask):
        """Register a task with the scheduler."""
        self.tasks[task.name] = task
        logger.info(f"Task registered: {task.name} (priority: {task.priority.name})")

    def remove_task(self, name: str):
        """Remove a task from the scheduler."""
        if name in self.tasks:
            del self.tasks[name]

    def enable_task(self, name: str, enabled: bool = True):
        """Enable/disable a specific task."""
        if name in self.tasks:
            self.tasks[name].enabled = enabled

    def get_task(self, name: str) -> Optional[ScheduledTask]:
        return self.tasks.get(name)

    # ─────────────────────────────────────────
    # Scheduling Logic
    # ─────────────────────────────────────────

    def build_execution_queue(self) -> List[str]:
        """
        Build the next execution queue with randomized ordering.
        Tasks are grouped by priority, then randomized within groups.
        """
        now = time.time()
        eligible_tasks: Dict[TaskPriority, List[ScheduledTask]] = defaultdict(list)
        
        for task in self.tasks.values():
            if not task.enabled:
                continue
            
            if task.name in self._completed_this_cycle:
                continue
            
            if not self._is_task_due(task, now):
                continue
            
            if not self._are_dependencies_met(task):
                continue
            
            if task.consecutive_fails >= 3:
                logger.warning(f"Task {task.name} skipped: {task.consecutive_fails} consecutive fails")
                continue
            
            eligible_tasks[task.priority].append(task)
        
        # Build queue: priority order, randomized within each priority
        queue = []
        for priority in sorted(eligible_tasks.keys(), key=lambda p: p.value):
            tasks_in_priority = eligible_tasks[priority]
            
            if self.behavior.randomize_within_priority:
                random.shuffle(tasks_in_priority)
            
            queue.extend(t.name for t in tasks_in_priority)
        
        # Apply random swaps for more natural behavior
        if self.behavior.swap_adjacent_probability > 0 and len(queue) > 1:
            queue = self._apply_random_swaps(queue)
        
        self._execution_queue = queue
        logger.info(f"Execution queue built: {queue}")
        return queue

    def _is_task_due(self, task: ScheduledTask, now: float) -> bool:
        """Check if a task is due to run."""
        # Check cooldown
        if task.cooldown_seconds > 0:
            elapsed = now - task.last_run_time
            if elapsed < task.cooldown_seconds:
                return False
        
        # Check schedule type
        if task.schedule_type == TaskScheduleType.ONCE:
            return task.run_count == 0
        
        elif task.schedule_type == TaskScheduleType.PERIODIC:
            if task.last_run_time == 0:
                return True
            return (now - task.last_run_time) >= task.period_seconds
        
        elif task.schedule_type == TaskScheduleType.DAILY:
            if task.last_run_time == 0:
                return True
            # Check if last run was on a different day
            from datetime import datetime
            last_date = datetime.fromtimestamp(task.last_run_time).date()
            today = datetime.fromtimestamp(now).date()
            return last_date < today
        
        elif task.schedule_type == TaskScheduleType.EVERY_CYCLE:
            return True  # Always eligible in a new cycle
        
        elif task.schedule_type == TaskScheduleType.ON_DEMAND:
            return False  # Only run when explicitly requested
        
        return True

    def _are_dependencies_met(self, task: ScheduledTask) -> bool:
        """Check if all task dependencies have been completed."""
        for dep_name in task.dependencies:
            if dep_name not in self._completed_this_cycle:
                return False
        return True

    def _apply_random_swaps(self, queue: List[str]) -> List[str]:
        """Apply random adjacent swaps for more natural ordering."""
        result = queue.copy()
        for i in range(len(result) - 1):
            if random.random() < self.behavior.swap_adjacent_probability:
                # Only swap if tasks are in the same priority group
                task_a = self.tasks.get(result[i])
                task_b = self.tasks.get(result[i + 1])
                if (task_a and task_b and 
                    task_a.priority == task_b.priority and
                    task_a.randomize_order and task_b.randomize_order):
                    result[i], result[i + 1] = result[i + 1], result[i]
        return result

    # ─────────────────────────────────────────
    # Execution
    # ─────────────────────────────────────────

    def execute_next(self) -> Optional[Dict]:
        """
        Execute the next task in the queue.
        Returns task result dict or None if queue is empty.
        """
        if self._paused or self._stopped:
            return None
        
        # Build queue if empty
        if not self._execution_queue:
            self.build_execution_queue()
        
        if not self._execution_queue:
            return None
        
        # Get next task
        task_name = self._execution_queue.pop(0)
        task = self.tasks.get(task_name)
        
        if not task or not task.enabled:
            return self.execute_next()  # Skip and try next
        
        # Human-like delay before task
        delay = self._get_random_delay()
        if delay > 0:
            logger.debug(f"Human delay: {delay:.1f}s before {task_name}")
            time.sleep(delay)
        
        # Execute task
        logger.info(f"▶ Executing: {task_name} (priority: {task.priority.name})")
        
        if self.on_task_start:
            self.on_task_start(task_name)
        
        start_time = time.time()
        success = False
        result = {}
        
        try:
            result = task.task_callable() or {}
            success = result.get('success', True)
        except Exception as e:
            logger.error(f"Task {task_name} crashed: {e}")
            result = {'success': False, 'error': str(e)}
            success = False
        
        duration = time.time() - start_time
        
        # Update task stats
        task.last_run_time = time.time()
        task.run_count += 1
        task.last_success = success
        task.total_duration += duration
        
        if success:
            task.consecutive_fails = 0
        else:
            task.fail_count += 1
            task.consecutive_fails += 1
        
        self._completed_this_cycle.add(task_name)
        self.total_tasks_executed += 1
        
        # Record history
        history_entry = {
            'task': task_name,
            'success': success,
            'duration': round(duration, 1),
            'timestamp': time.time(),
            'cycle': self.current_cycle,
        }
        self._execution_history.append(history_entry)
        
        logger.info(
            f"{'✅' if success else '❌'} {task_name}: "
            f"{'success' if success else 'failed'} in {duration:.1f}s"
        )
        
        if self.on_task_complete:
            self.on_task_complete(task_name, success, duration)
        
        return history_entry

    def run_cycle(self) -> Dict:
        """
        Run one complete cycle of all eligible tasks.
        Returns cycle summary.
        """
        self.current_cycle += 1
        self.cycle_start_time = time.time()
        self._completed_this_cycle.clear()
        self._execution_queue.clear()
        
        logger.info(f"═══ Cycle {self.current_cycle} started ═══")
        
        if self.on_cycle_start:
            self.on_cycle_start(self.current_cycle)
        
        # Check for break
        if (self.behavior.break_after_cycles > 0 and 
            self.current_cycle > 1 and
            self.current_cycle % self.behavior.break_after_cycles == 0):
            self._take_break()
        
        # Build and execute queue
        self.build_execution_queue()
        
        results = []
        while self._execution_queue and not self._stopped:
            if self._paused:
                time.sleep(1)
                continue
            
            result = self.execute_next()
            if result:
                results.append(result)
        
        # Cycle summary
        cycle_duration = time.time() - self.cycle_start_time
        success_count = sum(1 for r in results if r.get('success'))
        
        summary = {
            'cycle': self.current_cycle,
            'total_tasks': len(results),
            'successful': success_count,
            'failed': len(results) - success_count,
            'duration': round(cycle_duration, 1),
            'tasks': results,
        }
        
        logger.info(
            f"═══ Cycle {self.current_cycle} complete: "
            f"{success_count}/{len(results)} tasks, {cycle_duration:.0f}s ═══"
        )
        
        if self.on_cycle_complete:
            self.on_cycle_complete(self.current_cycle, summary)
        
        return summary

    def run_continuous(self, max_cycles: int = 0):
        """
        Run cycles continuously.
        Args:
            max_cycles: 0 = infinite
        """
        cycle_count = 0
        while not self._stopped:
            if self._paused:
                time.sleep(1)
                continue
            
            self.run_cycle()
            cycle_count += 1
            
            if max_cycles > 0 and cycle_count >= max_cycles:
                logger.info(f"Completed {max_cycles} cycles, stopping")
                break
            
            # Variable delay between cycles
            if self.behavior.vary_cycle_duration:
                variation = 1.0 + random.uniform(
                    -self.behavior.cycle_duration_variation,
                    self.behavior.cycle_duration_variation
                )
                inter_cycle_delay = random.uniform(5, 15) * variation
                logger.info(f"Inter-cycle delay: {inter_cycle_delay:.0f}s")
                time.sleep(inter_cycle_delay)

    def run_task_by_name(self, name: str) -> Optional[Dict]:
        """Execute a specific task by name (on-demand)."""
        task = self.tasks.get(name)
        if not task:
            logger.error(f"Task not found: {name}")
            return None
        
        self._execution_queue = [name]
        return self.execute_next()

    # ─────────────────────────────────────────
    # Human Behavior Simulation
    # ─────────────────────────────────────────

    def _get_random_delay(self) -> float:
        """Get a human-like random delay between tasks."""
        # Check for long pause (simulates human distraction)
        if random.random() < self.behavior.long_pause_probability:
            delay = random.uniform(
                self.behavior.long_pause_min,
                self.behavior.long_pause_max
            )
            logger.info(f"🧑 Simulating human pause: {delay:.0f}s")
            return delay
        
        # Normal inter-task delay
        return random.uniform(
            self.behavior.min_task_delay,
            self.behavior.max_task_delay
        )

    def _take_break(self):
        """Simulate a human taking a break."""
        duration = random.uniform(
            self.behavior.break_duration_min,
            self.behavior.break_duration_max
        )
        logger.info(f"☕ Taking a break: {duration:.0f}s")
        
        if self.on_break:
            self.on_break(duration)
        
        time.sleep(duration)

    @staticmethod
    def human_delay(min_s: float = 0.1, max_s: float = 0.5):
        """Static method for adding human-like delay anywhere in code."""
        time.sleep(random.uniform(min_s, max_s))

    @staticmethod
    def human_click_offset(x: int, y: int, max_offset: int = 5) -> Tuple[int, int]:
        """Add slight random offset to click coordinates."""
        ox = random.randint(-max_offset, max_offset)
        oy = random.randint(-max_offset, max_offset)
        return (x + ox, y + oy)

    # ─────────────────────────────────────────
    # Control
    # ─────────────────────────────────────────

    def pause(self):
        self._paused = True
        logger.info("Scheduler paused")

    def resume(self):
        self._paused = False
        logger.info("Scheduler resumed")

    def stop(self):
        self._stopped = True
        logger.info("Scheduler stopped")

    def has_pending_tasks(self) -> bool:
        """Check if there are tasks pending in current cycle."""
        return bool(self._execution_queue)

    # ─────────────────────────────────────────
    # Metrics & Stats
    # ─────────────────────────────────────────

    def get_stats(self) -> Dict:
        """Get scheduler statistics."""
        session_duration = time.time() - self.session_start_time
        
        task_stats = {}
        for name, task in self.tasks.items():
            avg_duration = (task.total_duration / max(task.run_count, 1))
            success_rate = ((task.run_count - task.fail_count) / max(task.run_count, 1)) * 100
            
            task_stats[name] = {
                'enabled': task.enabled,
                'priority': task.priority.name,
                'run_count': task.run_count,
                'fail_count': task.fail_count,
                'consecutive_fails': task.consecutive_fails,
                'avg_duration': round(avg_duration, 1),
                'success_rate': round(success_rate, 1),
                'last_run': task.last_run_time,
            }
        
        return {
            'current_cycle': self.current_cycle,
            'total_executed': self.total_tasks_executed,
            'session_duration': round(session_duration),
            'queue_remaining': len(self._execution_queue),
            'paused': self._paused,
            'tasks': task_stats,
        }

    def get_execution_history(self, last_n: int = 50) -> List[Dict]:
        """Get recent execution history."""
        return self._execution_history[-last_n:]


# ─────────────────────────────────────────────
# Pre-configured VRBOT Task Sets
# ─────────────────────────────────────────────

def create_default_scheduler(tasks_dict: Dict[str, Callable]) -> TaskScheduler:
    """
    Create a pre-configured scheduler with default VRBOT tasks.
    
    Args:
        tasks_dict: Dict mapping task names to their run() callables.
                    Expected keys: GatherResource, HuntMonster, TrainTroops,
                    UpgradeBuilding, DailyQuests, AllianceHelp, CollectRewards, etc.
    """
    config = HumanBehaviorConfig(
        min_task_delay=2.0,
        max_task_delay=8.0,
        long_pause_probability=0.05,
        break_after_cycles=8,
        break_duration_min=60,
        break_duration_max=180,
        randomize_within_priority=True,
        swap_adjacent_probability=0.3,
    )
    
    scheduler = TaskScheduler(behavior_config=config)
    
    # Define default task configurations
    default_configs = {
        'GatherResource': {
            'priority': TaskPriority.HIGH,
            'schedule': TaskScheduleType.EVERY_CYCLE,
            'cooldown': 0,
        },
        'HuntMonster': {
            'priority': TaskPriority.HIGH,
            'schedule': TaskScheduleType.EVERY_CYCLE,
            'cooldown': 0,
        },
        'KillMonster': {
            'priority': TaskPriority.HIGH,
            'schedule': TaskScheduleType.EVERY_CYCLE,
            'cooldown': 0,
        },
        'TrainTroops': {
            'priority': TaskPriority.NORMAL,
            'schedule': TaskScheduleType.PERIODIC,
            'cooldown': 600,  # 10 min
            'period': 600,
        },
        'UpgradeBuilding': {
            'priority': TaskPriority.NORMAL,
            'schedule': TaskScheduleType.PERIODIC,
            'cooldown': 900,  # 15 min
            'period': 900,
        },
        'DailyQuests': {
            'priority': TaskPriority.NORMAL,
            'schedule': TaskScheduleType.DAILY,
            'cooldown': 3600,
        },
        'AllianceHelp': {
            'priority': TaskPriority.NORMAL,
            'schedule': TaskScheduleType.PERIODIC,
            'cooldown': 300,
            'period': 300,
        },
        'CollectRewards': {
            'priority': TaskPriority.LOW,
            'schedule': TaskScheduleType.PERIODIC,
            'cooldown': 1800,  # 30 min
            'period': 1800,
        },
        'AllianceTech': {
            'priority': TaskPriority.LOW,
            'schedule': TaskScheduleType.PERIODIC,
            'cooldown': 3600,
            'period': 3600,
        },
        'NiflungBoss': {
            'priority': TaskPriority.HIGH,
            'schedule': TaskScheduleType.EVERY_CYCLE,
            'cooldown': 0,
        },
    }
    
    for task_name, callable_fn in tasks_dict.items():
        config_data = default_configs.get(task_name, {
            'priority': TaskPriority.NORMAL,
            'schedule': TaskScheduleType.EVERY_CYCLE,
            'cooldown': 0,
        })
        
        task = ScheduledTask(
            name=task_name,
            task_callable=callable_fn,
            priority=config_data['priority'],
            schedule_type=config_data['schedule'],
            cooldown_seconds=config_data.get('cooldown', 0),
            period_seconds=config_data.get('period', 0),
        )
        scheduler.add_task(task)
    
    return scheduler
