"""Task: Gather Supplies — Collect supply drops and resource packs."""

from tasks.base_task import EventTask


class TaskGatherSupplies(EventTask):
    name = "Gather Supplies"
    tag = "gather_supplies"
    cooldown_hours = 8
    icon_desc = (
        "the Gather Supplies or Supply Drop icon — a crate, supply box, "
        "or resource bundle icon on the city screen or events panel"
    )
    claim_desc = "a 'Gather', 'Collect', 'Claim', or 'Open' button"
    max_claims = 5
