"""Task: Rebate Pack Event — Claim rebate packs (new account)."""

from tasks.base_task import EventTask


class TaskRebatePack(EventTask):
    name = "Rebate Pack"
    tag = "rebate_pack"
    cooldown_hours = 24
    icon_desc = (
        "the Rebate Pack or New Player event icon — a special offer, gift, "
        "or pack icon with a discount badge. Usually in the events panel"
    )
    claim_desc = "a 'Claim', 'Collect', 'Free', or 'Redeem' button"
    max_claims = 3
