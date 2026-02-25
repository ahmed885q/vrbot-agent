"""Task: Cinderbone Soulburn — Event claiming."""

from tasks.base_task import EventTask


class TaskCinderbone(EventTask):
    name = "Cinderbone Soulburn"
    tag = "cinderbone"
    cooldown_hours = 12
    icon_desc = (
        "the Cinderbone Soulburn event icon — a flame or fire-themed icon, "
        "usually on the right side panel or floating event icons"
    )
    claim_desc = "a Claim, Collect, or Reward button (green or orange)"
    max_claims = 5
