"""Task: Toy Shop — Collect toys and claim event rewards."""
from tasks.base_task import EventTask


class TaskToyShop(EventTask):
    name = "Toy Shop"
    tag = "toy_shop"
    cooldown_hours = 12
    icon_desc = "Toy Shop event icon — a toy or shop icon on the right side panel"
    claim_desc = "a Collect, Claim, or Exchange button (green)"
    max_claims = 5
