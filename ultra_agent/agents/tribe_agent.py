"""TribeAgent — Alliance and tribe tasks specialist."""

from ultra_agent.agents.base_agent import BaseAgent


class TribeAgent(BaseAgent):
    NAME = "tribe"
    TASKS = ["tribe_tech", "tribe_gifts", "helps", "tribe_gold_tile"]
    COOLDOWN_SEC = 600  # Tribe tasks are once-a-day mostly

    def get_tasks(self, context: dict) -> list[str]:
        tasks = ["tribe_tech", "tribe_gifts", "helps"]
        if context.get("tribe_event_active"):
            tasks.append("tribe_gold_tile")
        return tasks
