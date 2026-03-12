"""Task: Community Events — Claim community rewards and link rewards (1k crystals)."""
from tasks.base_task import EventTask


class TaskCommunityEvents(EventTask):
    name = "Community Events"
    tag = "community_events"
    cooldown_hours = 12
    icon_desc = "Community Events icon — a group/people icon or gift icon on the right side panel"
    claim_desc = "a Claim, Collect, or Link button (green or highlighted)"
    max_claims = 5
