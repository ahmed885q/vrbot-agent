"""Task: Community Events — Claim community rewards and link rewards (1k crystals)."""

from tasks.base_task import EventTask


class TaskCommunityEvents(EventTask):
    name = "Community Events"
    tag = "community_events"
    cooldown_hours = 24
    icon_desc = (
        "a Community Event, Social, or Link Reward icon — may show a group of "
        "people, community badge, or social media icon on the events panel"
    )
    claim_desc = "a 'Claim', 'Collect', 'Redeem', or 'Link' button"
    max_claims = 5
