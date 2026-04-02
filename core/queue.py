"""
Core Queue Utilities — DLQ (Dead Letter Queue) Management
==========================================================
Centralized queue helpers used by the orchestrator, reassign script,
and status API. Stores DLQ entries in-memory with optional Redis
persistence when available.
"""

import logging
from datetime import datetime
from typing import Optional, List
from collections import deque

logger = logging.getLogger("core.queue")

# ══════════════════════════════════════════
#  In-Memory DLQ Store
# ══════════════════════════════════════════

# DLQ entries: list of dicts with job metadata
_dlq: deque = deque(maxlen=10000)


def dlq_push(farm_id: str, task, reason: str = "") -> dict:
    """
    Push a failed job to the Dead Letter Queue.

    Args:
        farm_id: The farm that failed
        task: TaskRequest object or dict with task info
        reason: Why the job was moved to DLQ

    Returns:
        The DLQ entry dict
    """
    entry = {
        "farm_id": farm_id,
        "task_type": getattr(task, "task_type", "unknown"),
        "task_id": getattr(task, "id", None),
        "priority": getattr(task, "priority", None),
        "retry_count": getattr(task, "retry_count", 0),
        "error_message": getattr(task, "error_message", None),
        "requested_by": getattr(task, "requested_by", None),
        "reason": reason or "max retries exceeded",
        "created_at": datetime.utcnow().isoformat(),
    }

    # Serialize enums to strings
    for key in ("task_type", "priority"):
        val = entry[key]
        if hasattr(val, "value"):
            entry[key] = val.value

    _dlq.append(entry)
    logger.warning(f"DLQ push: farm={farm_id} task={entry['task_type']} reason={entry['reason']}")

    # Try Redis persistence (best-effort)
    _redis_push(entry)

    return entry


def dlq_list(limit: int = 100, offset: int = 0) -> List[dict]:
    """
    List DLQ entries (newest first).

    Args:
        limit: Max entries to return
        offset: Skip first N entries

    Returns:
        List of DLQ entry dicts
    """
    items = list(reversed(_dlq))
    return items[offset:offset + limit]


def dlq_count() -> int:
    """Return total number of entries in the DLQ."""
    return len(_dlq)


def dlq_flush() -> int:
    """
    Clear all DLQ entries.

    Returns:
        Number of entries removed
    """
    count = len(_dlq)
    _dlq.clear()
    logger.info(f"DLQ flushed: {count} entries removed")

    # Also flush Redis DLQ
    _redis_flush()

    return count


def dlq_retry(farm_id: str) -> Optional[dict]:
    """
    Remove a specific farm's entry from DLQ and return it for retry.

    Args:
        farm_id: Farm to retry

    Returns:
        The DLQ entry if found, None otherwise
    """
    for i, entry in enumerate(_dlq):
        if entry["farm_id"] == farm_id:
            _dlq.remove(entry)
            logger.info(f"DLQ retry: farm={farm_id} removed from DLQ for re-processing")
            return entry
    return None


def dlq_get(farm_id: str) -> Optional[dict]:
    """
    Get a DLQ entry by farm_id without removing it.

    Args:
        farm_id: Farm to look up

    Returns:
        The DLQ entry if found, None otherwise
    """
    for entry in _dlq:
        if entry["farm_id"] == farm_id:
            return entry
    return None


# ══════════════════════════════════════════
#  Redis Persistence (Best-Effort)
# ══════════════════════════════════════════

_redis_client = None


def _get_redis():
    """Lazy-init Redis client. Returns None if unavailable."""
    global _redis_client
    if _redis_client is not None:
        return _redis_client
    try:
        import redis
        _redis_client = redis.Redis(host="localhost", port=6379, decode_responses=True)
        _redis_client.ping()
        return _redis_client
    except Exception:
        _redis_client = False  # Don't retry on every call
        return None


def _redis_push(entry: dict):
    """Best-effort push to Redis DLQ list."""
    r = _get_redis()
    if not r:
        return
    try:
        import json
        r.lpush("vrbot:dlq", json.dumps(entry))
        r.ltrim("vrbot:dlq", 0, 9999)  # Cap at 10k
    except Exception as e:
        logger.debug(f"Redis DLQ push failed (non-critical): {e}")


def _redis_flush():
    """Best-effort flush Redis DLQ."""
    r = _get_redis()
    if not r:
        return
    try:
        r.delete("vrbot:dlq")
    except Exception as e:
        logger.debug(f"Redis DLQ flush failed (non-critical): {e}")
