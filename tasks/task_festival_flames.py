"""Task: Festival of Flames — Claim event rewards."""
from tasks.base_task import EventTask


class TaskFestivalFlames(EventTask):
    name = "Festival of Flames"
    tag = "festival_flames"
    cooldown_hours = 8
    icon_desc = "Festival of Flames event icon — a flame or torch icon on the right side panel"
    claim_desc = "a Claim or Collect button (green or orange)"
    max_claims = 5
