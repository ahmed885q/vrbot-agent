"""DefenseAgent — Attack detection, resource protection, shields."""

import logging
import time
from ultra_agent.agents.base_agent import BaseAgent

log = logging.getLogger("ultra.defense")


class DefenseAgent(BaseAgent):
    NAME = "defense"
    TASKS = ["shield", "wall_repair"]
    COOLDOWN_SEC = 30  # Check often for attacks

    def can_run(self, context: dict) -> bool:
        # Defense always runs its check, ignoring cooldown if under attack
        if context.get("under_attack"):
            return True
        return super().can_run(context)

    def execute(self, bot, run_task_fn, smart_retry=None) -> dict:
        self.last_run = time.time()
        self.run_count += 1
        start = time.time()

        under_attack = self._check_attack(bot)

        if under_attack:
            log.warning("[Defense] UNDER ATTACK — activating shield!")
            result = run_task_fn(bot, "shield", smart_retry=smart_retry)
            ok = bool(result)
            if ok:
                self.success_count += 1
            return {
                "ok": ok, "agent": self.NAME,
                "tasks_run": 1, "tasks_ok": 1 if ok else 0,
                "tasks_total": 1,
                "duration_ms": int((time.time() - start) * 1000),
                "alert": "under_attack",
            }

        # Routine check — no attack
        return {
            "ok": True, "agent": self.NAME,
            "tasks_run": 0, "tasks_ok": 0, "tasks_total": 0,
            "duration_ms": int((time.time() - start) * 1000),
            "alert": None,
        }

    def _check_attack(self, bot) -> bool:
        """Check if the city is under attack by looking for attack notifications."""
        try:
            screenshot = bot.adb.screenshot() if hasattr(bot, "adb") else None
            if not screenshot:
                return False
            # Check for red attack indicators in the screenshot
            # This is a heuristic — bright red pixels in the notification area
            # Top 10% of screenshot, check for high red values
            sample = screenshot[:len(screenshot) // 10]
            red_count = sum(1 for i in range(0, len(sample) - 2, 3)
                           if sample[i] > 200 and sample[i + 1] < 80 and sample[i + 2] < 80)
            return red_count > 50
        except Exception:
            return False
