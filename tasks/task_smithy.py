"""Task: Smithy Conquest — Craft and upgrade equipment at the Smithy."""
from tasks.base_task import BuildingTask


class TaskSmithy(BuildingTask):
    name = "Smithy Conquest"
    tag = "smithy"
    cooldown_hours = 4
    building_desc = (
        "the Smithy building — a forge/anvil building where equipment is crafted. "
        "Usually has a hammer or anvil icon."
    )
    action_desc = "a Craft, Forge, or Upgrade button"
    confirm_desc = "a Confirm, Craft, or Start button"
