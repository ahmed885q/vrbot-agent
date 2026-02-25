"""Task: Expansion — Build expansion plots at level 5 until prosperity 4."""

from tasks.base_task import BuildingTask


class TaskExpansion(BuildingTask):
    name = "Expansion Build"
    tag = "expansion"
    cooldown_hours = 2
    building_desc = (
        "an empty plot or expansion area marked with a '+' icon or 'Build' sign "
        "at the edge/outskirts of the city walls. These are new building slots."
    )
    action_desc = "a 'Build' or 'Construct' button to start a new building"
    confirm_desc = "a 'Confirm' or 'Build' button (green)"
