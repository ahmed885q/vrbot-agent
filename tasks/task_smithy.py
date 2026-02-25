"""Task: Smithy Conquest — Craft and upgrade equipment."""

from tasks.base_task import BuildingTask


class TaskSmithy(BuildingTask):
    name = "Smithy Conquest"
    tag = "smithy"
    cooldown_hours = 6
    building_desc = (
        "the Smithy or Forge building — looks like an anvil, hammer, or workshop. "
        "May have a craft/gear icon above it."
    )
    action_desc = "a 'Craft', 'Forge', 'Upgrade', or 'Conquest' button"
    confirm_desc = "a 'Confirm', 'Craft', or 'Start' button"
