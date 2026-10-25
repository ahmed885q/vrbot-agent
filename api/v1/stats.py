"""
Stats API Router — /api/stats/*
================================
Returns farm telemetry: taps, tasks run, resources, time saved.
Used by the Vercel dashboard for the stats widget panel.

Mount in orchestrator:
    from api.v1.stats import router as stats_router
    app.include_router(stats_router)
"""

from fastapi import APIRouter, Query
from typing import Optional, List
from datetime import datetime, timezone

router = APIRouter(tags=["Stats"])

# ── Import stats module ──────────────────────────────────────────────
try:
    from vrbot_stats import (
        get_farm_stats,
        get_global_stats,
        get_weekly_resources,
    )
    _STATS_OK = True
except ImportError:
    _STATS_OK = False

    def get_farm_stats(farm_id, date=None):
        return {"farm_id": farm_id, "date": date or _today(), "taps_today": 0,
                "tasks_today": 0, "time_saved_minutes": 0,
                "resources": {"food": 0, "wood": 0, "stone": 0, "gold": 0}}

    def get_global_stats(date=None):
        return {"date": date or _today(), "total_taps": 0, "total_tasks": 0}

    def get_weekly_resources(farm_id):
        return {}


def _today():
    return datetime.now(timezone.utc).strftime("%Y-%m-%d")


# ══════════════════════════════════════════════════════════════════
#  GET /api/stats/farm/{farm_id}
# ══════════════════════════════════════════════════════════════════

@router.get("/api/stats/farm/{farm_id}")
async def farm_stats(
    farm_id: str,
    date: Optional[str] = Query(default=None, description="YYYY-MM-DD, default=today"),
):
    """
    Stats for a single farm on a given date.
    Returns: taps_today, tasks_today, time_saved_minutes, resources.
    """
    return get_farm_stats(farm_id, date)


# ══════════════════════════════════════════════════════════════════
#  GET /api/stats/global
# ══════════════════════════════════════════════════════════════════

@router.get("/api/stats/global")
async def global_stats(
    date: Optional[str] = Query(default=None, description="YYYY-MM-DD, default=today"),
):
    """
    Aggregate totals across all farms.
    Returns: total_taps, total_tasks for the day.
    """
    return get_global_stats(date)


# ══════════════════════════════════════════════════════════════════
#  GET /api/stats/farms
# ══════════════════════════════════════════════════════════════════

@router.get("/api/stats/farms")
async def all_farms_stats(
    farm_ids: Optional[str] = Query(
        default=None,
        description="Comma-separated farm IDs, e.g. farm_001,farm_002. Default: reads from env/config."
    ),
    date: Optional[str] = Query(default=None, description="YYYY-MM-DD, default=today"),
):
    """
    Stats for all farms in one call. Dashboard uses this for the farm grid.
    """
    import os
    if farm_ids:
        ids = [f.strip() for f in farm_ids.split(",")]
    else:
        # Auto-discover from env: VRBOT_FARM_IDS=farm_001,farm_002,...farm_020
        env_ids = os.environ.get("VRBOT_FARM_IDS", "farm_001")
        ids = [f.strip() for f in env_ids.split(",")]

    results = []
    total_taps = 0
    total_tasks = 0
    total_time = 0.0
    total_food = total_wood = total_stone = total_gold = 0

    for fid in ids:
        s = get_farm_stats(fid, date)
        results.append(s)
        total_taps  += s.get("taps_today", 0)
        total_tasks += s.get("tasks_today", 0)
        total_time  += s.get("time_saved_minutes", 0)
        r = s.get("resources", {})
        total_food  += r.get("food", 0)
        total_wood  += r.get("wood", 0)
        total_stone += r.get("stone", 0)
        total_gold  += r.get("gold", 0)

    return {
        "date": date or _today(),
        "farm_count": len(ids),
        "totals": {
            "taps_today": total_taps,
            "tasks_today": total_tasks,
            "time_saved_minutes": round(total_time, 1),
            "resources": {
                "food": total_food,
                "wood": total_wood,
                "stone": total_stone,
                "gold": total_gold,
            },
        },
        "farms": results,
    }


# ══════════════════════════════════════════════════════════════════
#  GET /api/stats/weekly/{farm_id}
# ══════════════════════════════════════════════════════════════════

@router.get("/api/stats/weekly/{farm_id}")
async def weekly_resources(farm_id: str):
    """
    Last 7 days of resource collection for a farm.
    Returns: {date: {food, wood, stone, gold}} — for the chart widget.
    """
    data = get_weekly_resources(farm_id)
    # Format for frontend chart consumption
    chart = []
    for date_str, resources in sorted(data.items()):
        chart.append({
            "date": date_str,
            "food":  resources.get("food", 0),
            "wood":  resources.get("wood", 0),
            "stone": resources.get("stone", 0),
            "gold":  resources.get("gold", 0),
            "total": sum(resources.values()),
        })
    return {"farm_id": farm_id, "weekly": chart}


# ══════════════════════════════════════════════════════════════════
#  GET /api/stats/summary — Dashboard hero widget
# ══════════════════════════════════════════════════════════════════

@router.get("/api/stats/summary")
async def dashboard_summary():
    """
    Combined summary for the hero stats row on the dashboard.
    Includes: active farms count, daily taps, tasks today, time saved, resources.
    """
    import os
    env_ids = os.environ.get("VRBOT_FARM_IDS", "farm_001")
    farm_count = len([f for f in env_ids.split(",") if f.strip()])

    global_s  = get_global_stats()
    date_str  = _today()

    # Sum resources across all farms
    ids = [f.strip() for f in env_ids.split(",")]
    total_resources = {"food": 0, "wood": 0, "stone": 0, "gold": 0}
    total_time = 0.0
    for fid in ids:
        s = get_farm_stats(fid, date_str)
        r = s.get("resources", {})
        for k in total_resources:
            total_resources[k] += r.get(k, 0)
        total_time += s.get("time_saved_minutes", 0)

    return {
        "date": date_str,
        "active_farms": farm_count,
        "taps_today": global_s.get("total_taps", 0),
        "tasks_today": global_s.get("total_tasks", 0),
        "time_saved_minutes": round(total_time, 1),
        "time_saved_hours": round(total_time / 60, 1),
        "resources_today": total_resources,
    }
