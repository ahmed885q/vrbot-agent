"""
VRBOT Stats Tracker v1.0
=========================
Redis-backed counters for farm telemetry.
Tracks: taps, tasks run, resources collected, time saved.

Storage keys (all per farm_id):
  vrbot:stats:{farm_id}:taps:{YYYY-MM-DD}           → INT
  vrbot:stats:{farm_id}:tasks:{YYYY-MM-DD}          → INT
  vrbot:stats:{farm_id}:tasks_by_name:{task_tag}    → INT (lifetime)
  vrbot:stats:{farm_id}:resources:{date}            → HASH {food,wood,stone,gold}
  vrbot:stats:{farm_id}:time_saved:{date}           → FLOAT (seconds)
  vrbot:stats:global:taps:{date}                    → INT (all farms)
  vrbot:stats:global:tasks:{date}                   → INT

TTL: 30 days on daily keys, no TTL on lifetime keys.
"""

import os
import time
import logging
from datetime import datetime, timezone
from typing import Optional, Dict, Any

log = logging.getLogger("vrbot.stats")

# ── Redis connection (lazy) ─────────────────────────────────────────
_redis = None

def _get_redis():
    global _redis
    if _redis is not None:
        return _redis
    try:
        import redis
        url = os.environ.get("REDIS_URL", "redis://localhost:6379/0")
        _redis = redis.from_url(url, decode_responses=True, socket_connect_timeout=3)
        _redis.ping()
        log.info("Stats: Redis connected")
    except Exception as e:
        log.warning(f"Stats: Redis unavailable ({e}) — stats disabled")
        _redis = None
    return _redis

def _today() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d")

_TTL_DAILY = 60 * 60 * 24 * 30   # 30 days


# ══════════════════════════════════════════════════════════════════
#  Core increment functions
# ══════════════════════════════════════════════════════════════════

def record_tap(farm_id: str, count: int = 1):
    """Increment tap counter for this farm and globally."""
    r = _get_redis()
    if not r:
        return
    try:
        date = _today()
        farm_key   = f"vrbot:stats:{farm_id}:taps:{date}"
        global_key = f"vrbot:stats:global:taps:{date}"
        pipe = r.pipeline()
        pipe.incrby(farm_key, count)
        pipe.expire(farm_key, _TTL_DAILY)
        pipe.incrby(global_key, count)
        pipe.expire(global_key, _TTL_DAILY)
        pipe.execute()
    except Exception as e:
        log.debug(f"Stats record_tap error: {e}")


def record_task_run(farm_id: str, task_tag: str, duration_seconds: float = 0):
    """Mark a task as completed — increments daily + lifetime counters."""
    r = _get_redis()
    if not r:
        return
    try:
        date = _today()
        pipe = r.pipeline()

        # Daily task count
        farm_daily = f"vrbot:stats:{farm_id}:tasks:{date}"
        pipe.incr(farm_daily)
        pipe.expire(farm_daily, _TTL_DAILY)

        # Global daily
        global_daily = f"vrbot:stats:global:tasks:{date}"
        pipe.incr(global_daily)
        pipe.expire(global_daily, _TTL_DAILY)

        # Lifetime per task name (no TTL)
        lifetime_key = f"vrbot:stats:{farm_id}:tasks_by_name:{task_tag}"
        pipe.incr(lifetime_key)

        # Time saved (1 task ≈ 3 min human time by default + actual duration)
        human_minutes = 3.0
        saved = human_minutes * 60 + duration_seconds
        time_key = f"vrbot:stats:{farm_id}:time_saved:{date}"
        pipe.incrbyfloat(time_key, saved)
        pipe.expire(time_key, _TTL_DAILY)

        pipe.execute()
        log.debug(f"Stats: task_run [{task_tag}] farm={farm_id} duration={duration_seconds:.1f}s")
    except Exception as e:
        log.debug(f"Stats record_task_run error: {e}")


def record_resources(farm_id: str, food: int = 0, wood: int = 0,
                     stone: int = 0, gold: int = 0):
    """Add gathered resource amounts to today's totals."""
    r = _get_redis()
    if not r or not any([food, wood, stone, gold]):
        return
    try:
        date = _today()
        key = f"vrbot:stats:{farm_id}:resources:{date}"
        pipe = r.pipeline()
        if food:  pipe.hincrbyfloat(key, "food", food)
        if wood:  pipe.hincrbyfloat(key, "wood", wood)
        if stone: pipe.hincrbyfloat(key, "stone", stone)
        if gold:  pipe.hincrbyfloat(key, "gold", gold)
        pipe.expire(key, _TTL_DAILY)
        pipe.execute()
    except Exception as e:
        log.debug(f"Stats record_resources error: {e}")


