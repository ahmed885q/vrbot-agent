"""Task: Leidolf in Hiding — Find and defeat Leidolf event."""

from tasks.base_task import EventTask


class TaskLeidolf(EventTask):
    name = "Leidolf in Hiding"
    tag = "leidolf"
    cooldown_hours = 12
    icon_desc = (
        "the Leidolf in Hiding event icon — a wanted poster, shadow figure, "
        "or special event icon with a Viking/outlaw theme"
    )
    claim_desc = "a 'Hunt', 'Find', 'Attack', 'Claim', or 'Collect' button"
    max_claims = 3
