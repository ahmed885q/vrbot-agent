"""
UltraCoordinator — Main orchestrator for the Ultra Agent system.

Cycle:
  1. Take screenshot → VisionAI analyzes
  2. MetaBrain decides which agent runs
  3. Selected agent executes its tasks
  4. SmartRetry handles failures
  5. Results logged to Supabase (if available)
"""

import logging
import time
from typing import Optional

from ultra_agent.vision import VisionAI
from ultra_agent.meta_brain import MetaBrain
from ultra_agent.agents import ALL_AGENTS

log = logging.getLogger("ultra.coordinator")


class UltraCoordinator:
    """
    Main entry point for Ultra Agent.

    Usage:
        from ultra_agent import UltraCoordinator
        ultra = UltraCoordinator(farm_name="farm_001")
        ultra.run_cycle(bot, run_task_fn, smart_retry)
    """

    def __init__(self, farm_name: str, supabase=None):
        self.farm_name = farm_name
        self.vision = VisionAI()
        self.brain = MetaBrain()
        self.agents = {name: cls() for name, cls in ALL_AGENTS.items()}
        self.supabase = supabase
        self.cycle_count = 0
        self.total_tasks_ok = 0
        self.total_tasks_fail = 0

    def run_cycle(self, bot, run_task_fn, smart_retry=None, context: Optional[dict] = None) -> dict:
        """
        Run one Ultra Agent cycle.

        Args:
            bot: Bot instance with adb, go_to_city(), etc.
            run_task_fn: The run_task(bot, task_name, smart_retry=sr) function
            smart_retry: SmartRetry instance
            context: Optional dict with game state hints

        Returns:
            Cycle result dict with agent used, tasks completed, etc.
        """
        self.cycle_count += 1
        cycle_start = time.time()
        ctx = context or {}

        # 1. Screenshot + Vision analysis
        screen = self._take_screenshot(bot)
        analysis = self.vision.analyze(screen)
        log.info("[Cycle %d] Screen: type=%s, brightness=%.0f, variance=%.0f",
                 self.cycle_count, analysis.screen_type, analysis.brightness, analysis.variance)

        # 2. MetaBrain decides
        decision = self.brain.decide(analysis.screen_type, ctx)

        # 3. Get the agent
        agent = self.agents.get(decision.agent)
        if not agent:
            log.error("[Cycle %d] Unknown agent: %s", self.cycle_count, decision.agent)
            return {"ok": False, "error": f"unknown agent: {decision.agent}"}

        # 4. Execute
        log.info("[Cycle %d] Agent=%s, reason=%s", self.cycle_count, decision.agent, decision.reason)
        result = agent.execute(bot, run_task_fn, smart_retry=smart_retry)

        # 5. Record result in brain
        self.brain.record_result(decision.agent, result["ok"],
                                  cooldown_sec=agent.COOLDOWN_SEC)

        # 6. Update stats
        self.total_tasks_ok += result.get("tasks_ok", 0)
        self.total_tasks_fail += result.get("tasks_run", 0) - result.get("tasks_ok", 0)

        # 7. Log to Supabase
        self._log_to_supabase(decision, result, analysis)

        cycle_ms = int((time.time() - cycle_start) * 1000)
        result["cycle"] = self.cycle_count
        result["cycle_ms"] = cycle_ms
        result["screen_type"] = analysis.screen_type

        log.info("[Cycle %d] Done: %s — %d/%d tasks OK (%dms)",
                 self.cycle_count, decision.agent,
                 result.get("tasks_ok", 0), result.get("tasks_run", 0), cycle_ms)

        return result

    def run_loop(self, bot, run_task_fn, smart_retry=None,
                 max_cycles: int = 0, cycle_delay: float = 30):
        """
        Run Ultra Agent in a continuous loop.

        Args:
            max_cycles: 0 = infinite
            cycle_delay: seconds between cycles
        """
        log.info("=== Ultra Agent starting for %s ===", self.farm_name)
        cycle = 0
        while max_cycles == 0 or cycle < max_cycles:
            cycle += 1
            try:
                result = self.run_cycle(bot, run_task_fn, smart_retry)
                if result.get("ok"):
                    time.sleep(cycle_delay)
                else:
                    time.sleep(cycle_delay * 2)  # Back off on failure
            except KeyboardInterrupt:
                log.info("Ultra Agent stopped by user")
                break
            except Exception as e:
                log.error("Cycle error: %s", e, exc_info=True)
                time.sleep(60)

        log.info("=== Ultra Agent stopped: %d cycles, %d OK, %d FAIL ===",
                 self.cycle_count, self.total_tasks_ok, self.total_tasks_fail)

    def _take_screenshot(self, bot) -> bytes:
        try:
            if hasattr(bot, "adb"):
                return bot.adb.screenshot() or b""
            return bot.screenshot() or b""
        except Exception:
            return b""

    def _log_to_supabase(self, decision, result, analysis):
        if not self.supabase:
            return
        try:
            self.supabase.table("ultra_agent_logs").insert({
                "farm_name": self.farm_name,
                "agent_used": decision.agent,
                "action": decision.reason,
                "result": "ok" if result.get("ok") else "fail",
                "screen_state": {
                    "type": analysis.screen_type,
                    "brightness": analysis.brightness,
                    "hash": analysis.screen_hash,
                },
                "duration_ms": result.get("duration_ms", 0),
            }).execute()
        except Exception as e:
            log.debug("Supabase log failed: %s", e)

    def get_stats(self) -> dict:
        return {
            "farm_name": self.farm_name,
            "cycles": self.cycle_count,
            "total_ok": self.total_tasks_ok,
            "total_fail": self.total_tasks_fail,
            "brain": self.brain.get_stats(),
            "agents": {name: agent.get_stats() for name, agent in self.agents.items()},
        }
