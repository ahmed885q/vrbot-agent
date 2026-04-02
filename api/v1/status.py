"""
Status API Router — /api/status, /api/job/{id}, /api/dlq
=========================================================
Provides operational visibility into the orchestrator, individual jobs,
and the dead letter queue.

Mount this router in orchestrator/api.py:
    from api.v1.status import router as status_router
    app.include_router(status_router)
"""

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel
from datetime import datetime
from typing import Optional

router = APIRouter(tags=["Status & DLQ"])


# ══════════════════════════════════════════
#  Lazy References to Orchestrator State
# ══════════════════════════════════════════
# These are set at router mount time by the orchestrator.
# Avoids circular imports since this module doesn't import orchestrator directly.

_scheduler = None
_config = None
_provisioner = None
_nifling_handler = None


def init_status_router(scheduler, config, provisioner=None, nifling_handler=None):
    """
    Initialize the status router with references to live orchestrator objects.
    Call this from orchestrator/api.py after creating the components.
    """
    global _scheduler, _config, _provisioner, _nifling_handler
    _scheduler = scheduler
    _config = config
    _provisioner = provisioner
    _nifling_handler = nifling_handler


# ══════════════════════════════════════════
#  GET /api/status — System Overview
# ══════════════════════════════════════════

@router.get("/api/status/overview")
async def system_overview():
    """
    Comprehensive system status: farms, active tasks, queues, error rate,
    and self-healing metrics. Used by the dashboard health panel.
    """
    if not _scheduler:
        raise HTTPException(status_code=503, detail="Scheduler not initialized")

    from core.queue import dlq_count

    farms = _scheduler.farms
    active = _scheduler.active_tasks

    # Compute farm status breakdown
    status_counts = {}
    for farm in farms.values():
        s = farm.status.value
        status_counts[s] = status_counts.get(s, 0) + 1

    # Farms needing work
    needs_farming = sum(1 for f in farms.values() if f.needs_farming(_config))
    needs_daily = sum(1 for f in farms.values() if f.needs_daily(_config))

    return {
        "timestamp": datetime.utcnow().isoformat(),
        "farms": {
            "total": len(farms),
            "by_status": status_counts,
            "needs_farming": needs_farming,
            "needs_daily": needs_daily,
        },
        "tasks": {
            "active": len(active),
            "farming_queue": len(_scheduler.farming_queue),
            "daily_queue": len(_scheduler.daily_queue),
            "nifling_queue": len(_scheduler.nifling_queue),
        },
        "batch": {
            "current": _scheduler.current_batch.batch_number if _scheduler.current_batch else None,
            "progress": f"{_scheduler.current_batch.progress_percent:.0f}%" if _scheduler.current_batch else None,
            "total_batches_run": _scheduler.batch_counter,
        },
        "health": {
            "error_rate": f"{_scheduler.error_tracker.recent_error_rate():.1%}",
            "learned_patterns": _scheduler.error_tracker.learned_patterns_count,
            "dlq_size": dlq_count(),
        },
        "config": {
            "max_concurrent": _config.max_concurrent_farms,
            "farming_interval": f"{_config.farming_interval_hours}h",
            "nifling_slots": _config.nifling_reserved_slots,
        },
    }


# ══════════════════════════════════════════
#  GET /api/job/{job_id} — Individual Job
# ══════════════════════════════════════════

@router.get("/api/job/{job_id}")
async def get_job(job_id: str):
    """
    Look up a specific job by its task ID.
    Searches active tasks, then queues, then DLQ.
    """
    if not _scheduler:
        raise HTTPException(status_code=503, detail="Scheduler not initialized")

    # Search active tasks
    for farm_id, task in _scheduler.active_tasks.items():
        if task.id == job_id:
            return _format_task(farm_id, task, source="active")

    # Search queues
    for queue_name, queue_list in [
        ("farming_queue", _scheduler.farming_queue),
        ("daily_queue", _scheduler.daily_queue),
        ("nifling_queue", _scheduler.nifling_queue),
    ]:
        for task in queue_list:
            if task.id == job_id:
                return _format_task(task.farm_id, task, source=queue_name)

    # Search DLQ
    from core.queue import dlq_list
    for entry in dlq_list(limit=0):
        if entry.get("task_id") == job_id:
            return {"source": "dlq", **entry}

    raise HTTPException(status_code=404, detail=f"Job {job_id} not found")


def _format_task(farm_id: str, task, source: str) -> dict:
    """Format a TaskRequest into an API response."""
    return {
        "job_id": task.id,
        "farm_id": farm_id,
        "source": source,
        "task_type": task.task_type.value,
        "priority": task.priority.value if hasattr(task.priority, "value") else task.priority,
        "status": task.status.value,
        "retry_count": task.retry_count,
        "created_at": task.created_at.isoformat() if task.created_at else None,
        "started_at": task.started_at.isoformat() if task.started_at else None,
        "completed_at": task.completed_at.isoformat() if task.completed_at else None,
        "duration_seconds": task.duration.total_seconds() if task.duration else None,
        "error_message": task.error_message,
        "requested_by": task.requested_by,
    }


# ══════════════════════════════════════════
#  /api/dlq — Dead Letter Queue
# ══════════════════════════════════════════

@router.get("/api/dlq")
async def list_dlq(
    limit: int = Query(default=100, ge=1, le=1000),
    offset: int = Query(default=0, ge=0),
):
    """
    List dead letter queue entries (newest first).
    These are jobs that exhausted all retry attempts.
    """
    from core.queue import dlq_list, dlq_count

    entries = dlq_list(limit=limit, offset=offset)
    return {
        "total": dlq_count(),
        "limit": limit,
        "offset": offset,
        "entries": entries,
    }


@router.delete("/api/dlq")
async def flush_dlq():
    """Flush all DLQ entries. Use with caution."""
    from core.queue import dlq_flush
    removed = dlq_flush()
    return {"flushed": removed}


class DLQRetryRequest(BaseModel):
    farm_id: str

@router.post("/api/dlq/retry")
async def retry_dlq_entry(req: DLQRetryRequest):
    """
    Pull a farm's entry from DLQ and re-queue it for execution.
    """
    if not _scheduler:
        raise HTTPException(status_code=503, detail="Scheduler not initialized")

    from core.queue import dlq_retry
    from orchestrator.models import TaskRequest, TaskType, TaskPriority

    entry = dlq_retry(req.farm_id)
    if not entry:
        raise HTTPException(
            status_code=404,
            detail=f"No DLQ entry found for farm {req.farm_id}"
        )

    # Map task_type string back to enum
    task_type_map = {t.value: t for t in TaskType}
    task_type = task_type_map.get(entry.get("task_type"), TaskType.FARMING)

    new_task = TaskRequest(
        farm_id=req.farm_id,
        task_type=task_type,
        priority=TaskPriority.NORMAL,
        retry_count=0,
        requested_by=entry.get("requested_by"),
    )

    # Route to appropriate queue
    if task_type == TaskType.NIFLING:
        _scheduler.nifling_queue.append(new_task)
    elif task_type == TaskType.DAILY:
        _scheduler.daily_queue.append(new_task)
    else:
        _scheduler.farming_queue.append(new_task)

    return {
        "status": "re-queued",
        "farm_id": req.farm_id,
        "task_type": task_type.value,
        "new_task_id": new_task.id,
    }
