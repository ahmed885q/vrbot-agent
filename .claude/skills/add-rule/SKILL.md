# Skill: Add Lesson Learned to CLAUDE.md

## When to Use
After every bug fix, incident resolution, or discovery of a non-obvious project behavior. This ensures the team (and Claude) never repeats the same mistake.

## Workflow

### Step 1: Identify the Lesson
After fixing a bug, ask:
- What was the root cause?
- Was it non-obvious or counter-intuitive?
- Would reading the code alone reveal this, or does it require context?

If the answer to the last question is "requires context" — it belongs in CLAUDE.md.

### Step 2: Write the Rule
Format each rule as a single, actionable line in the `## Rules` section of `CLAUDE.md`:
```markdown
- **<Short title>** — <What to do or not do>. <Why>.
```

### Step 3: Verify No Duplicate
Search CLAUDE.md for keywords from your new rule before adding it. Update existing rules if the new info refines them.

### Step 4: Commit
```bash
git add CLAUDE.md
git commit -m "docs: add lesson learned — <short description>"
```

## Master Rules List (All Known VRBOT Bugs)

These are the accumulated lessons from all past VRBOT incidents. All should be present in CLAUDE.md:

1. **Never create a `queue/` folder** — It shadows Python's stdlib `queue` module, causing `ImportError` across the entire project.
2. **Never `sed` across `venv/`** — Bulk find-and-replace that touches virtual environment files corrupts installed packages silently.
3. **Port 8889 = v2 orchestrator** — Port 8888 was legacy. All API calls, health checks, and farm communication use 8889.
4. **CORS is nginx-only** — Adding CORS middleware in Python causes duplicate headers and breaks browser preflight requests.
5. **`GPCSDKMainActivity` not `MainActivity`** — The Viking Rise game activity class changed. Using the wrong one causes black screen on launch.
6. **`go_to_city()` zooms camera out** — Always re-zoom after calling this if the task needs a specific zoom level.
7. **Hardcoded coord fallback required** — Every `_tap_ui()` must have a fallback `(x, y)` for when YOLO/template detection fails.
8. **Gather march button at (951, 462)** — Proven reliable coordinate; use as calibration reference.
9. **`int("JobPriority.HIGH")` ValueError** — Enum names get serialized as strings; always use `.value` before `int()` conversion.
10. **Never push directly to main** — Vercel auto-deploys from main. Broken pushes immediately break the production dashboard.
11. **Test on LDPlayer before Hetzner** — Screen DPI differences between local and cloud can break coordinate-based tasks.
12. **No hardcoded `192.168.x.x` IPs** — Local network IPs don't resolve on Hetzner. Use `cloud.vrbot.me` or env vars.
13. **Anti-ban delays mandatory** — Never fire taps in rapid succession. Always `time.sleep(random.uniform(1.5, 4.0))` between taps.
14. **Use `logging`, not `print()`** — All tasks must use structured logging via `logging.getLogger("vrbot.task")`.
15. **Vercel cron path is `/api/cron/run-tasks`** — Fires 4x daily. Don't rename or relocate without updating Vercel cron config.
16. **PayPal only for billing** — No Stripe or alternative payment providers without explicit approval.
17. **Stale Redis workers** — Workers that crash don't de-register. Manually `DEL vrbot:worker:<id>` or flush `vrbot:workers:active`.
