"""Task: Toy Shop — Collect toys and claim rewards."""

from tasks.base_task import EventTask


class TaskToyShop(EventTask):
    name = "Toy Shop"
    tag = "toy_shop"
    cooldown_hours = 12
    icon_desc = (
        "the Toy Shop event icon — a toy, gift box, or shop-themed icon. "
        "Usually on the right side event panel"
    )
    claim_desc = "a 'Claim', 'Collect', 'Exchange', or 'Buy' button"
    max_claims = 5
