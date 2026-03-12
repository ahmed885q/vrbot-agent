"""Task: Gather Supplies — Collect supply drops and resource packs from event."""
from tasks.base_task import EventTask


class TaskGatherSupplies(EventTask):
    name = "Gather Supplies"
    tag = "gather_supplies"
    cooldown_hours = 6
    icon_desc = "Gather Supplies event icon — a supply crate or package icon on the right panel"
    claim_desc = "a Collect, Claim, or Open button (green)"
    max_claims = 5
