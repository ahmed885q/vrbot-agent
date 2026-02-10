"""
All Viking Rise Tasks — Master Registry
"""

from tasks.core_tasks import (
    GatherTask,
    ConstructionTask,
    ResearchTask,
    HelpsTask,
    ShieldTask,
)

from tasks.daily_tasks import (
    ErrandsTask,
    ProsperityDailyTask,
    TaskRewardsTask,
    MailRewardsTask,
    OpenDailyGiftsTask,
    OpenAccountBoundItemsTask,
)

from tasks.world_tasks import (
    ClearCityForestTask,
    ReclaimMidgardTask,
    NiflungHuntingTask,
    LeidolfInHidingTask,
    CinderboneSoulburnTask,
    FestivalOfFlamesTask,
)

from tasks.management_tasks import (
    FarmerAppointmentsTask,
    VillageChampionsTask,
    HallOfValorTask,
    HeroXPChipsTask,
    RecruitFarmersTask,
    HeroTrainingTask,
    TribeGiftsTask,
    TribeTechTask,
)

from tasks.building_tasks import (
    StagingPostTask,
    CommissionsTask,
    SmithyConquestTask,
    UpgradeChiefHallTask,
    FastChiefHallTask,
    ExpansionBuildTask,
    ConstructionSpeedupTask,
    RedeemPromoCodesTask,
    DivinationTask,
    ChapterCompletionTask,
    RebatePackTask,
    ConquerIslandTask,
    GatherSuppliesTask,
)

# ─── Master Task List (order = default priority) ───
ALL_TASKS = [
    # High priority (check frequently)
    HelpsTask,
    GatherTask,
    ConstructionTask,
    ConstructionSpeedupTask,
    ShieldTask,

    # Medium priority (regular checks)
    ResearchTask,
    ErrandsTask,
    TaskRewardsTask,
    MailRewardsTask,
    StagingPostTask,
    CommissionsTask,

    # Daily activities
    ProsperityDailyTask,
    OpenDailyGiftsTask,
    OpenAccountBoundItemsTask,
    RecruitFarmersTask,

    # Buildings & progression
    UpgradeChiefHallTask,
    FastChiefHallTask,
    ExpansionBuildTask,
    SmithyConquestTask,
    DivinationTask,
    ChapterCompletionTask,

    # Hero management
    HallOfValorTask,
    HeroXPChipsTask,
    HeroTrainingTask,

    # Village management
    FarmerAppointmentsTask,
    VillageChampionsTask,

    # World / combat
    ClearCityForestTask,
    ReclaimMidgardTask,
    NiflungHuntingTask,
    GatherSuppliesTask,

    # Tribe
    TribeGiftsTask,
    TribeTechTask,

    # Events (run less frequently)
    LeidolfInHidingTask,
    CinderboneSoulburnTask,
    FestivalOfFlamesTask,
    RebatePackTask,
    ConquerIslandTask,
    RedeemPromoCodesTask,
]

# Quick lookup
TASK_MAP = {t.id: t for t in ALL_TASKS if hasattr(t, 'id')}
