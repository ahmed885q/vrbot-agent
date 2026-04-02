#!/usr/bin/env python3
"""
Deploy all new files to /root/vrbot-distributed and patch orchestrator.
Run: python3 /tmp/deploy_vrbot.py
"""
import ast
import os
import shutil
import subprocess
import sys

BASE = "/root/vrbot-distributed"
RESULTS = []


def ok(msg):
    RESULTS.append(f"  OK  {msg}")


def err(msg):
    RESULTS.append(f"  ERR {msg}")


def validate(path):
    with open(path) as f:
        src = f.read()
    try:
        ast.parse(src)
        return True
    except SyntaxError as e:
        err(f"syntax error in {path}: {e}")
        return False


# ─── 1. scripts/reassign.py ──────────────────────────────────────────────────

REASSIGN = r'''"""
VRBOT Self-Healing: Reassign stuck jobs back to the pending queue.
"""
from __future__ import annotations
import asyncio, logging, time
logger = logging.getLogger(__name__)

async def reassign_stuck_jobs(stale_seconds: int = 1800) -> int:
    from core.redis_client import get_redis, RK
    from core.models import JobStatus
    r = get_redis()
    reassigned = 0
    now = time.time()
    try:
        job_ids = await r.smembers(RK.QUEUE_PROCESSING)
    except Exception as exc:
        logger.error("reassign: failed to read processing set: %s", exc)
        return 0
    for job_id in job_ids:
        if isinstance(job_id, bytes):
            job_id = job_id.decode()
        try:
            raw = await r.hgetall(RK.job(job_id))
            if not raw:
                await r.srem(RK.QUEUE_PROCESSING, job_id)
                logger.info("reassign: removed ghost job %s", job_id)
                continue
            started_at = raw.get("started_at") or raw.get(b"started_at")
            ts = 0.0
            if started_at:
                if isinstance(started_at, bytes):
                    started_at = started_at.decode()
                try:
                    ts = float(started_at)
                except ValueError:
                    try:
                        from datetime import datetime
                        ts = datetime.fromisoformat(started_at).timestamp()
                    except Exception:
                        pass
            running_for = now - ts
            if running_for < stale_seconds:
                continue
            await r.srem(RK.QUEUE_PROCESSING, job_id)
            await r.hset(RK.job(job_id), "status", JobStatus.PENDING.value)
            await r.lpush(RK.QUEUE_PENDING, job_id)
            reassigned += 1
            logger.warning("reassign: re-queued stuck job %s (running %.0fs)", job_id, running_for)
        except Exception as exc:
            logger.error("reassign: error processing job %s: %s", job_id, exc)
    return reassigned

async def run_daemon(interval: int = 60, stale_seconds: int = 1800) -> None:
    logger.info("reassign daemon started (interval=%ds stale=%ds)", interval, stale_seconds)
    while True:
        try:
            n = await reassign_stuck_jobs(stale_seconds=stale_seconds)
            if n:
                logger.info("reassign: %d job(s) re-queued", n)
        except Exception as exc:
            logger.error("reassign daemon error: %s", exc)
        await asyncio.sleep(interval)

if __name__ == "__main__":
    import os
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
    asyncio.run(run_daemon(
        interval=int(os.getenv("CHECK_INTERVAL", "60")),
        stale_seconds=int(os.getenv("STALE_SECONDS", "1800")),
    ))
'''

scripts_dir = os.path.join(BASE, "scripts")
os.makedirs(scripts_dir, exist_ok=True)
reassign_path = os.path.join(scripts_dir, "reassign.py")
with open(reassign_path, "w") as f:
    f.write(REASSIGN)
if validate(reassign_path):
    ok(f"scripts/reassign.py created")
else:
    sys.exit(1)

# ─── 2. api/v1/status.py ─────────────────────────────────────────────────────

