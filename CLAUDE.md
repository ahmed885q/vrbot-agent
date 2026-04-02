# CLAUDE.md — VRBOT Agent

## Overview
VRBOT is a distributed game automation bot for Viking Rise, running across 20 farm instances on Hetzner cloud with a Vercel frontend dashboard.

## Rules

- **Never create a `queue/` folder** — It shadows Python's stdlib `queue` module, causing `ImportError` across the entire project.
- **Never `sed` across `venv/`** — Bulk find-and-replace that touches virtual environment files corrupts installed packages silently.
- **Port 8889 = v2 orchestrator** — Port 8888 was legacy. All API calls, health checks, and farm communication use 8889.
- **CORS is nginx-only** — Adding CORS middleware in Python causes duplicate headers and breaks browser preflight requests.
- **`com.gpc.sdk.unity.GPCSDKMainActivity` not `MainActivity`** — Viking Rise v1.5.093+ changed the activity class from `com.aspect.GPCSDKMainActivity` to `com.gpc.sdk.unity.GPCSDKMainActivity`. Using the wrong one causes black screen on launch.
- **`go_to_city()` zooms camera out** — Always re-zoom after calling this if the task needs a specific zoom level.
- **Hardcoded coord fallback required** — Every `_tap_ui()` must have a fallback `(x, y)` for when YOLO/template detection fails.
- **Gather march button at (951, 462)** — Proven reliable coordinate; use as calibration reference.
- **`int("JobPriority.HIGH")` ValueError** — Enum names get serialized as strings; always use `.value` before `int()` conversion.
- **Never push directly to main** — Vercel auto-deploys from main. Broken pushes immediately break the production dashboard.
- **Test on LDPlayer before Hetzner** — Screen DPI differences between local and cloud can break coordinate-based tasks.
- **No hardcoded `192.168.x.x` IPs** — Local network IPs don't resolve on Hetzner. Use `cloud.vrbot.me` or env vars.
- **Anti-ban delays mandatory** — Never fire taps in rapid succession. Always `time.sleep(random.uniform(1.5, 4.0))` between taps.
- **Use `logging`, not `print()`** — All tasks must use structured logging via `logging.getLogger("vrbot.task")`.
- **Vercel cron path is `/api/cron/run-tasks`** — Fires 4x daily. Don't rename or relocate without updating Vercel cron config.
- **PayPal only for billing** — No Stripe or alternative payment providers without explicit approval.
- **Stale Redis workers** — Workers that crash don't de-register. Manually `DEL vrbot:worker:<id>` or flush `vrbot:workers:active`.

## Skills

| Skill | Path | Description |
|-------|------|-------------|
| **new-task** | `.claude/skills/new-task/SKILL.md` | Reusable workflow for creating new VRBOT game automation tasks with standard template, COORDS dict, and checklist |
| **debug-farm** | `.claude/skills/debug-farm/SKILL.md` | Step-by-step debugging for farms showing error status (ValueError, ADB, black screen, Redis, stuck tasks) |
| **deploy** | `.claude/skills/deploy/SKILL.md` | Deploy pipeline for Hetzner backend (port 8889) and Vercel frontend with pre/post-deploy checks |
| **add-rule** | `.claude/skills/add-rule/SKILL.md` | Workflow for adding lessons learned to CLAUDE.md after every bug fix |

### Pre-Commit Hook

A Python pre-commit hook (`.git/hooks/pre-commit`) runs automatically before every commit and validates:
- `TASK_NAME` constant exists in task files
- `execute()` method exists
- `get_next_run()` method exists
- No hardcoded `192.168.x.x` IPs
- Warns (does not block) when committing directly to `main`
