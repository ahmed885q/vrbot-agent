"""
VRBOT Agent — Task Scheduler
Intelligent task scheduling with priority, retry, and dependency support.
"""
import time
import logging
import random
from datetime import datetime
from collections import defaultdict

log = logging.getLogger("vrbot.scheduler")


class Scheduler:
    """Task scheduler with priority queue and smart ordering."""

    def __init__(self, humanizer, rules_engine=None, config=None):
        self.human = humanizer
        self.rules = rules_engine
        self.config = config or {}
        self.retry_max = self.config.get("max_retries", 3)

        # Task tracking
        self._task_history = defaultdict(list)  # task_id -> [timestamps]
        self._retry_counts = defaultdict(int)
        self._completed_tasks = []
        self._failed_tasks = []

    def build_task_queue(self, task_classes, vision, adb, account_id=None):
        """
        Build prioritized task queue for current cycle.
        Returns list of instantiated tasks ready to execute.
        """
        queue = []

        for task_cls in task_classes:
            # Check rules engine
            if self.rules and account_id:
                if not self.rules.should_run_task(account_id, task_cls.task_id):
                    log.debug(f"Skipped by rule: {task_cls.task_name}")
                    continue

            # Check retry limits
            if self._retry_counts[task_cls.task_id] >= self.retry_max:
                log.warning(f"Max retries reached: {task_cls.task_name}")
                continue

            task = task_cls(vision, adb, self.human)
            queue.append(task)

        # Sort by priority
        queue.sort(key=lambda t: t.priority)

        # Apply human-like shuffle (slight randomization)
        queue = self.human.shuffle_tasks(queue)

        log.info(f"Task queue: {len(queue)} tasks for cycle")
        return queue

    def run_cycle(self, task_queue, account_id=None):
        """
        Execute one full cycle of tasks.
        Returns (completed_count, failed_count)
        """
        completed = 0
        failed = 0

        for task in task_queue:
            # Check if we need a rest
            if self.human.should_rest():
                self.human.take_rest()

            # Check if it's sleep time
            if self.human.should_sleep():
                log.info("💤 Sleep time — pausing until morning")
                return completed, failed

            # Check session timeout
            if self.human.session_expired():
                log.info("⏰ Session expired — stopping cycle")
                return completed, failed

            # Get overrides from rules
            overrides = {}
            if self.rules and account_id:
                overrides = self.rules.get_task_overrides(account_id, task.task_id)

            # Execute task
            success = task.execute(overrides)

            if success:
                completed += 1
                self._completed_tasks.append({
                    "task": task.task_id,
                    "time": datetime.now().isoformat(),
                    "duration": task.duration,
                })
                self._retry_counts[task.task_id] = 0
            else:
                failed += 1
                self._retry_counts[task.task_id] += 1
                self._failed_tasks.append({
                    "task": task.task_id,
                    "time": datetime.now().isoformat(),
                    "error": task.error,
                })

            # Random idle action between tasks (human-like)
            if random.random() < 0.15:  # 15% chance
                self.human.random_idle_action(task.adb)

            # Delay between tasks
            self.human.delay("normal")

        return completed, failed

    def reset_retries(self):
        """Reset retry counts for new rotation."""
        self._retry_counts.clear()

    @property
    def stats(self):
        return {
            "total_completed": len(self._completed_tasks),
            "total_failed": len(self._failed_tasks),
            "retry_counts": dict(self._retry_counts),
            "last_10_completed": self._completed_tasks[-10:],
            "last_5_failed": self._failed_tasks[-5:],
        }

