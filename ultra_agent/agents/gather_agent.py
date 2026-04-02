"""GatherAgent — Resource collection specialist."""

from ultra_agent.agents.base_agent import BaseAgent


class GatherAgent(BaseAgent):
    NAME = "gather"
    TASKS = ["gather", "gather_supplies", "gather_boost"]
    COOLDOWN_SEC = 120  # Gather has long march times

    def can_run(self, context: dict) -> bool:
        if not super().can_run(context):
            return False
        return context.get("marches_idle", 1) > 0

    def get_tasks(self, context: dict) -> list[str]:
        # Only run gather_boost if we have items for it
        tasks = ["gather"]
        if context.get("has_gather_boost"):
            tasks.append("gather_boost")
        return tasks
