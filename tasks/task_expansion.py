"""Task: Expansion — Build expansion plots to increase prosperity."""
from tasks.base_task import BuildingTask


class TaskExpansion(BuildingTask):
    name = "Expansion Build"
    tag = "expansion"
    cooldown_hours = 1
    building_desc = (
        "an empty expansion plot — a green glowing square or a buildable empty land "
        "with a hammer/build icon. It looks different from existing buildings."
    )
    action_desc = "a Build or Construct button (green)"
    confirm_desc = "a Confirm, Start, or Build button"
