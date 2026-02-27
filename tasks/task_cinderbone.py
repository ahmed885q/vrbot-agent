"""Task: Cinderbone Soulburn — Collect event rewards from Cinderbone event."""
from tasks.base_task import EventTask


class TaskCinderbone(EventTask):
    name = "Cinderbone Soulburn"
    tag = "cinderbone"
    cooldown_hours = 8
    icon_desc = "Cinderbone Soulburn event icon — a fire/skull icon on the right side panel"
    claim_desc = "a Claim or Collect button (green or orange)"
    max_claims = 5
