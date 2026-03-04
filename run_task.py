"""
VRBOT Task Runner - Run individual tasks for testing.

Usage: python run_task.py helps
"""

import sys
import importlib
from vrbot_core import Bot

TASK_MAP = {
    # Phase 2: Quick Collections
    "helps": ("tasks.task_helps", "TaskHelps"),
    "tribe_gifts": ("tasks.task_tribe_gifts", "TaskTribeGifts"),
    "mail_rewards": ("tasks.task_mail_rewards", "TaskMailRewards"),
    "daily_gifts": ("tasks.task_daily_gifts", "TaskDailyGifts"),
    "rewards": ("tasks.task_rewards", "TaskRewards"),
    "shield": ("tasks.task_shield", "TaskShield"),
    # Phase 3: Production
    "construction": ("tasks.task_construction", "TaskConstruction"),
    "research": ("tasks.task_research", "TaskResearch"),
    "train_troops": ("tasks.task_train_troops", "TaskTrainTroops"),
    "prosperity": ("tasks.task_prosperity", "TaskProsperity"),
    # Phase 4: Economy
    "errands": ("tasks.task_errands", "TaskErrands"),
    "commissions": ("tasks.task_commissions", "TaskCommissions"),
    "farmer_appointments": ("tasks.task_farmer_appointments", "TaskFarmerAppointments"),
    "recruit_farmers": ("tasks.task_recruit_farmers", "TaskRecruitFarmers"),
    "village_champions": ("tasks.task_village_champions", "TaskVillageChampions"),
    # Phase 5: Heroes
    "hall_of_valor": ("tasks.task_hall_of_valor", "TaskHallOfValor"),
    "hero_xp": ("tasks.task_hero_xp", "TaskHeroXp"),
    "hero_training": ("tasks.task_hero_training", "TaskHeroTraining"),
    "account_items": ("tasks.task_account_items", "TaskAccountItems"),
    "divination": ("tasks.task_divination", "TaskDivination"),
    "smithy": ("tasks.task_smithy", "TaskSmithy"),
    # Phase 6: Combat
    "gather": ("tasks.task_gather", "TaskGather"),
    "niflung": ("tasks.task_niflung", "TaskNiflung"),
    "staging_post": ("tasks.task_staging_post", "TaskStagingPost"),
    "clear_forest": ("tasks.task_clear_forest", "TaskClearForest"),
    "cinderbone": ("tasks.task_cinderbone", "TaskCinderbone"),
    "reclaim_midgard": ("tasks.task_reclaim_midgard", "TaskReclaimMidgard"),
    # Phase 7: Events
    "leidolf": ("tasks.task_leidolf", "TaskLeidolf"),
    "festival_flames": ("tasks.task_festival_flames", "TaskFestivalFlames"),
    "promo_codes": ("tasks.task_promo_codes", "TaskPromoCodes"),
    # Phase 8: Strategy
    "chief_hall": ("tasks.task_chief_hall", "TaskChiefHall"),
    "upgrade_chief_hall": ("tasks.task_upgrade_chief_hall", "TaskUpgradeChiefHall"),
    "expansion": ("tasks.task_expansion", "TaskExpansion"),
    "tribe_tech": ("tasks.task_tribe_tech", "TaskTribeTech"),
    "chapter": ("tasks.task_chapter", "TaskChapter"),
    "city_rush": ("tasks.task_city_rush_v2", "TaskCityRush"),
}

def run(task_name):
    if task_name not in TASK_MAP:
        print(f"Unknown task: {task_name}")
        print(f"Available: {list(TASK_MAP.keys())}")
        return
    module_name, class_name = TASK_MAP[task_name]
    mod = __import__(module_name, fromlist=[class_name])
        # Force reload to pick up code changes without worker restart
    importlib.reload(mod)
