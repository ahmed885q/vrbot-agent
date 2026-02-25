"""Task: Festival of Flames — Event rewards claiming."""

from tasks.base_task import EventTask


class TaskFestivalFlames(EventTask):
    name = "Festival of Flames"
    tag = "festival_flames"
    cooldown_hours = 12
    icon_desc = (
        "the Festival of Flames event icon — a torch, bonfire, or flame-themed "
        "icon, usually on the right side event panel"
    )
    claim_desc = "a Claim, Collect, or Reward button"
    max_claims = 5
