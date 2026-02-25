"""Task: Surprise Gift Box — Collect surprise gift boxes."""

from tasks.base_task import EventTask


class TaskSurpriseGift(EventTask):
    name = "Surprise Gift Box"
    tag = "surprise_gift"
    cooldown_hours = 12
    icon_desc = (
        "the Surprise Gift Box icon — a gift box, present, or mystery box icon. "
        "Usually floating on the city screen or in the events panel"
    )
    claim_desc = "an 'Open', 'Claim', or 'Collect' button"
    max_claims = 3
