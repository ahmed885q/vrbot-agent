"""
Ultra Agent API routes — plug into the existing FastAPI orchestrator.

Usage in orchestrator/api.py:
    from ultra_agent.api_routes import register_ultra_routes
    register_ultra_routes(app)
"""

import logging
from typing import Optional

log = logging.getLogger("ultra.api")

# Active coordinators per farm
_coordinators: dict = {}


def register_ultra_routes(app):
    """Register Ultra Agent endpoints on the FastAPI app."""
    from fastapi import Request
    from pydantic import BaseModel

    class UltraStartRequest(BaseModel):
        farm_name: str
        max_cycles: int = 0
        cycle_delay: float = 30

    class UltraStopRequest(BaseModel):
        farm_name: str

    @app.post("/api/v1/ultra/start")
    async def ultra_start(req: UltraStartRequest):
        if req.farm_name in _coordinators:
            return {"ok": False, "error": "Already running", "farm": req.farm_name}

        from ultra_agent.coordinator import UltraCoordinator
        coordinator = UltraCoordinator(farm_name=req.farm_name)
        _coordinators[req.farm_name] = coordinator

        log.info("[Ultra] Started for %s", req.farm_name)
        return {
            "ok": True,
            "farm": req.farm_name,
            "message": f"Ultra Agent registered for {req.farm_name}",
        }

    @app.post("/api/v1/ultra/stop")
    async def ultra_stop(req: UltraStopRequest):
        coord = _coordinators.pop(req.farm_name, None)
        if not coord:
            return {"ok": False, "error": "Not running", "farm": req.farm_name}
        log.info("[Ultra] Stopped for %s", req.farm_name)
        return {"ok": True, "farm": req.farm_name, "stats": coord.get_stats()}

    @app.get("/api/v1/ultra/status/{farm_name}")
    async def ultra_status(farm_name: str):
        coord = _coordinators.get(farm_name)
        if not coord:
            return {"running": False, "farm": farm_name}
        return {"running": True, "farm": farm_name, "stats": coord.get_stats()}

    @app.get("/api/v1/ultra/status")
    async def ultra_status_all():
        return {
            "total": len(_coordinators),
            "farms": {name: coord.get_stats() for name, coord in _coordinators.items()},
        }

    log.info("[Ultra] API routes registered: /api/v1/ultra/{start,stop,status}")
