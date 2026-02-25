"""Task: Conquer the Island — New account progression event."""

from tasks.base_task import EventTask


class TaskConquerIsland(EventTask):
    name = "Conquer the Island"
    tag = "conquer_island"
    cooldown_hours = 12
    icon_desc = (
        "the Conquer the Island event icon — an island, map, or exploration "
        "themed icon. Usually in the events panel for new accounts"
    )
    claim_desc = "a 'Claim', 'Collect', 'Conquer', or 'Complete' button"
    max_claims = 5
