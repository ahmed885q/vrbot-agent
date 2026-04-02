from ultra_agent.agents.gather_agent import GatherAgent
from ultra_agent.agents.hunt_agent import HuntAgent
from ultra_agent.agents.build_agent import BuildAgent
from ultra_agent.agents.daily_agent import DailyAgent
from ultra_agent.agents.tribe_agent import TribeAgent
from ultra_agent.agents.defense_agent import DefenseAgent

ALL_AGENTS = {
    "gather": GatherAgent,
    "hunt": HuntAgent,
    "build": BuildAgent,
    "daily": DailyAgent,
    "tribe": TribeAgent,
    "defense": DefenseAgent,
}

__all__ = ["ALL_AGENTS", "GatherAgent", "HuntAgent", "BuildAgent",
           "DailyAgent", "TribeAgent", "DefenseAgent"]
