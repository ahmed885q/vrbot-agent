"""BuildAgent — Construction, research, and training specialist."""

from ultra_agent.agents.base_agent import BaseAgent


class BuildAgent(BaseAgent):
    NAME = "build"
    TASKS = ["construction", "research", "train_troops", "heal_troops", "upgrade_chief_hall"]
    COOLDOWN_SEC = 300  # Building takes time, no need to check often

    def get_tasks(self, context: dict) -> list[str]:
        # Prioritize construction > research > training
        tasks = ["construction", "research", "train_troops"]
        if context.get("wounded", 0) > 0:
            tasks.insert(0, "heal_troops")  # Heal first
        return tasks
