"""Task: Train Troops — Recruit troops from Barracks."""

from tasks.base_task import BuildingTask


class TaskTrainTroops(BuildingTask):
    name = "Train Troops"
    tag = "train_troops"
    cooldown_hours = 2
    building_desc = (
        "the Barracks building — where troops are trained/recruited. "
        "Look for a military building with a sword, shield, or troop icon."
    )
    action_desc = "a 'Train', 'Recruit', or 'Queue' button"
    confirm_desc = "a 'Confirm' or 'Train' button (green)"
