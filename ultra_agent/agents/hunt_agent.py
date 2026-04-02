"""HuntAgent — Monster and Niflung hunting specialist."""

from ultra_agent.agents.base_agent import BaseAgent


class HuntAgent(BaseAgent):
    NAME = "hunt"
    TASKS = ["kill_monster", "niflung", "rally_niflung"]
    COOLDOWN_SEC = 180

    def can_run(self, context: dict) -> bool:
        if not super().can_run(context):
            return False
        return context.get("stamina", 20) >= 10

    def get_tasks(self, context: dict) -> list[str]:
        tasks = ["kill_monster"]
        stamina = context.get("stamina", 0)
        if stamina >= 30:
            tasks.append("niflung")
        if context.get("rally_available"):
            tasks.append("rally_niflung")
        return tasks
