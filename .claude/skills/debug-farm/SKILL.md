# Skill: Debug Farm Showing Error Status

## When to Use
When a farm instance reports error status in the orchestrator dashboard, logs show failures, or a task is stuck/crashing.

## Step-by-Step Debugging

### Step 1: Identify the Error
```bash
# Check orchestrator for farm status
curl -s http://cloud.vrbot.me:8889/api/farms | python -m json.tool

# Check specific farm logs
ssh root@88.99.64.19 "docker logs vrbot-farm-<N> --tail 100"
```

### Step 2: Common Fixes

#### Fix: `ValueError: invalid literal for int() — "JobPriority.HIGH"`
**Location**: `core/models.py` around line 138
**Cause**: Enum stored as string instead of int value in Redis/DB
**Fix**: Change `int(priority)` to `int(priority.value)` or handle string enum names:
```python
if isinstance(priority, str) and priority.startswith("JobPriority"):
    priority = getattr(JobPriority, priority.split(".")[-1]).value
```

#### Fix: ADB Device Not Found
```bash
# Restart ADB server inside container
docker exec vrbot-farm-<N> adb kill-server
docker exec vrbot-farm-<N> adb start-server
docker exec vrbot-farm-<N> adb devices

# If still missing, restart the emulator container
docker restart ldplayer-farm-<N>
sleep 10
docker restart vrbot-farm-<N>
```

#### Fix: Game Black Screen
**Cause**: Game crashed or Android activity not in foreground
```bash
# Force-restart the game
docker exec vrbot-farm-<N> adb shell am force-stop com.igg.android.vikingriseglobal
sleep 3
docker exec vrbot-farm-<N> adb shell am start -n com.igg.android.vikingriseglobal/com.gpc.sdk.unity.GPCSDKMainActivity
```
Note: The activity is `com.gpc.sdk.unity.GPCSDKMainActivity` (changed in v1.5.093).

#### Fix: Stale Worker Registration in Redis
**Cause**: Worker crashed but Redis still shows it as active
```bash
# Connect to Redis and clear stale entries
ssh root@88.99.64.19
redis-cli
> KEYS vrbot:worker:*
> DEL vrbot:worker:<stale-id>

# Or flush all worker registrations (they re-register on heartbeat)
> DEL vrbot:workers:active
```

#### Fix: Stuck Tasks (Running Forever)
**Cause**: Task entered infinite loop or ADB connection dropped mid-task
```bash
# Check what task is running
curl -s http://cloud.vrbot.me:8889/api/farms/<N>/status

# Force-cancel via API
curl -X POST http://cloud.vrbot.me:8889/api/farms/<N>/cancel

# If API unresponsive, restart the farm container
docker restart vrbot-farm-<N>
```

### Step 3: Verify Recovery
```bash
# Confirm farm is back online
curl -s http://cloud.vrbot.me:8889/api/farms | grep -A5 "farm-<N>"

# Watch logs for next successful task
ssh root@88.99.64.19 "docker logs vrbot-farm-<N> --tail 20 -f"
```

## Known Pitfalls

- **Never create a `queue/` folder in the project**: This shadows Python's stdlib `queue` module and causes cryptic import errors across the entire bot.
- **Never `sed` across `venv/`**: Running bulk find-and-replace that touches `venv/` corrupts installed packages. Always exclude it: `--exclude-dir=venv`.
- **Port 8889 = v2 orchestrator, NOT 8888**: The current distributed system runs on port 8889. Port 8888 was the legacy single-instance bot. Never deploy to or query port 8888.
- **CORS is handled by nginx only**: Do not add CORS middleware to the Python backend. Nginx on the Hetzner box handles all CORS headers. Adding it in Python causes duplicate headers and breaks preflight.
