"""Task: Rebate Pack Event — Claim rebate packs for new accounts."""
from tasks.base_task import EventTask


class TaskRebatePack(EventTask):
    name = "Rebate Pack"
    tag = "rebate_pack"
    cooldown_hours = 24
    icon_desc = "Rebate Pack event icon — a gift box or discount icon on the right side panel"
    claim_desc = "a Claim, Collect, or Open button (green or orange)"
    max_claims = 3
