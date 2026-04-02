"""
BaseAgent — Common interface for all specialist agents.

Each agent wraps one or more existing VRBOT tasks and adds:
- Pre-condition checking (is the agent relevant right now?)
- Task ordering within the agent's domain
- Post-task verification
- Duration tracking
"""

import logging
import time
from typing import Optional

log = logging.getLogger("ultra.agent")


class BaseAgent:
    """Base class for all Ultra Agent specialists."""

    NAME: str = "base"
    TASKS: list[str] = []  # Task names this agent manages (from tasks/ directory)
    COOLDOWN_SEC: float = 60  # Min seconds between runs

    def __init__(self):
        self.run_count = 0
        self.success_count = 0
        self.last_run = 0.0
        self.last_error: Optional[str] = None

    def can_run(self, context: dict) -> bool:
        """Check if this agent should run given the current context."""
        if time.time() - self.last_run < self.COOLDOWN_SEC:
            return False
        return True

    def get_tasks(self, context: dict) -> list[str]:
        """Return ordered list of tasks to execute. Override for custom logic."""
        return [t for t in self.TASKS]

    def execute(self, bot, run_task_fn, smart_retry=None) -> dict:
        """
        Run this agent's tasks using the existing run_task infrastructure.

        Args:
            bot: The Bot instance (has adb, go_to_city, etc.)
            run_task_fn: The run_task(bot, task_name, smart_retry=sr) function
            smart_retry: SmartRetry instance for failure recovery

        Returns:
            {"ok": bool, "tasks_run": int, "tasks_ok": int, "duration_ms": int}
        """
        self.last_run = time.time()
        self.run_count += 1
        start = time.time()

        tasks = self.get_tasks({})
        run = 0
        ok = 0

        for task_name in tasks:
            log.info("[%s] Running task: %s", self.NAME, task_name)
            try:
                bot.go_to_city()
                time.sleep(1)
                result = run_task_fn(bot, task_name, smart_retry=smart_retry)
                run += 1
                if result:
                    ok += 1
                    log.info("[%s] %s: OK", self.NAME, task_name)
                else:
                    log.warning("[%s] %s: FAILED", self.NAME, task_name)
                    self.last_error = f"{task_name} failed"
            except Exception as e:
                run += 1
                log.error("[%s] %s crashed: %s", self.NAME, task_name, e)
                self.last_error = str(e)
            time.sleep(2)  # Anti-ban delay between tasks

        duration_ms = int((time.time() - start) * 1000)
        success = ok > 0
        if success:
            self.success_count += 1

        return {
            "ok": success,
            "agent": self.NAME,
            "tasks_run": run,
            "tasks_ok": ok,
            "tasks_total": len(tasks),
            "duration_ms": duration_ms,
        }

    def get_stats(self) -> dict:
        return {
            "name": self.NAME,
            "runs": self.run_count,
            "successes": self.success_count,
            "last_error": self.last_error,
        }
