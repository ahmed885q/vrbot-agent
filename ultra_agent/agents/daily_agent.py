"""DailyAgent — Time-sensitive daily tasks specialist."""

from ultra_agent.agents.base_agent import BaseAgent


class DailyAgent(BaseAgent):
    NAME = "daily"
    TASKS = [
        "mail_rewards", "hall_of_valor", "prosperity", "helps",
        "daily_gifts", "commissions", "rewards", "surprise_gift",
    ]
    COOLDOWN_SEC = 300

    def get_tasks(self, context: dict) -> list[str]:
        done = set(context.get("daily_done", []))
        return [t for t in self.TASKS if t not in done]
