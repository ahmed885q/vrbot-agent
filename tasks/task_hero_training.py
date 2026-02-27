"""Task: Hero Training — Train heroes via Squad Base building."""
from tasks.base_task import BuildingTask


class TaskHeroTraining(BuildingTask):
    name = "Hero Training"
    tag = "hero_training"
    cooldown_hours = 4
    building_desc = (
        "the Squad Base building — a military-looking building where heroes train. "
        "It may have a hero icon or training indicator above it."
    )
    action_desc = "a Train, Start Training, or Level Up button"
    confirm_desc = "a Confirm or Start button"
