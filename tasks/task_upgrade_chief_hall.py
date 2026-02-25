"""Task: Upgrade Chief Hall — Find Chief Hall and upgrade."""

from tasks.base_task import BuildingTask


class TaskUpgradeChiefHall(BuildingTask):
    name = "Upgrade Chief Hall"
    tag = "upgrade_chief_hall"
    cooldown_hours = 2
    building_desc = (
        "the Chief Hall / Town Hall — the main, largest building in the center "
        "of the city. It may have a green upgrade arrow above it."
    )
    action_desc = "an 'Upgrade' button (green or blue)"
    confirm_desc = "a 'Confirm' or 'Upgrade' button"