# ══════════════════════════════════════════════════════════════════
#  Read functions (for API endpoint)
# ══════════════════════════════════════════════════════════════════

def get_farm_stats(farm_id: str, date: Optional[str] = None) -> Dict[str, Any]:
    """Return all stats for a farm on a given date (default: today)."""
    r = _get_redis()
    if not r:
        return _empty_farm_stats(farm_id, date or _today())

    date = date or _today()
    try:
        pipe = r.pipeline()
        pipe.get(f"vrbot:stats:{farm_id}:taps:{date}")
        pipe.get(f"vrbot:stats:{farm_id}:tasks:{date}")
        pipe.get(f"vrbot:stats:{farm_id}:time_saved:{date}")
        pipe.hgetall(f"vrbot:stats:{farm_id}:resources:{date}")
        taps, tasks, time_saved, resources = pipe.execute()

        time_saved_s = float(time_saved or 0)
        return {
            "farm_id": farm_id,
            "date": date,
            "taps_today": int(taps or 0),
            "tasks_today": int(tasks or 0),
            "time_saved_minutes": round(time_saved_s / 60, 1),
            "resources": {
                "food":  int(float(resources.get("food", 0))),
                "wood":  int(float(resources.get("wood", 0))),
                "stone": int(float(resources.get("stone", 0))),
                "gold":  int(float(resources.get("gold", 0))),
            },
        }
    except Exception as e:
        log.debug(f"Stats get_farm_stats error: {e}")
        return _empty_farm_stats(farm_id, date)


def get_global_stats(date: Optional[str] = None) -> Dict[str, Any]:
    """Aggregate stats across all farms for a date."""
    r = _get_redis()
    if not r:
        return {"date": date or _today(), "total_taps": 0, "total_tasks": 0}

    date = date or _today()
    try:
        pipe = r.pipeline()
        pipe.get(f"vrbot:stats:global:taps:{date}")
        pipe.get(f"vrbot:stats:global:tasks:{date}")
        taps, tasks = pipe.execute()
        return {
            "date": date,
            "total_taps": int(taps or 0),
            "total_tasks": int(tasks or 0),
        }
    except Exception as e:
        log.debug(f"Stats get_global_stats error: {e}")
        return {"date": date, "total_taps": 0, "total_tasks": 0}


def get_weekly_resources(farm_id: str) -> Dict[str, Any]:
    """Return resource totals for the last 7 days (for charts)."""
    r = _get_redis()
    from datetime import timedelta
    today = datetime.now(timezone.utc)
    result = {}

    for i in range(7):
        d = (today - timedelta(days=i)).strftime("%Y-%m-%d")
        if r:
            try:
                raw = r.hgetall(f"vrbot:stats:{farm_id}:resources:{d}")
                result[d] = {k: int(float(v)) for k, v in raw.items()} if raw else {}
            except Exception:
                result[d] = {}
        else:
            result[d] = {}

    return result


def _empty_farm_stats(farm_id: str, date: str) -> Dict[str, Any]:
    return {
        "farm_id": farm_id,
        "date": date,
        "taps_today": 0,
        "tasks_today": 0,
        "time_saved_minutes": 0,
        "resources": {"food": 0, "wood": 0, "stone": 0, "gold": 0},
    }


# ══════════════════════════════════════════════════════════════════
#  Decorator — wrap any task's run() method automatically
# ══════════════════════════════════════════════════════════════════

def track_task(farm_id: str):
    """
    Decorator factory for auto-tracking task run + taps.
    Usage in a task:
        @track_task(self.farm_id)
        def run(self): ...

    Or call manually at end of run():
        from vrbot_stats import record_task_run
        record_task_run(self.farm_id, self.tag, duration)
    """
    def decorator(fn):
        def wrapper(*args, **kwargs):
            start = time.time()
            result = fn(*args, **kwargs)
            duration = time.time() - start
            record_task_run(farm_id, "unknown", duration)
            return result
        return wrapper
    return decorator
