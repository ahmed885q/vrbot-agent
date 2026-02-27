"""Task: Leidolf in Hiding — Find and defeat Leidolf event boss."""
from tasks.base_task import EventTask


class TaskLeidolf(EventTask):
    name = "Leidolf in Hiding"
    tag = "leidolf"
    cooldown_hours = 4
    icon_desc = "Leidolf in Hiding event icon — a wanted poster or villain icon on right panel"
    claim_desc = "a Search, Find, Attack, or Claim button"
    max_claims = 3
