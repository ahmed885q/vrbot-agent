"""
Self-Healing Script: Reassign Stuck Jobs
=========================================
Detects and reassigns jobs stuck in RUNNING state beyond their timeout.
Designed to run as a periodic cron job or be called from the orchestrator.

Usage:
  python scripts/reassign.py              # one-shot check
  python scripts/reassign.py --loop 60    # check every 60 seconds
"""

import asyncio
import logging
import argparse
from datetime import datetime, timedelta
from typing import List, Tuple

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from orchestrator.models import (
    Farm, FarmStatus, TaskType, TaskStatus, TaskRequest, SchedulerConfig
)

logger = logging.getLogger("reassign")

# Timeouts per task type (minutes) — after this, a job is considered stuck
STUCK_THRESHOLDS = {
    TaskType.FARMING: 35,
    TaskType.DAILY: 25,
    TaskType.NIFLING: 50,
}

# Max times a single job can be reassigned before going to DLQ
MAX_REASSIGN_ATTEMPTS = 3


def find_stuck_jobs(
    active_tasks: dict,
    thresholds: dict = None,
) -> List[Tuple[str, TaskRequest]]:
    """
    Scan active tasks and return those that exceeded their timeout.

    Returns:
        List of (farm_id, task_request) tuples for stuck jobs.
    """
    thresholds = thresholds or STUCK_THRESHOLDS
    now = datetime.utcnow()
    stuck = []

    for farm_id, task in active_tasks.items():
        if task.status != TaskStatus.RUNNING:
            continue
        if task.started_at is None:
            continue

        threshold_minutes = thresholds.get(task.task_type, 30)
        elapsed = (now - task.started_at).total_seconds() / 60

        if elapsed > threshold_minutes:
            stuck.append((farm_id, task))
            logger.warning(
                f"Stuck job: farm={farm_id} task={task.task_type.value} "
                f"running {elapsed:.0f}min (threshold={threshold_minutes}min)"
            )

    return stuck


async def reassign_stuck_jobs(scheduler) -> dict:
    """
    Find and reassign stuck jobs in the batch scheduler.

    Steps for each stuck job:
    1. Cancel the running task
    2. Reset farm status to IDLE
    3. If under MAX_REASSIGN_ATTEMPTS, re-queue the task
    4. If over limit, move to DLQ (dead letter queue)

    Args:
        scheduler: BatchScheduler instance

    Returns:
        Summary dict with counts of reassigned, dlq'd, and skipped jobs.
    """
    stuck = find_stuck_jobs(scheduler.active_tasks)

    reassigned = 0
    sent_to_dlq = 0
    skipped = 0

    for farm_id, task in stuck:
        farm = scheduler.farms.get(farm_id)
        if not farm:
            logger.error(f"Farm {farm_id} not found — skipping stuck task")
            skipped += 1
            continue

        # Cancel the stuck task
        task.status = TaskStatus.CANCELLED
        task.completed_at = datetime.utcnow()
        task.error_message = f"auto-reassigned: stuck for >{STUCK_THRESHOLDS.get(task.task_type, 30)}min"

        # Remove from active
        scheduler.active_tasks.pop(farm_id, None)

        # Reset farm
        farm.status = FarmStatus.IDLE
        farm.consecutive_failures += 1

        # Record error for self-learning
        scheduler.error_tracker.record_error(
            f"farm_{farm_id}",
            "stuck_job_reassigned",
            farm_id=farm_id,
        )

        if task.retry_count < MAX_REASSIGN_ATTEMPTS:
            # Re-queue with incremented retry
            new_task = TaskRequest(
                farm_id=farm_id,
                task_type=task.task_type,
                priority=task.priority,
                retry_count=task.retry_count + 1,
                requested_by=task.requested_by,
            )

            if task.task_type == TaskType.NIFLING:
                scheduler.nifling_queue.append(new_task)
            elif task.task_type == TaskType.DAILY:
                scheduler.daily_queue.append(new_task)
            else:
                scheduler.farming_queue.append(new_task)

            reassigned += 1
            logger.info(
                f"Re-queued: farm={farm_id} task={task.task_type.value} "
                f"attempt={new_task.retry_count}/{MAX_REASSIGN_ATTEMPTS}"
            )
        else:
            # Exceeded retry limit — send to DLQ
            from core.queue import dlq_push
            dlq_push(farm_id, task)
            sent_to_dlq += 1
            logger.warning(
                f"DLQ: farm={farm_id} task={task.task_type.value} "
                f"exceeded {MAX_REASSIGN_ATTEMPTS} reassign attempts"
            )

    summary = {
        "checked": len(scheduler.active_tasks) + len(stuck),
        "stuck_found": len(stuck),
        "reassigned": reassigned,
        "sent_to_dlq": sent_to_dlq,
        "skipped": skipped,
        "timestamp": datetime.utcnow().isoformat(),
    }

    if stuck:
        logger.info(f"Reassign summary: {summary}")
    else:
        logger.debug("No stuck jobs found")

    return summary


async def run_loop(scheduler, interval_seconds: int = 60):
    """Run reassignment checks in a loop."""
    logger.info(f"Starting reassign loop (every {interval_seconds}s)")
    while True:
        try:
            await reassign_stuck_jobs(scheduler)
        except Exception as e:
            logger.error(f"Reassign loop error: {e}")
        await asyncio.sleep(interval_seconds)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Reassign stuck VRBOT jobs")
    parser.add_argument("--loop", type=int, default=0,
                        help="Run continuously with N second interval (0=one-shot)")
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
    )

    # Import scheduler — requires orchestrator to be importable
    from orchestrator.api import batch_scheduler

    if args.loop > 0:
        asyncio.run(run_loop(batch_scheduler, args.loop))
    else:
        result = asyncio.run(reassign_stuck_jobs(batch_scheduler))
        print(result)