STATUS = r'''"""
VRBOT Status API
GET    /api/status              - platform health snapshot
GET    /api/job/{job_id}        - single job details
GET    /api/dlq                 - dead-letter queue listing
DELETE /api/dlq/{job_id}        - remove one DLQ entry
POST   /api/dlq/{job_id}/retry  - move DLQ entry back to pending
"""
from __future__ import annotations
import json, time
from typing import Any, Dict, List, Optional
from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

router = APIRouter(tags=["Status"])

class PlatformStatus(BaseModel):
    status: str
    uptime_seconds: float
    queue: Dict[str, Any]
    workers: Dict[str, Any]
    dlq_size: int
    timestamp: float

class JobDetail(BaseModel):
    job_id: str
    farm_id: Optional[str] = None
    task_type: Optional[str] = None
    status: Optional[str] = None
    priority: Optional[int] = None
    attempts: Optional[int] = None
    created_at: Optional[str] = None
    started_at: Optional[str] = None
    completed_at: Optional[str] = None
    error: Optional[str] = None
    extra: Dict[str, Any] = {}

class DLQEntry(BaseModel):
    job_id: str
    farm_id: Optional[str] = None
    task_type: Optional[str] = None
    error: Optional[str] = None
    attempts: Optional[int] = None
    failed_at: Optional[str] = None

class DLQList(BaseModel):
    total: int
    items: List[DLQEntry]

def _decode(v: Any) -> str:
    return v.decode() if isinstance(v, bytes) else str(v) if v is not None else ""

async def _r():
    from core.redis_client import get_redis
    return get_redis()

async def _rk():
    from core.redis_client import RK
    return RK

@router.get("/api/status", response_model=PlatformStatus)
async def get_status():
    import os
    r = await _r(); RK = await _rk()
    start_env = os.getenv("VRBOT_START_TIME")
    uptime = time.time() - float(start_env) if start_env else 0.0
    try:
        pending = await r.llen(RK.QUEUE_PENDING)
        processing = await r.scard(RK.QUEUE_PROCESSING)
    except Exception:
        pending = processing = 0
    try:
        dlq_size = await r.llen(RK.DLQ)
    except Exception:
        dlq_size = 0
    try:
        workers_online = len(await r.smembers(RK.WORKER_SET))
    except Exception:
        workers_online = 0
    return PlatformStatus(status="ok", uptime_seconds=round(uptime, 1),
        queue={"pending": pending, "processing": processing},
        workers={"online": workers_online}, dlq_size=dlq_size, timestamp=time.time())

@router.get("/api/job/{job_id}", response_model=JobDetail)
async def get_job(job_id: str):
    r = await _r(); RK = await _rk()
    raw = await r.hgetall(RK.job(job_id))
    if not raw:
        raise HTTPException(status_code=404, detail=f"Job {job_id!r} not found")
    decoded: Dict[str, str] = {_decode(k): _decode(v) for k, v in raw.items()}
    known = {"farm_id","task_type","status","priority","attempts","created_at","started_at","completed_at","error"}
    extra = {k: v for k, v in decoded.items() if k not in known}
    return JobDetail(job_id=job_id, farm_id=decoded.get("farm_id"), task_type=decoded.get("task_type"),
        status=decoded.get("status"),
        priority=int(decoded["priority"]) if decoded.get("priority","").isdigit() else None,
        attempts=int(decoded["attempts"]) if decoded.get("attempts","").isdigit() else None,
        created_at=decoded.get("created_at"), started_at=decoded.get("started_at"),
        completed_at=decoded.get("completed_at"), error=decoded.get("error"), extra=extra)

@router.get("/api/dlq", response_model=DLQList)
async def list_dlq(limit: int = Query(50, ge=1, le=500), offset: int = Query(0, ge=0)):
    r = await _r(); RK = await _rk()
    try:
        total = await r.llen(RK.DLQ)
        raws = await r.lrange(RK.DLQ, offset, offset + limit - 1)
    except Exception:
        return DLQList(total=0, items=[])
    items: List[DLQEntry] = []
    for raw in raws:
        try:
            e = json.loads(_decode(raw))
            items.append(DLQEntry(job_id=e.get("job_id") or e.get("id","?"),
                farm_id=e.get("farm_id"), task_type=e.get("task_type"),
                error=e.get("error"), attempts=e.get("attempts"), failed_at=e.get("failed_at")))
        except Exception:
            pass
    return DLQList(total=total, items=items)

@router.delete("/api/dlq/{job_id}")
async def delete_dlq_entry(job_id: str):
    r = await _r(); RK = await _rk()
    entries = await r.lrange(RK.DLQ, 0, -1)
    removed = 0
    for raw in entries:
        try:
            e = json.loads(_decode(raw))
            if e.get("job_id") == job_id or e.get("id") == job_id:
                await r.lrem(RK.DLQ, 1, raw); removed += 1
        except Exception:
            pass
    if not removed:
        raise HTTPException(status_code=404, detail=f"Job {job_id!r} not found in DLQ")
    return {"deleted": removed, "job_id": job_id}

@router.post("/api/dlq/{job_id}/retry")
async def retry_dlq_entry(job_id: str):
    r = await _r(); RK = await _rk()
    entries = await r.lrange(RK.DLQ, 0, -1)
    for raw in entries:
        try:
            e = json.loads(_decode(raw))
            eid = e.get("job_id") or e.get("id")
            if eid == job_id:
                await r.lrem(RK.DLQ, 1, raw)
                e["status"] = "pending"; e.pop("error", None); e.pop("failed_at", None)
                await r.hset(RK.job(job_id), mapping={k: str(v) for k,v in e.items()})
                await r.lpush(RK.QUEUE_PENDING, job_id)
                return {"retried": True, "job_id": job_id}
        except Exception:
            pass
    raise HTTPException(status_code=404, detail=f"Job {job_id!r} not found in DLQ")
'''

