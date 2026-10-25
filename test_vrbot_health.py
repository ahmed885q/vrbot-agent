#!/usr/bin/env python3
"""
VRBOT Health Check Script
==========================
يجرب كل الـ endpoints ويطلع ريبورت كامل

Usage:
    python3 test_vrbot_health.py
    python3 test_vrbot_health.py --host cloud.vrbot.me --port 8889
"""

import sys
import json
import time
import argparse
import urllib.request
import urllib.error
from datetime import datetime

# ── Config ──────────────────────────────────────────────
DEFAULT_HOST = "cloud.vrbot.me"
DEFAULT_PORT = 8889
TIMEOUT = 10

# ANSI colors
GREEN  = "\033[92m"
RED    = "\033[91m"
YELLOW = "\033[93m"
CYAN   = "\033[96m"
BOLD   = "\033[1m"
RESET  = "\033[0m"

def ok(msg):   print(f"  {GREEN}✅ {msg}{RESET}")
def fail(msg): print(f"  {RED}❌ {msg}{RESET}")
def warn(msg): print(f"  {YELLOW}⚠  {msg}{RESET}")
def info(msg): print(f"  {CYAN}ℹ  {msg}{RESET}")

# ── HTTP helper ──────────────────────────────────────────
def get(base, path, timeout=TIMEOUT):
    url = f"http://{base}{path}"
    try:
        req = urllib.request.Request(url, headers={"Accept": "application/json"})
        with urllib.request.urlopen(req, timeout=timeout) as r:
            body = r.read().decode()
            return r.status, json.loads(body) if body else {}
    except urllib.error.HTTPError as e:
        return e.code, {}
    except urllib.error.URLError as e:
        return None, str(e.reason)
    except Exception as e:
        return None, str(e)

# ── Test sections ────────────────────────────────────────
results = {"passed": 0, "failed": 0, "warned": 0}

def check(label, passed, detail="", warning=False):
    if passed:
        ok(f"{label}" + (f" — {detail}" if detail else ""))
        results["passed"] += 1
    elif warning:
        warn(f"{label}" + (f" — {detail}" if detail else ""))
        results["warned"] += 1
    else:
        fail(f"{label}" + (f" — {detail}" if detail else ""))
        results["failed"] += 1

def section(title):
    print(f"\n{BOLD}{CYAN}{'═'*50}{RESET}")
    print(f"{BOLD}{CYAN}  {title}{RESET}")
    print(f"{BOLD}{CYAN}{'═'*50}{RESET}")

