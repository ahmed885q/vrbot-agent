# Skill: Create New VRBOT Game Automation Task

## When to Use
When creating a new task file in `tasks/` for automating a Viking Rise game action.

## Task Template

Every new task MUST follow this structure:

```python
"""
Task: <TaskDescription>
Features:
- <bullet list of what it automates>
- Anti-ban delays between all actions
- Human-like behavior patterns
"""

import time
import random
import logging
from tasks.base_task import BaseTask, cooldown_ok, cooldown_save

log = logging.getLogger("vrbot.task")

# === TASK IDENTITY ===
TASK_NAME = "task_<snake_name>"

# === COORDINATES (LDPlayer 1280x720) ===
COORDS = {
    "button_name": (x, y),
    # Always provide hardcoded fallback coordinates
}


class Task<PascalName>(BaseTask):
    name = "<Human Readable Name>"
    tag = TASK_NAME
    cooldown_hours = 4  # adjust per task

    def __init__(self, bot):
        super().__init__(bot)

    def execute(self):
        """Main task logic. Called by the scheduler."""
        if not cooldown_ok(self.tag, self.cooldown_hours):
            return
        log.info(f"[{self.tag}] Starting execution")
        try:
            self._run()
            cooldown_save(self.tag)
        except Exception as e:
            log.error(f"[{self.tag}] Failed: {e}")

    def _run(self):
        """Internal execution — override with task-specific logic."""
        bot = self.bot
        bot.go_to_city()
        # ... task-specific taps and logic ...

    @staticmethod
    def get_next_run():
        """Return datetime of next scheduled run, or None for on-demand."""
        return None
```

## 4-Step Checklist

Before marking a new task complete, verify:

1. **TASK_NAME constant** — must exist as a module-level string, matching the filename without `.py`
2. **`execute()` method** — entry point called by the scheduler; must handle cooldown
3. **`get_next_run()` method** — static method returning next scheduled datetime or None
4. **COORDS dict** — all screen coordinates in a single dict with hardcoded fallback values

## Known Pitfalls

- **Hardcoded coord fallback always required**: Detection (YOLO/template) can fail — every `_tap_ui()` call must have a fallback `(x, y)` coordinate that works on LDPlayer 1280x720.
- **`go_to_city()` zooms camera out**: After calling `bot.go_to_city()`, the camera is zoomed out to max. If your task needs a specific zoom level, zoom in explicitly before interacting with buildings.
- **Test on LDPlayer before Hetzner**: Always verify coordinates and tap sequences locally on LDPlayer (1280x720) before deploying to the Hetzner cloud farms. Screen DPI and resolution differences can break tasks.
- **Gather march proven at (951, 462)**: The "march" confirmation button for gather tasks is reliably at `(951, 462)`. Use this as reference when calibrating nearby coordinates.
- **Anti-ban delays**: Always add `time.sleep(random.uniform(1.5, 4.0))` between consecutive taps. Never fire taps in rapid succession.
- **Never use `print()`**: Use `log.info()` / `log.error()` from the `logging` module. The base task sets up structured logging.