api_dir = os.path.join(BASE, "api", "v1")
os.makedirs(api_dir, exist_ok=True)
# ensure __init__.py files
for d in [os.path.join(BASE, "api"), api_dir]:
    init = os.path.join(d, "__init__.py")
    if not os.path.exists(init):
        open(init, "w").close()

status_path = os.path.join(api_dir, "status.py")
with open(status_path, "w") as f:
    f.write(STATUS)
if validate(status_path):
    ok(f"api/v1/status.py created")
else:
    sys.exit(1)

# ─── 3. Append DLQ functions to core/queue.py ────────────────────────────────

DLQ_APPEND = r'''

# ─── DLQ helpers (appended) ──────────────────────────────────────────────────
import json as _dlq_json, time as _dlq_time
from typing import Any as _Any, Dict as _Dict, Optional as _Opt

async def push_to_dlq(r, rk, job_id: str, farm_id: _Opt[str]=None,
        task_type: _Opt[str]=None, error: _Opt[str]=None,
        attempts: int=0, extra: _Opt[_Dict[str, _Any]]=None) -> bool:
    entry = {"job_id": job_id, "farm_id": farm_id, "task_type": task_type,
             "error": error, "attempts": attempts,
             "failed_at": _dlq_time.strftime("%Y-%m-%dT%H:%M:%SZ", _dlq_time.gmtime())}
    if extra:
        entry.update(extra)
    try:
        await r.lpush(rk.DLQ, _dlq_json.dumps(entry))
        await r.ltrim(rk.DLQ, 0, 9999)
        return True
    except Exception:
        return False

async def get_dlq_entries(r, rk, limit: int=50, offset: int=0) -> _Dict[str, _Any]:
    try:
        total = await r.llen(rk.DLQ)
        raws = await r.lrange(rk.DLQ, offset, offset+limit-1)
    except Exception:
        return {"total": 0, "items": []}
    items = []
    for raw in raws:
        try:
            items.append(_dlq_json.loads(raw.decode() if isinstance(raw, bytes) else raw))
        except Exception:
            pass
    return {"total": total, "items": items}

async def remove_from_dlq(r, rk, job_id: str) -> int:
    entries = await r.lrange(rk.DLQ, 0, -1); removed = 0
    for raw in entries:
        try:
            e = _dlq_json.loads(raw.decode() if isinstance(raw, bytes) else raw)
            if e.get("job_id") == job_id or e.get("id") == job_id:
                await r.lrem(rk.DLQ, 1, raw); removed += 1
        except Exception:
            pass
    return removed

async def retry_from_dlq(r, rk, job_id: str) -> bool:
    entries = await r.lrange(rk.DLQ, 0, -1)
    for raw in entries:
        try:
            e = _dlq_json.loads(raw.decode() if isinstance(raw, bytes) else raw)
            eid = e.get("job_id") or e.get("id")
            if eid == job_id:
                await r.lrem(rk.DLQ, 1, raw)
                e["status"] = "pending"; e.pop("error", None); e.pop("failed_at", None)
                await r.hset(rk.job(job_id), mapping={k: str(v) for k, v in e.items()})
                await r.lpush(rk.QUEUE_PENDING, job_id)
                return True
        except Exception:
            pass
    return False

async def purge_dlq(r, rk) -> int:
    try:
        size = await r.llen(rk.DLQ)
        await r.delete(rk.DLQ)
        return size
    except Exception:
        return 0
'''

