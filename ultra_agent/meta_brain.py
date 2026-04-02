"""
MetaBrain — Decides which specialist agent runs next.

Priority logic:
  1. Defense agent always checks first (protect resources)
  2. Daily tasks if near reset time (UTC 00:00)
  3. Gather if marches are idle
  4. Build/Research if resources are high
  5. Tribe tasks if alliance events active
  6. Hunt if stamina available

Each decision is logged for learning.
"""

import logging
import time
from datetime import datetime, timezone
from dataclasses import dataclass
from typing import Optional

log = logging.getLogger("ultra.brain")


@dataclass
class Decision:
    agent: str
    priority: int
    reason: str
    screen_type: str
    timestamp: float


class MetaBrain:
    """Selects the best agent for the current game state."""

    # Agent priority weights (higher = more important)
    WEIGHTS = {
        "defense": 100,  # Always check first
        "daily":    80,  # Time-sensitive
        "gather":   60,  # Core income
        "build":    50,  # Growth
        "tribe":    40,  # Alliance
        "hunt":     30,  # Optional
    }

    # Hours before UTC reset where daily tasks get boosted
    DAILY_URGENCY_HOURS = 4

    def __init__(self):
        self.last_decisions: list[Decision] = []
        self._cooldowns: dict[str, float] = {}  # agent → next_allowed_time
        self._fail_counts: dict[str, int] = {}

    def decide(self, screen_type: str, context: dict) -> Decision:
        """
        Choose the best agent based on screen state and context.

        context keys:
          - marches_idle: int (idle march slots)
          - resources: dict (gold, food, wood, stone)
          - under_attack: bool
          - stamina: int
          - daily_done: list[str] (completed daily tasks)
          - tribe_event_active: bool
          - hour_utc: int (current UTC hour, auto-filled if missing)
        """
        now = time.time()
        hour = context.get("hour_utc", datetime.now(timezone.utc).hour)

        scores: dict[str, tuple[int, str]] = {}

        # Defense — always first if under attack
        if context.get("under_attack"):
            scores["defense"] = (200, "under_attack")
        else:
            scores["defense"] = (10, "routine_check")

        # Daily — urgency near reset
        hours_to_reset = (24 - hour) % 24
        daily_done = set(context.get("daily_done", []))
        daily_remaining = {"mail_rewards", "hall_of_valor", "prosperity",
                           "helps", "daily_gifts"} - daily_done
        if daily_remaining:
            urgency = 80 if hours_to_reset <= self.DAILY_URGENCY_HOURS else 40
            scores["daily"] = (urgency, f"{len(daily_remaining)} tasks left, {hours_to_reset}h to reset")
        else:
            scores["daily"] = (0, "all done")

        # Gather — if marches idle
        marches = context.get("marches_idle", 0)
        if marches > 0:
            scores["gather"] = (60 + marches * 10, f"{marches} idle marches")
        else:
            scores["gather"] = (5, "no idle marches")

        # Build — if resources high
        resources = context.get("resources", {})
        gold = resources.get("gold", 0)
        if gold > 500000:
            scores["build"] = (55, f"gold={gold}")
        else:
            scores["build"] = (20, "low resources")

        # Tribe — if event active
        if context.get("tribe_event_active"):
            scores["tribe"] = (70, "event active")
        else:
            scores["tribe"] = (30, "routine")

        # Hunt — if stamina available
        stamina = context.get("stamina", 0)
        if stamina >= 20:
            scores["hunt"] = (35, f"stamina={stamina}")
        else:
            scores["hunt"] = (5, "low stamina")

        # Apply cooldowns — penalize recently-run agents
        for agent, (score, reason) in list(scores.items()):
            cd = self._cooldowns.get(agent, 0)
            if now < cd:
                scores[agent] = (max(0, score - 50), reason + " (cooldown)")

            # Penalize agents that keep failing
            fails = self._fail_counts.get(agent, 0)
            if fails >= 3:
                scores[agent] = (max(0, score - 30), reason + f" ({fails} fails)")

        # Screen-type adjustments
        if screen_type == "menu":
            # If stuck in a menu, daily agent is best at closing dialogs
            scores["daily"] = (scores["daily"][0] + 20, scores["daily"][1] + " +menu_bonus")
        elif screen_type == "world_map":
            # World map = good for gather/hunt
            scores["gather"] = (scores["gather"][0] + 15, scores["gather"][1] + " +world_bonus")
            scores["hunt"] = (scores["hunt"][0] + 15, scores["hunt"][1] + " +world_bonus")

        # Pick highest score
        best_agent = max(scores, key=lambda a: scores[a][0])
        best_score, best_reason = scores[best_agent]

        decision = Decision(
            agent=best_agent,
            priority=best_score,
            reason=best_reason,
            screen_type=screen_type,
            timestamp=now,
        )

        self.last_decisions.append(decision)
        if len(self.last_decisions) > 50:
            self.last_decisions = self.last_decisions[-50:]

        log.info("[Brain] → %s (score=%d, reason=%s)", best_agent, best_score, best_reason)
        return decision

    def record_result(self, agent: str, success: bool, cooldown_sec: float = 60):
        """Record agent result for future decisions."""
        if success:
            self._fail_counts[agent] = 0
            self._cooldowns[agent] = time.time() + cooldown_sec
        else:
            self._fail_counts[agent] = self._fail_counts.get(agent, 0) + 1

    def get_stats(self) -> dict:
        return {
            "total_decisions": len(self.last_decisions),
            "cooldowns": {k: round(v - time.time(), 1) for k, v in self._cooldowns.items() if v > time.time()},
            "fail_counts": dict(self._fail_counts),
            "last_5": [{"agent": d.agent, "score": d.priority, "reason": d.reason}
                        for d in self.last_decisions[-5:]],
        }
