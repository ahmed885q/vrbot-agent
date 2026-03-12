"""Task: Conquer the Island — New account progression event claiming."""
from tasks.base_task import EventTask


class TaskConquerIsland(EventTask):
    name = "Conquer the Island"
    tag = "conquer_island"
    cooldown_hours = 12
    icon_desc = "Conquer the Island event icon — an island or map icon on the right side panel"
    claim_desc = "a Claim or Collect rewards button (green or highlighted)"
    max_claims = 5