queue_path = os.path.join(BASE, "core", "queue.py")
if os.path.exists(queue_path):
    with open(queue_path) as f:
        existing = f.read()
    if "push_to_dlq" in existing:
        ok("core/queue.py DLQ functions already present — skipped")
    else:
        shutil.copy(queue_path, queue_path + ".bak_dlq")
        with open(queue_path, "a") as f:
            f.write(DLQ_APPEND)
        if validate(queue_path):
            ok("core/queue.py DLQ functions appended")
        else:
            shutil.copy(queue_path + ".bak_dlq", queue_path)
            err("core/queue.py restored from backup due to syntax error")
            sys.exit(1)
else:
    ok("core/queue.py not found — skipped")

# ─── 4. Register status router in main.py (orchestrator) ─────────────────────

orchestrator_path = os.path.join(BASE, "main.py")
if os.path.exists(orchestrator_path):
    with open(orchestrator_path) as f:
        content = f.read()

    if "status_router" in content or "api.v1.status" in content:
        ok("main.py: status router already registered — skipped")
    else:
        shutil.copy(orchestrator_path, orchestrator_path + ".bak_status")

        import_line = "from api.v1.status import router as status_router"
        include_line = "app.include_router(status_router)"

        lines = content.split("\n")

        # Find insertion point for import (after last from/import line)
        insert_import_at = 0
        for i, line in enumerate(lines):
            stripped = line.strip()
            if stripped.startswith("from ") or stripped.startswith("import "):
                insert_import_at = i + 1

        lines.insert(insert_import_at, import_line)

        # Find include_router calls and add after last one
        if "include_router" in content:
            last_include = 0
            for i, line in enumerate(lines):
                if "include_router" in line:
                    last_include = i
            lines.insert(last_include + 1, include_line)
        else:
            lines.append(include_line)

        content = "\n".join(lines)
        with open(orchestrator_path, "w") as f:
            f.write(content)

        if validate(orchestrator_path):
            ok("main.py: status router registered")
        else:
            shutil.copy(orchestrator_path + ".bak_status", orchestrator_path)
            err("main.py restored from backup due to syntax error")
            sys.exit(1)
else:
    err(f"main.py not found at {orchestrator_path}")

# ─── 5. Final validation of all touched files ─────────────────────────────────

print("\n=== AST VALIDATION ===")
files_to_validate = [
    os.path.join(BASE, "scripts", "reassign.py"),
    os.path.join(BASE, "api", "v1", "status.py"),
    os.path.join(BASE, "main.py"),
]
if os.path.exists(os.path.join(BASE, "core", "queue.py")):
    files_to_validate.append(os.path.join(BASE, "core", "queue.py"))

all_valid = True
for fpath in files_to_validate:
    if not os.path.exists(fpath):
        print(f"  SKIP {fpath} (not found)")
        continue
    try:
        with open(fpath) as f:
            ast.parse(f.read())
        print(f"  OK   {fpath}")
    except SyntaxError as e:
        print(f"  ERR  {fpath}: {e}")
        all_valid = False

print("\n=== RESULTS ===")
for r in RESULTS:
    print(r)

if all_valid:
    print("\nALL_FILES_VALID")
else:
    print("\nSOME_FILES_HAVE_ERRORS")
    sys.exit(1)