# ════════════════════════════════════════════════════════
def run_tests(base):
    start = time.time()

    # ── 1. Health check ──────────────────────────────────
    section("1. Orchestrator Health")
    status, data = get(base, "/api/health")
    check("HTTP 200 /api/health", status == 200, f"got {status}")
    if isinstance(data, dict):
        check("status=ok", data.get("status") == "ok", str(data.get("status")))

    # ── 2. System status ─────────────────────────────────
    section("2. System Status")
    status, data = get(base, "/api/status")
    check("HTTP 200 /api/status", status == 200, f"got {status}")
    if isinstance(data, dict):
        farms = data.get("farms", {})
        active = len([f for f in farms.values() if isinstance(f, dict) and f.get("status") == "active"])
        total  = len(farms)
        check(f"Farms detected", total > 0, f"{total} farms found")
        check(f"Active farms", active > 0, f"{active}/{total} active", warning=(active == 0))

    # ── 3. Stats endpoints ───────────────────────────────
    section("3. Stats API")

    # Summary
    status, data = get(base, "/api/stats/summary")
    check("HTTP 200 /api/stats/summary", status == 200, f"got {status}")
    if isinstance(data, dict):
        check("active_farms field", "active_farms" in data, str(data.get("active_farms")))
        check("taps_today field",   "taps_today"   in data, str(data.get("taps_today")))
        check("tasks_today field",  "tasks_today"  in data, str(data.get("tasks_today")))
        info(f"Stats → taps={data.get('taps_today',0)} tasks={data.get('tasks_today',0)} "
             f"time_saved={data.get('time_saved_minutes',0):.1f}min")

    # Global stats
    status, data = get(base, "/api/stats/global")
    check("HTTP 200 /api/stats/global", status == 200, f"got {status}")

    # All farms stats
    status, data = get(base, "/api/stats/farms")
    check("HTTP 200 /api/stats/farms", status == 200, f"got {status}")
    if isinstance(data, list):
        check("Returns farm list", len(data) >= 0, f"{len(data)} farm records")

    # ── 4. Farm health checks ────────────────────────────
    section("4. Farm Health (first 3 farms)")
    status, sys_data = get(base, "/api/status")
    farms = sys_data.get("farms", {}) if isinstance(sys_data, dict) else {}
    farm_ids = list(farms.keys())[:3]

    if not farm_ids:
        warn("No farms found — skipping farm-level checks")
        results["warned"] += 1
    else:
        for fid in farm_ids:
            status, data = get(base, f"/api/farms/{fid}/health")
            check(f"Farm {fid} health", status == 200, f"HTTP {status}")
            if isinstance(data, dict):
                farm_status = data.get("status", "unknown")
                check(f"Farm {fid} not error", farm_status != "error",
                      f"status={farm_status}", warning=(farm_status not in ("ok","active","running")))

    # ── 5. Batch/Scheduler status ────────────────────────
    section("5. Batch Scheduler")
    status, data = get(base, "/api/batch/status")
    check("HTTP 200 /api/batch/status", status == 200, f"got {status}")
    if isinstance(data, dict):
        info(f"Scheduler: {json.dumps(data, ensure_ascii=False)[:120]}")

    # ── 6. Scaler status ─────────────────────────────────
    section("6. Auto Scaler")
    status, data = get(base, "/api/scaler/status")
    check("HTTP 200 /api/scaler/status", status == 200, f"got {status}")

    # ── 7. Task stats per farm ───────────────────────────
    section("7. Per-Farm Stats (first farm)")
    if farm_ids:
        fid = farm_ids[0]
        status, data = get(base, f"/api/stats/farm/{fid}")
        check(f"HTTP 200 /api/stats/farm/{fid}", status == 200, f"got {status}")
        if isinstance(data, dict):
            info(f"Farm {fid} stats: {json.dumps(data, ensure_ascii=False)[:200]}")

        # Weekly resources
        status, data = get(base, f"/api/stats/weekly/{fid}")
        check(f"Weekly resources {fid}", status == 200, f"got {status}")

    # ── 8. Capacity validation ───────────────────────────
    section("8. Capacity Validation")
    status, data = get(base, "/api/validate/capacity/5")
    check("HTTP 200 /api/validate/capacity/5", status in (200, 400), f"got {status}")

    # ── Results ──────────────────────────────────────────
    elapsed = time.time() - start
    section("RESULTS")
    total = results["passed"] + results["failed"] + results["warned"]
    print(f"\n  {BOLD}Passed:  {GREEN}{results['passed']}/{total}{RESET}")
    print(f"  {BOLD}Failed:  {RED}{results['failed']}/{total}{RESET}")
    print(f"  {BOLD}Warned:  {YELLOW}{results['warned']}/{total}{RESET}")
    print(f"  Time:    {elapsed:.2f}s")
    print(f"  Run at:  {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")

    if results["failed"] == 0:
        print(f"  {BOLD}{GREEN}🔥 ALL CHECKS PASSED — Bot is healthy!{RESET}\n")
        return 0
    else:
        print(f"  {BOLD}{RED}⚠  {results['failed']} check(s) failed — see above{RESET}\n")
        return 1


# ── Entry point ──────────────────────────────────────────
if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="VRBOT Health Check")
    parser.add_argument("--host", default=DEFAULT_HOST)
    parser.add_argument("--port", default=DEFAULT_PORT, type=int)
    args = parser.parse_args()

    base = f"{args.host}:{args.port}"
    print(f"\n{BOLD}VRBOT Health Check{RESET}")
    print(f"Target: {CYAN}http://{base}{RESET}")
    print(f"Time:   {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

    sys.exit(run_tests(base))
