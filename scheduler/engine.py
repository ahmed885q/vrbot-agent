"""
Task Scheduler — Manages task execution order, timing, and anti-ban breaks
"""

import asyncio
import time
import logging
from typing import List

log = logging.getLogger("vrbot.scheduler")


class Scheduler:
    def __init__(self, humanizer):
        self.humanizer = humanizer
        self.tasks: list = []
        self._last_run: dict = {}  # task_id -> timestamp
        self._enabled: dict = {}  # task_id -> bool
        self._cycle = 0

    def register(self, task):
        """Register a task"""
        self.tasks.append(task)
        self._last_run[task.id] = 0
        self._enabled[task.id] = True
        log.debug(f"Registered: {task.id} (every {task.interval_sec}s)")

    def enable(self, task_id: str):
        self._enabled[task_id] = True

    def disable(self, task_id: str):
        self._enabled[task_id] = False

    def is_due(self, task) -> bool:
        """Check if task should run now"""
        if not self._enabled.get(task.id, True):
            return False
        elapsed = time.time() - self._last_run.get(task.id, 0)
        return elapsed >= task.interval_sec

    async def run(self, shutdown: asyncio.Event):
        """Main scheduler loop"""
        log.info(f"Scheduler started with {len(self.tasks)} tasks")

        while not shutdown.is_set():
            self._cycle += 1

            # Get due tasks and shuffle order (anti-ban)
            due = [t for t in self.tasks if self.is_due(t)]
            if due:
                due = self.humanizer.shuffle_tasks(due)

            for task in due:
                if shutdown.is_set():
                    break

                # Check for rest break
                await self.humanizer.maybe_rest()

                # Run task
                try:
                    log.info(f"▶ Running: {task.name}")
                    start = time.time()

                    if task.ws:
                        await task.ws.report_status("busy", task.name)

                    await task.execute()

                    elapsed = time.time() - start
                    self._last_run[task.id] = time.time()
                    log.info(f"✓ Done: {task.name} ({elapsed:.1f}s)")

                    if task.ws:
                        await task.ws.report_task(task.id, "done", f"{elapsed:.1f}s")

                except Exception as e:
                    log.error(f"✗ Failed: {task.name} — {e}")
                    if task.ws:
                        await task.ws.report_task(task.id, "error", str(e))

                # Delay between tasks
                await self.humanizer.delay()

            # Wait before next cycle check
            try:
                await asyncio.wait_for(shutdown.wait(), timeout=5.0)
            except asyncio.TimeoutError:
                pass

        log.info("Scheduler stopped")
