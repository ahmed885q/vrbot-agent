"""Task: Surprise Gift Box — Collect surprise gift boxes that appear in city."""
from tasks.base_task import EventTask


class TaskSurpriseGift(EventTask):
    name = "Surprise Gift Box"
    tag = "surprise_gift"
    cooldown_hours = 4
    icon_desc = "a floating gift box icon — a colorful present/gift that pops up on the city screen"
    claim_desc = "an Open, Collect, or Claim button"
    max_claims = 3
